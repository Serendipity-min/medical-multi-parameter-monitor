"""A发送背压定向回归，可替换旧应用源作反事实；不访问硬件。"""
from pathlib import Path
import argparse
import datetime
import json
import subprocess

ROOT=Path(__file__).resolve().parents[1]
p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--application-source',type=Path)
a=p.parse_args()
co=ROOT/'node-a/STM32F407_HOSPITAL/HARDWARE/CANopen'
out=ROOT/'node-b/build'/datetime.datetime.now(datetime.timezone.utc).strftime('field01-a-tx-%Y%m%dT%H%M%S%fZ')
out.mkdir()
sources=[a.application_source or co/'canopen_app.c',co/'CANopen.c',co/'OD.c',
         *sorted((co/'301').glob('*.c')),*sorted((co/'303').glob('*.c')),co/'305/CO_LSSslave.c',
         ROOT/'node-b/tests/b4_host_driver.c',ROOT/'node-a/tests/tx_backpressure.c']
command=['gcc','-std=c99','-O1','-DMP_FIVE_NODE_A','-include',str(ROOT/'node-a/tests/stubs/stm32f4xx.h'),
         *['-I'+str(x) for x in (ROOT/'node-a/tests/stubs',co,ROOT/'node-a/STM32F407_HOSPITAL/HARDWARE/UNO')],
         *map(str,sources),'-o',str(out/'a-tx.exe')]
build=subprocess.run(command,capture_output=True)
(out/'compile.log').write_bytes(build.stdout+build.stderr)
run=subprocess.run([str(out/'a-tx.exe')],capture_output=True) if build.returncode==0 else None
if run:(out/'run.log').write_bytes(run.stdout+run.stderr)
result=dict(scope='HOST_REAL_A_STACK_CAN_BUSY_STUB_NOT_FIELD',compile_exit=build.returncode,test_exit=run.returncode if run else None)
(out/'result.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
print(out.relative_to(ROOT),result)
print((build.stderr+(run.stdout+run.stderr if run else b'')).decode(errors='replace')[-1800:])
raise SystemExit(build.returncode or (run.returncode if run else 1))
