"""真实C推进器/coreMQTT→隔离TLS Broker→Backend→WSS的加速软件回放。"""
import asyncio
from contextlib import asynccontextmanager
import ctypes as C
import hashlib
import json
import os
from pathlib import Path
import queue
import re
import select
import socket
import ssl
import subprocess
import sys
import threading
import time
import uuid
from unittest.mock import patch
import paho.mqtt.client as mqtt
import uvicorn
from fastapi import FastAPI
from websockets.asyncio.client import connect
from b5_local_broker import Broker,free_port
import b5_g3_contract as g

ROOT=g.ROOT
sys.path.insert(0,str(ROOT/'cloud/backend'))
from app.main import create_app
from app.hub import Hub
from app.adapters import decode_mqtt

STREAM={'ecg':4,'hr':5,'resp':6,'rr':7,'temp':8,'status':9}
SCALE={4:1000,5:100,6:1000000,7:100,8:100}

def main():
    pointer=json.loads((ROOT/'node-b/build/b5-egress-final-r1-pointer.json').read_text());private=Path(pointer['root'])/('local-TLS-'+uuid.uuid4().hex[:8]);private.mkdir()
    out=ROOT/'node-b/build'/('egress-TLS-'+uuid.uuid4().hex[:8]);out.mkdir()
    audit=g.load(Path(pointer['root'])/'evidence-audit/receipt-private.json')
    temp=json.loads((ROOT/pointer['temperature_pointer']).read_text());folder=Path(temp['windows']['ECG60']['output'])
    events=[json.loads(s) for s in (folder/'cloud-events-private.jsonl').read_text('utf8').splitlines()]
    arm=g.load(folder/'ARM_ATTEMPT.json')['monotonic'];rows={}
    for x in events:
        if x['kind']!='BROKER_RAW' or x['monotonic']<arm or x['data']['retain']:continue
        m=decode_mqtt(x['data']['topic'],bytes.fromhex(x['data']['payload_hex'])).model_dump()
        if m['validity']=='OFFLINE':continue
        key=g.telemetry_key(m);rows[key]=m
    source=sorted(rows.values(),key=lambda m:(m['timestamp'],m['node_id'],m['stream']))
    # 反事实软件回放：从源UTC重新入队，历史Broker分类不当作原始C入队观测。
    # 波形值已在evidence-audit中逐批对照B原码；原件和REPLAY结论完全保留。
    base=source[0]['timestamp']//1000*1000
    original_statuses=sum(m['stream'] in ('NODE_STATUS','GATEWAY_STATUS') for m in source)
    source=[m for m in source if m['stream'] not in ('NODE_STATUS','GATEWAY_STATUS')]
    mqttroot=ROOT/'gateway/mqtt';vendor=ROOT/'gateway/third_party/coreMQTT/source'
    flags=['C:/mingw64/bin/gcc.exe','-shared','-std=c11','-O2','-Wall','-Wextra','-Werror','-Wno-unused-parameter',
           '-DGATEWAY_MQTT_HOST_TEST','-DMP_B5_CLOUD_CANDIDATE','-DMP_B5_EGRESS_FINAL','-DMP_FRAME_MAX_SAMPLES=100',
           '-DMP_LIVE_CAPACITY=24','-DMP_CACHE_CAPACITY=56','-DMP_MQTT_GATEWAY_ID="GW-B5-001"',
           '-I'+str(mqttroot/'src'),'-I'+str(ROOT/'gateway/b5'),'-I'+str(vendor/'include'),'-I'+str(vendor/'interface')]
    cfiles=[ROOT/'gateway/b5/host_tls_bridge.c',ROOT/'gateway/b5/b5_policy.c',ROOT/'gateway/data_model/model.c',ROOT/'gateway/storage/router.c',
            mqttroot/'src/gateway_transport.c',mqttroot/'src/mqtt_transport_adapter.c',*[vendor/n for n in ('core_mqtt.c','core_mqtt_serializer.c','core_mqtt_state.c')]]
    dll=out/'gateway.dll';r=subprocess.run([*flags,*map(str,cfiles),'-o',str(dll)],capture_output=True,timeout=90)
    (out/'build.log').write_bytes(r.stdout+r.stderr)
    inputs=[*cfiles,*list((ROOT/'gateway/b5').glob('*.h')),*list((mqttroot/'src').glob('*.h')),
            ROOT/'gateway/storage/router.h',ROOT/'gateway/data_model/model.h',Path(__file__)]
    source_binding={str(f.relative_to(ROOT)):g.sha(f.read_bytes()) for f in inputs}
    g.save(private/'source-bindings-private.json',source_binding)
    g.write_private(private/'executed-runner.py',Path(__file__).read_bytes())
    if r.returncode:print('TLS_BRIDGE_BUILD_FAILED',r.stderr.decode(errors='replace')[-2400:]);return r.returncode
    broker=Broker(ROOT/'node-b/build/b5-runtime/root',out/'broker');server=None;thread=None;observer=None;tls=None
    recorded=[];snapshots=[];observer_errors=[];connected=threading.Event();subscribed=threading.Event()
    clock=[0];epoch_anchor=time.monotonic();origin=free_port();url='https://127.0.0.1:'+str(origin);token='synthetic-egress-'+uuid.uuid4().hex
    config=out/'backend.json';config.write_text(json.dumps(dict(host='127.0.0.1',port=broker.port,username='b5-reader',password=broker.password,
        client_id='b5-backend-'+uuid.uuid4().hex[:8],ca_file=str(broker.cert))))
    env=dict(MONITOR_MQTT_CONFIG=str(config),MONITOR_VIEW_TOKEN=token,MONITOR_GATEWAY_IDS='GW-B5-001',
             MONITOR_ALLOWED_ORIGINS=url,MONITOR_LOG_DIR=str(out/'backend-logs'),MONITOR_WEB_DIR=str(ROOT/'cloud/web/dist'))
    result={'status':'FAIL','hardware_operations':0,'formal_cloud_operations':0,'physical_ESP_AT_TLS':'NOT_RUN',
            'source_UTC_rewritten':False,'mode':'ACCELERATED_COUNTERFACTUAL_SOURCE_REPLAY_NOT_HARDWARE_ACCEPTANCE',
            'historical_failed_Broker_records':audit['Broker_messages'],'unobserved_original_C_enqueue_timing':'UNKNOWN'}
    result['source_sha256']=source_binding
    result['status_fixture']='NEW_CONTROLLED_5S_PRODUCTION_NOT_BACKFILLED_HISTORICAL_MESSAGES'
    result['original_status_messages_preserved_in_historical_audit']=original_statuses
    def now_ms():return clock[0]+int((time.monotonic()-epoch_anchor)*1000)
    try:
        with patch.dict(os.environ,env):
            backend=create_app()
            @asynccontextmanager
            async def life(app):
                async with backend.router.lifespan_context(backend):
                    backend.state.hub.clock=lambda:(base+now_ms())/1000
                    backend.state.hub.monotonic=lambda:now_ms()/1000
                    yield
            outer=FastAPI(lifespan=life);outer.mount('/medical-monitor',backend)
            server=uvicorn.Server(uvicorn.Config(outer,host='127.0.0.1',port=origin,ssl_keyfile=str(broker.key),ssl_certfile=str(broker.cert),log_level='warning'))
            thread=threading.Thread(target=server.run,daemon=True);thread.start()
            deadline=time.monotonic()+15
            while not server.started or not hasattr(backend.state,'adapter') or not backend.state.adapter.connected:
                if time.monotonic()>deadline:raise TimeoutError('LOCAL_BACKEND_READY')
                time.sleep(.05)
            observer=mqtt.Client(mqtt.CallbackAPIVersion.VERSION2,client_id='b5-observe-'+uuid.uuid4().hex[:8]);observer.username_pw_set('b5-audit',broker.password)
            observer.tls_set_context(ssl.create_default_context(cafile=str(broker.cert)))
            def conn(c,u,flags,reason,props):
                if reason==0:c.subscribe('mpm/v1/GW-B5-001/#',qos=1);connected.set()
            observer.on_connect=conn;observer.on_subscribe=lambda *a:subscribed.set()
            observer.on_message=lambda c,u,m:recorded.append(dict(topic=m.topic,payload_hex=m.payload.hex(),qos=m.qos,retain=m.retain,fixture_ms=now_ms()))
            observer.connect('127.0.0.1',broker.port);observer.loop_start();assert connected.wait(5) and subscribed.wait(5)
            tls=ssl.create_default_context(cafile=str(broker.cert)).wrap_socket(socket.create_connection(('127.0.0.1',broker.port)),server_hostname='localhost')
            tls.setsockopt(socket.IPPROTO_TCP,socket.TCP_NODELAY,1)
            lib=C.CDLL(str(dll));Io=C.CFUNCTYPE(C.c_int,C.c_void_p,C.c_int,C.c_int);Clock=C.CFUNCTYPE(C.c_uint32)
            class Entry(C.Structure):
                _fields_=[('report_utc',C.c_uint64),('arrival_utc',C.c_uint64),('seq',C.c_uint32),('epoch',C.c_uint32),
                          ('boot',C.c_uint32),('centi',C.c_int32),('valid',C.c_uint32)]
            lib.bridge_temp_read.argtypes=[C.POINTER(Entry)];entry_records=[]
            lib.bridge_status.argtypes=[C.c_uint32,C.c_uint32,C.c_uint32,C.c_uint64]
            lib.bridge_open.argtypes=[Io,Io,Clock,C.c_uint32];lib.bridge_put.argtypes=[C.c_uint32,C.c_uint32,C.c_uint64,C.c_uint32,C.c_uint32,C.c_uint32,C.c_uint32,C.c_uint32,C.POINTER(C.c_int32)]
            cursor=[0];feeding=[False];ready=[False];injections=[0];close_seen=[False];status_at=[-5000];status_seq=[0]
            status_epoch,status_boot=map(int,next(m['session_id'] for m in source if m['node_id']=='NODE-B').split('-')[1:])
            def feed():
                if not ready[0] or feeding[0]:return now_ms()
                feeding[0]=True
                try:
                    tick=now_ms()
                    if tick-status_at[0]>=5000:
                        status_at[0]=tick;status_seq[0]+=1;lib.bridge_status(status_epoch,status_boot,status_seq[0],base+tick)
                    while cursor[0]<len(source) and source[cursor[0]]['timestamp']<=base+tick:
                        m=source[cursor[0]];cursor[0]+=1;stream=11 if m['stream']=='GATEWAY_STATUS' else 9 if m['stream']=='NODE_STATUS' else STREAM[m['stream'].lower()]
                        epoch,boot=map(int,m['session_id'].split('-')[1:]);values=m['samples'] if m['sample_rate'] else [m['value']]
                        if stream in (9,11):nums=[1]
                        else:nums=[g.fixed(v,SCALE[stream]) if v is not None else 0 for v in values]
                        a=(C.c_int32*len(nums))(*nums);lib.bridge_put(stream,m['seq'],m['timestamp'],epoch,boot,m['validity']=='VALID',m['sample_rate'] or 0,len(nums),a)
                    return tick
                finally:feeding[0]=False
            def write(ptr,n,timeout):
                try:
                    if ready[0] and injections[0]<3 and now_ms()>=100000+injections[0]*6000:
                        clock[0]+=1500 if injections[0]<2 else 2516;injections[0]+=1;feed()
                    tls.settimeout(timeout/1000);tls.sendall(C.string_at(ptr,n));return n
                except OSError:observer_errors.append('TLS_SEND_FAILED');return -1
            def read(ptr,n,timeout):
                try:
                    if not tls.pending() and not select.select([tls],[],[],timeout/1000)[0]:return 0
                    data=tls.recv(n)
                    if not data:return -1
                    C.memmove(ptr,data,len(data));return len(data)
                except OSError:observer_errors.append('TLS_READ_FAILED');return -1
            callbacks=(Io(write),Io(read),Clock(feed));assert lib.bridge_open(*callbacks,base//1000)==1
            ready[0]=True
            async def evaluate():
                context=ssl.create_default_context(cafile=str(broker.cert))
                async with connect(url.replace('https:','wss:')+'/medical-monitor/ws/v1/monitor',ssl=context,origin=url) as ws:
                    await ws.send(json.dumps(dict(token=token,gateway_id='GW-B5-001')))
                    async def receive():
                        async for raw in ws:snapshots.append(json.loads(raw))
                    receiver=asyncio.create_task(receive());deadline=time.monotonic()+300
                    try:
                        while cursor[0]<len(source) or lib.bridge_queued():
                            clock[0]+=25;assert lib.bridge_step()==1
                            e=Entry()
                            while lib.bridge_temp_read(C.byref(e)):
                                entry_records.append({name:getattr(e,name) for name,typ in e._fields_})
                            if time.monotonic()>deadline:raise TimeoutError('LOCAL_REPLAY_BUDGET')
                            await asyncio.sleep(.001)
                        await asyncio.sleep(1)
                    finally:
                        receiver.cancel()
                        try:await receiver
                        except asyncio.CancelledError:pass
            asyncio.run(evaluate());assert not lib.bridge_error() and not observer_errors
            messages={};max_bytes=0
            for row in recorded:
                m=decode_mqtt(row['topic'],bytes.fromhex(row['payload_hex'])).model_dump();messages[g.telemetry_key(m)]=m;max_bytes=max(max_bytes,len(bytes.fromhex(row['payload_hex'])))
            assert all(m['source']=='MOCK' and m['synthetic'] for m in messages.values())
            # CONNECT遗嘱不会在正常关闭前交付；每个源身份/UTC/值都须实际收到。
            for m in source:
                actual=messages.get(g.telemetry_key(m));assert actual is not None
                assert all(actual[k]==m[k] for k in ('timestamp','seq','session_id','validity','unit','value','samples','sample_rate'))
            health=backend.state.hub
            assert health.accepted==len(messages) and health.rejected==0 and backend.state.adapter.dropped==0
            meaningful=[s for s in snapshots if s['server_time']>=base+60000 and s['server_time']<source[-1]['timestamp']-1000]
            assert meaningful and all(s['gateway_state']=='ONLINE' and s['nodes']['NODE-B']=='ONLINE' for s in meaningful)
            assert all(m['validity']!='STALE' for s in meaningful for m in s['streams'] if m['node_id']=='NODE-B')
            assert max_bytes<=2047
            result.update(status='PASS',source_records=len(source),Broker_received=len(messages),Backend_accepted=health.accepted,
                Backend_rejected=health.rejected,WSS_snapshots=len(snapshots),WSS_no_unexpected_STALE=True,
                Backend_dropped=backend.state.adapter.dropped,temperature_entry_records=len(entry_records),temperature_trace_lost=lib.bridge_trace_lost(),
                exact_source_identity_UTC_values_match=True,live_high_water=lib.bridge_high_water(),overflow_expired_replay_drop=lib.bridge_error(),
                injected_delivery_stalls_ms=[1500,1500,2516],max_JSON_bytes=max_bytes,C_coreMQTT_DLL_sha256=g.sha(dll.read_bytes()))
            lib.bridge_close();close_seen[0]=True
    except BaseException as e:
        result.update(error_type=type(e).__name__,error_text_sha256=g.sha(str(e).encode()));raise
    finally:
        g.write_private(private/'Broker-private.jsonl',('\n'.join(json.dumps(x) for x in recorded)+'\n').encode())
        g.write_private(private/'WSS-private.jsonl',('\n'.join(json.dumps(x) for x in snapshots)+'\n').encode())
        if 'entry_records' in locals():g.write_private(private/'C-temp-entry-private.jsonl',('\n'.join(json.dumps(x) for x in entry_records)+'\n').encode())
        if tls:tls.close()
        if observer:observer.disconnect();observer.loop_stop()
        if server:server.should_exit=True
        if thread:thread.join(timeout=10)
        broker.close();result['owned_local_resources_closed']=True;g.save(private/'receipt-private.json',result)
        (out/'receipt.json').write_text(json.dumps(result,indent=2)+'\n');(ROOT/'node-b/build/b5-egress-TLS-latest.json').write_text(json.dumps({'out':str(out)})+'\n')
        print(json.dumps(result))
    return 0

if __name__=='__main__':raise SystemExit(main())
