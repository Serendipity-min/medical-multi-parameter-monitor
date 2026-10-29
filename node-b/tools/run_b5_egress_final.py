"""出口最小修复定向Host门；不连接硬件或远端。"""
import hashlib
import json
from pathlib import Path
import subprocess
import uuid
import shutil

ROOT=Path(__file__).resolve().parents[2]

def main():
    out=ROOT/'node-b/build'/('egress-final-host-'+uuid.uuid4().hex[:10]);out.mkdir()
    mqtt=ROOT/'gateway/mqtt';vendor=ROOT/'gateway/third_party/coreMQTT/source'
    flags=['C:/mingw64/bin/gcc.exe','-std=c11','-O2','-Wall','-Wextra','-Werror','-Wno-unused-parameter',
           '-DMP_FRAME_MAX_SAMPLES=100','-DMP_LIVE_CAPACITY=24','-DMP_CACHE_CAPACITY=56','-DMP_B5_CLOUD_CANDIDATE','-DMP_B5_EGRESS_FINAL',
           '-DMP_MQTT_GATEWAY_ID="GW-B5-001"', '-I'+str(mqtt/'src'),'-I'+str(ROOT/'gateway/b5'),
           '-I'+str(vendor/'include'),'-I'+str(vendor/'interface')]
    model=[ROOT/'gateway/data_model/model.c',ROOT/'gateway/storage/router.c',ROOT/'gateway/b5/b5_policy.c']
    core=[vendor/n for n in ('core_mqtt.c','core_mqtt_serializer.c','core_mqtt_state.c')]
    fixture=['-DGATEWAY_MQTT_HOST_TEST','-DMOCK_USERNAME="b5-gateway"','-DMOCK_CLIENT_ID="b5-c-isolated"',
             mqtt/'tests/mocks/mock_esp.c',mqtt/'src/gateway_transport.c',mqtt/'src/mqtt_transport_adapter.c']
    cases=[]
    def run(name,args):
        r=subprocess.run(list(map(str,args)),capture_output=True,cwd=ROOT,timeout=90)
        log=r.stdout+r.stderr;(out/(name+'.log')).write_bytes(log)
        cases.append(dict(name=name,exit_code=r.returncode,log_sha256=hashlib.sha256(log).hexdigest()))
        print(name,r.returncode,log.decode(errors='replace')[-2200:],flush=True)
        return r.returncode==0
    ok=True;exe=out/'async.exe'
    pointer=json.loads((ROOT/'node-b/build/b5-egress-final-r1-pointer.json').read_text());baseline=out/'baseline-source'
    # GCC不支持该EFS归档的长路径；复制的是经冻结SHA匹配的公开源码，不复制私有镜像。
    shutil.copytree(Path(pointer['root'])/'baseline-source',baseline)
    legacy_flags=[x for x in flags if x not in ('-DMP_B5_EGRESS_FINAL','-DMP_LIVE_CAPACITY=24','-DMP_CACHE_CAPACITY=56')]+['-DMP_CACHE_CAPACITY=64']
    legacy_fixture=[baseline/'gateway/mqtt/src'/x.name if isinstance(x,Path) and x.parent==mqtt/'src' else x for x in fixture]
    legacy_model=[baseline/x.relative_to(ROOT) for x in model];legacy=out/'baseline.exe'
    if run('compile-deployed-C43036-baseline',[*legacy_flags,*legacy_fixture,*legacy_model,*core,ROOT/'gateway/b5/test_egress_async.c','-o',legacy]):
        ok=run('historical-stalls-old-C-reproduction',[legacy]) and ok
    else:ok=False
    expanded=[x for x in legacy_flags if x!='-DMP_CACHE_CAPACITY=64']+['-DMP_LIVE_CAPACITY=24','-DMP_CACHE_CAPACITY=56']
    if run('compile-capacity-only-control',[*expanded,*legacy_fixture,*legacy_model,*core,ROOT/'gateway/b5/test_egress_async.c','-o',legacy]):
        ok=run('capacity-only-control-observed-not-assumed',[legacy]) and ok
    else:ok=False
    entry=out/'entry.o'
    if run('compile-actual-final-entry',[*flags,'-DCO_MULTIPLE_OD','-I'+str(ROOT/'gateway/dual_can'),
            '-I'+str(ROOT/'gateway/canopen/src'),'-I'+str(ROOT/'gateway/third_party/CANopenNode'),
            '-Dmain=b5_firmware_main','-c',ROOT/'gateway/b5/network_main.c','-o',entry]):
        exe=out/'entry.exe'
        if run('link-final-entry',[*flags,'-DCO_MULTIPLE_OD','-I'+str(ROOT/'gateway/dual_can'),
               '-I'+str(ROOT/'gateway/canopen/src'),'-I'+str(ROOT/'gateway/third_party/CANopenNode'),
               entry,ROOT/'gateway/b5/test_entry.c',ROOT/'gateway/b5/b5_policy.c','-o',exe]):
            for mode in ('normal','overflow','inflight','wrap','openfail','retry-pass','retry-exhaust'):ok=run('entry-'+mode,[exe,mode]) and ok
        else:ok=False
    else:ok=False
    exe=out/'async.exe'
    if run('compile-async',[*flags,*fixture,*model,*core,ROOT/'gateway/b5/test_egress_async.c','-o',exe]):
        ok=run('async-pressure',[exe]) and ok
    else:ok=False
    exe=out/'at-stop.exe'
    if run('compile-real-platform',[*flags,'-DMP_CAN_RX_IRQ','-DPLATFORM_HOST_TEST',mqtt/'src/platform.c',ROOT/'gateway/b5/test_at_stop.c','-o',exe]):
        for phase in (0,1,2,3,4,'budget','closed','ready','busy','silent','sendfail'):ok=run('AT-stop-'+str(phase),[exe,str(phase)]) and ok
    else:ok=False
    exe=out/'sntp-retry.exe'
    if run('compile-actual-sntp-retry',[*flags,'-DGATEWAY_MQTT_HOST_TEST','-DMP_H3_FRESH_SNTP',
            '-ffunction-sections','-fdata-sections',ROOT/'gateway/b5/test_sntp_retry.c',
            mqtt/'src/mqtt_transport_adapter.c',*core,ROOT/'gateway/b5/b5_policy.c',ROOT/'gateway/data_model/model.c','-Wl,--gc-sections','-o',exe]):
        ok=run('actual-sntp-retry-positive-negative',[exe]) and ok
    else:ok=False
    for name in ('qos_ack','connect_keepalive'):
        exe=out/(name+'.exe')
        if run('compile-'+name,[*flags,*fixture,*model,*core,mqtt/('tests/test_p5_'+name+'.c'),'-o',exe]):ok=run(name,[exe]) and ok
        else:ok=False
    receipt=dict(status='PASS' if ok else 'FAIL',hardware_operations=0,network_operations=0,cases=cases)
    (out/'receipt.json').write_text(json.dumps(receipt,indent=2)+'\n')
    (ROOT/'node-b/build/b5-egress-final-host-latest.json').write_text(json.dumps({'out':str(out)})+'\n')
    return 0 if ok else 1

if __name__=='__main__':raise SystemExit(main())
