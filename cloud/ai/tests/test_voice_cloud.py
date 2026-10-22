"""VOICE-002功能负例：替身仅在网络边界，不发真实模型或Broker请求。"""
import asyncio
import time
from concurrent.futures import ThreadPoolExecutor
import pytest
from cloud.ai.downlink import FormalVoicePublisher, encode, short_text
from cloud.ai.voice_budget import VoiceBudget
from cloud.ai.providers import ValidatedExplanation
from cloud.ai.tests.test_ai import client, post, body


@pytest.mark.parametrize('text', ['\ufdd0','\ufffe','\uffff','\U0001fffe','\U0010ffff','\u2066','[v5]','\0'])
def test_same_unicode_rejections_as_device(text):
    with pytest.raises(ValueError):short_text(text)


def test_astral_rejected_consistently_with_existing_p6_policy():
    with pytest.raises(ValueError):short_text('😀')


def test_window_budget_not_reset_by_new_instance_and_unknown_cost_retained(tmp_path):
    budget=VoiceBudget(str(tmp_path/'usage.sqlite'),int(time.time()*1000)+60000)
    a=budget.reserve(100);b=budget.reserve(100)
    with pytest.raises(ValueError):budget.reserve(100)
    budget.finish(a,{'status':'VALIDATED','usage':{'total_tokens':500}})
    budget.finish(b,{'status':'TIMEOUT'})
    other=VoiceBudget(str(tmp_path/'usage.sqlite'),int(time.time()*1000)+60000)
    other.reserve(100)
    with pytest.raises(ValueError):other.reserve(100)
    with pytest.raises(ValueError):other.reserve(1701)


def test_window_budget_concurrent_reservations(tmp_path):
    budget=VoiceBudget(str(tmp_path/'usage.sqlite'),int(time.time()*1000)+60000)
    def reserve(_):
        try:budget.reserve(100);return True
        except ValueError:return False
    with ThreadPoolExecutor(max_workers=6) as pool:assert sum(pool.map(reserve,range(6)))==2


def test_formal_publisher_scope_window_size_and_no_automatic_retry(tmp_path):
    ca=tmp_path/'ca.pem';ca.write_text('synthetic-ca-not-used-for-network')
    pub=FormalVoicePublisher('mqtt.example.invalid',str(ca),'synthetic-user','synthetic-pass',int(time.time()*1000)+60000)
    calls=[]
    def send(topic,payload):calls.append(topic);raise RuntimeError('synthetic-fail')
    pub._send=send
    now=int(time.time()*1000)
    assert asyncio.run(pub.publish('GW-DEV-001',encode('1'*32,'2'*32,'休息。',now)))=='DISABLED'
    assert asyncio.run(pub.publish('GW-C-001',encode('1'*32,'2'*32,'中'*21,now)))=='VOICE_SHORT_LIMIT'
    with pytest.raises(RuntimeError):asyncio.run(pub.publish('GW-C-001',encode('1'*32,'2'*32,'休息。',now)))
    assert calls==['mpm/v1/GW-C-001/voice/reply']
    pub.until_ms=now-1
    assert asyncio.run(pub.publish('GW-C-001',encode('1'*32,'2'*32,'休息。',now)))=='DISABLED'


def test_formal_uses_actual_model_short_sentence_not_deterministic_prefix():
    class Model:
        async def explain(self,*_):return ValidatedExplanation('请适当休息。',{'status':'VALIDATED'})
    class Pub:
        short_only=True
        async def publish(self,gateway,payload):self.payload=payload;return 'BROKER_PUBACK_ONLY'
    pub=Pub();data=body();data.update(question='请给出一般健康提示',voice=True)
    r=post(client(provider=Model(),publisher=pub),data).json()
    assert r['voice_text']=='请适当休息。' and r['voice_status']=='BROKER_PUBACK_ONLY'
    assert r['voice_text'].encode() in pub.payload and '非真人' in r['answer']


def test_formal_overlong_sentence_has_no_broker_side_effect():
    class Model:
        async def explain(self,*_):return '请结合实际情况注意数据来源并复测并向专业人员了解说明。'
    class Pub:
        short_only=True
        async def publish(self,*_):raise AssertionError('must not publish')
    data=body();data.update(question='一般建议',voice=True)
    r=post(client(provider=Model(),publisher=Pub()),data).json()
    assert r['voice_status']=='VOICE_SHORT_LIMIT'
