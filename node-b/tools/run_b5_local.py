"""实测CAN离线产物→真实本地TLS Broker→实际Backend→WSS；非ESP/正式云端验收。"""
from pathlib import Path
import asyncio
from contextlib import asynccontextmanager
import hashlib
import json
import os
import ssl
import sys
import threading
import time
import uuid
import queue
from unittest.mock import patch
import paho.mqtt.client as mqtt
import uvicorn
from fastapi import FastAPI
from websockets.asyncio.client import connect
from b5_local_broker import Broker,free_port

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'cloud/backend'));sys.path.insert(0,str(ROOT))
from app.main import create_app
from app.hub import Hub
from cloud.ai.facts import extract,answer_facts


def load(p):return json.loads(p.read_text(encoding='utf-8'))


class Suite:
    def __init__(self,out,broker,private):
        self.out,self.broker,self.private=out,broker,private
        self.clock=[1577836800.0];self.port=free_port();self.origin=f'https://127.0.0.1:{self.port}'
        self.token='synthetic-b5-view-'+uuid.uuid4().hex;self.seq=0;self.case='initial';self.observed=queue.Queue()
        self.evidence=private/('local-TLS-recording-'+out.name);self.evidence.mkdir()
        self.config=out/'backend-synthetic.json'
        self.config.write_text(json.dumps({'host':'127.0.0.1','port':broker.port,'username':'b5-reader','password':broker.password,'client_id':'b5-local-backend-'+uuid.uuid4().hex[:8],'ca_file':str(broker.cert)}),encoding='utf-8')

    def client(self,user,client_id):
        c=mqtt.Client(mqtt.CallbackAPIVersion.VERSION2,client_id=client_id,protocol=mqtt.MQTTv311)
        c.username_pw_set(user,self.broker.password);c.tls_set_context(ssl.create_default_context(cafile=str(self.broker.cert)))
        return c

    async def wait(self,predicate,label,seconds=8):
        end=time.monotonic()+seconds
        while time.monotonic()<end:
            if predicate():return
            await asyncio.sleep(.025)
        raise AssertionError(label)

    def publish(self,suffix,body,qos=1):
        info=self.publisher.publish('mpm/v1/GW-B5-001/'+suffix,json.dumps(body),qos=qos,retain=suffix.endswith('status'))
        if qos:info.wait_for_publish(timeout=3);assert info.is_published()

    def status(self):
        self.seq+=1
        self.publish('status',{'timestamp':int(self.clock[0]*1000),'seq':self.seq,'session_id':'b5-local-'+self.case,'validity':'VALID','source':'MOCK','synthetic':True,'unit':'state','value':'ONLINE'})

    async def snapshot(self,ws,predicate):
        async with asyncio.timeout(8):
            while True:
                raw=await ws.recv()
                # 每次运行独占目录，逐条保留原始JSON；当前显示别名不充当失败原件。
                with (self.evidence/'WSS-payloads-private.jsonl').open('a',encoding='utf-8',newline='\n') as f:f.write(raw+'\n')
                value=json.loads(raw)
                # 加速回放时客户端可能积压旧快照；只有当前受控时钟下的新快照能作事实。
                if -1000<=int(self.clock[0]*1000)-value['server_time']<=5000 and predicate(value):return value

    async def case_run(self,label):
        source=self.private/(label+'-MpFrame-MQTT-private.jsonl')
        records=[json.loads(s) for s in source.read_text(encoding='utf-8').splitlines()]
        self.case=label;self.clock[0]=min(r['payload']['timestamp'] for r in records)/1000;self.seq=0
        # 两份历史记录各自使用当时本地测试UTC，不能为串接案例而篡改采集时间。
        # 此测试夹具在服务器事件循环内换新Hub；生产Backend没有该管理接口。
        fresh=Hub(['GW-B5-001'],clock=lambda:self.clock[0],monotonic=lambda:self.clock[0])
        fresh.broker_connected=True;self.app.state.hub=fresh;self.app.state.adapter.hub=fresh
        self.status();last_status=self.clock[0]
        context=ssl.create_default_context(cafile=str(self.broker.cert))
        async with connect(self.origin.replace('https:','wss:')+'/medical-monitor/ws/v1/monitor',ssl=context,origin=self.origin) as ws:
            await ws.send(json.dumps({'token':self.token,'gateway_id':'GW-B5-001'}))
            for r in records:
                assert r['payload']['source']=='MOCK' and r['payload']['synthetic']
                self.clock[0]=max(self.clock[0],r['payload']['timestamp']/1000)
                if self.clock[0]-last_status>=5:self.status();last_status=self.clock[0]
                self.publish(r['topic'].split('GW-B5-001/')[1],r['payload'],r['qos'])
                await asyncio.sleep(.003)
            self.status()
            def good(s):
                streams={i['stream']:i for i in s['streams']}
                valid='HR' if label=='ECG' else 'RR';invalid='RR' if label=='ECG' else 'HR'
                expected={name:next(r['payload']['seq'] for r in reversed(records) if r['topic'].endswith('/telemetry/'+name.lower())) for name in (valid,invalid)}
                return s['gateway_state']=='ONLINE' and s['nodes']['NODE-A']=='OFFLINE' and streams.get(valid,{}).get('validity')=='VALID' and streams.get(invalid,{}).get('validity')=='INVALID' and all(streams[name]['seq']==seq for name,seq in expected.items())
            snap=await self.snapshot(ws,good);streams={i['stream']:i for i in snap['streams']}
            valid='HR' if label=='ECG' else 'RR';invalid='RR' if label=='ECG' else 'HR'
            assert streams[valid]['value']==(60 if label=='ECG' else 15)
            assert streams[invalid]['value'] is None and streams['TEMP']['value'] is None and streams['TEMP']['validity']=='INVALID'
            (self.private/(label+'-WSS-snapshot-private.json')).write_text(json.dumps(snap,ensure_ascii=False,indent=2),encoding='utf-8')
            with (self.evidence/(label+'-WSS-snapshot-private.json')).open('x',encoding='utf-8',newline='\n') as f:json.dump(snap,f,ensure_ascii=False,indent=2)
            facts=extract(snap,'GW-B5-001',int(self.clock[0]*1000));text=answer_facts(facts,'心率和呼吸率体温')
            assert all(f['value'] is None for f in facts if f['stream'] in (invalid,'TEMP'))
            assert '模拟数据，非真人测量' in text
            original=streams[valid];key=('GW-B5-001','NODE-B',valid)
            before=fresh.accepted;self.publish('NODE-B/telemetry/'+valid.lower(),{k:v for k,v in original.items() if k not in ('gateway_id','node_id','stream')})
            await asyncio.sleep(.15);assert fresh.current[key][0].seq==original['seq']
            self.clock[0]+=6;self.status()
            stale=await self.snapshot(ws,lambda s:all(i['value'] is None for i in s['streams'] if i['stream']==valid))
            assert next(i for i in stale['streams'] if i['stream']==valid)['validity']=='STALE'
            assert all(f['value'] is None for f in extract(stale,'GW-B5-001',int(self.clock[0]*1000)))
            replay={k:v for k,v in original.items() if k not in ('gateway_id','node_id','stream')};replay['source']='REPLAY'
            self.publish('NODE-B/replay/'+valid.lower(),replay)
            replayed=await self.snapshot(ws,lambda s:s.get('replay') is not None)
            assert all(i['value'] is None for i in replayed['streams'] if i['stream']==valid)
            node_session=original['session_id'];stamp=int(self.clock[0]*1000)
            self.publish('NODE-B/status',{'timestamp':stamp,'seq':9000,'session_id':'new-node-boot','validity':'VALID','source':'MOCK','synthetic':True,'unit':'state','value':'ONLINE'})
            old=dict(replay,source='MOCK',seq=999999,timestamp=stamp)
            self.publish('NODE-B/telemetry/'+valid.lower(),old)
            await asyncio.sleep(.15)
            masked=await self.snapshot(ws,lambda s:s['nodes']['NODE-B']=='ONLINE' and all(i['value'] is None for i in s['streams'] if i['stream']==valid))
            new=dict(old,session_id='new-node-boot',seq=1)
            self.publish('NODE-B/telemetry/'+valid.lower(),new)
            recovered=await self.snapshot(ws,lambda s:any(i['stream']==valid and i['validity']=='VALID' for i in s['streams']))
            assert next(i for i in recovered['streams'] if i['stream']==valid)['session_id']=='new-node-boot'
            self.publish('NODE-B/status',{'timestamp':stamp+1,'seq':9001,'session_id':'new-node-boot','validity':'OFFLINE','source':'MOCK','synthetic':True,'unit':'state','value':'OFFLINE'})
            offline=await self.snapshot(ws,lambda s:s['nodes']['NODE-B']=='OFFLINE')
            assert all(i['value'] is None and not i['samples'] for i in offline['streams'])
            return {'case':label,'status':'PASS','source_file_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),
                    'actual_MQTT_messages':len(records),'Backend_accepted':fresh.accepted,'Backend_rejected':fresh.rejected,
                    'valid_stream':valid,'value':streams[valid]['value'],'invalid_stream':invalid,
                    'checks':['actual_Broker_Backend_WSS','MOCK_and_synthetic','TEMP_INVALID','A_OFFLINE','duplicate','STALE_6s','REPLAY_not_current','node_boot_old_session_masked','new_session_recovers','OFFLINE_clears','AI_facts_null_invalid_stale'],
                    'source_UTC_unchanged':True,'fixture_Backend_Hub_reset_between_recordings':True}

    async def run(self):
        await self.wait(lambda:self.server.started,'HTTPS_BACKEND_NOT_READY')
        self.loop=asyncio.get_running_loop()
        await self.wait(lambda:self.app.state.adapter.connected,'BACKEND_SUBACK')
        self.app.state.hub.clock=lambda:self.clock[0];self.app.state.hub.monotonic=lambda:self.clock[0]
        self.publisher=self.client('b5-gateway','b5-c-isolated');self.publisher.connect('127.0.0.1',self.broker.port);self.publisher.loop_start()
        await self.wait(lambda:self.publisher.is_connected(),'PUBLISHER_CONNACK')
        self.audit=self.client('b5-audit','b5-local-audit')
        subscribed=threading.Event();self.audit.on_connect=lambda c,*_:c.subscribe('#',qos=1)
        self.audit.on_subscribe=lambda *_:subscribed.set()
        def observed(_client,_user,message):
            with (self.evidence/'Broker-payloads-private.jsonl').open('a',encoding='utf-8',newline='\n') as f:
                f.write(json.dumps({'topic':message.topic,'payload_hex':message.payload.hex(),'qos':message.qos,'retain':message.retain,'received_monotonic':time.monotonic()})+'\n')
            self.observed.put(message.topic)
        self.audit.on_message=observed
        self.audit.connect('127.0.0.1',self.broker.port);self.audit.loop_start();await self.wait(subscribed.is_set,'AUDIT_SUBACK')
        try:
            results=[await self.case_run(label) for label in ('ECG','RR')]
            forbidden='mpm/v1/GW-C-001/status'
            self.publisher.publish(forbidden,'{}',qos=1).wait_for_publish(timeout=3);await asyncio.sleep(.3)
            topics=[]
            while not self.observed.empty():topics.append(self.observed.get_nowait())
            assert forbidden not in topics
            # 仅本地夹具以相同测试订阅者ID触发Broker断链；保留真实Paho循环观察自动重连。
            # 手工disconnect会终止Paho循环，不能拿它冒充网络断链恢复。
            kick=self.client('b5-reader',self.app.state.adapter.config['client_id'])
            kick.connect('127.0.0.1',self.broker.port);kick.loop_start()
            try:
                await self.wait(lambda:not self.app.state.hub.broker_connected,'BACKEND_DISCONNECT')
                assert self.app.state.hub.snapshot('GW-B5-001')['gateway_state']=='OFFLINE'
            finally:kick.disconnect();kick.loop_stop()
            await self.wait(lambda:self.app.state.adapter.connected and self.app.state.hub.broker_connected,'BACKEND_RECONNECT_SUBACK')
            report={'status':'PASS','mode':'LOCAL_TLS_MOCK_ONLY','cases':results,'ACL_foreign_gateway_topic_blocked':True,
                    'actual_Backend_disconnect_reconnect':True,'QoS0_puback_is_not_claimed':True,
                    'ESP_AT_TLS_hardware_execution':False,'formal_cloud_operations':0,'listener_scope':'127.0.0.1_EPHEMERAL_NOT8884'}
            report['raw_Broker_WSS_archive_sha256']={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in self.evidence.iterdir()}
            report['raw_Broker_WSS_archive_scope']='UNIQUE_RESTRICTED_EFS_PER_RUN_NOT_MUTABLE_FIXTURE_ALIAS'
            (self.out/'result.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
            print('LOCAL_TLS_BROKER_BACKEND_WSS_PASS',flush=True)
        finally:
            self.publisher.disconnect();self.publisher.loop_stop();self.audit.disconnect();self.audit.loop_stop()


def main():
    private=Path(load(ROOT/'node-b/build/b5-private-pointer.json')['base'])
    out=ROOT/'node-b/build'/('b5-local-'+uuid.uuid4().hex[:10]);out.mkdir()
    broker=Broker(ROOT/'node-b/build/b5-runtime/root',out/'broker');suite=Suite(out,broker,private)
    env={'MONITOR_MQTT_CONFIG':str(suite.config),'MONITOR_VIEW_TOKEN':suite.token,'MONITOR_GATEWAY_IDS':'GW-B5-001',
         'MONITOR_ALLOWED_ORIGINS':suite.origin,'MONITOR_LOG_DIR':str(out/'backend-logs'),'MONITOR_WEB_DIR':str(ROOT/'cloud/web/dist')}
    result=1
    try:
        with patch.dict(os.environ,env):
            backend=create_app();suite.app=backend
            @asynccontextmanager
            async def lifespan(outer):
                async with backend.router.lifespan_context(backend):
                    suite.server_loop=asyncio.get_running_loop();yield
            outer=FastAPI(lifespan=lifespan);outer.mount('/medical-monitor',backend)
            server=uvicorn.Server(uvicorn.Config(outer,host='127.0.0.1',port=suite.port,ssl_keyfile=str(broker.key),ssl_certfile=str(broker.cert),log_level='warning'))
            suite.server=server
            thread=threading.Thread(target=server.run,daemon=True);thread.start()
            try:
                for _ in range(100):
                    if hasattr(suite,'server_loop'):break
                    time.sleep(.05)
                # Hub与适配器只在真实服务器事件循环内读写，避免跨线程测试污染契约。
                asyncio.run_coroutine_threadsafe(suite.run(),suite.server_loop).result(timeout=180)
                result=0
            finally:server.should_exit=True;thread.join(timeout=10)
    finally:
        broker.close()
        (out/'process-receipt.json').write_text(json.dumps({'exit_code':result,'cleanup':'OWNED_BACKEND_AND_BROKER_STOPPED','no_system_service_installed':True})+'\n',encoding='utf-8')
        (ROOT/'node-b/build/b5-local-latest.json').write_text(json.dumps({'out':str(out),'exit_code':result})+'\n',encoding='utf-8')
    return result


if __name__=='__main__':raise SystemExit(main())
