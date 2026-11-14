"""合成PCM、真实协议/事实/FastAPI/C解析器；不连接Broker、板或大模型。"""
import asyncio
import copy
import ctypes as C
import os
from pathlib import Path
import struct
import time
import zlib

os.environ['MPM_NODE_PROFILE'] = 'five'
import pytest
from fastapi.testclient import TestClient
from cloud.ai.app import create_app, Settings
from cloud.ai.appliance_reply import Recording, RecordingReplyAdapter, adapt_reply, HEADER
from cloud.ai.downlink import encode
from cloud.ai.facts import extract, digest, answer_facts
from cloud.ai.snapshot import SnapshotReader
from cloud.ai.appliance_worker import fact_flow, whisper_pcm
from cloud.microphone.protocol import AudioAssembler

NOW = 1800000020000
GW = 'GW-B5-001'


def snapshot(now=NOW):
    data = asyncio.run(SnapshotReader('MOCK').read(GW))
    data['server_time'] = now
    for f in data['streams']:
        f['timestamp'] = now-100
    return data


def facts(now=NOW):
    return extract(snapshot(now), GW, now)


def packet(fs=None, question='当前高压多少', now=NOW, context=None):
    fs = fs or facts(now)
    return adapt_reply(encode('a'*32, digest(fs), answer_facts(fs, question).split('\n')[0], now),
                       fs, question, context or Recording(now//1000-1, 1234, now+300000), now)


@pytest.mark.parametrize('question,wanted,unwanted', [('当前高压多少','118','76'), ('当前低压多少','76','118'),
    ('当前物体温度多少','36.5','118'), ('当前呼吸率多少','没有可用当前读数','118')])
def test_fact_selection(question, wanted, unwanted):
    answer = answer_facts(facts(), question)
    assert wanted in answer and unwanted not in answer
    assert '请明确指定' in answer_facts(facts(), '你好')


@pytest.mark.parametrize('stream,ttl', [('NIBP',90000), ('TEMP',5000)])
def test_expiry_exact_boundary(stream, ttl):
    data = snapshot()
    item = next(f for f in data['streams'] if f['stream'] == stream)
    item['timestamp'] = NOW-ttl+1
    assert next(f for f in extract(data,GW,NOW) if f['stream']==stream)['value'] is not None
    item['timestamp'] -= 1
    f = next(f for f in extract(data,GW,NOW) if f['stream']==stream)
    assert f['value'] is None and f['validity']=='STALE'


@pytest.mark.parametrize('change', ['node','gateway','unit','duplicate','source'])
def test_wrong_measurement_identity(change):
    data = snapshot(); item = data['streams'][-1]
    if change=='node': item['node_id']='NODE-A'
    if change=='gateway': item['gateway_id']='GW-C-001'
    if change=='unit': item['unit']='degC'
    if change=='duplicate': data['streams'].append(copy.deepcopy(item))
    if change=='source': item['source']='LIVE'
    with pytest.raises(ValueError): extract(data,GW,NOW)


def test_replay_and_invalid_never_speak_values():
    fs = facts()
    for state in ('REPLAY','INVALID','OFFLINE','STALE'):
        data = snapshot(); item = next(f for f in data['streams'] if f['stream']=='NIBP')
        if state=='REPLAY': item['source']='REPLAY'
        else: item['validity']=state
        fs=extract(data,GW,NOW); p=packet(fs)
        assert p[50] and p[82:].decode()=='当前读数不可用'


@pytest.mark.parametrize('change', ['digest','text','role','session','seq','ambiguous'])
def test_adapter_rejects_untrusted(change):
    fs=facts(); question='当前高压多少'
    if change=='role': next(f for f in fs if f['stream']=='NIBP')['node_id']='NODE-A'
    if change=='session': fs[-1]['session_id']='browser-generated'
    if change=='seq': fs[-1]['seq']=0
    if change=='ambiguous': question='当前高压和温度多少'
    text = answer_facts(fs,question).split('\n')[0]
    payload=encode('a'*32, '0'*32 if change=='digest' else digest(fs), '高压999' if change=='text' else text,NOW)
    with pytest.raises(ValueError): adapt_reply(payload,fs,question,Recording(1,2,NOW+10000),NOW)


class Reply(C.Structure):
    _fields_=[('timestamp',C.c_uint64),('expires',C.c_uint64),('seq',C.c_uint32),('epoch',C.c_uint32),
        ('boot',C.c_uint32),('node',C.c_uint8),('stream',C.c_uint8),('status',C.c_uint8),('synthetic',C.c_uint8),
        ('text',C.c_void_p),('length',C.c_uint)]


@pytest.fixture(scope='module')
def native():
    path=os.environ.get('FIVE_APPLIANCE_NATIVE_OUT')
    assert path, 'First run gateway/microphone/run_five_appliance_tests.py and set FIVE_APPLIANCE_NATIVE_OUT'
    lib=C.CDLL(str(Path(path).resolve()/'mic-protocol.dll'))
    lib.mic_fact_reply_valid.argtypes=[C.c_void_p,C.c_size_t,C.c_uint32,C.c_uint32,C.c_uint64,C.POINTER(Reply)]
    lib.mic_fact_reply_valid.restype=C.c_int
    return lib


def c_accept(native, p, now=NOW, session=NOW//1000-1, crc=1234):
    result=Reply(); buf=C.create_string_buffer(bytes(p))
    return native.mic_fact_reply_valid(buf,len(p),session,crc,now,C.byref(result)),result


def test_python_mr02_consumed_by_real_c(native):
    p=packet(); ok,f=c_accept(native,p)
    assert ok and (f.node,f.stream,f.seq,f.epoch,f.boot)==(5,3,1,123,1)
    assert f.timestamp==NOW-100 and f.synthetic==1


@pytest.mark.parametrize('field', ['magic','session','crc','gateway','role','stream','flags','digest','issued','expired','old_fact','seq','length','no_utc'])
def test_actual_c_parser_negative(native,field):
    p=bytearray(packet())
    if field=='magic': p[:4]=b'MR01'
    if field=='session': p[4]^=1
    if field=='crc': p[8]^=1
    if field=='gateway': p[55]^=1
    if field=='role': p[48]=1
    if field=='stream': p[49]=6
    if field=='flags': p[51]=2
    if field=='digest': p[64:80]=bytes(16)
    if field=='issued': struct.pack_into('<Q',p,12,NOW+1001)
    if field=='expired': struct.pack_into('<Q',p,20,NOW)
    if field=='old_fact': struct.pack_into('<Q',p,28,NOW-90000)
    if field=='seq': struct.pack_into('<I',p,36,0)
    if field=='length': p[80]+=1
    assert c_accept(native,p,0 if field=='no_utc' else NOW)[0]==0


def test_c_mc01_roundtrip_and_no_audio_padding(native):
    path=Path(os.environ['FIVE_APPLIANCE_NATIVE_OUT'])/'synthetic-mc01.bin'
    wire=path.read_bytes(); assembler=AudioAssembler(allow_short=True); audio=None
    for offset in range(0,len(wire),544): audio=assembler.feed('C',wire[offset:offset+544],offset/544*.25)
    expected=struct.pack('<'+'h'*16160,*[((i*13+7+32768)%65536)-32768 for i in range(16160)])
    assert audio['pcm']==expected and audio['crc32']==zlib.crc32(expected) and audio['chunks']==64
    context=Recording(audio['session'],audio['crc32'],NOW+300000)
    p=packet(context=context)
    assert c_accept(native,p,session=context.session,crc=context.crc)[0]
    with pytest.raises(ValueError,match='REPLAY'): assembler.feed('C',wire[:544],30)
    with pytest.raises(ValueError): AudioAssembler().feed('C',wire[:544],0)
    broken=bytearray(wire[:544]);broken[40]^=1
    with pytest.raises(ValueError): AudioAssembler(allow_short=True).feed('C',broken,0)


class Reader:
    async def read(self,gateway): return await SnapshotReader('MOCK').read(gateway)


def client(publisher=None):
    return TestClient(create_app(Settings('x'*32), reader=Reader(), publisher=publisher))


def request(client, **fields):
    body=dict(session_id='b'*32,gateway_id=GW,question='当前高压多少',voice=True);body.update(fields)
    return client.post('/medical-monitor/ai/api/v1/text',headers={'Authorization':'Bearer '+'x'*32},json=body)


def test_real_api_default_voice_disabled_and_auth(monkeypatch):
    monkeypatch.delenv('P6_MQTT_MODE',raising=False)
    with client() as c:
        data=request(c).json()
        assert data['voice_status']=='DISABLED' and '118' in data['answer'] and '物体温度' not in data['answer']
        assert request(c,gateway_id='GW-C-001').status_code==403
        assert request(c,measurement=999).status_code==422
        assert c.post('/medical-monitor/ai/api/v1/text',json={}).status_code==401


def test_formal_gateway_requires_explicit_configuration(monkeypatch):
    monkeypatch.setenv('P6_AI_TOKEN', 'x' * 32)
    monkeypatch.delenv('P6_GATEWAY_IDS', raising=False)
    monkeypatch.delenv('P6_MQTT_MODE', raising=False)
    assert Settings.from_env().gateways == ('GW-B5-001',)
    monkeypatch.setenv('P6_GATEWAY_IDS', 'GW-C-001')
    settings = Settings.from_env()
    assert settings.gateways == ('GW-C-001',)
    reads = []

    class FormalReader:
        async def read(self, gateway):
            reads.append(gateway)
            data = await SnapshotReader('MOCK').read(gateway)
            for item in data['streams']:
                item.update(source='LIVE', synthetic=False)
            return data

    with TestClient(create_app(settings, reader=FormalReader())) as c:
        for question, stream, node in [('当前温度多少', 'TEMP', 'NODE-D'), ('当前高压多少', 'NIBP', 'NODE-E')]:
            response = request(c, gateway_id='GW-C-001', question=question, voice=False)
            assert response.status_code == 200
            data = response.json()
            assert data['gateway_id'] == 'GW-C-001' and data['voice_status'] == 'PAUSED'
            assert len(data['facts']) == 1
            fact = data['facts'][0]
            assert (fact['stream'], fact['node_id'], fact['source']) == (stream, node, 'LIVE')
            assert fact['value'] is not None
        assert request(c).status_code == 403
        assert request(c, gateway_id='unlisted').status_code == 422
    assert reads == ['GW-C-001', 'GW-C-001']


def test_audio_asr_api_mr02_flow(native):
    sent=[]; now=int(time.time()*1000)
    async def send(topic,p): sent.append((topic,p))
    replies=RecordingReplyAdapter(send)
    with client(replies) as c:
        assert request(c).json()['voice_status']=='NO_RECORDING_CONTEXT'
        async def asr(pcm,rate):
            assert len(pcm)==32320 and rate==16000
            return '当前低压多少'
        c.app.state.worker_token='x'*32
        flow=fact_flow(replies,asr,c.app)
        wire=bytearray((Path(os.environ['FIVE_APPLIANCE_NATIVE_OUT'])/'synthetic-mc01.bin').read_bytes())
        for start in range(0,len(wire),544): struct.pack_into('<I',wire,start+4,now//1000)
        async def run():
            result=None
            for start in range(0,len(wire),544): result=await flow.feed('mpm/mic/v1/in',wire[start:start+544])
            return result
        result=asyncio.run(run())
        assert result['voice_status']=='BROKER_PUBACK_ONLY_NOT_TTS_DONE'
        assert len(sent)==1 and sent[0][0]=='mpm/mic/v1/out'
        payload=sent[0][1]; crc=struct.unpack_from('<I',wire,20)[0]
        assert c_accept(native,payload,int(time.time()*1000),now//1000,crc)[0]
        assert '76' in payload[82:].decode() and '118' not in payload[82:].decode()
        assert replies.recording is None and request(c).json()['voice_status']=='NO_RECORDING_CONTEXT'


@pytest.mark.parametrize('topic,qos,retain',[('wrong',1,False),('mpm/mic/v1/in',0,False),('mpm/mic/v1/in',1,True)])
def test_audio_authority(topic,qos,retain):
    with pytest.raises(ValueError,match='AUTHORITY'):
        RecordingReplyAdapter(None).feed_audio(topic,bytes(544),qos,retain,NOW)


def test_api_snapshot_delay_does_not_refresh_source_age(monkeypatch):
    clock=[NOW]; reads=[]
    monkeypatch.setattr(time,'time',lambda:clock[0]/1000)
    class FixedSource:
        async def read(self,gateway):
            reads.append(1); clock[0]+=5000; return copy.deepcopy(source)
    source=snapshot()
    app=create_app(Settings('x'*32),reader=FixedSource())
    with TestClient(app) as c:
        data=request(c,question='物体温度',voice=False).json()
    assert len(reads)==1 and 'STALE' in data['answer'] and '36.5' not in data['answer']


@pytest.mark.parametrize('stream,ttl,question',[('TEMP',5000,'物体温度'),('NIBP',90000,'当前高压多少')])
def test_delayed_reply_at_fact_expiry(native, stream, ttl, question):
    fs=facts(); item=next(f for f in fs if f['stream']==stream)
    item['timestamp']=NOW-ttl+50
    issued=encode('a'*32,digest(fs),answer_facts(fs,question),NOW)
    ctx=Recording(NOW//1000-1,1234,NOW+300000)
    fresh=adapt_reply(issued,fs,question,ctx,NOW+49)
    assert c_accept(native,fresh,NOW+49)[0]
    assert not c_accept(native,fresh,NOW+50)[0]
    refused=adapt_reply(issued,fs,question,ctx,NOW+50)
    assert c_accept(native,refused,NOW+50)[1].status==2
    assert refused[82:].decode()=='当前读数不可用'


@pytest.mark.parametrize('question,kind,status',[
    ('血压偏高怎么办','GENERAL_ADVICE',5),('心率和血压','MULTI_VALUE',6),('你好','CLARIFY',6),
])
def test_question_rules_and_control_parser(native, question, kind, status):
    sent=[]
    async def send(topic,payload):sent.append(payload)
    replies=RecordingReplyAdapter(send)
    replies.recording=Recording(NOW//1000-1,1234,int(time.time()*1000)+20000)
    with client(replies) as c:
        result=request(c,question=question).json()
    assert result['answer_kind']==kind and result['model_evidence'] is None
    if kind=='MULTI_VALUE':
        assert {f['stream'] for f in result['facts']}=={'HR','NIBP'}
        assert '72' in result['answer'] and '118' in result['answer']
    else:
        assert not result['facts'] and not any(c.isdigit() for c in result['answer'])
    frame=bytearray(sent[0]); now=int(time.time()*1000)
    ok, reply=c_accept(native,frame,now)
    assert ok and reply.status==status and frame[82:]==b'!'
    frame[36]=1
    assert not c_accept(native,frame,now)[0]


def test_backend_isolated_gateway_profile_and_wss(monkeypatch):
    from cloud.backend.app.main import create_app as backend
    monkeypatch.setenv('MONITOR_VIEW_TOKEN','v'*32)
    monkeypatch.setenv('MONITOR_GATEWAY_IDS',GW)
    monkeypatch.setenv('MONITOR_TESTING','1')
    monkeypatch.delenv('MONITOR_MQTT_CONFIG',raising=False)
    with TestClient(backend()) as c:
        assert set(c.app.state.hub.gateways)=={GW}
        with c.websocket_connect('/ws/v1/monitor',headers={'origin':'http://127.0.0.1:5173'}) as ws:
            ws.send_json({'token':'v'*32,'gateway_id':GW})
            data=ws.receive_json()
            # 与后端conftest一致：等服务端清理订阅并发送关闭帧，再退出TestClient的取消作用域。
            ws.close()
            while ws.receive()['type']=='websocket.send':
                pass
            assert data['gateway_id']==GW and data['node_profile']=='five'
            assert {'NODE-A','NODE-B','NODE-D','NODE-E'}<=data['nodes'].keys()


@pytest.mark.parametrize('exit_code',[0,3])
def test_worker_asr_boundary_and_ephemeral_pcm(monkeypatch,tmp_path,exit_code):
    import json
    import wave
    pcm=bytes(32000)
    class Process:
        returncode=None
        async def wait(self):self.returncode=exit_code;return exit_code
    async def spawn(*args,**kwargs):
        wav=Path(args[args.index('-f')+1]);prefix=Path(args[args.index('-of')+1])
        with wave.open(str(wav),'rb') as inp:assert inp.getframerate()==16000 and inp.readframes(16000)==pcm
        prefix.with_suffix('.json').write_text(json.dumps({'transcription':[{'text':'当前温度多少'}]}),encoding='utf-8')
        assert args[args.index('-t')+1]=='1'
        return Process()
    monkeypatch.setattr(asyncio,'create_subprocess_exec',spawn)
    if exit_code:
        with pytest.raises(RuntimeError,match='ASR_EXIT_3'):
            asyncio.run(whisper_pcm(pcm,16000,Path('fake-asr'),Path('fake-model'),tmp_path))
    else:assert asyncio.run(whisper_pcm(pcm,16000,Path('fake-asr'),Path('fake-model'),tmp_path))=='当前温度多少'
    assert not list(tmp_path.iterdir())


def test_worker_default_cannot_open_network(monkeypatch):
    from cloud.ai.appliance_worker import run
    monkeypatch.delenv('P6_MQTT_MODE',raising=False)
    with pytest.raises(ValueError,match='ISOLATED_WORKER_NOT_ENABLED'):asyncio.run(run(None))
