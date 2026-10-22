"""B-ALG-001 补充离线门禁：真实C算法、复位/时间边界及可选私有历史回放。

不连接设备，不提供SWD入口；历史路径只从仓库外清单读入，原码与逐帧派生不入库。
"""
import argparse
import ctypes as C
import datetime
import hashlib
import json
import math
from pathlib import Path
import struct
import subprocess


ROOT = Path(__file__).resolve().parents[2]
NAMES = ['tag', 'abi_version', 'samples', 'last_sequence', 'last_sample_ms', 'segment',
         'discontinuities', 'clipped_samples', 'ecg_raw', 'resp_raw', 'ecg_filtered',
         'resp_filtered', 'hr', 'rpm', 'hr_valid', 'rpm_valid', 'hr_reason', 'rpm_reason',
         'hr_candidates', 'hr_accepted', 'resp_candidates', 'resp_accepted',
         'hr_last_cycle_ms', 'resp_last_cycle_ms', 'hr_fresh_intervals',
         'resp_fresh_intervals', 'ecg_rms_codes', 'resp_rms_codes',
         'ecg_mains_fraction', 'resp_mains_fraction']


class Diag(C.Structure):
    _fields_ = [(n, C.c_int32 if 8 <= i < 12 else C.c_float if i >= 26 else C.c_uint32)
                for i, n in enumerate(NAMES)]


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load(source, output):
    cmd = ['C:/mingw64/bin/gcc.exe', '-std=c99', '-O2', '-Wall', '-Wextra', '-Werror',
           '-ffp-contract=off', '-shared', str(source), '-o', str(output), '-lm']
    p = subprocess.run(cmd, capture_output=True, timeout=60)
    output.with_suffix('.compile.log').write_bytes(p.stdout + p.stderr)
    if p.returncode:
        raise RuntimeError('Host compile failed; original compile log retained')
    lib = C.CDLL(str(output))
    lib.BioV2_Init.argtypes = [C.c_uint32]
    lib.BioV2_Process.argtypes = [C.c_int32, C.c_int32, C.c_uint32, C.c_uint32, C.c_uint8]
    lib.BioV2_Tick.argtypes = [C.c_uint32]
    return lib, Diag.in_dll(lib, 'g_bio_v2')


