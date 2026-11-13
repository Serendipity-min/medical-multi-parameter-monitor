"""当前39948B独立RESP15、RA–LL–RL与C共同窗的150秒B只读原码取证。"""
import argparse
import ctypes as C
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time

import b4_recovery as pkg
import b4_runtime as live
import readback_b as raw
import runtime_state_b as runtime

ROOT = Path(__file__).resolve().parents[2]
SCOPE = 'B4_RESP15_RALL_CAN_JOINT_READONLY_150S'
SLOTS = 0x20002160
READS = {a: set(s) for a, s in live.READS.items()}
READS[SLOTS] = {3072}
# VTOR=0时允许核对已读固件首64B与地址0别名，不扩大任何目标写入口。
READS[0x08000000] = {64, 39948}
# 本次为独立呼吸15专用profile，不复用普通ECG或旧RA–LA源记录。
MENU = {'mode': 'INDEPENDENT_RESPIRATION', 'RESP_bpm': 15,
        'RESP_amplitude_literal': '1.5R', 'waveform_period_literal': '30bpm',
        'apnea_literal': '0s', 'ECG_reference_bpm': None}
CRITERIA = {'warmup_ms': 45000, 'evaluation_ms': 90000,
            'RR_nominal_range': [14, 16], 'minimum_raw_frames': 22000,
            'maximum_diagnostic_gap_ms': 1500, 'minimum_saved_observations': 90,
            'SPS_range': [247.5, 252.5], 'required_RR_saved_valid_fraction': 1.0,
            'CH1_required_near_rail_frames': 0, 'ECG': 'CHARACTERIZATION_ONLY',
            'required_raw_period_status': 'PERIOD_COHERENT_EXPLORATORY_ONLY',
            'CAN_reference': 'C_START_PLUS_45_TO_135_SECONDS',
            'common_raw_selection': 'B_SAMPLE_TICKS_WITHIN_C_RECEIVED_RESP_WAVE_SOURCE_TICK_SPAN'}



def bindings():
    names = ('b4_resp_rall_can_current.py', 'b4_runtime.py', 'c_b4_readonly.py', 'readback_b.py',
             'runtime_state_b.py', 'live_state_b.py', 'resp_exploratory.py', 'b4_recovery.py')
    return {n: raw.sha(Path(__file__).with_name(n)) for n in names}


def plan():
    # 独立呼吸15源与RA–LL–RL专用记录；心电仅表征，阻抗幅度仍未绝对标定。
    return {'scope': SCOPE, 'menu': MENU, 'criteria': CRITERIA, 'tools_sha256': bindings(),
            'image_sha256': live.IMAGE_SHA, 'duration_s': 150, 'hard_limit_s': 180,
            'explicit_reset_halt_go_writes': 0, 'probe_sessions': 1, 'retries': 0,
            'Z0_ohm': None, 'delta_Zpp_ohm': None,
            'source_case_model': 'SKX-2000+', 'manual_model': 'SKX-2000D+ V2.2',
            'model_equivalence': 'NOT_PROVEN', 'new_C_receive_window': True,
            'leads': {'R': 'RA', 'L': 'LL', 'F': 'RL', 'LA': 'EMPTY'}}


def validate(a):
    live.need(a.get('enabled') is True and a.get('owner_approved') is True,
              'RESP_CAN_CURRENT_OWNER_REQUIRED')
    live.need(a.get('plan') == plan(), 'RESP_CAN_CURRENT_BINDINGS_DRIFT')
    live.need(a.get('observed_menu') == MENU and a.get('JLink_on_B') is True
              and a.get('battery_no_USB') is True, 'RESP_CAN_CURRENT_SOURCE_ROUTE')
    live.need(time.time() < a.get('expires_unix', 0), 'RESP_CAN_CURRENT_EXPIRED')


