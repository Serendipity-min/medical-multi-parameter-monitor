"""E3名义RR六格矩阵的单格入口；45秒预热、90秒评价、2秒尾段，准备态不能开SDK。"""
import argparse
import hashlib
import json
from pathlib import Path
import sys
import time

import capture_resp_b as base
import resp_rall20_b as capture
import recover_resp_rall20_b as recovery
import recover_resp_runtime_b as connection
from readback_b import Link, PRIVATE, HALT, LOCKUP, RESET, identity, check_identity, require, sha, write_json

ROOT = Path(__file__).resolve().parents[2]
SOURCE_SCHEMA = 'RESP_E3_RA_LL_SOURCE_1'
PROFILE_SCHEMA = 'RESP_E3_RA_LL_CAPTURE_137S_1'
SCOPE = 'E3_ONE_NORMAL_RESET_45_WARMUP_90_EVALUATION_2_TAIL'
CELLS = tuple(f'{rate}-r{repeat}' for rate in (12, 18, 24) for repeat in (1, 2))
DURATION, SLOT_LIMIT, SDK_LIMIT, SESSION_LIMIT = 137, 2741, 10000, 360
EVALUATION_MS = [45000, 135000]
READS = capture.READS | {0: 64}
# 地址级计数也受限，不能用总SDK预算把预检或整片核验重复执行。
READ_LIMITS = {a: 2 for a in READS}
READ_LIMITS.update({0: 1, 0xe000edf0: 2800, 0xe000ed08: 5, 0xe000101c: 10,
                    0x20001ae4: 277, 0x2000018c: 277, 0x200001bc: 277,
                    0x20001f30: SLOT_LIMIT, 0x20000000: 1})
CRITERIA = {'warmup_ms': [0, 45000], 'evaluation_ms': EVALUATION_MS, 'tail_ms': [135000, 137000],
            'rr_tolerance_rpm': 1, 'min_live_observations': 45, 'live_edge_tolerance_ms': 1500,
            'max_live_gap_ms': 2000, 'required_live_valid_fraction': 1.0,
            'sps_range': [240, 260], 'steady_frame_edge_tolerance_ms': 12,
            'repeat_raw_difference_rpm': 1, 'nominal_not_calibrated': True}


def bindings():
    # 已执行的21项共享依赖不改；新增三项入口和独立测试冻结本轮协议。
    names = ('resp_matrix_b.py', 'analyze_resp_matrix_b.py', 'supervise_resp_matrix_b.py')
    result = recovery.bindings() | {f'node-b/tools/{n}': sha(ROOT/'node-b/tools'/n) for n in names}
    return result | {'node-b/tests/test_resp_matrix_b.py': sha(ROOT/'node-b/tests/test_resp_matrix_b.py')}


def validate_source(s, cell, ready=False):
    require(cell in CELLS and s.get('cell') == cell, 'E3_SOURCE_CELL')
    target = int(cell.split('-')[0])
    require(s.get('schema') == SOURCE_SCHEMA and s.get('source_type') == 'RESP_EXPLORATORY'
            and s.get('stage') == 'E3' and s.get('target_rpm') == target, 'E3_SOURCE_SCHEMA')
    require(s.get('mode') == 'INDEPENDENT_RESPIRATION' and s.get('data_source') == 'ENGINEERING_NONHUMAN', 'E3_SOURCE_MODE')
    require(s.get('leads') == capture.LEADS and all(s.get(k) is True for k in
            ('battery_only', 'usb_disconnected', 'CAN_A_C_human_disconnected')), 'E3_ELECTRICAL_FACTS')
    require(all(k in s and s[k] is None for k in ('Z0_ohm', 'delta_Zpp_ohm', 'reference_rpm')), 'E3_UNKNOWN_TRUTH_NULL')
    require(s.get('dynamic_pair') == 'MANUFACTURER_MANUAL_RA_LL' and s.get('impedance_calibration') == 'NOT_CALIBRATED'
            and s.get('manual_sha256') == capture.MANUAL_SHA and s.get('acceptance_class') == 'NOMINAL_RATE_MATCH', 'E3_SOURCE_BOUNDARY')
    menu = s.get('menu', {})
    require(all(menu.get(k) == v for k, v in {'mode_literal': '呼吸波形', 'amplitude_literal': '1.5R',
            'waveform_period_literal': '20bpm', 'apnea_literal': '0s', 'ecg_rate_literal': '60BPM'}.items()), 'E3_FIXED_CONTROLS')
    require(s.get('apnea_semantics') == 'ZERO_DISPLAY_RECORDED_SEMANTICS_UNVERIFIED', 'E3_APNEA_SEMANTICS')
    if ready or s.get('operator_ready'):
        require(s.get('operator_ready') is True and s.get('menu_confirmed') is True
                and s.get('nominal_rpm') == target and menu.get('respiration_rate_literal') == f'{target}bpm', 'E3_RATE_NOT_SET')
        owner = Path(s.get('owner_confirmation_record', ''))
        require(owner.is_file() and sha(owner) == s.get('owner_confirmation_sha256')
                and owner.read_text('utf-8') == s.get('owner_confirmation') and bool(s['owner_confirmation']), 'E3_MENU_CONFIRMATION_BINDING')
        safety = Path(s.get('safety_record', ''))
        require(safety.is_file() and sha(safety) == s.get('safety_record_sha256'), 'E3_SAFETY_BINDING')
        facts = json.loads(safety.read_text('utf-8'))
        require(facts.get('status') == 'CONFIRMED_FOR_E3_RA_LL_137S' and all(facts.get(k) is True for k in
                ('RA_LL_setup_owner_reported', 'battery_no_USB', 'no_grounded_instrument', 'meter_removed_OFF',
                 'CAN_A_C_human_disconnected', 'no_shorts_or_abnormalities')) and bool(facts.get('electrical_basis')), 'E3_SAFETY_FACTS')
    else:
        # 计划目标与实际菜单分开；当前30不能写成已设12/18/24。
        require(s.get('nominal_rpm') is None and menu.get('respiration_rate_literal') is None
                and s.get('menu_confirmed') is False and s.get('operator_ready') is False, 'E3_TEMPLATE_NOT_ACTUAL')
    return 'E3_SOURCE_READY' if ready else 'E3_SOURCE_RECORDED_NOT_PERMISSION'


