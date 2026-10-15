"""纯脱机已知ECG/呼吸工程信号源及真实BIO_V2回放，不访问串口/J-Link/开发板。"""
from pathlib import Path
import argparse
import csv
import ctypes as ct
import datetime
import hashlib
import json
import math
import subprocess

PREP = Path(__file__).resolve().parent
ROOT = PREP.parent
SOURCE = ROOT / '实验固件/HARDWARE/bio_v2.c'
EXPECTED_SOURCE = '3adca55cb1eb1fa3ed8e4148f837287d0454bcc2c08ae77a8f73deb1dac156a7'
FIELDS = (
    ['tag', 'abi_version', 'samples', 'last_sequence', 'last_sample_ms', 'segment',
     'discontinuities', 'clipped_samples']
    + ['ecg_raw', 'resp_raw', 'ecg_filtered', 'resp_filtered']
    + ['hr', 'rpm', 'hr_valid', 'rpm_valid', 'hr_reason', 'rpm_reason',
       'hr_candidates', 'hr_accepted', 'resp_candidates', 'resp_accepted',
       'hr_last_cycle_ms', 'resp_last_cycle_ms', 'hr_fresh_intervals', 'resp_fresh_intervals']
    + ['ecg_rms_codes', 'resp_rms_codes', 'ecg_mains_fraction', 'resp_mains_fraction']
)


class Diagnostic(ct.Structure):
    # 公开结构固定30个4字节成员，拒绝布局漂移，不能复制别的版本RAM地址。
    _fields_ = [(name, ct.c_int32 if 8 <= i < 12 else
                 ct.c_float if i >= 26 else ct.c_uint32)
                for i, name in enumerate(FIELDS)]


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def signal(i):
    # 已知60bpm工程QRS/P/T形状与15次/分正弦；ADC码幅度不冒充校准mV/欧姆。
    t = i / 250.0
    phase = ((t - .3 + .5) % 1.0) - .5
    ecg = (200000 + 10000 * math.exp(-.5 * (phase / .012) ** 2)
           + 1800 * math.exp(-.5 * ((phase - .23) / .055) ** 2)
           + 700 * math.exp(-.5 * ((phase + .16) / .035) ** 2))
    resp = 640000 + 1200 * math.sin(2 * math.pi * .25 * t)
    return round(ecg), round(resp)


