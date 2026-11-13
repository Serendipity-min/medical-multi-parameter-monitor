"""GEMINI-P5-001 本地 E 命令空指针守卫专项测试运行脚本。
直接编译并执行 test_p5_emcy_console.c，调用生产 service() 分支进行负向与恢复验证。
"""
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[3]
MQTT = ROOT / 'gateway/mqtt'
CANOPEN = ROOT / 'gateway/canopen'
DATA_MODEL = ROOT / 'gateway/data_model'
STORAGE = ROOT / 'gateway/storage'
CANOPEN_NODE = ROOT / 'gateway/third_party/CANopenNode'


def main() -> int:
    if sys.platform == 'win32':
        linux_root = '/mnt/' + ROOT.drive[0].lower() + ROOT.as_posix()[2:]
        return subprocess.call([
            'wsl', '-d', 'HERA-C3', '--cd', linux_root, '--',
            'python3', 'gateway/mqtt/tests/test_p5_emcy_console.py', *sys.argv[1:]
        ])

    out = MQTT / 'build/p5-tests/emcy_console'
    out.parent.mkdir(parents=True, exist_ok=True)
    c_source = MQTT / 'tests/test_p5_emcy_console.c'

    compile_cmd = [
        'gcc', '-std=c11', '-O1', '-Wall', '-Wextra', '-Werror',
        '-DCO_MULTIPLE_OD',
        f'-I{MQTT / "src"}',
        f'-I{CANOPEN / "src"}',
        f'-I{DATA_MODEL}',
        f'-I{STORAGE}',
        f'-I{CANOPEN_NODE}',
        str(c_source),
        '-o', str(out),
    ]

    compiled = subprocess.run(compile_cmd, capture_output=True, text=True)
    if compiled.returncode != 0:
        print("Compile failed:", compiled.stderr, file=sys.stderr)
        return compiled.returncode

    res = subprocess.run([str(out)], capture_output=True, text=True)
    print(res.stdout, end='')
    if res.returncode != 0:
        print(res.stderr, file=sys.stderr)
    return res.returncode


if __name__ == '__main__':
    raise SystemExit(main())
