"""本机真实Backend Hub/鉴权/WSS，只有显式MOCK生产者，不连接任何Broker。"""
import asyncio
from contextlib import asynccontextmanager
import json
from pathlib import Path
import sys
import time
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'backend'))
from app.main import create_app
from app.models import Telemetry
from fastapi import Request

app=create_app()
state={'seq':0,'nibp_completed':None,'probe':True,'phase':'unmeasured','synthetic':True}
original=app.router.lifespan_context


@asynccontextmanager
async def life(application):
    async with original(application):
        hub=application.state.hub;hub.broker_connected=True
        async def pump():
            while True:
                now=int(time.time()*1000);state['seq']+=1
                def emit(node,stream,unit,value,validity='VALID',stamp=None,**extra):
                    hub.ingest(Telemetry(gateway_id='GW-C-001',node_id=node,stream=stream,unit=unit,value=value,
                        timestamp=now if stamp is None else stamp,seq=state['seq'],session_id='r2-explicit-synthetic',
                        validity=validity,source='MOCK',synthetic=True,**extra))
                emit('GATEWAY','GATEWAY_STATUS','state','ONLINE')
                emit('NODE-A','NODE_STATUS','state','ONLINE')
                emit('NODE-B','NODE_STATUS','state','OFFLINE','OFFLINE')
                for stream,value,unit in [('SPO2',97,'%'),('PR',73,'bpm')]:
                    emit('NODE-A',stream,unit,value if state['probe'] else None,'VALID' if state['probe'] else 'INVALID')
                completed=state['nibp_completed'];valid=completed is not None and state['phase']=='measured'
                # 同一次完成的timestamp固定；持续到达的新seq不能续期，故意让Hub独立执行90秒门禁。
                emit('NODE-A','NIBP','mmHg',[123,81] if valid else None,
                     'VALID' if valid else 'INVALID',completed if valid else now)
                await asyncio.sleep(.25)
        task=asyncio.create_task(pump())
        try:yield
        finally:
            task.cancel();await asyncio.gather(task,return_exceptions=True)
app.router.lifespan_context=life


@app.post('/fixture/control')
async def control(request:Request):
    body=await request.json()
    if body.get('phase')=='measured':state.update(phase='measured',nibp_completed=int(time.time()*1000))
    if body.get('phase')=='aborted':state['phase']='aborted'
    if type(body.get('probe')) is bool:state['probe']=body['probe']
    return {'phase':state['phase'],'synthetic':True,'completion_timestamp':state['nibp_completed']}


@app.get('/fixture/state')
async def stats():
    snap=app.state.hub.snapshot('GW-C-001')
    return {'phase':state['phase'],'synthetic':True,'accepted':app.state.hub.accepted,
        'subscribers':len(app.state.hub.subscribers),'node_b':snap['nodes']['NODE-B'],
        'nibp_validity':next((f['validity'] for f in snap['streams'] if f['stream']=='NIBP'),'MISSING'),
        'completion_timestamp':state['nibp_completed']}
