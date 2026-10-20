"""真实Node-A/CANopen字节经过真实Gateway Adapter/JSON，再进入真实Hub和AI事实层。"""
import json,subprocess,sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT/'cloud/backend'))


def test_node_a_completion_wire_reaches_backend_and_ai(tmp_path):
    run=subprocess.run([sys.executable,str(ROOT/'node-a/tests/run_host.py'),'--phase','h3-r2-wire'],capture_output=True,text=True)
    assert run.returncode==0,run.stdout+run.stderr
    trace=subprocess.run([str(ROOT/'node-a/build/host.exe'),'--wire'],capture_output=True)
    assert trace.returncode==0
    here=ROOT/'gateway/physical_can';co=ROOT/'gateway/canopen';vendor=ROOT/'gateway/third_party/CANopenNode'
    sources=[here/'src/stack.c',here/'src/adapter.c',co/'src/mp_can_driver.c',co/'src/mp_od.c',ROOT/'gateway/data_model/model.c',ROOT/'gateway/storage/router.c',vendor/'CANopen.c',*sorted((vendor/'301').glob('*.c')),here/'tests/wire.c']
    command=['gcc','-std=c11','-O1','-DCO_MULTIPLE_OD','-DMP_H3_TEST_SOURCE','-I'+str(here/'src'),'-I'+str(co/'src'),'-I'+str(vendor),*map(str,sources),'-o',str(tmp_path/'wire.exe')]
    built=subprocess.run(command,capture_output=True,text=True);assert built.returncode==0,built.stderr
    canonical=subprocess.run([str(tmp_path/'wire.exe')],input=trace.stdout,capture_output=True)
    assert canonical.returncode==0,canonical.stderr.decode(errors='replace')
    from app.adapters import decode_mqtt
    from app.hub import Hub
    from cloud.ai.facts import extract
    now=[1800000006.6];hub=Hub(['GW-C-001'],clock=lambda:now[0]);hub.broker_connected=True
    frames=[]
    for line in canonical.stdout.decode().splitlines():
        topic,payload=line.split('\t',1);message=decode_mqtt(topic,payload.encode());hub.ingest(message)
        if message.stream=='NIBP':frames.append(message)
    assert len(frames)>=2 and all(f.source=='MOCK' and f.synthetic and f.validity=='VALID' for f in frames)
    # Node-A夹具在tick0取得一次结果；后续每两秒上报必须保留相同完成UTC。
    assert {f.timestamp for f in frames}=={1800000000000}
    snap=hub.snapshot('GW-C-001');assert snap['nodes']['NODE-B']=='OFFLINE'
    facts=extract(snap,'GW-C-001',int(now[0]*1000));assert next(f for f in facts if f['stream']=='NIBP')['value'] is not None
    # 同一测量收到更高seq也不能续命；保持节点心跳新鲜，单独验证90秒过期。
    now[0]=1800000090.001
    for key,(old,_) in list(hub.current.items()):
        if old.stream in ('GATEWAY_STATUS','NODE_STATUS'):
            hub.ingest(old.model_copy(update={'timestamp':int(now[0]*1000),'seq':old.seq+1}))
    hub.ingest(frames[-1].model_copy(update={'seq':frames[-1].seq+1}))
    expired=hub.snapshot('GW-C-001');f=next(f for f in extract(expired,'GW-C-001',int(now[0]*1000)) if f['stream']=='NIBP')
    assert f['value'] is None and f['validity']=='STALE' and expired['nodes']['NODE-B']=='OFFLINE'
    # 输出是明确合成的协议证据，不作真实采集或Broker实测通过。
    out=ROOT/'gateway/physical_can/evidence/h3-r2'
    (out/'synthetic-node-a-can.txt').write_bytes(trace.stdout)
    (out/'synthetic-gateway-canonical.jsonl').write_bytes(canonical.stdout)