class Link(live.Link):
    def call(self, name, *args, timeout=5):
        # 仅扩大一个固定RAM槽块的读取范围；所有目标写/复位/暂停/Go API继续禁止。
        live.need(name in runtime.CALLS - {'JLINKARM_GetRegisterList', 'JLINKARM_GetRegisterName',
                                         'JLINKARM_ReadReg'}, 'RESP_CAN_CURRENT_FUNCTION_DENIED')
        live.need(self.sdk_calls < 24000, 'RESP_CAN_CURRENT_CALL_BUDGET')
        if name == 'JLINKARM_ExecCommand':
            command = args[0].decode('ascii')
            live.need(command in runtime.COMMANDS or command == 'SetRestartOnClose = 1',
                      'RESP_CAN_CURRENT_COMMAND_DENIED')
            if command == 'SetRestartOnClose = 1':
                live.need(self.verified_running_flash, 'RESP_CAN_CURRENT_CLOSE_NOT_VERIFIED')
        if name == 'JLINKARM_ReadMemEx':
            live.need(args[1] in READS.get(args[0], set()) and args[3] == 0,
                      'RESP_CAN_CURRENT_READ_DENIED')
        self.sdk_calls += 1
        return raw.Link.call(self, name, *args, timeout=timeout)

    def read(self, address, size):
        live.need(size in READS.get(address, set()), 'RESP_CAN_CURRENT_READ_DENIED')
        data = (C.c_uint8 * size)()
        live.need(self.call('JLINKARM_ReadMemEx', address, size, data, 0) == size,
                  'RESP_CAN_CURRENT_PARTIAL_READ')
        return bytes(data)


def capture(link, out, reference):
    link.open()
    seen = raw.identity(link)
    raw.write_json(out / 'identity-private.json', seen)
    raw.check_identity(seen)
    live.need(seen == reference, 'RESP_CAN_CURRENT_WRONG_BOARD')
    live.need(hashlib.sha256(link.read(0x08000000, 39948)).hexdigest() == live.IMAGE_SHA,
              'RESP_CAN_CURRENT_WRONG_FIRMWARE')
    live.need(hashlib.sha256(link.read(0x1fffc000, 16)).hexdigest() == runtime.OPTIONS_SHA,
              'RESP_CAN_CURRENT_OPTIONS_DRIFT')
    raw.write_json(out / 'entry-sticky-private.json', {'DHCSR': link.u32(live.ro.SYSTEM['DHCSR'])})
    first = live.snapshot(link, out, 'entry')
    raw.write_json(out / 'window-private.json', {'anchor_device_ms': first['bio']['last_sample_ms'],
                                               'frozen_plan': plan()})
    # READY必须有至少2秒真实推进和名义250SPS证据；C只能在新鲜READY后发送一次START。
    time.sleep(2)
    baseline = live.snapshot(link, out, 'ready-check')
    live.assess(first, baseline)
    raw.write_json(out / 'READY.json', {'host_monotonic': time.monotonic(),
                   'B4_image_sha256': live.IMAGE_SHA, 'samples': baseline['bio']['samples']})
    previous = baseline
    started = time.monotonic()
    index = 0
    with (out / 'slots-private.bin').open('xb') as slots, \
         (out / 'chunks-private.jsonl').open('x', encoding='utf-8') as chunks, \
         (out / 'diagnostics-private.jsonl').open('x', encoding='utf-8') as diagnostics:
        diagnostics.write(json.dumps(first) + '\n'); diagnostics.flush()
        while time.monotonic() - started < 150:
            live.need(index < 3001, 'RESP_CAN_CURRENT_SLOT_BUDGET')
            target = started + index * .05
            if time.monotonic() < target:
                time.sleep(target - time.monotonic())
            state = link.u32(live.ro.SYSTEM['DHCSR'])
            if state & (raw.HALT | raw.LOCKUP | raw.RESET):
                # 新异常先保留实际状态，不以关闭时隐式Go恢复异常CPU。
                raw.write_json(out / 'changed-state-private.json', {'DHCSR': state, 'chunk': index})
                link.verified_running_flash = False
                raise ValueError('RESP_CAN_CURRENT_CPU_CHANGED')
            before = time.monotonic()
            block = link.read(SLOTS, 3072)
            after = time.monotonic()
            slots.write(block); slots.flush()
            chunks.write(json.dumps({'index': index, 'offset': index * 3072, 'start': before,
                                     'end': after, 'sha256': hashlib.sha256(block).hexdigest()}) + '\n')
            chunks.flush()
            if index % 10 == 0:
                current = live.snapshot(link, out, f'diag-{index:04d}')
                diagnostics.write(json.dumps(current) + '\n'); diagnostics.flush()
                live.assess(previous, current)
                previous = current
            index += 1
        final = live.snapshot(link, out, 'final')
        diagnostics.write(json.dumps(final) + '\n'); diagnostics.flush()
        sps = live.assess(first, final)
    return {'status': 'READONLY_WINDOW_CAPTURED_ANALYSIS_PENDING', 'exit_code': 0,
            'chunks': index, 'elapsed_host_s': time.monotonic() - started,
            'device_sps': sps, 'samples_advanced': final['bio']['samples'] - first['bio']['samples'],
            'new_C_receive_window': True, 'explicit_reset_halt_go_writes': 0}


