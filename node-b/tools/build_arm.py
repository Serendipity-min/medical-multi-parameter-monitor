"""只在隔离目录构建BIO_V2，不下载；外部DSP库须与归档SHA完全一致。"""
import argparse
import datetime
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--keil-root', type=Path, required=True)
    parser.add_argument('--dsp-lib', type=Path, required=True)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[2]
    dependency = json.loads((root / 'node-b/evidence/external-build-dependencies.json').read_text('utf-8'))
    expected = dependency['CMSIS_DSP_ARMCC_library']['sha256']
    if not args.dsp_lib.is_file() or sha(args.dsp_lib) != expected:
        raise ValueError('外部CMSIS DSP库缺失或SHA不符，不使用替代产物')
    uv = args.keil_root / 'UV4/UV4.exe'
    fromelf = args.keil_root / 'ARM/ARMCC/bin/fromelf.exe'
    if not uv.is_file() or not fromelf.is_file():
        raise ValueError('缺少Keil/ARMCC工具')
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    out = root / 'node-b/build' / ('arm-' + stamp)
    project = out / 'firmware'
    shutil.copytree(root / 'node-b/firmware/biov2/实验固件', project)
    shutil.copyfile(args.dsp_lib, project / 'CORE/arm_cortexM4lf_math.lib')
    # 原Keil工程引用的输出目录在纯源码签出中为空，显式建立后再运行构建。
    for folder in ['OBJ', 'USER/Listings']:
        (project / folder).mkdir(parents=True, exist_ok=True)
    sys.path.insert(0, str(root / 'node-b/acquisition/工具'))
    from acq_swd import ascii_mapping
    with ascii_mapping(project) as prefix:
        command = [str(uv), '-r', prefix + 'USER/BIO_V2.uvprojx', '-o', prefix + 'build.log']
        proc = subprocess.run(command, capture_output=True, timeout=180)
    (out / 'launcher.log').write_bytes(proc.stdout + proc.stderr)
    log = project / 'build.log'
    text = log.read_text('utf-8', errors='replace') if log.exists() else ''
    resource = re.search(r'Program Size: Code=(\d+) RO-data=(\d+) RW-data=(\d+) ZI-data=(\d+)', text)
    report = {'scope': 'ORDINARY_ARM_BUILD_NO_DOWNLOAD', 'exit_code': proc.returncode,
              'zero_errors_observed': bool(re.search(r'0 Error\(s\)', text)),
              'zero_warnings_observed': bool(re.search(r'0 Warning\(s\)', text)),
              'CMSIS_library_sha256': expected, 'outputs': {},
              'tool_sha256': {'UV4': sha(uv), 'fromelf': sha(fromelf)}}
    success = proc.returncode == 0 and report['zero_errors_observed'] and resource is not None
    if success:
        report['resources'] = dict(zip(('code', 'ro', 'rw', 'zi'), map(int, resource.groups())))
        axf = project / 'OBJ/BIO_V2.axf'
        binary = project / 'OBJ/BIO_V2.bin'
        symbols = out / 'symbols.txt'
        for mode, target in [('--bin', binary), ('-s', symbols)]:
            result = subprocess.run([str(fromelf), mode, '--output', str(target), str(axf)], capture_output=True)
            (out / ('fromelf-' + target.suffix[1:] + '.log')).write_bytes(result.stdout + result.stderr)
            if result.returncode:
                success = False
                report['conversion_exit'] = result.returncode
                break
        if success:
            old = re.findall(r'\b(?:PanTompkins_\w+|RespRate_\w+|ECG_Filter_\w+|EcgDespike|ecg_median)\b',
                             symbols.read_text(errors='replace'))
            report['old_algorithm_symbols'] = old
            success = not old
            for file in (axf, binary, symbols):
                report['outputs'][file.name] = {'bytes': file.stat().st_size, 'sha256': sha(file)}
    report['status'] = 'PASS' if success else 'FAIL'
    (out / 'receipt.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(report, indent=2))
    print('receipt=' + str((out / 'receipt.json').relative_to(root)))
    return 0 if success else 1


if __name__ == '__main__':
    raise SystemExit(main())
