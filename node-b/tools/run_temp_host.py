"""温度新增路径定向回归：不连接实板、串口或网络。"""
from pathlib import Path
import hashlib
import json
import subprocess
import sys
import uuid

ROOT=Path(__file__).resolve().parents[2]

def main():
    out=ROOT/'node-b/build'/('temp-host-'+uuid.uuid4().hex[:8]);out.mkdir()
    v=ROOT/'gateway/third_party';b=ROOT/'node-b/canopen';d=ROOT/'gateway/dual_can';t=ROOT/'node-b/temperature'
    core=[v/'CANopenNode/CANopen.c',*sorted((v/'CANopenNode/301').glob('*.c'))]
    flags=['C:/mingw64/bin/gcc.exe','-std=c99','-O2','-Wall','-Wextra','-Werror','-Wno-unused-parameter']
    cases=[]
    def run(name,args,stdout=None):
        result=subprocess.run(list(map(str,args)),cwd=ROOT,capture_output=True,timeout=90)
        log=result.stdout+result.stderr;(out/(name+'.log')).write_bytes(log)
        cases.append({'name':name,'exit_code':result.returncode,'log_sha256':hashlib.sha256(log).hexdigest()})
        print(name,result.returncode,flush=True)
        if result.returncode:raise RuntimeError('TEMP_HOST_CASE_FAILED_'+name)
        if stdout:stdout.write_bytes(result.stdout)
    exe=out/'parser.exe'
    run('compile-parser',[*flags,t/'gy641.c',t/'test_gy641.c','-o',exe]);run('parser',[exe])
    inc=['-I'+str(x) for x in (b,v/'CANopenNode',ROOT/'node-b/firmware/biov2/实验固件/HARDWARE',t)]
    sources=[*core,v/'CANopenNode/303/CO_LEDs.c',b/'OD.c',b/'b_canopen_app.c',ROOT/'node-b/tests/b4_host_driver.c',
             ROOT/'node-b/firmware/biov2/实验固件/HARDWARE/bio_v2.c']
    exe=out/'producer.exe'
    run('compile-temperature-producer',[*flags,'-DB4_HOST','-DB_TEMP_ENABLED',*inc,*sources,
        t/'test_temp_protocol.c',t/'gy641.c','-lm','-o',exe])
    run('temperature-producer',[exe,out/'wire-decimal.txt'])
    lines=[]
    for line in (out/'wire-decimal.txt').read_text().splitlines():
        q=list(map(int,line.split()));lines.append(f'{q[0]} {q[1]:x} {q[2]} '+bytes(q[3:]).hex())
    (out/'wire-hex.txt').write_text('\n'.join(lines)+'\n')
    exe=out/'gateway.exe';inc=['-I'+str(x) for x in (d,ROOT/'gateway/canopen/src',v/'CANopenNode')]
    run('compile-gateway',[*flags,'-DCO_MULTIPLE_OD','-DMP_FRAME_MAX_SAMPLES=100','-DMP_CACHE_CAPACITY=64',
        '-DMP_B5_CLOUD_CANDIDATE','-DMP_MQTT_GATEWAY_ID="GW-B5-001"',*inc,*core,
        ROOT/'gateway/canopen/src/mp_od.c',d/'b4_bus.c',d/'b4_gateway.c',ROOT/'gateway/data_model/model.c',
        ROOT/'gateway/storage/router.c',ROOT/'gateway/b5/replay_can.c','-o',exe])
    run('gateway',[exe,out/'wire-hex.txt'],out/'messages.jsonl')
    sys.path.insert(0,str(ROOT))
    from cloud.backend.app.adapters import decode_mqtt
    temp=[]
    for row in (out/'messages.jsonl').read_text().splitlines():
        m=json.loads(row);value=decode_mqtt(m['topic'],json.dumps(m['payload'],separators=(',',':')).encode()).model_dump()
        if value['stream']=='TEMP':temp.append(value)
    valid=[x for x in temp if x['validity']=='VALID']
    assert valid and all(x['value']==33.07 for x in valid)
    assert any(x['validity']=='INVALID' and x['value'] is None for x in temp)
    assert all(x['synthetic'] and x['source']=='MOCK' for x in temp)
    # CAN标量时间是节点报告秒锚；物理接收时刻和帧龄另留源证据，不声称精确测温UTC。
    assert all(1792713600000<=x['timestamp']<=1792713604000 for x in valid)
    report={'status':'PASS','hardware_operations':0,'network_operations':0,'cases':cases,
            'Backend_temperature_messages':len(temp),'temperature_quantity':'nonhuman_object_surface',
            'absolute_accuracy':'NOT_CALIBRATED','BIO_source_sha256':hashlib.sha256(sources[-1].read_bytes()).hexdigest(),
            'source_sha256':{p.relative_to(ROOT).as_posix():hashlib.sha256(p.read_bytes()).hexdigest()
                             for p in [*t.glob('*.[ch]'),b/'b_canopen_app.c',d/'b4_gateway.c',Path(__file__)]}}
    (out/'receipt.json').write_text(json.dumps(report,indent=2)+'\n')
    (ROOT/'node-b/build/b5-temp-host-latest.json').write_text(json.dumps({'out':str(out)})+'\n')
    print('TEMP_HOST_PASS producer_CAN_Gateway_Backend_units_validity_sample_age_NO_HARDWARE')
    return 0

if __name__=='__main__':raise SystemExit(main())
