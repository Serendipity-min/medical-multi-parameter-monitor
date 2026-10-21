"""F0只读接管：新证据目录、外部租约和服务器内存查询，绝不打开开发板。"""
import hashlib
import inspect
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from .ac_readonly import closeout_snapshot
from .ac_runtime_readonly import snapshot
from .r2_audit import production_snapshot

ROOT = Path(__file__).resolve().parents[3]
BASE = '5a4cfd25753b5fe8f812d3acc6494aa898e1adb1'
OUT = ROOT / 'gateway/physical_can/evidence/h3-ac-final'
PRIVATE = Path('E:/medical-monitor-h3-private/ac-final')


def main():
    started = datetime.now(timezone.utc).isoformat()
    OUT.mkdir(parents=True, exist_ok=True)
    PRIVATE.mkdir(parents=True, exist_ok=True)
    head = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()
    remote = subprocess.check_output(['git', 'ls-remote', 'origin', 'refs/heads/dev/h3-nodea-cloud-ai-integration'], cwd=ROOT, text=True).split()[0]
    if head != BASE or remote != BASE:
        raise RuntimeError('BASELINE_DRIFT_STOP')
    lease = Path('E:/medical-monitor-h3-private/ac-closeout/single-writer.json')
    previous = json.loads(lease.read_text())
    if previous.get('write_lease_active'):
        raise RuntimeError('EXISTING_WRITER_STOP')
    # 归档上轮原件；只依据明确交接和租约认领，不宣称能排除所有编辑器写入。
    with (PRIVATE / 'previous-single-writer.json').open('x') as f:
        json.dump(previous, f, indent=2)
    lease.write_text(json.dumps({'executor': 'Codex', 'contract': 'MPM-H3-004-R1.0',
        'worktree': str(ROOT), 'started_utc': started, 'write_lease_active': True,
        'state': 'F0_SOFTWARE_ONLY', 'owner_basis': 'EXPLICIT_UNIQUE_EXECUTOR_ASSIGNMENT'}, indent=2))
    outputs = {}
    for label, functions, call in (
        ('cloud', [production_snapshot, closeout_snapshot], 'closeout_snapshot'),
        ('runtime', [snapshot], 'snapshot')):
        code = '\n'.join(inspect.getsource(f) for f in functions)
        code += '\nimport json\nprint(json.dumps(' + call + '()))\n'
        r = subprocess.run(['ssh', 'tencent-codex', 'sudo -n python3 -'],
                           input=code, capture_output=True, text=True, timeout=60)
        try:
            data = json.loads(r.stdout)
        except ValueError:
            data = {'exit_code': r.returncode or 1, 'failure': 'REMOTE_OUTPUT_SUPPRESSED'}
        # 远端函数仅返回摘要；stderr不进入Git，避免SSH失败时暴露连接信息。
        data['ssh_exit_code'] = r.returncode
        raw = json.dumps(data, indent=2).encode()
        with (OUT / ('F0-' + label + '.json')).open('xb') as f:
            f.write(raw)
        outputs[label] = {'exit_code': data.get('exit_code', 1),
                          'sha256': hashlib.sha256(raw).hexdigest()}
    receipt = {'stage': 'F0', 'gate': 'READONLY_COMPLETE_FIELD_INPUT_PENDING',
        'source_commit': head, 'device_or_runtime_sha': None, 'source_label': 'NO_ACQUISITION',
        'window_start_utc': started, 'window_end_utc': datetime.now(timezone.utc).isoformat(),
        'command': 'python -m cloud.deploy.h3.final_audit',
        'exit_code': max(v['exit_code'] for v in outputs.values()),
        'observed_vs_simulated': 'ACTUAL_READONLY_SERVER_NO_BOARD_ACCESS',
        'raw_evidence_sha': outputs, 'security_scope': 'READONLY_NO_SCANNER_NO_SERVER_WRITES',
        'owner_auth_id': 'MPM-H3-004_SIGNED_SOFTWARE', 'rollback_state': 'NO_MUTATION',
        'unresolved': ['FIELD_STATE', 'QUALIFIED_NIBP_SOURCE', 'SG_CONTROL_PLANE', 'FORMAL_ACL_AUDIENCE'],
        'null_reasons': {'device_or_runtime_sha': 'NO_PHYSICAL_READ_OR_NEW_RUNTIME_YET'}}
    with (OUT / 'F0-receipt.json').open('x') as f:
        json.dump(receipt, f, indent=2)
    print(json.dumps({'exit_code': receipt['exit_code'], 'server_writes': False, 'board_access': False}))
    return receipt['exit_code']


if __name__ == '__main__':
    raise SystemExit(main())