def sample(i):
    # 纯软件已知节律；ADC码不是校准mV或欧姆，不冒充模拟器实测。
    t = i / 250
    phase = ((t - .3 + .5) % 1) - .5
    h = (200000 + 10000 * math.exp(-.5 * (phase / .012) ** 2)
         + 1800 * math.exp(-.5 * ((phase - .23) / .055) ** 2)
         + 700 * math.exp(-.5 * ((phase + .16) / .035) ** 2))
    return round(h), round(640000 + 1200 * math.sin(2 * math.pi * .25 * t))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--replay-manifest', type=Path)
    args = parser.parse_args()
    out = ROOT / 'node-b/build' / ('pretest-' + datetime.datetime.now(
        datetime.timezone.utc).strftime('%Y%m%dT%H%M%S%fZ'))
    out.mkdir(parents=True, exist_ok=False)
    current = ROOT / 'node-b/firmware/biov2/实验固件/HARDWARE/bio_v2.c'
    old = ROOT / 'node-b/reference/biov2-before-isolation/HARDWARE/bio_v2.c'
    lib, d = load(current, out / 'current.dll')
    before, bd = load(old, out / 'before.dll')
    cases = []

    def check(name, ok):
        # 不在第一条失败退出，保留独立负例的全部真实结果。
        cases.append({'case': name, 'pass': bool(ok)})

    def warm(start=1000, seq=1):
        lib.BioV2_Init(start)
        for i in range(17500):
            h, r = sample(i)
            lib.BioV2_Process(h, r, (start + 4 * i) & 0xffffffff,
                              (seq + i) & 0xffffffff, 0)
        return (start + 4 * 17499) & 0xffffffff

    check('diag_120_bytes_host', C.sizeof(Diag) == 120)
    end = warm()
    check('fixture_precondition_both_valid', d.hr_valid and d.rpm_valid)
    lib.BioV2_Tick(end + 100)
    check('gap_100ms_inclusive_still_valid', d.hr_valid and d.rpm_valid)
    lib.BioV2_Tick(end + 101)
    check('gap_101ms_drops_both_qualifications', not d.hr_valid and not d.rpm_valid
          and d.hr_fresh_intervals == d.resp_fresh_intervals == 0)
    for kind in ['flags', 'sequence', 'time_reversal']:
        end = warm()
        lib.BioV2_Process(*sample(17500), end - 4 if kind == 'time_reversal' else end + 4,
                          17509 if kind == 'sequence' else 17501, 1 if kind == 'flags' else 0)
        check(kind + '_invalidates_without_old_cycles', not d.hr_valid and not d.rpm_valid
              and d.discontinuities == 1 and d.hr_fresh_intervals == d.resp_fresh_intervals == 0)
    warm(start=0xfffff000, seq=0xfffff000)
    check('timestamp_and_sequence_wrap_together', d.hr_valid and d.rpm_valid
          and d.discontinuities == 0)
    lib.BioV2_Init(500)
    check('normal_software_init_drops_old_qualification', d.hr == d.rpm == 0
          and d.hr_valid == d.rpm_valid == 0 and d.samples == 0)
    qualified = True
    for i in range(17500):
        lib.BioV2_Process(*sample(i), 500 + 4 * i, i + 1, 0)
        if d.hr_valid and (i * 4 < 5000 or d.hr_fresh_intervals < 3):
            qualified = False
        if d.rpm_valid and (i * 4 < 10000 or d.resp_fresh_intervals < 3):
            qualified = False
    check('valid_requires_warmup_and_three_fresh_intervals', qualified
          and d.hr_valid and d.rpm_valid)

    history = {'raw8412': {'status': 'NOT_RUN_PRIVATE_RAW_UNAVAILABLE'},
               'csv37169': {'status': 'NOT_RUN_EXACT_SHA_NOT_FOUND'}}
    if args.replay_manifest:
        manifest = json.loads(args.replay_manifest.read_text(encoding='utf-8'))
        entry = manifest.get('raw8412')
        if entry:
            file = Path(entry['path'])
            # 整份原码先验SHA；不更改flags、序号或时间，也不填缺失样本。
            assert sha(file) == entry['sha256']
            blob = file.read_bytes()
            assert len(blob) == entry['expected_frames'] * 24
            frames = []
            for at in range(0, len(blob), 24):
                b = blob[at:at + 24]
                seq, cyc, ms = struct.unpack_from('<III', b, 12)
                frames.append((int.from_bytes(b[6:9], 'big', signed=True),
                               int.from_bytes(b[3:6], 'big', signed=True), ms, seq, b[9]))
            replay = {}
            for name, alg, diag in [('before', before, bd), ('current', lib, d)]:
                alg.BioV2_Init(frames[0][2])
                hv = rv = 0
                for frame in frames:
                    alg.BioV2_Process(*frame)
                    hv += bool(diag.hr_valid)
                    rv += bool(diag.rpm_valid)
                replay[name] = {'hr_valid_samples': hv, 'rr_valid_samples': rv,
                                'samples_counter': diag.samples, 'clipped_samples': diag.clipped_samples,
                                'last_sequence': diag.last_sequence, 'hr_reason': diag.hr_reason,
                                'rr_reason': diag.rpm_reason}
            check('historical_all_CH1_positive_rail', all(f[1] == 8388607 for f in frames))
            check('historical_current_preserves_frames_old_early_return_reproduced',
                  replay['current']['samples_counter'] == len(frames)
                  and replay['before']['samples_counter'] == 0)
            check('historical_no_reference_no_accuracy_claim',
                  replay['current']['hr_valid_samples'] == replay['current']['rr_valid_samples'] == 0)
            history['raw8412'] = {'status': 'REPLAYED_CHARACTERIZATION_ONLY', 'source_sha256': sha(file),
                                  'source_kind': entry['kind'], 'frames': len(frames),
                                  'reference': 'NONE', 'accuracy': 'NOT_EVALUATED', 'results': replay}
    receipt = {'utc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
               'scope': 'B1_OFFLINE_ONLY', 'hardware_access': False,
               'algorithm_sha256': sha(current), 'before_sha256': sha(old),
               'script_sha256': sha(__file__), 'cases': cases, 'history': history,
               'pass': sum(x['pass'] for x in cases), 'total': len(cases)}
    (out / 'receipt.json').write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({'pass': receipt['pass'], 'total': receipt['total'],
                      'failed': [x['case'] for x in cases if not x['pass']],
                      'receipt': str((out / 'receipt.json').relative_to(ROOT))}))
    return int(receipt['pass'] != receipt['total'])


if __name__ == '__main__':
    raise SystemExit(main())
