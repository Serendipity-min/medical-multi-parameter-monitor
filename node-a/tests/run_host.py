"""编译真实 Node-A 协议/应用；原始失败和修复结果使用相同测试入口保存退出码。"""
from pathlib import Path
import argparse
import json
import subprocess
import os
ROOT=Path(__file__).resolve().parents[1]
CO=ROOT/'STM32F407_HOSPITAL/HARDWARE/CANopen'
parser=argparse.ArgumentParser();parser.add_argument('--phase',required=True);args=parser.parse_args()
build=ROOT/'build';build.mkdir(exist_ok=True)
# 新合同通过外部测试目录隔离回执，wire夹具复用此入口时也不覆盖历史原件。
out=Path(os.environ.get('NODE_A_TEST_EVIDENCE',ROOT/'evidence'));out.mkdir(parents=True,exist_ok=True)
sources=[CO/'CANopen.c',CO/'OD.c',CO/'canopen_app.c',*sorted((CO/'301').glob('*.c')),*sorted((CO/'303').glob('*.c')),CO/'305/CO_LSSslave.c',ROOT/'tests/host.c']
cmd=['gcc','-std=c99','-g','-O0','-include',str(ROOT/'tests/stubs/stm32f4xx.h'),'-I'+str(ROOT/'tests/stubs'),'-I'+str(CO),'-I'+str(ROOT/'STM32F407_HOSPITAL/HARDWARE/UNO'),*map(str,sources),'-o',str(build/'host.exe')]
r=subprocess.run(cmd,capture_output=True);log=r.stdout+r.stderr;compile_exit=r.returncode
test_exit=None
if not compile_exit:
    r=subprocess.run([str(build/'host.exe')],capture_output=True);log+=r.stdout+r.stderr;test_exit=r.returncode
(out/(args.phase+'-host.log')).write_bytes(log)
(out/(args.phase+'-host-exit.json')).write_text(json.dumps({'compile_exit':compile_exit,'test_exit':test_exit,'mode':'HOST_PROTOCOL_WITH_EXTERNAL_IO_STUBS'},indent=2),encoding='utf-8')
print('compile',compile_exit,'test',test_exit);print(log.decode('utf-8',errors='replace')[-2000:])
raise SystemExit(compile_exit or test_exit or 0)
