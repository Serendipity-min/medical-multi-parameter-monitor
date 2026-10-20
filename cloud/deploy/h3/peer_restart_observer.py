"""只读隔离WSS核对A重启；只存状态/会话/序列元数据，不保存生理值。"""
import asyncio
from datetime import datetime,timezone
import json
import time
from cloud.deploy.h3.isolated_server import STATE,load_env


async def observe(seconds=600):
    from websockets.asyncio.client import connect
    env=load_env(STATE/'backend.env')
    result={'action':'ACTUAL_NODE_A_POWER_CYCLE_WSS','started_utc':datetime.now(timezone.utc).isoformat(),
            'baseline_online':False,'node_a_offline_seen':False,'new_session_recovered':False,
            'node_b_not_offline':0,'invalid_values_visible':0,'gateway_unavailable_after_baseline':0,
            'transitions':[],'raw_measurements_saved':False,'exit_code':1}
    target=STATE/('peer-restart-'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')+'.json')
    started=time.monotonic();before=set();previous=None;recovered_at=None
    async with connect('ws://127.0.0.1:18775/ws/v1/monitor',origin='http://127.0.0.1:18767') as ws:
        await ws.send(json.dumps({'token':env['MONITOR_VIEW_TOKEN'],'gateway_id':'GW-C-001'}))
        while time.monotonic()-started<seconds:
            data=json.loads(await asyncio.wait_for(ws.recv(),3));nodes=data['nodes'];streams=data['streams']
            sessions={s['session_id'] for s in streams if s['node_id']=='NODE-A' and s['source']!='REPLAY'}
            if nodes.get('NODE-B')!='OFFLINE':result['node_b_not_offline']+=1
            for s in streams:
                if s['validity']!='VALID' and (s.get('value') is not None or s.get('samples')):
                    result['invalid_values_visible']+=1
            online=data['gateway_state']=='ONLINE' and nodes.get('NODE-A')=='ONLINE'
            if online and sessions and not result['baseline_online']:
                result['baseline_online']=True;before=sessions
            elif result['baseline_online']:
                if data['gateway_state']!='ONLINE':result['gateway_unavailable_after_baseline']+=1
                if nodes.get('NODE-A')=='OFFLINE':result['node_a_offline_seen']=True
                # 必须有故障后新会话，不能把一次ONLINE状态包或旧读数当恢复证据。
                if result['node_a_offline_seen'] and online and sessions-before:
                    result['new_session_recovered']=True
                    if recovered_at is None:recovered_at=time.monotonic()
            state={'gateway':data['gateway_state'],'nodes':nodes,'sessions':sorted(sessions),
                   'validities':{s['stream']:s['validity'] for s in streams}}
            if state!=previous:
                result['transitions'].append({'elapsed_s':round(time.monotonic()-started,3),**state});previous=state
            result['elapsed_s']=round(time.monotonic()-started,3)
            target.write_text(json.dumps(result,indent=2))
            # 恢复后继续观察20秒，确认不会再次锁止或复活旧会话。
            if recovered_at is not None and time.monotonic()-recovered_at>=20:break
    result['exit_code']=int(not result['new_session_recovered'] or any(result[k] for k in
        ('node_b_not_offline','invalid_values_visible','gateway_unavailable_after_baseline')))
    result['finished_utc']=datetime.now(timezone.utc).isoformat();target.write_text(json.dumps(result,indent=2))
    return result


if __name__=='__main__':
    try:
        result=asyncio.run(observe());print(json.dumps(result));raise SystemExit(result['exit_code'])
    except Exception as exc:
        print(json.dumps({'exit_code':1,'failure_type':type(exc).__name__,'details_suppressed':True}));raise SystemExit(1)
