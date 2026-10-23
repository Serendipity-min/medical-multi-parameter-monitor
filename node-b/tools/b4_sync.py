"""现部署25488B的独立双通道补证：专用源profile、137秒只读原槽及共同窗口评价。"""
import argparse
import ctypes as C
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time

import precan_last_round_b as last
import readback_b as raw
import runtime_state_b as runtime
from b4_recovery import protected
from resp_exploratory import decode

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'node-b/acquisition/工具'))
from stable_slot_export import StableSlots, unpack_slot_fields

SCOPE = 'B4_03_SYNC_NORMAL_ECG60_RESP20_RA_LL_137S_READONLY'
MENU = {'mode': 'NORMAL_ECG', 'HR_bpm': 60, 'ECG_amplitude_menu_mV': 2,
        'RESP_amplitude_literal': '1.5R', 'apnea_literal': '0s', 'waveform_period_literal': '20bpm'}
CRITERIA = {'warmup_ms': 45000, 'evaluation_ms': 90000, 'tail_ms': 2000,
            'HR_range_bpm': [58, 62], 'RR_range_rpm': [19, 21], 'minimum_joint_observations': 90,
            'maximum_observation_gap_ms': 1500, 'minimum_raw_frames': 22000,
            'device_domain_sps_range': [247.5, 252.5], 'required_joint_saved_validity_fraction': 1.0}
SLOTS = 0x20001f38
READS = {a: {n} for a, n in raw.REGIONS.items() if a != 0x08000000}
READS[0x08000000] = {25488}; READS[SLOTS] = {3072}
READS.update({a: {4} for a in (last.SYSTEM | last.FIELDS).values()})
READS.update({0x20001aec: {120}, 0x20000194: {48}, 0x200001c4: {12}})


def digest(data): return hashlib.sha256(data).hexdigest()
def require(ok, reason):
    if not ok: raise ValueError(reason)


def bindings():
    names = ('b4_sync.py', 'precan_last_round_b.py', 'live_state_b.py', 'runtime_state_b.py',
             'readback_b.py', 'resp_exploratory.py', 'b4_recovery.py')
    result = {n: digest((ROOT / 'node-b/tools' / n).read_bytes()) for n in names}
    result['stable_slot_export.py'] = digest((ROOT / 'node-b/acquisition/工具/stable_slot_export.py').read_bytes())
    return result


def plan():
    return {'scope': SCOPE, 'enabled': False, 'source_type': 'ECG_RESP_SIMULTANEOUS_MANUAL_NOMINAL',
            'menu_required': MENU, 'source_nominal_HR': 60, 'source_nominal_RR': 20,
            'independent_reference_HR_RR': None, 'Z0_ohm': None, 'delta_Zpp_ohm': None,
            'leads': {'R_red': 'RA', 'L_yellow': 'LL', 'F_green': 'RL', 'LA': 'EMPTY'},
            'current_firmware_bytes': 25488, 'current_firmware_sha256': last.IMAGE_SHA,
            'criteria': CRITERIA, 'duration_s': 137, 'hard_timeout_s': 180,
            'reset_halt_go_writes': 0, 'slot_block_limit': 2741, 'poll_interval_s': .05,
            'diagnostic_semantics': 'SAVED_NONATOMIC_JOINT_OBSERVATION_NOT_CONTINUOUS_SAMPLE_VALIDITY',
            'tools_sha256': bindings()}


