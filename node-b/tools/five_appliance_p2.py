"""P2 本机联合测试。MQTT/WS 均走回环，输入、账户与识别文本均为合成测试资料。"""
import argparse
import asyncio
from collections import Counter, defaultdict
from contextlib import ExitStack, contextmanager
import ctypes as C
import hashlib
from importlib.metadata import version
import json
import os
from pathlib import Path
import secrets
import socket
import subprocess
import sys
import tempfile
import threading
import time
from unittest.mock import patch
import zlib

import paho.mqtt.client as mqtt
import uvicorn
from websockets.asyncio.client import connect
from b5_local_broker import free_port

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
os.environ['MPM_NODE_PROFILE'] = 'five'
from cloud.ai.app import create_app, Settings
from cloud.ai.appliance_reply import GATEWAY, RecordingReplyAdapter
from cloud.ai.appliance_worker import fact_flow
from cloud.ai.downlink import IsolatedPublisher
from cloud.ai.snapshot import SnapshotReader
from cloud.backend.app.main import create_app as backend_app

UP = 'mpm/mic/v1/in'
DOWN = 'mpm/mic/v1/out'
ROLES = ('five-c', 'five-backend', 'five-audio-worker')
ORIGIN = 'http://127.0.0.1:18966'
STREAMS = ('ppg', 'spo2', 'pr', 'nibp', 'ecg', 'hr', 'resp', 'rr', 'temp', 'node_status', 'fault', 'gateway_status')
WAVES = {0, 4, 6}


def utc_ms():
    return time.time_ns() // 1000000


def linux(path):
    path = path.resolve()
    return '/mnt/' + path.drive[0].lower() + path.as_posix()[2:]


@contextmanager
def broker(runtime, distro, out):
    """复用已有 Mosquitto，专属 launcher 在 stdin 关闭时回收子进程。"""
    port = free_port()
    passwords = {role: secrets.token_urlsafe(32) for role in ROLES}
    prefix = ['wsl', '-d', distro, '--', 'env', 'LD_LIBRARY_PATH=' +
              ':'.join(linux(runtime / p) for p in ('usr/lib/x86_64-linux-gnu', 'lib/x86_64-linux-gnu'))]
    with tempfile.TemporaryDirectory(dir=out, prefix='p2-private-') as folder:
        folder = Path(folder)
        password_file = folder / 'passwd'
        password_file.write_text(''.join(f'{role}:{value}\n' for role, value in passwords.items()), encoding='ascii')
        subprocess.run(prefix + [linux(runtime/'usr/bin/mosquitto_passwd'), '-U', linux(password_file)],
                       check=True, capture_output=True, timeout=15)
        acl = ROOT/'cloud/broker/five-appliance-acl.example'
        conf = folder/'mosquitto.conf'
        conf.write_text(f'user root\nlistener {port} 127.0.0.1\nallow_anonymous false\npersistence false\n'
                        f'password_file {linux(password_file)}\nacl_file {linux(acl)}\nlog_dest stdout\n', encoding='ascii')
        launcher = ('import subprocess,sys; p=subprocess.Popen(sys.argv[1:]); '
                    'sys.stdin.read(); p.terminate(); p.wait(timeout=5)')
        with (out/'broker.log').open('wb') as log:
            process = subprocess.Popen(prefix+['python3','-u','-c',launcher,
                                       linux(runtime/'usr/sbin/mosquitto'),'-c',linux(conf)],
                                       stdin=subprocess.PIPE, stdout=log, stderr=subprocess.STDOUT)
            try:
                for _ in range(100):
                    assert process.poll() is None, 'BROKER_EXITED'
                    try:
                        with socket.create_connection(('127.0.0.1',port), timeout=.1):
                            break
                    except OSError:
                        time.sleep(.1)
                else:
                    raise TimeoutError('BROKER_NOT_READY')
                yield port, passwords, folder
            finally:
                process.communicate(b'', timeout=12)


