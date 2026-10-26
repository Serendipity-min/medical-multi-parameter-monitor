"""B5普通Host验证：真实协议/驱动/模型，替换设备边界；无扫描器和目标I/O。"""
from pathlib import Path
import hashlib
import json
import subprocess
import sys
import uuid

ROOT=Path(__file__).resolve().parents[2]


def main():
    out=ROOT/'node-b/build'/('b5-host-'+uuid.uuid4().hex[:10]);out.mkdir(parents=True)
    dual=ROOT/'gateway/dual_can';mqtt=ROOT/'gateway/mqtt';vendor=ROOT/'gateway/third_party'
    flags=['C:/mingw64/bin/gcc.exe','-std=c11','-O2','-Wall','-Wextra','-Werror','-Wno-unused-parameter',
           '-DCO_MULTIPLE_OD','-DMP_FRAME_MAX_SAMPLES=100','-DMP_CACHE_CAPACITY=64',
           '-DMP_B5_CLOUD_CANDIDATE','-DMP_MQTT_GATEWAY_ID="GW-B5-001"',
           '-I'+str(dual),'-I'+str(ROOT/'gateway/canopen/src'),'-I'+str(vendor/'CANopenNode'),
           '-I'+str(ROOT/'gateway/b5'),'-I'+str(mqtt/'src'),
           '-I'+str(vendor/'coreMQTT/source/include'),'-I'+str(vendor/'coreMQTT/source/interface')]
    model=[ROOT/'gateway/data_model/model.c',ROOT/'gateway/storage/router.c',ROOT/'gateway/b5/b5_policy.c']
    co=[dual/'b4_bus.c',dual/'b4_gateway.c',ROOT/'gateway/canopen/src/mp_od.c',
        vendor/'CANopenNode/CANopen.c',*sorted((vendor/'CANopenNode/301').glob('*.c'))]
    core=[vendor/'coreMQTT/source'/n for n in ('core_mqtt.c','core_mqtt_serializer.c','core_mqtt_state.c')]
    cases=[]

    def run(name,argv,expected=0):
        p=subprocess.run(list(map(str,argv)),cwd=ROOT,capture_output=True,timeout=90)
        log=p.stdout+p.stderr;(out/(name+'.log')).write_bytes(log)
        cases.append({'name':name,'exit_code':p.returncode,'expected_exit':expected,'argv':list(map(str,argv)),
                      'log_sha256':hashlib.sha256(log).hexdigest()})
        print(name,p.returncode,log.decode('utf-8',errors='replace')[-1600:],flush=True)
        return p.returncode==expected

    ok=True
    replay=out/'replay_can.exe'
    ok=run('compile-real-CAN-replay',[*flags,*co,*model,ROOT/'gateway/b5/replay_can.c','-o',replay]) and ok
    policy=out/'policy.exe'
    if run('compile-policy',[*flags,*model,vendor/'coreMQTT/source/core_mqtt_serializer.c',ROOT/'gateway/b5/test_policy.c','-o',policy]):
        ok=run('policy',[policy]) and ok
    else:ok=False
    sntp=out/'sntp.exe'
    if run('compile-H3-SNTP',[*flags,ROOT/'gateway/b5/tests/sntp_sample.c','-o',sntp]):
        ok=run('H3-fresh-SNTP-parser',[sntp]) and ok
    else:ok=False
    conflict=out/'i2s_conflict.c';conflict.write_text('#include "b4_resources.h"\n',encoding='utf-8')
    rejected=run('CAN2-I2S2-conflict-negative',[*flags,'-DB4_I2S2_PB12_PB13=1','-c',conflict,'-o',out/'conflict.o'],expected=1)
    ok=rejected and 'B4_CAN2_CONFLICTS_WITH_I2S2_PB12_PB13' in (out/'CAN2-I2S2-conflict-negative.log').read_text() and ok
    entry_obj=out/'entry.o'
    if run('compile-actual-network-entry',[*flags,'-Dmain=b5_firmware_main','-c',ROOT/'gateway/b5/network_main.c','-o',entry_obj]):
        entry=out/'entry.exe'
        if run('compile-entry-control-test',[*flags,entry_obj,ROOT/'gateway/b5/test_entry.c',ROOT/'gateway/b5/b5_policy.c','-o',entry]):
            ok=run('entry-420s',[entry]) and ok
            ok=run('entry-overflow-stop',[entry,'overflow']) and ok
        else:ok=False
    else:ok=False
    config=out/'config.exe'
    if run('compile-H3-config',[*flags,ROOT/'gateway/b5/test_config.c',ROOT/'gateway/b5/b5_policy.c','-o',config]):
        ok=run('H3-config-integrity-and-B5-identity',[config]) and ok
    else:ok=False
    fixture=['-DGATEWAY_MQTT_HOST_TEST','-DMOCK_USERNAME="b5-gateway"','-DMOCK_CLIENT_ID="b5-c-isolated"',
             mqtt/'tests/mocks/mock_esp.c',mqtt/'src/gateway_transport.c',mqtt/'src/mqtt_transport_adapter.c']
    for name in ('qos_ack','connect_keepalive'):
        exe=out/(name+'.exe')
        if run('compile-'+name,[*flags,*fixture,*model,*core,mqtt/('tests/test_p5_'+name+'.c'),'-o',exe]):
            ok=run(name,[exe]) and ok
        else:ok=False
    pressure=out/'pressure.exe'
    if run('compile-AT-CAN-pressure',[*flags,'-DB4_BXCAN_MMIO_TEST','-DB5_MMIO_INPUT',*fixture,*model,*co,*core,
             dual/'b4_bxcan.c',ROOT/'gateway/b5/test_at_pressure.c','-o',pressure]):
        ok=run('AT-CAN-pressure',[pressure]) and ok
    else:ok=False
    # 实测CAN副本只输出到EFS，不把传感器原始载荷写入Git。
    if replay.exists():
        private=Path(json.loads((ROOT/'node-b/build/b5-private-pointer.json').read_text())['base'])
        for label in ('ECG','RR'):
            target=private/(label+'-MpFrame-MQTT-private.jsonl')
            if target.exists():continue
            with target.open('xb') as stream:
                p=subprocess.run([str(replay),str(private/(label+'-CAN-private.txt'))],stdout=stream,stderr=subprocess.PIPE,timeout=60)
            cases.append({'name':label+'-actual-CAN-to-MQTT','exit_code':p.returncode,'output_sha256':hashlib.sha256(target.read_bytes()).hexdigest()})
            ok=(p.returncode==0) and ok
            print(label+'-actual-CAN-to-MQTT',p.returncode,flush=True)
    inputs=[*model,*co,*core,*(ROOT/'gateway/b5').glob('*.[ch]'),dual/'b4_bxcan.c',dual/'tests/bxcan_mmio_shim.h',
            mqtt/'src/gateway_transport.c',mqtt/'src/mqtt_transport_adapter.c',mqtt/'tests/mocks/mock_esp.c']
    result={'status':'PASS' if ok else 'FAIL','hardware_operations':0,'cases':cases,
            'source_sha256':{str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in inputs}}
    (out/'receipt.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    (ROOT/'node-b/build/b5-host-latest.json').write_text(json.dumps({'out':str(out),'status':result['status']})+'\n',encoding='utf-8')
    return 0 if ok else 1


if __name__=='__main__':raise SystemExit(main())
