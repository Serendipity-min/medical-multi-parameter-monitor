"""真实 Hub.snapshot 与真实 WSS 的只读适配验证，所有遥测为合成夹具。"""
import asyncio
import json
import sys
import time
from pathlib import Path
from cloud.ai.snapshot import SnapshotReader
from cloud.ai.facts import extract

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'backend'))
from app.hub import Hub
from app.models import Telemetry


def test_monitor_wss_reads_existing_hub_without_mutation(monkeypatch):
    from websockets.asyncio.server import serve
    async def run():
        hub = Hub(['GW-C-001']); hub.broker_connected = True
        stamp = int(time.time() * 1000)
        for node, stream, unit, value in [('GATEWAY', 'GATEWAY_STATUS', 'state', 'ONLINE'),
                                          ('NODE-B', 'NODE_STATUS', 'state', 'ONLINE'),
                                          ('NODE-B', 'HR', 'bpm', 72.0)]:
            hub.ingest(Telemetry(gateway_id='GW-C-001', node_id=node, stream=stream, timestamp=stamp,
                                seq=1, session_id='p6-synthetic-hub', validity='VALID', source='MOCK', synthetic=True, unit=unit, value=value))
        before = hub.accepted
        async def handler(ws):
            auth = json.loads(await ws.recv())
            assert auth == {'token': 'synthetic-monitor-readonly-token-32', 'gateway_id': 'GW-C-001'}
            await ws.send(json.dumps(hub.snapshot(auth['gateway_id'])))
        async with serve(handler, '127.0.0.1', 0) as server:
            port = server.sockets[0].getsockname()[1]
            monkeypatch.setenv('P6_MONITOR_WS_URL', f'ws://127.0.0.1:{port}/ws/v1/monitor')
            monkeypatch.setenv('P6_MONITOR_VIEW_TOKEN', 'synthetic-monitor-readonly-token-32')
            snap = await SnapshotReader('MONITOR').read('GW-C-001')
            assert extract(snap, 'GW-C-001', int(time.time() * 1000))[0]['value'] == 72.0
            assert hub.accepted == before and not hub.subscribers
    asyncio.run(run())
