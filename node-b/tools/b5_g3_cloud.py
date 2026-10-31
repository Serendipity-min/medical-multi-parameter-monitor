"""G3只订阅观察：独立MQTT观察身份、实际Backend健康、SSH转发WSS；绝不发布。"""
import asyncio
import json
from pathlib import Path
import queue
import socket
import ssl
import subprocess
import sys
import threading
import time

import b5_g3_contract as g
import b5_g1_smoke as prior
sys.path.insert(0,str(g.ROOT))
from cloud.backend.app.adapters import decode_mqtt


def current_b_session(snap,fresh_gateway,profile=None):
    streams={x['stream']:x for x in snap['streams'] if x['node_id']=='NODE-B'}
    if not {'HR','RR','TEMP','ECG'}<=streams.keys():return None
    names=('HR','RR','TEMP','ECG','RESP') if profile is not None else ('HR','RR','TEMP','ECG')
    if any(n not in streams for n in names):return None
    rows=[streams[n] for n in names]
    sessions={m['session_id'] for m in rows}
    if len(sessions)!=1:return None
    session=next(iter(sessions))
    if not session.startswith(fresh_gateway.rsplit('-',1)[0]+'-'):return None
    if profile is None:
        if streams['ECG']['validity']!='VALID' or streams['HR']['validity']!='VALID':return None
    else:
        import b5_channel_profiles as channels
        if not channels.ready_streams(streams,profile):return None
    if any(m['source']!='MOCK' or m['synthetic'] is not True for m in rows):return None
    return session

def drain_final_events(rawq,log):
    while not rawq.empty():
        kind,data=rawq.get_nowait();g.append(log,kind,data)


def close_client_bounded(client,timeout=1.5):
    result={}
    def close():
        try:client.disconnect();client.loop_stop();result['complete']=True
        except Exception:result['error']=True
    thread=threading.Thread(target=close,daemon=True);thread.start();thread.join(timeout)
    return result.get('complete') is True

async def bounded_health(host,port,timeout=3):
    async def request():
        reader,writer=await asyncio.open_connection('127.0.0.1',port,ssl=ssl.create_default_context(),
            server_hostname=host,ssl_handshake_timeout=timeout)
        try:
            writer.write(('GET /medical-monitor/api/health HTTP/1.1\r\nHost: '+host+
                ':18775\r\nConnection: close\r\n\r\n').encode());await writer.drain()
            head=await reader.readuntil(b'\r\n\r\n');rows=head.decode('ascii').split('\r\n')
            g.require(rows[0].split()[1]=='200','G3_HEALTH_HTTP_STATUS')
            headers=dict(row.lower().split(':',1) for row in rows[1:] if ':' in row)
            length=int(headers['content-length']);g.require(0<length<=65536,'G3_HEALTH_BODY_BOUND')
            return json.loads(await reader.readexactly(length))
        finally:
            writer.close()
            try:await asyncio.wait_for(writer.wait_closed(),.2)
            except asyncio.TimeoutError:pass
    return await asyncio.wait_for(request(),timeout)


