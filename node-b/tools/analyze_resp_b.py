"""RESP原码、实板诊断与冻结C源Host回放分开分析；不连接探针。"""
import argparse
import csv
import ctypes as C
import json
from pathlib import Path
import struct
import subprocess
import sys

from readback_b import PRIVATE, require, sha, write_json
from resp_exploratory import ROOT, FIELDS, decode, estimate_period, raw_integrity, reason_names, validate_source

SOURCE = ROOT / 'node-b/firmware/biov2/实验固件/HARDWARE/bio_v2.c'
SOURCE_SHA = '3adca55cb1eb1fa3ed8e4148f837287d0454bcc2c08ae77a8f73deb1dac156a7'


def require_capture_end(receipt, supervisor):
    """成功末值不能抵消尾段、恢复或真实子进程退出失败。"""
    require(receipt['status'] == 'RESP_CAPTURE_FILES_SAVED' and receipt['tail_halt_confirmed']
            and receipt['resume_confirmed'], 'RESP_UNCONFIRMED_CAPTURE_END')
    require(supervisor['worker_exit_code'] == supervisor['supervisor_exit_code'] == receipt['process_exit_code'] == 0,
            'RESP_CAPTURE_EXIT_NONZERO')


def replay(rows, out):
    require(sha(SOURCE) == SOURCE_SHA, 'RESP_BIO_SOURCE_DRIFT')
    dll = out / 'bio_v2_resp_replay.dll'
    command = ['C:/mingw64/bin/gcc.exe', '-std=c99', '-O2', '-Wall', '-Wextra', '-Werror',
               '-ffp-contract=off', '-shared', str(SOURCE), '-o', str(dll), '-lm']
    process = subprocess.run(command, capture_output=True, timeout=60)
    (out / 'compile.stdout.log').write_bytes(process.stdout)
    (out / 'compile.stderr.log').write_bytes(process.stderr)
    write_json(out / 'compile-receipt.json', {'command': command, 'exit_code': process.returncode,
                                             'bio_source_sha256': SOURCE_SHA})
    require(process.returncode == 0, 'RESP_HOST_COMPILE_FAILED')
    lib = C.CDLL(str(dll.resolve()))
    lib.BioV2_Init.argtypes = [C.c_uint32]
    lib.BioV2_Process.argtypes = [C.c_int32, C.c_int32, C.c_uint32, C.c_uint32, C.c_uint8]
    memory = (C.c_uint8 * 120).in_dll(lib, 'g_bio_v2')
    lib.BioV2_Init(rows[0]['device_ms'])
    derived = [];events = [];last = (0, 0)
    # 回放初态从首个保留帧重置，不能冒称包含板上此前全部历史或与ARM逐位相同。
    try:
        for row in rows:
            lib.BioV2_Process(row['ch2_raw'], row['ch1_raw'], row['device_ms'], row['source_seq'], row['flags_raw'])
            d = dict(zip(FIELDS, struct.unpack('<8I4i14I4f', bytes(memory))))
            d.update(origin='FROZEN_C_HOST_REPLAY_NOT_LIVE', source_seq=row['source_seq'], device_ms=row['device_ms'])
            derived.append(d)
            now = (d['resp_candidates'], d['resp_accepted'])
            if now != last:
                events.append({'origin': 'FROZEN_C_HOST_REPLAY_NOT_LIVE', 'source_seq': row['source_seq'],
                               'device_ms': row['device_ms'], 'resp_candidates': now[0], 'resp_accepted': now[1],
                               'resp_last_cycle_ms': d['resp_last_cycle_ms'], 'rpm_reason': d['rpm_reason']})
            last = now
    finally:
        # Windows不会因CDLL局部变量离开作用域自动释放模块；先结束所有调用再卸载宿主算法DLL。
        # 这仅涉及Host回放库，与J-Link无关；避免测试临时目录因DLL句柄残留而无法清理。
        if sys.platform == 'win32':
            import _ctypes
            del memory
            _ctypes.FreeLibrary(lib._handle)
    with (out / 'replay-not-live-private.csv').open('x', encoding='utf-8', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(derived[0]));writer.writeheader();writer.writerows(derived)
    write_json(out / 'resp-events-REPLAY-private.json', events)
    return derived, events, sha(dll)


