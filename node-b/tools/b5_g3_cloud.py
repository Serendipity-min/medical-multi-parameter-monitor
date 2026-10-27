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


async def observe(a,root,bundle,stop,shared):
    P=g.load(bundle['cloud_package']['path']);credentials=g.load(bundle['cloud_credentials']['path'])
    host=P['snapshot']['backend']['host'];origin=P['origin'];client=None;tunnel=None
    rawq=queue.Queue(maxsize=2048);connected=threading.Event();subscribed=threading.Event();pre_sessions=set()
    con_reason=[];sub_codes=[];port=prior.free_port();r={'status':'STOP','exit_code':1,'publications':0}
    network_log=(root/'cloud-events-private.jsonl').open('x',encoding='utf8')
    tunnel_log=(root/'tunnel-private.log').open('xb')
    try:
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
            put('OBSERVER_DISCONNECT',{'code':reason.value})
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
          open_timeout=8,max_size=65536,max_queue=8) as ws:
            await ws.send(json.dumps({'token':credentials['view_token'],'gateway_id':'GW-B5-001'}))
            health=await asyncio.to_thread(prior.health,host,port)
            g.require(health.get('status')=='ok' and health.get('mqtt_connected') is True,'G3_BACKEND_NOT_READY')
            g.append(network_log,'BACKEND_HEALTH_BEFORE',health);health_at=time.monotonic();first=True
            fresh_gateway=None;common=False;arm_baseline=False
            while not stop.is_set():
                g.require(tunnel.poll() is None,'G3_TUNNEL_EXITED')
                g.require(not shared.get('cloud_queue_overflow') and not shared.get('cloud_disconnected'),'G3_CLOUD_TRANSPORT_FAILURE')
                arm=g.maybe(root/'ARM_ATTEMPT.json')
                if (root/'ARM_PREPARE.json').exists() and not arm_baseline:
                    health=await asyncio.to_thread(prior.health,host,port)
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
                    health=await asyncio.to_thread(prior.health,host,port);g.append(network_log,'BACKEND_HEALTH',health)
                    g.require(health.get('status')=='ok' and health.get('mqtt_connected') is True,'G3_BACKEND_DISCONNECTED')
                    health_at=time.monotonic()
                try:raw=await asyncio.wait_for(ws.recv(),.2)
                except asyncio.TimeoutError:continue
                snap=json.loads(raw);g.assert_snapshot(snap);g.append(network_log,'WSS_RAW',snap)
                shared['cloud_last_monotonic']=time.monotonic()
                if first:
                    g.save(root/'NET_READY.json',{'monotonic':time.monotonic(),'backend_health':health,
                       'observer_CONNACK':con_reason,'observer_SUBACK':sub_codes,'WSS_authenticated_snapshot':True,
                       'health_baseline_may_include_old_messages':True});first=False
                streams={x['stream']:x for x in snap['streams'] if x['node_id']=='NODE-B'}
                if (arm and not common and fresh_gateway and snap['gateway_state']=='ONLINE'
                    and snap['nodes']['NODE-B']=='ONLINE' and {'HR','RR','TEMP','ECG'}<=streams.keys()
                    and streams['ECG']['session_id']==streams['HR']['session_id']
                    and streams['ECG']['source']=='MOCK' and streams['HR']['source']=='MOCK'):
                    g.save(root/'CLOUD_COMMON.json',{'monotonic':time.monotonic(),'server_time':snap['server_time'],
                         'gateway_session':fresh_gateway,'B_session':streams['HR']['session_id']})
                    common=True
            health=await asyncio.to_thread(prior.health,host,port);g.append(network_log,'BACKEND_HEALTH_AFTER',health)
            r.update(status='CLOUD_OBSERVATIONS_SAVED_REVIEW_PENDING',exit_code=0,
                     observer_CONNACK=con_reason,observer_SUBACK=sub_codes,WSS_authenticated=True)
    except BaseException as e:
        r.update(g.error_record(e))
        shared['cloud_error']=True
        if not (root/'CLOUD_FAULT.json').exists():g.save(root/'CLOUD_FAULT.json',{'reason':'CLOUD_OBSERVER_FAILED'})
    finally:
        if client:
            stop.set()
            try:client.disconnect();client.loop_stop()
            except Exception:r['client_close_error']=True
        if tunnel:
            tunnel.terminate()
            try:tunnel.wait(timeout=5)
            except subprocess.TimeoutExpired:tunnel.kill();tunnel.wait(timeout=5)
        tunnel_log.close();network_log.close();g.save(root/'cloud-receipt-private.json',r)
    return r


def run(a,root,bundle,stop,shared):return asyncio.run(observe(a,root,bundle,stop,shared))
