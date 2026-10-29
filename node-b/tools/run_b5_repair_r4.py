"""R4真实AT组合离线门；不打开串口、SDK、网络或设备。"""
import hashlib
import json
from pathlib import Path
import subprocess
import uuid

ROOT=Path(__file__).resolve().parents[2]

def main():
    out=ROOT/'node-b/build'/('repair-r4-host-'+uuid.uuid4().hex[:10]);out.mkdir()
    mqtt=ROOT/'gateway/mqtt';vendor=ROOT/'gateway/third_party/coreMQTT/source'
    flags=['C:/mingw64/bin/gcc.exe','-std=c11','-O2','-Wall','-Wextra','-Werror','-Wno-unused-parameter',
        '-DMP_FRAME_MAX_SAMPLES=100','-DMP_LIVE_CAPACITY=24','-DMP_CACHE_CAPACITY=56',
        '-DMP_B5_CLOUD_CANDIDATE','-DMP_B5_EGRESS_FINAL','-DMP_CAN_RX_IRQ','-DPLATFORM_HOST_TEST',
        '-DGATEWAY_MQTT_HOST_TEST','-DMP_MQTT_GATEWAY_ID="GW-B5-001"',
        '-I'+str(mqtt/'src'),'-I'+str(ROOT/'gateway/b5'),'-I'+str(vendor/'include'),'-I'+str(vendor/'interface')]
    cases=[]
    def run(name,argv):
        r=subprocess.run(list(map(str,argv)),cwd=ROOT,capture_output=True,timeout=90)
        raw=r.stdout+r.stderr;(out/(name+'.log')).write_bytes(raw)
        cases.append(dict(name=name,exit_code=r.returncode,log_sha256=hashlib.sha256(raw).hexdigest()))
        print(name,r.returncode,raw.decode(errors='replace')[-1800:],flush=True)
        return r.returncode==0
    pointer=json.loads((ROOT/'node-b/build/b5-egress-final-r1-pointer.json').read_text('utf8'))
    old_source=Path(pointer['fallback_r2_root'])/'deployed46584-source/gateway/mqtt/src/platform.c'
    original=json.loads((Path(pointer['fallback_r2_build'])/'receipt.json').read_text('utf8'))
    data=old_source.read_bytes();expected=next(v for k,v in original['source_sha256'].items() if k.replace('\\','/')=='gateway/mqtt/src/platform.c')
    assert hashlib.sha256(data).hexdigest()==expected
    old=out/'deployed_platform.c';old.write_bytes(data)
    legacy=out/'old-send.exe'
    ok=run('compile-deployed-platform-50ms-counterexample',[*flags,'-DEXPECT_OLD_DEFECT',old,ROOT/'gateway/b5/test_at_stop.c','-o',legacy])
    if ok:ok=run('deployed-854B-50ms-counterexample',[legacy,'short854'])
    fixed=out/'send.exe'
    built=run('compile-repaired-platform-admission',[*flags,mqtt/'src/platform.c',ROOT/'gateway/b5/test_at_stop.c','-o',fixed]);ok=built and ok
    if built:ok=run('repaired-854B-50ms-zero-UART',[fixed,'short854']) and ok
    pi=out/'pi.exe';ok=run('compile-PI-real-platform',[*flags,ROOT/'gateway/b5/test_repair_r4_pi.c','-o',pi]) and ok
    if ok:
        for name,arg in [('poll','poll'),*[(f'poll{n}',f'poll{n}') for n in (1,50,200,1000)],
            ('parser-matrix','parser-matrix'),('binary-OK','\r\nOK\r\n'),('binary-ERROR','\r\nERROR\r\n'),('binary-URC','\r\nready\r\n>')]:
            ok=run(name,[pi,arg]) and ok
    exe=out/'chain.exe'
    sources=[ROOT/'gateway/b5/test_repair_r4_chain.c',mqtt/'src/mqtt_transport_adapter.c',
        ROOT/'gateway/storage/router.c',ROOT/'gateway/data_model/model.c',ROOT/'gateway/b5/b5_policy.c',
        *[vendor/n for n in ('core_mqtt.c','core_mqtt_serializer.c','core_mqtt_state.c')]]
    deployed=json.loads((ROOT/'node-b/build/b5-repair-r4-pointer.json').read_text('utf8'))
    for file,macro,case in [('platform.c','EXPECT_CLOSE_DEFECT','expected-close'),('gateway_transport.c','EXPECT_TIME_DEFECT','clock19')]:
        previous=Path(deployed['root'])/'compiled-source/gateway/mqtt/src'/file;short=out/('deployed-R4-'+file);short.write_bytes(previous.read_bytes())
        selector='REPAIR_PLATFORM_SOURCE' if file=='platform.c' else 'REPAIR_TRANSPORT_SOURCE'
        oldexe=out/(macro+'.exe');built=run('compile-'+macro,[*flags,'-DMP_H3_FRESH_SNTP','-D'+macro,'-D'+selector+'="'+short.as_posix()+'"',*sources,'-o',oldexe]);ok=built and ok
        if built:ok=run('reproduce-'+macro,[oldexe,case]) and ok
    compiled=run('compile-real-egress-core-adapter-platform-UART',[*flags,*sources,'-o',exe]);ok=compiled and ok
    if compiled:
        for mode in ('normal','wrap','poll','keepalive','close-active','wrong','missing','late','during','duplicate','deferqueue','raw854','raw2048',
            'no-prompt','slow-prompt','partial-data','slowrx','rxlate','stopack',
            'age900','age4500','age4950','age4999','terminal1','terminal2','terminal3','terminal4','terminal5',
            'stop1','stop2','stop3','stop4','pressure'):
            ok=run('combined-'+mode,[exe,mode]) and ok
    ntp=out/'ntp-chain.exe';built=run('compile-actual-SNTP-AT-chain',[*flags,'-DMP_H3_FRESH_SNTP',*sources,'-o',ntp]);ok=built and ok
    if built:
        for mode in ('expected-close','close-no-ok','fresh-rotate','clock19','clock19-wrap','clock-never'):ok=run('SNTP-chain-'+mode,[ntp,mode]) and ok
    (out/'receipt.json').write_text(json.dumps(dict(status='PASS' if ok else 'FAIL',cases=cases,
        hardware_operations=0,network_operations=0),indent=2)+'\n',encoding='utf8')
    (ROOT/'node-b/build/b5-repair-r4-host-latest.json').write_text(json.dumps(dict(out=str(out)))+'\n',encoding='utf8')
    return 0 if ok else 1

if __name__=='__main__':raise SystemExit(main())
