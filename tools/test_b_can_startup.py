"""真实节点CAN驱动活跃总线启动回归；SPL为替身，无硬件/网络入口。"""
import argparse
import datetime
import hashlib
import json
from pathlib import Path
import subprocess
import uuid

ROOT = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--driver-source', type=Path)
args = parser.parse_args()
out = ROOT / 'node-b/build' / (datetime.datetime.now(datetime.timezone.utc).strftime('b-can-startup-%Y%m%dT%H%M%S%fZ-') + uuid.uuid4().hex[:8])
out.mkdir()
stub = out / 'stubs'
stub.mkdir()
for name in ('stm32f4xx.h', 'stm32f4xx_can.h', 'stm32f4xx_gpio.h', 'stm32f4xx_rcc.h', 'misc.h'):
    (stub / name).write_text('#include "can_startup_spl_stub.h"\n')
driver = args.driver_source or ROOT/'node-b/canopen/CO_driver.c'
command = ['gcc', '-std=c99', '-O1', '-Wall', '-Wextra',
           *['-I' + str(p) for p in (stub, ROOT/'node-b/tests', ROOT/'node-b/canopen', ROOT/'gateway/third_party/CANopenNode')],
           str(driver), str(ROOT/'node-b/tests/can_startup.c'),
           '-o', str(out/'startup.exe')]
build = subprocess.run(command, capture_output=True)
(out/'compile.log').write_bytes(build.stdout+build.stderr)
run = subprocess.run([str(out/'startup.exe')], capture_output=True) if build.returncode == 0 else None
if run:
    (out/'run.log').write_bytes(run.stdout+run.stderr)
result = dict(scope='HOST_REAL_NODE_DRIVER_SPL_SIMULATED', compile_exit=build.returncode,
              test_exit=run.returncode if run else None, driver_source=str(driver),
              driver_sha256=hashlib.sha256(driver.read_bytes()).hexdigest())
(out/'result.json').write_text(json.dumps(result, indent=2)+'\n')
print(out.relative_to(ROOT), json.dumps(result))
print((build.stderr+(run.stdout+run.stderr if run else b'')).decode(errors='replace')[-2000:])
raise SystemExit(build.returncode or (run.returncode if run else 1))
