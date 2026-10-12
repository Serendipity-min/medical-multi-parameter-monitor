"""真实隔离 Mosquitto+启用 P6 的生产 coreMQTT；模拟 UART，不操作开发板。"""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[3]
MQTT = ROOT / 'gateway/mqtt'


def main():
    parser = argparse.ArgumentParser(); parser.add_argument('--runtime', type=Path, required=True)
    args = parser.parse_args()
    if sys.platform == 'win32':
        def linux(path):
            path = path.resolve(); return '/mnt/' + path.drive[0].lower() + path.as_posix()[2:]
        commit = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()
        return subprocess.call(['wsl', '-d', 'HERA-C3', '--cd', linux(ROOT), '--', 'env', 'P6_COMMIT=' + commit,
                                'python3', 'gateway/mqtt/tests/run_p6_broker.py', '--runtime', linux(args.runtime)])
    sys.path.insert(0, str(ROOT))
    from cloud.ai.downlink import encode
    # 复用原测试的 Broker/标准 MQTT 观察端，不安装工具或借用生产配置。
    spec = importlib.util.spec_from_file_location('p5_broker', MQTT / 'tests/run_broker_integration.py')
    base = importlib.util.module_from_spec(spec); spec.loader.exec_module(base)
    out = ROOT / 'build/p6/broker-b1' / time.strftime('%Y%m%dT%H%M%S')
    out.mkdir(parents=True)
    core = ROOT / 'gateway/third_party/coreMQTT'
    sources = [MQTT / 'tests/broker_gateway.c', MQTT / 'src/gateway_transport.c', MQTT / 'src/mqtt_transport_adapter.c',
               MQTT / 'src/p6_voice.c', ROOT / 'gateway/data_model/model.c', ROOT / 'gateway/storage/router.c',
               *[core / 'source' / name for name in ('core_mqtt.c', 'core_mqtt_serializer.c', 'core_mqtt_state.c')]]
    command = ['gcc', '-std=c11', '-O1', '-Wall', '-Wextra', '-Werror', '-DGATEWAY_P6_VOICE=1', '-DP6_BROKER_TEST', '-DGATEWAY_MQTT_HOST_TEST',
               '-I' + str(MQTT / 'src'), '-I' + str(core / 'source/include'), '-I' + str(core / 'source/interface'),
               *map(str, sources), '-o', str(out / 'gateway')]
    compile_result = subprocess.run(command, capture_output=True, text=True)
    (out / 'compile.log').write_text(compile_result.stdout + compile_result.stderr)
    if compile_result.returncode: print(compile_result.stderr); return compile_result.returncode
    checks, records = [], []
    def check(label, value):
        if not value: raise AssertionError(label)
        checks.append(label); print('PASS', label, flush=True)
    def publish(observer, payload, retain=False, topic='mpm/v1/GW-C-001/voice/reply'):
        observer.connection.sendall(base.packet(0x33 if retain else 0x32, base.field(topic) + b'\x00\x77' + payload))
        kind, ack = base.read_packet(observer.connection)
        assert kind == 0x40 and ack == b'\x00\x77'
    def stop(process):
        if process and process.poll() is None:
            process.stdin.write('close\n'); process.stdin.flush()
            process.wait(timeout=5)
    broker = base.Broker(args.runtime, out / 'broker')
    process = observer = None
    proxies = []
    try:
        observer = base.Observer(broker.port, 'p6-writer')
        process = subprocess.Popen([str(out / 'gateway'), str(broker.port)], stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True, bufsize=1)
        ready = base.line_from(process); check('p6_subscribe_and_original_status_qos1', ready['ready'])
        now = ready['epoch'] * 1000
        good = encode('1'*32, '2'*32, '模拟心率72 bpm。', now)
        publish(observer, good)
        result = base.command(process, 'scalar'); records.append(result)
        check('legal_voice_during_real_telemetry_matching_puback', result['ok'] and result['puback_before_return'])
        state = base.command(process, 'voice'); records.append(state)
        check('uart_frame_sent_without_waiting_playback', state['tts_bytes'] > 5 and state['accepted'] == 0 and state['completed'] == 0)
        accepted = base.command(process, 'accepted'); check('41_is_acceptance_only', accepted['accepted'] == 1 and accepted['completed'] == 0)
        completed = base.command(process, 'completed'); check('4f_only_host_completion', completed['completed'] == 1)
        publish(observer, good); time.sleep(.1)
        state = base.command(process, 'voice'); check('broker_duplicate_business_turn_refused', state['rejected'] >= 1)
        bad = bytearray(good); bad[0] = ord('X'); publish(observer, bytes(bad)); time.sleep(.1)
        result = base.command(process, 'scalar'); state = base.command(process, 'voice')
        check('malformed_application_frame_rejected_telemetry_survives', result['ok'] and state['rejected'] >= 2)
        check('disconnect_reconnect_resubscribes', base.command(process, 'reconnect')['reconnected'])
        publish(observer, good); time.sleep(.1); state = base.command(process, 'voice')
        check('dedup_survives_real_reconnect', state['rejected'] >= 3 and state['completed'] == 1)
        expired = encode('3'*32, '2'*32, '模拟', now-20000); publish(observer, expired)
        result = base.command(process, 'scalar'); state = base.command(process, 'voice')
        check('expired_voice_does_not_change_puback_success', result['ok'] and state['rejected'] >= 4)
        publish(observer, b'x' * 600)
        # 固定上游将过大 MQTT 报文有界 drain 后继续，不假设必须断开，更不能改库迎合断言。
        time.sleep(.1)
        after_oversize = base.command(process, 'scalar'); oversized_state = base.command(process, 'voice')
        check('oversize_mqtt_rx_drained_without_uart_or_buffer_growth',
              after_oversize['ok'] and oversized_state['tts_bytes'] == state['tts_bytes'] and oversized_state['completed'] == state['completed'])
        check('session_after_oversize_has_normal_qos1', after_oversize['puback_before_return'])
        stop(process); process = None
        # 受控代理仅作用于进程自有 loopback 测试链路，错号不得确认 Router。
        class WrongAck(base.AckProxy):
            def run(self, broker_port):
                import socket, threading
                try:
                    client, _ = self.listener.accept(); server = socket.create_connection(('127.0.0.1', broker_port), timeout=3)
                    self.sockets = [client, server]
                    def up():
                        try:
                            while not self.closed:
                                data = client.recv(4096)
                                if not data: break
                                server.sendall(data)
                        except OSError: pass
                    threading.Thread(target=up, daemon=True).start()
                    ack_count = 0
                    while not self.closed:
                        kind, body = base.read_packet(server, timeout=10)
                        if kind == 0x40:
                            ack_count += 1
                            if ack_count > 1: body = ((int.from_bytes(body, 'big') + 1) & 65535).to_bytes(2, 'big')
                        client.sendall(base.packet(kind, body))
                except (OSError, EOFError): pass
        for mode in ('delay', 'wrong'):
            proxy = WrongAck(broker.port, mode) if mode == 'wrong' else base.AckProxy(broker.port, mode)
            proxies.append(proxy)
            process = subprocess.Popen([str(out / 'gateway'), str(proxy.port)], stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True, bufsize=1)
            ready = base.line_from(process); assert ready['ready']
            voice = encode(('4' if mode == 'delay' else '5')*32, '2'*32, '模拟心率72 bpm。', ready['epoch']*1000)
            publish(observer, voice)
            result = base.command(process, 'scalar'); records.append(result)
            check('p6_delayed_puback_no_early_success' if mode == 'delay' else 'p6_wrong_puback_recaches_even_with_voice',
                  result['ok'] and result['elapsed_ms'] >= 650 if mode == 'delay' else not result['ok'] and result['cache'] == 1 and not result['router_online'])
            stop(process); process = None; proxy.close()
    finally:
        stop(process)
        if observer: observer.close()
        for proxy in proxies: proxy.close()
        broker.close()
    check('all_owned_broker_gateway_proxy_processes_stopped', broker.process.poll() is not None)
    report = {'result':'PASS', 'exit_code':0, 'parent_commit':os.environ.get('P6_COMMIT') or subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(), 'broker':'Mosquitto 2.0.21 loopback',
              'mode':'HOST_VERIFIED', 'hardware':'NOT_RUN', 'ESP_AT_TLS':'NOT_RUN', 'checks':checks, 'records':records,
              'binary_sha256':hashlib.sha256((out/'gateway').read_bytes()).hexdigest(),
              'source_sha256':{p.relative_to(ROOT).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in sources}}
    (out/'result.json').write_text(json.dumps(report, indent=2)); (out.parent/'latest.json').write_text(json.dumps(report, indent=2))
    return 0


if __name__ == '__main__': raise SystemExit(main())