async def observe(a,root,bundle,stop,shared,*,snapshot_validator=None,session_selector=None):
    validate=snapshot_validator or g.assert_snapshot
    select_session=session_selector or current_b_session
    P=g.load(bundle['cloud_package']['path']);credentials=g.load(bundle['cloud_credentials']['path'])
    host=P['snapshot']['backend']['host'];origin=P['origin'];client=None;tunnel=None
    rawq=queue.Queue(maxsize=2048);connected=threading.Event();subscribed=threading.Event();pre_sessions=set()
    con_reason=[];sub_codes=[];disconnects=[];port=prior.free_port();r={'status':'STOP','exit_code':1,'publications':0}
    network_log=(root/'cloud-events-private.jsonl').open('x',encoding='utf8')
    tunnel_log=(root/'tunnel-private.log').open('xb')
    try:
        async def health_query(label,timeout=3):
            g.append(network_log,'HEALTH_BEGIN',{'label':label,'deadline_monotonic':time.monotonic()+timeout})
            try:return await bounded_health(host,port,timeout)
            finally:g.append(network_log,'HEALTH_END',{'label':label})
        tunnel=subprocess.Popen(['ssh','-o','BatchMode=yes','-o','StrictHostKeyChecking=yes',
          '-o','ExitOnForwardFailure=yes','-o','ConnectTimeout=10','-o','ServerAliveInterval=15',
          '-o','ServerAliveCountMax=2','-N','-L',f'127.0.0.1:{port}:127.0.0.1:18775','tencent-codex'],
          stdout=tunnel_log,stderr=subprocess.STDOUT,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
        until=time.monotonic()+12
        while time.monotonic()<until:
            g.require(tunnel.poll() is None,'G3_TUNNEL_EXITED')
            try:
                with socket.create_connection(('127.0.0.1',port),timeout=.1):break
            except OSError:await asyncio.sleep(.1)
        else:raise ValueError('G3_TUNNEL_NOT_READY')
        client=prior.client('b5-observer',credentials['passwords']['b5-observer'],a['observer_client_id'])
        def put(kind,data):
            try:rawq.put_nowait((kind,data))
            except queue.Full:shared['cloud_queue_overflow']=True
        def on_connect(_c,_u,_flags,reason,_props):
            con_reason.append(reason.value);put('OBSERVER_CONNACK',{'code':reason.value});connected.set()
        def on_sub(_c,_u,mid,reasons,_props):
            sub_codes.extend(x.value for x in reasons);put('OBSERVER_SUBACK',{'mid':mid,'codes':list(sub_codes)});subscribed.set()
        def on_message(_c,_u,m):
            put('BROKER_RAW',{'topic':m.topic,'payload_hex':bytes(m.payload).hex(),'qos':m.qos,'retain':bool(m.retain),
                              'dup':bool(m.dup),'received_monotonic':time.monotonic(),'received_UTC_ms':int(time.time()*1000)})
        def on_disconnect(_c,_u,_flags,reason,_props):
            event={'code':reason.value,'requested_shutdown':stop.is_set(),'received_monotonic':time.monotonic()}
            disconnects.append(event);put('OBSERVER_DISCONNECT',event)
            if not stop.is_set():shared['cloud_disconnected']=True
        client.on_connect=on_connect;client.on_subscribe=on_sub;client.on_message=on_message;client.on_disconnect=on_disconnect
        await asyncio.to_thread(client.connect,host,8883,15);client.loop_start()
        await prior.until(connected.is_set,'G3_OBSERVER_CONNACK_TIMEOUT')
        g.require(con_reason==[0],'G3_OBSERVER_CONNECT_REJECTED')
        result,mid=client.subscribe('mpm/v1/GW-B5-001/#',qos=1);g.require(result==0,'G3_OBSERVER_SUBSCRIBE_CALL')
        await prior.until(subscribed.is_set,'G3_OBSERVER_SUBACK_TIMEOUT')
        g.require(sub_codes and all(x<128 for x in sub_codes),'G3_OBSERVER_SUBACK_REJECTED')
        async with prior.connect(origin.replace('https:','wss:')+'/medical-monitor/ws/v1/monitor',host='127.0.0.1',
          port=port,server_hostname=host,ssl=ssl.create_default_context(),origin=origin,proxy=None,
          open_timeout=8,close_timeout=1,max_size=65536,max_queue=8) as ws:
            await ws.send(json.dumps({'token':credentials['view_token'],'gateway_id':'GW-B5-001'}))
            # WSS令牌发送不等于鉴权通过；先收到并校验首份真实快照，再冻结基线。
            first_snap=json.loads(await asyncio.wait_for(ws.recv(),3))
            validate(first_snap,a.get('channel_profile'));g.append(network_log,'WSS_RAW',first_snap)
            health=await health_query('BEFORE')
            g.require(health.get('status')=='ok' and health.get('mqtt_connected') is True,'G3_BACKEND_NOT_READY')
            g.append(network_log,'BACKEND_HEALTH_BEFORE',health);health_at=time.monotonic();first=True
            fresh_gateway=None;common=False;arm_baseline=False
            while not stop.is_set():
                g.require(tunnel.poll() is None,'G3_TUNNEL_EXITED')
                g.require(not shared.get('cloud_queue_overflow') and not shared.get('cloud_disconnected'),'G3_CLOUD_TRANSPORT_FAILURE')
                arm=g.maybe(root/'ARM_ATTEMPT.json')
                if (root/'ARM_PREPARE.json').exists() and not arm_baseline:
                    health=await health_query('ARM_BASELINE')
                    g.require(health.get('status')=='ok' and health.get('mqtt_connected') is True,'G3_ARM_BACKEND_NOT_READY')
                    g.append(network_log,'BACKEND_ARM_BASELINE',health)
                    g.save(root/'ARM_BACKEND_BASELINE.json',{'monotonic':time.monotonic(),'health':health})
                    arm_baseline=True
                while not rawq.empty():
                    kind,data=rawq.get_nowait();g.append(network_log,kind,data)
                    if kind!='BROKER_RAW':continue
                    blob=bytes.fromhex(data['payload_hex']);g.require(len(blob)<=2047,'G3_MQTT_2048_BUFFER')
                    message=decode_mqtt(data['topic'],blob).model_dump()
                    g.require(message['gateway_id']=='GW-B5-001' and message['synthetic'] and message['source'] in ('MOCK','REPLAY'),
                              'G3_BROKER_SOURCE_OR_NAMESPACE')
                    g.append(network_log,'BROKER_DECODED',message)
                    if message['stream']=='GATEWAY_STATUS':
                        if not arm:pre_sessions.add(message['session_id'])
                        elif (message['value']=='ONLINE' and message['validity']=='VALID' and message['source']=='MOCK'
                              and message['session_id'] not in pre_sessions and message['timestamp']>=arm['UTC_ms']-5000):
                            fresh_gateway=message['session_id']
                if time.monotonic()-health_at>=1:
                    health=await health_query('PERIODIC');g.append(network_log,'BACKEND_HEALTH',health)
                    g.require(health.get('status')=='ok' and health.get('mqtt_connected') is True,'G3_BACKEND_DISCONNECTED')
                    health_at=time.monotonic()
                try:raw=await asyncio.wait_for(ws.recv(),.2)
                except asyncio.TimeoutError:continue
                snap=json.loads(raw);validate(snap,a.get('channel_profile'));g.append(network_log,'WSS_RAW',snap)
                shared['cloud_last_monotonic']=time.monotonic()
                if first:
                    g.save(root/'NET_READY.json',{'monotonic':time.monotonic(),'backend_health':health,
                       'observer_CONNACK':con_reason,'observer_SUBACK':sub_codes,'WSS_authenticated_snapshot':True,
                       'health_baseline_may_include_old_messages':True,
                       'baseline_after_CONNACK_SUBACK_authenticated_WSS':True});first=False
                session=select_session(snap,fresh_gateway,a.get('channel_profile')) if fresh_gateway else None
                if (arm and not common and fresh_gateway and snap['gateway_state']=='ONLINE'
                    and snap['nodes']['NODE-B']=='ONLINE' and session):
                    g.save(root/'CLOUD_COMMON.json',{'monotonic':time.monotonic(),'server_time':snap['server_time'],
                         'gateway_session':fresh_gateway,'B_session':session})
                    common=True
            health=await health_query('AFTER',1);g.append(network_log,'BACKEND_HEALTH_AFTER',health)
            r.update(status='CLOUD_OBSERVATIONS_SAVED_REVIEW_PENDING',exit_code=0,
                     observer_CONNACK=con_reason,observer_SUBACK=sub_codes,WSS_authenticated=True)
    except BaseException as e:
        r.update(g.error_record(e))
        shared['cloud_error']=True
        if not (root/'CLOUD_FAULT.json').exists():g.save(root/'CLOUD_FAULT.json',{'reason':'CLOUD_OBSERVER_FAILED'})
    finally:
        g.save(root/'cloud-cleanup-started-private.json',dict(r,observer_disconnects=disconnects,cleanup_complete=False))
        client_closed=True
        if client:
            stop.set()
            client_closed=close_client_bounded(client)
            if not client_closed:r.update(client_close_error=True,exit_code=1,client_thread_state='UNKNOWN')
        if tunnel:
            tunnel.terminate()
            try:tunnel.wait(timeout=1)
            except subprocess.TimeoutExpired:tunnel.kill();tunnel.wait(timeout=1)
        # 回调会先触发失败锁存；退出时仍落盘其原因码，不丢最后一批原始事件。
        drain_final_events(rawq,network_log);r['observer_disconnects']=disconnects;r['cleanup_complete']=client_closed
        tunnel_log.close();network_log.close();g.save(root/'cloud-receipt-private.json',r)
    return r


def run(a,root,bundle,stop,shared):return asyncio.run(observe(a,root,bundle,stop,shared))
