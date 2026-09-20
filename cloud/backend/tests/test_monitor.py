"""验证 MQTT 迁移中的状态边界和浏览器订阅生命周期。"""
import asyncio
import json
import sys
from pathlib import Path
import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.adapters import decode_mqtt
from app.hub import Hub
from app.main import create_app

BASE = 'mpm/v1/GW-DEV-001'

def message(suffix='NODE-B/telemetry/hr', **changes):
    body = {'timestamp': 1000000, 'seq': 1, 'session_id': 'session-a',
            'validity': 'VALID', 'source': 'MOCK', 'synthetic': True, 'value': 72.0, 'unit': 'bpm'}
    body.update(changes)
    return decode_mqtt(BASE+'/'+suffix, json.dumps(body).encode())

def ready():
    clock = [1000.0]
    hub = Hub(['GW-DEV-001'], clock=lambda: clock[0], monotonic=lambda: clock[0])
    hub.broker_connected = True
    for suffix in ['status', 'NODE-A/status', 'NODE-B/status']:
        hub.ingest(message(suffix, value='ONLINE', unit='state'))
    return hub, clock

def test_per_stream_expiry_does_not_follow_other_messages():
    hub, clock = ready()
    hub.ingest(message())
    clock[0] += 6
    hub.ingest(message('NODE-B/telemetry/temp', timestamp=1006000, value=36.6, unit='degC'))
    streams = {s['stream']:s for s in hub.snapshot('GW-DEV-001')['streams']}
    assert streams['HR']['validity'] == 'STALE' and streams['HR']['value'] is None
    assert streams['TEMP']['value'] == 36.6

def test_qos_duplicates_and_session_restart():
    hub, _ = ready()
    assert hub.ingest(message())
    assert not hub.ingest(message())
    assert not hub.ingest(message(seq=0))
    assert hub.ingest(message(session_id='session-b', seq=0, timestamp=1000001))
    assert not hub.ingest(message(session_id='session-c', timestamp=999000))

def test_will_old_timestamp_offlines_current_session():
    hub, _ = ready()
    hub.ingest(message())
    hub.ingest(message('status', seq=10, timestamp=1000010, unit='state', value='ONLINE'))
    assert hub.ingest(message('status', seq=2**53-1, timestamp=999000, unit='state', value='OFFLINE', validity='OFFLINE'))
    snapshot=hub.snapshot('GW-DEV-001')
    assert snapshot['gateway_state']=='OFFLINE'
    assert snapshot['streams'][0]['value'] is None
    assert hub.ingest(message('status', seq=11, timestamp=1000020, unit='state', value='ONLINE'))
    assert hub.snapshot('GW-DEV-001')['gateway_state']=='ONLINE'

def test_old_session_will_cannot_offline_new_session():
    hub, _ = ready()
    hub.ingest(message('status', session_id='new', timestamp=1000010, value='ONLINE', unit='state'))
    assert not hub.ingest(message('status', value='OFFLINE', unit='state', seq=2**53-1))
    assert hub.snapshot('GW-DEV-001')['gateway_state']=='ONLINE'

def test_replay_never_overwrites_live_or_refreshes_state():
    hub, clock = ready()
    hub.ingest(message())
    hub.ingest(message('NODE-B/replay/hr', source='REPLAY', value=50.0, timestamp=900000))
    assert hub.snapshot('GW-DEV-001')['streams'][0]['value']==72
    clock[0]+=16
    hub.ingest(message('NODE-B/replay/hr', source='REPLAY', value=51.0, timestamp=901000))
    snap=hub.snapshot('GW-DEV-001')
    assert snap['gateway_state']=='STALE' and snap['replay']['synthetic']

def test_broker_disconnect_and_node_offline_clear_values():
    hub, _ = ready()
    hub.ingest(message())
    hub.ingest(message('NODE-B/status', value='OFFLINE', validity='OFFLINE', unit='state', seq=2))
    assert hub.snapshot('GW-DEV-001')['streams'][0]['validity']=='OFFLINE'
    hub.broker_connected=False
    assert hub.snapshot('GW-DEV-001')['gateway_state']=='OFFLINE'

