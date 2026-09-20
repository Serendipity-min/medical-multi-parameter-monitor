"""FastAPI 入口：鉴权后接入模拟设备与浏览器，外层由现有 Nginx 终止 TLS。"""

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
from pydantic import ValidationError
from .adapters import MockJsonAdapter
from .hub import Hub

logger = logging.getLogger('medical-monitor')


async def receive_text_frame(ws: WebSocket) -> str:
    # MOCK/1 仅接受文本帧；二进制帧应按协议拒绝，不能触发内部 KeyError。
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
        device_token = os.environ.get('MONITOR_DEVICE_TOKEN', '')
        view_token = os.environ.get('MONITOR_VIEW_TOKEN', '')
        if min(len(device_token), len(view_token)) < 32 or device_token == view_token:
            raise RuntimeError('Configure two distinct tokens of at least 32 characters')
        app.state.tokens = {'device': device_token, 'view': view_token}
        app.state.origins = set(os.environ.get('MONITOR_ALLOWED_ORIGINS', 'http://127.0.0.1:5173').split(','))
        app.state.hub = Hub(os.environ.get('MONITOR_GATEWAY_ID', 'GW-DEV-001'))

        async def tick():
            while True:
                await asyncio.sleep(1)
                app.state.hub.publish()

        task = asyncio.create_task(tick())
        try:
            yield
        finally:
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await task

    app = FastAPI(title='Medical monitor simulation', lifespan=lifespan,
                  docs_url=None, redoc_url=None, openapi_url=None)

    @app.get('/health')
    @app.get('/api/health')
    async def health():
        return {'status': 'ok', 'simulation': True, 'protocol': 'MVIEW/1'}

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
        except (ValueError, asyncio.TimeoutError, WebSocketDisconnect):
            with contextlib.suppress(RuntimeError, WebSocketDisconnect):
                await ws.close(code=1008)
            logger.info('authentication rejected role=%s', role)
            return False
        return True

    @app.websocket('/device/v1/ingest')
    async def ingest(ws: WebSocket):
        if not await authenticate(ws, 'device'):
            return
        hub = app.state.hub
        owner = object()
        if not hub.connect(owner):
            await ws.close(code=1008, reason='gateway already connected')
            return
        logger.info('gateway connected')
        try:
            await ws.send_json({'type': 'ready'})
            while True:
                try:
                    raw = await receive_text_frame(ws)
                    if len(raw) > 65536:
                        await ws.close(code=1009)
                        break
                    accepted = hub.ingest(MockJsonAdapter().decode(raw))
                except (ValueError, ValidationError):
                    # 不输出原始载荷/异常详情，防止凭据或后续真实数据进入日志。
                    await ws.close(code=1008, reason='invalid MOCK/1 frame')
                    break
                await ws.send_json({'type': 'ack', 'accepted': accepted})
        except WebSocketDisconnect:
            pass
        finally:
            hub.disconnect(owner)
            logger.info('gateway disconnected')

    @app.websocket('/ws/v1/monitor')
    async def monitor(ws: WebSocket):
        if not await authenticate(ws, 'view'):
            return
        hub = app.state.hub
        if len(hub.subscribers) >= 32:
            await ws.close(code=1013)
            return
        queue = asyncio.Queue(maxsize=1)
        hub.subscribers.add(queue)
        queue.put_nowait(hub.snapshot())

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
            hub.subscribers.discard(queue)
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
