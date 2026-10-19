"""Node-A 实际 Host CAN 帧→候选 RPDO/Router→coreMQTT→隔离 Broker→原 Backend。"""
import argparse
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import hashlib
from datetime import datetime, timezone
ROOT=Path(__file__).resolve().parents[3]
HERE=ROOT/'gateway/physical_can'
parser=argparse.ArgumentParser();parser.add_argument('--runtime',type=Path,required=True);args=parser.parse_args()
if sys.platform=='win32':
    linux=lambda p:'/mnt/'+p.resolve().drive[0].lower()+p.resolve().as_posix()[2:]
    raise SystemExit(subprocess.call(['wsl','-d','HERA-C3','--cd',linux(ROOT),'--','python3','gateway/physical_can/tests/run_wire_broker.py','--runtime',linux(args.runtime)]))
spec=importlib.util.spec_from_file_location('ordinary_broker',ROOT/'gateway/mqtt/tests/run_broker_integration.py');ordinary=importlib.util.module_from_spec(spec);spec.loader.exec_module(ordinary)
sys.path.insert(0,str(ROOT/'cloud/backend'))
from app.adapters import decode_mqtt
from app.hub import Hub
out=HERE/'evidence';work=HERE/'build/wire-broker';work.mkdir(parents=True,exist_ok=True)
co=ROOT/'gateway/canopen';core=ROOT/'gateway/third_party/CANopenNode';mqtt=ROOT/'gateway/mqtt';vendor=ROOT/'gateway/third_party/coreMQTT'
sources=[HERE/'src/stack.c',HERE/'src/adapter.c',HERE/'tests/broker_wire.c',co/'src/mp_od.c',co/'src/mp_can_driver.c',ROOT/'gateway/data_model/model.c',ROOT/'gateway/storage/router.c',core/'CANopen.c',*sorted((core/'301').glob('*.c')),mqtt/'src/gateway_transport.c',mqtt/'src/mqtt_transport_adapter.c',vendor/'source/core_mqtt.c',vendor/'source/core_mqtt_serializer.c',vendor/'source/core_mqtt_state.c']
includes=[HERE/'src',co/'src',core,mqtt/'src',mqtt/'tests',vendor/'source/include',vendor/'source/interface']
cmd=['gcc','-std=c11','-O1','-D_POSIX_C_SOURCE=200809L','-DCO_MULTIPLE_OD','-DGATEWAY_MQTT_HOST_TEST',*['-I'+str(p) for p in includes],*map(str,sources),'-o',str(work/'wire_gateway')]
report={'mode':'LOCAL_HOST_SENSOR_STUBS_TO_REAL_STACKS_AND_ISOLATED_BROKER','hardware':'NOT_RUN','ESP_AT_TLS':'NOT_RUN','production_broker':'NOT_ACCESSED','real_patient_data':False,'exit_code':1}
broker=observer=None
try:
    compile=subprocess.run(cmd,capture_output=True);(out/'wire-broker-compile.log').write_bytes(compile.stdout+compile.stderr)
    report['compile_exit']=compile.returncode;assert compile.returncode==0
    # 每次运行使用独立目录，既有证据不删除；Broker 拒绝覆盖旧目录时仍可安全复测。
    run_dir=work/datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    broker=ordinary.Broker(args.runtime,run_dir/'broker')
    observer=ordinary.Observer(broker.port,'physical-wire-observer');assert observer.accepted;observer.subscribe()
    run=subprocess.run([str(work/'wire_gateway'),str(broker.port),str(out/'node-a-can-frames.txt')],capture_output=True,timeout=30)
    (out/'wire-broker-client.log').write_bytes(run.stdout+run.stderr);report['client_exit']=run.returncode;assert run.returncode==0
    result=json.loads(run.stdout);report.update(result);messages=[]
    hub=Hub(['GW-C-001'],clock=lambda:1800000006.6);hub.broker_connected=True
    for _ in range(result['messages']):
        kind,body=ordinary.read_packet(observer.connection)
        assert kind&0xF0==0x30
        length=int.from_bytes(body[:2],'big');topic=body[2:2+length].decode();offset=2+length;qos=(kind>>1)&3
        if qos:
            observer.connection.sendall(ordinary.packet(0x40,body[offset:offset+2]));offset+=2
        payload=body[offset:];item=decode_mqtt(topic,payload);hub.ingest(item)
        if item.node_id=='NODE-B': assert item.stream=='NODE_STATUS' and item.value=='OFFLINE'
        messages.append({'topic':topic,'qos':qos,'payload':json.loads(payload)})
    snapshot=hub.snapshot('GW-C-001')
    assert snapshot['nodes']['NODE-A']=='ONLINE' and snapshot['nodes']['NODE-B']=='OFFLINE'
    scalar={item['stream']:item for item in snapshot['streams']}
    assert scalar['SPO2']['value']==98 and scalar['PR']['value']==72 and scalar['NIBP']['value']==[118,76]
    assert scalar['PPG']['sample_rate']==50 and len(scalar['PPG']['samples'])==50
    assert result['matching_pubacks']>=10
    (out/'wire-broker-messages.json').write_text(json.dumps(messages,indent=2),encoding='utf-8')
    (out/'wire-backend-snapshot.json').write_text(json.dumps(snapshot,indent=2),encoding='utf-8')
    report['checks']=['real_node_a_can_output','candidate_gateway_rpdo','router_canonical','coremqtt_qos1_matching_puback','loopback_broker_delivery','original_backend_strict_schema','node_a_values_match','ppg_50hz_batch','node_b_offline_no_fabricated_measurement']
    report['wire_sha256']=hashlib.sha256((out/'node-a-can-frames.txt').read_bytes()).hexdigest()
    report['source_sha256']={p.relative_to(ROOT).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in sources}
    report['exit_code']=0
except BaseException as error:
    report['failure_type']=type(error).__name__
    raise
finally:
    if observer: observer.close()
    if broker: broker.close();report['owned_broker_stopped']=broker.process.poll() is not None
    (out/'wire-broker-result.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
print('Physical candidate isolated wire/Broker/Backend PASS',report.get('messages'),report.get('matching_pubacks'))
