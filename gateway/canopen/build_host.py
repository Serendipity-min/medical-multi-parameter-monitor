"""Linux/CI 本机编译；Windows 可通过 WSL 调用同一脚本，无网络下载。"""
from pathlib import Path
import hashlib
import json
import subprocess
ROOT = Path(__file__).resolve().parent
VENDOR = ROOT.parent / 'third_party/CANopenNode'
def build(name, extra=()):
    out = ROOT / 'build' / name
    out.parent.mkdir(exist_ok=True)
    sources = [*sorted((ROOT/'src').glob('*.c')), ROOT.parent/'data_model/model.c', ROOT.parent/'storage/router.c', VENDOR/'CANopen.c', *sorted((VENDOR/'301').glob('*.c')), ROOT/'tests'/f'{name}.c', *extra]
    subprocess.run(['gcc', '-std=c11', '-g', '-O1', '-Wall', '-Wextra', '-Wno-unused-parameter', '-DCO_MULTIPLE_OD', '-I'+str(ROOT/'src'), '-I'+str(VENDOR), *map(str,sources), '-o', str(out)], check=True)
    return out
if __name__ == '__main__':
    # 构建前核验固定上游文件完整性，避免本机与 CI 使用不同的协议核心。
    manifest=json.loads((VENDOR/'upstream.json').read_text(encoding='utf-8'))
    for name,expected in manifest['sha256'].items():
        if hashlib.sha256((VENDOR/name).read_bytes()).hexdigest()!=expected:raise RuntimeError('CANopenNode pinned file mismatch: '+name)
    subprocess.run([str(build('protocol'))], check=True)
    subprocess.run([str(build('pipeline'))], check=True)
    # 保留完整跨语言夹具，下一条 CI 检查使用真实 C 输出验证现有 Backend。
    with (ROOT/'build/canonical.jsonl').open('w',encoding='utf-8') as output:
        subprocess.run([str(build('emit'))],stdout=output,check=True)
