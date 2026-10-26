"""39948B独立呼吸15专用137秒只读窗口；复用受审读取流程，不改阈值/源/硬件。"""
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
SCOPE = 'B4_INDEPENDENT_RESP15_45W90E_READONLY'
SLOTS = 0x20002160
READS = {a: set(s) for a, s in live.READS.items()}
READS[SLOTS] = {3072}
# 独立呼吸菜单与上一普通ECG源记录分离；不将伴随ECG菜单当作实测输入真值。
MENU = {'mode': 'INDEPENDENT_RESPIRATION', 'RESP_bpm': 15,
        'RESP_amplitude_literal': '1.5R', 'waveform_period_literal': '30bpm',
        'apnea_literal': '0s', 'ECG_reference_bpm': None}
CRITERIA = {'warmup_ms': 45000, 'evaluation_ms': 90000, 'tail_ms': 2000,
            'RR_nominal_range': [14, 16], 'minimum_raw_frames': 22000,
            'maximum_diagnostic_gap_ms': 1500, 'minimum_saved_observations': 90,
            'SPS_range': [247.5, 252.5], 'required_RR_saved_valid_fraction': 1.0,
            'required_RR_raw_agreement_rpm': 1.0, 'required_new_clipped_frames': 0,
            'required_raw_period_status': 'PERIOD_COHERENT_EXPLORATORY_ONLY',
            'ECG': 'CHARACTERIZATION_ONLY_NO_KNOWN_REFERENCE',
            'new_C_receive_window': False}



def bindings():
    names = ('b4_resp15_current.py', 'b4_runtime.py', 'c_b4_readonly.py', 'readback_b.py',
             'runtime_state_b.py', 'live_state_b.py', 'resp_exploratory.py', 'b4_recovery.py')
    return {n: raw.sha(Path(__file__).with_name(n)) for n in names}


def plan():
    # 本窗仅比较已确认独立呼吸15的名义速率，不宣称绝对阻抗/频率校准或双通道PASS。
    return {'scope': SCOPE, 'menu': MENU, 'criteria': CRITERIA, 'tools_sha256': bindings(),
            'image_sha256': live.IMAGE_SHA, 'duration_s': 137, 'hard_limit_s': 180,
            'explicit_reset_halt_go_writes': 0, 'probe_sessions': 1, 'retries': 0,
            'Z0_ohm': None, 'delta_Zpp_ohm': None,
            'source_case_model': 'SKX-2000+', 'manual_model': 'SKX-2000D+ V2.2',
            'model_equivalence': 'NOT_PROVEN', 'new_C_receive_window': False,
            'leads': {'R': 'RA', 'L': 'LL', 'F': 'RL', 'LA': 'EMPTY'}}


def validate(a):
    live.need(a.get('enabled') is True and a.get('owner_approved') is True,
              'RESP15_CURRENT_OWNER_REQUIRED')
    live.need(a.get('plan') == plan(), 'RESP15_CURRENT_BINDINGS_DRIFT')
    live.need(a.get('observed_menu') == MENU and a.get('JLink_on_B') is True
              and a.get('battery_no_USB') is True, 'RESP15_CURRENT_SOURCE_ROUTE')
    live.need(time.time() < a.get('expires_unix', 0), 'RESP15_CURRENT_EXPIRED')


class Link(live.Link):
    def call(self, name, *args, timeout=5):
        # 仅扩大一个固定RAM槽块的读取范围；所有目标写/复位/暂停/Go API继续禁止。
        live.need(name in runtime.CALLS - {'JLINKARM_GetRegisterList', 'JLINKARM_GetRegisterName',
                                         'JLINKARM_ReadReg'}, 'RESP15_CURRENT_FUNCTION_DENIED')
        live.need(self.sdk_calls < 24000, 'RESP15_CURRENT_CALL_BUDGET')
        if name == 'JLINKARM_ExecCommand':
            command = args[0].decode('ascii')
            live.need(command in runtime.COMMANDS or command == 'SetRestartOnClose = 1',
                      'RESP15_CURRENT_COMMAND_DENIED')
            if command == 'SetRestartOnClose = 1':
                live.need(self.verified_running_flash, 'RESP15_CURRENT_CLOSE_NOT_VERIFIED')
        if name == 'JLINKARM_ReadMemEx':
            live.need(args[1] in READS.get(args[0], set()) and args[3] == 0,
                      'RESP15_CURRENT_READ_DENIED')
        self.sdk_calls += 1
        return raw.Link.call(self, name, *args, timeout=timeout)

    def read(self, address, size):
        live.need(size in READS.get(address, set()), 'RESP15_CURRENT_READ_DENIED')
        data = (C.c_uint8 * size)()
        live.need(self.call('JLINKARM_ReadMemEx', address, size, data, 0) == size,
                  'RESP15_CURRENT_PARTIAL_READ')
        return bytes(data)


def capture(link, out, reference):
    link.open()
    seen = raw.identity(link)
    raw.write_json(out / 'identity-private.json', seen)
    raw.check_identity(seen)
    live.need(seen == reference, 'RESP15_CURRENT_WRONG_BOARD')
    live.need(hashlib.sha256(link.read(0x08000000, 39948)).hexdigest() == live.IMAGE_SHA,
              'RESP15_CURRENT_WRONG_FIRMWARE')
    live.need(hashlib.sha256(link.read(0x1fffc000, 16)).hexdigest() == runtime.OPTIONS_SHA,
              'RESP15_CURRENT_OPTIONS_DRIFT')
    raw.write_json(out / 'entry-sticky-private.json', {'DHCSR': link.u32(live.ro.SYSTEM['DHCSR'])})
    first = live.snapshot(link, out, 'entry')
    raw.write_json(out / 'window-private.json', {'anchor_device_ms': first['bio']['last_sample_ms'],
                                               'frozen_plan': plan()})
    previous = first
    started = time.monotonic()
    index = 0
    with (out / 'slots-private.bin').open('xb') as slots, \
         (out / 'chunks-private.jsonl').open('x', encoding='utf-8') as chunks, \
         (out / 'diagnostics-private.jsonl').open('x', encoding='utf-8') as diagnostics:
        diagnostics.write(json.dumps(first) + '\n'); diagnostics.flush()
        while time.monotonic() - started < 137:
            live.need(index < 2741, 'RESP15_CURRENT_SLOT_BUDGET')
            target = started + index * .05
            if time.monotonic() < target:
                time.sleep(target - time.monotonic())
            state = link.u32(live.ro.SYSTEM['DHCSR'])
            if state & (raw.HALT | raw.LOCKUP | raw.RESET):
                # 新异常先保留实际状态，不以关闭时隐式Go恢复异常CPU。
                raw.write_json(out / 'changed-state-private.json', {'DHCSR': state, 'chunk': index})
                link.verified_running_flash = False
                raise ValueError('RESP15_CURRENT_CPU_CHANGED')
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
            'new_C_receive_window': False, 'explicit_reset_halt_go_writes': 0}


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
        live.need(args.authorization is not None and args.out is not None, 'RESP15_CURRENT_AUTH_OUT')
        a = json.loads(pkg.protected(args.authorization, False).read_text('utf-8')); validate(a)
        pkg.protected(args.out.parent, False)
        live.need(not args.out.exists(), 'RESP15_CURRENT_OUTPUT_EXISTS')
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
