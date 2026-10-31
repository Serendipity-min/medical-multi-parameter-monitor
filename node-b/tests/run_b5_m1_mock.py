"""只运行M1-P0离线正负例；审计钩子拒绝SDK/DLL/COM、子进程与网络。"""
import argparse
import ctypes  # Windows标准库初始化kernel32；不构造或加载J-Link SDK。
import hashlib
import io
import json
import os
from pathlib import Path
import sys
import types
import unittest

ROOT=Path(__file__).resolve().parents[2]
sys.path[:0]=[str(ROOT/'node-b/tests'),str(ROOT/'node-b/tools')]


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--out',type=Path,required=True);a=p.parse_args()
    a.out.mkdir(exist_ok=False);os.environ['M1_TEST_ROOT']=str(a.out)
    blocked=[]
    def audit(event,args):
        if event in ('ctypes.dlopen','socket.connect','socket.bind','subprocess.Popen'):
            blocked.append(event);raise AssertionError('M1_OFFLINE_GUARD_'+event)
    sys.addaudithook(audit)
    serial=types.ModuleType('serial')
    def denied(*args,**kwargs):blocked.append('serial.Serial');raise AssertionError('M1_OFFLINE_GUARD_SERIAL')
    serial.Serial=denied;sys.modules['serial']=serial
    suite=unittest.defaultTestLoader.loadTestsFromName('test_b5_m1')
    stream=io.StringIO();result=unittest.TextTestRunner(stream=stream,verbosity=2).run(suite)
    log=stream.getvalue();(a.out/'tests.log').write_text(log,encoding='utf-8')
    names=['node-b/tools/b5_m1_entry.py','node-b/tools/b5_m1_review.py','node-b/tests/test_b5_m1.py','node-b/tests/run_b5_m1_mock.py']
    for name in names:(a.out/Path(name).name).write_bytes((ROOT/name).read_bytes())
    report={'scope':'M1_P0_OFFLINE_ONLY','status':'PASS_MOCK' if result.wasSuccessful() and not blocked else 'FAIL_MOCK',
        'tests_run':result.testsRun,'failures':len(result.failures),'errors':len(result.errors),'blocked_events':blocked,
        'exit_code':0 if result.wasSuccessful() and not blocked else 1,'SDK_COM_network_actions':0,
        'ctypes_bootstrap':'Windows stdlib kernel32 initialized before guard; no JLink constructor',
        'log_sha256':hashlib.sha256(log.encode()).hexdigest(),
        'sources':{n:hashlib.sha256((ROOT/n).read_bytes()).hexdigest() for n in names}}
    (a.out/'receipt.json').write_text(json.dumps(report,indent=2)+'\n')
    if report['exit_code']:print(log[-14000:])
    print(json.dumps(report));return report['exit_code']


if __name__=='__main__':raise SystemExit(main())
