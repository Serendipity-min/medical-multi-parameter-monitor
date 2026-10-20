"""同AP电脑/服务器回环的有界TLS1.2 MQTT对照；专用主题不进入监护模型。"""
import argparse
import base64
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import secrets
import shutil
import socket
import ssl
import subprocess
import threading
import time

STATE = Path('/var/lib/medical-monitor-p6/h3-20261019')


def prepare():
    directory = Path('/opt/medical-monitor-h3/broker')
    target = STATE / 'network-probe.json'
    if target.exists():
        raise ValueError('PROBE_ROLE_ALREADY_EXISTS')
    # 每轮单独保留原件，避免第二轮对照覆盖此前的凭据/ACL备份。
    backup = STATE / ('network-probe-backup-' + str(time.time_ns())); backup.mkdir(mode=0o700)
    hashes = {}
    for name in ('passwords', 'acl'):
        source = directory / name
        shutil.copy2(source, backup / name)
        (backup / name).chmod(0o600)
        hashes[name] = hashlib.sha256(source.read_bytes()).hexdigest()
    password = secrets.token_urlsafe(30)
    salt = secrets.token_bytes(12); rounds = 101000
    encoded = lambda b: base64.b64encode(b).decode()
    key = hashlib.pbkdf2_hmac('sha512', password.encode(), salt, rounds)
    # 只添加独立8884测试角色；不改原GW/Backend的ACL，也不接触正式Broker。
    with (directory / 'passwords').open('a') as output:
        output.write('h3-net-probe:$7$' + str(rounds) + '$' + encoded(salt) + '$' + encoded(key) + '\n')
    with (directory / 'acl').open('a') as output:
        output.write('\nuser h3-net-probe\ntopic readwrite h3/net-probe/#\n')
    config = json.loads((STATE / 'backend.json').read_text())
    config.update(username='h3-net-probe', password=password)
    target.write_text(json.dumps(config)); target.chmod(0o600)
    (STATE/'network-probe-ownership.json').write_text(json.dumps({
        'backup':str(backup),'before':hashes,
        'after':{name:hashlib.sha256((directory/name).read_bytes()).hexdigest() for name in hashes}}))
    result = subprocess.run(['systemctl', 'kill', '--signal=HUP', 'medical-monitor-h3-broker-diagnostic'], capture_output=True)
    if result.returncode:
        raise RuntimeError('ISOLATED_ROLE_RELOAD_FAILED')
    return {'action': 'ADD_SCOPED_ISOLATED_NETWORK_PROBE_ROLE', 'port': 8884,
            'topic_namespace': 'h3/net-probe/#', 'original_isolated_file_hashes': hashes,
            'production_broker_modified': False, 'exit_code': 0}


def cleanup():
    directory=Path('/opt/medical-monitor-h3/broker')
    ownership=STATE/'network-probe-ownership.json'
    data=json.loads(ownership.read_text())
    backup=Path(data['backup'])
    if backup.parent!=STATE or not backup.name.startswith('network-probe-backup-'):
        raise ValueError('OWNED_BACKUP_REQUIRED')
    # 两个文件均核对后才恢复；别人已更改隔离配置时不能覆盖，也不涉及正式Broker。
    for name in ('passwords','acl'):
        if hashlib.sha256((directory/name).read_bytes()).hexdigest()!=data['after'][name] or \
           hashlib.sha256((backup/name).read_bytes()).hexdigest()!=data['before'][name]:
            raise ValueError('PROBE_OWNERSHIP_CHANGED')
    for name in ('passwords','acl'):
        # 备份故意是0600；覆盖原文件内容并保留其mosquitto组/原权限。
        shutil.copyfile(backup/name,directory/name)
    (STATE/'network-probe.json').unlink();ownership.unlink()
    result=subprocess.run(['systemctl','kill','--signal=HUP','medical-monitor-h3-broker-diagnostic'],capture_output=True)
    return {'action':'RESTORE_OWNED_ISOLATED_PROBE_ROLE','restored_original_hashes':True,
            'production_broker_modified':False,'exit_code':result.returncode}


