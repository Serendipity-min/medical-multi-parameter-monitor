"""真机合成源验收：只保存归一化状态，不保存凭据、地址或串口原始回复。"""
import argparse
import asyncio
import json
from pathlib import Path
import subprocess
import time

import serial
from websockets.asyncio.client import connect


async def main(args):
    config = json.loads(args.config.read_text(encoding='utf-8'))
    checks, transitions, logs = [], [], []
    port = serial.Serial(port=None, baudrate=115200, timeout=0.01)
    # CH340 的 DTR/RTS 不参与本次测试，避免开串口时误复位。
    port.dtr = False
    port.rts = False
    port.port = args.port
    port.open()
    pending = b''
    started = time.monotonic()
    try:
        async with connect(config['browser_url'], origin=config['origin']) as ws:
            await ws.send(json.dumps({'token': config['view_token'], 'gateway_id': 'GW-C-001'}))

            async def wait(predicate, timeout=90):
                nonlocal pending
                deadline = time.monotonic() + timeout
                while time.monotonic() < deadline:
                    pending += port.read(port.in_waiting)
                    parts = pending.split(b'\n')
                    pending = parts.pop()
                    for line in parts:
                        # 固件仅打印白名单状态；不接收通用 AT/网络数据作为证据。
                        text = line.decode('ascii', errors='ignore').strip()
                        if text.startswith('GW '):
                            logs.append(text)
                    snapshot = json.loads(await asyncio.wait_for(ws.recv(), 10))
                    state = snapshot['gateway_state']
                    if not transitions or transitions[-1]['state'] != state:
                        transitions.append({'seconds': round(time.monotonic()-started, 2), 'state': state})
                    if predicate(snapshot):
                        return snapshot
                raise AssertionError('Gateway state did not converge before timeout')

            def valid(snapshot):
                streams = {item['stream']: item for item in snapshot['streams']}
                return (snapshot['gateway_state'] == 'ONLINE' and len(streams) == 9
                        and all(item['validity'] == 'VALID' and item['source'] == 'MOCK'
                                and item['synthetic'] for item in streams.values())
                        and streams['HR']['value'] == 73 and streams['RR']['value'] == 16
                        and len(streams['ECG']['samples']) == 250
                        and len(streams['PPG']['samples']) == 50
                        and len(streams['RESP']['samples']) == 50)

            snapshot = await wait(valid)
            first = next(item for item in snapshot['streams'] if item['stream'] == 'HR')
            await wait(lambda s: valid(s) and next(i for i in s['streams'] if i['stream']=='HR')['seq'] >= first['seq'] + 5)
            checks.append('STM32 Paho MQTT 3.1.1 publishes nine synthetic streams through verified TLS')
            print('PASS hardware data progression', flush=True)
            port.write(b'D')
            await wait(lambda s: s['gateway_state'] == 'OFFLINE', 45)
            checks.append('ESP Wi-Fi disconnect produces Gateway OFFLINE')
            await wait(valid, 100)
            checks.append('ESP Wi-Fi reconnect restores nine streams without a PC publisher')
            print('PASS Wi-Fi loss and recovery', flush=True)
            if args.ssh_alias:
                # 明确授权的项目 Broker 重启，失败时 finally 保证恢复服务。
                try:
                    result = subprocess.run(['ssh', args.ssh_alias, 'sudo systemctl stop medical-monitor-mqtt'], capture_output=True, timeout=30)
                    assert result.returncode == 0
                    await wait(lambda s: s['gateway_state'] == 'OFFLINE', 20)
                finally:
                    result = subprocess.run(['ssh', args.ssh_alias, 'sudo systemctl start medical-monitor-mqtt'], capture_output=True, timeout=30)
                    assert result.returncode == 0
                await wait(valid, 100)
                checks.append('STM32 reconnects after Broker restart and republishes retained state')
                print('PASS hardware Broker recovery', flush=True)
    finally:
        port.close()
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps({'checks': checks, 'transitions': transitions,
            'serial_status': logs, 'duration_seconds': round(time.monotonic()-started, 2),
            'source': 'MOCK', 'physical_sensors': False}, indent=2, ensure_ascii=False)+'\n', encoding='utf-8')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--config', type=Path, required=True)
    parser.add_argument('--port', default='COM15')
    parser.add_argument('--ssh-alias')
    parser.add_argument('--output', type=Path, required=True)
    asyncio.run(main(parser.parse_args()))