def test_live_and_replayed_emcy_use_same_browser_schema_without_current_alarm():
    hub, _ = ready()
    # 非合成 LIVE 沿用同一快照字段；历史 EMCY 只进入 replay，不覆盖当前事件。
    hub.ingest(message(source='LIVE', synthetic=False))
    hub.ingest(message('NODE-B/event', value='EMCY-0000', unit='code', source='LIVE', synthetic=False))
    hub.ingest(message('NODE-B/replay/fault', value='EMCY-1000', unit='code', source='REPLAY', synthetic=False, timestamp=900000))
    snap=hub.snapshot('GW-DEV-001')
    assert snap['streams'][0]['source']=='LIVE' and snap['streams'][0]['value']==72
    assert snap['event']['value']=='EMCY-0000'
    assert snap['replay']['value']=='EMCY-1000' and snap['replay']['source']=='REPLAY'

def test_invalid_and_old_retained_status():
    hub, clock = ready()
    hub.ingest(message(validity='INVALID'))
    assert hub.snapshot('GW-DEV-001')['streams'][0]['value'] is None
    clock[0] += 16
    # 保留的 ONLINE 即使刚收到，也必须检查原始采集时间。
    hub.current.clear()
    hub.ingest(message('status', value='ONLINE', unit='state'))
    assert hub.snapshot('GW-DEV-001')['gateway_state']=='STALE'

@pytest.mark.parametrize('changes', [dict(source='LIVE'),dict(source='REPLAY'),dict(unit='degC'),
                                   dict(gateway_id='other'),dict(timestamp=1.2),dict(value=float('nan'))])
def test_reject_bad_payload(changes):
    with pytest.raises(ValueError): message(**changes)

def test_wave_and_replay_topic_validation():
    wave=message('NODE-B/telemetry/ecg', value=None, unit='mV', samples=[0.0,1.0], sample_rate=250)
    assert wave.stream=='ECG'
    with pytest.raises(ValueError): message('NODE-B/telemetry/ecg', value=None, unit='mV', samples=[], sample_rate=250)
    with pytest.raises(ValueError): message('NODE-A/telemetry/hr')
    with pytest.raises(ValueError): message('NODE-B/telemetry/fault', value='x', unit='code')

def test_future_gateway_and_bounded_subscriber():
    hub, _ = ready()
    with pytest.raises(ValueError): hub.ingest(message(timestamp=1006000))
    queue=asyncio.Queue(maxsize=1)
    hub.subscribers[queue]='GW-DEV-001'
    hub.publish(); hub.publish()
    assert queue.qsize()==1

def test_browser_auth_and_no_device_ingest(monkeypatch):
    monkeypatch.setenv('MONITOR_TESTING','1')
    monkeypatch.delenv('MONITOR_MQTT_CONFIG',raising=False)
    monkeypatch.setenv('MONITOR_VIEW_TOKEN','unit-test-view-token-not-production-123')
    monkeypatch.setenv('MONITOR_ALLOWED_ORIGINS','http://testserver')
    app=create_app()
    with TestClient(app) as client:
        assert client.get('/health').json()['status']=='degraded'
        with pytest.raises(WebSocketDisconnect):
            with client.websocket_connect('/device/v1/ingest'): pass
        with client.websocket_connect('/ws/v1/monitor',headers={'origin':'http://testserver'}) as ws:
            ws.send_json({'token':'unit-test-view-token-not-production-123','gateway_id':'GW-C-001'})
            assert ws.receive_json()['gateway_id']=='GW-C-001'
        assert not app.state.hub.subscribers
        with pytest.raises(WebSocketDisconnect):
            with client.websocket_connect('/ws/v1/monitor',headers={'origin':'http://testserver'}) as ws:
                ws.send_json({'token':'wrong'})
                ws.receive_json()
