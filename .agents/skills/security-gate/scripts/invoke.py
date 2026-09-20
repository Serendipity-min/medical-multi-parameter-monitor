"""定位集中库或导出项目中的唯一执行器；参数原样转发，不自行决定扫描授权。"""
from pathlib import Path
import subprocess
import sys

def main():
    for parent in Path(__file__).resolve().parents:
        gate = parent / 'tools/security_gate/gate.py'
        if gate.is_file():
            return subprocess.call([sys.executable, str(gate), *sys.argv[1:]])
    print('Security Gate runner missing: restore the complete exported package.', file=sys.stderr)
    return 3

if __name__ == '__main__':
    raise SystemExit(main())
