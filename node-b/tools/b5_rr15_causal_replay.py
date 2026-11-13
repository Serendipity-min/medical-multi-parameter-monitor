"""Offline RR15 false-HR replay using sealed G3 B blocks and the real BioV2 C source.

Does not access SWD, COM, MQTT, cloud, or devices. Uses only private local EFS
files supplied by the operator, and a newly compiled *host* BioV2 library.
This is a diagnostic tool, NOT a frozen reviewer or a threshold optimization.
No physical/patient data should be committed to Git.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import ctypes as C
import hashlib
import json
import math
from pathlib import Path
import shutil
import struct
import subprocess
import sys

BLOCK_BYTES = 5692
RAW_SLOTS = 128
RAW_BYTES = 24
MORE = ('hr', 'rpm', 'hr_valid', 'rpm_valid', 'hr_reason', 'rpm_reason',
        'hr_candidates', 'hr_accepted', 'resp_candidates', 'resp_accepted',
        'hr_last_cycle_ms', 'resp_last_cycle_ms', 'hr_fresh_intervals',
        'resp_fresh_intervals')
FIELDS = ([(k, C.c_uint32) for k in
           ('tag', 'abi_version', 'samples', 'last_sequence', 'last_sample_ms',
            'segment', 'discontinuities', 'clipped_samples')]
          + [(k, C.c_int32) for k in
             ('ecg_raw', 'resp_raw', 'ecg_filtered', 'resp_filtered')]
          + [(k, C.c_uint32) for k in MORE]
          + [(k, C.c_float) for k in
             ('ecg_rms_codes', 'resp_rms_codes',
              'ecg_mains_fraction', 'resp_mains_fraction')])


class Diag(C.Structure):
    _fields_ = FIELDS


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sealed_raw_frames(window: Path, expected_sha256: str, expected_index_sha256: str):
    """Apply the frozen reader's >=2 identical copies rule, never guess a frame."""
    idx = window / 'B' / 'blocks-private.jsonl'
    binary = window / 'B' / 'blocks-private.bin'
    if not idx.is_file() or not binary.is_file():
        raise FileNotFoundError('Expected joint/B/blocks-private.{jsonl,bin}')
    if digest(idx.read_bytes()) != expected_index_sha256:
        raise ValueError('PRIVATE_BLOCK_INDEX_SHA256_MISMATCH')
    versions = defaultdict(Counter)
    blocks = 0
    full_digest = hashlib.sha256()
    high = 0
    invalid_status = set()
    with idx.open('r', encoding='utf-8') as entries, binary.open('rb') as data:
        for line in entries:
            row = json.loads(line)['data']
            block = data.read(BLOCK_BYTES)
            if (len(block) != BLOCK_BYTES or row['offset'] != blocks * BLOCK_BYTES
                    or digest(block) != row['sha256']):
                raise ValueError('G3_BLOCK_HASH_OR_OFFSET at block ' + str(blocks))
            full_digest.update(block)
            current_high = max(struct.unpack_from('<I', block, n * RAW_BYTES + 12)[0]
                               for n in range(RAW_SLOTS))
            if current_high < high:
                raise ValueError('RAW_SEQUENCE_EPOCH_RESTART_OR_WRAP')
            high = current_high
            for n in range(RAW_SLOTS):
                f = block[n * RAW_BYTES:(n + 1) * RAW_BYTES]
                status = int.from_bytes(f[:3], 'big')
                seq = struct.unpack_from('<I', f, 12)[0]
                if seq and status & 0xf01fff != 0xc00000:
                    invalid_status.add(seq)
                if seq and status & 0xf01fff == 0xc00000:
                    versions[seq][f] += 1
            blocks += 1
        if data.read(1):
            raise ValueError('G3_EXTRA_UNINDEXED_BYTES')
    if full_digest.hexdigest() != expected_sha256:
        raise ValueError('PRIVATE_BLOCKS_FULL_SHA256_MISMATCH')
    stable, rejected = [], 0
    for seq, counts in versions.items():
        repeated = [frame for frame, n in counts.items() if n >= 2]
        if len(repeated) != 1:
            rejected += 1
            continue
        f = repeated[0]
        ms = struct.unpack_from('<I', f, 20)[0]
        ecg = int.from_bytes(f[6:9], 'big', signed=True)
        resp = int.from_bytes(f[3:6], 'big', signed=True)
        cycles = struct.unpack_from('<I', f, 16)[0]
        stable.append((seq, ms, ecg, resp, f[9], cycles, int.from_bytes(f[:3], 'big')))
    stable.sort(key=lambda row: row[0])
    if not stable:
        raise ValueError('NO_VERIFIED_RAW_FRAMES')
    gaps = [(a[0], b[0]) for a, b in zip(stable, stable[1:]) if b[0] != a[0] + 1]
    continuous = [(a, b) for a, b in zip(stable, stable[1:]) if b[0] == a[0] + 1]
    ticks = Counter((b[1] - a[1]) & 0xffffffff for a, b in continuous)
    irq = [(b[5] - a[5]) & 0xffffffff for a, b in continuous]
    return stable, {'blocks': blocks, 'stable': len(stable),
                    'unqualified_sequences': rejected,
                    'invalid_status_sequences': len(invalid_status),
                    'nonzero_flags_frames': sum(bool(r[4]) for r in stable),
                    'sequence_gaps': gaps, 'IRQ_ms_step_histogram': dict(sorted(ticks.items())),
                    'IRQ_cycles_step_min': min(irq) if irq else None,
                    'IRQ_cycles_step_max': max(irq) if irq else None,
                    'raw_status_values': sorted({r[6] for r in stable}),
                    'blocks_sha256': expected_sha256,'index_sha256': expected_index_sha256}


