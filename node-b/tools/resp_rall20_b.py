"""RA–LL呼吸20独立单窗：分别保存呼吸率和波形周期，冻结45秒，不修改算法或换算未知阻抗。"""
import argparse
import hashlib
import json
from pathlib import Path
import sys
import time

import capture_resp_b as base
import recover_resp_runtime_b as connection
import runtime_state_b as runtime
from readback_b import PRIVATE, HALT, LOCKUP, RESET, identity, check_identity, require, sha, write_json
# 新窗口明确使用厂家RA–LL路径；旧模块的LEADS与历史profile不改。
LEADS = {'R_red': 'RA', 'L_yellow': 'LL', 'F_green': 'RL'}
MANUAL_SHA = '8b264906747e76336e7a7221ab77b76e3697078f794b064e77081e7e56fc48aa'

ROOT = Path(__file__).resolve().parents[2]
SOURCE_SCHEMA = 'RESP_RA_LL20_SOURCE_1'
PROFILE_SCHEMA = 'RESP_RA_LL20_CAPTURE_45S_1'
DURATION = 45
SLOT_LIMIT = 901
READS = base.READS | {0xe000ed08: 4, 0xe000101c: 4}


def bindings():
    # 新入口分别冻结；之前10秒profile和全部已执行工具保持原字节。
    return connection.bindings() | {p.relative_to(ROOT).as_posix(): sha(p) for p in
        (Path(__file__), ROOT/'node-b/tools/analyze_resp_rall20_b.py',
         ROOT/'node-b/tools/supervise_resp_rall20_b.py')}


def validate_source(source, ready=False):
    require(source.get('schema') == SOURCE_SCHEMA and source.get('source_type') == 'RESP_EXPLORATORY', 'VALIDITY_SOURCE_SCHEMA')
    require(source.get('stage') == 'RESP_RA_LL20_SINGLE_WINDOW'
            and source.get('mode') == 'INDEPENDENT_RESPIRATION', 'VALIDITY_MODE')
    require(source.get('data_source') == 'ENGINEERING_NONHUMAN', 'VALIDITY_NONHUMAN')
    require(source.get('leads') == LEADS and all(source.get(k) is True for k in
            ('battery_only', 'usb_disconnected', 'CAN_A_C_human_disconnected')), 'VALIDITY_ELECTRICAL_FACTS')
    # 呼吸率20与波形周期20是不同菜单项；名义设置不能充当独立标定的频率真值。
    require(all(k in source and source[k] is None for k in ('Z0_ohm', 'delta_Zpp_ohm', 'reference_rpm')), 'VALIDITY_UNKNOWN_TRUTH_NULL')
    require(source.get('impedance_calibration') == 'NOT_CALIBRATED'
            and source.get('dynamic_pair') == 'MANUFACTURER_MANUAL_RA_LL', 'VALIDITY_NO_Z_CALIBRATION')
    require(source.get('manual_sha256') == MANUAL_SHA, 'RALL20_MANUAL_BINDING')
    require(source.get('acceptance_class') == 'RAW_PERIOD_AND_BIO_VALIDITY_NOT_SOURCE_ACCURACY', 'VALIDITY_ACCEPTANCE_CLASS')
    menu = source.get('menu', {})
    require(menu.get('mode_literal') == '呼吸波形' and menu.get('amplitude_literal') == '1.5R'
            and menu.get('waveform_period_literal') == '20bpm'
            and menu.get('respiration_rate_literal') == '20bpm'
            and menu.get('ecg_rate_literal') == '60BPM'
            and menu.get('apnea_literal') == '0s'
            and source.get('nominal_rpm') == 20, 'VALIDITY_ACTUAL_MENU')
    require(source.get('apnea_semantics') == 'ZERO_DISPLAY_RECORDED_SEMANTICS_UNVERIFIED', 'VALIDITY_APNEA_NOT_ASSUMED')
    if ready:
        require(source.get('operator_ready') is True and bool(source.get('owner_confirmation')), 'VALIDITY_SOURCE_NOT_READY')
        record = Path(source.get('safety_record', ''))
        require(record.is_file() and sha(record) == source.get('safety_record_sha256'), 'VALIDITY_SAFETY_BINDING')
        safety = json.loads(record.read_text('utf-8'))
        require(safety.get('status') == 'CONFIRMED_FOR_BOUNDED_RESP_RA_LL20_45S'
                and all(safety.get(k) is True for k in ('RA_LL_setup_owner_reported', 'battery_no_USB',
                'no_grounded_instrument', 'meter_removed_OFF', 'CAN_A_C_human_disconnected'))
                and bool(safety.get('electrical_basis')), 'VALIDITY_SAFETY_FACTS')
    return 'VALIDITY_SOURCE_READY' if ready else 'VALIDITY_SOURCE_RECORDED'


