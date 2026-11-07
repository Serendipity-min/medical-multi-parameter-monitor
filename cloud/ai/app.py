"""隔离 FastAPI 应用：鉴权、容量/超时/会话上限，故障不触碰监护主链。"""
import asyncio
from collections import OrderedDict, deque
from dataclasses import dataclass
import hmac
import os
import time
import uuid
import httpx
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pathlib import Path
from pydantic import BaseModel, ConfigDict, Field, ValidationError
from .downlink import IsolatedPublisher, short_text
from .facts import ADVICE_TEXT, CLARIFY_TEXT, extract, digest, answer_facts, question_rule
from .providers import Provider
from .snapshot import SnapshotReader
from .appliance_reply import RecordingReplyAdapter, UNAVAILABLE
from .facts import CHANNELS


@dataclass
class Settings:
    token: str
    mode: str = 'MOCK'
    snapshot_mode: str = 'MOCK'
    gateways: tuple = ('GW-B5-001',)

    @classmethod
    def from_env(cls):
        return cls(os.environ.get('P6_AI_TOKEN', ''), os.environ.get('P6_MODEL_MODE', 'MOCK'), os.environ.get('P6_SNAPSHOT_MODE', 'MOCK'))


class Question(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    session_id: str = Field(pattern='^[0-9a-f]{32}$')
    gateway_id: str = Field(pattern='^GW-B5-001$')
    question: str = Field(min_length=1, max_length=500)
    voice: bool = False


def create_app(settings=None, reader=None, provider=None, publisher=None):
    settings = settings or Settings.from_env()
    if len(settings.token) < 32:
        raise ValueError('P6_AI_TOKEN_REQUIRED')
    if CHANNELS['TEMP'][0] != 'NODE-D' or CHANNELS['NIBP'][0] != 'NODE-E':
        raise ValueError('FIVE_PROFILE_REQUIRED')
    if reader is None and settings.snapshot_mode == 'MONITOR' and not os.environ.get('P6_MONITOR_WS_URL'):
        raise ValueError('EXPLICIT_ISOLATED_MONITOR_URL_REQUIRED')
    app = FastAPI(title='P6 文字问答', docs_url=None, redoc_url=None, openapi_url=None)
    app.add_middleware(CORSMiddleware, allow_origins=[s for s in os.environ.get('P6_ALLOWED_ORIGINS', '').split(',') if s],
                       allow_methods=['POST', 'GET'], allow_headers=['Authorization', 'Content-Type'])
    reader = reader or SnapshotReader(settings.snapshot_mode)
    provider = provider or Provider(settings.mode)
    sessions, requests = OrderedDict(), deque()
    active = set()
    if publisher is None and os.environ.get('P6_MQTT_MODE') == 'ISOLATED':
        transport = IsolatedPublisher(int(os.environ['P6_MQTT_PORT']), os.environ['P6_MQTT_USERNAME'], os.environ['P6_MQTT_PASSWORD'])
        async def send_recording_reply(topic, packet):
            await asyncio.to_thread(transport._send, topic, packet)
        publisher = RecordingReplyAdapter(send_recording_reply)
    app.state.recording_reply = publisher

    def authenticate(request):
        if not hmac.compare_digest(request.headers.get('authorization', ''), 'Bearer ' + settings.token):
            raise HTTPException(401, 'AI_AUTH_REQUIRED')

    @app.get('/health')
    @app.get('/medical-monitor/ai/health')
    async def health():
        return {'status': 'ok', 'model_mode': settings.mode, 'snapshot_mode': settings.snapshot_mode,
                'real_model': 'REAL_MODEL_BLOCKED' if settings.mode == 'MOCK' else 'REAL_MODEL_VERIFIED' if (getattr(provider, 'last_call', None) or {}).get('status') == 'VALIDATED' else 'CONFIGURED_NOT_PROVEN',
                'voice_mode': 'ISOLATED' if publisher else 'DISABLED',
                'model_id': getattr(provider, 'model', None), 'budget_used': getattr(provider, 'budget_used', 0),
                'usage': provider.ledger.summary() if getattr(provider, 'budget_dir', None) else None}

    @app.post('/api/v1/text')
    @app.post('/medical-monitor/ai/api/v1/text')
    async def text(request: Request):
        authenticate(request)
        raw = bytearray()
        # 流式限长先于解析，验证错误不回显用户问题或鉴权字段。
        async for chunk in request.stream():
            if len(raw) + len(chunk) > 4096:
                raise HTTPException(413, 'REQUEST_SIZE')
            raw.extend(chunk)
        try:
            question = Question.model_validate_json(raw)
            if not question.question.strip() or any(ord(c) < 32 for c in question.question):
                raise ValueError('QUESTION_TEXT')
            question.question.encode('utf-8', errors='strict')
        except (ValidationError, ValueError):
            raise HTTPException(422, 'QUESTION_INVALID') from None
        if question.gateway_id not in settings.gateways:
            raise HTTPException(403, 'GATEWAY_NOT_ALLOWED')
        now = time.monotonic()
        while requests and now - requests[0] >= 60:
            requests.popleft()
        if len(requests) >= 12 or len(active) >= 4 or question.session_id in active:
            raise HTTPException(429, 'AI_RATE_LIMIT')
        requests.append(now)
        active.add(question.session_id)
        try:
            # 同会话串行、总会话有界；网关切换清空上下文，防止不同来源串位。
            for key, entry in list(sessions.items()):
                if now - entry['at'] >= 1800:
                    sessions.pop(key)
            session = sessions.get(question.session_id, {'gateway': question.gateway_id, 'history': []})
            if session['gateway'] != question.gateway_id:
                session = {'gateway': question.gateway_id, 'history': []}
            async with asyncio.timeout(12):
                kind, streams = question_rule(question.question)
                facts = []
                if streams:
                    snapshot = await reader.read(question.gateway_id)
                    facts = [f for f in extract(snapshot, question.gateway_id, int(time.time() * 1000))
                             if f['stream'] in streams]
                answer = (ADVICE_TEXT if kind == 'GENERAL_ADVICE' else CLARIFY_TEXT if kind == 'CLARIFY'
                          else answer_facts(facts, question.question))
                turn_id, fact_digest = uuid.uuid4().hex, digest(facts)
                voice_text = (CLARIFY_TEXT if kind == 'MULTI_VALUE' else UNAVAILABLE
                              if kind == 'SINGLE_VALUE' and (not facts or facts[0]['value'] is None)
                              else short_text(answer.split('\n')[0]))
                voice_status = 'PAUSED'
                # 浏览器取消/关闭后禁止继续下发；已经交给 Broker 的消息无法本地撤回。
                if await request.is_disconnected():
                    raise HTTPException(499, 'TURN_CANCELLED')
                if question.voice:
                    if publisher is None:
                        voice_status = 'DISABLED'
                    else:
                        try:
                            voice_status = await publisher.publish_facts(question.gateway_id, turn_id, facts, question.question, int(time.time() * 1000))
                        except Exception:
                            voice_status = 'DOWNLINK_FAILED'
                session.update(at=now, history=(session['history'] + [{'question': question.question, 'answer': answer}])[-4:])
                sessions[question.session_id] = session
                sessions.move_to_end(question.session_id)
                while len(sessions) > 128:
                    sessions.popitem(last=False)
                return dict(turn_id=turn_id, session_id=question.session_id, gateway_id=question.gateway_id,
                            model_mode=settings.mode, answer_kind=kind,
                            answer=answer, facts=facts, fact_digest=fact_digest, voice_text=voice_text,
                            model_evidence=None, model_input_fact_digest=None,
                            voice_status=voice_status, real_model='REAL_MODEL_BLOCKED' if settings.mode == 'MOCK' else 'NOT_CALLED')
        except (TimeoutError, httpx.TimeoutException):
            raise HTTPException(504, 'AI_TIMEOUT') from None
        except HTTPException:
            raise
        except asyncio.CancelledError:
            raise
        except Exception:
            # 第三方异常含 URL/头/用户内容的可能性，统一固定错误码，禁止转存原异常。
            raise HTTPException(503, 'AI_UNAVAILABLE') from None
        finally:
            active.discard(question.session_id)
    # 隔离大屏仅在明确配置静态目录时托管，不写生产 Nginx 或原监护 Web。
    web_dir = os.environ.get('P6_WEB_DIR')
    if web_dir:
        if not Path(web_dir).is_dir():
            raise ValueError('P6_WEB_DIR_REQUIRED')
        app.mount('/medical-monitor', StaticFiles(directory=web_dir, html=True), name='p6-preview')
    return app
