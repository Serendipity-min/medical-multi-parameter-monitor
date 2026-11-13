"""合同功能验收：TLS、认证、ACL、PUBACK、Retain 与真实异常断线 LWT。"""

import argparse
import json
from pathlib import Path
import queue
import socket
import ssl
import sys
import threading
import time
import uuid

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'backend'))
from app.mqtt_adapter import configured_client


def wait_for(predicate, seconds=10):
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        if predicate():
            return
        time.sleep(0.05)
    raise RuntimeError('MQTT functional check timeout')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--publisher', type=Path, required=True)
    parser.add_argument('--reader', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    publisher = json.loads(args.publisher.read_text(encoding='utf-8-sig'))
    reader = json.loads(args.reader.read_text(encoding='utf-8-sig'))
    checks = []
    clients = []

    def passed(name):
        checks.append(name)
        print('PASS ' + name, flush=True)

    # 每个角色创建独立客户端并等待回调确认，用实际 Broker 行为检验权限与消息语义。
    def connect(config, will=None):
        client = configured_client(config, 'acceptance-' + uuid.uuid4().hex[:12])
        received = queue.Queue()
        state = {}

        def on_connect(c, u, f, reason, p):
            state['code'] = reason.value

        client.on_connect = on_connect
        client.on_message = lambda c, u, m: received.put((m.topic, bytes(m.payload), m.retain))
        if will:
            client.will_set(will[0], will[1], qos=1, retain=True)
        client.connect_async(config['host'], config.get('port', 8883), 10)
        client.loop_start()
        clients.append(client)
        wait_for(lambda: 'code' in state)
        return client, received, state['code']

    def subscribe(client, topic):
        ready = threading.Event()
        client.on_subscribe = lambda *args: ready.set()
        client.subscribe(topic, 1)
        assert ready.wait(10)

    def publish(client, topic, payload, retain=False):
        info = client.publish(topic, payload, qos=1, retain=retain)
        info.wait_for_publish(timeout=10)
        assert info.is_published()

    def find(received, topic, body, retained=None, seconds=5):
        end = time.monotonic() + seconds
        while time.monotonic() < end:
            try:
                t, b, r = received.get(timeout=0.1)
            except queue.Empty:
                continue
            if t == topic and b == body and (retained is None or r == retained):
                return True
        return False

    try:
        observer, events, code = connect(reader)
        assert code == 0
        subscribe(observer, 'mpm/v1/+/+/#')
        subscribe(observer, 'mpm/v1/+/status')
        passed('TLS certificate verified and backend subscribed')
        bad = {**publisher, 'password': 'intentionally-invalid-test-password'}
        client, _, code = connect(bad)
        assert code != 0
        client.disconnect()
        client.loop_stop()
        passed('Wrong password rejected')
        client, _, code = connect({**publisher, 'username': None, 'password': None})
        assert code != 0
        client.disconnect()
        client.loop_stop()
        passed('Anonymous client rejected')
        # 用不信任任何 CA 的上下文确认连接确实依赖证书验证。
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        try:
            with socket.create_connection((publisher['host'], 8883), timeout=5) as raw:
                with context.wrap_socket(raw, server_hostname=publisher['host']):
                    pass
        except ssl.SSLCertVerificationError:
            passed('Untrusted certificate rejected')
        else:
            raise AssertionError('CA verification missing')
        with socket.create_connection((publisher['host'], 8883), timeout=5) as raw:
            raw.sendall(b'\x10\x0c\x00\x04MQTT\x04\x02\x00\x0a\x00\x00')
            try:
                reply = raw.recv(4)
            except ConnectionResetError:
                reply = b''
            assert not reply.startswith(b'\x20')
        passed('Plain MQTT rejected by TLS listener')
        marker = uuid.uuid4().hex.encode()
        client, inbound, code = connect(publisher)
        assert code == 0
        topic = 'mpm/v1/GW-DEV-001/NODE-B/event'
        publish(client, topic, marker)
        assert find(events, topic, marker)
        passed('QoS1 PUBACK and authorized publish received')
        publish(client, 'mpm/v1/GW-C-001/NODE-B/event', marker)
        assert not find(events, 'mpm/v1/GW-C-001/NODE-B/event', marker, seconds=1)
        passed('Publisher cannot write another gateway')
        publish(observer, topic, marker + b'-reader')
        assert not find(events, topic, marker + b'-reader', seconds=1)
        passed('Backend account cannot publish')
        subscribe(client, topic)
        publish(client, topic, marker + b'-read')
        assert not find(inbound, topic, marker + b'-read', seconds=1)
        passed('Publisher account cannot subscribe to data')
        status = 'mpm/v1/GW-DEV-001/status'
        session = uuid.uuid4().hex
        body = {
            'timestamp': int(time.time() * 1000),
            'seq': 2**53 - 1,
            'session_id': session,
            'validity': 'OFFLINE',
            'source': 'MOCK',
            'synthetic': True,
            'value': 'OFFLINE',
            'unit': 'state',
        }
        will = json.dumps(body).encode()
        victim, _, code = connect(publisher, (status, will))
        assert code == 0
        body.update(seq=0, value='ONLINE', validity='VALID')
        online = json.dumps(body).encode()
        publish(victim, status, online, True)
        fresh, retained, code = connect(reader)
        assert code == 0
        subscribe(fresh, status)
        assert find(retained, status, online, True)
        passed('New subscriber receives retained ONLINE')
        # 直接关闭 TCP，不发 MQTT DISCONNECT；此时只由 Broker 生成 Will。
        victim.socket().shutdown(socket.SHUT_RDWR)
        victim.loop_stop()
        assert find(events, status, will, seconds=15)
        passed('Abnormal TCP loss triggers retained OFFLINE Will')
    finally:
        for client in clients:
            client.disconnect()
            client.loop_stop()
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(
            json.dumps({'checks': checks, 'passed': len(checks)}, indent=2), encoding='utf-8'
        )


if __name__ == '__main__':
    main()
