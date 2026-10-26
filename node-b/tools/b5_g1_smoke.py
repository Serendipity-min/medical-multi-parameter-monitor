"""G1真实账号/Backend/WSS限时冒烟，非实板：SSH隧道、真实TLS、最小MQTT5拒绝负例。"""
import argparse
import asyncio
import http.client
import json
from pathlib import Path
import queue
import socket
import ssl
import subprocess
import sys
import threading
import time

import paho.mqtt.client as mqtt
from websockets.asyncio.client import connect

import b5_g1_cloud as g
from b4_recovery import protected


def free_port():
    with socket.socket() as sock:
        sock.bind(('127.0.0.1',0));return sock.getsockname()[1]


def client(user,password,identity,protocol=mqtt.MQTTv311):
    c=mqtt.Client(mqtt.CallbackAPIVersion.VERSION2,client_id=identity,protocol=protocol,reconnect_on_failure=False)
    c.username_pw_set(user,password);c.tls_set_context(ssl.create_default_context());c.connect_timeout=6
    c.reconnect_delay_set(1,1)
    # 本次客户端不启用自动重连；失败保留且结束，不踢正式或其它测试会话。
    return c


async def until(predicate,label,seconds=8):
    end=time.monotonic()+seconds
    while time.monotonic()<end:
        if predicate():return
        await asyncio.sleep(.025)
    raise ValueError(label)


def health(host,port):
    context=ssl.create_default_context()
    with socket.create_connection(('127.0.0.1',port),timeout=5) as raw:
        with context.wrap_socket(raw,server_hostname=host) as conn:
            conn.sendall(('GET /medical-monitor/api/health HTTP/1.1\r\nHost: '+host+':18775\r\nConnection: close\r\n\r\n').encode())
            response=http.client.HTTPResponse(conn);response.begin()
            if response.status!=200:raise ValueError('BACKEND_HEALTH_HTTP_STATUS')
            return json.loads(response.read())


