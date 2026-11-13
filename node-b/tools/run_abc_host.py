"""三板最小集成回归：实际双CAN驱动/入口，硬件与网络边界为Host替身。"""
import datetime
import hashlib
import json
from pathlib import Path
import subprocess

ROOT=Path(__file__).resolve().parents[2]


def main():
    out=ROOT/'node-b/build'/('abc-core-host-'+datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%S%f'))
    out.mkdir();dual=ROOT/'gateway/dual_can';vendor=ROOT/'gateway/third_party/CANopenNode'
    flags=['C:/mingw64/bin/gcc.exe','-std=c11','-O2','-Wall','-Wextra','-Werror','-Wno-unused-parameter',
        '-DMP_FRAME_MAX_SAMPLES=100','-DMP_LIVE_CAPACITY=24','-DMP_CACHE_CAPACITY=56','-DMP_B5_EGRESS_FINAL',
        '-DCO_MULTIPLE_OD','-I'+str(dual),'-I'+str(ROOT/'gateway/canopen/src'),'-I'+str(vendor),
        '-I'+str(ROOT/'gateway/b5'),'-I'+str(ROOT/'gateway/mqtt/src')]
    cases=[]
    def run(name,command):
        p=subprocess.run(list(map(str,command)),capture_output=True,cwd=ROOT,timeout=90)
        log=p.stdout+p.stderr;(out/(name+'.log')).write_bytes(log)
        cases.append({'name':name,'actual_exit_code':p.returncode,'log_sha256':hashlib.sha256(log).hexdigest()})
        print(name,p.returncode,flush=True)
        if p.returncode:print(log.decode(errors='replace')[-1800:]);raise RuntimeError(name)
    try:
        for label,extra in (('bench',['-DB4_CAPTURE_SERIAL']),('B5-only',['-DMP_B5_CLOUD_CANDIDATE']),
                            ('ABC',['-DMP_B5_CLOUD_CANDIDATE','-DMP_ABC_TRI_CANDIDATE'])):
            exe=out/('link-'+label+'.exe');run('compile-link-'+label,[*flags,*extra,dual/'tests/link_policy.c','-o',exe]);run('link-'+label,[exe])
        exe=out/'abc-driver.exe'
        run('compile-real-dual-driver',[*flags,'-DMP_B5_CLOUD_CANDIDATE','-DMP_ABC_TRI_CANDIDATE',
            '-DB4_BXCAN_MMIO_TEST','-DABC_MMIO_INPUT',dual/'b4_bxcan.c',dual/'tests/abc_dual_driver.c','-o',exe])
        run('real-dual-driver-clock-filter-routing-busoff-stop',[exe])
        entry_flags=[*flags,'-DMP_B5_CLOUD_CANDIDATE','-DMP_ABC_TRI_CANDIDATE',
            '-I'+str(ROOT/'gateway/third_party/coreMQTT/source/include'),'-I'+str(ROOT/'gateway/third_party/coreMQTT/source/interface')]
        obj=out/'entry.o';exe=out/'entry.exe'
        run('compile-actual-ABC-entry',[*entry_flags,'-Dmain=b5_firmware_main','-c',ROOT/'gateway/b5/network_main.c','-o',obj])
        run('link-entry',[*entry_flags,obj,ROOT/'gateway/b5/test_entry.c',ROOT/'gateway/b5/b5_policy.c','-o',exe])
        for mode in ('normal','overflow','A-overflow','inflight','wrap','openfail','retry-pass','retry-exhaust'):
            run('entry-'+mode,[exe,mode])
        result={'exit_code':0,'status':'HOST_COMPONENT_PASS','hardware_actions':0,'cases':cases}
    except RuntimeError:
        result={'exit_code':1,'status':'HOST_COMPONENT_FAIL','hardware_actions':0,'cases':cases}
    (out/'receipt.json').write_text(json.dumps(result,indent=2)+'\n')
    (ROOT/'node-b/build/abc-core-host-pointer.json').write_text(json.dumps({'out':str(out)})+'\n')
    return result['exit_code']


if __name__=='__main__':raise SystemExit(main())
