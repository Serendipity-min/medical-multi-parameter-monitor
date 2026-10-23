"""RA–LL呼吸30单窗：复用冻结恢复/采样，独立源和profile，对照20bpm基线。"""
import argparse
import json
from pathlib import Path
import sys
import resp_rall20_b as capture
import capture_resp_b as base
import recover_resp_rall20_b as recovery
from readback_b import PRIVATE, require, sha, write_json

ROOT = Path(__file__).resolve().parents[2]
SOURCE_SCHEMA = 'RESP_RA_LL30_SOURCE_1'
PROFILE_SCHEMA = 'RESP_RA_LL30_CAPTURE_45S_1'
DURATION = 45
SLOT_LIMIT = 901
LEADS = capture.LEADS.copy()
MANUAL_SHA = capture.MANUAL_SHA
READS = capture.READS | {0: 64}
BASELINE_SHA = '954a06da964f538e99f851ceff878974955882783f6ba84ea97537e6e4171406'


def bindings():
    # 旧20窗口的21项依赖保持原字节；本窗新增入口、分析、监督与对照四项。
    names = ('resp_rall30_b.py', 'analyze_resp_rall30_b.py',
             'supervise_resp_rall30_b.py', 'compare_resp_20_30_b.py')
    return recovery.bindings() | {(ROOT/'node-b/tools'/name).relative_to(ROOT).as_posix():
                                 sha(ROOT/'node-b/tools'/name) for name in names}