async def run(private,P,credentials,port):
    host=P['snapshot']['backend']['host'];origin=P['origin'];raw_events=[];observed=[];clients=[]
    session='b5-g1-'+P['tx'];received=queue.Queue()
    def append(label,data):
        row={'monotonic':time.monotonic(),'label':label,'data':data};raw_events.append(row)
        with (private/'smoke-events-private.jsonl').open('a',encoding='utf8',newline='\n') as f:f.write(json.dumps(row)+'\n')
    def attach(user,identity,protocol=mqtt.MQTTv311):
        c=client(user,credentials['passwords'][user],identity,protocol);clients.append(c);c.ack=threading.Event();c.sub=threading.Event();c.publish_ack=[]
        def connected(_c,_u,_flags,reason,_props):
            append(identity+'-CONNACK',{'reason':reason.value});c.connect_reason=reason.value;c.ack.set()
        def subscribed(_c,_u,mid,reasons,_props):
            append(identity+'-SUBACK',{'mid':mid,'reasons':[r.value for r in reasons]});c.sub_codes=[r.value for r in reasons];c.sub.set()
        def published(_c,_u,mid,reason,_props):
            append(identity+'-PUBACK',{'mid':mid,'reason':reason.value});c.publish_ack.append((mid,reason.value))
        c.on_connect=connected;c.on_subscribe=subscribed;c.on_publish=published
        c.on_message=lambda _c,_u,m:received.put({'topic':m.topic,'payload_hex':m.payload.hex(),'qos':m.qos,'retain':m.retain})
        c.connect(host,8883,keepalive=15);c.loop_start();return c
    try:
        before=await asyncio.to_thread(health,host,port);append('Backend-health-before',before)
        if not before['mqtt_connected']:raise ValueError('ISOLATED_BACKEND_NOT_SUBSCRIBED')
        observer=attach('b5-observer','b5-evidence-isolated');publisher=attach('b5-gateway','b5-c-isolated')
        await until(lambda:observer.ack.is_set() and publisher.ack.is_set(),'POSITIVE_CONNACK')
        if observer.connect_reason or publisher.connect_reason:raise ValueError('POSITIVE_AUTH_REJECTED')
        observer.subscribe('mpm/v1/GW-B5-001/#',qos=1)
        await until(observer.sub.is_set,'POSITIVE_SUBACK')
        if any(x>=128 for x in observer.sub_codes):raise ValueError('POSITIVE_SUBSCRIBE_REJECTED')
        context=ssl.create_default_context()
        async with connect(origin.replace('https:','wss:')+'/medical-monitor/ws/v1/monitor',
                           host='127.0.0.1',port=port,server_hostname=host,ssl=context,origin=origin,
                           open_timeout=8,proxy=None) as ws:
            await ws.send(json.dumps({'token':credentials['view_token'],'gateway_id':'GW-B5-001'}))
            now=int(time.time()*1000)
            def body(unit,value,validity='VALID',**extra):
                return dict(timestamp=now,seq=1,session_id=session,validity=validity,source='MOCK',synthetic=True,unit=unit,value=value,**extra)
            records=[('status',body('state','ONLINE')),
                     ('NODE-B/status',body('state','ONLINE')),
                     ('NODE-B/telemetry/hr',body('bpm',60.0)),
                     ('NODE-B/telemetry/rr',body('breaths/min',None,'INVALID')),
                     ('NODE-B/telemetry/temp',body('degC',None,'INVALID')),
                     ('NODE-B/telemetry/ecg',body('mV',None,samples=[0.0]*100,sample_rate=250))]
            expected={}
            for suffix,payload in records:
                topic='mpm/v1/GW-B5-001/'+suffix;blob=json.dumps(payload,separators=(',',':')).encode();expected[topic]=blob
                append('synthetic-fixture-publish',{'topic':topic,'payload_hex':blob.hex(),'qos':1,'retain':False,'not_ADC_or_hardware':True})
                info=publisher.publish(topic,blob,qos=1,retain=False)
                await asyncio.to_thread(info.wait_for_publish,5)
                if not info.is_published():raise ValueError('POSITIVE_PUBACK_TIMEOUT')
            end=time.monotonic()+8;snapshot=None
            while time.monotonic()<end:
                raw=await asyncio.wait_for(ws.recv(),3);value=json.loads(raw)
                append('WSS-raw',value)
                streams={x['stream']:x for x in value['streams']}
                if (value['gateway_state']=='ONLINE' and value['nodes']['NODE-A']=='OFFLINE' and
                    value['nodes']['NODE-B']=='ONLINE' and all(x in streams for x in ['HR','RR','TEMP','ECG']) and
                    streams['HR']['value']==60.0 and streams['HR']['validity']=='VALID' and
                    streams['RR']['validity']=='INVALID' and streams['RR']['value'] is None and
                    streams['TEMP']['validity']=='INVALID' and streams['TEMP']['value'] is None and
                    len(streams['ECG']['samples'])==100 and
                    all(x['source']=='MOCK' and x['synthetic'] and x['session_id']==session for x in streams.values())):
                    snapshot=value;break
            if snapshot is None:raise ValueError('WSS_CONTENT_NOT_MATCHED')
            await until(lambda:received.qsize()>=len(records),'BROKER_OBSERVER_MESSAGES')
            while not received.empty():
                item=received.get();append('Broker-observer-raw',item);observed.append(item)
            if not all(any(x['topic']==topic and bytes.fromhex(x['payload_hex'])==blob for x in observed) for topic,blob in expected.items()):
                raise ValueError('BROKER_PAYLOAD_MISMATCH')
            after=await asyncio.to_thread(health,host,port);append('Backend-health-after',after)
            if after['accepted']-before['accepted']!=len(records) or after['rejected']!=before['rejected']:
                raise ValueError('BACKEND_ACCEPTANCE_COUNT')
            denied=[]
            for user,suffix in [('b5-gateway','pub'),('b5-observer','obs')]:
                c=attach(user,'b5-g1-deny-'+suffix+'-isolated',mqtt.MQTTv5)
                await until(c.ack.is_set,'NEGATIVE_CONNACK')
                if c.connect_reason:raise ValueError('NEGATIVE_AUTH_UNEXPECTEDLY_REJECTED')
                payload=body('bpm',60.0);info=c.publish(g.DENY,json.dumps(payload).encode(),qos=1,retain=False)
                await until(lambda:any(mid==info.mid for mid,_ in c.publish_ack),'NEGATIVE_PUBACK')
                reason=next(reason for mid,reason in c.publish_ack if mid==info.mid)
                denied.append({'role':user,'namespace':g.DENY,'protocol':'MQTTv5','PUBACK_reason':reason,'denied':reason==0x87})
                if reason!=0x87:raise ValueError('NEGATIVE_PUBLISH_NOT_EXPLICITLY_DENIED')
                c.disconnect();c.loop_stop()
            append('negative-results',denied)
            return {'status':'PASS','source':'G1_GENERATED_MOCK_FIXTURES_NOT_DEVICE_ADC','real_tls_MQTTv311_positive':True,
                    'CONNECT_SUBACK_observed':True,'Broker_payloads_matched':len(records),
                    'Backend_accepted_delta':after['accepted']-before['accepted'],'Backend_rejected_delta':after['rejected']-before['rejected'],
                    'WSS_Cloud_TLS_via_SSH_tunnel':True,'WSS_HR_VALID_RR_TEMP_INVALID':True,'WSS_MOCK_synthetic_only':True,
                    'A_segment_OFFLINE':True,'negative_MQTTv5':denied,'negative_subscription_test':'NOT_RUN_STATIC_ACL_NO_READ_GRANT',
                    'formal_namespace_messages_sent':0,'B5START_sent':0,'hardware_access':False,'test_clients_cleanly_disconnected':True,'exit_code':0}
    finally:
        for c in clients:
            try:c.disconnect();c.loop_stop()
            except Exception:pass