@contextmanager
def mqtt_client(port, user, password, topic=None, receive=None, *, protocol=mqtt.MQTTv311):
    connected, subscribed = threading.Event(), threading.Event()
    connack = []
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, protocol=protocol)
    client.username_pw_set(user, password)
    client.max_inflight_messages_set(1)
    client.connect_timeout = 2

    def on_connect(c, userdata, flags, reason, properties):
        connack.append(not reason.is_failure)
        connected.set()
        if topic and not reason.is_failure:
            c.subscribe(topic, 1)

    def on_subscribe(c, userdata, mid, codes, properties):
        if len(codes) == 1 and not codes[0].is_failure:
            subscribed.set()

    client.on_connect, client.on_subscribe = on_connect, on_subscribe
    if receive:
        client.on_message = lambda c, u, m: receive(m.topic, bytes(m.payload), m.qos, m.retain)
    client.connect('127.0.0.1', port, keepalive=15)
    client.loop_start()
    try:
        assert connected.wait(3) and connack[0], 'MQTT_AUTH_OR_CONNECTION'
        if topic:
            assert subscribed.wait(3), 'MQTT_SUBSCRIPTION'
        yield client
    finally:
        client.disconnect()
        client.loop_stop()


def acl_probe(port, passwords):
    denied = {}
    for role, topic in [(ROLES[0], DOWN), (ROLES[1], UP), (ROLES[2], f'mpm/v1/{GATEWAY}/status')]:
        with mqtt_client(port, role, passwords[role], protocol=mqtt.MQTTv5) as client:
            reasons = []
            client.on_publish = lambda c, u, mid, reason, props: reasons.append(reason.value)
            info = client.publish(topic, b'P2 ACL probe', qos=1)
            info.wait_for_publish(2)
            assert reasons == [135], (role, reasons)
            denied[role] = reasons[0]
    return denied


class Frame(C.Structure):
    _fields_ = [('timestamp', C.c_uint64), ('seq', C.c_uint32), ('epoch', C.c_uint32), ('boot', C.c_uint32),
                ('values', C.c_int32*100), ('count', C.c_uint16), ('rate', C.c_uint16),
                ('node', C.c_uint8), ('stream', C.c_uint8), ('valid', C.c_bool),
                ('synthetic', C.c_bool), ('replay', C.c_bool)]


class Reply(C.Structure):
    _fields_ = [('timestamp', C.c_uint64), ('expires', C.c_uint64), ('seq', C.c_uint32),
                ('epoch', C.c_uint32), ('boot', C.c_uint32), ('node', C.c_uint8), ('stream', C.c_uint8),
                ('status', C.c_uint8), ('synthetic', C.c_uint8), ('text', C.c_void_p), ('length', C.c_uint)]


def mqtt_size(topic, body, qos):
    length = 2 + len(topic) + 2*qos + len(body)
    return length + (2 if length < 128 else 3)


def native_libraries(args):
    dll = args.out/'telemetry.dll'
    build = subprocess.run([args.cc,'-shared','-O2','-DMP_FRAME_MAX_SAMPLES=100','-DMP_FIVE_NODE',
                   '-DMP_B5_CLOUD_CANDIDATE','-DMP_MQTT_GATEWAY_ID="GW-B5-001"',
                   str(ROOT/'gateway/data_model/model.c'),'-o',str(dll)], capture_output=True, timeout=30)
    (args.out/'telemetry-build.log').write_bytes(build.stdout+build.stderr)
    build.check_returncode()
    model = C.CDLL(str(dll.resolve()))
    for name in ('mp_topic','mp_json'):
        getattr(model,name).argtypes = [C.POINTER(Frame), C.c_void_p, C.c_size_t]
    mic = C.CDLL(str((args.native/'mic-protocol.dll').resolve()))
    mic.mic_chunk_packet_length.argtypes = [C.c_void_p,C.c_uint32,C.c_uint,C.c_uint32,C.c_void_p,C.c_uint]
    mic.mic_fact_reply_valid.argtypes = [C.c_void_p,C.c_size_t,C.c_uint32,C.c_uint32,C.c_uint64,C.POINTER(Reply)]
    return model, mic


