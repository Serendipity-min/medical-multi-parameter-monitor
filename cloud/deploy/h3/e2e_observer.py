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


def save_status(result,out):
    # 每个观测仅写自身状态；取消跨会话共享文件，避免并发replace争用/混淆结果。
    own=out/'status.json';temporary=out/'status.tmp'
    body=json.dumps(result,indent=2)
    temporary.write_text(body);temporary.replace(own)


def active_ppg(snapshot):
    # 合同活跃负载门禁要求真实新PPG持续到达；标量质量INVALID不能伪改VALID。
    # 仍按既有5秒时效，缺席B必须明确OFFLINE；三流全VALID的旧指标另行保留。
    ppg=next((s for s in snapshot['streams'] if s['stream']=='PPG'),{})
    age=snapshot['server_time']-ppg.get('timestamp',0)
    return (snapshot['gateway_state']=='ONLINE' and snapshot['nodes'].get('NODE-A')=='ONLINE'
            and snapshot['nodes'].get('NODE-B')=='OFFLINE' and ppg.get('validity')=='VALID'
            and ppg.get('source')=='MOCK' and ppg.get('synthetic') is True
            and 0<=age<=5000 and bool(ppg.get('samples')))


async def observe(seconds,criterion='all-three-valid'):
    from websockets.asyncio.client import connect
    config=json.loads((STATE/'backend.json').read_text());env=load_env(STATE/'backend.env')
    if config['port']!=8884 or config['username']!='h3-backend':raise ValueError('ISOLATED_ONLY')
    stamp=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    out=STATE/('e2e-'+stamp);out.mkdir(mode=0o700)
    result={'source':'ACTUAL_ISOLATED_MQTT_WSS_OBSERVATION_NOT_CLINICAL_ACCURACY',
            'started_utc':datetime.now(timezone.utc).isoformat(),'target_seconds':seconds,
            'mqtt_received':0,'mqtt_invalid':0,'mqtt_qos':{},'wss_snapshots':0,
            'matched_valid_streams':{},'value_mismatches':0,'node_b_online_seen':False,
            'unexpected_node_a_source':0,'active_ranges':[],'raw_measurements_saved':False,'exit_code':1,
            'criterion':criterion,'longest_active_ppg_s':0,'invalid_values_visible':0,'node_b_not_offline':0,
            'validity_observations':{},'active_ppg_ranges':[]}
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
    ppg_active=None;ppg_last=None;ppg_best=0.0;validities=Counter()
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
                if snapshot.get('nodes',{}).get('NODE-B')!='OFFLINE':result['node_b_not_offline']+=1
                for stream in snapshot['streams']:
                    validities[stream['stream']+':'+stream['validity']]+=1
                    if stream['validity']!='VALID' and (stream.get('value') is not None or stream.get('samples')):
                        result['invalid_values_visible']+=1
                if active_ppg(snapshot):
                    if ppg_active is None:ppg_active=now
                    ppg_last=now;ppg_best=max(ppg_best,now-ppg_active)
                elif ppg_active is not None:
                    result['active_ppg_ranges'].append({'seconds':round(ppg_last-ppg_active,3)})
                    ppg_active=None
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
                                  longest_active_ppg_s=round(ppg_best,3),validity_observations=dict(validities),
                                  mqtt_stream_counts=dict(received),matched_valid_streams=dict(matched),mqtt_qos=dict(qos))
                    save_status(result,out)
                if result['value_mismatches'] or result['node_b_online_seen'] or result['unexpected_node_a_source']:break
        if active is not None:result['active_ranges'].append({'seconds':round(active_last-active,3)})
        if ppg_active is not None:result['active_ppg_ranges'].append({'seconds':round(ppg_last-ppg_active,3)})
        result['backend_health_after']=httpx.get('http://127.0.0.1:18775/health',trust_env=False).json()
        shared_failure=(result['mqtt_invalid']>0 or result['value_mismatches']>0 or result['node_b_online_seen']
                        or result['unexpected_node_a_source']>0 or result['backend_health_after']['dropped']>0
                        or result['invalid_values_visible']>0 or result['node_b_not_offline']>0
                        or result['backend_health_after']['rejected']>result['backend_health_before']['rejected'])
        result['all_three_valid_exit_code']=int(best<300 or shared_failure)
        # 活跃PPG路径还须实际核对过有效SpO2/PR；不能用空闲/纯无效窗口代替。
        result['active_ppg_exit_code']=int(ppg_best<300 or shared_failure
            or any(matched[name]==0 for name in ('PPG','SPO2','PR')))
        result['exit_code']=result['active_ppg_exit_code'] if criterion=='active-ppg' else result['all_three_valid_exit_code']
    finally:
        c.disconnect();c.loop_stop();meta.close();wss_meta.close()
        result['finished_utc']=datetime.now(timezone.utc).isoformat()
        (out/'result.json').write_text(json.dumps(result,indent=2));save_status(result,out)
    return result


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--seconds',type=int,default=420)
    parser.add_argument('--criterion',choices=('all-three-valid','active-ppg'),default='all-three-valid');args=parser.parse_args()
    if not 300<=args.seconds<=1800:parser.error('range 300..1800')
    try:
        result=asyncio.run(observe(args.seconds,args.criterion));print(json.dumps(result,indent=2));raise SystemExit(result['exit_code'])
    except Exception as exc:
        print(json.dumps({'failure_type':type(exc).__name__,'details_suppressed':True}));raise SystemExit(1)