def validate_profile(profile):
    require(profile.get('schema') == PROFILE_SCHEMA and profile.get('source_schema') == SOURCE_SCHEMA, 'VALIDITY_PROFILE_NO_ECG_REUSE')
    require(profile.get('duration_s') == DURATION and profile.get('slot_limit') == SLOT_LIMIT
            and profile.get('evaluation_ms') == [10000, 40000], 'VALIDITY_FROZEN_DURATION')
    require(profile.get('tools_sha256') == bindings() and profile.get('sdk_call_limit') == 4000
            and profile.get('session_timeout_s') == 240, 'VALIDITY_TOOL_BUDGET')
    require(profile.get('read_regions') == {hex(a): n for a, n in READS.items()}, 'VALIDITY_READ_SCOPE')
    anchor = Path(profile.get('frozen_ABI_binding_profile', ''))
    require(anchor.is_file() and sha(anchor) == profile.get('frozen_ABI_binding_sha256'), 'VALIDITY_ABI_ANCHOR')
    # 这里只验证冻结固件/ABI身份，不冒用10秒profile作为本次运行权限或源类型。
    base.validate(json.loads(anchor.read_text('utf-8')))
    return 'VALIDITY_PROFILE_BOUND'


class ValidityLink(connection.RecoveryLink):
    def call(self, name, *args, timeout=5):
        require(name != 'JLINKARM_Reset', 'VALIDITY_RESET_DENIED')
        if name == 'JLINKARM_ExecCommand':
            require(args[0] != b'SetResetType = 0', 'VALIDITY_RESET_POLICY_DENIED')
        if name == 'JLINKARM_ReadMemEx':
            require(READS.get(args[0]) == args[1], 'VALIDITY_READ_SCOPE')
        return super().call(name, *args, timeout=timeout)


def ready_snapshot(link, folder, index):
    """只取采集准入需要的PC/VTOR和故障状态，不展开BOOT/关闭重连问题调查。"""
    system = {k: link.u32(a) for k, a in
              (('DHCSR', 0xe000edf0), ('VTOR', 0xe000ed08), ('CFSR', 0xe000ed28), ('HFSR', 0xe000ed2c))}
    pcs = []
    for _ in range(5):
        pcs.append(link.u32(0xe000101c)); time.sleep(.02)
    bio = base.snapshot(link, folder, index)
    result = {'label': 'attach-entry' if index == 0 else 'ready', 'system': system,
              'pc_samples': pcs, 'pc_regions': [runtime.pc_region(x) for x in pcs],
              'bio': bio, 'DHCSR_after': link.u32(0xe000edf0)}
    write_json(folder/f'{index:04d}-ready-private.json', result)
    return result


