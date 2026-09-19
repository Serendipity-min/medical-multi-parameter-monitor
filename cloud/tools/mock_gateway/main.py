"""本地模拟网关：只生成合成波形，不读取患者或硬件数据。"""

import argparse
import asyncio
import json
import math
import os
from pathlib import Path
import time
import uuid

from websockets.asyncio.client import connect
from websockets.exceptions import ConnectionClosed, InvalidHandshake


def make_frame(seq: int, session_id: str, control: dict | None = None) -> dict:
    control = control or {}
    mode = control.get('mode', 'LIVE')
    quality = control.get('quality', 'VALID')
    now = time.time() - (60 if mode == 'REPLAY' else 0)

    def wave(name: str, rate: int):
        points = []
        for i in range(rate // 5):
            t = seq * .2 + i / rate
            phase = (t * 1.2) % 1
            if name == 'ECG':
                y = .10 * math.sin(2 * math.pi * phase) + math.exp(-((phase - .25) / .022)**2) - .22 * math.exp(-((phase - .30) / .028)**2)
            elif name == 'PPG':
                y = max(0, math.sin(math.pi * phase)) ** 3
            else:
                y = .8 * math.sin(2 * math.pi * .25 * t)
            points.append(round(y, 5))
        return {'quality': quality, 'samples': points, 'sample_rate': rate}

    def scalar(value):
        return {'quality': quality, 'value': value}

    return {'protocol': 'MOCK/1', 'gateway_id': 'GW-DEV-001', 'session_id': session_id,
            'seq': seq, 'mode': mode, 'captured_at': now, 'simulation': True,
            'nodes': {
                'NODE-A': {'online': control.get('node_a_online', True), 'signals': {
                    'PPG': wave('PPG', 50), 'SpO2': scalar(98.0), 'PR': scalar(72.0),
                    'NIBP': scalar([118.0, 76.0])}},
                'NODE-B': {'online': control.get('node_b_online', True), 'signals': {
                    'ECG': wave('ECG', 250), 'RESP': wave('RESP', 50), 'HR': scalar(72.0),
                    'RR': scalar(15.0), 'TEMP': scalar(36.6)}}}}


def read_control(path: Path | None) -> dict:
    if not path or not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding='utf-8-sig'))
        if not isinstance(data, dict) or data.get('mode', 'LIVE') not in {'LIVE', 'REPLAY'} or data.get('quality', 'VALID') not in {'VALID', 'INVALID', 'STALE'}:
            raise ValueError
        for field in ('node_a_online', 'node_b_online', 'network_online', 'pause'):
            if field in data and type(data[field]) is not bool:
                raise ValueError
        return data
    except (ValueError, OSError):
        # 控制文件正被编辑时停止发帧，不把半写入内容当作正常状态。
        return {'pause': True}


async def run(url: str, token: str, control_path: Path | None, duration: float):
    if not url.startswith(('wss://', 'ws://127.0.0.1:', 'ws://localhost:')):
        raise ValueError('Remote gateway connections require WSS')
    started = time.monotonic()
    session_id, seq = str(uuid.uuid4()), 0
    while duration <= 0 or time.monotonic() - started < duration:
        if not read_control(control_path).get('network_online', True):
            await asyncio.sleep(.2)
            continue
        try:
            # 使用系统信任链，严禁通过关闭证书校验完成 WSS 验收。
            async with connect(url, max_size=65536, open_timeout=10, ping_interval=20) as ws:
                await ws.send(json.dumps({'token': token}))
                await ws.recv()
                print('MOCK connected', flush=True)
                while duration <= 0 or time.monotonic() - started < duration:
                    control = read_control(control_path)
                    if not control.get('network_online', True):
                        break
                    if not control.get('pause', False):
                        await ws.send(json.dumps(make_frame(seq, session_id, control)))
                        await ws.recv()
                        seq += 1
                    await asyncio.sleep(.2)
        except (OSError, TimeoutError, ConnectionClosed, InvalidHandshake) as exc:
            # 只记录异常类型，不回显含域名或鉴权信息的连接错误正文。
            print(f'MOCK reconnect pending: {type(exc).__name__}', flush=True)
            await asyncio.sleep(1)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='MOCK/1 synthetic gateway')
    parser.add_argument('--config', type=Path, help='外部 JSON 配置，包含 device_url 和 device_token')
    parser.add_argument('--control', type=Path, help='运行中可编辑的模拟状态 JSON')
    parser.add_argument('--duration', type=float, default=0, help='秒；0 表示持续运行，Ctrl+C 停止')
    args = parser.parse_args()
    config = json.loads(args.config.read_text(encoding='utf-8-sig')) if args.config else {}
    url = config.get('device_url', os.environ.get('MONITOR_DEVICE_URL', 'ws://127.0.0.1:18765/device/v1/ingest'))
    token = config.get('device_token', os.environ.get('MONITOR_DEVICE_TOKEN', ''))
    if not token:
        parser.error('Configure MONITOR_DEVICE_TOKEN or external config')
    try:
        asyncio.run(run(url, token, args.control, args.duration))
    except KeyboardInterrupt:
        print('MOCK stopped')
