"""仅本地显示夹具：已通过Broker/WSS的实际快照→真实Backend/WSS→七页UI；不再联网Broker。"""
from pathlib import Path
import json
import os
import sys
import asyncio
import uuid
from contextlib import asynccontextmanager
from unittest.mock import patch
import uvicorn
from fastapi import FastAPI
from b5_local_broker import free_port
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'cloud/backend'))
from app.main import create_app
from app.adapters import decode_mqtt


def main():
    private=Path(json.loads((ROOT/'node-b/build/b5-private-pointer.json').read_text())['base'])
    prior=Path(json.loads((ROOT/'node-b/build/b5-local-latest.json').read_text())['out'])
    assert json.loads((prior/'result.json').read_text())['status']=='PASS'
    cert,key=prior/'broker/loopback.crt',prior/'broker/loopback.key'
    port=free_port();origin=f'https://127.0.0.1:{port}';token='synthetic-b5-browser-'+uuid.uuid4().hex
    env={'MONITOR_TESTING':'1','MONITOR_GATEWAY_IDS':'GW-B5-001','MONITOR_VIEW_TOKEN':token,
         'MONITOR_ALLOWED_ORIGINS':origin,'MONITOR_WEB_DIR':str(ROOT/'cloud/web/dist'),'MONITOR_MQTT_CONFIG':''}
    with patch.dict(os.environ,env):
        backend=create_app()
        @asynccontextmanager
        async def lifespan(outer):
            async with backend.router.lifespan_context(backend):
                async def seed(label):
                    snap=json.loads((private/(label+'-WSS-snapshot-private.json')).read_text(encoding='utf-8'))
                    hub=backend.state.hub;hub.current.clear();hub.current_generation.clear();hub.gateway_generation.clear()
                    hub.clock=lambda:snap['server_time']/1000;hub.monotonic=hub.clock;hub.broker_connected=True
                    stamp=snap['server_time'];session=next(s['session_id'] for s in snap['streams'])
                    body={'timestamp':stamp,'seq':1,'session_id':session,'validity':'VALID','source':'MOCK','synthetic':True,'unit':'state','value':'ONLINE'}
                    for suffix in ('status','NODE-B/status'):hub.ingest(decode_mqtt('mpm/v1/GW-B5-001/'+suffix,json.dumps(body).encode()))
                    for s in snap['streams']:
                        body={k:v for k,v in s.items() if k not in ('gateway_id','node_id','stream')}
                        hub.ingest(decode_mqtt('mpm/v1/GW-B5-001/NODE-B/telemetry/'+s['stream'].lower(),json.dumps(body).encode()))
                await seed('ECG')
                access={'origin':origin,'url':origin+'/medical-monitor/?gateway=GW-B5-001','token':token,'source':'ACTUAL_WSS_SNAPSHOTS_WITH_CONTROLLED_CLOCK_NOT_NEW_MEASUREMENT'}
                (ROOT/'node-b/build/b5-browser-access.json').write_text(json.dumps(access)+'\n',encoding='utf-8')
                async def control():
                    last='ECG'
                    until=asyncio.get_running_loop().time()+600
                    while True:
                        if asyncio.get_running_loop().time()>=until:server.should_exit=True;return
                        control=ROOT/'node-b/build/b5-browser-control.txt'
                        if control.exists():
                            label=control.read_text().strip()
                            if label in ('ECG','RR') and label!=last:await seed(label);last=label
                            if label=='STOP':server.should_exit=True;return
                        await asyncio.sleep(.1)
                task=asyncio.create_task(control())
                try:yield
                finally:task.cancel();await asyncio.gather(task,return_exceptions=True)
        outer=FastAPI(lifespan=lifespan);outer.mount('/medical-monitor',backend)
        server=uvicorn.Server(uvicorn.Config(outer,host='127.0.0.1',port=port,ssl_keyfile=str(key),ssl_certfile=str(cert),log_level='warning'))
        print('B5_BROWSER_LOOPBACK_FIXTURE_START',flush=True);server.run()
    return 0


if __name__=='__main__':raise SystemExit(main())
