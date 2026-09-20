"""本机固定 MQTT 回归：真实 Paho 实现 + 内存 stub，不使用网络/串口或随机输入。"""

import argparse
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
PACKET = Path('gateway/third_party/paho-embedded-c/MQTTPacket/src')
CLIENT = Path('gateway/third_party/paho-embedded-c/MQTTClient-C/src')
TESTS = Path('gateway/canopen/tests')
BUILD = Path('gateway/canopen/build/security-regression')

# 与固件相同的客户端 packet 实现；formatter 只进入专门的本机测试二进制。
PACKET_SOURCES = [
    PACKET / 'MQTTConnectClient.c',
    PACKET / 'MQTTDeserializePublish.c',
    PACKET / 'MQTTPacket.c',
    PACKET / 'MQTTSerializePublish.c',
    PACKET / 'MQTTSubscribeClient.c',
    PACKET / 'MQTTUnsubscribeClient.c',
]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--cc', default='gcc', help='本机已有的 C 编译器，不自动安装')
    args = parser.parse_args()
    output = ROOT / BUILD
    output.mkdir(parents=True, exist_ok=True)
    flags = [
        '-std=c11', '-g', '-O1', '-Wall', '-Wextra', '-Werror',
        '-Wno-unused-parameter', '-fsanitize=address,undefined',
        '-fno-sanitize-recover=all', '-fno-omit-frame-pointer',
        '-ffunction-sections', '-fdata-sections', '-Wl,--gc-sections',
        '-fno-pie', '-no-pie',
        '-DMQTTCLIENT_PLATFORM_HEADER=mqtt_host_platform.h',
        '-DMAX_MESSAGE_HANDLERS=1',
        f'-I{PACKET.as_posix()}', f'-I{CLIENT.as_posix()}', f'-I{TESTS.as_posix()}',
    ]
    suites = [
        ('test_mqtt_bounded', 29, PACKET_SOURCES),
        ('test_mqtt_client_bounds', 10, [*PACKET_SOURCES, CLIENT / 'MQTTClient.c']),
        ('test_mqtt_formatter', 3, [*PACKET_SOURCES, PACKET / 'MQTTFormat.c']),
    ]
    # 仅覆盖子进程的 sanitizer 选项，不改变用户环境变量或平台配置。
    env = os.environ.copy()
    env['ASAN_OPTIONS'] = 'detect_leaks=1:halt_on_error=1'
    env['UBSAN_OPTIONS'] = 'halt_on_error=1:print_stacktrace=1'
    results = []
    for name, count, sources in suites:
        binary = BUILD / name
        command = [args.cc, *flags, *[path.as_posix() for path in sources],
                   (TESTS / f'{name}.c').as_posix(), '-o', binary.as_posix()]
        # 每次重建并保留编译/执行记录；失败也写结果摘要，禁止把异常算作 PASS。
        compiled = subprocess.run(command, cwd=ROOT, env=env, text=True,
                                  stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        (output / f'{name}.build.log').write_text(compiled.stdout, encoding='utf-8')
        run_code = None
        if compiled.returncode == 0:
            tested = subprocess.run([binary.as_posix()], cwd=ROOT, env=env, text=True,
                                    stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
            run_code = tested.returncode
            (output / f'{name}.run.log').write_text(tested.stdout, encoding='utf-8')
        status = 'PASS' if compiled.returncode == 0 and run_code == 0 else 'FAIL'
        results.append({'suite': name, 'fixed_cases': count, 'status': status,
                        'compile_exit': compiled.returncode, 'run_exit': run_code,
                        'command': command})
        print(f'{name}: {status} ({count} fixed cases)')

    summary = {'sanitizers': ['ASan', 'UBSan'], 'fixed_cases': sum(s[1] for s in suites),
               'network_or_hardware': False, 'suites': results}
    (output / 'results.json').write_text(json.dumps(summary, indent=2) + '\n', encoding='utf-8')
    return 0 if all(item['status'] == 'PASS' for item in results) else 1


if __name__ == '__main__':
    sys.exit(main())
