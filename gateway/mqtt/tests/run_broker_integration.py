"""隔离 Mosquitto 普通集成：只允许 loopback，P4/P5 真客户端，固定合成数据。"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import select
import socket
import struct
import subprocess
import sys
import threading
import time
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[3]
MQTT = ROOT / 'gateway/mqtt'
P4_SHA = '8dee339491cfd4edc468bb9451511d421f26db5e'
USER = 'synthetic-user'
PASSWORD = 'synthetic-mqtt-password'
TOPIC = 'mpm/v1/GW-C-001/'


def linux_path(path):
    path = Path(path).resolve()
    return '/mnt/' + path.drive[0].lower() + path.as_posix()[2:]


def extract_p4():
    # 唯一改动是测试配置指针注入，冻结 P4 TLS/MQTT 逻辑和 Paho 源仍原样编译。
    raw = subprocess.check_output(['git', 'show', P4_SHA + ':gateway/mqtt/src/gateway_transport.c'], cwd=ROOT)
    old = 'static const GatewayConfig *config = GATEWAY_CONFIG;'
    text = raw.decode('utf-8')
    assert text.count(old) == 1
    text = text.replace(old, 'extern const GatewayConfig gateway_test_config;\n'
                        'static const GatewayConfig *config = &gateway_test_config;')
    dest = MQTT / 'build/p0-broker/p4_gateway_transport.c'
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(text, encoding='utf-8')
    (dest.parent / 'p4-source-identity.json').write_text(json.dumps(
        {'commit': P4_SHA, 'original_sha256': hashlib.sha256(raw).hexdigest(),
         'shim_sha256': hashlib.sha256(dest.read_bytes()).hexdigest(),
         'shim': 'synthetic_config_pointer_only'}, indent=2), encoding='utf-8')
    return dest


def packet(kind, body=b''):
    remaining = len(body)
    prefix = bytearray([kind])
    while True:
        digit = remaining % 128
        remaining //= 128
        prefix.append(digit | (128 if remaining else 0))
        if not remaining:
            return bytes(prefix) + body


def field(value):
    value = value.encode() if isinstance(value, str) else value
    return struct.pack('!H', len(value)) + value


def read_packet(connection, timeout=5):
    # 仅为普通测试观察端解码标准 MQTT311 帧，不用于 Gateway 业务或任意目标探测。
    connection.settimeout(timeout)
    def exact(count):
        data = bytearray()
        while len(data) < count:
            part = connection.recv(count - len(data))
            if not part:
                raise EOFError('isolated MQTT socket closed')
            data.extend(part)
        return bytes(data)
    kind = exact(1)[0]
    remaining = 0
    for index in range(4):
        digit = exact(1)[0]
        remaining += (digit & 127) * (128**index)
        if not digit & 128:
            if remaining > 65536:
                raise ValueError('fixture receive capacity exceeded')
            return kind, exact(remaining)
    raise ValueError('fixture MQTT length invalid')


class Observer:
    def __init__(self, port, label, password=PASSWORD):
        self.connection = socket.create_connection(('127.0.0.1', port), timeout=5)
        body = b'\0\4MQTT\4\xc2\0\x3c' + field('synthetic-observer-' + label) + field(USER) + field(password)
        self.connection.sendall(packet(0x10, body))
        kind, data = read_packet(self.connection)
        self.accepted = kind == 0x20 and data == b'\0\0'

    def subscribe(self):
        self.connection.sendall(packet(0x82, b'\0\x01' + field(TOPIC + '#') + b'\x01'))
        kind, body = read_packet(self.connection)
        assert kind == 0x90 and body == b'\0\x01\x01'

    def message(self, suffix, timeout=5):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            kind, body = read_packet(self.connection, max(.1, deadline - time.monotonic()))
            if kind & 0xf0 != 0x30:
                continue
            length = struct.unpack('!H', body[:2])[0]
            topic = body[2:2 + length].decode()
            offset = 2 + length
            qos = (kind >> 1) & 3
            if qos:
                identifier = body[offset:offset + 2]
                offset += 2
                self.connection.sendall(packet(0x40, identifier))
            if topic == TOPIC + suffix:
                return {'topic': topic, 'qos': qos, 'retained': bool(kind & 1),
                        'payload': json.loads(body[offset:]), 'received_at': time.monotonic()}
        raise TimeoutError('expected isolated test message missing')

    def close(self):
        try:
            self.connection.sendall(packet(0xe0))
        except OSError:
            pass
        self.connection.close()


def free_port():
    with socket.socket() as listener:
        listener.bind(('127.0.0.1', 0))
        return listener.getsockname()[1]


class Broker:
    def __init__(self, runtime, directory):
        directory.mkdir(parents=True)
        directory.chmod(0o755)
        self.port = free_port()
        self.env = dict(os.environ, LD_LIBRARY_PATH=str(runtime / 'usr/lib/x86_64-linux-gnu'))
        passwords = directory / 'synthetic.passwd'
        subprocess.run([str(runtime / 'usr/bin/mosquitto_passwd'), '-b', '-c', str(passwords), USER, PASSWORD],
                       env=self.env, check=True, capture_output=True)
        passwords.chmod(0o644)
        config = directory / 'mosquitto.conf'
        config.write_text(f'listener {self.port} 127.0.0.1\nallow_anonymous false\n'
                          f'password_file {passwords}\npersistence false\nlog_dest stdout\nlog_type all\n')
        self.log = (directory / 'broker.log').open('w')
        self.process = subprocess.Popen([str(runtime / 'usr/sbin/mosquitto'), '-c', str(config)],
                                        env=self.env, stdout=self.log, stderr=subprocess.STDOUT)
        try:
            for _ in range(50):
                if self.process.poll() is not None:
                    raise RuntimeError('isolated broker startup failed; see broker.log')
                try:
                    probe = socket.create_connection(('127.0.0.1', self.port), timeout=.1)
                    probe.close()
                    break
                except OSError:
                    time.sleep(.1)
            else:
                raise TimeoutError('isolated broker did not become ready')
        except BaseException:
            self.close()
            raise

    def close(self):
        # 只操作本工具创建并持有的 PID，不调用 service/systemctl 或按进程名批量终止。
        if self.process.poll() is None:
            self.process.terminate()
            try:
                self.process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait(timeout=3)
        self.log.close()


class AckProxy:
    def __init__(self, broker_port, mode):
        self.listener = socket.socket()
        self.listener.bind(('127.0.0.1', 0))
        self.port = self.listener.getsockname()[1]
        self.listener.listen(1)
        self.listener.settimeout(3)
        self.mode = mode
        self.sockets = []
        self.forwarded_at = None
        self.closed = False
        self.thread = threading.Thread(target=self.run, args=(broker_port,), daemon=True)
        self.thread.start()

    def run(self, broker_port):
        try:
            client, _ = self.listener.accept()
            server = socket.create_connection(('127.0.0.1', broker_port), timeout=3)
            self.sockets = [client, server]
            def upstream():
                try:
                    while not self.closed:
                        data = client.recv(4096)
                        if not data: break
                        server.sendall(data)
                except OSError:
                    pass
            threading.Thread(target=upstream, daemon=True).start()
            while not self.closed:
                kind, body = read_packet(server, timeout=30)
                # 仅延迟/丢弃 Broker 产生的正常 PUBACK；不构造错号、畸形包或攻击输入。
                if kind == 0x40 and self.mode == 'drop':
                    continue
                if kind == 0x40 and self.mode == 'delay':
                    time.sleep(.7)
                    self.forwarded_at = time.monotonic()
                client.sendall(packet(kind, body))
        except (OSError, EOFError):
            pass

    def close(self):
        self.closed = True
        self.listener.close()
        for connection in self.sockets:
            try: connection.shutdown(socket.SHUT_RDWR)
            except OSError: pass
            connection.close()
        self.thread.join(timeout=2)


def line_from(process, timeout=8):
    if not select.select([process.stdout], [], [], timeout)[0]:
        raise TimeoutError('Gateway response missing')
    line = process.stdout.readline()
    if not line:
        raise RuntimeError('Gateway stopped before response')
    return json.loads(line)


def command(process, value):
    process.stdin.write(value + '\n')
    process.stdin.flush()
    return line_from(process)


def build(out):
    include = ['-I' + str(MQTT / 'src'), '-I' + str(MQTT / 'tests'), '-I' + str(MQTT / 'tests/mocks')]
    # P4 强制包含的平台头早于 C 文件正文，POSIX 特性宏必须由命令行先定义。
    common = ['gcc', '-D_POSIX_C_SOURCE=200809L', '-std=c11', '-O1', '-Wall', '-Wextra', *include,
              str(MQTT / 'tests/broker_gateway.c'), str(ROOT / 'gateway/data_model/model.c'),
              str(ROOT / 'gateway/storage/router.c')]
    core = ROOT / 'gateway/third_party/coreMQTT'
    paho = ROOT / 'gateway/third_party/paho-embedded-c'
    sources = ['MQTTConnectClient.c', 'MQTTDeserializePublish.c', 'MQTTPacket.c',
               'MQTTSerializePublish.c', 'MQTTSubscribeClient.c', 'MQTTUnsubscribeClient.c']
    commands = {
        'P5': [*common, '-Werror', '-DGATEWAY_MQTT_HOST_TEST',
               '-I' + str(core / 'source/include'), '-I' + str(core / 'source/interface'),
               str(MQTT / 'src/gateway_transport.c'), str(MQTT / 'src/mqtt_transport_adapter.c'),
               *[str(core / 'source' / file) for file in ['core_mqtt.c', 'core_mqtt_serializer.c', 'core_mqtt_state.c']]],
        'P4': [*common, '-DP5_P4_BASELINE_TEST', '-DMQTTCLIENT_PLATFORM_HEADER=p4_platform_for_broker.h',
               '-include', 'MQTTClient.h', '-I' + str(paho / 'MQTTClient-C/src'),
               '-I' + str(paho / 'MQTTPacket/src'),
               str(MQTT / 'build/p0-broker/p4_gateway_transport.c'),
               str(paho / 'MQTTClient-C/src/MQTTClient.c'),
               *[str(paho / 'MQTTPacket/src' / file) for file in sources]],
    }
    for name, args in commands.items():
        compiled = subprocess.run([*args, '-o', str(out / name)], text=True, capture_output=True)
        (out / f'{name}-compile.log').write_text(compiled.stdout + compiled.stderr)
        if compiled.returncode:
            raise RuntimeError(name + ' host compilation failed; see compile.log')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--runtime', required=True, type=Path)
    args = parser.parse_args()
    if sys.platform == 'win32':
        extract_p4()
        commit = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()
        return subprocess.call(['wsl', '-d', 'HERA-C3', '--cd', linux_path(ROOT), '--', 'env',
                                'P5_COMMIT=' + commit, 'python3', 'gateway/mqtt/tests/run_broker_integration.py',
                                '--runtime', linux_path(args.runtime)])
    runtime = args.runtime.resolve()
    if not (MQTT / 'build/p0-broker/p4_gateway_transport.c').exists(): extract_p4()
    out = MQTT / 'build/p0-broker' / datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    out.mkdir(parents=True)
    report = {'started_at': datetime.now(timezone.utc).isoformat(),
              'code_commit': os.environ.get('P5_COMMIT') or subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
              'broker': 'Mosquitto 2.0.21 Debian 2.0.21-1', 'transport': 'POSIX TCP loopback; ESP/TLS NOT_RUN',
              'physical_nodes': False, 'real_patient_data': False, 'security_gate': 'NOT_AUTHORIZED/NOT_RUN',
              'baseline': P4_SHA, 'checks': [], 'variants': {}, 'broker_cleanup': []}
    # 摘要绑定真实编译文件；旧 HEAD 只代表父提交，不能冒充未提交夹具已存在于该提交。
    inputs = [MQTT / 'tests/broker_gateway.c', Path(__file__),
              MQTT / 'tests/mocks/p4_platform_for_broker.h',
              MQTT / 'src/gateway_transport.c', MQTT / 'src/mqtt_transport_adapter.c',
              ROOT / 'gateway/data_model/model.c', ROOT / 'gateway/storage/router.c',
              ROOT / 'gateway/third_party/coreMQTT/upstream.json',
              ROOT / 'gateway/third_party/paho-embedded-c/patched.json']
    report['source_sha256'] = {path.relative_to(ROOT).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
                               for path in inputs}
    identity = json.loads((MQTT / 'build/p0-broker/p4-source-identity.json').read_text())
    assert hashlib.sha256((MQTT / 'build/p0-broker/p4_gateway_transport.c').read_bytes()).hexdigest() == identity['shim_sha256']
    report['p4_source_identity'] = identity
    env = dict(os.environ, LD_LIBRARY_PATH=str(runtime / 'usr/lib/x86_64-linux-gnu'))
    version = subprocess.run([str(runtime / 'usr/sbin/mosquitto'), '-h'], env=env,
                             text=True, capture_output=True).stdout.splitlines()[0]
    assert version == 'mosquitto version 2.0.21'
    report['broker_version_actual'] = version
    def check(name, condition, notes=''):
        report['checks'].append({'check': name, 'result': 'PASS' if condition else 'FAIL', 'notes': notes})
        if not condition: raise AssertionError(name)
        print('PASS', name, flush=True)
    try:
        build(out)
        report['host_binary_sha256'] = {variant: hashlib.sha256((out / variant).read_bytes()).hexdigest()
                                        for variant in ('P4', 'P5')}
        for variant in ('P4', 'P5'):
            broker = Broker(runtime, out / ('broker_' + variant))
            observer = late = process = None
            frames = {}
            try:
                rejected = Observer(broker.port, variant + '-bad', 'synthetic-wrong-password')
                check(variant + '_broker_auth_rejects_wrong_password', not rejected.accepted)
                rejected.close()
                observer = Observer(broker.port, variant)
                assert observer.accepted
                observer.subscribe()
                process = subprocess.Popen([str(out / variant), str(broker.port)], stdin=subprocess.PIPE,
                                           stdout=subprocess.PIPE, stderr=(out / f'{variant}-gateway.log').open('w'), text=True)
                assert line_from(process)['ready']
                online = observer.message('status')
                check(variant + '_online_qos1', online['payload']['value'] == 'ONLINE' and online['qos'] == 1)
                frames['online'] = online['payload']
                late = Observer(broker.port, variant + '-late')
                late.subscribe(); retained = late.message('status')
                check(variant + '_retained_online_new_subscriber', retained['retained'] and retained['payload'] == frames['online'])
                late.close(); late = None
                for action, suffix, qos in [('scalar', 'NODE-A/telemetry/spo2', 1),
                                            ('wave', 'NODE-B/telemetry/ecg', 0), ('replay', 'NODE-B/replay/ecg', 1)]:
                    reply = command(process, action)
                    received = observer.message(suffix)
                    check(variant + '_' + action + '_broker_delivery', reply['ok'] and received['qos'] == qos)
                    if qos: check(variant + '_' + action + '_matching_puback', reply['puback_before_return'] and reply['published_id'] == reply['puback_id'])
                    frames[action] = received['payload']
                # 等待一个真实 15s 保活周期，期间 Gateway 主循环持续执行 yield。
                time.sleep(16)
                reply = command(process, 'scalar')
                observer.message('NODE-A/telemetry/spo2')
                check(variant + '_real_keepalive_pingreq', reply['ok'] and reply['pings'] >= 1)
                process.kill(); process.wait(timeout=3)
                offline = observer.message('status')
                check(variant + '_abrupt_disconnect_lwt', offline['payload']['value'] == 'OFFLINE' and offline['qos'] == 1)
                frames['will'] = offline['payload']
                late = Observer(broker.port, variant + '-offline')
                late.subscribe(); retained = late.message('status')
                check(variant + '_retained_offline_after_lwt', retained['retained'] and retained['payload'] == frames['will'])
                report['variants'][variant] = frames
            finally:
                if process and process.poll() is None: process.kill(); process.wait(timeout=3)
                if late: late.close()
                if observer: observer.close()
                broker.close()
                report['broker_cleanup'].append({'pid': broker.process.pid, 'stopped': broker.process.poll() is not None})
        check('p4_p5_normal_payload_and_will_equivalence', report['variants']['P4'] == report['variants']['P5'])
        for mode in ('delay', 'drop'):
            broker = Broker(runtime, out / mode)
            observer = process = proxy = None
            try:
                observer = Observer(broker.port, mode); observer.subscribe()
                # 初始 ONLINE 需成功；仅在其后启动 PUBACK 延迟/丢失情形。
                proxy = AckProxy(broker.port, 'normal')
                process = subprocess.Popen([str(out / 'P5'), str(proxy.port)], stdin=subprocess.PIPE,
                                           stdout=subprocess.PIPE, stderr=(out / f'{mode}-gateway.log').open('w'), text=True)
                assert line_from(process)['ready']; observer.message('status')
                proxy.mode = mode
                process.stdin.write('scalar\n'); process.stdin.flush()
                delivered = observer.message('NODE-A/telemetry/spo2')
                check('p5_' + mode + '_broker_already_received_frame', delivered['qos'] == 1)
                if mode == 'delay':
                    check('p5_delay_no_early_router_success', not select.select([process.stdout], [], [], 0)[0])
                reply = line_from(process, timeout=8)
                if mode == 'delay':
                    check('p5_real_delayed_puback_success', reply['ok'] and reply['elapsed_ms'] >= 650
                          and reply['puback_before_return'] and proxy.forwarded_at is not None)
                else:
                    check('p5_real_missing_puback_failure', not reply['ok'] and 5000 <= reply['elapsed_ms'] < 5500)
                    check('p5_real_missing_puback_router_cache', reply['cache'] == 1 and not reply['router_online']
                          and reply['seq'] == 17 and reply['timestamp'] == 1800000000123)
            finally:
                if process and process.poll() is None: process.kill(); process.wait(timeout=3)
                if proxy: proxy.close()
                if observer: observer.close()
                broker.close()
                report['broker_cleanup'].append({'pid': broker.process.pid, 'stopped': broker.process.poll() is not None})
        check('all_owned_isolated_brokers_stopped', len(report['broker_cleanup']) == 4
              and all(item['stopped'] for item in report['broker_cleanup']))
        report['result'] = 'PASS'
    except BaseException as error:
        report['result'] = 'FAIL'
        report['failure'] = type(error).__name__ + ': ' + str(error)
        raise
    finally:
        report['completed_at'] = datetime.now(timezone.utc).isoformat()
        report['passed'] = sum(c['result'] == 'PASS' for c in report['checks'])
        (out / 'result.json').write_text(json.dumps(report, indent=2) + '\n')
        (out.parent / 'latest.json').write_text(json.dumps(report, indent=2) + '\n')
    print('Isolated Broker checks PASS:', report['passed'])
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
