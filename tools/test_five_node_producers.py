"""运行实际 D/E 生产者与 CANopenNode，UART/压力/控制器使用主机输入边界。"""
from pathlib import Path
import datetime
import json
import subprocess

ROOT = Path(__file__).resolve().parents[1]
out = ROOT / 'node-b/build/five-node-m1' / datetime.datetime.now(datetime.timezone.utc).strftime('producers-%Y%m%dT%H%M%S%fZ')
out.mkdir(parents=True)
results = []
for role, adapter, co_path, vendor_path, extra in (
    ('D', 'node-d/d_canopen.c', 'node-b/canopen', 'gateway/third_party/CANopenNode', ['node-b/temperature/gy641.c']),
    ('E', 'node-e/e_canopen.c', 'node-a/STM32F407_HOSPITAL/HARDWARE/CANopen', 'node-a/STM32F407_HOSPITAL/HARDWARE/CANopen', []),
):
    co, vendor = ROOT / co_path, ROOT / vendor_path
    sources = [ROOT / adapter, co / 'OD.c', vendor / 'CANopen.c', *sorted((vendor / '301').glob('*.c')),
               *sorted((vendor / '303').glob('*.c')), ROOT / 'node-b/tests/b4_host_driver.c',
               ROOT / 'tools/five_node_producer_host.c', *[ROOT / p for p in extra]]
    if role == 'E':
        sources.append(vendor / '305/CO_LSSslave.c')
    exe = out / (role + '.exe')
    command = ['gcc', '-std=c99', '-O1', '-DROLE_' + role, '-include', str(ROOT / 'node-a/tests/stubs/stm32f4xx.h'),
               *['-I' + str(p) for p in (ROOT / 'node-a/tests/stubs', ROOT / 'node-d/tests', co, vendor, ROOT / 'node-b/temperature')],
               *map(str, sources), '-o', str(exe)]
    build = subprocess.run(command, capture_output=True)
    (out / (role + '-build.log')).write_bytes(build.stdout + build.stderr)
    run = subprocess.run([str(exe)], capture_output=True) if not build.returncode else None
    if run:
        (out / (role + '-test.log')).write_bytes(run.stdout + run.stderr)
    results.append(dict(role=role, compile_exit=build.returncode, test_exit=run.returncode if run else None))
    print(results[-1])
    if build.returncode or (run and run.returncode):
        print((build.stderr + (run.stderr if run else b'')).decode(errors='replace')[-2000:])
(out / 'receipt.json').write_text(json.dumps(results, indent=2), encoding='utf-8')
print(out.relative_to(ROOT))
raise SystemExit(int(any(r['compile_exit'] or r['test_exit'] for r in results)))
