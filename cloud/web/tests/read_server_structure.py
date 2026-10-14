"""U4 只读结构检查：仅用现有 SSH 别名；不输出凭据/主机地址，不执行发布或重启。"""
import argparse
import json
import subprocess
from pathlib import Path

SCRIPT = r'''
import pathlib, json, subprocess, hashlib, re
out = {'inspection': 'READ_ONLY', 'services': {}}
for name in ['p6-ai.service','medical-monitor.service','medical-monitor-mqtt.service','nginx.service']:
    text = subprocess.check_output(['systemctl','show',name,'--property=ActiveState,SubState,MainPID,ExecMainStartTimestamp,WorkingDirectory,User'],text=True)
    out['services'][name] = dict(line.split('=',1) for line in text.splitlines() if '=' in line)
current = pathlib.Path('/opt/medical-monitor/current')
out['formal_release'] = str(current.resolve())
out['formal_index_sha256'] = hashlib.sha256((current/'web/dist/index.html').read_bytes()).hexdigest()
out['p6_index_sha256'] = hashlib.sha256(pathlib.Path('/opt/medical-monitor-p6/cloud/web/dist/index.html').read_bytes()).hexdigest()
files = sorted(pathlib.Path('/var/lib/medical-monitor-p6/20261014-budget').glob('call-*.json'))
out['budget_used'],out['budget_remaining'] = len(files),5-len(files)
out['budget_file_hashes'] = {p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in files}
out['nginx'] = []
# 只输出 medical-monitor 的 location，不展开其它应用配置，也不读取服务器环境文件。
for p in sorted(pathlib.Path('/etc/nginx').rglob('*')):
    if not p.is_file() or p.stat().st_size>1048576: continue
    text = p.read_text(errors='replace')
    blocks = re.findall(r'location\s+(?:[=~^*]+\s+)?(/medical-monitor[^\s{]*)\s*\{([^}]+)\}',text)
    if not blocks: continue
    entries=[]
    for location,body in blocks:
        entries.append({'location':location, 'loopback_ports':re.findall(r'127\.0\.0\.1:(\d+)',body),
                        'static_paths':re.findall(r'(?:alias|root)\s+(/opt/medical-monitor[^;\s]*)',body),
                        'websocket_upgrade':'Upgrade' in body})
    out['nginx'].append({'path':str(p), 'sha256':hashlib.sha256(p.read_bytes()).hexdigest(), 'entries':entries})
unit=pathlib.Path('/etc/systemd/system/p6-ai.service')
out['p6_unit_sha256']=hashlib.sha256(unit.read_bytes()).hexdigest()
print(json.dumps(out,ensure_ascii=False,indent=2))
'''


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--phase", choices=["before", "after"], required=True)
    args = parser.parse_args()
    r = subprocess.run(["ssh", "-o", "BatchMode=yes", "-o", "StrictHostKeyChecking=yes", "-o", "LogLevel=ERROR",
                        "tencent-codex", "sudo -n python3 -"], input=SCRIPT, text=True, encoding="utf-8", capture_output=True, timeout=30)
    # SSH 原始错误可能含真实主机地址，失败仅报告退出码。
    if r.returncode:
        raise SystemExit(f"read-only inspection failed, exit {r.returncode}")
    data = json.loads(r.stdout)
    out = Path(__file__).resolve().parents[2] / "evidence/p6-v2-ui"
    (out / f"server-{args.phase}.json").write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding="utf-8")
    print("read-only inspection PASS; budget",data["budget_used"],"/5; remaining",data["budget_remaining"])
    if args.phase == "after":
        before = json.loads((out/"server-before.json").read_text(encoding="utf-8"))
        assert before == data, "server structure/service/budget changed; inspect before finalizing"
        print("server structure, services, static entry, budget hashes unchanged")


if __name__ == "__main__":
    main()
