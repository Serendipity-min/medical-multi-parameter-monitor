"""分级归档B4构建/失败原件及恢复副本；只处理文件，不触及实板或云端。"""
from pathlib import Path
import argparse
import ctypes
import datetime
import hashlib
import json
import shutil
import subprocess
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[2]
EVIDENCE = ROOT / 'node-b/evidence/B4-001'
ORIGINAL = Path('E:/medical-monitor-node-b-precan-private/20261023/last-round')


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def load(p):
    return json.loads(p.read_text(encoding='utf-8'))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('node-arm', 'gateway-arm', 'host', 'baseline-regression'):
        parser.add_argument('--' + name, required=True, type=Path)
    args = parser.parse_args()
    runs = {name: (ROOT / path).resolve() for name, path in vars(args).items()}
    for run in runs.values():
        if not run.is_relative_to((ROOT / 'node-b/build').resolve()): raise ValueError('归档输入必须位于当前构建目录')
    final = {name: load(path / 'receipt.json') for name, path in runs.items()}
    assert all(final[name]['status'] == 'PASS' for name in ('node_arm', 'gateway_arm', 'host'))
    assert all(c['exit_code'] == 0 for c in final['baseline_regression']['results'])
    # 恢复原件先核验，整片前缀必须精确等于已验收25488B；绝不提升旧25284B。
    freeze = load(EVIDENCE / 'deployment-freeze.json')
    for name, item in freeze['verified_originals'].items(): assert sha(ORIGINAL / name) == item['sha256']
    assert (ORIGINAL / 'install-01/after-full-private.bin').read_bytes()[:25488] == (ORIGINAL / 'candidate/BIO_V2.bin').read_bytes()
    for name, expected in freeze['source_sha256'].items(): assert sha(ROOT / name) == expected
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    archive = Path('E:/medical-monitor-node-b-precan-private/20261023') / ('b4-software-' + stamp)
    archive.mkdir(exist_ok=False)
    p = subprocess.run(['cipher', '/E', str(archive)], capture_output=True)
    if p.returncode: raise RuntimeError('不能启用归档目录EFS，退出=' + str(p.returncode))
    copies = {
        'candidate/BIO_V2.bin': 'L1-current/BIO_V2-25488B.bin',
        'candidate/BIO_V2.axf': 'L1-current/BIO_V2.axf', 'candidate/symbols.txt': 'L1-current/symbols.txt',
        'install-01/after-full-private.bin': 'L2-recovery/current-full-flash.bin',
        'install-01/before-options-1.bin': 'L2-recovery/options-original.bin',
        'install-01/before-full-1.bin': 'L2-history/previous-full-flash.bin',
    }
    for old, new in copies.items():
        target = archive / new; target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ORIGINAL / old, target); assert sha(target) == sha(ORIGINAL / old)
    print('Recovery copies verified; archiving software attempts...', flush=True)
    # 原失败轮次不覆盖、不删除；压缩只是新增的受限加密副本。
    with zipfile.ZipFile(archive / 'software-attempt-originals.zip', 'x', zipfile.ZIP_DEFLATED, compresslevel=3) as z:
        for folder in sorted((ROOT / 'node-b/build').glob('b4-*')):
            for file in sorted(folder.rglob('*')):
                if file.is_file(): z.write(file, file.relative_to(ROOT / 'node-b/build').as_posix())
    for name, folder in runs.items():
        destination = archive / ('final-' + name)
        destination.mkdir()
        for file in folder.glob('*'):
            if file.is_file(): shutil.copy2(file, destination / file.name)
    # 使用真实退出码保存旧目标及HMI回归，不运行Security Gate或任何网络服务。
    cases = []
    for name, cmd in [('legacy-canopen', ['gateway/canopen/build_host.py']),
                      ('legacy-canonical-backend', ['gateway/canopen/tools/check_canonical.py']),
                      ('screen-reset-host', ['node-b/tests/test_hmi_reset.py'])]:
        p = subprocess.run([sys.executable, *cmd], cwd=ROOT, capture_output=True, timeout=180)
        log = archive / (name + '.log'); log.write_bytes(p.stdout + p.stderr)
        cases.append({'name': name, 'exit_code': p.returncode, 'log_sha256': sha(log)})
        print(name, p.returncode, flush=True)
    assert all(case['exit_code'] == 0 for case in cases)
    # 核实EFS属性；只有真正加密的原件副本才签归档完成。身份与私有原码不进Git。
    encrypted = []
    # Win32失败值是无符号0xffffffff，不能用ctypes默认有符号返回值比较。
    ctypes.windll.kernel32.GetFileAttributesW.restype = ctypes.c_uint32
    for file in archive.rglob('*'):
        if file.is_file():
            attrs = ctypes.windll.kernel32.GetFileAttributesW(str(file))
            if attrs == 0xffffffff or not attrs & 0x4000: raise RuntimeError('原件未加密：' + file.name)
            encrypted.append(file)
    history = []
    for folder in sorted((ROOT / 'node-b/build').glob('b4-*')):
        receipt = folder / 'receipt.json'
        if receipt.exists():
            d = load(receipt)
            history.append({'run': folder.name, 'status': d.get('status'), 'receipt_sha256': sha(receipt),
                            'exit_code': d.get('exit_code'), 'cases': d.get('cases')})
        else:
            history.append({'run': folder.name, 'status': 'ABORTED_BEFORE_RECEIPT',
                            'exit_code': 1, 'exit_evidence': 'observed tool transcript; no original receipt emitted'})
    # Git仅保留可复核摘要；大日志、可执行文件、BIN及整片恢复原件均留私有目录。
    for name, data in final.items():
        (EVIDENCE / ('final-' + name + '.json')).write_text(json.dumps(data, indent=2) + '\n', encoding='utf-8')
    for file in runs['host'].glob('*.log'):
        shutil.copy2(file, EVIDENCE / ('host-' + file.name))
    report = {'scope': 'SOFTWARE_OFFLINE_ONLY', 'hardware_operations': 0, 'cloud_changes': 0,
              'security_gate_run': False, 'archive': str(archive), 'encrypted_files_verified': len(encrypted),
              'archive_sha256': {str(f.relative_to(archive)): sha(f) for f in encrypted},
              'regression': cases, 'attempt_history': history,
              'status': 'SOFTWARE_VALIDATION_PASS_HARDWARE_ADMISSION_BLOCKED'}
    (EVIDENCE / 'stage-results.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    policy = {'deployed': {'commit': freeze['baseline'], 'bytes': 25488,
                          'bin_sha256': freeze['verified_originals']['candidate/BIO_V2.bin']['sha256'],
                          'archive': str(archive / 'L1-current/BIO_V2-25488B.bin')},
              'restore_full_flash_sha256': freeze['verified_originals']['install-01/after-full-private.bin']['sha256'],
              'old_25284B': 'HISTORICAL_ONLY_NEVER_NEW_DEPLOYMENT_CANDIDATE',
              'b4_can_software_candidate': final['node_arm']['artifacts']['B4_NODE_B.bin'],
              'hardware_deployment_authorized': False, 'requires_pi_admission': True}
    target = ROOT / 'node-b/deployment/current.json'; target.parent.mkdir(exist_ok=True)
    target.write_text(json.dumps(policy, indent=2) + '\n', encoding='utf-8')
    print('EFS files verified:', len(encrypted)); print('archive=' + str(archive))


if __name__ == '__main__':
    main()
