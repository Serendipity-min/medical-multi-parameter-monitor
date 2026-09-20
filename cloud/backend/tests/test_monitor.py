"""验收关键语义：断线失效、历史隔离、鉴权、重复包与慢浏览器。"""

import asyncio
import json
from pathlib import Path
import secrets
import sys
import time

import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'tools' / 'mock_gateway'))
from app.adapters import MockJsonAdapter
from app.hub import Hub
from app.main import create_app
from main import make_frame


@pytest.fixture
def client(monkeypatch):
    # 测试令牌每次生成，与部署凭据完全独立。
    device, view = secrets.token_urlsafe(32), secrets.token_urlsafe(32)
    monkeypatch.setenv('MONITOR_DEVICE_TOKEN', device)
    monkeypatch.setenv('MONITOR_VIEW_TOKEN', view)
    monkeypatch.setenv('MONITOR_ALLOWED_ORIGINS', 'http://testserver')
    with TestClient(create_app()) as test_client:
        yield test_client, device, view


def frame(seq=0, control=None):
    return MockJsonAdapter().decode(json.dumps(make_frame(seq, 'test-session', control)))


def test_replay_does_not_refresh_live_and_disconnect_clears_values():
    hub = Hub('GW-DEV-001')
    owner = object()
    assert hub.connect(owner)
    hub.ingest(frame())
    assert hub.snapshot()['live_fresh']
    hub.ingest(frame(1, {'mode': 'REPLAY', 'node_a_online': False}))
    snapshot = hub.snapshot()
    assert snapshot['live']['seq'] == 0
    assert snapshot['live']['nodes']['NODE-A']['online']
    hub.live_received -= 6
    snapshot = hub.snapshot()
    assert snapshot['gateway_online'] and not snapshot['live_fresh']
    assert snapshot['live']['nodes']['NODE-B']['signals']['HR']['value'] is None
    hub.disconnect(owner)
    assert not hub.snapshot()['gateway_online']


@pytest.mark.parametrize('control', [{'quality': 'INVALID'}, {'quality': 'STALE'}, {'node_b_online': False}])
def test_invalid_and_offline_cannot_display_values(control):
    hub = Hub('GW-DEV-001'); hub.connect(object()); hub.ingest(frame(control=control))
    signals = hub.snapshot()['live']['nodes']['NODE-B']['signals']
    assert signals['HR']['value'] is None
    assert signals['ECG']['samples'] == []


def test_old_live_and_duplicate_and_session_rules():
    hub = Hub('GW-DEV-001'); hub.connect(object())
    old = frame(); old.captured_at -= 20
    assert hub.ingest(old)
    assert not hub.snapshot()['live_fresh']
    assert not hub.ingest(frame())
    altered = frame(1); altered.session_id = 'another-session'
    with pytest.raises(ValueError): hub.ingest(altered)
    future = frame(1); future.captured_at = time.time() + 60
    with pytest.raises(ValueError): hub.ingest(future)


def test_bounded_subscriber_and_connection_ownership():
    hub = Hub('GW-DEV-001'); first = object(); second = object()
    assert hub.connect(first)
    assert not hub.connect(second)
    hub.disconnect(second)
    assert hub.owner is first
    queue = asyncio.Queue(maxsize=1); hub.subscribers.add(queue)
    for seq in range(30): hub.ingest(frame(seq))
    assert queue.qsize() == 1
    assert queue.get_nowait()['live']['seq'] == 29


def test_adapter_rejects_incomplete_or_nonfinite_payload():
    payload = make_frame(0, 'test')
    payload['nodes']['NODE-B']['signals']['HR']['value'] = float('nan')
    with pytest.raises(ValueError): MockJsonAdapter().decode(json.dumps(payload))
    payload = make_frame(0, 'test'); del payload['nodes']['NODE-A']
    with pytest.raises(ValueError): MockJsonAdapter().decode(json.dumps(payload))


def test_health_and_websocket_roundtrip(client):
    c, device, view = client
    assert c.get('/health').json()['status'] == 'ok'
    with c.websocket_connect('/ws/v1/monitor', headers={'Origin': 'http://testserver'}) as browser:
        browser.send_json({'token': view}); assert not browser.receive_json()['gateway_online']
        with c.websocket_connect('/device/v1/ingest') as gateway:
            gateway.send_json({'token': device}); assert gateway.receive_json()['type'] == 'ready'
            gateway.send_json(make_frame(0, 'test')); assert gateway.receive_json()['accepted']
            for _ in range(4):
                snapshot = browser.receive_json()
                if snapshot['gateway_online']: break
            assert snapshot['live']['nodes']['NODE-B']['signals']['HR']['value'] == 72
        for _ in range(4):
            snapshot = browser.receive_json()
            if not snapshot['gateway_online']: break
        assert not snapshot['live_fresh']


def test_auth_and_origin_and_role_separation(client):
    c, device, view = client
    for endpoint, token, headers in [('/device/v1/ingest', view, {}), ('/ws/v1/monitor', device, {'Origin': 'http://testserver'}), ('/ws/v1/monitor', view, {'Origin': 'http://untrusted.example'})]:
        with pytest.raises(WebSocketDisconnect):
            with c.websocket_connect(endpoint, headers=headers) as ws:
                ws.send_json({'token': token}); ws.receive_json()


def test_restart_and_browser_resubscribe(client):
    c, device, view = client
    for _ in range(2):
        with c.websocket_connect('/device/v1/ingest') as gateway:
            gateway.send_json({'token': device}); gateway.receive_json()
            gateway.send_json(make_frame(0, 'new-session')); assert gateway.receive_json()['accepted']
            with c.websocket_connect('/ws/v1/monitor', headers={'Origin': 'http://testserver'}) as browser:
                browser.send_json({'token': view}); assert browser.receive_json()['live_fresh']


def test_missing_tokens_fail_startup(monkeypatch):
    monkeypatch.delenv('MONITOR_DEVICE_TOKEN', raising=False)
    monkeypatch.delenv('MONITOR_VIEW_TOKEN', raising=False)
    with pytest.raises(RuntimeError):
        with TestClient(create_app()): pass


@pytest.mark.parametrize('binary', [True, False])
def test_malformed_auth_is_rejected_without_internal_error(client, binary):
    c, _, _ = client
    with pytest.raises(WebSocketDisconnect) as error:
        with c.websocket_connect('/device/v1/ingest') as ws:
            if binary:
                ws.send_bytes(b'not-a-text-frame')
            else:
                ws.send_json({'token': '无效模拟令牌'})
            ws.receive_json()
    assert error.value.code == 1008


def test_binary_device_payload_closes_by_protocol(client):
    c, device, _ = client
    with pytest.raises(WebSocketDisconnect) as error:
        with c.websocket_connect('/device/v1/ingest') as ws:
            ws.send_json({'token': device}); ws.receive_json()
            ws.send_bytes(b'not-MOCK-json'); ws.receive_json()
    assert error.value.code == 1008
