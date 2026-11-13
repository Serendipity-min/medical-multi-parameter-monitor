"""B4普通软件回归，所有失败保留真实退出码；不接SDK、串口或网络服务。"""
from pathlib import Path
import argparse
import datetime
import hashlib
import json
import subprocess
import os
import sys

ROOT = Path(__file__).resolve().parents[2]
VENDOR = ROOT / 'gateway/third_party/CANopenNode'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--temperature', action='store_true', help='真实温度解析器/生产者的纯Host变体')
    parser.add_argument('--out', type=Path, help='新的独立输出目录')
    args = parser.parse_args()
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    out = (args.out or ROOT / 'node-b/build' / ('b4-host-' + stamp)).resolve()
    out.mkdir(parents=True, exist_ok=False)
    gcc = 'C:/mingw64/bin/gcc.exe'
    cases = []

    def run(name, command, expected=0, input_data=None):
        env = dict(os.environ)
        if name.startswith('dual-gateway'):
            env['B4_CANONICAL_OUT'] = str(out / (name + '-canonical.jsonl'))
        p = subprocess.run(list(map(str, command)), env=env, input=input_data, capture_output=True, cwd=ROOT, timeout=180)
        log = out / (name + '.log'); log.write_bytes(p.stdout + p.stderr)
        cases.append({'name': name, 'exit_code': p.returncode, 'expected_exit': expected,
                      'passed': p.returncode == expected, 'command': list(map(str, command)),
                      'log_sha256': hashlib.sha256(log.read_bytes()).hexdigest()})
        print(name, p.returncode, flush=True)
        if p.returncode != expected:
            print((p.stdout + p.stderr).decode('utf-8', errors='replace')[-5000:])
        return p.returncode == expected

    core = [VENDOR / 'CANopen.c', *sorted((VENDOR / '301').glob('*.c'))]
    b = ROOT / 'node-b/canopen'
    includes = ['-I' + str(b), '-I' + str(VENDOR), '-I' + str(ROOT / 'node-b/firmware/biov2/实验固件/HARDWARE')]
    sources = [*core, VENDOR / '303/CO_LEDs.c', b / 'OD.c', b / 'b_canopen_app.c',
               ROOT / 'node-b/tests/b4_host_driver.c', ROOT / 'node-b/tests/b4_node_protocol.c',
               ROOT / 'node-b/firmware/biov2/实验固件/HARDWARE/bio_v2.c']
    temperature_sources = [ROOT / 'node-b/temperature/gy641.c'] if args.temperature else []
    temperature_flags = ['-DB_TEMP_ENABLED', '-I' + str(ROOT / 'node-b/temperature')] if args.temperature else []
    if run('compile-node-b', [gcc, '-std=c99', '-O2', '-DB4_HOST', '-Wall', '-Wextra', '-Wno-unused-parameter',
                             *temperature_flags, *includes, *sources, *temperature_sources, '-lm', '-o', out / 'b4_node.exe']):
        run('node-b-protocol', [out / 'b4_node.exe', out / 'b2-synthetic-wire.txt'])
        run('node-b-jitter-protocol', [out / 'b4_node.exe', out / 'b2-jitter-wire.txt', 'jitter'])
    # 独立单位测试复用真实B队列/PDO、网关序列化及Backend，避免只验证帮助函数。
    units_sources = [p for p in sources if p.name != 'b4_node_protocol.c'] + [
        ROOT / 'node-b/tests/b4_ecg_units.c', ROOT / 'gateway/data_model/model.c',
        ROOT / 'gateway/third_party/coreMQTT/source/core_mqtt_serializer.c']
    if run('compile-ecg-gain4', [gcc, '-std=c99', '-O2', '-DB4_HOST', '-DMP_FRAME_MAX_SAMPLES=100',
            '-Wall', '-Wextra', '-Wno-unused-parameter', *includes,
            '-I' + str(ROOT / 'gateway/data_model'),
            '-I' + str(ROOT / 'gateway/third_party/coreMQTT/source/include'),
            '-I' + str(ROOT / 'gateway/third_party/coreMQTT/source/interface'),
            '-I' + str(ROOT / 'gateway/mqtt/src'), *units_sources, '-lm', '-o', out / 'b4_units.exe']):
        run('ecg-gain4-wire-and-json', [out / 'b4_units.exe', out / 'gain4-mv.jsonl'])
        run('ecg-gain4-existing-backend', [sys.executable, ROOT / 'node-b/tests/b4_ecg_json.py', out / 'gain4-mv.jsonl'])
    dual = ROOT / 'gateway/dual_can'
    g_sources = [*core, ROOT / 'gateway/canopen/src/mp_od.c', dual / 'b4_bus.c', dual / 'b4_gateway.c',
                 ROOT / 'gateway/data_model/model.c', ROOT / 'gateway/storage/router.c', dual / 'tests/simulator.c',
                 ROOT / 'gateway/third_party/coreMQTT/source/core_mqtt_serializer.c']
    if (dual / 'tests/simulator.c').exists() and run('compile-dual-gateway', [gcc, '-std=c11', '-O2',
            '-DCO_MULTIPLE_OD', '-DMP_FRAME_MAX_SAMPLES=100', '-DMP_CACHE_CAPACITY=64',
            '-Wall', '-Wextra', '-Wno-unused-parameter', '-Werror',
            '-I' + str(dual), '-I' + str(ROOT / 'gateway/canopen/src'), '-I' + str(VENDOR),
            '-I' + str(ROOT / 'gateway/third_party/coreMQTT/source/include'),
            '-I' + str(ROOT / 'gateway/third_party/coreMQTT/source/interface'), '-I' + str(ROOT / 'gateway/mqtt/src'),
            *g_sources, '-o', out / 'b4_gateway.exe']):
        extra = ['temperature'] if args.temperature else []
        run('dual-gateway', [out / 'b4_gateway.exe', out / 'b2-synthetic-wire.txt', 'normal', *extra])
        run('dual-gateway-5s-mqtt-pressure', [out / 'b4_gateway.exe', out / 'b2-synthetic-wire.txt', 'pressure', *extra])
        run('dual-gateway-jitter', [out / 'b4_gateway.exe', out / 'b2-jitter-wire.txt', 'normal', *extra])
        backend = [sys.executable, ROOT / 'node-b/tests/b4_backend.py', out / 'dual-gateway-canonical.jsonl']
        if args.temperature:
            backend += ['--temperature', '--snapshots', out / 'tri-host-snapshots.json']
        if run('c-to-existing-backend', backend) and args.temperature:
            run('existing-ui-from-Hub-snapshots', ['node', ROOT / 'cloud/web/tests/tri-host-run.mjs',
                out / 'tri-host-snapshots.json', out / 'tri-host.test.cjs'])
    run('i2s2-conflict-negative', [gcc, '-E', '-x', 'c', '-I' + str(dual), '-include', 'b4_resources.h',
        '-DMP_FRAME_MAX_SAMPLES=100', '-DMP_CACHE_CAPACITY=64', '-DB4_I2S2_PB12_PB13=1', '-'], expected=1, input_data=b'')
    run('mixed-model-abi-negative', [gcc, '-E', '-x', 'c', '-I' + str(dual), '-include', 'b4_resources.h',
        '-DMP_FRAME_MAX_SAMPLES=250', '-DMP_CACHE_CAPACITY=64', '-'], expected=1, input_data=b'')
    report = {'version': 'B4-0.3', 'scope': 'HOST_OFFLINE_SYNTHETIC_NOT_HARDWARE', 'cases': cases,
              'temperature_enabled': args.temperature,
              'status': 'PASS' if len(cases) == (14 if args.temperature else 13) and all(c['passed'] for c in cases) else 'FAIL',
              'source_sha256': {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
                                for p in sources + units_sources + g_sources + temperature_sources + [b / 'ecg_units.h',
                                    ROOT / 'node-b/temperature/gy641.h', ROOT / 'node-b/temperature/b_temperature.h',
                                    ROOT / 'node-b/tests/b4_backend.py', ROOT / 'node-b/tests/b4_ecg_json.py',
                                    ROOT / 'cloud/backend/app/adapters.py', ROOT / 'cloud/backend/app/hub.py',
                                    ROOT / 'cloud/backend/app/models.py', ROOT / 'cloud/web/tests/tri-host-run.mjs',
                                    ROOT / 'cloud/web/tests/tri-host.test.ts', ROOT / 'cloud/web/src/model/viewModel.ts',
                                    ROOT / 'cloud/web/src/state/monitorStore.ts', ROOT / 'cloud/web/src/state/sessionHistory.ts',
                                    ROOT / 'cloud/web/src/types.ts', Path(__file__)] if p.exists()}}
    # 原始编码/Canonical输出属于合成夹具，与真实E3原码分目录、分身份归档。
    report['fixture_sha256'] = {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                               for p in out.glob('*') if p.suffix in ('.txt', '.jsonl')}
    (out / 'executed-runner.py').write_bytes(Path(__file__).read_bytes())
    (out / 'receipt.json').write_text(json.dumps(report, indent=2) + '\n')
    print(str(out.relative_to(ROOT)) if out.is_relative_to(ROOT) else out.name)
    return int(report['status'] != 'PASS')


if __name__ == '__main__':
    raise SystemExit(main())