class SyncLink(last.LastLink):
    def __init__(self, out): super().__init__(out, 'final')
    def call(self, name, *args, timeout=5):
        require(name in runtime.CALLS - {'JLINKARM_GetRegisterList', 'JLINKARM_GetRegisterName', 'JLINKARM_ReadReg'},
                'SYNC_FUNCTION_DENIED')
        require(self.sdk_calls < 20000, 'SYNC_SDK_BUDGET')
        if name == 'JLINKARM_ExecCommand':
            command = args[0].decode('ascii')
            require(command in runtime.COMMANDS or command == 'SetRestartOnClose = 1', 'SYNC_POLICY_DENIED')
            if command == 'SetRestartOnClose = 1': require(self.verified_running_flash, 'SYNC_CLOSE_NOT_VERIFIED')
        if name == 'JLINKARM_ReadMemEx':
            require(args[1] in READS.get(args[0], set()) and args[3] == 0, 'SYNC_READ_DENIED')
        self.sdk_calls += 1
        return raw.Link.call(self, name, *args, timeout=timeout)
    def read(self, address, size):
        require(size in READS.get(address, set()), 'SYNC_READ_DENIED')
        b = (C.c_uint8 * size)()
        n = self.call('JLINKARM_ReadMemEx', address, size, b, 0)
        require(n == size, 'SYNC_PARTIAL_READ')
        return bytes(b)


def evaluate(rows, diagnostics, anchor):
    """共同设备时间轴判据采前冻结；不把CAN运输或保存观察率冒充生理连续有效率。"""
    start, end = anchor + 45000, anchor + 135000
    selected = [r for r in rows if start <= r['device_tick_raw'] < end]
    saved = [d for d in diagnostics if start <= d['last_sample_ms'] < end]
    failures = []
    if len(selected) < 22000: failures.append('INSUFFICIENT_RAW_FRAMES')
    if not rows or rows[-1]['device_tick_raw'] < end: failures.append('EVALUATION_NOT_COVERED')
    if any(b['source_seq'] != a['source_seq'] + 1 for a, b in zip(selected, selected[1:])):
        failures.append('RAW_SEQUENCE_GAP')
    if any(r['flags_raw'] for r in selected): failures.append('RAW_FLAGS')
    if len(saved) < 90: failures.append('INSUFFICIENT_JOINT_OBSERVATIONS')
    if not saved or saved[0]['last_sample_ms'] - start > 1500 or end - saved[-1]['last_sample_ms'] > 1500:
        failures.append('DIAGNOSTIC_EDGE_COVERAGE')
    if any(b['last_sample_ms'] - a['last_sample_ms'] > 1500 for a, b in zip(saved, saved[1:])):
        failures.append('DIAGNOSTIC_GAP')
    hr = sum(bool(d['hr_valid']) and d['hr_reason'] == 0 and 58 <= d['hr'] <= 62 for d in saved)
    rr = sum(bool(d['rpm_valid']) and d['rpm_reason'] == 0 and 19 <= d['rpm'] <= 21 for d in saved)
    joint = sum(bool(d['hr_valid'] and d['rpm_valid']) and not(d['hr_reason'] | d['rpm_reason'])
                and 58 <= d['hr'] <= 62 and 19 <= d['rpm'] <= 21 for d in saved)
    if joint != len(saved) or not saved: failures.append('JOINT_VALIDITY_OR_RATE')
    errors = ('init_errors', 'spi_errors', 'bad_status', 'queue_overflow', 'long_gap_count')
    if any(d['adc'][k] for d in diagnostics for k in errors): failures.append('ADC_ERROR_PRESENT')
    if diagnostics and diagnostics[-1]['clipped_samples'] != diagnostics[0]['clipped_samples']:
        failures.append('NEW_CLIPPED_SAMPLES')
    sps = None
    if len(selected) > 1:
        span = selected[-1]['device_tick_raw'] - selected[0]['device_tick_raw']
        sps = (len(selected) - 1) * 1000 / span if span > 0 else None
    if sps is None or not 247.5 <= sps <= 252.5: failures.append('ADC_DEVICE_SPS_OUT_OF_RANGE')
    return {'status': 'SYNC_SAVED_OBSERVATIONS_PASS_RAW_PERIOD_REVIEW_REQUIRED' if not failures else 'SYNC_WINDOW_FAIL',
            'failures': failures, 'raw_frames': len(selected), 'saved_observations': len(saved),
            'HR_pass_observations': hr, 'RR_pass_observations': rr, 'joint_pass_observations': joint,
            'device_domain_sps_not_calibrated': sps, 'criteria': CRITERIA,
            'CAN_transport': 'NOT_TESTED_CAN_DISCONNECTED', 'absolute_accuracy': 'NOT_CLAIMED',
            'raw_waveform_period_review': 'REQUIRED_BEFORE_FINAL_SIMULTANEOUS_PASS'}


