"""仅读取路由器观测进程的脱敏状态；不访问凭据或改变服务。"""
from pathlib import Path
from datetime import datetime,timezone
import json,subprocess

root=Path(__file__).resolve().parents[3]
ref=json.loads(Path('E:/medical-monitor-h3-private/r2-router-active-window-reference.json').read_text())
keys=('state','started_utc','updated_utc','elapsed_s','continuous_online_s','longest_online_s',
      'mqtt_received','mqtt_invalid','wss_snapshots','node_b_online_seen','invalid_values_visible',
      'transitions','sessions','online_interruptions')
# 远端只返回固定元数据白名单，不取包含配置的文件，也不打印SSH错误详情。
code="import json\nfrom pathlib import Path\np=Path('/var/lib/medical-monitor-p6/h3-20261019')/('r2c-'+"+repr(ref['isolation_tag'])+")/'cold-status.json'\nd=json.loads(p.read_text())\nprint(json.dumps({k:d.get(k) for k in "+repr(keys)+"}))\n"
r=subprocess.run(['ssh','tencent-codex','sudo -n python3 -'],input=code,text=True,capture_output=True,timeout=30)
try:value=json.loads(r.stdout)
except ValueError:value={'exit_code':r.returncode or 1,'failure_code':'STATUS_OUTPUT_SUPPRESSED'}
stamp=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
with (root/'gateway/physical_can/evidence/h3-r2/router-migration'/('status-'+stamp+'.json')).open('x') as f:json.dump(value,f,indent=2)
print(json.dumps(value))
