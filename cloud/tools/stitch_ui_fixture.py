"""本地 UI 回归夹具：真实 Backend/Hub + 明确 MOCK 数据，仅监听回环接口。"""
import argparse
import asyncio
from contextlib import asynccontextmanager
import json
import os
from pathlib import Path
import secrets
import sys

parser = argparse.ArgumentParser()
parser.add_argument('--repo', type=Path, required=True)
parser.add_argument('--output', type=Path, required=True)
args = parser.parse_args()
args.repo = args.repo.resolve()
args.output = args.output.resolve()
if args.output.is_relative_to(args.repo):
    parser.error('临时凭据目录必须在仓库之外')
args.output.mkdir(parents=True, exist_ok=True)
control_file = args.output / 'control.json'
control_file.write_text('{}', encoding='utf-8')
# 凭据只在本次进程生成并保存在仓库外；不会连接 MQTT 或任何外部服务器。
token = secrets.token_urlsafe(32)
origin = 'http://127.0.0.1:18765'
(args.output / 'config.json').write_text(json.dumps({'origin': origin, 'view_token': token}), encoding='utf-8')
os.environ['MONITOR_TESTING'] = '1'
os.environ.pop('MONITOR_MQTT_CONFIG', None)
os.environ['MONITOR_VIEW_TOKEN'] = token
os.environ['MONITOR_ALLOWED_ORIGINS'] = origin
os.environ['MONITOR_WEB_DIR'] = str(args.repo / 'cloud/web/dist')
sys.path[:0] = [str(args.repo / 'cloud/backend'), str(args.repo / 'cloud/tools')]
from app.main import create_app
from app.adapters import decode_mqtt
from app.models import CHANNELS, WAVES
from mock_mqtt.main import payload, read_control, wave
from fastapi import FastAPI
import uvicorn

child = create_app()


async def inject():
    seq = 0
    values = {'HR': 72.0, 'RR': 15.0, 'SPO2': 98.0, 'PR': 72.0, 'TEMP': 36.6, 'NIBP': [118.0, 76.0]}
    while True:
        control = read_control(control_file)
        hub = child.state.hub
        hub.broker_connected = control.get('network_online', True)
        if hub.broker_connected and not control.get('pause'):
            base = 'mpm/v1/GW-DEV-001'
            # 状态消息保持当前时间；REPLAY 仅进入历史面板，不能续活实时测量值。
            def send(suffix, body):
                hub.ingest(decode_mqtt(base + '/' + suffix, json.dumps(body).encode()))

            send('status', payload('local-ui-fixture', seq, 'GATEWAY_STATUS', 'ONLINE'))
            for node, streams in CHANNELS.items():
                online = control.get('node_a_online' if node == 'NODE-A' else 'node_b_online', True)
                send(node + '/status', payload('local-ui-fixture', seq, 'NODE_STATUS',
                     'ONLINE' if online else 'OFFLINE', validity='VALID' if online else 'OFFLINE'))
                for stream in streams:
                    source = control.get('mode', 'MOCK')
                    body = payload(control.get('session', 'local-ui-fixture'), seq, stream,
                                   control.get('values', {}).get(stream, values.get(stream)),
                                   source=source, validity=control.get('validities', {}).get(stream, control.get('validity', 'VALID')))
                    if source == 'REPLAY':
                        body['timestamp'] -= 60000
                    if stream in WAVES:
                        body.update(wave(stream, seq))
                    kind = 'replay' if source == 'REPLAY' else 'telemetry'
                    send(f'{node}/{kind}/{stream.lower()}', body)
            seq += 1
        await asyncio.sleep(0.2)


@asynccontextmanager
async def lifespan(app):
    # 挂载子应用的生命周期需显式管理；退出时回收注入任务及 Backend 自有任务。
    async with child.router.lifespan_context(child):
        task = asyncio.create_task(inject())
        try:
            yield
        finally:
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)


app = FastAPI(lifespan=lifespan, docs_url=None, redoc_url=None, openapi_url=None)
app.mount('/medical-monitor', child)
uvicorn.run(app, host='127.0.0.1', port=18765, access_log=False)
