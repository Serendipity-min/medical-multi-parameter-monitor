"""仅离线核对BIO_V2构建、ARM offsetof和旧profile拒绝；没有硬件访问入口。"""
import argparse
import ctypes as C
import datetime
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--arm-build', required=True, type=Path)
    parser.add_argument('--keil-root', default=Path('D:/keil'), type=Path)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[2]
    sys.path.insert(0, str(root / 'node-b/tests'))
    from run_pretest import NAMES, Diag
    arm = args.arm_build.resolve()
    build = json.loads((arm / 'receipt.json').read_text(encoding='utf-8'))
    # 输入必须是本轮真实产物，不仅信任先前回执中的摘要文本。
    artifacts = {'BIO_V2.bin': arm / 'firmware/OBJ/BIO_V2.bin',
                 'BIO_V2.axf': arm / 'firmware/OBJ/BIO_V2.axf',
                 'symbols.txt': arm / 'symbols.txt'}
    for name, path in artifacts.items():
        assert hashlib.sha256(path.read_bytes()).hexdigest() == build['outputs'][name]['sha256']
    assert build['outputs']['BIO_V2.bin']['sha256'] == '438a8120f6df06ce219cdc30c0e5b697ac0e993f98d5a80521b10361536ae3ae'
    out = root / 'node-b/build' / ('abi-audit-' + datetime.datetime.now(
        datetime.timezone.utc).strftime('%Y%m%dT%H%M%S%fZ'))
    out.mkdir(exist_ok=False)
    header = root / 'node-b/firmware/biov2/实验固件/HARDWARE/bio_v2.h'
    (out / 'bio_v2.h').write_bytes(header.read_bytes())
    source = ('#include <stddef.h>\n#include "bio_v2.h"\n'
              '/* 用ARM编译器生成实际布局；不链接或下载固件。 */\n'
              'const unsigned int bio_layout[] = {sizeof(BioV2Diag),'
              + ','.join('offsetof(BioV2Diag,' + n + ')' for n in NAMES) + '};\n')
    (out / 'layout.c').write_text(source, encoding='utf-8')
    cc = args.keil_root / 'ARM/ARMCC/bin/armcc.exe'
    cmd = [str(cc), '--cpu=Cortex-M4.fp.sp', '--c99', '-S', 'layout.c', '-o', 'layout.s']
    p = subprocess.run(cmd, cwd=out, capture_output=True, timeout=60)
    (out / 'compile.log').write_bytes(p.stdout + p.stderr)
    assert p.returncode == 0
    assembly = (out / 'layout.s').read_text(errors='replace')
    # ARM目标额外产生VFE头部DCD，必须限定本数组，不能把其它段的数据当偏移。
    array = re.search(r'^bio_layout\s*\n(.*?)^\s+EXPORT bio_layout', assembly, re.M | re.S)
    assert array is not None
    words = [int(s, 0) for s in re.findall(r'^\s+DCD\s+(0x[0-9a-fA-F]+|\d+)\s*$', array[1], re.M)]
    assert words == [C.sizeof(Diag)] + [getattr(Diag, n).offset for n in NAMES]
    symbols = artifacts['symbols.txt'].read_text(errors='replace')

    def symbol(name, size):
        hits = re.findall(r'\b' + re.escape(name) + r'\s+0x([0-9a-fA-F]{8})\s+[^\n]*?0x'
                          + format(size, 'x') + r'\s*$', symbols, re.M)
        assert len(hits) == 1, (name, hits)
        return '0x' + hits[0]

    report = {'status': 'OFFLINE_LAYOUT_ONLY_NOT_INSTALLED_CAPTURE_PROFILE',
              'device_identity': 'NOT_OBSERVED', 'hardware_access': False,
              'firmware_binding': build['outputs'], 'arm_layout_exit': p.returncode,
              'host_arm_layout_equal': True,
              'diag': {'address': symbol('g_bio_v2', 120), 'bytes': words[0],
                       'tag': '0x324f4942', 'abi_version': 2,
                       'fields': [{'name': n, 'offset': v} for n, v in zip(NAMES, words[1:])]},
              'slots': {'address': symbol('slots', 3072), 'bytes': 3072, 'record_bytes': 24},
              'adc_stats': {'address': symbol('s_stats', 48), 'bytes': 48},
              'register_readback': {'address': symbol('g_ads_readback', 12), 'bytes': 12},
              'head': symbol('head', 4), 'tail': symbol('tail', 4)}
    sys.path.insert(0, str(root / 'node-b/acquisition/工具'))
    from acq_storage import create_run, offline_precheck
    run = create_run(out / 'synthetic-run', 'synthetic', 'legacy-profile-negative',
                     'SOFTWARE_FIXTURE', 'SYNTHETIC_NO_DEVICE', duration=1, warmup=0,
                     uid='00000000-00000000-00000001')
    try:
        offline_precheck(run, artifacts['BIO_V2.bin'], artifacts['BIO_V2.axf'], artifacts['symbols.txt'])
    except ValueError as exc:
        # 精确确认失败发生在BIN身份，不能把无关配置错误冒充安全拒绝。
        assert str(exc) == 'bin SHA 不符合适配器', str(exc)
        report['legacy_profile_negative'] = 'REJECTED_CURRENT_BIN_AS_EXPECTED'
    else:
        raise AssertionError('Legacy profile accepted incompatible BIO_V2')
    report['tool_sha256'] = hashlib.sha256(cc.read_bytes()).hexdigest()
    report['script_sha256'] = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    (out / 'receipt.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({'status': report['status'], 'diag_bytes': words[0],
                      'legacy_profile': report['legacy_profile_negative'],
                      'receipt': str((out / 'receipt.json').relative_to(root))}))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