async def exercise(args, port, passwords, folder, model, mic):
    loop = asyncio.get_running_loop()
    view_token, ai_token = secrets.token_urlsafe(32), secrets.token_urlsafe(32)
    ws_port = free_port()
    uri = f'ws://127.0.0.1:{ws_port}/ws/v1/monitor'
    config = folder/'backend.json'
    config.write_text(json.dumps(dict(host='127.0.0.1', port=port, tls=False, username=ROLES[1],
                                      password=passwords[ROLES[1]], client_id='p2-backend')), encoding='utf-8')
    env = dict(MONITOR_MQTT_CONFIG=str(config), MONITOR_GATEWAY_IDS=GATEWAY, MONITOR_VIEW_TOKEN=view_token,
               MONITOR_WAVE_BATCH_DELIVERY='1', MONITOR_ALLOWED_ORIGINS=ORIGIN, MONITOR_WEB_DIR='',
               MONITOR_LOG_DIR=str(args.out/'backend'), P6_MONITOR_WS_URL=uri, P6_MONITOR_VIEW_TOKEN=view_token,
               P6_MONITOR_ORIGIN=ORIGIN, P6_WEB_DIR='', P6_MQTT_MODE='DISABLED')
    sent, sizes, seq = Counter(), defaultdict(list), Counter()
    waves = defaultdict(set)
    telemetry = []
    link_lock = asyncio.Lock()
    incoming, output = asyncio.Queue(maxsize=256), asyncio.Queue(maxsize=4)
    overflow = []
    turn = {}
    stop_producer = asyncio.Event()

    def enqueue(queue, value):
        def add():
            try:
                queue.put_nowait(value)
            except asyncio.QueueFull:
                overflow.append(1)
        loop.call_soon_threadsafe(add)

    publisher = IsolatedPublisher(port, ROLES[2], passwords[ROLES[2]])

    async def send_reply(topic, packet):
        await asyncio.to_thread(publisher._send, topic, packet)

    replies = RecordingReplyAdapter(send_reply)

    async def mock_asr(pcm, rate):
        assert rate == 16000 and pcm == turn['pcm'], 'PCM_CHANGED'
        turn['assembled'] = time.monotonic()
        return turn['question']

    async def consume(flow):
        while True:
            topic, body, qos, retain, received = await incoming.get()
            if not turn.get('first_received'):
                turn['first_received'] = received
            turn['blocks_received'] += 1
            result = await flow.feed(topic, body, qos, retain)
            if result:
                turn['result'] = result

    async def observe():
        async with connect(uri, origin=ORIGIN, proxy=None) as ws:
            await ws.send(json.dumps(dict(token=view_token,gateway_id=GATEWAY)))
            async for body in ws:
                for fact in json.loads(body)['streams']:
                    if fact['stream'] in ('ECG','RESP','PPG') and fact['validity']=='VALID':
                        waves[fact['stream']].add(fact['seq'])

    async def send(client, topic, body, qos):
        async with link_lock:
            info = client.publish(topic, body, qos=qos)
            await asyncio.to_thread(info.wait_for_publish,2)
            assert info.is_published(), 'C_PUBLISH_TIMEOUT'

    async def measure(client, node, stream, values, rate=0):
        label = STREAMS[stream]
        seq[node, stream] += 1
        stamp = utc_ms()
        frame = Frame(stamp, seq[node,stream], 1712345678, 1, (C.c_int32*100)(*values),
                      len(values), rate, node, stream, True, True, False)
        topic, body = C.create_string_buffer(100), C.create_string_buffer(2048)
        assert model.mp_topic(C.byref(frame),topic,len(topic)) and model.mp_json(C.byref(frame),body,len(body))
        qos = 0 if rate else 1
        size = mqtt_size(topic.value,body.value,qos)
        telemetry.append((time.monotonic(), size))
        await send(client, topic.value.decode('ascii'), body.value, qos)
        sent[label] += 1
        sizes[label].append(size)
        return stamp

    async def produce(client):
        start = loop.time()
        wave = [(-1 if i%2 else 1)*(1103+i) for i in range(100)]
        resp = [(-1 if i%2 else 1)*(10000+i) for i in range(50)]
        ppg = [1230000+i for i in range(50)]
        tick = 0
        while not stop_producer.is_set():
            await asyncio.sleep(max(0,start+tick*.2-loop.time()))
            if stop_producer.is_set():
                break
            if tick%25==0:
                await measure(client,3,11,[1])
                for node in (1,2,4,5):
                    await measure(client,node,9,[1])
            if tick%2==0:
                await measure(client,2,4,wave,250)
            if tick%5==0:
                for node, stream, value, rate in ((2,6,resp,50),(1,0,ppg,50),(1,1,[9750],0),
                        (1,2,[7200],0),(2,5,[6000],0),(2,7,[1800],0),(4,8,[2450],0)):
                    await measure(client,node,stream,value,rate)
            tick += 1

    async def audio(client, count, question, expected_status, *, paced):
        pcm = bytes((i*13+7)%256 for i in range(32320 if count==64 else 64000))
        started = time.monotonic()
        session, crc = utc_ms()//1000, zlib.crc32(pcm)
        turn.clear()
        turn.update(pcm=pcm,question=question,blocks_received=0)
        for index in range(count):
            if paced:
                await asyncio.sleep(max(0,started+index*.25-time.monotonic()))
            wire = C.create_string_buffer(544)
            mic.mic_chunk_packet_length(wire,session,index,crc,pcm[index*512:],len(pcm))
            await send(client, UP, wire.raw, 1)
        raw, arrived = await asyncio.wait_for(output.get(),12)
        async with asyncio.timeout(2):
            while 'result' not in turn:
                await asyncio.sleep(.005)
        reply = Reply()
        assert mic.mic_fact_reply_valid(raw,len(raw),session,crc,utc_ms(),C.byref(reply)), 'C_REJECTED'
        assert reply.status==expected_status and turn['blocks_received']==count
        result = turn['result']
        return dict(blocks=count, upload_pacing_ms=250 if paced else 0, pcm_bytes=len(pcm),
                    mqtt_publish_bytes=count*mqtt_size(UP.encode(),bytes(544),1), c_status=reply.status,
                    answer_kind=result['answer_kind'], source_age_ms=utc_ms()-reply.timestamp if reply.timestamp else None,
                    assemble_s=turn['assembled']-turn['first_received'], final_to_mr02_s=arrived-turn['assembled'],
                    first_send_to_c_s=time.monotonic()-started, valid_remaining_ms=reply.expires-utc_ms(),
                    source_seq=reply.seq, mock_source=bool(reply.synthetic), fact_streams=[f['stream'] for f in result['facts']])

    tasks = []
    with patch.dict(os.environ,env), ExitStack() as stack:
        backend = backend_app()
        server = uvicorn.Server(uvicorn.Config(backend, host='127.0.0.1', port=ws_port, log_level='warning', access_log=False))
        server_task = asyncio.create_task(server.serve())
        try:
            async with asyncio.timeout(8):
                while not server.started or not backend.state.hub.broker_connected:
                    await asyncio.sleep(.025)
            client = stack.enter_context(mqtt_client(port,ROLES[0],passwords[ROLES[0]],DOWN,
                                  lambda topic,body,qos,retain:enqueue(output,(body,time.monotonic()))))
            stack.enter_context(mqtt_client(port,ROLES[2],passwords[ROLES[2]],UP,
                                  lambda topic,body,qos,retain:enqueue(incoming,(topic,body,qos,retain,time.monotonic()))))
            app = create_app(Settings(ai_token,mode='MOCK',snapshot_mode='MONITOR'),publisher=replies)
            app.state.worker_token = ai_token
            reader = SnapshotReader('MONITOR')
            tasks = [asyncio.create_task(consume(fact_flow(replies,mock_asr,app))),asyncio.create_task(observe()),
                     asyncio.create_task(produce(client))]
            began = time.monotonic()
            await asyncio.sleep(1.1)
            first = await reader.read(GATEWAY)
            assert first['node_profile']=='five' and set(first['nodes'])=={'NODE-A','NODE-B','NODE-D','NODE-E'}
            assert not any(f['stream']=='NIBP' for f in first['streams'])
            bp_stamp = await measure(client,5,3,[1180,760])
            turns = [await audio(client,64,'当前高压多少',0,paced=True),
                     await audio(client,125,'当前物体温度',0,paced=True)]
            for question,status in [('血压偏高怎么办',5),('心率和血压',6)]:
                await asyncio.sleep(1.05)
                turns.append(await audio(client,64,question,status,paced=False))
            await asyncio.sleep(max(0,(bp_stamp+90100-utc_ms())/1000))
            last = await reader.read(GATEWAY)
            bp = next(f for f in last['streams'] if f['stream']=='NIBP')
            assert bp['validity']=='STALE' and bp['value'] is None
            turns.append(await audio(client,64,'当前高压多少',2,paced=False))
            elapsed = time.monotonic()-began
            stop_producer.set()
            await asyncio.wait_for(tasks[-1],3)
            await asyncio.sleep(.25)
            assert not overflow
            assert all(row['source']=='MOCK' and row['synthetic'] for row in last['streams'])
            expected = {'ECG','RESP','PPG','HR','RR','SPO2','PR','TEMP','NIBP'}
            assert {row['stream'] for row in last['streams']}==expected
            assert backend.state.hub.accepted==sum(sent.values()) and not backend.state.hub.rejected
            assert not backend.state.adapter.dropped
            assert all(len(waves[name])==sent[name.lower()] for name in ('ECG','RESP','PPG')), 'WS_WAVE_GAP'
            for task in tasks[:2]:
                assert not task.done(), task.exception()
            assert all(t['assemble_s']<90 and t['first_send_to_c_s']+t['pcm_bytes']/32000<300 for t in turns)
            # 仅重放 P1 实测平均服务率，不把回环开销等同于 ESP-AT。保留真实线包长度。
            available_at = telemetry[0][0]
            late = 0
            for queued_at, size in telemetry:
                available_at = max(available_at,queued_at)+max(1/8.08,size/11520)
                late += available_at-queued_at>=5
            assert late>0
            return dict(duration_s=elapsed, counts=dict(sent), backend_accepted=backend.state.hub.accepted,
                        backend_rejected=backend.state.hub.rejected, backend_dropped=backend.state.adapter.dropped,
                        ws_unique_wave_batches={k:len(v) for k,v in waves.items()}, bp_expiry_age_ms=utc_ms()-bp_stamp,
                        bp_readable_before_completion=False, audio_turns=turns, telemetry_frames_per_s=sum(sent.values())/elapsed,
                        telemetry_mqtt_bytes=sum(sum(v) for v in sizes.values()),
                        mqtt_size_by_stream={k:dict(min=min(v),max=max(v),mean=sum(v)/len(v)) for k,v in sizes.items()},
                        p1_rate_projection=dict(service_frames_s=8.08,telemetry_only_over_5s=late,
                                                tail_service_debt_s=available_at-telemetry[-1][0],audio_residual='NONE'))
        finally:
            for task in tasks:
                task.cancel()
            await asyncio.gather(*tasks,return_exceptions=True)
            server.should_exit=True
            await asyncio.wait_for(server_task,8)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--runtime',type=Path,required=True)
    parser.add_argument('--native',type=Path,required=True)
    parser.add_argument('--out',type=Path,required=True)
    parser.add_argument('--cc',default='C:/mingw64/bin/gcc.exe')
    parser.add_argument('--distro',default='HERA-C3')
    args = parser.parse_args()
    args.out.mkdir(parents=True,exist_ok=False)
    model, mic = native_libraries(args)
    with broker(args.runtime,args.distro,args.out) as (port,passwords,folder):
        denied = acl_probe(port,passwords)
        result = asyncio.run(exercise(args,port,passwords,folder,model,mic))
    result.update(scope='LOOPBACK_MOSQUITTO_MOCK_ASR_C_PARSER', acl_denied_puback=denied,
                  dependencies={name:version(name) for name in ('fastapi','pydantic','uvicorn','websockets','paho-mqtt','httpx')},
                  script_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                  functional='PASS', loopback_deadlines='PASS', device_throughput='NOT_PASS_P1_CAPACITY_EVIDENCE',
                  real_asr_tts='NOT_RUN')
    (args.out/'joint-results.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(result,indent=2))


if __name__=='__main__':
    main()
