"""把两轮 Node-A CAN 实测数据提交到 A 分支并推送。

安全设计：使用临时 GIT_INDEX_FILE，从 A 分支的树载入索引，只追加本轮新增目录，
因此**不切换分支、不触碰工作区已修改的已跟踪文件、不影响当前检出的 P5 分支**。
"""
import os
import subprocess
import sys

REPO = r'E:\多参数心电监护仪系统-样机开发'
PARENT = '043a2901f369a2d52a3b0c80a102047d7e6c1dfc'
TARGET_DIR = 'doc/A/实测数据'
MESSAGE = """test(node-a): record two real-time CAN captures of vitals to Gateway-C

- passive RX-only observation on COM15 (bench CAN_ONLY_BENCH), no bytes written
- DTR/RTS held False; no S/G/T/P/D bench command, no flash, no reset
- decode per OD.c 0x1A02: 0x381 = SpO2/100 | PR/100 | NIBP_SYS/10 | NIBP_DIA/10
- two rounds: BP 112/76 and 109/78 mmHg; operator confirmed matching local screens
- NIBP 90 s CAN freshness reproduced twice (90.0 s / 90.0 s)
- zero bus errors in both rounds (TEC/REC/LEC/BOFF and RXQ overflows all 0)
- Gateway protocol layer stayed paused=1 (A=0, MODEL valid=0); not protocol acceptance
"""

index_path = os.path.join(os.environ['TEMP'], f'dsh_a_index_{os.getpid()}.tmp')
if os.path.exists(index_path):
    os.remove(index_path)
env = os.environ.copy()
env['GIT_INDEX_FILE'] = index_path


def git(*args, check=False, input_bytes=None):
    result = subprocess.run(['git', *args], cwd=REPO, capture_output=True,
                            env=env, input=input_bytes)
    out = result.stdout.decode('utf-8', 'replace').strip()
    err = result.stderr.decode('utf-8', 'replace').strip()
    if check and result.returncode != 0:
        raise SystemExit(f'FAILED: git {" ".join(args)}\n{err}')
    return result.returncode, out, err


# 0) 身份：沿用该提交的作者，避免提交者缺失
rc, author, _ = git('log', '-1', '--format=%an|%ae', PARENT, check=True)
name, email = author.split('|')
env.setdefault('GIT_AUTHOR_NAME', name)
env.setdefault('GIT_AUTHOR_EMAIL', email)
env.setdefault('GIT_COMMITTER_NAME', name)
env.setdefault('GIT_COMMITTER_EMAIL', email)

# 1) 列出要提交的文件
root = os.path.join(REPO, 'doc', 'A', '实测数据')
planned = []
for base, _, files in os.walk(root):
    for filename in files:
        full = os.path.join(base, filename)
        rel = os.path.relpath(full, REPO).replace(os.sep, '/')
        planned.append((rel, os.path.getsize(full)))
planned.sort()
total = sum(size for _, size in planned)
print(f'待提交 {len(planned)} 个文件，共 {total} 字节：')
for rel, size in planned:
    print(f'  {size:>9d}  {rel}')

# 2) 临时索引：载入 A 的树，只追加目标目录
git('read-tree', 'A', check=True)
rc, out, err = git('add', '--', TARGET_DIR)
if rc != 0:
    raise SystemExit(f'git add 失败（中文路径？）：{err}')
rc, tree, err = git('write-tree', check=True)
print(f'tree = {tree}')

# 3) 建提交
msg_path = os.path.join(os.environ['TEMP'], f'dsh_a_msg_{os.getpid()}.txt')
with open(msg_path, 'w', encoding='utf-8', newline='\n') as handle:
    handle.write(MESSAGE)
rc, commit, err = git('commit-tree', tree, '-p', PARENT, '-F', msg_path)
if rc != 0:
    raise SystemExit(f'commit-tree 失败：{err}')
print(f'commit = {commit}')

# 4) 移动 A 分支引用（A 未被检出，安全）
git('update-ref', 'refs/heads/A', commit, check=True)

# 5) 核对本次提交只新增了目标目录
rc, stat, _ = git('diff', '--stat', PARENT, commit)
print('--- 与父提交的差异 ---')
print(stat)

# 6) 推送
rc, out, err = git('push', 'origin', 'A')
print(f'--- git push origin A (exit {rc}) ---')
print(out or '(无 stdout)')
if err:
    print('stderr:', err)
sys.exit(0 if rc == 0 else 1)
