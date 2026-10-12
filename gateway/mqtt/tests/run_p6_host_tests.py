"""P6 普通脱机回归；编译生产驱动/Transport/coreMQTT，不运行任何安全扫描。"""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[3]
MQTT = ROOT / 'gateway/mqtt'
VENDOR = ROOT / 'gateway/third_party/coreMQTT'


def main():
    if sys.platform == 'win32':
        linux_root = '/mnt/' + ROOT.drive[0].lower() + ROOT.as_posix()[2:]
        commit = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()
        return subprocess.call(['wsl', '-d', 'HERA-C3', '--cd', linux_root, '--', 'env', 'P6_COMMIT=' + commit,
                                'python3', 'gateway/mqtt/tests/run_p6_host_tests.py'])
    out = ROOT / 'build/p6/host' / datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    out.mkdir(parents=True)
    report = {'parent_commit': os.environ.get('P6_COMMIT') or subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
              'security_gate': 'NOT_RUN', 'hardware': 'NOT_RUN', 'suites': []}
    inputs = [MQTT / 'src/p6_voice.c', MQTT / 'src/p6_voice.h', MQTT / 'src/p6_config.h',
              MQTT / 'src/gateway_transport.c', MQTT / 'tests/mocks/mock_esp.c',
              MQTT / 'tests/test_p6_voice.c', MQTT / 'tests/test_p6_mqtt.c']
    report['source_sha256'] = {p.relative_to(ROOT).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest() for p in inputs}
    for suite in ('voice', 'mqtt'):
        sources = [MQTT / 'src/p6_voice.c', MQTT / f'tests/test_p6_{suite}.c']
        if suite == 'mqtt':
            sources += [MQTT / 'src/gateway_transport.c', MQTT / 'src/mqtt_transport_adapter.c', MQTT / 'tests/mocks/mock_esp.c',
                        ROOT / 'gateway/data_model/model.c', ROOT / 'gateway/storage/router.c',
                        *[VENDOR / 'source' / p for p in ('core_mqtt.c', 'core_mqtt_serializer.c', 'core_mqtt_state.c')]]
        command = ['gcc', '-std=c11', '-O1', '-Wall', '-Wextra', '-Werror', '-DGATEWAY_P6_VOICE=1', '-DGATEWAY_MQTT_HOST_TEST',
                   '-I' + str(MQTT / 'src'), '-I' + str(VENDOR / 'source/include'), '-I' + str(VENDOR / 'source/interface'),
                   *map(str, sources), '-o', str(out / suite)]
        compiled = subprocess.run(command, text=True, capture_output=True)
        (out / (suite + '-compile.log')).write_text(compiled.stdout + compiled.stderr)
        if compiled.returncode: print(compiled.stderr); return compiled.returncode
        result = subprocess.run([str(out / suite)], text=True, capture_output=True, timeout=30)
        (out / (suite + '.log')).write_text(result.stdout + result.stderr)
        report['suites'].append({'suite': suite, 'exit_code': result.returncode, 'cases': result.stdout.splitlines()})
        print(result.stdout, end='')
        if result.returncode: print(result.stderr); break
    report['exit_code'] = result.returncode
    report['passed'] = sum(len(s['cases']) for s in report['suites'])
    report['result'] = 'HOST_VERIFIED' if not result.returncode else 'FAIL'
    (out / 'result.json').write_text(json.dumps(report, indent=2))
    (out.parent / 'latest.json').write_text(json.dumps(report, indent=2))
    return result.returncode


if __name__ == '__main__': raise SystemExit(main())