def observe(config, seconds=300, loopback=False):
    import paho.mqtt.client as mqtt
    if config['port'] != 8884 or config['username'] != 'h3-net-probe':
        raise ValueError('ISOLATED_PROBE_ROLE_REQUIRED')
    ident = ('server' if loopback else 'pc') + '-' + secrets.token_hex(5)
    result = {'action': 'TLS12_MQTT_NETWORK_CONTROL', 'side': 'SERVER_LOOPBACK' if loopback else 'PC_SAME_AP',
              'started_utc': datetime.now(timezone.utc).isoformat(), 'target_seconds': seconds,
              'qos1_puback': 0, 'qos0_send': 0, 'failure_count': 0,
              'puback_max_ms': 0, 'disconnects': 0, 'latencies_ms': [],
              'automatic_reconnect': False, 'synthetic_non_monitor_topic': True,
              'connection_addresses_saved': False, 'measurement_values_saved': False}
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id='h3-net-probe-' + ident,
                         clean_session=True, protocol=mqtt.MQTTv311, reconnect_on_failure=False)
    client.max_inflight_messages_set(1); client.max_queued_messages_set(2)
    client.username_pw_set(config['username'], config['password'])
    context = ssl.create_default_context()
    context.minimum_version = context.maximum_version = ssl.TLSVersion.TLSv1_2
    client.tls_set_context(context); client.connect_timeout = 8
    connected = threading.Event()
    def on_connect(c, _u, _f, code, _p):
        result['connack'] = code.value
        if not code.is_failure:
            result['tls_version'] = c.socket().version()
            result['socket_family'] = int(c.socket().family)
            connected.set()
    def on_disconnect(_c, _u, _flags, code, _p):
        if code.value: result['disconnects'] += 1
    client.on_connect = on_connect; client.on_disconnect = on_disconnect
    original_resolver = socket.getaddrinfo
    def resolver(host, port, *args, **kwargs):
        # 服务器回环仍保留真实证书SNI/名称校验；仅此独立进程强制IPv4传输路径。
        target = '127.0.0.1' if loopback and host == config['host'] else host
        return original_resolver(target, port, socket.AF_INET, socket.SOCK_STREAM)
    socket.getaddrinfo = resolver
    started = time.monotonic()
    try:
        client.connect(config['host'], 8884, keepalive=15); client.loop_start()
        if not connected.wait(8): raise RuntimeError('PROBE_CONNACK_TIMEOUT')
        started = time.monotonic(); wave = scalar = status = -10.0
        while time.monotonic() - started < seconds:
            elapsed = time.monotonic() - started
            sends = []
            if elapsed - wave >= 1:
                wave = elapsed; sends.append((0, 637))
            if elapsed - scalar >= 2:
                scalar = elapsed; sends.extend([(1, 154)] * 3)
            if elapsed - status >= 5:
                status = elapsed; sends.extend([(1, 156)] * 3)
            for qos, length in sends:
                before = time.monotonic()
                info = client.publish('h3/net-probe/' + ident, b'x' * length, qos=qos, retain=False)
                info.wait_for_publish(timeout=5)
                if info.rc != mqtt.MQTT_ERR_SUCCESS or not info.is_published():
                    result['failure_count'] += 1
                    raise RuntimeError('PROBE_SEND_OR_PUBACK_TIMEOUT')
                if qos:
                    delay = round((time.monotonic() - before) * 1000, 3)
                    result['latencies_ms'].append(delay)
                    result['puback_max_ms'] = max(result['puback_max_ms'], delay)
                    result['qos1_puback'] += 1
                else:
                    result['qos0_send'] += 1
            time.sleep(.01)
        result['exit_code'] = int(bool(result['failure_count'] or result['disconnects']))
    except Exception as exc:
        result.update(exit_code=1, failure_type=type(exc).__name__, details_suppressed=True)
    finally:
        client.disconnect(); client.loop_stop(); socket.getaddrinfo = original_resolver
        result['elapsed_s'] = round(time.monotonic() - started, 3)
        result['finished_utc'] = datetime.now(timezone.utc).isoformat()
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('action', choices=('prepare', 'cleanup', 'pc', 'server'))
    parser.add_argument('--seconds', type=int, default=300)
    args = parser.parse_args()
    if not 30 <= args.seconds <= 600: parser.error('seconds 30..600')
    try:
        if args.action == 'prepare': result = prepare()
        elif args.action == 'cleanup': result = cleanup()
        else:
            if args.action == 'pc':
                remote = "import pathlib;print(pathlib.Path('/var/lib/medical-monitor-p6/h3-20261019/network-probe.json').read_text())"
                query = subprocess.run(['ssh', 'tencent-codex', 'sudo -n python3 -'], input=remote,
                                       text=True, capture_output=True, timeout=20)
                if query.returncode: raise RuntimeError('PROBE_CONFIG_UNAVAILABLE')
                config = json.loads(query.stdout)
            else: config = json.loads((STATE / 'network-probe.json').read_text())
            result = observe(config, args.seconds, args.action == 'server')
        print(json.dumps(result, indent=2))
        raise SystemExit(result.get('exit_code', 0))
    except Exception as exc:
        print(json.dumps({'exit_code': 1, 'failure_type': type(exc).__name__, 'details_suppressed': True}))
        raise SystemExit(1)
