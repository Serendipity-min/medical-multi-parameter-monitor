"""无采集输入的隔离链路观察；不以INVALID标量冒充生理采集验收。"""
import asyncio
from collections import Counter
from datetime import datetime,timezone
import json
import time
from cloud.deploy.h3.isolated_server import STATE,load_env


async def observe(seconds=320):
    from websockets.asyncio.client import connect
    if not 30<=seconds<=1200:raise ValueError('BOUNDED_OBSERVATION_REQUIRED')
    env=load_env(STATE/'backend.env');states=Counter();a=Counter();b=Counter();bad=0;snapshots=0
    started=time.monotonic();first=None;last=None;sessions=set()
    async with connect('ws://127.0.0.1:18775/ws/v1/monitor',origin='http://127.0.0.1:18767') as ws:
        await ws.send(json.dumps({'token':env['MONITOR_VIEW_TOKEN'],'gateway_id':'GW-C-001'}))
        while time.monotonic()-started<seconds:
            data=json.loads(await asyncio.wait_for(ws.recv(),3));snapshots+=1
            now=time.monotonic()
            if first is None:first=now
            last=now
            states[data['gateway_state']]+=1;a[data['nodes'].get('NODE-A')]+=1;b[data['nodes'].get('NODE-B')]+=1
            for stream in data['streams']:
                # 只记录状态/会话；原始值和波形即使出现也不落盘。
                if stream['validity']!='VALID' and (stream.get('value') is not None or stream.get('samples')):bad+=1
                if stream['node_id']=='NODE-A':sessions.add(stream['session_id'])
    result={'source':'ACTUAL_ISOLATED_WSS_NO_PHYSIO_INPUT','gateway_states':dict(states),
        'node_a_states':dict(a),'node_b_states':dict(b),'invalid_values_visible':bad,
        'snapshots':snapshots,'observed_s':round(last-first,3) if last is not None else 0,
        'elapsed_s':round(time.monotonic()-started,3),'sessions':sorted(sessions),
        'finished_utc':datetime.now(timezone.utc).isoformat(),'raw_values_saved':False}
    result['exit_code']=int(not snapshots or set(states)!={'ONLINE'} or set(a)!={'ONLINE'} or set(b)!={'OFFLINE'} or bad!=0)
    return result


if __name__=='__main__':
    result=asyncio.run(observe());print(json.dumps(result));raise SystemExit(result['exit_code'])
