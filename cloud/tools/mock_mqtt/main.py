"""合成 MQTT 发布器：只生成 MOCK 或标记 synthetic 的 REPLAY。"""

import argparse
import json
import math
from pathlib import Path
import socket
import sys
import time
import uuid

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'backend'))
from app.models import CHANNELS, UNITS, WAVES
from app.mqtt_adapter import configured_client


# 所有模拟源明确携带 synthetic；REPLAY 仅改变传输类别，不把合成数据伪装为 LIVE。
def payload(session, seq, stream, value=None, source='MOCK', validity='VALID', timestamp=None):
    return {
        'timestamp': timestamp or int(time.time() * 1000),
        'seq': seq,
        'session_id': session,
        'validity': validity,
        'source': source,
        'synthetic': True,
        'value': value,
        'unit': UNITS[stream],
    }


def read_control(path):
    if not path or not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding='utf-8-sig'))
        if not isinstance(data, dict) or data.get('mode', 'MOCK') not in {'MOCK', 'REPLAY'}:
            raise ValueError('mode')
        if data.get('validity', 'VALID') not in {'VALID', 'INVALID', 'STALE'}:
            raise ValueError('validity')
        for key in ['network_online', 'pause', 'node_a_online', 'node_b_online']:
            if key in data and type(data[key]) is not bool:
                raise ValueError('control flag')
        return data
    except (OSError, ValueError):
        return {'pause': True}


def wave(stream, seq):
    rate = 250 if stream == 'ECG' else 50
    samples = []
    for i in range(rate // 5):
        t = seq * 0.2 + i / rate
        phase = t * 1.2 % 1
        if stream == 'ECG':
            y = (
                0.1 * math.sin(2 * math.pi * phase)
                + math.exp(-(((phase - 0.25) / 0.022) ** 2))
                - 0.22 * math.exp(-(((phase - 0.30) / 0.028) ** 2))
            )
        elif stream == 'PPG':
            y = max(0, math.sin(math.pi * phase)) ** 3
        else:
            y = 0.8 * math.sin(2 * math.pi * 0.25 * t)
        samples.append(round(y, 5))
    return {'sample_rate': rate, 'samples': samples}


# 控制文件与凭据从仓库外传入；循环发送合成数据，并负责客户端正常退出。
def run(config, control_path=None, duration=0):
    end = time.monotonic() + duration if duration else float('inf')
    gateway = config.get('gateway_id', 'GW-DEV-001')
    base = f'mpm/v1/{gateway}'
    while time.monotonic() < end:
        if not read_control(control_path).get('network_online', True):
            time.sleep(0.2)
            continue
        session, seq = uuid.uuid4().hex, 0
        capture_origin = int(time.time() * 1000)
        next_tick = time.monotonic()
        client = configured_client(config, config['client_id'])
        will = payload(session, 2**53 - 1, 'GATEWAY_STATUS', 'OFFLINE', validity='OFFLINE')
        client.will_set(base + '/status', json.dumps(will), qos=1, retain=True)
        client.connect_async(config['host'], config.get('port', 8883), keepalive=10)
        client.loop_start()
        abnormal = False
        try:
            while time.monotonic() < end:
                control = read_control(control_path)
                if not control.get('network_online', True):
                    # 模拟链路中断时不发 DISCONNECT，让 Broker 真正触发 LWT。
                    abnormal = True
                    active = client.socket()
                    if active:
                        try:
                            active.shutdown(socket.SHUT_RDWR)
                        except OSError:
                            pass
                    break
                if not client.is_connected() or control.get('pause'):
                    time.sleep(0.2)
                    capture_origin = int(time.time() * 1000) - seq * 200
                    next_tick = time.monotonic()
                    continue
                source = control.get('mode', 'MOCK')
                stamp = capture_origin + seq * 200 - (60000 if source == 'REPLAY' else 0)
                messages = []
                if seq % 10 == 0:
                    messages.append(
                        (
                            base + '/status',
                            payload(session, seq, 'GATEWAY_STATUS', 'ONLINE'),
                            1,
                            True,
                        )
                    )
                    for node in CHANNELS:
                        online = control.get(
                            'node_a_online' if node == 'NODE-A' else 'node_b_online', True
                        )
                        messages.append(
                            (
                                base + '/' + node + '/status',
                                payload(
                                    session,
                                    seq,
                                    'NODE_STATUS',
                                    'ONLINE' if online else 'OFFLINE',
                                    validity='VALID' if online else 'OFFLINE',
                                ),
                                1,
                                True,
                            )
                        )
                values = {
                    'HR': 72.0,
                    'RR': 15.0,
                    'SPO2': 98.0,
                    'PR': 72.0,
                    'TEMP': 36.6,
                    'NIBP': [118.0, 76.0],
                }
                for node, streams in CHANNELS.items():
                    for stream in sorted(streams):
                        if stream not in WAVES and seq % 5:
                            continue
                        body = payload(
                            session,
                            seq,
                            stream,
                            values.get(stream),
                            source,
                            control.get('validity', 'VALID'),
                            stamp,
                        )
                        if stream in WAVES:
                            body.update(wave(stream, seq))
                        kind = 'replay' if source == 'REPLAY' else 'telemetry'
                        messages.append(
                            (
                                f'{base}/{node}/{kind}/{stream.lower()}',
                                body,
                                1 if source == 'REPLAY' or stream not in WAVES else 0,
                                False,
                            )
                        )
                if control.get('event') and seq % 10 == 0:
                    messages.append(
                        (
                            base + '/NODE-B/event',
                            payload(session, seq, 'FAULT', 'SYNTHETIC_TEST_EVENT'),
                            1,
                            False,
                        )
                    )
                acknowledgements = []
                for topic, body, qos, retain in messages:
                    info = client.publish(
                        topic, json.dumps(body, separators=(',', ':')), qos=qos, retain=retain
                    )
                    if qos:
                        acknowledgements.append(info)
                # 先发送本周期消息再统一确认，避免每个标量各等待一次公网往返。
                for info in acknowledgements:
                    try:
                        info.wait_for_publish(timeout=4)
                    except RuntimeError:
                        break
                    if not info.is_published():
                        break
                seq += 1
                next_tick += 0.2
                if time.monotonic() - next_tick > 1:
                    # 长时间阻塞后重新开始采集时间轴，不伪造丢失期间的波形。
                    capture_origin = int(time.time() * 1000) - seq * 200
                    next_tick = time.monotonic()
                time.sleep(max(0, next_tick - time.monotonic()))
        finally:
            if not abnormal and client.is_connected():
                offline = payload(
                    session, 2**53 - 1, 'GATEWAY_STATUS', 'OFFLINE', validity='OFFLINE'
                )
                info = client.publish(base + '/status', json.dumps(offline), qos=1, retain=True)
                try:
                    info.wait_for_publish(timeout=3)
                except RuntimeError:
                    pass
                client.disconnect()
            client.loop_stop()


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--config', type=Path, required=True)
    parser.add_argument('--control', type=Path)
    parser.add_argument('--duration', type=float, default=0)
    args = parser.parse_args()
    try:
        run(json.loads(args.config.read_text(encoding='utf-8-sig')), args.control, args.duration)
    except KeyboardInterrupt:
        pass