def worker(auth_path):
    pointer=json.loads((g.ROOT/'node-b/build/b5-g1-private-pointer.json').read_bytes());private=Path(pointer['base'])
    a=json.loads(protected(auth_path,False).read_bytes());raw=protected(private/a['package_filename'],False).read_bytes();P=json.loads(raw)
    g.authorize(a,P,raw)
    if a.get('smoke_tool_sha256')!=g.sha(Path(__file__).read_bytes()):raise ValueError('SMOKE_TOOL_BINDING')
    apply=json.loads((g.ROOT/'node-b/evidence/B5-G1/apply.json').read_bytes())
    if apply.get('setup_exit_code')!=0 or apply.get('tx')!=P['tx']:raise ValueError('G1_APPLY_NOT_PASSED')
    g.write_private(private/'G1-smoke-started-private.json',g.encode({'time':time.time(),'auth_sha256':g.sha(auth_path.read_bytes())}))
    creds=json.loads(protected(private/'test-credentials-private.json',False).read_bytes());port=free_port()
    with (private/'SSH-tunnel-log-private.bin').open('xb') as log:
        args=['ssh','-o','BatchMode=yes','-o','StrictHostKeyChecking=yes','-o','ExitOnForwardFailure=yes','-o','ConnectTimeout=10',
              '-o','ServerAliveInterval=15','-o','ServerAliveCountMax=2','-N','-L',f'127.0.0.1:{port}:127.0.0.1:18775','tencent-codex']
        tunnel=subprocess.Popen(args,stdout=log,stderr=subprocess.STDOUT,creationflags=subprocess.CREATE_NO_WINDOW)
        try:
            end=time.monotonic()+12
            while time.monotonic()<end:
                if tunnel.poll() is not None:raise ValueError('SSH_TUNNEL_START_FAILED')
                try:
                    with socket.create_connection(('127.0.0.1',port),timeout=.1):break
                except OSError:time.sleep(.1)
            else:raise ValueError('SSH_TUNNEL_NOT_READY')
            result=asyncio.run(asyncio.wait_for(run(private,P,creds,port),100))
        finally:
            tunnel.terminate();tunnel.wait(timeout=8)
    result.update(tx=P['tx'],tool_sha256=g.sha(Path(__file__).read_bytes()),package_sha256=g.sha(raw),
                  raw_events_sha256=g.sha((private/'smoke-events-private.jsonl').read_bytes()))
    return result


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--authorization',required=True,type=Path);a=parser.parse_args()
    try:result=worker(a.authorization)
    except Exception as e:
        import traceback
        private=Path(json.loads((g.ROOT/'node-b/build/b5-g1-private-pointer.json').read_bytes())['base'])
        g.write_private(private/('smoke-failure-'+str(time.time_ns())+'-private.txt'),traceback.format_exc().encode())
        reason=str(e) if isinstance(e,ValueError) and str(e).replace('_','').isalnum() else type(e).__name__
        result={'status':'STOP_SMOKE_FAILED_NO_RETRY','reason':reason,'exit_code':1,'automatic_retry':False,'automatic_rollback':False}
    (g.ROOT/'node-b/evidence/B5-G1/smoke.json').write_bytes(g.encode(result));print(json.dumps(result));return result['exit_code']


if __name__=='__main__':raise SystemExit(main())
