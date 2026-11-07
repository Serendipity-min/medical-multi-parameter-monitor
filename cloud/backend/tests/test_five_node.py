"""MPM_NODE_PROFILE=five；仅合成输入，经真实 MQTT 解析、Hub 和 WSS 验证来源与失效。"""
import json
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.adapters import decode_mqtt
from app.hub import Hub
from app.main import create_app
from app.models import NODE_PROFILE
from cloud.ai.facts import extract

pytestmark = pytest.mark.skipif(NODE_PROFILE != 'five', reason='run in dedicated five-node process')
GW = 'GW-DEV-001'
START = 1800000000.0


def frame(node, stream, value, stamp=START, seq=1, session='node-session', replay=False):
    suffix = 'status' if node == 'GATEWAY' else f'{node}/status' if stream == 'STATUS' else f'{node}/{"replay" if replay else "telemetry"}/{stream.lower()}'
    unit = 'state' if stream == 'STATUS' else 'mmHg' if stream == 'NIBP' else 'degC' if stream == 'TEMP' else 'bpm'
    return decode_mqtt(f'mpm/v1/{GW}/{suffix}', json.dumps(dict(timestamp=int(stamp * 1000), seq=seq,
        session_id=session, validity='OFFLINE' if value == 'OFFLINE' else 'VALID', source='REPLAY' if replay else 'MOCK',
        synthetic=True, value=value, unit=unit)).encode())


def setup():
    now = [START]
    hub = Hub([GW], clock=lambda: now[0], monotonic=lambda: now[0])
    hub.broker_connected = True
    for node in ('GATEWAY', 'NODE-A', 'NODE-B', 'NODE-D', 'NODE-E'):
        hub.ingest(frame(node, 'STATUS', 'ONLINE'))
    hub.ingest(frame('NODE-D', 'TEMP', 30.2))
    hub.ingest(frame('NODE-E', 'NIBP', [120.0, 80.0]))
    hub.ingest(frame('NODE-B', 'HR', 60.0))
    return hub, now


def test_roles_and_node_local_offline():
    hub, now = setup()
    for node, stream, value in [('NODE-A', 'NIBP', [120.0, 80.0]), ('NODE-B', 'TEMP', 30.2), ('NODE-D', 'HR', 60.0)]:
        with pytest.raises(ValueError):
            frame(node, stream, value)
    now[0] += 1
    hub.ingest(frame('NODE-D', 'STATUS', 'OFFLINE', now[0], seq=2))
    snap = hub.snapshot(GW)
    assert snap['node_profile'] == 'five' and snap['nodes']['NODE-B'] == 'ONLINE'
    values = {x['stream']: x['value'] for x in snap['streams']}
    assert values['TEMP'] is None and values['HR'] == 60.0 and values['NIBP'] == [120.0, 80.0]
    assert {x['stream']: x['node_id'] for x in snap['streams']} == {'TEMP': 'NODE-D', 'NIBP': 'NODE-E', 'HR': 'NODE-B'}


@pytest.mark.parametrize('age, view_valid, speech_valid', [(89, True, True), (90, True, False), (90.001, False, False)])
def test_completion_age_is_not_extended_by_duplicate(age, view_valid, speech_valid):
    hub, now = setup()
    now[0] += age
    for node in ('GATEWAY', 'NODE-E'):
        hub.ingest(frame(node, 'STATUS', 'ONLINE', now[0], seq=2))
    hub.ingest(frame('NODE-E', 'NIBP', [120.0, 80.0], START, seq=2))
    snap = hub.snapshot(GW)
    pressure = next(x for x in snap['streams'] if x['stream'] == 'NIBP')
    assert (pressure['value'] is not None) == view_valid and pressure['timestamp'] == int(START * 1000)
    facts = extract(snap, GW, int(now[0] * 1000))
    assert (next(x for x in facts if x['stream'] == 'NIBP')['value'] is not None) == speech_valid


def test_reboot_replay_and_identical_new_completion():
    hub, now = setup()
    now[0] += 1
    hub.ingest(frame('NODE-E', 'STATUS', 'ONLINE', now[0], session='new-boot'))
    hub.ingest(frame('NODE-E', 'NIBP', [120.0, 80.0], START, seq=100))
    hub.ingest(frame('NODE-E', 'NIBP', [120.0, 80.0], START, seq=101, replay=True))
    pressure = lambda: next(x for x in hub.snapshot(GW)['streams'] if x['stream'] == 'NIBP')
    assert pressure()['value'] is None
    hub.ingest(frame('NODE-E', 'NIBP', [120.0, 80.0], now[0], session='new-boot'))
    assert pressure()['value'] == [120.0, 80.0] and pressure()['timestamp'] == int(now[0] * 1000)


def test_real_wss_snapshot_contains_independent_DE(monkeypatch):
    monkeypatch.setenv('MONITOR_TESTING', '1')
    monkeypatch.setenv('MONITOR_VIEW_TOKEN', 'synthetic-five-node-readonly-' + 'x' * 32)
    monkeypatch.setenv('MONITOR_ALLOWED_ORIGINS', 'http://testserver')
    monkeypatch.delenv('MONITOR_MQTT_CONFIG', raising=False)
    app = create_app()
    with TestClient(app) as client:
        app.state.hub, _ = setup()
        with client.websocket_connect('/ws/v1/monitor', headers={'origin': 'http://testserver'}) as ws:
            ws.send_json({'token': 'synthetic-five-node-readonly-' + 'x' * 32, 'gateway_id': GW})
            snap = ws.receive_json()
            assert snap['node_profile'] == 'five' and snap['nodes']['NODE-D'] == snap['nodes']['NODE-E'] == 'ONLINE'