def capture_case(lib, diagnostic, output, name, mode):
    duration = 120 if mode == 'recovery' else 90
    rows = []
    lib.BioV2_Init(1000)
    with (output / (name + '_samples.csv')).open('x', newline='', encoding='utf-8') as inp, \
            (output / (name + '_replay.csv')).open('x', newline='', encoding='utf-8') as result:
        iw, rw = csv.writer(inp), csv.writer(result)
        iw.writerow(['source_seq', 'assigned_ms', 'ecg_adc_code', 'resp_adc_code',
                     'flags', 'source_kind', 'expected_ecg_bpm', 'expected_resp_rpm'])
        rw.writerow(['source_seq'] + FIELDS)
        for i in range(duration * 250):
            ecg, resp = signal(i)
            if mode == 'resp_clip' or (mode == 'recovery' and 60 * 250 <= i < 85 * 250):
                resp = 8388607
            if mode == 'ecg_clip':
                ecg = -8388608
            now = 1000 + i * 4
            iw.writerow([i + 1, now, ecg, resp, 0, 'SOFTWARE_SYNTHETIC',
                         None if mode == 'ecg_clip' else 60,
                         None if resp == 8388607 else 15])
            lib.BioV2_Process(ecg, resp, now, i + 1, 0)
            # 覆盖独立getter的发布路径；没有真实采集时钟或设备状态读取。
            if i % 50 == 0:
                value = ct.c_uint16()
                lib.BioV2_GetHeart(ct.byref(value), now)
                lib.BioV2_GetResp(ct.byref(value), now)
            state = {field: getattr(diagnostic, field) for field in FIELDS}
            rows.append(state)
            rw.writerow([i + 1] + [state[field] for field in FIELDS])
    return rows


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, help='只能指定不存在的输出目录，禁止覆盖历史采集')
    args = parser.parse_args()
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    output = args.output or PREP / '软件信号源' / ('run-' + stamp)
    # 不使用硬件工具，生成/回放之前冻结当前C输入；所有错误留在独立目录中。
    output.mkdir(parents=True, exist_ok=False)
    receipt = {'source_kind': 'SOFTWARE_SYNTHETIC', 'hardware_operations': [],
               'status': 'PREPARING', 'physiological_accuracy': 'NOT_EVALUATED',
               'adc_electrodes_rld_resp_modulation_coverage': 'NOT_EXERCISED', 'checks': []}
    try:
        if digest(SOURCE) != EXPECTED_SOURCE or ct.sizeof(Diagnostic) != 120:
            raise ValueError('冻结算法源或公开结构身份不符')
        receipt['source_sha256'] = digest(SOURCE)
        dll = output / 'bio_v2_host.dll'
        command = ['C:/mingw64/bin/gcc.exe', '-std=c99', '-O2', '-Wall', '-Wextra',
                   '-Werror', '-ffp-contract=off', '-shared', str(SOURCE), '-o', str(dll), '-lm']
        process = subprocess.run(command, capture_output=True, timeout=60)
        (output / 'compile.stdout.log').write_bytes(process.stdout)
        (output / 'compile.stderr.log').write_bytes(process.stderr)
        receipt['compile_exit'] = process.returncode
        receipt['compile_command'] = command
        if process.returncode:
            raise RuntimeError('普通Host编译失败，保留日志')
        lib = ct.CDLL(str(dll.resolve()))
        lib.BioV2_Init.argtypes = [ct.c_uint32]
        lib.BioV2_Process.argtypes = [ct.c_int32, ct.c_int32, ct.c_uint32, ct.c_uint32, ct.c_uint8]
        for function in ['BioV2_GetHeart', 'BioV2_GetResp']:
            getattr(lib, function).argtypes = [ct.POINTER(ct.c_uint16), ct.c_uint32]
        diagnostic = Diagnostic.in_dll(lib, 'g_bio_v2')
        all_rows = {mode: capture_case(lib, diagnostic, output, mode, mode)
                    for mode in ['normal', 'resp_clip', 'ecg_clip', 'recovery']}
        reference = all_rows['normal']
        hf = [field for field in FIELDS if field.startswith(('ecg_', 'hr'))]
        rf = [field for field in FIELDS if field.startswith(('resp_', 'rpm'))]

        def check(name, success):
            receipt['checks'].append({'name': name, 'pass': bool(success)})
            if not success:
                raise AssertionError(name)

        check('normal_HR60_RPM15', reference[-1]['hr_valid'] and reference[-1]['hr'] == 60
              and reference[-1]['rpm_valid'] and reference[-1]['rpm'] == 15)
        check('resp_clip_healthy_ECG_exact', all(all(a[k] == b[k] for k in hf)
              for a, b in zip(reference, all_rows['resp_clip'])))
        check('resp_clip_protected', all(not r['rpm_valid'] and r['rpm_reason'] & 32
              for r in all_rows['resp_clip']))
        check('ecg_clip_healthy_resp_exact', all(all(a[k] == b[k] for k in rf)
              for a, b in zip(reference, all_rows['ecg_clip'])))
        check('ecg_clip_protected', all(not r['hr_valid'] and r['hr_reason'] & 32
              for r in all_rows['ecg_clip']))
        recovered = all_rows['recovery']
        check('recovery_ECG_first90s_exact', all(all(a[k] == b[k] for k in hf)
              for a, b in zip(reference, recovered)))
        check('recovery_own_warmup', all(not r['rpm_valid']
              for r in recovered[85 * 250:95 * 250]))
        check('recovery_fresh_cycles', recovered[-1]['rpm_valid'] and recovered[-1]['rpm'] == 15)
        check('source_unchanged', digest(SOURCE) == EXPECTED_SOURCE)
        receipt.update(status='PASS_OFFLINE_SOFTWARE_FIXTURES', pass_count=len(receipt['checks']),
                       generated_samples={name: len(rows) for name, rows in all_rows.items()},
                       finals={name: rows[-1] for name, rows in all_rows.items()})
    except BaseException as error:
        receipt.update(status='FAIL_OR_INCOMPLETE', error=type(error).__name__ + ': ' + str(error))
        raise
    finally:
        (output / 'receipt.json').write_text(json.dumps(receipt, ensure_ascii=False, indent=2), 'utf-8')
        # 最后封存所有成功/失败文件；清单不包含自身，不覆盖任何已有实测包。
        files = [p for p in output.iterdir() if p.is_file()]
        (output / 'manifest.json').write_text(json.dumps({'self_excluded': True, 'files': [
            {'path': p.name, 'bytes': p.stat().st_size, 'sha256': digest(p)} for p in files
        ]}, ensure_ascii=False, indent=2), 'utf-8')
    print(json.dumps({'scope': receipt['status'], 'checks': receipt['pass_count'],
                      'output': str(output.resolve()), 'hardware_operations': []}, ensure_ascii=True))


if __name__ == '__main__':
    main()