def capture(link, out):
    link.open(); last.board(link, out)
    require(digest(link.read(0x08000000, 25488)) == last.IMAGE_SHA, 'SYNC_DEPLOYED_FIRMWARE_CHANGED')
    require(digest(link.read(0x1fffc000, 16)) == runtime.OPTIONS_SHA, 'SYNC_OPTIONS_CHANGED')
    link.u32(last.SYSTEM['DHCSR'])  # 单独消费/保留入口以前的复位粘滞状态，窗口内新复位则STOP。
    first = last.sample(link, out, 0); last.running(first)
    link.verified_running_flash = True; link.set_close_resume(True)
    diagnostics = [first['bio']]; anchor = diagnostics[0]['last_sample_ms']
    stable = StableSlots(); start = time.monotonic(); index = 0; previous = anchor
    with (out / 'running-slots-private.bin').open('xb') as slots, (out / 'chunks-private.jsonl').open('x', encoding='utf-8') as chunks:
        while time.monotonic() - start < 137:
            require(index < 2741, 'SYNC_SLOT_BUDGET')
            target = start + index * .05
            if time.monotonic() < target: time.sleep(target - time.monotonic())
            if link.u32(last.SYSTEM['DHCSR']) & (raw.HALT | raw.LOCKUP | raw.RESET):
                link.verified_running_flash = False
                raise ValueError('SYNC_CPU_STATE_CHANGED')
            before = time.monotonic(); block = link.read(SLOTS, 3072); after = time.monotonic()
            slots.write(block); slots.flush()
            chunks.write(json.dumps({'index': index, 'start': before, 'end': after, 'sha256': digest(block)}) + '\n'); chunks.flush()
            stable.add_running_chunk(block, source_path=f'running-slots-private.bin@{index * 3072}')
            if index % 10 == 0:
                link.verified_running_flash = False
                s = last.sample(link, out, index + 1); last.running(s)
                require(s['bio']['last_sample_ms'] >= previous, 'SYNC_COUNTER_RESTART')
                link.verified_running_flash = True
                previous = s['bio']['last_sample_ms']; diagnostics.append(s['bio'])
            index += 1
    selected = stable.select()
    require(len(selected.boots) == 1 and not selected.conflicts and not selected.multi_repeat_conflicts,
            'SYNC_SLOT_CONFLICT_OR_MULTIPLE_BOOTS')
    rows = [unpack_slot_fields(b) for _, b in sorted(selected.frames.items())]
    raw.write_json(out / 'stable-raw-private.json', rows)
    raw.write_json(out / 'diagnostics-private.json', diagnostics)
    report = evaluate(rows, diagnostics, anchor)
    report.update(chunks=index, pending_unconfirmed=len(selected.pending), firmware_sha256=last.IMAGE_SHA,
                  raw_reconstruction='REPEATED_IDENTICAL_SLOTS_NO_HALT_TAIL', reset_halt_go_writes=0)
    raw.write_json(out / 'evaluation-private.json', report)
    # 主机重建/落盘也需要时间；正常续跑退出前再检查一次，不能用较早的Flash状态掩盖新HALT/ROM。
    link.verified_running_flash = False
    final = last.sample(link, out, 3000); last.running(final)
    require(final['bio']['last_sample_ms'] >= previous, 'SYNC_FINAL_COUNTER_RESTART')
    link.verified_running_flash = True
    return report


