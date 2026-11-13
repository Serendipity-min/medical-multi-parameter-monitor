"""本地 UI 回归夹具：真实 Backend/Hub + 明确 MOCK 数据，仅监听回环接口。"""
import argparse
import asyncio
from contextlib import asynccontextmanager
import json
import os
from pathlib import Path
import secrets
import sys
import time
import uuid

parser = argparse.ArgumentParser()
parser.add_argument('--repo', type=Path, required=True)
parser.add_argument('--output', type=Path, required=True)
parser.add_argument('--reuse-config', action='store_true', help='重启本机预览时保留仓库外的临时只读令牌')
parser.add_argument('--port', type=int, default=18765, help='独立回环验收端口，避免测试故障开关影响用户预览')
args = parser.parse_args()
if not 1024 <= args.port <= 65535:
    parser.error('预览端口必须在 1024–65535 之间')
args.repo = args.repo.resolve()
args.output = args.output.resolve()
if args.output.is_relative_to(args.repo):
    parser.error('临时凭据目录必须在仓库之外')
args.output.mkdir(parents=True, exist_ok=True)
control_file = args.output / 'control.json'
control_file.write_text('{}', encoding='utf-8')
# 凭据只在本次进程生成并保存在仓库外；不会连接 MQTT 或任何外部服务器。
token = secrets.token_urlsafe(32)
origin = f'http://127.0.0.1:{args.port}'
config_file = args.output / 'config.json'
if args.reuse_config and config_file.exists():
    # 仅复用同一回环预览的外部配置；不读取服务器凭据或浏览器存储。
    previous = json.loads(config_file.read_text(encoding='utf-8'))
    if previous.get('origin') != origin or not isinstance(previous.get('view_token'), str) or len(previous['view_token']) < 32:
        parser.error('预览配置无效')
    token = previous['view_token']
config_file.write_text(json.dumps({'origin': origin, 'view_token': token}), encoding='utf-8')
os.environ['MONITOR_TESTING'] = '1'
os.environ.pop('MONITOR_MQTT_CONFIG', None)
os.environ['MONITOR_VIEW_TOKEN'] = token
os.environ['MONITOR_ALLOWED_ORIGINS'] = origin
os.environ['MONITOR_WEB_DIR'] = str(args.repo / 'cloud/web/dist')
sys.path[:0] = [str(args.repo / 'cloud/backend'), str(args.repo / 'cloud/tools')]
from app.main import create_app
from app.adapters import decode_mqtt
from app.models import CHANNELS, WAVES
from mock_mqtt.main import payload, read_control
from preview_signals import PreviewTimeline, scalar_value, waveform
from fastapi import FastAPI
import uvicorn

child = create_app()


async def inject():
    seq = 0
    timeline = PreviewTimeline()
    session = 'preview-' + uuid.uuid4().hex[:16]
    origin_ms = int(time.time() * 1000)
    started = asyncio.get_running_loop().time()
    while True:
        elapsed = asyncio.get_running_loop().time() - started
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
                    validity = control.get('validities', {}).get(stream, control.get('validity', 'VALID'))
                    fixed = control.get('scenario') == 'fixed'
                    signature = json.dumps([source, validity, fixed, control.get('session'), control.get('values', {}).get(stream)])
                    captured = timeline.capture(stream, elapsed, signature)
                    if captured is None:
                        continue
                    value = control.get('values', {}).get(stream, scalar_value(stream, captured, fixed))
                    body = payload(control.get('session', session), seq, stream, value,
                                   source=source, validity=validity)
                    # 固定采样时基，避免系统调度抖动制造波形重叠；标量保持真实测量时刻。
                    body['timestamp'] = origin_ms + round(captured * 1000)
                    if source == 'REPLAY':
                        body['timestamp'] -= 60000
                    if stream in WAVES:
                        body.update(waveform(stream, captured, fixed))
                    kind = 'replay' if source == 'REPLAY' else 'telemetry'
                    send(f'{node}/{kind}/{stream.lower()}', body)
            seq += 1
        # 落后时跳过过期时间槽，不追发一串伪造的历史测量。
        next_slot = (int(elapsed / .2) + 1) * .2
        await asyncio.sleep(max(.001, started + next_slot - asyncio.get_running_loop().time()))


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
uvicorn.run(app, host='127.0.0.1', port=args.port, access_log=False)