def mains_projection(rows, center_seq, rate=250):
    """Independent 50 Hz line-projection estimate; not BioV2's mains fraction."""
    by_seq = {row[0]: row for row in rows}
    required = range(center_seq - rate, center_seq)
    if any(s not in by_seq for s in required):
        return {'quality': 'INSUFFICIENT_CONTIGUOUS_SOURCE'}
    selected = [by_seq[s] for s in required]
    if any(not 1 <= ((b[1]-a[1]) & 0xffffffff) <= 8 for a,b in zip(selected,selected[1:])):
        return {'quality': 'INSUFFICIENT_CONTIGUOUS_SOURCE'}
    values = [row[2] for row in selected]
    seconds = [((row[1]-selected[0][1]) & 0xffffffff)/1000 for row in selected]
    n = len(values)
    average = sum(values) / n
    ac = [v - average for v in values]
    power = sum(v * v for v in ac) / n
    if power <= 0:
        return {'quality': 'DC', 'raw_rms_codes': 0}
    re = sum(v * math.cos(2 * math.pi * 50 * t) for t, v in zip(seconds,ac)) * 2 / n
    im = sum(v * math.sin(2 * math.pi * 50 * t) for t, v in zip(seconds,ac)) * 2 / n
    return {'quality': 'RAW_UNCALIBRATED',
            'raw_rms_codes': round(math.sqrt(power), 3),
            'line_50hz_projection_fraction': round(min(1., (re*re+im*im)/(2*power)), 5),
            'max_abs_to_rms': round(max(abs(v) for v in ac) / math.sqrt(power), 3),
            'actual_samples': n}