def worker(args, a):
    args.out.mkdir(exist_ok=False)
    link = None
    result = {'status': 'STOP', 'exit_code': 1}
    try:
        reference = json.loads(pkg.protected(Path(a['identity']), False).read_text('utf-8'))
        link = Link(args.out)
        result = capture(link, args.out, reference)
    except BaseException as e:
        raw.write_json(args.out / 'failure-private.json', {'reason': str(e), 'type': type(e).__name__})
    finally:
        if link:
            try:
                if not link.verified_running_flash and link.close_resume_enabled:
                    link.set_close_resume(False)
            except BaseException as e:
                result.update(exit_code=1, close_policy_error=type(e).__name__)
            finally:
                try:
                    link.close()
                except BaseException as e:
                    result.update(exit_code=1, close_error=type(e).__name__)
            result.update(sdk_calls=link.sdk_calls, close_resume=link.close_resume_enabled)
        raw.write_json(args.out / 'receipt-private.json', result)
        for p in args.out.iterdir():
            if p.is_file():
                pkg.protected(p, False)
    print(json.dumps(result)); return result['exit_code']


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--authorization', type=Path)
    p.add_argument('--out', type=Path)
    p.add_argument('--worker', action='store_true', help=argparse.SUPPRESS)
    args = p.parse_args()
    try:
        live.need(args.authorization is not None and args.out is not None, 'RESP_CAN_CURRENT_AUTH_OUT')
        a = json.loads(pkg.protected(args.authorization, False).read_text('utf-8')); validate(a)
        pkg.protected(args.out.parent, False)
        live.need(not args.out.exists(), 'RESP_CAN_CURRENT_OUTPUT_EXISTS')
        if args.worker:
            return worker(args, a)
        with args.authorization.with_suffix('.used').open('x') as f:
            f.write(SCOPE)
        command = [sys.executable, '-X', 'utf8', str(Path(__file__)), '--worker',
                   '--authorization', str(args.authorization), '--out', str(args.out)]
        reason = None
        start = time.monotonic()
        with args.out.with_name(args.out.name + '-worker.log').open('xb') as log:
            child = subprocess.Popen(command, stdout=log, stderr=subprocess.STDOUT)
            try:
                # 主监督器不再连接硬件；DLL超时或总时限到即停止，不自动重试/复位。
                while child.poll() is None:
                    if time.monotonic() - start > 180:
                        reason = 'HARD_LIMIT'
                    if (args.out / 'STOP').exists():
                        reason = 'OWNER_STOP'
                    try:
                        lines = (args.out / 'heartbeat-events.jsonl').read_text('utf-8').splitlines()
                        event = json.loads(lines[-1]) if lines else {}
                        if event.get('active') and time.monotonic() > event['deadline_monotonic']:
                            reason = 'SDK_TIMEOUT'
                    except (OSError, ValueError):
                        pass
                    if reason:
                        child.kill(); break
                    time.sleep(.05)
            finally:
                if child.poll() is None:
                    child.kill()
                child.wait(timeout=5)
        args.out.mkdir(exist_ok=True)
        raw.write_json(args.out / 'supervisor-private.json', {'reason': reason,
                       'worker_exit_code': child.returncode, 'elapsed_s': time.monotonic() - start})
        return 1 if reason else child.returncode
    except (ValueError, RuntimeError, OSError, TypeError, KeyError) as e:
        print(json.dumps({'status': 'STOP_BEFORE_SDK', 'type': type(e).__name__})); return 1


if __name__ == '__main__':
    sys.exit(main())
