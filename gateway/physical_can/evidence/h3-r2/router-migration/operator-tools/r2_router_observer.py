# 路由器窗口使用独立引用及证据目录，保留此前热点原始记录。
"""C独立冷启动的被动MQTT/WSS观察：仅计数/身份/状态，不保存生理值或原始波形。"""
from pathlib import Path
import inspect,json,subprocess,sys
ROOT=Path(__file__).resolve().parents[3]


def remote_observe(tag):
    import asyncio,hashlib,json,os,pwd,threading,time,urllib.request
    from collections import Counter
    from datetime import datetime,timezone
    from pathlib import Path
    import sys
    runtime=Path('/opt/medical-monitor-h3/releases/runtime-37808287a557');sys.path.insert(0,str(runtime))
    from cloud.deploy.h3.isolated_server import load_env
    from cloud.backend.app.mqtt_adapter import configured_client
    from cloud.backend.app.adapters import decode_mqtt
    from websockets.asyncio.client import connect
    state=Path('/var/lib/medical-monitor-p6/h3-20261019')
    owned=state/('r2c-'+tag);config=json.loads((owned/'backend.json').read_text());env=load_env(owned/'backend.env')
    if config.get('port')!=8884 or config.get('username')!='h3-backend':raise RuntimeError('ISOLATED_READONLY_ONLY')
    # 此用户的8884到原Broker地址已被临时NAT转回环；先读凭据再降权，不扩大公网放行。
    user=pwd.getpwnam('medical-ai');os.setgid(user.pw_gid);os.setuid(user.pw_uid)
    result={'exit_code':1,'state':'WAITING_FOR_C_AND_A','started_utc':datetime.now(timezone.utc).isoformat(),
        'target_online_s':310,'max_window_s':1800,'source':'ACTUAL_C_FLASH_COLD_BOOT_NO_HOST_NO_PHYSIO',
        'mqtt_received':0,'mqtt_invalid':0,'wss_snapshots':0,'invalid_values_visible':0,'node_b_online_seen':False,
        'real_AI_calls':0,'raw_values_saved':False,'transitions':[],'sessions':[],'metadata_rows':0}
    lock=threading.Lock();subscribed=threading.Event();counts=Counter();qos=Counter();sessions=set();last_state=None
    meta=(owned/'cold-mqtt-metadata.jsonl').open('x')
    def save():
        with lock:
            result['mqtt_stream_counts']=dict(counts);result['mqtt_qos_counts']={str(k):v for k,v in qos.items()}
            body=json.dumps(result)
        p=owned/'cold-status.tmp';p.write_text(body);p.replace(owned/'cold-status.json')
    client=configured_client(config,'h3-r2c-cold-observer-'+tag)
    def on_connect(c,_u,_f,reason,_props):
        result['mqtt_connack']=reason.value
        if not reason.is_failure:c.subscribe('mpm/v1/GW-C-001/#',qos=1)
    def on_subscribe(*args):subscribed.set()
    def on_message(_c,_u,message):
        try:
            frame=decode_mqtt(message.topic,message.payload);data=json.loads(message.payload)
            row={k:data.get(k) for k in ('session_id','seq','timestamp','validity','source','synthetic')}
            row.update(node_id=frame.node_id,stream=frame.stream,qos=message.qos,wire_sha256=hashlib.sha256(message.payload).hexdigest(),received_utc=datetime.now(timezone.utc).isoformat())
            with lock:
                result['mqtt_received']+=1;counts[frame.node_id+':'+frame.stream]+=1;qos[message.qos]+=1
                if frame.node_id=='NODE-B' and data.get('value')=='ONLINE':result['node_b_online_seen']=True
                meta.write(json.dumps(row)+'\n');meta.flush();result['metadata_rows']+=1
        except Exception:
            with lock:result['mqtt_invalid']+=1
    client.on_connect=on_connect;client.on_subscribe=on_subscribe;client.on_message=on_message
    def health():
        with urllib.request.urlopen('http://127.0.0.1:18775/health',timeout=2) as response:return json.load(response)
    async def observe():
        nonlocal last_state
        started=time.monotonic();online_at=None;longest=0.;last_report=0.
        result['backend_health_before']=health()
        client.connect(config['host'],8884,keepalive=15);client.loop_start()
        if not await asyncio.to_thread(subscribed.wait,10):raise RuntimeError('OBSERVER_SUBACK_TIMEOUT')
        result['observer_ready']=True;save();print(json.dumps({'state':'OBSERVER_READY_WAITING_FOR_C','mqtt_subscribed':True}),flush=True)
        async with connect('ws://127.0.0.1:18775/ws/v1/monitor',origin='http://127.0.0.1:18767') as ws:
            await ws.send(json.dumps({'token':env['MONITOR_VIEW_TOKEN'],'gateway_id':'GW-C-001'}))
            while time.monotonic()-started<1800:
                data=json.loads(await asyncio.wait_for(ws.recv(),4));now=time.monotonic();result['wss_snapshots']+=1
                state_now=(data['gateway_state'],data['nodes'].get('NODE-A'),data['nodes'].get('NODE-B'))
                if state_now!=last_state:
                    result['transitions'].append({'elapsed_s':round(now-started,3),'gateway':state_now[0],'a':state_now[1],'b':state_now[2]});last_state=state_now
                if state_now[2]=='ONLINE':result['node_b_online_seen']=True
                for stream in data['streams']:
                    if stream.get('session_id'):sessions.add(stream['session_id'])
                    if stream['validity']!='VALID' and (stream.get('value') is not None or stream.get('samples')):result['invalid_values_visible']+=1
                good=state_now==('ONLINE','ONLINE','OFFLINE') and not result['node_b_online_seen'] and not result['invalid_values_visible']
                if good:
                    if online_at is None:online_at=now
                    longest=max(longest,now-online_at);result['state']='CONTINUOUS_ONLINE_OBSERVATION'
                else:
                    if online_at is not None:result['online_interruptions']=result.get('online_interruptions',0)+1
                    online_at=None
                result.update(elapsed_s=round(now-started,3),continuous_online_s=round(now-online_at,3) if online_at else 0,
                    longest_online_s=round(longest,3),sessions=sorted(sessions),updated_utc=datetime.now(timezone.utc).isoformat())
                if now-last_report>=2:save();last_report=now
                if result['node_b_online_seen'] or result['invalid_values_visible']:raise RuntimeError('STATE_OR_INVALID_VALUE_VIOLATION')
                if online_at and now-online_at>=310:
                    result['backend_health_after']=health()
                    before=result['backend_health_before'];after=result['backend_health_after']
                    result['backend_accepted_delta']=after['accepted']-before['accepted']
                    result['backend_rejected_delta']=after['rejected']-before['rejected']
                    result['backend_dropped_delta']=after['dropped']-before['dropped']
                    result['exit_code']=int(result['mqtt_invalid']!=0 or result['backend_rejected_delta']!=0 or result['backend_dropped_delta']!=0 or not result['mqtt_received'])
                    result['state']='COLD_BOOT_CLOUD_WINDOW_PASS' if result['exit_code']==0 else 'COLD_BOOT_CLOUD_WINDOW_FAIL'
                    break
            else:result['state']='WAIT_OR_CONTINUITY_TIMEOUT'
    try:asyncio.run(observe())
    except Exception as exc:result.update(failure_type=type(exc).__name__,state='OBSERVER_FAILED',failure_code=str(exc) if type(exc) is RuntimeError else 'DETAILS_SUPPRESSED')
    finally:
        client.disconnect();client.loop_stop();meta.close();save()
    return result