def compile_host(source: Path, output: Path, gcc: str):
    compiler = Path(shutil.which(gcc) or gcc).resolve(strict=True)
    abi_source=output.with_suffix('.abi.c')
    offsets=', '.join(['sizeof(BioV2Diag)']+['offsetof(BioV2Diag, '+k+')' for k,_ in FIELDS])
    abi_source.write_text('#include "bio_v2.h"\n#include <stddef.h>\n'
        'uint32_t BioV2_ReplayAbi(uint32_t index) {\n'
        ' const uint32_t offsets[] = {'+offsets+'};\n'
        ' return index < sizeof(offsets)/sizeof(offsets[0]) ? offsets[index] : 0xffffffffu;\n}\n',encoding='utf-8')
    command = [str(compiler), '-std=c99', '-O2', '-Wall', '-Wextra', '-Werror',
               '-ffp-contract=off', '-shared']
    if sys.platform != 'win32':
        command.append('-fPIC')
    command += [str(source),str(abi_source),'-I',str(source.parent), '-o', str(output), '-lm']
    p = subprocess.run(command, capture_output=True, text=True, timeout=180,
                       check=False)
    output.with_suffix('.compile.stdout.log').write_text(p.stdout,encoding='utf-8')
    output.with_suffix('.compile.stderr.log').write_text(p.stderr,encoding='utf-8')
    if p.returncode:
        raise RuntimeError('HOST_COMPILE_FAILED: ' + p.stderr[:1500])
    version = subprocess.run([str(compiler),'--version'],capture_output=True,check=True,timeout=10)
    return {'source_sha256': digest(source.read_bytes()),
            'header_sha256': digest(source.with_suffix('.h').read_bytes()) if source.with_suffix('.h').is_file() else None,
            'compiler_sha256': digest(compiler.read_bytes()),'compiler_version':version.stdout.decode(errors='replace').splitlines()[0],
            'ABI_proof_source_sha256':digest(abi_source.read_bytes()),
            'command':command,'artifact_sha256':digest(output.read_bytes()),'compiler_exit_code': p.returncode}


