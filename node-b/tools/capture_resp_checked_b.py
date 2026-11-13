"""当前已运行状态下的独立RESP卡：先核VTOR/PCSR及BIO推进，不允许复位或重试。"""
import argparse
import hashlib
import json
from pathlib import Path
import sys
import time

import capture_resp_b as capture
import recover_resp_runtime_b as recovery
import runtime_state_b as runtime
from readback_b import PRIVATE, HALT, LOCKUP, RESET, identity, check_identity, require, sha, write_json
from resp_exploratory import validate_source

ROOT = Path(__file__).resolve().parents[2]


def bindings():
    return recovery.bindings() | {str(p.relative_to(ROOT)).replace('\\', '/'): sha(p) for p in
                                  (Path(__file__), ROOT/'node-b/tools/supervise_resp_checked_b.py')}


class CheckedLink(recovery.RecoveryLink):
    def call(self, name, *args, timeout=5):
        # 复用经过测试的连接/读取实现，但新卡完全去掉复位权限和窗口前go。
        require(name != 'JLINKARM_Reset', 'CHECKED_RESET_DENIED')
        if name == 'JLINKARM_ExecCommand':
            require(args[0] != b'SetResetType = 0', 'CHECKED_RESET_POLICY_DENIED')
        if name == 'JLINKARM_Go':
            require(self.counts['go_requests'] < 1, 'CHECKED_GO_BUDGET')
        return super().call(name, *args, timeout=timeout)


def running_precheck(link, reference, out):
    folder = out/'running-precheck'; folder.mkdir()
    link.open(); seen = identity(link); check_identity(seen)
    require(seen['uid_hex'] == reference['uid_hex'] and seen['optcr'] == reference['optcr'], 'CHECKED_BOARD_BINDING')
    state = link.u32(0xe000edf0)
    write_json(folder/'initial-state-private.json', {'DHCSR': state})
    require(not state & (HALT | LOCKUP), 'CHECKED_INITIAL_NOT_RUNNING')
    observations = [runtime.snapshot(link, folder, 'attach-entry')]
    # Flash存在、PC采样、向量表、有效诊断及计数推进必须共同成立，不以单一条件放行。
    require(hashlib.sha256(link.read(0x08000000, 1048576)).hexdigest() == runtime.FLASH_SHA, 'CHECKED_FLASH_DRIFT')
    require(hashlib.sha256(link.read(0x1fffc000, 16)).hexdigest() == runtime.OPTIONS_SHA, 'CHECKED_OPTIONS_DRIFT')
    time.sleep(.5); observations.append(runtime.snapshot(link, folder, 'after-flash'))
    gate = runtime.capture_gate(observations)
    write_json(folder/'gate-private.json', gate)
    require(gate['status'] == 'READY_FOR_NEW_CAPTURE_CARD', 'CHECKED_RUNNING_GATE_FAILED')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('dll', 'card', 'manifest', 'out'):
        parser.add_argument('--'+name, required=True, type=Path)
    parser.add_argument('--card-sha256', required=True)
    args = parser.parse_args()
    require(args.out.resolve().is_relative_to(PRIVATE.resolve()) and not args.out.exists(), 'CHECKED_PRIVATE_EXCLUSIVE_OUTPUT')
    manifest = json.loads(args.manifest.read_text('utf-8'))
    require(manifest['enabled'] is True and manifest['owner_capture_authorized'] is True, 'CHECKED_CAPTURE_NOT_AUTHORIZED')
    require(sha(args.card) == args.card_sha256 == manifest['card_sha256'], 'CHECKED_CARD_SHA')
    require(bindings() == manifest['tools_sha256'], 'CHECKED_TOOL_DRIFT')
    require(args.out.resolve() == Path(manifest['out']).resolve(), 'CHECKED_OUTPUT_BINDING')
    require(args.dll.resolve() == Path(manifest['dll']).resolve() and sha(args.dll) == manifest['dll_sha256'], 'CHECKED_DLL_BINDING')
    require(sha(Path(manifest['owner_approval_record'])) == manifest['owner_approval_sha256'], 'CHECKED_APPROVAL_BINDING')
    profile_path = Path(manifest['profile']); source_path = Path(manifest['source_record'])
    require(sha(profile_path) == manifest['profile_sha256'] and sha(source_path) == manifest['source_record_sha256'], 'CHECKED_PROFILE_SOURCE_DRIFT')
    profile = json.loads(profile_path.read_text('utf-8')); capture.validate(profile)
    validate_source(json.loads(source_path.read_text('utf-8')), 'E1', ready=True)
    reference = json.loads(Path(profile['identity_reference']).read_text('utf-8'))
    args.out.mkdir()
    receipt = {'status': 'RESP_CAPTURE_STARTED', 'process_exit_code': 1, 'tail_halt_confirmed': False,
               'resume_confirmed': False, 'target_end_state': 'UNKNOWN', 'board_open_attempted': False,
               'profile_sha256': sha(profile_path), 'source_record_sha256': sha(source_path),
               'card_sha256': args.card_sha256, 'tools_sha256': capture.bindings(),
               'checked_tools_sha256': bindings(), 'stage': 'E1', 'source_type': 'RESP_EXPLORATORY'}
    link = None
    try:
        link = CheckedLink(args.dll.resolve(), args.out); receipt['board_open_attempted'] = True
        running_precheck(link, reference, args.out)
        receipt['running_precheck'] = 'VTOR_PC_BIO_ADVANCE_CONFIRMED_SAME_CONNECTION'
        capture.collect(link, profile, args.out, receipt)
    except BaseException as exc:
        receipt.update(status='RESP_CAPTURE_STOP', error=type(exc).__name__+': '+str(exc))
    finally:
        if link:
            receipt.update(link.counts)
            try:
                link.close()
            except BaseException as exc:
                receipt.update(status='RESP_CAPTURE_STOP', close_error=type(exc).__name__+': '+str(exc))
    if receipt['status'] == 'RESP_CAPTURE_FILES_SAVED':
        try:
            receipt['export'] = capture.export(args.out)
            receipt.update(stable_raw_sha256=sha(args.out/'stable-raw-private.csv'),
                           diagnostics_sha256=sha(args.out/'diagnostics-private.jsonl'), process_exit_code=0)
        except BaseException as exc:
            receipt.update(status='RESP_EXPORT_FAILED', error=type(exc).__name__+': '+str(exc), process_exit_code=2)
    write_json(args.out/'receipt-private.json', receipt)
    print(json.dumps({k: receipt[k] for k in ('status', 'process_exit_code', 'target_end_state')}))
    return receipt['process_exit_code']


if __name__ == '__main__':
    sys.exit(main())
