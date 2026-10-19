"""H2R普通功能回归；保留原始退出码，归档新证据后恢复原有证据字节。非Security Gate。"""
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / 'gateway/physical_can/evidence/h2r' / datetime.now(timezone.utc).strftime('regression-%Y%m%dT%H%M%SZ')
OUT.mkdir(parents=True)
protected = [ROOT / x for x in ('node-a/evidence', 'gateway/physical_can/evidence',
                               'gateway/canopen/evidence', 'gateway/mqtt/evidence')]


def evidence_files():
    result = {}
    for directory in protected:
        if directory.exists():
            for path in directory.rglob('*'):
                if path.is_file() and not path.is_relative_to(ROOT / 'gateway/physical_can/evidence/h2r'):
                    result[path.relative_to(ROOT)] = path.read_bytes()
    return result


commands = [
    ('h2r-host', ['python', 'gateway/physical_can/bench_build.py', '--h2r', '--host']),
    ('h2r-arm', ['python', 'gateway/physical_can/bench_build.py', '--h2r']),
    ('capture-host', ['python', 'gateway/physical_can/tests/test_capture_uart.py']),
    ('download-gate-host', ['python', 'gateway/physical_can/tests/test_flash_plan.py']),
    ('a-download-gate-host', ['python', 'gateway/physical_can/tests/test_a_flash_gate.py']),
    ('node-a-host', ['python', 'node-a/tests/run_host.py', '--phase', 'h2r']),
    ('node-a-keil', ['D:/keil/UV4/UV4.exe', '-r', str(ROOT / 'node-a/STM32F407_HOSPITAL/USER/STM32F407_Template.uvprojx'),
                     '-o', str(OUT / 'node-a-keil-build.log')]),
    ('h0-startup-host', ['python', 'gateway/physical_can/tests/run_startup.py']),
    ('physical-host', ['python', 'gateway/physical_can/build.py', '--host']),
    ('physical-arm', ['python', 'gateway/physical_can/build.py']),
    ('physical-wire', ['python', 'gateway/physical_can/build.py', '--host', '--wire', 'gateway/physical_can/evidence/node-a-can-frames.txt']),
    ('p5-can-host', ['python', 'gateway/mqtt/tests/run_p5_host_tests.py', '--with-can-capture']),
    ('canonical', ['python', 'gateway/canopen/tools/check_canonical.py']),
    ('p5-arm', ['python', 'gateway/mqtt/build.py']),
    ('backend', ['python', '-m', 'pytest', 'cloud/backend/tests', '-q']),
    ('isolated-broker', ['python', 'gateway/mqtt/tests/run_broker_integration.py', '--runtime', 'E:/medical-monitor-p5/isolated-broker/runtime']),
    ('physical-wire-broker', ['python', 'gateway/physical_can/tests/run_wire_broker.py', '--runtime', 'E:/medical-monitor-p5/isolated-broker/runtime']),
]
before = evidence_files()
results = []
env = dict(os.environ, PYTHONIOENCODING='utf-8')
try:
    for name, command in commands:
        start = datetime.now(timezone.utc).isoformat()
        print(name, 'START', flush=True)
        run = subprocess.run(command, cwd=ROOT, env=env, capture_output=True)
        (OUT / (name + '.log')).write_bytes(run.stdout + run.stderr)
        results.append({'name': name, 'command': command, 'exit_code': run.returncode,
                        'started_utc': start, 'finished_utc': datetime.now(timezone.utc).isoformat()})
        (OUT / 'results.json').write_text(json.dumps(results, indent=2) + '\n', encoding='utf-8')
        print(name, 'EXIT', run.returncode, flush=True)
finally:
    after = evidence_files()
    restored = {}
    for rel, data in after.items():
        if before.get(rel) != data:
            dest = OUT / 'generated' / rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(data)
    for rel, data in before.items():
        path = ROOT / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        restored[rel.as_posix()] = hashlib.sha256(data).hexdigest()
    for rel in after.keys() - before.keys():
        path = (ROOT / rel).resolve()
        # 仅移除本次测试新建且已归档的证据文件；不递归删除、不碰用户源码或旧证据。
        if not path.is_relative_to(ROOT.resolve()) or not (OUT / 'generated' / rel).is_file():
            raise RuntimeError('GENERATED_EVIDENCE_RESTORE_SCOPE_MISMATCH')
        path.unlink()
    assert all((ROOT / rel).read_bytes() == data for rel, data in before.items())
    (OUT / 'restored-original-evidence.json').write_text(json.dumps({'bytewise_restored': True, 'sha256': restored}, indent=2) + '\n', encoding='utf-8')
print('RESULTS', OUT, flush=True)
raise SystemExit(0 if len(results) == len(commands) and all(x['exit_code'] == 0 for x in results) else 1)
