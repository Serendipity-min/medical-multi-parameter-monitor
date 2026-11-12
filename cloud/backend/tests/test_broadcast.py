"""用合成采集序列验证播报门禁、时钟和快照契约。"""

import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.broadcast import DISCLAIMER, GATEWAY, blood_pressure
from app.hub import Hub
from app.main import create_app
from app.models import CHANNELS, NODE_PROFILE, UNITS, Telemetry

EPOCH = 1_700_000_000
FORBIDDEN = ('缺氧', '诊断', '疾病', '高血压', '低血压', '治疗', '用药', '异常')


class Feed:
    def __init__(self, *, enabled=True, hr=False, gateway=GATEWAY):
        self.t, self.seq = 0, 0
        self.last_beat = None
        self.gateway = gateway
        self.session = 'capture-1'
        self.hub = Hub([gateway], lambda: EPOCH + self.t, lambda: self.t, broadcast=enabled, broadcast_hr=hr)
        self.hub.broker_connected = True

    def frame(self, node, stream, value, *, timestamp=None, source='LIVE', validity='VALID', synthetic=False):
        self.seq += 1
        return Telemetry(
            gateway_id=self.gateway, node_id=node, stream=stream, value=value, unit=UNITS[stream],
            timestamp=int((EPOCH + self.t) * 1000) if timestamp is None else timestamp,
            seq=self.seq, session_id=self.session, source=source, validity=validity, synthetic=synthetic,
        )

    def beat(self, value='ONLINE'):
        # 正式固件的状态帧是 MOCK；状态只用于连通性，播报的读数仍必须是 LIVE。
        self.hub.ingest(self.frame('GATEWAY', 'GATEWAY_STATUS', value, source='MOCK', synthetic=True))
        for node in CHANNELS:
            self.hub.ingest(self.frame(node, 'NODE_STATUS', value, source='MOCK', synthetic=True))
        self.last_beat = self.t if value == 'ONLINE' else None

    def send(self, stream, value, *, impossible_synthetic_live=False, **fields):
        if self.last_beat is None or self.t - self.last_beat >= 10:
            self.beat()
        node = next(node for node, streams in CHANNELS.items() if stream in streams)
        frame = self.frame(node, stream, value, **fields)
        if impossible_synthetic_live:
            frame = frame.model_copy(update={'synthetic': True})
        return self.hub.ingest(frame)

    def snapshot(self):
        return self.hub.snapshot(self.gateway)


@pytest.mark.parametrize('sys,dia,label,level', [
    (89, 70, '偏低', 'notice'), (110, 59, '偏低', 'notice'), (89, 91, '偏低', 'notice'),
    (90, 60, '在一般参考范围内', 'info'), (119, 79, '在一般参考范围内', 'info'),
    (120, 70, '正常高值', 'info'), (110, 80, '正常高值', 'info'), (139, 89, '正常高值', 'info'),
    (140, 89, '偏高', 'notice'), (139, 90, '偏高', 'notice'), (150, 95, '偏高', 'notice'),
])
def test_blood_pressure_thresholds(sys, dia, label, level):
    assert blood_pressure(sys, dia) == (label, level)


@pytest.mark.parametrize('age_ms,emits', [(89_999, True), (90_000, False), (90_001, False)])
def test_nibp_freshness_and_once_per_result(age_ms, emits):
    feed = Feed()
    for t in range(0, 101, 10):
        feed.t = t
        feed.beat()
    timestamp = (EPOCH + 100) * 1000 - age_ms
    assert feed.send('NIBP', [145, 92], timestamp=timestamp)
    assert feed.send('NIBP', [145, 92], timestamp=timestamp)  # 同一测量被换了 seq。
    snap = feed.snapshot()
    assert len(snap['broadcast_history']) == int(emits)
    if emits:
        first = snap['broadcast']
        assert first['text'] == '本次血压约 145/92 mmHg，偏高。建议静坐 5 分钟后复测。'
        feed.t += 1
        assert feed.send('NIBP', [118, 76])
        assert len(feed.snapshot()['broadcast_history']) == 2
        assert feed.snapshot()['broadcast']['id'] != first['id']


