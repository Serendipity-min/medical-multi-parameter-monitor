"""新C2.5 Host测试调度器；仅已安装GCC/纯合成夹具，未使用串口、socket或服务。"""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import sys

HERE = Path(__file__).resolve().parents[1]
ROOT = HERE.parents[4]
BASE = ROOT / 'gateway/mqtt/build/h16-diagnostic'

def linux(path):
    return '/mnt/' + path.drive[0].lower() + path.as_posix()[2:]

def main():
    runs = [p for p in BASE.glob('run-*') if (p / 'reports/build-summary.json').exists()]
    run = sorted(runs)[-1]
    out = BASE / 'host' / ('run-' + datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ'))
    out.mkdir(parents=True)
    receipt = {'kind': 'OFFLINE_DIAGNOSTIC_HOST_TESTS', 'hardware_activity': False,
               'broker_activity': False, 'security_gate': 'NOT_AUTHORIZED/NOT_RUN', 'tests': [], 'source_run': str(run)}
    commands = [('build_contract', [sys.executable, '-m', 'unittest', 'discover', '-s', str(HERE / 'tests'), '-p', 'test_build_contract.py', '-v'])]
    fixed = ['wsl', '-d', 'HERA-C3', '--', 'gcc', '-std=c11', '-O1', '-Wall', '-Wextra', '-Werror', '-DPROBE_HOST_TEST']
    compiler_jobs = [('probe', fixed + ['-I' + linux(HERE), linux(HERE / 'probe_events.c'),
                                      linux(HERE / 'tests/test_probe_host.c'), '-o', linux(out / 'probe')])]
    for variant in ('P4', 'P5'):
        source = run / (variant.lower() + '-source')
        mqtt = source / 'gateway/mqtt'
        core = source / 'gateway/third_party' / ('paho-embedded-c' if variant == 'P4' else 'coreMQTT')
        includes = [mqtt / 'src', HERE, ROOT / 'gateway/mqtt/tests/mocks']
        flags = ['-DPROBE_VARIANT_ID=' + variant[1]]
        # 联测只核对结果/测量包围，不作Host性能比较。两版本同用O0保留严格告警，
        # 避免P4原有未显式字段宽度的snprintf在Host配置注入后被O1跨函数推断为截断。
        # 原P4/P5代码不修补；ARM仍用冻结的Os选项，失败日志保留供审查。
        overlay_fixed = [arg for arg in fixed if arg != '-O1'] + ['-O0']
        files = [mqtt / 'src/gateway_transport.c', mqtt / 'src/probe_events.c',
                 source / 'gateway/data_model/model.c', source / 'gateway/storage/router.c',
                 ROOT / 'gateway/mqtt/tests/mocks/mock_esp.c', HERE / 'tests/test_overlay_host.c']
        if variant == 'P4':
            includes += [core / 'MQTTClient-C/src', core / 'MQTTPacket/src']
            flags += ['-DMQTTCLIENT_PLATFORM_HEADER=gateway_platform.h', '-DMAX_MESSAGE_HANDLERS=1']
            files += [HERE / 'tests/p4_host_platform.c', core / 'MQTTClient-C/src/MQTTClient.c']
            files += [core / 'MQTTPacket/src' / name for name in ('MQTTConnectClient.c', 'MQTTDeserializePublish.c',
                       'MQTTPacket.c', 'MQTTSerializePublish.c', 'MQTTSubscribeClient.c', 'MQTTUnsubscribeClient.c')]
        else:
            includes += [core / 'source/include', core / 'source/interface']
            flags += ['-DGATEWAY_MQTT_HOST_TEST']
            files += [mqtt / 'src/mqtt_transport_adapter.c']
            files += [core / 'source' / name for name in ('core_mqtt.c', 'core_mqtt_serializer.c', 'core_mqtt_state.c')]
        compiler_jobs.append((variant + '-overlay', [*overlay_fixed, *flags, *['-I' + linux(p) for p in includes], *map(linux, files), '-o', linux(out / (variant + '-overlay'))]))
        compiler_jobs.append((variant + '-heap', [*fixed, *flags, '-I' + linux(HERE), linux(HERE / 'probe_events.c'),
                              linux(mqtt / 'src/heap.c'), linux(HERE / 'tests/test_heap_host.c'), '-o', linux(out / (variant + '-heap'))]))
    for name, command in compiler_jobs:
        result = subprocess.run(command, capture_output=True, text=True, encoding='utf-8', errors='replace')
        (out / (name + '-compile.log')).write_text(result.stdout + result.stderr, encoding='utf-8')
        if result.returncode:
            print(result.stderr); raise SystemExit(result.returncode)
        commands.append((name, ['wsl', '-d', 'HERA-C3', '--', linux(out / name)]))
    for name, command in commands:
        result = subprocess.run(command, capture_output=True, text=True, encoding='utf-8', errors='replace')
        log = out / (name + '.log'); log.write_text(result.stdout + result.stderr, encoding='utf-8')
        if result.returncode:
            print(result.stdout + result.stderr); raise SystemExit(result.returncode)
        cases = result.stdout.splitlines()
        if name == 'build_contract':
            import re
            count = int(re.search(r'Ran (\d+) tests', result.stderr)[1])
        else:
            count = sum(line.startswith('PASS ') for line in cases)
        receipt['tests'].append({'name': name, 'exit_code': result.returncode, 'cases': count,
                                 'command': command, 'log_sha256': hashlib.sha256(log.read_bytes()).hexdigest()})
        print(f'{name}: {count} PASS', flush=True)
    receipt['passed'] = sum(row['cases'] for row in receipt['tests'])
    receipt['input_sha256'] = {file.relative_to(ROOT).as_posix(): hashlib.sha256(file.read_bytes()).hexdigest()
                              for file in HERE.rglob('*') if file.is_file() and file.suffix in ('.c', '.h', '.py', '.patch')}
    (out / 'host-summary.json').write_text(json.dumps(receipt, indent=2), encoding='utf-8')
    print(json.dumps({'new_diagnostic_tests': receipt['passed'], 'source_run': str(run), 'receipt': str(out / 'host-summary.json')}))

if __name__ == '__main__':
    main()
