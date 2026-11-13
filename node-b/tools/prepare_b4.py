"""从冻结提交提取参考实现并核验部署原件；仅文件操作，不加载任何调试器。"""
from pathlib import Path
import hashlib
import json
import subprocess

ROOT = Path(__file__).resolve().parents[2]
H3 = 'a5cdd5b0b1ad48108fd631136e9de69e30582f2d'
BASE = '9988d37cd5470d6857bb535aab1d821cf2581302'
PRIVATE = Path('E:/medical-monitor-node-b-precan-private/20261023/last-round')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    # 参考代码在新实验分支内独立维护，绝不写入原 H3/A/实测工作区。
    imports = {}
    source = 'node-a/STM32F407_HOSPITAL/HARDWARE/CANopen/'
    names = ['CO_driver.c', 'CO_driver_target.h', 'OD.c', 'OD.h', 'node_irq.h', 'node_policy.h']
    for name in names:
        data = subprocess.check_output(['git', 'show', H3 + ':' + source + name], cwd=ROOT)
        target = ROOT / 'node-b/canopen' / name
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists():
            raise RuntimeError('拒绝覆盖已编辑的参考文件：' + name)
        target.write_bytes(data)
        imports[target.relative_to(ROOT).as_posix()] = {'source': source + name,
                                                     'sha256': hashlib.sha256(data).hexdigest()}
    evidence = ROOT / 'node-b/evidence/B4-001'
    evidence.mkdir(parents=True, exist_ok=True)
    (evidence / 'reference-import.json').write_text(json.dumps(
        {'commit': H3, 'files': imports}, indent=2) + '\n', encoding='utf-8')
    files = {
        'candidate/BIO_V2.bin': 'b8e74577dae7a5a1f6caa27687193f5128f89bd70781f06a1d80b0c74d409b44',
        'candidate/BIO_V2.axf': 'fe862a8382d967aa6bf1e156501028fc6adcc2bfa5dc3d9ed7396f2722632005',
        'candidate/symbols.txt': '221417c8f4d632f39624f90291ab85a38af34dfef86d262cb531e77678877981',
        'install-01/after-full-private.bin': 'd2ea7cbf7081b20f82a4a6ca6dde4918b9c4d4b194a3c6c358c2d74012993316',
        'install-01/before-full-1.bin': 'f713277a50a5ec8d8a93317f412d5ab1b754e5d619918e57e9efe9dceef24cbb',
    }
    verified = {}
    for name, expected in files.items():
        file = PRIVATE / name
        actual = sha(file)
        if actual != expected:
            raise RuntimeError('冻结原件 SHA 不符：' + name)
        verified[name] = {'sha256': actual, 'bytes': file.stat().st_size}
    # 整片恢复包含 options，但本轮不生成可执行下载计划或公开设备身份。
    for name in ['install-01/before-options-1.bin', 'install-01/before-options-2.bin',
                 'screen-01/receipt-private.json', 'final-01/receipt-private.json']:
        file = PRIVATE / name
        verified[name] = {'sha256': sha(file), 'bytes': file.stat().st_size}
    firmware = ROOT / 'node-b/firmware/biov2/实验固件'
    sources = {p.relative_to(ROOT).as_posix(): sha(p) for p in sorted(firmware.rglob('*')) if p.is_file()}
    manifest = {'baseline': BASE, 'deployed_bytes': 25488, 'status': 'FROZEN_REPAIRED_DEPLOYMENT',
                'old_25284B': 'HISTORICAL_ONLY_NOT_DEPLOYABLE_CANDIDATE', 'verified_originals': verified,
                'source_sha256': sources, 'private_archive': str(PRIVATE),
                'archive_protection': 'EXISTING_RESTRICTED_ACL_AND_NTFS_EFS',
                'hardware_this_round': False, 'SCREEN_RESET_MCU_RESET_FIX_PASS': True,
                'CPU_ROM_ROOT_CAUSE_UNRESOLVED': True, 'INDEPENDENT_COLD_BOOT_NOT_VALIDATED': True}
    (evidence / 'deployment-freeze.json').write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    print('Frozen repaired deployment and recovery originals verified; no hardware access.')


if __name__ == '__main__':
    main()