def precheck(link, binding, out):
    folder = out/'precheck'; folder.mkdir()
    link.open(); seen = identity(link); check_identity(seen)
    reference = json.loads(Path(binding['identity_reference']).read_text('utf-8'))
    require(seen['uid_hex'] == reference['uid_hex'] and seen['optcr'] == reference['optcr'], 'VALIDITY_BOARD_BINDING')
    write_json(folder/'identity-private.json', seen)
    flash_sha = hashlib.sha256(link.read(0x08000000, 1048576)).hexdigest()
    options_sha = hashlib.sha256(link.read(0x1fffc000, 16)).hexdigest()
    write_json(folder/'image-hashes.json', {'flash_sha256': flash_sha, 'options_sha256': options_sha})
    require(flash_sha == binding['flash_sha256'] and options_sha == binding['options_sha256'], 'VALIDITY_FLASH_OPTIONS_DRIFT')
    state = link.u32(0xe000edf0)
    write_json(folder/'initial-state-private.json', {'DHCSR': state, 'VTOR': link.u32(0xe000ed08)})
    require(not state & LOCKUP, 'VALIDITY_LOCKUP')
    if state & HALT:
        # 会话间已暂停时，只续跑实际Flash候选且无fault的应用；ROM绝不直接go。
        core = runtime.core_if_halted(link); write_json(folder/'halted-core-private.json', core)
        require(runtime.pc_region(core.get('registers', {}).get('R15', 0)) == 'BIO_V2_FLASH'
                and link.u32(0xe000ed08) == 0x08000000
                and link.u32(0xe000ed28) == link.u32(0xe000ed2c) == 0, 'VALIDITY_HALTED_NOT_SAFE_FLASH')
        require(link.u32(0xe000edf0) & HALT, 'VALIDITY_HALT_CHANGED')
        link.call('JLINKARM_Go'); time.sleep(.5)
    observations = [ready_snapshot(link, folder, 0)]
    time.sleep(.5); observations.append(ready_snapshot(link, folder, 1))
    for observation in observations:
        check_input(observation['bio'])
    gate = runtime.capture_gate(observations); write_json(folder/'gate-private.json', gate)
    require(gate['status'] == 'READY_FOR_NEW_CAPTURE_CARD', 'VALIDITY_RUNNING_GATE_FAILED')


def check_input(diagnostic):
    require(not any(diagnostic['adc'][k] for k in ('init_errors', 'spi_errors', 'bad_status', 'queue_overflow')), 'VALIDITY_ADC_ERROR')
    require(abs(diagnostic['resp_raw']) < 8220835 and abs(diagnostic['ecg_raw']) < 8220835, 'VALIDITY_NEAR_RAIL')
    actual = bytes.fromhex(diagnostic['registers_hex'])
    expected = {0: 0x73, 1: 1, 2: 0xe0, 3: 0xf0, 4: 0x40, 5: 0x40, 6: 0xec, 7: 0, 9: 0xea, 10: 3, 11: 0x0c}
    require(all(actual[k] & (0xfc if k == 11 else 255) == v for k, v in expected.items()), 'VALIDITY_INIT_CACHE_DRIFT')


