import ctypes
import hashlib
import io
import json
from pathlib import Path
import sys
import types
import unittest
ROOT=Path(__file__).resolve().parents[2];sys.path[:0]=[str(ROOT/'node-b/tools'),str(ROOT/'node-b/tests')]
blocked=[]
def audit(event,args):
    if event in ('ctypes.dlopen','subprocess.Popen','socket.connect','socket.bind'):
        blocked.append(event);raise AssertionError('OFFLINE_GUARD_'+event)
sys.addaudithook(audit)
serial=types.ModuleType('serial')
def denied(*args,**kwargs):
    blocked.append('serial.Serial');raise AssertionError('OFFLINE_GUARD_SERIAL')
serial.Serial=denied;sys.modules['serial']=serial
suite=unittest.TestSuite(unittest.defaultTestLoader.loadTestsFromName(name) for name in ('test_b4_runtime','test_b4_temperature_observation'))
stream=io.StringIO();result=unittest.TextTestRunner(stream=stream,verbosity=2).run(suite)
ev=ROOT/'node-b/evidence/CODEX-R6-ECG-TEMP-20261030';ev.mkdir(exist_ok=True)
(ev/'temperature-host-fix-mock.log').write_text(stream.getvalue(),encoding='utf-8')
receipt={'status':'PASS_MOCK' if result.wasSuccessful() else 'NOT_PASS_MOCK','exit_code':0 if result.wasSuccessful() else 1,
    'tests_run':result.testsRun,'failures':len(result.failures),'errors':len(result.errors),'blocked_events':blocked,'native_target_calls_in_this_test_run':0,
    'sources':{p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in ['node-b/tools/b4_runtime.py','node-b/tests/test_b4_temperature_observation.py','node-b/tests/test_b4_runtime.py']}}
(ev/'temperature-host-fix-mock.json').write_text(json.dumps(receipt,indent=2)+'\n',encoding='utf-8')
print(json.dumps(receipt));raise SystemExit(receipt['exit_code'])
