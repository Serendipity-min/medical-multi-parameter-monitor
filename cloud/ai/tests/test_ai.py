"""普通功能回归：真实服务/事实校验，模型与读数仅用明确合成夹具。"""
import asyncio
import copy
import json
import time
import uuid
import pytest
from fastapi.testclient import TestClient
from cloud.ai.app import Settings, create_app
from cloud.ai.snapshot import SnapshotReader
from cloud.ai.facts import extract, answer_facts
from cloud.ai.downlink import encode, decode, short_text, SimulatedGateway, HEADER
from cloud.ai.providers import Provider, EXPLANATIONS

TOKEN = 'synthetic-ai-token-for-offline-tests-only'


def snapshot():
    return asyncio.run(SnapshotReader('MOCK').read('GW-C-001'))


def body(**kwargs):
    return dict(session_id=uuid.uuid4().hex, gateway_id='GW-C-001', question='现在心率多少', voice=False, **kwargs)


def client(reader=None, provider=None, publisher=None):
    return TestClient(create_app(Settings(TOKEN, snapshot_mode='MOCK'), reader, provider, publisher))


def post(c, data=None):
    return c.post('/api/v1/text', json=data or body(), headers={'Authorization': 'Bearer ' + TOKEN})


def test_numeric_mock_has_exact_value_and_provenance():
    result = post(client()).json()
    assert '72 bpm' in result['answer'] and '非真人' in result['answer']
    assert result['real_model'] == 'REAL_MODEL_BLOCKED' and result['voice_status'] == 'PAUSED'
    assert len(result['fact_digest']) == 32 and result['facts'][0]['session_id']


@pytest.mark.parametrize('validity', ['INVALID', 'STALE', 'OFFLINE'])
def test_invalid_never_exposes_old_value(validity):
    snap = snapshot(); snap['streams'][0]['validity'] = validity
    facts = extract(snap, 'GW-C-001', int(time.time() * 1000))
    assert facts[0]['value'] is None and '72' not in answer_facts(facts, '心率')


@pytest.mark.parametrize('change', ['node', 'unit', 'gateway', 'duplicate', 'nan', 'range', 'source', 'synthetic', 'seq'])
def test_bad_fact_rejected(change):
    snap = snapshot(); item = snap['streams'][0]
    if change == 'node': item['node_id'] = 'NODE-A'
    if change == 'unit': item['unit'] = '%'
    if change == 'gateway': item['gateway_id'] = 'GW-DEV-001'
    if change == 'duplicate': snap['streams'].append(copy.deepcopy(item))
    if change == 'nan': item['value'] = float('nan')
    if change == 'range': item['value'] = 999
    if change == 'source': item['source'] = 'LIVE'
    if change == 'synthetic': item['synthetic'] = False
    if change == 'seq': item['seq'] = -1
    with pytest.raises(ValueError): extract(snap, 'GW-C-001', int(time.time() * 1000))


def test_old_timestamp_and_replay_are_not_current():
    snap = snapshot(); snap['streams'][0]['timestamp'] -= 6000
    assert extract(snap, 'GW-C-001', int(time.time() * 1000))[0]['value'] is None
    snap = snapshot(); snap['streams'][0]['source'] = 'REPLAY'
    fact = extract(snap, 'GW-C-001', int(time.time() * 1000))[0]
    assert fact['value'] is None and '历史补传' in answer_facts([fact], '心率')


def test_gateway_offline_masks_all_values():
    snap = snapshot(); snap['gateway_state'] = 'OFFLINE'
    assert all(f['value'] is None for f in extract(snap, 'GW-C-001', int(time.time() * 1000)))


def test_auth_extra_fields_and_oversize_do_not_echo_secrets():
    c = client()
    assert c.post('/api/v1/text', json=body()).status_code == 401
    data = body(); data['snapshot'] = snapshot()
    assert post(c, data).status_code == 422
    result = c.post('/api/v1/text', content='x' * 5000, headers={'Authorization': 'Bearer ' + TOKEN})
    assert result.status_code == 413 and TOKEN not in result.text


def test_global_rate_limit_cannot_be_bypassed_by_new_session():
    c = client()
    assert all(post(c).status_code == 200 for _ in range(12))
    assert post(c).status_code == 429


def test_provider_failure_preserves_monitor_and_fixed_error():
    class Broken:
        async def explain(self, *_): raise RuntimeError('synthetic-secret-must-not-echo')
    c = client(provider=Broken()); data = body(); data['question'] = '解释项目'
    result = post(c, data)
    assert result.status_code == 503 and 'secret' not in result.text
    assert c.get('/health').status_code == 200