if __name__=='__main__':
    ref=json.loads(Path('E:/medical-monitor-h3-private/r2-router-active-window-reference.json').read_text());tag=ref['isolation_tag']
    code='import json\n'+inspect.getsource(remote_observe)+'\nr=remote_observe('+repr(tag)+')\nprint(json.dumps(r),flush=True)\nraise SystemExit(r["exit_code"])\n'
    p=subprocess.Popen(['ssh','tencent-codex','sudo -n /opt/medical-monitor-p6/.venv/bin/python -'],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
    p.stdin.write(code);p.stdin.close()
    lines=[]
    for line in p.stdout:
        lines.append(line);print(line.rstrip(),flush=True)
    err=p.stderr.read();status=p.wait()
    # 保存本程序输出的JSON元数据；SSH/第三方stderr不落公开日志。
    out=ROOT/'gateway/physical_can/evidence/h3-r2/router-migration'
    with (out/'cold-observer.log').open('x') as f:f.write(''.join(lines))
    try:result=json.loads(lines[-1])
    except (ValueError,IndexError):result={'exit_code':status or 1,'failure_code':'OBSERVER_STDERR_SUPPRESSED','stderr_present':bool(err)}
    with (out/'cold-observer-result.json').open('x') as f:json.dump(result,f,indent=2)
    raise SystemExit(status or result['exit_code'])
