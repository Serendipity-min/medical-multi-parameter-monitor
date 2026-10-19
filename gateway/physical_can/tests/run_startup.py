"""H0 使用真实协议/队列及策略，仅替换物理寄存器；baseline 模式编译受审 stack 字节。"""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess

ROOT=Path(__file__).resolve().parents[3]
HERE=ROOT/'gateway/physical_can'
CO=ROOT/'gateway/canopen'
VENDOR=ROOT/'gateway/third_party/CANopenNode'
BASE='1dfc9667d14941456bae75ba130ac8a8b219ccef'
parser=argparse.ArgumentParser()
parser.add_argument('--baseline',action='store_true')
args=parser.parse_args()
build=HERE/'build';build.mkdir(exist_ok=True)
out=HERE/'evidence/h0';out.mkdir(exist_ok=True)
stack=HERE/'src/stack.c'
if args.baseline:
    # 原始失败由固定提交源码复现，不修改当前 worktree 的实现。
    stack=build/'h0-baseline-stack.c'
    stack.write_bytes(subprocess.check_output(['git','show',BASE+':gateway/physical_can/src/stack.c'],cwd=ROOT))
sources=[stack,CO/'src/mp_can_driver.c',CO/'src/mp_od.c',VENDOR/'CANopen.c',*sorted((VENDOR/'301').glob('*.c')),HERE/'tests/startup.c']
if not args.baseline:
    sources.append(HERE/'src/lifecycle.c')
name='startup-baseline' if args.baseline else 'startup-fixed'
cmd=['gcc','-std=c11','-O1','-g','-DCO_MULTIPLE_OD','-Wall','-Wextra','-Wno-unused-parameter',*(['-DH0_BASELINE'] if args.baseline else []),*['-I'+str(p) for p in [HERE/'src',CO/'src',VENDOR]],*map(str,sources),'-o',str(build/(name+'.exe'))]
r=subprocess.run(cmd,capture_output=True);log=r.stdout+r.stderr
result={'compile_exit':r.returncode,'test_exit':None,'mode':'HOST_REGISTER_STUB_TXOK_POLICY','hardware':'NOT_RUN','command':cmd,'baseline':BASE if args.baseline else None,'source_sha256':{str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in sources}}
if r.returncode==0:
    r=subprocess.run([str(build/(name+'.exe')),*(['baseline'] if args.baseline else [])],capture_output=True)
    result['test_exit']=r.returncode;log+=r.stdout+r.stderr
(out/(name+'.log')).write_bytes(log)
(out/(name+'-result.json')).write_text(json.dumps(result,indent=2),encoding='utf-8')
print(log.decode('utf-8',errors='replace'));print(name,result['compile_exit'],result['test_exit'])
raise SystemExit(result['compile_exit'] or result['test_exit'] or 0)
