"""隔离AI功能验证的只读合成快照；Node-B始终离线，不冒充硬件链路验收。"""
import asyncio
import hmac
import os
import time
from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect

app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)
state = {'validity': 'VALID', 'delay': 0}


def snapshot(gateway):
    now = int(time.time()*1000)
    specs = [('SPO2','NODE-A','%',97.0),('PR','NODE-A','bpm',70.0),
             ('NIBP','NODE-A','mmHg',[116.0,75.0]),('HR','NODE-B','bpm',None),
             ('RR','NODE-B','breaths/min',None),('TEMP','NODE-B','degC',None)]
    return dict(type='snapshot',schema_version=1,gateway_id=gateway,gateway_state='ONLINE',
                broker_connected=True,nodes={'NODE-A':'ONLINE','NODE-B':'OFFLINE'},server_time=now,
                streams=[dict(gateway_id=gateway,node_id=node,stream=stream,unit=unit,
                              timestamp=now-100000 if state['validity']=='STALE' else now,
                              session_id='H3_NONPERSONAL_SOFTWARE_FIXTURE',seq=now//100,
                              source='MOCK',synthetic=True,validity='OFFLINE' if node=='NODE-B' else state['validity'],
                              value=value if node=='NODE-A' and state['validity']=='VALID' else None)
                         for stream,node,unit,value in specs])


@app.get('/health')
async def health():return {'mode':'SOFTWARE_FIXTURE_NOT_HARDWARE',**state}


@app.post('/fixture/control')
async def control(request: Request):
    if not hmac.compare_digest(request.headers.get('authorization',''),'Bearer '+os.environ['H3_FIXTURE_TOKEN']):
        from fastapi import HTTPException
        raise HTTPException(401)
    body=await request.json()
    if body.get('validity') in ('VALID','INVALID','STALE'):state['validity']=body['validity']
    if body.get('delay') in (0,4):state['delay']=body['delay']
    return state


@app.websocket('/ws/v1/monitor')
async def monitor(ws:WebSocket):
    await ws.accept()
    try:
        auth=await asyncio.wait_for(ws.receive_json(),2)
        if not hmac.compare_digest(auth.get('token',''),os.environ['H3_FIXTURE_TOKEN']):
            await ws.close(1008);return
        await asyncio.sleep(state['delay'])
        while True:
            await ws.send_json(snapshot(auth['gateway_id']))
            await asyncio.sleep(.5)
    except (WebSocketDisconnect,TimeoutError,RuntimeError):pass
