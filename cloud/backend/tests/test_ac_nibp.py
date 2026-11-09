"""AC-1完成时刻/重启负例：经实际Hub及AI事实层验证，数值均为合成输入。"""
import json,sys
from pathlib import Path
import pytest
from fastapi.testclient import TestClient

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app.adapters import decode_mqtt
from app.hub import Hub
from app.main import create_app
from cloud.ai.facts import extract

GW='GW-C-001';START=1800000000.0


def frame(node,stream,stamp,session='ac-node-a',seq=1,value=None,source='MOCK'):
    suffix='status' if stream=='GATEWAY_STATUS' else f'{node}/status' if stream=='NODE_STATUS' else f'{node}/'+('replay' if source=='REPLAY' else 'telemetry')+'/nibp'
    return decode_mqtt('mpm/v1/'+GW+'/'+suffix,json.dumps(dict(timestamp=int(stamp*1000),session_id=session,
      seq=seq,validity='VALID' if value!='OFFLINE' else 'OFFLINE',source=source,synthetic=True,
      unit='mmHg' if stream=='NIBP' else 'state',value=value)).encode())


def setup():
    now=[START];hub=Hub([GW],clock=lambda:now[0],monotonic=lambda:now[0]);hub.broker_connected=True
    for node,stream,value in [('GATEWAY','GATEWAY_STATUS','ONLINE'),('NODE-A','NODE_STATUS','ONLINE'),('NODE-B','NODE_STATUS','OFFLINE')]:
        hub.ingest(frame(node,stream,now[0],value=value))
    hub.ingest(frame('NODE-A','NIBP',now[0],value=[117,77]))
    return hub,now


def nibp(snapshot):return next(item for item in snapshot['streams'] if item['stream']=='NIBP')


@pytest.mark.parametrize('age,valid',[(89.999,True),(90,False),(90.001,False)])
def test_completion_boundary_with_repeated_seq_and_fresh_status(age,valid):
    hub,now=setup();now[0]+=age
    for node,stream in [('GATEWAY','GATEWAY_STATUS'),('NODE-A','NODE_STATUS')]:
        hub.ingest(frame(node,stream,now[0],seq=2,value='ONLINE'))
    # 重发只提高seq，完成时间不变；Backend/WSS快照与AI必须在同一个边界判龄。
    hub.ingest(frame('NODE-A','NIBP',START,seq=2,value=[117,77]))
    snap=hub.snapshot(GW);item=nibp(snap);fact=extract(snap,GW,int(now[0]*1000))[0]
    assert (item['value'] is not None)==valid and (fact['value'] is not None)==valid
    assert item['timestamp']==int(START*1000) and snap['nodes']['NODE-B']=='OFFLINE'


@pytest.mark.parametrize('restarted',['NODE-A','GATEWAY'])
def test_restart_cannot_reactivate_previous_measurement(restarted):
    hub,now=setup();now[0]+=1
    hub.ingest(frame(restarted,'NODE_STATUS' if restarted=='NODE-A' else 'GATEWAY_STATUS',now[0],session='ac-new-boot',value='ONLINE'))
    snap=hub.snapshot(GW)
    assert nibp(snap)['value'] is None
    assert extract(snap,GW,int(now[0]*1000))[0]['value'] is None
    # 旧会话高seq和REPLAY都不能续活；新会话同数值是真实的新完成事件，可以重新显示。
    hub.ingest(frame('NODE-A','NIBP',START,seq=9,value=[117,77]))
    hub.ingest(frame('NODE-A','NIBP',START,seq=10,value=[117,77],source='REPLAY'))
    assert nibp(hub.snapshot(GW))['value'] is None
    hub.ingest(frame('NODE-A','NODE_STATUS',now[0],session='ac-new-boot',seq=2,value='ONLINE'))
    hub.ingest(frame('NODE-A','NIBP',now[0],session='ac-new-boot',seq=1,value=[117,77]))
    assert nibp(hub.snapshot(GW))['value']==[117,77]


def test_actual_wss_does_not_publish_previous_boot_nibp(monkeypatch):
    token='ac-local-synthetic-readonly-'+'x'*32
    monkeypatch.setenv('MONITOR_TESTING','1');monkeypatch.delenv('MONITOR_MQTT_CONFIG',raising=False)
    monkeypatch.setenv('MONITOR_VIEW_TOKEN',token);monkeypatch.setenv('MONITOR_ALLOWED_ORIGINS','http://testserver')
    app=create_app()
    with TestClient(app) as client:
        hub,now=setup();now[0]+=1
        hub.ingest(frame('NODE-A','NODE_STATUS',now[0],session='ac-new-boot',value='ONLINE'));app.state.hub=hub
        with client.websocket_connect('/ws/v1/monitor',headers={'origin':'http://testserver'}) as ws:
            ws.send_json({'token':token,'gateway_id':GW});snap=ws.receive_json()
            assert nibp(snap)['value'] is None and snap['nodes']['NODE-B']=='OFFLINE'