def validate_profile(p):
    require(p.get('schema') == PROFILE_SCHEMA and p.get('source_schema') == SOURCE_SCHEMA, 'E3_NO_OLD_PROFILE')
    require(p.get('cell') in CELLS and p.get('scope') == SCOPE, 'E3_PROFILE_CELL_SCOPE')
    require(p.get('duration_s') == DURATION and p.get('slot_limit') == SLOT_LIMIT
            and p.get('criteria') == CRITERIA, 'E3_FROZEN_TIMING_CRITERIA')
    require(p.get('sdk_call_limit') == SDK_LIMIT and p.get('session_timeout_s') == SESSION_LIMIT
            and p.get('tools_sha256') == bindings(), 'E3_TOOL_BUDGET')
    require(p.get('read_regions') == {hex(a): n for a, n in READS.items()}
            and p.get('read_limits') == {hex(a): n for a, n in READ_LIMITS.items()}, 'E3_READ_SCOPE')
    anchor = Path(p.get('frozen_ABI_binding_profile', ''))
    require(anchor.is_file() and sha(anchor) == p.get('frozen_ABI_binding_sha256'), 'E3_ABI_ANCHOR')
    # 旧E1仅是ABI身份锚点；本轮源、时限和权限全部由独立E3文件给出。
    base.validate(json.loads(anchor.read_text('utf-8')))
    return 'E3_PROFILE_BOUND_NOT_PERMISSION'


class MatrixLink(recovery.RecoveryRallLink):
    def __init__(self, dll, out):
        self.read_counts = {}
        self.function_counts = {}
        super().__init__(dll, out)

    def gate(self):
        # 137秒采样及前末整片读的专用硬时限，不修改旧入口240秒规则。
        require(not (self.out/'STOP').exists(), 'OWNER_STOP')
        require(time.monotonic()-self.started <= SESSION_LIMIT, 'E3_SESSION_TIMEOUT')
        require(not self.error, 'SDK_ERROR_SEE_PRIVATE_LOG')

    def call(self, name, *args, timeout=5):
        require(name in connection.CALLS, 'E3_SDK_FUNCTION_DENIED')
        require(self.counts['sdk_calls'] < SDK_LIMIT, 'E3_SDK_BUDGET')
        if name == 'JLINKARM_ExecCommand':
            command = args[0].decode('ascii')
            require(command in connection.COMMANDS, 'E3_COMMAND_DENIED')
            if command == 'SetResetType = 0':
                require(self.reset_phase, 'E3_RESET_POLICY_PHASE')
        if name == 'JLINKARM_Reset':
            require(self.reset_phase, 'E3_RESET_PHASE')
        if name == 'JLINKARM_ReadMemEx':
            address, size = args[:2]
            require(READS.get(address) == size and args[3] == 0, 'E3_READ_SCOPE')
            require(address != 0 or self.alias_phase, 'E3_ALIAS_PHASE')
            count = self.read_counts.get(address, 0)
            require(count < READ_LIMITS[address], 'E3_ADDRESS_READ_BUDGET')
            self.read_counts[address] = count+1
            timeout = min(timeout, 45 if size == 1048576 else (15 if size == 131072 else 5))
        function_limits = {'JLINKARM_OpenEx': 1, 'JLINKARM_Connect': 1, 'JLINKARM_GetRegisterList': 1,
                           'JLINKARM_GetRegisterName': 256, 'JLINKARM_ReadReg': 21}
        if name in function_limits:
            count = self.function_counts.get(name, 0)
            require(count < function_limits[name], 'E3_FUNCTION_BUDGET')
            self.function_counts[name] = count+1
        if name in ('JLINKARM_GetRegisterList', 'JLINKARM_GetRegisterName', 'JLINKARM_ReadReg'):
            require(self.register_reads_allowed, 'E3_CORE_REQUIRES_HALT')
        limits = {'JLINKARM_Reset': ('reset_requests', 1), 'JLINKARM_Halt': ('halt_requests', 1), 'JLINKARM_Go': ('go_requests', 2)}
        if name in limits:
            key, limit = limits[name]
            require(self.counts[key] < limit, 'E3_CONTROL_BUDGET')
            self.counts[key] += 1
        self.counts['sdk_calls'] += 1
        # 只进入冻结底层心跳包装，避免祖先4000次预算/重复计数；白名单在上方完整重申。
        return Link.call(self, name, *args, timeout=timeout)


