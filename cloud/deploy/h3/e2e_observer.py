"""只读隔离MQTT/WSS逐层核对，原始读数/波形不落盘，不把软件夹具当硬件验收。"""
import argparse
import asyncio
from collections import Counter
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path
import ssl
import sys
import threading
import time

ROOT=Path(__file__).resolve().parents[3];sys.path.insert(0,str(ROOT))
from cloud.backend.app.mqtt_adapter import configured_client
from cloud.backend.app.adapters import decode_mqtt
from cloud.deploy.h3.isolated_server import STATE,load_env


async def observe(seconds):
    from websockets.asyncio.client import connect
    config=json.loads((STATE/'backend.json').read_text());env=load_env(STATE/'backend.env')
    if config['port']!=8884 or config['username']!='h3-backend':raise ValueError('ISOLATED_ONLY')
    stamp=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    out=STATE/('e2e-'+stamp);out.mkdir(mode=0o700)
    result={'source':'ACTUAL_ISOLATED_MQTT_WSS_OBSERVATION_NOT_CLINICAL_ACCURACY',
            'started_utc':datetime.now(timezone.utc).isoformat(),'target_seconds':seconds,
            'mqtt_received':0,'mqtt_invalid':0,'mqtt_qos':{},'wss_snapshots':0,
            'matched_valid_streams':{},'value_mismatches':0,'node_b_online_seen':False,
            'unexpected_node_a_source':0,'active_ranges':[],'raw_measurements_saved':False,'exit_code':1}
    latest={};lock=threading.Lock();ready=threading.Event();received=Counter();matched=Counter();qos=Counter();wss_last={}
    meta=(out/'mqtt-metadata.jsonl').open('x',encoding='utf-8')
    wss_meta=(out/'wss-metadata.jsonl').open('x',encoding='utf-8')
    c=configured_client(config,'h3-e2e-observer-'+stamp)

    def on_connect(client,_u,_flags,reason,_props):
        result['mqtt_connack']=reason.value
        if not reason.is_failure:client.subscribe('mpm/v1/GW-C-001/#',qos=1)
    def on_subscribe(*args):ready.set()
    def on_message(_c,_u,message):
        try:
            frame=decode_mqtt(message.topic,message.payload)
            data=json.loads(message.payload)
            # 状态与事件同样核对来源，但只在内存保留最新值用于WSS匹配。
            row={k:data.get(k) for k in ('session_id','seq','timestamp','validity','source','synthetic')}
            row.update(topic=message.topic,wire_sha256=hashlib.sha256(message.payload).hexdigest(),qos=message.qos,
                       received_utc=datetime.now(timezone.utc).isoformat(),node_id=frame.node_id,stream=frame.stream)
            with lock:
                result['mqtt_received']+=1;qos[message.qos]+=1;received[frame.stream]+=1
                latest[(frame.node_id,frame.stream)]=data
                if frame.node_id=='NODE-B' and data.get('value')=='ONLINE':result['node_b_online_seen']=True
                if frame.node_id=='NODE-A' and (data.get('source') not in ('MOCK','REPLAY') or not data.get('synthetic')):result['unexpected_node_a_source']+=1
                meta.write(json.dumps(row)+'\n');meta.flush()
        except Exception:
            with lock:result['mqtt_invalid']+=1
    c.on_connect=on_connect;c.on_subscribe=on_subscribe;c.on_message=on_message
    started=time.monotonic();active=None;active_last=None;best=0.0
    try:
        import httpx
        result['backend_health_before']=httpx.get('http://127.0.0.1:18775/health',trust_env=False).json()
        c.connect(config['host'],8884);c.loop_start()
        if not await asyncio.to_thread(ready.wait,8):raise RuntimeError('MQTT_SUBACK_TIMEOUT')
        async with connect('ws://127.0.0.1:18775/ws/v1/monitor',origin='http://127.0.0.1:18767',max_size=65536) as ws:
            await ws.send(json.dumps({'token':env['MONITOR_VIEW_TOKEN'],'gateway_id':'GW-C-001'}))
            while time.monotonic()-started<seconds:
                snapshot=json.loads(await asyncio.wait_for(ws.recv(),3))
                if snapshot['gateway_id']!='GW-C-001':raise ValueError('WSS_GATEWAY_MISMATCH')
                if abs(int(time.time()*1000)-snapshot['server_time'])>2000:raise ValueError('BACKEND_TIME_MISMATCH')
                result['wss_snapshots']+=1
                if snapshot.get('nodes',{}).get('NODE-B')=='ONLINE':result['node_b_online_seen']=True
                streams={s['stream']:s for s in snapshot['streams']}
                good=snapshot['gateway_state']=='ONLINE' and snapshot.get('nodes',{}).get('NODE-A')=='ONLINE'
                for name in ('PPG','SPO2','PR'):
                    s=streams.get(name,{})
                    good=good and s.get('validity')=='VALID' and s.get('source')=='MOCK' and s.get('synthetic') is True
                now=time.monotonic()
                if good:
                    if active is None:active=now;active_last=now
                    active_last=now;best=max(best,now-active)
                elif active is not None:
                    result['active_ranges'].append({'seconds':round(active_last-active,3)});active=None
                with lock:
                    for s in snapshot['streams']:
                        data=latest.get((s['node_id'],s['stream']))
                        signature=tuple(s.get(k) for k in ('session_id','seq','timestamp','validity','source','synthetic'))
                        if wss_last.get(s['stream'])!=signature:
                            wss_last[s['stream']]=signature
                            row={k:s.get(k) for k in ('stream','node_id','session_id','seq','timestamp','validity','source','synthetic')}
                            row.update(server_time=snapshot['server_time'],nodes=snapshot['nodes'])
                            wss_meta.write(json.dumps(row)+'\n');wss_meta.flush()
                        if not data or s.get('validity')!='VALID' or data.get('validity')!='VALID':continue
                        if any(s.get(k)!=data.get(k) for k in ('session_id','seq','timestamp')):continue
                        same=s.get('value')==data.get('value') and s.get('source')==data.get('source') and s.get('synthetic')==data.get('synthetic')
                        if s['stream'] in ('PPG','ECG','RESP'):same=same and s.get('samples')==data.get('samples')
                        if same:matched[s['stream']]+=1
                        else:result['value_mismatches']+=1
                    result.update(elapsed_s=round(now-started,3),longest_active_s=round(best,3),
                                  mqtt_stream_counts=dict(received),matched_valid_streams=dict(matched),mqtt_qos=dict(qos))
                    status=STATE/'e2e-status.json';tmp=status.with_suffix('.tmp')
                    tmp.write_text(json.dumps(result,indent=2));tmp.replace(status)
                if result['value_mismatches'] or result['node_b_online_seen'] or result['unexpected_node_a_source']:break
        if active is not None:result['active_ranges'].append({'seconds':round(active_last-active,3)})
        result['backend_health_after']=httpx.get('http://127.0.0.1:18775/health',trust_env=False).json()
        result['exit_code']=int(best<300 or result['mqtt_invalid']>0 or result['value_mismatches']>0 or result['node_b_online_seen'] or result['unexpected_node_a_source']>0 or result['backend_health_after']['dropped']>0)
    finally:
        c.disconnect();c.loop_stop();meta.close();wss_meta.close()
        result['finished_utc']=datetime.now(timezone.utc).isoformat()
        (out/'result.json').write_text(json.dumps(result,indent=2));(STATE/'e2e-status.json').write_text(json.dumps(result,indent=2))
    return result


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--seconds',type=int,default=420);args=parser.parse_args()
    if not 300<=args.seconds<=1800:parser.error('range 300..1800')
    try:
        result=asyncio.run(observe(args.seconds));print(json.dumps(result,indent=2));raise SystemExit(result['exit_code'])
    except Exception as exc:
        print(json.dumps({'failure_type':type(exc).__name__,'details_suppressed':True}));raise SystemExit(1)
