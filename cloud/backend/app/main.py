"""FastAPI 入口：MQTT 订阅接入设备，鉴权后向浏览器推送；外层由 Nginx 终止 HTTPS。"""

import asyncio
import contextlib
import json
import logging
import os
import secrets
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from .mqtt_adapter import MqttAdapter
from .hub import Hub

logger = logging.getLogger('medical-monitor')


async def receive_text_frame(ws: WebSocket) -> str:
    # 浏览器只接受文本鉴权帧，二进制帧按无效输入拒绝。
    message = await ws.receive()
    if message['type'] == 'websocket.disconnect':
        raise WebSocketDisconnect(message.get('code', 1000))
    text = message.get('text')
    if not isinstance(text, str):
        raise ValueError('text frame required')
    return text


def create_app() -> FastAPI:
    @asynccontextmanager
    async def lifespan(app):
        view_token = os.environ.get('MONITOR_VIEW_TOKEN', '')
        if len(view_token) < 32:
            raise RuntimeError('Configure a view token of at least 32 characters')
        app.state.tokens = {'view': view_token}
        app.state.origins = set(os.environ.get('MONITOR_ALLOWED_ORIGINS', 'http://127.0.0.1:5173').split(','))
        gateways = os.environ.get('MONITOR_GATEWAY_IDS', 'GW-DEV-001,GW-C-001').split(',')
        app.state.hub = Hub(gateways)
        config = os.environ.get('MONITOR_MQTT_CONFIG')
        # 单元测试可显式关闭网络；正式启动缺少配置立即失败，避免假健康。
        if not config and os.environ.get('MONITOR_TESTING') != '1':
            raise RuntimeError('MONITOR_MQTT_CONFIG is required')
        adapter = MqttAdapter(app.state.hub, config) if config else None
        app.state.adapter = adapter
        mqtt_task = asyncio.create_task(adapter.run()) if adapter else None

        async def tick():
            while True:
                await asyncio.sleep(.1)
                app.state.hub.publish()

        task = asyncio.create_task(tick())
        try:
            yield
        finally:
            if mqtt_task:
                mqtt_task.cancel()
                await asyncio.gather(mqtt_task, return_exceptions=True)
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await task

    app = FastAPI(title='Medical monitor', lifespan=lifespan,
                  docs_url=None, redoc_url=None, openapi_url=None)

    @app.get('/health')
    @app.get('/api/health')
    async def health():
        return {'status': 'ok' if app.state.hub.broker_connected else 'degraded',
                'transport': 'MQTT 3.1.1/TLS', 'mqtt_connected': app.state.hub.broker_connected,
                'accepted': app.state.hub.accepted, 'rejected': app.state.hub.rejected,
                'dropped': app.state.adapter.dropped if app.state.adapter else 0}

    async def authenticate(ws: WebSocket, role: str) -> bool:
        origin = ws.headers.get('origin')
        if (role == 'view' and origin not in app.state.origins) or (origin and origin not in app.state.origins):
            await ws.close(code=1008)
            return False
        await ws.accept()
        try:
            # 首帧鉴权避免 Token 出现在 URL、Nginx 日志及浏览器历史中。
            raw = await asyncio.wait_for(receive_text_frame(ws), 5)
            data = json.loads(raw)
            token = data.get('token', '') if isinstance(data, dict) else ''
            if len(raw) > 4096 or not isinstance(token, str) or not token.isascii() or not secrets.compare_digest(token, app.state.tokens[role]):
                raise ValueError('authentication rejected')
            gateway = data.get('gateway_id', app.state.hub.gateways[0])
            if gateway not in app.state.hub.gateways:
                raise ValueError('gateway rejected')
            ws.state.gateway_id = gateway
        except (ValueError, asyncio.TimeoutError, WebSocketDisconnect):
            with contextlib.suppress(RuntimeError, WebSocketDisconnect):
                await ws.close(code=1008)
            logger.info('authentication rejected role=%s', role)
            return False
        return True

    @app.websocket('/ws/v1/monitor')
    async def monitor(ws: WebSocket):
        if not await authenticate(ws, 'view'):
            return
        hub = app.state.hub
        if len(hub.subscribers) >= 32:
            await ws.close(code=1013)
            return
        queue = asyncio.Queue(maxsize=1)
        hub.subscribers[queue] = ws.state.gateway_id
        queue.put_nowait(hub.snapshot(ws.state.gateway_id))

        async def sender():
            while True:
                await asyncio.wait_for(ws.send_json(await queue.get()), timeout=5)

        async def receiver():
            while True:
                await receive_text_frame(ws)

        tasks = {asyncio.create_task(sender()), asyncio.create_task(receiver())}
        try:
            # 接收与发送任一结束都回收队列和协程，浏览器断开不会残留订阅。
            done, _ = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
            for task in done:
                task.result()
        except (WebSocketDisconnect, RuntimeError, ValueError, asyncio.TimeoutError):
            pass
        finally:
            hub.subscribers.pop(queue, None)
            for task in tasks:
                task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)
            with contextlib.suppress(RuntimeError, WebSocketDisconnect):
                await ws.close()

    static = os.environ.get('MONITOR_WEB_DIR')
    if static:
        app.mount('/', StaticFiles(directory=Path(static), html=True), name='web')
    return app


app = create_app()
