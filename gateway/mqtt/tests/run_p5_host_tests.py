"""用既有 GCC 编译真实 P5 源码的普通功能用例；不启用 sanitizer 或扫描器。"""
import argparse
import json
import re
import hashlib
import os
from pathlib import Path
import subprocess
import sys
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[3]
MQTT = ROOT / 'gateway/mqtt'
VENDOR = ROOT / 'gateway/third_party/coreMQTT'


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--asan-ubsan', action='store_true')
    parser.add_argument('--authorize-sanitizers', action='store_true')
    parser.add_argument('--with-can-capture', action='store_true')
    args = parser.parse_args()
    # 普通CI默认无sanitizer；安全模式必须在G1授权后显式选择，不能隐式升级普通测试。
    if args.asan_ubsan != args.authorize_sanitizers:
        parser.error('ASAN_UBSAN_REQUIRES_EXPLICIT_AUTHORIZATION')
    if sys.platform == 'win32':
        # 只复用已安装 HERA-C3 的 GCC，不安装工具；argv 直接传递，避免 shell 拼接路径。
        linux_root = '/mnt/' + ROOT.drive[0].lower() + ROOT.as_posix()[2:]
        commit = subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip()
        # Windows worktree 的 .git 绝对路径无法由 Linux Git 解析，仅传公开提交标识。
        return subprocess.call(['wsl', '-d', 'HERA-C3', '--cd', linux_root, '--',
                                'env', 'P5_COMMIT=' + commit,
                                'python3', 'gateway/mqtt/tests/run_p5_host_tests.py', *sys.argv[1:]])
    # Gate只复制源码、不带.git；G1必须从批准HEAD注入P5_COMMIT，不能造一个快照提交冒充源身份。
    source_commit = os.environ.get('P5_COMMIT') or subprocess.check_output(
        ['git', 'rev-parse', 'HEAD'], text=True).strip()
    if not re.fullmatch(r'[0-9a-f]{40}', source_commit):
        parser.error('EXACT_SOURCE_COMMIT_REQUIRED')
    if args.with_can_capture:
        # bear包围此入口时同时捕获原CAN/Router及活动coreMQTT的真实编译命令。
        subprocess.run([sys.executable, str(ROOT / 'gateway/canopen/build_host.py')], check=True)
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    out = MQTT / 'build/p5-tests' / stamp
    out.mkdir(parents=True, exist_ok=True)
    report = {'started_at': datetime.now(timezone.utc).isoformat(), 'synthetic': True,
              'security_gate': 'AUTHORIZED_BOUNDED_ASAN_UBSAN' if args.asan_ubsan else 'NOT_AUTHORIZED/NOT_RUN', 'tests': []}
    report['commit'] = source_commit
    report['asan_ubsan'] = args.asan_ubsan
    report['with_can_capture'] = args.with_can_capture
    report['compiler'] = subprocess.check_output(['gcc', '--version'], text=True).splitlines()[0]
    # 文件摘要绑定本次真实编译输入；即使提交后再增补文档，也不混淆测试代码版本。
    inputs = [*sorted((MQTT / 'src').glob('*.[ch]')),
              *sorted((MQTT / 'tests').rglob('*.[ch]')), VENDOR / 'upstream.json',
              ROOT / 'gateway/data_model/model.c', ROOT / 'gateway/storage/router.c']
    report['source_sha256'] = {p.relative_to(ROOT).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
                               for p in inputs}
    suites = {'transport': ['mqtt_transport_adapter.c'],
              'assert_fault': ['gateway_assert.c'],
              'qos_ack': ['mqtt_transport_adapter.c', 'gateway_transport.c'],
              'connect_keepalive': ['mqtt_transport_adapter.c', 'gateway_transport.c']}
    for name, project_sources in suites.items():
        command = ['gcc', '-std=c11', '-O1', '-Wall', '-Wextra', '-Werror',
                   '-I' + str(MQTT / 'src'), '-I' + str(VENDOR / 'source/include'),
                   '-I' + str(VENDOR / 'source/interface'),
                   *[str(MQTT / 'src' / source) for source in project_sources],
                   str(MQTT / f'tests/test_p5_{name}.c'), '-o', str(out / name)]
        if name == 'assert_fault':
            command[1:1] = ['-DGATEWAY_ASSERT_HOST_TEST']
        elif name != 'transport':
            # 编译同一官方库与同一模型/Router，只替换 ESP 字节 I/O 和固定合成配置。
            command[1:1] = ['-DGATEWAY_MQTT_HOST_TEST',
                            str(MQTT / 'tests/mocks/mock_esp.c'),
                            str(ROOT / 'gateway/data_model/model.c'),
                            str(ROOT / 'gateway/storage/router.c'),
                            *[str(VENDOR / 'source' / source) for source in
                              ['core_mqtt.c', 'core_mqtt_serializer.c', 'core_mqtt_state.c']]]
        if args.asan_ubsan:
            # 同一42项固定夹具编译真实活动源码；编译和链接一起启用，不关闭任何诊断。
            command[1:1] = ['-fsanitize=address,undefined', '-fno-omit-frame-pointer', '-g']
        compiled = subprocess.run(command, text=True, capture_output=True)
        (out / f'{name}-compile.log').write_text(compiled.stdout + compiled.stderr, encoding='utf-8')
        if compiled.returncode:
            report['result'] = 'FAIL'
            report['compile_failure'] = name
            (out / 'result.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
            print(compiled.stderr)
            return 1
        test_environment = os.environ.copy()
        if args.asan_ubsan:
            test_environment.update(ASAN_OPTIONS='detect_leaks=1:halt_on_error=1',
                                    UBSAN_OPTIONS='halt_on_error=1:print_stacktrace=1')
        result = subprocess.run([str(out / name)], text=True, capture_output=True,
                                env=test_environment, timeout=120 if args.asan_ubsan else None)
        (out / f'{name}.log').write_text(result.stdout + result.stderr, encoding='utf-8')
        report['tests'].append({'suite': name, 'exit_code': result.returncode,
                                'cases': result.stdout.splitlines(), 'command': command})
        print(result.stdout, end='')
        if result.returncode:
            print(result.stderr)
            report['result'] = 'FAIL'
            (out / 'result.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
            return 1
    report['result'] = 'PASS'
    report['passed'] = sum(len(t['cases']) for t in report['tests'])
    (out / 'result.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    (out.parent / 'latest.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    print('P5 ordinary host checks PASS:', report['passed'])
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
