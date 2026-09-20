"""安装验收用最小合成仓库：真实工具与 ASan/UBSan 的正向通路，不扫描业务代码。"""
import argparse
import json
from pathlib import Path
import subprocess
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from common import HERE, bridge, dump, output_root

def main():
    bridge()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--authorize', action='store_true')
    args = parser.parse_args()
    if not args.authorize:
        parser.error('explicit installation verification authorization required')
    root = output_root() / 'smoke-fixture'
    root.mkdir(exist_ok=False)
    (root / 'src').mkdir()
    # 合成输入只验证普通计算与 sanitizer 运行库，不构造错误内存访问。
    (root / 'src/smoke.c').write_text('int main(void) { int values[3] = {1, 2, 3}; return values[0] + values[1] + values[2] == 6 ? 0 : 1; }\n')
    (root / 'src/example.py').write_text('assert sum([1, 2, 3]) == 6\n')
    dump(root / '.security-gate.json', {'name':'installation-smoke','source_roots':['src'],
        'requirements':[], 'npm_roots':[], 'first_party_c':[], 'commands':[
            {'name':'asan-ubsan-build','argv':['gcc','-fsanitize=address,undefined','-fno-pie','-no-pie','src/smoke.c','-o','smoke'], 'modes':['quick'],'mandatory':True},
            {'name':'asan-ubsan-test','argv':['./smoke'],'modes':['quick'],'mandatory':True},
            {'name':'python-test','argv':[sys.executable,'src/example.py'],'modes':['quick'],'mandatory':True}]})
    subprocess.run(['git','init','-q',str(root)],check=True)
    subprocess.run(['git','-C',str(root),'add','.'],check=True)
    subprocess.run(['git','-C',str(root),'-c','user.name=Gate Fixture','-c','user.email=gate@example.com','commit','-qm','synthetic installation fixture'],check=True)
    return subprocess.call([sys.executable, str(HERE/'gate.py'),'quick','--repo',str(root),'--authorize'])

if __name__ == '__main__':
    raise SystemExit(main())