def authorize(a):
    require(a.get('enabled') is True and a.get('owner_approved') is True and a.get('scope') == SCOPE, 'SYNC_AUTHORIZATION_REQUIRED')
    require(a.get('plan') == plan(), 'SYNC_PROFILE_DRIFT')
    require(a.get('card_sha256') == raw.sha(ROOT / 'node-b/docs/AUTH-B-B4-03-SYNC-001-R1.md'), 'SYNC_CARD_DRIFT')
    require(time.time() < a.get('expires_unix', 0), 'SYNC_AUTH_EXPIRED')
    require(a.get('observed_menu') == MENU, 'SYNC_SOURCE_NOT_CONFIRMED')
    for k in ('battery_no_USB', 'RA_LL_RL_unchanged', 'CAN_A_C_human_disconnected', 'meter_removed_OFF', 'electrical_gate_pass'):
        require(a.get(k) is True, 'SYNC_SITE_NOT_READY')


def main():
    p = argparse.ArgumentParser(description=__doc__); p.add_argument('--plan', action='store_true')
    p.add_argument('--authorization', type=Path); p.add_argument('--out', type=Path)
    p.add_argument('--worker', action='store_true', help=argparse.SUPPRESS); args = p.parse_args()
    if args.plan: print(json.dumps(plan(), ensure_ascii=False, indent=2)); return 0
    try:
        require(args.authorization is not None and args.out is not None, 'SYNC_AUTHORIZATION_AND_OUTPUT_REQUIRED')
        authorize(json.loads(protected(args.authorization, False).read_text('utf-8')))
        require(not args.out.exists(), 'SYNC_OUTPUT_EXISTS'); protected(args.out.parent, False)
        if not args.worker:
            with args.authorization.with_suffix('.used').open('x') as mark: mark.write(SCOPE)
            argv = [sys.executable, '-X', 'utf8', str(Path(__file__)), '--worker', '--authorization', str(args.authorization), '--out', str(args.out)]
            start = time.monotonic(); reason = None
            with args.out.with_name(args.out.name + '-worker.log').open('xb') as log:
                child = subprocess.Popen(argv, stdout=log, stderr=subprocess.STDOUT)
                try:
                    while child.poll() is None:
                        if time.monotonic() - start > 180: reason = 'SESSION_TIMEOUT'
                        if (args.out / 'STOP').exists(): reason = 'OWNER_STOP'
                        try:
                            events = (args.out / 'heartbeat-events.jsonl').read_text('utf-8').splitlines()
                            e = json.loads(events[-1]) if events else {}
                            if e.get('active') and time.monotonic() > e['deadline_monotonic']: reason = 'SDK_TIMEOUT'
                        except (OSError, ValueError): pass
                        if reason: child.kill(); break
                        time.sleep(.05)
                finally:
                    if child.poll() is None: child.kill()
                    child.wait(timeout=5)
            args.out.mkdir(exist_ok=True)
            raw.write_json(args.out / 'supervisor-private.json', {'reason': reason, 'worker_exit_code': child.returncode})
            return child.returncode if not reason else 1
        args.out.mkdir(); link = None; result = {'status': 'STOP', 'exit_code': 1}
        try:
            link = SyncLink(args.out); report = capture(link, args.out)
            result = {'status': report['status'], 'exit_code': 0 if not report['failures'] else 3}
        except BaseException as e:
            raw.write_json(args.out / 'failure-private.json', {'reason': str(e), 'type': type(e).__name__})
        finally:
            if link:
                try:
                    if not link.verified_running_flash and link.close_resume_enabled: link.set_close_resume(False)
                except BaseException as e: result.update(exit_code=1, close_policy_error_type=type(e).__name__)
                finally:
                    try: link.close()
                    except BaseException as e: result.update(exit_code=1, close_error_type=type(e).__name__)
                result.update(sdk_calls=link.sdk_calls, close_resume_enabled=link.close_resume_enabled)
            raw.write_json(args.out / 'receipt-private.json', result)
        print(json.dumps(result)); return result['exit_code']
    except (ValueError, OSError, TypeError) as e:
        print(json.dumps({'status': 'STOP_BEFORE_SDK', 'error_type': type(e).__name__})); return 1


if __name__ == '__main__': sys.exit(main())