def collect(link, binding, out, receipt):
    started = time.monotonic(); index = 0
    # 不因RR提前有效缩窗，不因失效延窗；原始诊断和每块SHA即时落盘。
    with (out/'running-slots-private.bin').open('xb') as raw, \
            (out/'chunks-private.jsonl').open('x', encoding='utf-8') as chunks, \
            (out/'diagnostics-private.jsonl').open('x', encoding='utf-8') as diags:
        while time.monotonic()-started < DURATION:
            require(index < SLOT_LIMIT, 'E3_SLOT_BUDGET')
            target = started+index*.05
            if time.monotonic() < target:
                time.sleep(target-time.monotonic())
            require(not link.u32(0xe000edf0) & (HALT | LOCKUP | RESET), 'E3_WINDOW_STATE_CHANGED')
            a = time.monotonic(); blob = link.read(0x20001f30, 3072); b = time.monotonic()
            offset = raw.tell(); raw.write(blob); raw.flush()
            chunks.write(json.dumps({'index': index, 'offset': offset, 'bytes': len(blob),
                'host_start_s': a, 'host_end_s': b, 'sha256': hashlib.sha256(blob).hexdigest()})+'\n'); chunks.flush()
            if index % 10 == 0:
                diagnostic = base.snapshot(link, out, index)
                diags.write(json.dumps(diagnostic)+'\n'); diags.flush(); capture.check_input(diagnostic)
            index += 1
    receipt.update(window_elapsed_s=time.monotonic()-started, chunks=index)
    require(link.call('JLINKARM_Halt', timeout=3) == 0, 'E3_TAIL_HALT_FAILED')
    link.stable_halt(); ram = link.read(0x20000000, 131072); link.stable_halt()
    with (out/'final-paused-ram-private.bin').open('xb') as stream:
        stream.write(ram)
    receipt.update(tail_halt_confirmed=True, ram_sha256=sha(out/'final-paused-ram-private.bin'))
    require(hashlib.sha256(link.read(0x08000000, 1048576)).hexdigest() == binding['flash_sha256'], 'E3_END_FLASH_DRIFT')
    require(hashlib.sha256(link.read(0x1fffc000, 16)).hexdigest() == binding['options_sha256'], 'E3_END_OPTIONS_DRIFT')
    final = identity(link); check_identity(final)
    reference = json.loads(Path(binding['identity_reference']).read_text('utf-8'))
    require(final['uid_hex'] == reference['uid_hex'] and final['optcr'] == reference['optcr'], 'E3_END_BOARD_DRIFT')
    link.stable_halt(); link.call('JLINKARM_Go'); time.sleep(.02)
    require(not link.u32(0xe000edf0) & (HALT | LOCKUP | RESET), 'E3_RESUME_FAILED')
    receipt.update(status='RESP_CAPTURE_FILES_SAVED', resume_confirmed=True, target_end_state='RUNNING_BEFORE_CLOSE')


