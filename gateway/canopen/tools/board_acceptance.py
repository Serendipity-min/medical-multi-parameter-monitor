"""硬件合同验收；凭据仅从外部配置读入，日志仅保存合成帧与固定控制台诊断。"""

import argparse
from collections import Counter
import json
from pathlib import Path
import re
import subprocess
import sys
import threading
import time
import serial

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / 'cloud/backend'))
from app.mqtt_adapter import configured_client
from app.adapters import decode_mqtt


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--reader', type=Path, required=True)
    parser.add_argument('--flash-helper', type=Path)
    parser.add_argument('--port', default='COM15')
    parser.add_argument('--ssh-alias')
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--smoke', action='store_true')
    parser.add_argument(
        '--quiesce',
        action='store_true',
        help='升级正在运行的本阶段固件前先等待WiFi断开，避免ESP残留CIPSEND数据态',
    )
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    config = json.loads(args.reader.read_text(encoding='utf-8-sig'))
    client = configured_client(config, 'phase2-board-observer')
    events = []
    lines = []
    checks = []
    errors = Counter()
    lock = threading.Lock()
    connected = threading.Event()
    success = False
    start = time.monotonic()
    latest = {}
    connections = []
    serial_log = (args.output / 'serial.jsonl').open('w', encoding='utf-8')
    samples = (args.output / 'synthetic-samples.jsonl').open('w', encoding='utf-8')

    def on_connect(c, u, f, reason, p):
        if not reason.is_failure:
            connections.append(time.monotonic())
            c.subscribe('mpm/v1/GW-C-001/#', 1)

    client.on_connect = on_connect
    client.on_subscribe = lambda *unused: connected.set()

    def on_message(c, u, msg):
        try:
            value = decode_mqtt(msg.topic, msg.payload)
            # 验收仅预期合成测试节点；不把未预期的真实传感器载荷持久化。
            if not value.synthetic:
                errors['unexpected_non_synthetic'] += 1
                return
            now = time.monotonic()
            with lock:
                events.append((now, value))
                latest[(value.node_id, value.stream)] = (now, value)
                if len(events) <= 15:
                    samples.write(
                        json.dumps(
                            {'topic': msg.topic, 'payload': value.model_dump()}, ensure_ascii=False
                        )
                        + '\n'
                    )
                    samples.flush()
        except Exception:
            errors['decode_failed'] += 1

    client.on_message = on_message
    client.connect_async(config['host'], config.get('port', 8883), 15)
    client.loop_start()
    # 禁止打开串口时切换 DTR/RTS，避免未经计划复位。
    uart = serial.Serial(port=None, baudrate=115200, timeout=0.05)
    uart.dtr = False
    uart.rts = False
    uart.port = args.port
    uart.open()

    def pump():
        raw = uart.readline().decode('ascii', errors='ignore').strip()
        if re.fullmatch(r'GW [A-Z0-9_ =a-z-]+', raw):
            entry = {'elapsed_s': round(time.monotonic() - start, 3), 'message': raw}
            lines.append(entry)
            serial_log.write(json.dumps(entry) + '\n')
            serial_log.flush()
            print(raw, flush=True)

    # 轮询条件时持续采集串口日志；超时即判本轮失败，由 finally 保存已完成项和诊断。
    def wait(predicate, timeout=25):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            pump()
            with lock:
                if predicate():
                    return
        raise RuntimeError('Hardware acceptance condition timed out')

    # 只认操作标记之后到达的消息，避免保留消息或上一项结果造成假通过。
    def received(node, stream, since=0, valid=None):
        item = latest.get((node, stream))
        return bool(item and item[0] > since and (valid is None or item[1].validity == valid))

    def passed(name):
        checks.append(name)
        print('PASS ' + name, flush=True)

    def command(value):
        uart.write(value.encode('ascii'))
        uart.flush()
        return time.monotonic()

    try:
        if not connected.wait(20):
            raise RuntimeError('Observer subscription failed')
        # 烧录工具由外部显式传入；已有固件升级先退出发送态，避免 ESP 残留半包。
        if args.flash_helper:
            if args.quiesce:
                command('D')
                wait(lambda: any(e['message'] == 'GW WIFI_TEST_DISCONNECTED' for e in lines), 20)
            result = subprocess.run(
                [sys.executable, str(args.flash_helper), 'install'], capture_output=True, timeout=90
            )
            if result.returncode:
                raise RuntimeError('Temporary firmware install failed')
        wait(
            lambda: received('NODE-A', 'SPO2', valid='VALID')
            and received('NODE-B', 'ECG', valid='VALID'),
            100,
        )
        passed('F407 CANopenNode / bxCAN loopback / TLS MQTT dual node startup')
        wait(
            lambda: received('NODE-B', 'RR', valid='INVALID')
            and received('NODE-B', 'TEMP', valid='VALID')
        )
        if (
            latest[('NODE-A', 'SPO2')][1].value != 97.0
            or latest[('NODE-B', 'TEMP')][1].value != 36.7
        ):
            raise RuntimeError('PDO scalar mismatch')
        passed('OD fixed point mapping and reserved RR INVALID')
        # 完整验收先验证节点/CAN 隔离，再验证网络缓存；每个动作等待对应结果后继续。
        if not args.smoke:
            for node, key, other, stream in [
                ('NODE-A', 'A', 'NODE-B', 'ECG'),
                ('NODE-B', 'B', 'NODE-A', 'PPG'),
            ]:
                marker = command(key)
                wait(
                    lambda: received(node, 'NODE_STATUS', marker, 'OFFLINE')
                    and received(other, stream, marker, 'VALID')
                )
                passed(node + ' loss isolated from other node')
                marker = command(key)
                wait(lambda: received(node, 'NODE_STATUS', marker, 'VALID'))
                passed(node + ' heartbeat recovered')
            marker = command('E')
            wait(lambda: received('NODE-A', 'FAULT', marker))
            passed('EMCY arrived at MQTT')
            marker = command('E')
            wait(
                lambda: received('NODE-A', 'FAULT', marker)
                and latest[('NODE-A', 'FAULT')][1].value == 'EMCY-0000'
            )
            previous = latest[('NODE-B', 'ECG')][1].session_id
            marker = command('R')
            wait(
                lambda: received('NODE-B', 'ECG', marker, 'VALID')
                and latest[('NODE-B', 'ECG')][1].session_id != previous
            )
            passed('Node communication restart changed generation')
            previous = latest[('NODE-B', 'ECG')][1].session_id
            marker = command('G')
            wait(
                lambda: received('NODE-B', 'ECG', marker, 'VALID')
                and latest[('NODE-B', 'ECG')][1].session_id != previous
            )
            passed('Gateway CANopen restart restored PDO')
            marker = command('C')
            wait(
                lambda: received('NODE-A', 'NODE_STATUS', marker, 'OFFLINE')
                and received('NODE-B', 'NODE_STATUS', marker, 'OFFLINE')
                and received('GATEWAY', 'GATEWAY_STATUS', marker, 'VALID')
            )
            passed('CAN failure leaves MQTT gateway status running')
            marker = command('C')
            wait(
                lambda: received('NODE-A', 'SPO2', marker, 'VALID')
                and received('NODE-B', 'ECG', marker, 'VALID')
            )
            passed('CAN recovery resumes both nodes')
            marker = command('D')
            wait(lambda: any(e['message'] == 'GW WIFI_TEST_DISCONNECTED' for e in lines), 15)
            # 重连后先出现实时帧，然后观察有原采集时间的 REPLAY；缓存容量不足的丢弃由计数如实记录。
            wait(lambda: any(t > marker + 25 and v.source == 'REPLAY' for t, v in events), 130)
            after = [(t, v) for t, v in events if t > marker + 25]
            replay_at = next(t for t, v in after if v.source == 'REPLAY')
            if not any(t < replay_at and v.source == 'MOCK' for t, v in after):
                raise RuntimeError('Realtime priority missing')
            passed('WiFi outage cached data then realtime before rate limited REPLAY')
            if args.ssh_alias:
                marker = time.monotonic()
                result = subprocess.run(
                    ['ssh', args.ssh_alias, 'sudo systemctl restart medical-monitor-mqtt'],
                    capture_output=True,
                    timeout=30,
                )
                if result.returncode:
                    raise RuntimeError('Project Broker restart failed')
                wait(
                    lambda: any(t > marker for t in connections)
                    and any(t > marker + 2 and v.source == 'REPLAY' for t, v in events)
                    and received('NODE-B', 'ECG', marker + 2, 'VALID'),
                    130,
                )
                passed('Broker restart and client resubscription recovered with replay')
        if errors:
            raise RuntimeError('Unexpected message validation errors')
        success = True
    finally:
        # 失败也保存已通过子项与最后指标，避免只有成功截图而无法回溯故障过程。
        client.disconnect()
        client.loop_stop()
        uart.close()
        serial_log.close()
        samples.close()
        counts = Counter(v.stream for _, v in events)
        report = {
            'passed': success,
            'checks': checks,
            'elapsed_s': round(time.monotonic() - start, 2),
            'received': dict(counts),
            'decode_errors': dict(errors),
            'persisted_samples_synthetic_only': True,
            'limitations': [
                'Single-board internal loopback uses two CANopenNode test producers; no physical A/B acceptance',
                'RAM cache is finite and volatile; overflow is counted',
            ],
            'last_metrics': next(
                (x for x in reversed(lines) if x['message'].startswith('GW METRICS')), None
            ),
        }
        (args.output / 'report.json').write_text(
            json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8'
        )


if __name__ == '__main__':
    main()