def replay(libpath: Path, rows, stream_name: str):
    lib = C.CDLL(str(libpath))
    lib.BioV2_Init.argtypes = [C.c_uint32]
    lib.BioV2_Process.argtypes = [C.c_int32, C.c_int32, C.c_uint32,
                                  C.c_uint32, C.c_uint8]
    lib.BioV2_Init.restype = None
    lib.BioV2_Process.restype = None
    diag = Diag.in_dll(lib, 'g_bio_v2')
    if C.sizeof(Diag) != 120:
        raise AssertionError('BIO_V2_ABI_SIZE_DRIFT')
    lib.BioV2_ReplayAbi.argtypes=[C.c_uint32];lib.BioV2_ReplayAbi.restype=C.c_uint32
    if [lib.BioV2_ReplayAbi(i) for i in range(len(FIELDS)+1)] != [C.sizeof(Diag)]+[getattr(Diag,k).offset for k,_ in FIELDS]:
        raise AssertionError('BIO_V2_C_SIZE_OR_OFFSETOF_DRIFT')
    lib.BioV2_Init(rows[0][1])
    eligible = 0
    hr_valid = 0
    rr_valid = 0
    episodes = []
    open_episode = None
    prev_seq = None
    frequencies = Counter()
    for row in rows:
        seq, ms, ecg, resp, flags = row[:5]
        lib.BioV2_Process(ecg, resp, ms, seq, flags)
        if ((ms - rows[0][1]) & 0xffffffff) < 45000:
            continue
        eligible += 1
        rr_valid += int(diag.rpm_valid != 0)
        if diag.hr_valid:
            hr_valid += 1
            frequencies[int(diag.hr)] += 1
            if open_episode is None or prev_seq != seq - 1:
                open_episode = {'start_seq': seq, 'end_seq': seq, 'first_ms': ms,
                                'last_ms': ms, 'rates': set(), 'last_accepted_peak_timestamp_ms': 0}
                episodes.append(open_episode)
            open_episode['end_seq'] = seq
            open_episode['last_ms'] = ms
            open_episode['rates'].add(int(diag.hr))
            open_episode['last_accepted_peak_timestamp_ms'] = int(diag.hr_last_cycle_ms)
        else:
            open_episode = None
        prev_seq = seq
    for item in episodes:
        item['rates'] = sorted(item['rates'])
        item['duration_ms'] = item['last_ms'] - item['first_ms'] + 4
        item['ecg_raw_features_before_event'] = mains_projection(rows, item['start_seq'])
    result = {
        'stream': stream_name, 'verified_input_samples': len(rows),
        'analyzed_samples_after_replay_warmup': eligible,
        'hr_valid_samples': hr_valid, 'rr_valid_samples': rr_valid,
        'hr_valid_fraction': round(hr_valid / eligible, 6) if eligible else None,
        'hr_rates_while_valid': dict(sorted(frequencies.items())),
        'hr_episode_count': len(episodes),
        'episodes_first_24': episodes[:24],
        'important_limit': 'Raw full-session host replay; NOT the original 600 SWD snapshots '
                           'or the frozen T0 evaluation boundary'}
    return result


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--rr-joint', type=Path, required=True)
    p.add_argument('--rr-blocks-sha256', required=True)
    p.add_argument('--rr-index-sha256', required=True)
    p.add_argument('--ecg-joint', type=Path, required=True)
    p.add_argument('--ecg-blocks-sha256', required=True)
    p.add_argument('--ecg-index-sha256', required=True)
    p.add_argument('--baseline-source', type=Path, required=True)
    p.add_argument('--baseline-source-sha256', required=True)
    p.add_argument('--baseline-header-sha256', required=True)
    p.add_argument('--candidate-source', type=Path)
    p.add_argument('--candidate-source-sha256')
    p.add_argument('--candidate-header-sha256')
    p.add_argument('--gcc', default=shutil.which('gcc') or 'C:/mingw64/bin/gcc.exe')
    p.add_argument('--out-private', type=Path, required=True)
    a = p.parse_args()
    import b4_recovery as private
    repo_root = Path(__file__).resolve().parents[2]
    if a.out_private.resolve().is_relative_to(repo_root):
        p.error('Private results must not be written anywhere inside the Git repository')
    private.protected(a.out_private.parent,False)
    for window in (a.rr_joint,a.ecg_joint):private.protected(window,False)
    if digest(a.baseline_source.read_bytes()) != a.baseline_source_sha256 or digest(a.baseline_source.with_suffix('.h').read_bytes()) != a.baseline_header_sha256:
        raise ValueError('BASELINE_C_SOURCE_OR_HEADER_DRIFT')
    if a.candidate_source and (digest(a.candidate_source.read_bytes()) != a.candidate_source_sha256 or
                              digest(a.candidate_source.with_suffix('.h').read_bytes()) != a.candidate_header_sha256):
        raise ValueError('CANDIDATE_C_SOURCE_OR_HEADER_DRIFT')
    windows = {}
    for name, window, expected, index in (('RR15', a.rr_joint, a.rr_blocks_sha256,a.rr_index_sha256),
                                   ('ECG60', a.ecg_joint, a.ecg_blocks_sha256,a.ecg_index_sha256)):
        frames, receipt = sealed_raw_frames(window, expected,index)
        windows[name] = (frames, receipt)
    build = a.out_private.parent/(a.out_private.stem+'-host-build')
    build.mkdir(exist_ok=False);private.protected(build,False)
    evaluations = {}
    for label, source in [('baseline', a.baseline_source),
                          ('candidate', a.candidate_source)]:
        if source is None:
            continue
        staged=build/label;staged.mkdir();private.protected(staged,False)
        shutil.copyfile(source,staged/'bio_v2.c');shutil.copyfile(source.with_suffix('.h'),staged/'bio_v2.h')
        libpath = staged / ('bio_v2_host' + ('.dll' if sys.platform == 'win32' else '.so'))
        provenance = compile_host(staged/'bio_v2.c', libpath, a.gcc)
        evaluations[label] = {'provenance': provenance,
                              'windows': {name: replay(libpath, frames, name)
                                          for name, (frames, _) in windows.items()}}
    output = {'status': 'OFFLINE_CAUSAL_REPLAY_ONLY_NOT_FIELD_PASS',
              'sha256_bound_inputs': {k: receipt for k, (_, receipt) in windows.items()},
              'evaluations': evaluations,
              'restrictions': ['Do not revise frozen R5/R6 results',
                               'Do not force HR INVALID based on RR15 mode',
                               'Do not select threshold from RR15 alone',
                               'Independent holdout ECG60/90/120 and RR negative data required',
                               'No target SDK, UART, flash, board or cloud access']}
    with a.out_private.open('x', encoding='utf-8') as out:
        json.dump(output, out, indent=2, ensure_ascii=False)
        out.write('\n')
    print(json.dumps({'status': output['status'],
                      'rr_hr_episodes': evaluations['baseline']['windows']['RR15']['hr_episode_count'],
                      'ecg_hr_valid_fraction': evaluations['baseline']['windows']['ECG60']['hr_valid_fraction'],
                      'receipt_sha256': digest(a.out_private.read_bytes())}, ensure_ascii=False))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