def authorize(args):
    m = json.loads(args.manifest.read_text('utf-8'))
    require(m.get('enabled') is True and m.get('owner_reset_authorized') is True, 'E3_NOT_AUTHORIZED')
    require(args.out.resolve().is_relative_to(PRIVATE.resolve()) and not args.out.exists(), 'E3_EXCLUSIVE_OUTPUT')
    owner = Path(m['owner_request_record'])
    require(sha(owner) == m['owner_request_sha256'] and owner.read_text('utf-8') == m['owner_request']
            and bool(m['owner_request']), 'E3_OWNER_BINDING')
    require(sha(args.card) == args.card_sha256 == m['card_sha256'] and m['tools_sha256'] == bindings(), 'E3_CARD_TOOLS')
    # 分格卡继承的共同协议同样核字节，避免只冻结短卡却漏掉其权限/判据正文。
    protocol = Path(m['protocol_record'])
    require(sha(protocol) == m['protocol_sha256'] and m['protocol_sha256'] in args.card.read_text('utf-8'), 'E3_PROTOCOL_BINDING')
    require(args.out.resolve() == Path(m['out']).resolve() and args.dll.resolve() == Path(m['dll']).resolve()
            and sha(args.dll) == m['dll_sha256'], 'E3_ARGUMENTS')
    profile_path, source_path = Path(m['profile']), Path(m['source_record'])
    require(sha(profile_path) == m['profile_sha256'] and sha(source_path) == m['source_record_sha256'], 'E3_PROFILE_SOURCE_SHA')
    p = json.loads(profile_path.read_text('utf-8')); validate_profile(p)
    s = json.loads(source_path.read_text('utf-8')); validate_source(s, p['cell'], ready=True)
    require(m.get('cell') == p['cell'] and s['owner_confirmation_sha256'] == m.get('menu_confirmation_sha256'), 'E3_CELL_MENU_BINDING')
    # 前格失败不能自动进入后格；六次为独立计划格，不是失败重试机会。
    index = CELLS.index(p['cell'])
    if index:
        previous = Path(m['previous_analysis'])
        require(sha(previous) == m.get('previous_analysis_sha256'), 'E3_PREVIOUS_SHA')
        last = json.loads(previous.read_text('utf-8'))
        require(last.get('cell') == CELLS[index-1] and last.get('analysis_exit_code') == 0
                and last.get('status') == 'E3_CELL_NOMINAL_RATE_MATCH', 'E3_PREVIOUS_NOT_PASS')
    marker = PRIVATE/'resp-003/e3-matrix-r1'/('attempt-'+p['cell']+'.json')
    require(not marker.exists(), 'E3_CELL_ALREADY_ATTEMPTED')
    return m, p, s, marker


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('dll', 'card', 'manifest', 'out'):
        parser.add_argument('--'+name, required=True, type=Path)
    parser.add_argument('--card-sha256', required=True)
    args = parser.parse_args()
    m, profile, source, marker = authorize(args)
    # 令牌在SDK前独占消耗；进程崩溃也不得换目录暗中重试同格。
    write_json(marker, {'cell': profile['cell'], 'manifest_sha256': sha(args.manifest), 'status': 'ATTEMPT_RESERVED'})
    binding = json.loads(Path(profile['frozen_ABI_binding_profile']).read_text('utf-8'))
    args.out.mkdir(); link = None
    receipt = {'status': 'RESP_CAPTURE_STARTED', 'process_exit_code': 1, 'tail_halt_confirmed': False,
               'resume_confirmed': False, 'target_end_state': 'UNKNOWN', 'board_open_attempted': False,
               'stage': 'E3', 'cell': profile['cell'], 'source_type': 'RESP_EXPLORATORY', 'duration_s': DURATION,
               'profile_sha256': m['profile_sha256'], 'source_record_sha256': m['source_record_sha256'],
               'card_sha256': args.card_sha256, 'tools_sha256': bindings(), 'criteria': CRITERIA}
    try:
        link = MatrixLink(args.dll.resolve(), args.out); receipt['board_open_attempted'] = True
        recovery.restore(link, binding, args.out); collect(link, binding, args.out, receipt)
    except BaseException as error:
        receipt.update(status='RESP_CAPTURE_STOP', error=type(error).__name__+': '+str(error))
    finally:
        if link:
            receipt.update(link.counts, read_counts={hex(a): n for a, n in link.read_counts.items()}, function_counts=link.function_counts)
            try:
                link.close()
            except BaseException as error:
                receipt.update(status='RESP_CAPTURE_STOP', close_error=type(error).__name__+': '+str(error))
    if receipt['status'] == 'RESP_CAPTURE_FILES_SAVED':
        try:
            receipt['export'] = base.export(args.out)
            receipt.update(stable_raw_sha256=sha(args.out/'stable-raw-private.csv'),
                           diagnostics_sha256=sha(args.out/'diagnostics-private.jsonl'), process_exit_code=0)
        except BaseException as error:
            receipt.update(status='RESP_EXPORT_FAILED', error=type(error).__name__+': '+str(error), process_exit_code=2)
    write_json(args.out/'receipt-private.json', receipt)
    print(json.dumps({k: receipt[k] for k in ('status', 'process_exit_code', 'target_end_state')}))
    return receipt['process_exit_code']


if __name__ == '__main__':
    sys.exit(main())