def test_session_gateway_switch_has_no_old_context():
    seen = []
    class Recorder:
        async def explain(self, _question, _facts, history):
            seen.append(len(history)); return EXPLANATIONS['quality']
    c = client(provider=Recorder()); data = body(); data['question'] = '解释数据'
    assert post(c, data).status_code == 200
    assert post(c, data).status_code == 200
    data['gateway_id'] = 'GW-DEV-001'
    assert post(c, data).status_code == 200 and seen == [0, 1, 0]


def test_downlink_failure_does_not_fail_visible_answer():
    class Broken:
        async def publish(self, *_): raise RuntimeError('synthetic-secret')
    data = body(); data['voice'] = True
    result = post(client(publisher=Broken()), data)
    assert result.status_code == 200 and result.json()['voice_status'] == 'DOWNLINK_FAILED'


def test_real_model_requires_server_account_and_budget(monkeypatch):
    monkeypatch.delenv('P6_REAL_BUDGET_APPROVED', raising=False)
    with pytest.raises(ValueError, match='REAL_MODEL_BLOCKED'): Provider('DOUBAO')


def test_doubao_http_contract_and_independent_output_validation(monkeypatch):
    import httpx
    original = httpx.AsyncClient
    monkeypatch.setenv('ARK_API_KEY', 'synthetic-not-a-real-key')
    monkeypatch.setenv('ARK_MODEL_ID', 'synthetic-model')
    monkeypatch.setenv('P6_REAL_ACCOUNT_APPROVED', '1')
    monkeypatch.setenv('P6_REAL_BUDGET_APPROVED', '1')
    outputs = iter(['{"kind":"quality"}', '{"kind":"take-drug","dose":50}'])
    def handle(request):
        assert request.url.path == '/api/v3/chat/completions'
        assert request.headers['Authorization'] == 'Bearer synthetic-not-a-real-key'
        assert json.loads(request.content)['model'] == 'synthetic-model'
        return httpx.Response(200, json={'choices': [{'message': {'content': next(outputs)}}]})
    monkeypatch.setattr(httpx, 'AsyncClient', lambda **kwargs: original(transport=httpx.MockTransport(handle), **kwargs))
    provider = Provider('DOUBAO')
    assert asyncio.run(provider.explain('解释', [], [])) == EXPLANATIONS['quality']
    with pytest.raises(ValueError): asyncio.run(provider.explain('解释', [], []))
    provider.calls = 5
    with pytest.raises(ValueError, match='CALL_LIMIT'): asyncio.run(provider.explain('解释', [], []))


def test_utf8_boundary_and_wire_roundtrip():
    text = short_text('模拟心率正常。' * 100)
    assert len(text.encode()) <= 240 and '\ufffd' not in text
    now = int(time.time() * 1000)
    payload = encode('1' * 32, '2' * 32, text, now)
    assert len(payload) <= 294 and HEADER.size == 54
    assert decode(payload, now)['fact_digest'] == '2' * 32


@pytest.mark.parametrize('bad', ['[v9]恶意标签', '控制\x00字符', '\ud800', '\u202e伪造方向', '\u0085控制', '😀'])
def test_voice_control_and_invalid_unicode_rejected(bad):
    with pytest.raises(ValueError): encode('1' * 32, '2' * 32, bad, 100000)


@pytest.mark.parametrize('bad', ['retain', 'qos', 'topic', 'expiry', 'duplicate', 'order', 'size', 'unicode'])
def test_simulator_rejects_bad_downlink(bad):
    sim = SimulatedGateway('GW-C-001'); topic = sim.topic; now = 100000
    payload = encode('1' * 32, '2' * 32, '模拟心率72 bpm。', now)
    qos, retain = 1, False
    if bad == 'retain': retain = True
    if bad == 'qos': qos = 0
    if bad == 'topic': topic = 'mpm/v1/GW-DEV-001/voice/reply'
    if bad == 'expiry': now += 15000
    if bad == 'size': payload += b'x' * 250
    if bad == 'unicode': payload = payload[:-1] + b'\xff'
    if bad in ('duplicate', 'order'):
        sim.receive(topic, payload, qos, retain, now)
        if bad == 'order': payload = encode('3' * 32, '2' * 32, '模拟', now - 1)
    with pytest.raises(ValueError): sim.receive(topic, payload, qos, retain, now)
