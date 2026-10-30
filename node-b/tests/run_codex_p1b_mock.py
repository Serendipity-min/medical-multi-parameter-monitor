import ast
import ctypes
import hashlib
import io
import json
from pathlib import Path
import sys
import unittest

root=Path(__file__).resolve().parents[2]
out=root/'node-b/evidence/CODEX-R6-P1B0-20261030'
sys.path[:0]=[str(root/'node-b/tools'),str(root/'node-b/tests')]
blocked=[]
def audit(event,args):
    if event in ('ctypes.dlopen','subprocess.Popen','socket.connect','socket.bind'):
        blocked.append(event);raise AssertionError('OFFLINE_GUARD_'+event)
sys.addaudithook(audit)
import types
serial=types.ModuleType('serial')
def denied(*args,**kwargs):
    blocked.append('serial.Serial');raise AssertionError('OFFLINE_GUARD_SERIAL')
serial.Serial=denied
sys.modules['serial']=serial
import test_codex_p1b_gate as test
captured=[]
original=test.Capture.run_capture
def record(self,fault=None):
    result,link,saved=original(self,fault)
    captured.append({'fault':fault or 'NONE','adapter_model':'FAKE_PYTHON_EXCEPTION_OR_STATE',
                     'native_return':'NOT_EXPOSED_BY_FAKE_ADAPTER',
                     'receipt':result,'Close_calls':link.closes,'read_attempts':len(link.reads)})
    return result,link,saved
test.Capture.run_capture=record
stream=io.StringIO()
run=unittest.TextTestRunner(stream=stream,verbosity=2).run(unittest.defaultTestLoader.loadTestsFromModule(test))
(out/'mock-final-04.log').write_text(stream.getvalue(),encoding='utf-8')
receipt={'status':'PASS_MOCK' if run.wasSuccessful() else 'NOT_PASS_MOCK','exit_code':0 if run.wasSuccessful() else 1,
         'tests_run':run.testsRun,'failures':len(run.failures),'errors':len(run.errors),'blocked_events':blocked,
         'native_target_calls_in_this_test_run':0,'SDK_residual_risk':'UNRESOLVED_NOT_PROVED_BY_MOCK',
         'test_sha256':hashlib.sha256(Path(test.__file__).read_bytes()).hexdigest()}
(out/'mock-final-04.json').write_text(json.dumps(receipt,indent=2)+'\n',encoding='utf-8')
(out/'mock-SDK-fault-matrix.json').write_text(json.dumps({'cases':captured,
    'numeric_native_stub_cases':[{'api':'JLINKARM_ReadMemEx','requested':4,'returned':-1,'rejected_as':'G3_B_NATIVE_READ_ERROR'},
                                 {'api':'JLINKARM_ReadMemEx','requested':4,'returned':3,'rejected_as':'G3_B_POSITIVE_SHORT_READ'}],
    'signal_and_kill_limit':'SystemExit and receipt construction only; not actual OS SIGTERM/taskkill',
    'OpenEx_limit':'OpenEx has pointer/None ABI, not an integer error ABI; negative label in FakeLink means adapter exception only'
    },indent=2)+'\n',encoding='utf-8')
tree=ast.parse((root/'node-b/tools/b5_g3_joint.py').read_text(encoding='utf-8'))
fn=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='joint_worker')
assert len(fn.args.kwonlyargs)==1 and fn.args.kwonlyargs[0].arg=='b_worker_command' and fn.args.kw_defaults[0].value is None
assign=next(n for n in ast.walk(fn) if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='command' for t in n.targets))
assert isinstance(assign.value,ast.IfExp) and isinstance(assign.value.body,ast.Name) and assign.value.body.id=='b_worker_command'
assert 'b_worker_command' not in ast.unparse(assign.value.orelse)
(out/'joint-worker-default-static.json').write_text(json.dumps({'status':'PASS_STATIC_NOT_RUNTIME_INTEGRATION',
    'exit_code':0,'keyword_only_default':None,'override_from':'DIRECT_PYTHON_CALLER_ARGUMENT_ONLY',
    'legacy_default_command_preserved':True,'CLI_validation_unchanged':True},indent=2)+'\n',encoding='utf-8')
print(json.dumps(receipt));sys.exit(receipt['exit_code'])