@pytest.mark.parametrize('param,value,hr,emits', [
    ('SPO2', 89.99, False, True), ('SPO2', 90.0, False, False), ('SPO2', 90.01, False, False),
    ('PR', 59.99, False, True), ('PR', 60.0, False, False), ('PR', 100.0, False, False),
    ('PR', 100.01, False, True),
    ('HR', 59.99, True, True), ('HR', 60.0, True, False), ('HR', 100.0, True, False),
    ('HR', 100.01, True, True), ('HR', 55.0, False, False),
])
def test_rolling_rules_require_full_window_and_120_seconds(param, value, hr, emits):
    feed = Feed(hr=hr)
    for t in range(181):
        feed.t = t
        feed.send(param, value)
        if t < 180:
            assert feed.snapshot()['broadcast'] is None
    snap = feed.snapshot()
    assert bool(snap['broadcast']) is emits
    if emits:
        assert (snap['broadcast']['param'], snap['broadcast']['ts'], snap['broadcast']['level']) == (
            param, (EPOCH+180)*1000, 'notice')
        assert snap['broadcast']['ts'] == snap['server_time']
        assert not any(word in snap['broadcast']['text'] for word in FORBIDDEN)


@pytest.mark.parametrize('param,normal,outlier', [('SPO2', 95.0, 85.0), ('PR', 75.0, 140.0)])
def test_rolling_median_ignores_isolated_outliers(param, normal, outlier):
    feed = Feed()
    for t in range(241):
        feed.t = t
        feed.send(param, outlier if t % 25 == 0 else normal)
    assert feed.snapshot()['broadcast_history'] == []


@pytest.mark.parametrize('param,abnormal,normal', [('SPO2', 89.0, 90.0), ('PR', 105.0, 100.0)])
def test_recovering_median_restarts_sustained_interval(param, abnormal, normal):
    feed = Feed()
    for t in range(329):
        feed.t = t
        feed.send(param, normal if 120 <= t < 180 else abnormal)
        assert feed.snapshot()['broadcast'] is None
    feed.t = 329
    feed.send(param, abnormal)
    # 60 秒窗各半时中位数仍越界，t=209 开始第二次计时。
    assert feed.snapshot()['broadcast']['ts'] == (EPOCH+329)*1000


def test_temperature_ready_and_repeat_intervals_are_per_parameter():
    feed = Feed()
    for t in range(361):
        feed.t = t
        feed.send('TEMP', 30.24)
        feed.send('PR', 105.0)
        if t == 59:
            assert feed.snapshot()['broadcast'] is None
        if t == 60:
            assert feed.snapshot()['broadcast']['text'] == '当前体表温度约 30.2 °C（体表温度低于体温，不作判断）。'
        if t == 359:
            assert [e['param'] for e in feed.snapshot()['broadcast_history']] == ['PR', 'TEMP']
    assert [e['param'] for e in feed.snapshot()['broadcast_history']] == ['TEMP', 'PR', 'TEMP']


@pytest.mark.parametrize('param,value', [('SPO2', 85.0), ('PR', 105.0)])
def test_sustained_notices_repeat_no_sooner_than_five_minutes(param, value):
    feed = Feed()
    for t in range(481):
        feed.t = t
        feed.send(param, value)
        if t == 479:
            assert len(feed.snapshot()['broadcast_history']) == 1
    history = feed.snapshot()['broadcast_history']
    assert len(history) == 2 and history[0]['ts'] - history[1]['ts'] == 300_000


@pytest.mark.parametrize('fields', [
    {'source': 'MOCK', 'synthetic': True}, {'source': 'REPLAY'}, {'impossible_synthetic_live': True},
    {'validity': 'INVALID'}, {'validity': 'STALE'}, {'validity': 'OFFLINE'},
])
def test_filtered_data_cannot_drive_nibp_or_rolling_broadcasts(fields):
    feed = Feed()
    feed.send('NIBP', [151, 91], **fields)
    for t in range(181):
        feed.t = t
        feed.send('SPO2', 85.0, **fields)
        feed.send('TEMP', 30.0, **fields)
    assert feed.snapshot()['broadcast_history'] == []


def test_expired_scalar_clears_all_continuous_windows_and_invalid_temp_breaks_continuity():
    feed = Feed()
    for t in range(115):
        feed.t = t
        if t < 50:
            feed.send('SPO2', 89.0)
        feed.send('TEMP', 30.0)
        if t < 114:
            assert feed.snapshot()['broadcast'] is None
    assert feed.snapshot()['broadcast']['ts'] == (EPOCH+114)*1000

    feed = Feed()
    for t in range(121):
        feed.t = t
        feed.send('TEMP', 30.0, validity='INVALID' if t == 59 else 'VALID')
        if t < 120:
            assert feed.snapshot()['broadcast'] is None
    assert feed.snapshot()['broadcast']['param'] == 'TEMP'