def collect(link, binding, out, receipt):
    started = time.monotonic(); index = 0
    # 固定45秒和单调时钟，诊断即时保存，失败不得靠多采一轮消除。
    with (out/'running-slots-private.bin').open('xb') as raw, \
            (out/'chunks-private.jsonl').open('x', encoding='utf-8') as chunks, \
            (out/'diagnostics-private.jsonl').open('x', encoding='utf-8') as diags:
        while time.monotonic()-started < DURATION:
            require(index < SLOT_LIMIT, 'VALIDITY_SLOT_BUDGET')
            target = started+index*.05
            if time.monotonic() < target:
                time.sleep(target-time.monotonic())
            require(not link.u32(0xe000edf0) & (HALT | LOCKUP | RESET), 'VALIDITY_WINDOW_STATE_CHANGED')
            a = time.monotonic(); blob = link.read(0x20001f30, 3072); b = time.monotonic()
            offset = raw.tell(); raw.write(blob); raw.flush()
            chunks.write(json.dumps({'index': index, 'offset': offset, 'bytes': len(blob),
                'host_start_s': a, 'host_end_s': b, 'sha256': hashlib.sha256(blob).hexdigest()})+'\n'); chunks.flush()
            if index % 10 == 0:
                d = base.snapshot(link, out, index)
                diags.write(json.dumps(d)+'\n'); diags.flush(); check_input(d)
            index += 1
    receipt.update(window_elapsed_s=time.monotonic()-started, chunks=index)
    require(link.call('JLINKARM_Halt', timeout=3) == 0, 'VALIDITY_TAIL_HALT_FAILED')
    link.stable_halt(); ram = link.read(0x20000000, 131072); link.stable_halt()
    with (out/'final-paused-ram-private.bin').open('xb') as stream:
        stream.write(ram)
    receipt.update(tail_halt_confirmed=True, ram_sha256=sha(out/'final-paused-ram-private.bin'))
    require(hashlib.sha256(link.read(0x08000000, 1048576)).hexdigest() == binding['flash_sha256'], 'VALIDITY_END_FLASH_DRIFT')
    require(hashlib.sha256(link.read(0x1fffc000, 16)).hexdigest() == binding['options_sha256'], 'VALIDITY_END_OPTIONS_DRIFT')
    final = identity(link); check_identity(final)
    reference = json.loads(Path(binding['identity_reference']).read_text('utf-8'))
    require(final['uid_hex'] == reference['uid_hex'] and final['optcr'] == reference['optcr'], 'VALIDITY_END_IDENTITY_DRIFT')
    link.stable_halt(); link.call('JLINKARM_Go'); time.sleep(.02)
    require(not link.u32(0xe000edf0) & (HALT | LOCKUP | RESET), 'VALIDITY_RESUME_FAILED')
    receipt.update(status='RESP_CAPTURE_FILES_SAVED', resume_confirmed=True, target_end_state='RUNNING_BEFORE_CLOSE')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('dll', 'card', 'manifest', 'out'):
        parser.add_argument('--'+name, required=True, type=Path)
    parser.add_argument('--card-sha256', required=True)
    args = parser.parse_args()
    require(args.out.resolve().is_relative_to(PRIVATE.resolve()) and not args.out.exists(), 'VALIDITY_PRIVATE_EXCLUSIVE_OUTPUT')
    m = json.loads(args.manifest.read_text('utf-8'))
    require(m['enabled'] is True and bool(m['owner_request']), 'VALIDITY_NOT_AUTHORIZED')
    require(sha(Path(m['owner_request_record'])) == m['owner_request_sha256'], 'VALIDITY_OWNER_REQUEST_BINDING')
    # 原话字节和清单文字双重绑定；确认不是任意非空字符串即可打开硬件。
    require(Path(m['owner_request_record']).read_text('utf-8') == m['owner_request'], 'RALL20_OWNER_TEXT_MISMATCH')
    require(sha(args.card) == args.card_sha256 == m['card_sha256'] and bindings() == m['tools_sha256'], 'VALIDITY_CARD_TOOLS_DRIFT')
    require(args.out.resolve() == Path(m['out']).resolve() and args.dll.resolve() == Path(m['dll']).resolve()
            and sha(args.dll) == m['dll_sha256'], 'VALIDITY_ARGUMENT_BINDING')
    profile_path = Path(m['profile']); source_path = Path(m['source_record'])
    require(sha(profile_path) == m['profile_sha256'] and sha(source_path) == m['source_record_sha256'], 'VALIDITY_SOURCE_PROFILE_DRIFT')
    profile = json.loads(profile_path.read_text('utf-8')); validate_profile(profile)
    validate_source(json.loads(source_path.read_text('utf-8')), ready=True)
    binding = json.loads(Path(profile['frozen_ABI_binding_profile']).read_text('utf-8'))
    args.out.mkdir(); link = None
    receipt = {'status': 'RESP_CAPTURE_STARTED', 'process_exit_code': 1, 'tail_halt_confirmed': False,
        'resume_confirmed': False, 'target_end_state': 'UNKNOWN', 'board_open_attempted': False,
        'stage': 'RESP_RA_LL20_SINGLE_WINDOW', 'source_type': 'RESP_EXPLORATORY', 'duration_s': DURATION,
        'profile_sha256': sha(profile_path), 'source_record_sha256': sha(source_path),
        'card_sha256': args.card_sha256, 'tools_sha256': bindings()}
    try:
        link = ValidityLink(args.dll.resolve(), args.out); receipt['board_open_attempted'] = True
        precheck(link, binding, args.out); collect(link, binding, args.out, receipt)
    except BaseException as error:
        receipt.update(status='RESP_CAPTURE_STOP', error=type(error).__name__+': '+str(error))
    finally:
        if link:
            receipt.update(link.counts)
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
