"""定向编译与运行真实五板 C 接收路径，不访问物理端口。"""
from pathlib import Path
import datetime
import json
import subprocess

ROOT = Path(__file__).resolve().parents[1]
out = ROOT / 'node-b/build/five-node-m1' / datetime.datetime.now(datetime.timezone.utc).strftime('host-%Y%m%dT%H%M%S%fZ')
out.mkdir(parents=True)
vendor = ROOT / 'gateway/third_party/CANopenNode'
sources = [ROOT / f for f in ('gateway/dual_can/b4_gateway.c', 'gateway/dual_can/b4_bus.c',
           'gateway/canopen/src/mp_od.c', 'gateway/data_model/model.c', 'gateway/storage/router.c',
           'gateway/dual_can/tests/five_node.c')]
sources += [vendor / 'CANopen.c', *sorted((vendor / '301').glob('*.c'))]
command = ['gcc', '-std=c11', '-O1', '-g', '-Wall', '-Wextra', '-Wno-unused-parameter',
           '-DCO_MULTIPLE_OD', '-DMP_FIVE_NODE', '-DMP_FRAME_MAX_SAMPLES=100', '-DMP_CACHE_CAPACITY=64',
           '-I' + str(ROOT / 'gateway/dual_can'), '-I' + str(ROOT / 'gateway/canopen/src'),
           '-I' + str(vendor), *map(str, sources), '-o', str(out / 'five-node-host.exe')]
build = subprocess.run(command, capture_output=True)
(out / 'five-node-host-build.log').write_bytes(build.stdout + build.stderr)
run = subprocess.run([str(out / 'five-node-host.exe')], capture_output=True) if build.returncode == 0 else None
if run:
    (out / 'five-node-host-run.log').write_bytes(run.stdout + run.stderr)
result = dict(scope='HOST_ONLY_REAL_PROTOCOL_IO_SIMULATED', compile_exit=build.returncode,
              test_exit=run.returncode if run else None)
(out / 'five-node-host-result.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
print(str(out.relative_to(ROOT)), result)
print((build.stderr + (run.stdout + run.stderr if run else b'')).decode(errors='replace')[-3000:])
raise SystemExit(build.returncode or (run.returncode if run else 1))