@pytest.mark.parametrize('stop', ['will', 'stale', 'broker', 'new-session'])
def test_gateway_loss_clears_latest_history_and_windows_without_replaying(stop):
    feed = Feed()
    for t in range(60):
        feed.t = t
        feed.send('TEMP', 30.0)
    feed.send('NIBP', [145, 90])
    previous = feed.snapshot()['broadcast']
    if stop == 'will':
        feed.beat('OFFLINE')
    elif stop == 'stale':
        feed.t += 16
    elif stop == 'broker':
        feed.hub.broker_connected = False
    else:
        feed.t += 1
        feed.session = 'capture-2'
        feed.beat()
    assert feed.snapshot()['broadcast'] is None
    assert feed.snapshot()['broadcast_history'] == []
    feed.t += 1
    feed.hub.broker_connected = True
    feed.beat()
    assert feed.send('NIBP', [145, 90], timestamp=previous['ts'] + 1)
    assert feed.send('TEMP', 30.0)
    assert feed.snapshot()['broadcast_history'] == []


def test_history_bound_latest_expiry_ids_and_disclaimer():
    feed = Feed()
    for t in range(12):
        feed.t = t
        feed.send('NIBP', [145, 92])
    snap = feed.snapshot()
    history = snap['broadcast_history']
    assert len(history) == len({item['id'] for item in history}) == 10
    assert snap['broadcast'] == history[0]
    assert all(item['disclaimer'] == DISCLAIMER and DISCLAIMER not in item['text'] for item in history)
    assert all(word not in item['text'] for item in history for word in FORBIDDEN)
    for t in range(21, 612, 10):
        feed.t = t
        feed.beat()
    assert feed.snapshot()['broadcast'] == history[0]
    feed.t = 611.001
    assert feed.snapshot()['broadcast'] is None
    assert feed.snapshot()['broadcast_history'] == history
    other = Feed()
    other.send('NIBP', [110, 70])
    assert other.snapshot()['broadcast']['id'] not in {item['id'] for item in history}


def test_formal_gateway_scope_rr_and_disabled_snapshot():
    other = Feed(gateway='GW-DEV-001')
    other.send('NIBP', [150, 92])
    assert other.snapshot()['broadcast'] is None and other.snapshot()['broadcast_history'] == []
    enabled, disabled = Feed(), Feed(enabled=False, hr=True)
    for feed in (enabled, disabled):
        feed.send('RR', 40.0)
    expected = enabled.snapshot()
    assert expected.pop('broadcast') is None and expected.pop('broadcast_history') == []
    assert disabled.snapshot() == expected
    assert set(expected) == {'type', 'schema_version', 'node_profile', 'gateway_id', 'gateways', 'gateway_state',
                             'broker_connected', 'nodes', 'server_time', 'streams', 'replay', 'event'}
    assert expected['node_profile'] == NODE_PROFILE


@pytest.mark.parametrize('broadcast,hr', [(None, None), ('0', '1'), ('1', None), ('1', '1')])
def test_feature_flags_and_optional_wss_fields(monkeypatch, monitor_snapshot, broadcast, hr):
    monkeypatch.setenv('MONITOR_TESTING', '1')
    monkeypatch.delenv('MONITOR_MQTT_CONFIG', raising=False)
    monkeypatch.setenv('MONITOR_VIEW_TOKEN', 'synthetic-broadcast-view-token-00000')
    monkeypatch.setenv('MONITOR_PUBLIC_VIEW', '1')
    monkeypatch.setenv('MONITOR_ALLOWED_ORIGINS', 'http://testserver')
    for name, value in (('MONITOR_BROADCAST', broadcast), ('MONITOR_BROADCAST_HR', hr)):
        if value is None:
            monkeypatch.delenv(name, raising=False)
        else:
            monkeypatch.setenv(name, value)
    app = create_app()
    with TestClient(app) as client:
        snap = monitor_snapshot(client, {'gateway_id': GATEWAY})
        if broadcast != '1':
            assert 'broadcast' not in snap and 'broadcast_history' not in snap
            assert app.state.hub.broadcast is None
        else:
            assert snap['broadcast'] is None and snap['broadcast_history'] == []
            assert ('HR' in app.state.hub.broadcast.params) == (hr == '1')
