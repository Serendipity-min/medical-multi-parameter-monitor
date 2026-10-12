"""只读 WSS 快照或明确标记的 MOCK；不注入 Hub，不扩大监护接口。"""
import asyncio
import json
import os
import time
from .facts import CHANNELS


class SnapshotReader:
    def __init__(self, mode: str):
        if mode not in ('MONITOR', 'MOCK'):
            raise ValueError('SNAPSHOT_MODE')
        self.mode = mode

    async def read(self, gateway: str) -> dict:
        if self.mode == 'MOCK':
            now = int(time.time() * 1000)
            values = {'HR': 72.0, 'SPO2': 98.0, 'PR': 71.0, 'RR': None, 'TEMP': 36.5, 'NIBP': [118.0, 76.0]}
            return dict(type='snapshot', schema_version=1, gateway_id=gateway, gateway_state='ONLINE', broker_connected=True,
                        nodes={'NODE-A': 'ONLINE', 'NODE-B': 'ONLINE'}, server_time=now,
                        streams=[dict(gateway_id=gateway, node_id=spec[0], stream=name, unit=spec[1],
                                      timestamp=now, session_id='p6-synthetic-fixture', seq=1,
                                      validity='INVALID' if value is None else 'VALID', source='MOCK', synthetic=True, value=value)
                                 for name, value in values.items() for spec in [CHANNELS[name]]])
        from websockets.asyncio.client import connect
        uri = os.environ.get('P6_MONITOR_WS_URL', 'ws://127.0.0.1:18765/ws/v1/monitor')
        token = os.environ.get('P6_MONITOR_VIEW_TOKEN', '')
        if len(token) < 32 or not (uri.startswith('wss://') or uri.startswith('ws://127.0.0.1:')):
            raise ValueError('READONLY_MONITOR_CONFIG')
        # 每次请求有界获取一次服务端快照并关闭连接，避免旧缓存或订阅者泄漏。
        async with asyncio.timeout(3):
            async with connect(uri, origin=os.environ.get('P6_MONITOR_ORIGIN'), max_size=65536, max_queue=1, open_timeout=2) as ws:
                await ws.send(json.dumps({'token': token, 'gateway_id': gateway}))
                return json.loads(await ws.recv())