def validate_source(source, ready=False):
    require(source.get('schema') == SOURCE_SCHEMA and source.get('source_type') == 'RESP_EXPLORATORY', 'VALIDITY_SOURCE_SCHEMA')
    require(source.get('stage') == 'RESP_RA_LL30_SINGLE_WINDOW'
            and source.get('mode') == 'INDEPENDENT_RESPIRATION', 'VALIDITY_MODE')
    require(source.get('data_source') == 'ENGINEERING_NONHUMAN', 'VALIDITY_NONHUMAN')
    require(source.get('leads') == LEADS and all(source.get(k) is True for k in
            ('battery_only', 'usb_disconnected', 'CAN_A_C_human_disconnected')), 'VALIDITY_ELECTRICAL_FACTS')
    # 呼吸率30与波形周期20是不同菜单项；名义设置不能充当独立标定的频率真值。
    require(all(k in source and source[k] is None for k in ('Z0_ohm', 'delta_Zpp_ohm', 'reference_rpm')), 'VALIDITY_UNKNOWN_TRUTH_NULL')
    require(source.get('impedance_calibration') == 'NOT_CALIBRATED'
            and source.get('dynamic_pair') == 'MANUFACTURER_MANUAL_RA_LL', 'VALIDITY_NO_Z_CALIBRATION')
    require(source.get('manual_sha256') == MANUAL_SHA, 'RALL30_MANUAL_BINDING')
    require(source.get('acceptance_class') == 'RAW_PERIOD_AND_BIO_VALIDITY_NOT_SOURCE_ACCURACY', 'VALIDITY_ACCEPTANCE_CLASS')
    menu = source.get('menu', {})
    require(menu.get('mode_literal') == '呼吸波形' and menu.get('amplitude_literal') == '1.5R'
            and menu.get('waveform_period_literal') == '20bpm'
            and menu.get('respiration_rate_literal') == '30bpm'
            and menu.get('ecg_rate_literal') == '60BPM'
            and menu.get('apnea_literal') == '0s'
            and source.get('nominal_rpm') == 30, 'VALIDITY_ACTUAL_MENU')
    require(source.get('apnea_semantics') == 'ZERO_DISPLAY_RECORDED_SEMANTICS_UNVERIFIED', 'VALIDITY_APNEA_NOT_ASSUMED')
    if ready:
        require(source.get('operator_ready') is True and bool(source.get('owner_confirmation')), 'VALIDITY_SOURCE_NOT_READY')
        record = Path(source.get('safety_record', ''))
        require(record.is_file() and sha(record) == source.get('safety_record_sha256'), 'VALIDITY_SAFETY_BINDING')
        safety = json.loads(record.read_text('utf-8'))
        require(safety.get('status') == 'CONFIRMED_FOR_BOUNDED_RESP_RA_LL30_45S'
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
    require(profile.get('baseline_summary_sha256') == BASELINE_SHA, 'RALL30_BASELINE_BINDING')
    anchor = Path(profile.get('frozen_ABI_binding_profile', ''))
    require(anchor.is_file() and sha(anchor) == profile.get('frozen_ABI_binding_sha256'), 'VALIDITY_ABI_ANCHOR')
    # 这里只验证冻结固件/ABI身份，不冒用10秒profile作为本次运行权限或源类型。
    base.validate(json.loads(anchor.read_text('utf-8')))
    return 'VALIDITY_PROFILE_BOUND'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('dll', 'card', 'manifest', 'out'):
        parser.add_argument('--'+name, required=True, type=Path)
    parser.add_argument('--card-sha256', required=True)
    args = parser.parse_args()
    require(args.out.resolve().is_relative_to(PRIVATE.resolve()) and not args.out.exists(), 'RALL_RECOVERY_EXCLUSIVE_PRIVATE_OUTPUT')
    m = json.loads(args.manifest.read_text('utf-8'))
    require(m.get('enabled') is True and m.get('owner_reset_authorized') is True, 'RALL_RECOVERY_NOT_AUTHORIZED')
    owner = Path(m['owner_request_record'])
    require(sha(owner) == m['owner_request_sha256'] and owner.read_text('utf-8') == m['owner_request'], 'RALL_RECOVERY_OWNER_BINDING')
    require(sha(args.card) == args.card_sha256 == m['card_sha256'] and bindings() == m['tools_sha256'], 'RALL_RECOVERY_CARD_TOOLS')
    require(args.dll.resolve() == Path(m['dll']).resolve() and sha(args.dll) == m['dll_sha256']
            and args.out.resolve() == Path(m['out']).resolve(), 'RALL_RECOVERY_ARGUMENTS')
    profile_path = Path(m['profile']); source_path = Path(m['source_record'])
    require(sha(profile_path) == m['profile_sha256'] and sha(source_path) == m['source_record_sha256'], 'RALL_RECOVERY_PROFILE_SOURCE_SHA')
    profile = json.loads(profile_path.read_text('utf-8')); validate_profile(profile)
    source = json.loads(source_path.read_text('utf-8')); validate_source(source, ready=True)
    require(profile.get('recovery_scope') == source.get('recovery_scope') == 'E2_MATCHED_20_TO_30_SINGLE_NORMAL_RESET_45S', 'RALL_RECOVERY_SCOPE')
    binding = json.loads(Path(profile['frozen_ABI_binding_profile']).read_text('utf-8'))
    args.out.mkdir(); link = None
    receipt = {'status': 'RESP_CAPTURE_STARTED', 'process_exit_code': 1, 'tail_halt_confirmed': False,
               'resume_confirmed': False, 'target_end_state': 'UNKNOWN', 'board_open_attempted': False,
               'stage': 'RESP_RA_LL30_SINGLE_WINDOW', 'source_type': 'RESP_EXPLORATORY', 'duration_s': 45,
               'profile_sha256': sha(profile_path), 'source_record_sha256': sha(source_path),
               'card_sha256': args.card_sha256, 'tools_sha256': bindings()}
    try:
        link = recovery.RecoveryRallLink(args.dll.resolve(), args.out); receipt['board_open_attempted'] = True
        recovery.restore(link, binding, args.out); capture.collect(link, binding, args.out, receipt)
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
            receipt['export'] = capture.base.export(args.out)
            receipt.update(stable_raw_sha256=sha(args.out/'stable-raw-private.csv'),
                           diagnostics_sha256=sha(args.out/'diagnostics-private.jsonl'), process_exit_code=0)
        except BaseException as error:
            receipt.update(status='RESP_EXPORT_FAILED', error=type(error).__name__+': '+str(error), process_exit_code=2)
    write_json(args.out/'receipt-private.json', receipt)
    print(json.dumps({k: receipt[k] for k in ('status', 'process_exit_code', 'target_end_state')}))
    return receipt['process_exit_code']


if __name__ == '__main__':
    sys.exit(main())
