"""只准备隔离的测试解释器，不安装到项目运行 venv，也不执行任何扫描。"""
import argparse
import json
import subprocess
import sys
from pathlib import Path
from common import HERE, bridge, dump, environment, execute, output_root
from adapters import test_python

def main():
    bridge()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo', type=Path, required=True)
    parser.add_argument('--requirements', required=True)
    parser.add_argument('--constraints')
    parser.add_argument('--authorized-machine', action='store_true')
    args = parser.parse_args()
    if not args.authorized_machine:
        parser.error('explicit machine setup authorization required')
    repo = args.repo.resolve()
    for rel in (args.requirements, args.constraints):
        if rel and not (repo / rel).resolve().is_relative_to(repo):
            parser.error('requirement paths must remain in target repository')
    python = test_python(repo)
    python.parent.parent.mkdir(parents=True, exist_ok=True)
    if not python.exists():
        subprocess.run([sys.executable, '-m', 'venv', str(python.parent.parent)], check=True)
    command = [python, '-m', 'pip', 'install', '--index-url', 'https://pypi.org/simple', '-r', repo / args.requirements]
    if args.constraints:
        command += ['-c', repo / args.constraints]
    result = execute(command, repo, output_root() / 'prepare/raw', 'test-environment', 600)
    print(json.dumps(result))
    return 0 if result['status'] == 'OK' else 3

if __name__ == '__main__':
    raise SystemExit(main())