def analyze(folder, source_record, profile_path, out):
    source = json.loads(source_record.read_text('utf-8'));validate_source(source, 'E1')
    profile = json.loads(profile_path.read_text('utf-8'))
    from capture_resp_b import validate
    validate(profile)
    receipt = json.loads((folder / 'receipt-private.json').read_text('utf-8'))
    supervisor = json.loads((folder / 'supervisor-receipt-private.json').read_text('utf-8'))
    require_capture_end(receipt, supervisor)
    require(sha(source_record) == receipt['source_record_sha256'], 'RESP_SOURCE_DRIFT')
    require(sha(profile_path) == receipt['profile_sha256'], 'RESP_PROFILE_DRIFT')
    require(sha(folder / 'final-paused-ram-private.bin') == receipt['ram_sha256'], 'RESP_RAM_DRIFT')
    require(sha(folder / 'stable-raw-private.csv') == receipt['stable_raw_sha256'], 'RESP_RAW_DRIFT')
    require(sha(folder / 'diagnostics-private.jsonl') == receipt['diagnostics_sha256'], 'RESP_DIAG_DRIFT')
    # 每一块运行态原件按当次记录的偏移/长度/哈希复核，末尾多余字节也拒绝。
    chunks = [json.loads(line) for line in (folder / 'chunks-private.jsonl').read_text('utf-8').splitlines()]
    with (folder / 'running-slots-private.bin').open('rb') as stream:
        for chunk in chunks:
            require(stream.tell() == chunk['offset'] and chunk['bytes'] == 3072, 'RESP_CHUNK_LAYOUT')
            import hashlib
            require(hashlib.sha256(stream.read(3072)).hexdigest() == chunk['sha256'], 'RESP_CHUNK_DRIFT')
        require(not stream.read(1), 'RESP_UNACCOUNTED_CHUNK_BYTES')
    live = [json.loads(line) for line in (folder / 'diagnostics-private.jsonl').read_text('utf-8').splitlines()]
    require(bool(live), 'RESP_NO_LIVE_DIAG')
    raw_diags = sorted(folder.glob('*-diag.bin'))
    require(len(raw_diags) == len(live), 'RESP_DIAG_COUNT')
    for path, diagnostic in zip(raw_diags, live):
        stem = path.name.removesuffix('-diag.bin')
        actual = decode(path.read_bytes(), (folder / (stem + '-stats.bin')).read_bytes(),
                        (folder / (stem + '-rreg-cache.bin')).read_bytes())
        require(all(actual[k] == diagnostic[k] for k in actual), 'RESP_DIAG_ORIGINAL_MISMATCH')
    with (folder / 'stable-raw-private.csv').open(encoding='utf-8', newline='') as stream:
        rows = [{k: int(row[k]) for k in ('source_seq', 'device_ms', 'irq_cycles', 'status_raw',
                                         'flags_raw', 'ch1_raw', 'ch2_raw')} for row in csv.DictReader(stream)]
    require(len(rows) > 1, 'RESP_NO_STABLE_RAW')
    out.mkdir(exist_ok=False)
    derived, events, dll_sha = replay(rows, out)
    anchor = live[0]['last_sample_ms']
    # 环形槽的前置历史仍完整保留，但不能混入本次10秒源状态的周期结论。
    offset = lambda ms: ((ms - anchor + 0x80000000) & 0xffffffff) - 0x80000000
    selected = [r for r in rows if 0 <= offset(r['device_ms']) < 10000]
    estimate = estimate_period(selected, receipt['export'])
    failures = raw_integrity(selected, receipt['export'])
    errors = {key: max(d['adc'][key] for d in live)
              for key in ('init_errors', 'spi_errors', 'bad_status', 'queue_overflow')}
    if any(errors.values()):
        failures.append('ADC_ERRORS')
    if any(abs(r['ch2_raw']) >= 8220835 for r in selected):
        failures.append('CH2_NEAR_RAIL')
    host_span = (live[-1]['host_start_s'] + live[-1]['host_end_s'] - live[0]['host_start_s'] - live[0]['host_end_s']) / 2
    sps = (live[-1]['adc']['captured'] - live[0]['adc']['captured']) / host_span if host_span > 0 else None
    if sps is None or not 240 <= sps <= 260:
        failures.append('HOST_OBSERVED_SPS')
    coherent = estimate['status'] == 'PERIOD_COHERENT_EXPLORATORY_ONLY'
    status = 'E1_INPUT_SEEN' if coherent and not failures else 'RESP_PATH_NOT_OBSERVED'
    if failures:
        status = 'RESP_INPUT_INTEGRITY_FAIL'
    summary = {'stage': 'E1', 'status': status, 'analysis_exit_code': 2 if failures else (0 if coherent else 3),
               'source_type': 'RESP_EXPLORATORY', 'nominal_menu_rpm': source['nominal_rpm'],
               'menu_literals': source['menu'], 'dynamic_pair': 'UNVERIFIED',
               'Z0_ohm': None, 'delta_Zpp_ohm': None, 'impedance_calibration': 'NOT_CALIBRATED',
               'source_record_sha256': sha(source_record), 'profile_sha256': sha(profile_path),
               'capture_receipt_sha256': sha(folder / 'receipt-private.json'),
               'raw_csv_sha256': sha(folder / 'stable-raw-private.csv'), 'bio_source_sha256': SOURCE_SHA,
               'host_replay_dll_sha256': dll_sha, 'retained_frames': len(rows), 'analysis_frames': len(selected),
               'pre_anchor_frames_preserved': sum(offset(r['device_ms']) < 0 for r in rows),
               'failures': failures, 'adc_error_max': errors, 'observed_host_sps': sps,
               'independent_raw_estimate': estimate,
               'live_diagnostics': [{k: d[k] for k in FIELDS} | {'hr_reason_names': reason_names(d['hr_reason']),
                                      'rpm_reason_names': reason_names(d['rpm_reason'])} for d in live],
               'replay_final': derived[-1], 'replay_resp_event_records': len(events),
               'RR_acceptance': 'NOT_EVALUATED_10S_WARMUP_AND_FRESH_INTERVAL_LIMIT',
               'E2': 'NOT_RUN_SEPARATE_CARD_REQUIRED', 'E3': 'NOT_RUN_SEPARATE_CARD_REQUIRED',
               'limitations': ['L1 raw periodicity is not proof of absolute impedance or physical electrode-pair calibration',
                               'No L2 menu rate tracking proof from one rate/window',
                               'Live RAM diagnostic observations are nonatomic; RREG cache is not fresh SPI read',
                               'Host replay reset at first retained frame; not complete board history or bit-identical ARM',
                               'No clinical accuracy; nominal source menu is not an independently calibrated reference']}
    write_json(out / 'analysis-summary-private.json', summary)
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    t = [offset(r['device_ms']) / 1000 for r in rows]
    fig, axes = plt.subplots(4, 1, figsize=(11, 10), layout='constrained')
    axes[0].plot(t, [r['ch1_raw'] for r in rows]);axes[0].set(title='CH1 raw; engineering simulator; impedance NOT calibrated', ylabel='ADC codes')
    axes[1].plot(t, [r['resp_filtered'] for r in derived]);axes[1].set(title='Frozen BIO_V2 RESP filtered; HOST REPLAY', ylabel='UI scale')
    axes[2].plot(t, [r['ch2_raw'] for r in rows]);axes[2].set(title='CH2 raw ECG companion observation', ylabel='ADC codes')
    axes[3].scatter([offset(d['last_sample_ms']) / 1000 for d in live], [d['rpm'] for d in live], label='live rpm')
    axes[3].scatter([offset(d['last_sample_ms']) / 1000 for d in live], [d['rpm_reason'] for d in live], label='reason bits')
    axes[3].set(title='Saved live non-atomic diagnostic observations; no RR acceptance', xlabel='Device seconds relative to first diagnostic')
    axes[3].legend();fig.savefig(out / 'resp-waveforms-private.png', dpi=150);plt.close(fig)
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('capture', 'source-record', 'profile', 'out'):
        parser.add_argument('--' + name, required=True, type=Path)
    args = parser.parse_args()
    require(args.out.resolve().is_relative_to(PRIVATE.resolve()), 'RESP_PRIVATE_ANALYSIS_OUTPUT')
    require(not args.out.exists(), 'RESP_ANALYSIS_OUTPUT_ALREADY_EXISTS')
    try:
        result = analyze(args.capture, args.source_record, args.profile, args.out)
        print(json.dumps({k: result[k] for k in ('status', 'analysis_exit_code', 'analysis_frames', 'RR_acceptance')}))
        return result['analysis_exit_code']
    except BaseException as exc:
        args.out.mkdir(exist_ok=True)
        write_json(args.out / 'analysis-failure-private.json', {'status': 'RESP_ANALYSIS_FAILED',
                   'error': type(exc).__name__ + ': ' + str(exc), 'analysis_exit_code': 1})
        return 1


if __name__ == '__main__':
    sys.exit(main())
