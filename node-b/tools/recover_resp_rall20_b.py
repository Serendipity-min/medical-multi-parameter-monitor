"""独立恢复窗口：一次正常复位核实Flash入口后采45秒；不修改已执行入口或固件。"""
import argparse
import hashlib
import json
from pathlib import Path
import sys
import time

import resp_rall20_b as capture
import recover_resp_runtime_b as connection
import runtime_state_b as runtime
from readback_b import PRIVATE, HALT, LOCKUP, RESET, require, sha, write_json, identity, check_identity

ROOT = Path(__file__).resolve().parents[2]


def bindings():
    # 原45秒入口及分析依赖继续逐项冻结，新增恢复权限只绑定本文件与独立监督。
    return capture.bindings() | {p.relative_to(ROOT).as_posix(): sha(p) for p in
        (Path(__file__), ROOT/'node-b/tools/supervise_recover_resp_rall20_b.py')}


class RecoveryRallLink(capture.ValidityLink):
    def __init__(self, dll, out):
        self.reset_phase = False
        self.alias_phase = False
        super().__init__(dll, out)

    def call(self, name, *args, timeout=5):
        if name == 'JLINKARM_Reset' or (name == 'JLINKARM_ExecCommand' and args[0] == b'SetResetType = 0'):
            # 只有身份/整片核验后的复位阶段才能绕过原入口的reset=0门；底层仍计数≤1。
            require(self.reset_phase, 'RALL_RECOVERY_RESET_OUTSIDE_APPROVED_PHASE')
            return connection.RecoveryLink.call(self, name, *args, timeout=timeout)
        if name == 'JLINKARM_ReadMemEx' and args[0] == 0:
            require(self.alias_phase and args[1] == 64, 'RALL_RECOVERY_ALIAS_SCOPE')
            return connection.RecoveryLink.call(self, name, *args, timeout=timeout)
        return super().call(name, *args, timeout=timeout)


def restore(link, binding, out):
    folder = out/'precheck'; folder.mkdir()
    link.open(); seen = identity(link); check_identity(seen)
    reference = json.loads(Path(binding['identity_reference']).read_text('utf-8'))
    require(seen['uid_hex'] == reference['uid_hex'] and seen['optcr'] == reference['optcr'], 'RALL_RECOVERY_BOARD_BINDING')
    write_json(folder/'identity-private.json', seen)
    flash = link.read(0x08000000, 1048576); options = link.read(0x1fffc000, 16)
    require(hashlib.sha256(flash).hexdigest() == binding['flash_sha256']
            and hashlib.sha256(options).hexdigest() == binding['options_sha256'], 'RALL_RECOVERY_IMAGE_DRIFT')
    write_json(folder/'image-hashes.json', {'flash_sha256': hashlib.sha256(flash).hexdigest(),
                                          'options_sha256': hashlib.sha256(options).hexdigest()})
    write_json(folder/'initial-state-private.json', {'DHCSR': link.u32(0xe000edf0), 'VTOR': link.u32(0xe000ed08)})
    # 不依赖前一次ROM/Flash状态；本卡授权的一次正常复位后只接受真实Flash向量与栈。
    link.reset_phase = True
    try:
        link.policy('SetResetType = 0')
        require(link.call('JLINKARM_Reset', timeout=5) == 0, 'RALL_RECOVERY_RESET_FAILED')
    finally:
        link.reset_phase = False
    require(link.u32(0xe000edf0) & HALT, 'RALL_RECOVERY_RESET_NOT_HALTED')
    core = runtime.core_if_halted(link); write_json(folder/'reset-core-private.json', core)
    link.alias_phase = True
    try:
        alias = link.read(0, 64)
    finally:
        link.alias_phase = False
    connection.verify_reset_entry(core.get('registers', {}), flash[:64], alias)
    link.call('JLINKARM_Go'); time.sleep(3)
    # 先检查应用向量和运行状态，再解码RAM；避免再次以ABI错误遮蔽运行环境未就绪。
    observations = []
    for index in (0, 1):
        if index:
            time.sleep(.5)
        state = link.u32(0xe000edf0); vtor = link.u32(0xe000ed08)
        require(not state & (HALT | LOCKUP | RESET) and vtor == 0x08000000, 'RALL_RECOVERY_APPLICATION_NOT_RUNNING')
        observation = capture.ready_snapshot(link, folder, index)
        capture.check_input(observation['bio']); observations.append(observation)
    gate = runtime.capture_gate(observations); write_json(folder/'gate-private.json', gate)
    require(gate['status'] == 'READY_FOR_NEW_CAPTURE_CARD', 'RALL_RECOVERY_RUNNING_GATE')


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
    profile = json.loads(profile_path.read_text('utf-8')); capture.validate_profile(profile)
    source = json.loads(source_path.read_text('utf-8')); capture.validate_source(source, ready=True)
    require(profile.get('recovery_scope') == source.get('recovery_scope') == 'ONE_NORMAL_RESET_BEFORE_NEW_45S', 'RALL_RECOVERY_SCOPE')
    binding = json.loads(Path(profile['frozen_ABI_binding_profile']).read_text('utf-8'))
    args.out.mkdir(); link = None
    receipt = {'status': 'RESP_CAPTURE_STARTED', 'process_exit_code': 1, 'tail_halt_confirmed': False,
               'resume_confirmed': False, 'target_end_state': 'UNKNOWN', 'board_open_attempted': False,
               'stage': 'RESP_RA_LL20_RECOVERY_SINGLE_WINDOW', 'source_type': 'RESP_EXPLORATORY', 'duration_s': 45,
               'profile_sha256': sha(profile_path), 'source_record_sha256': sha(source_path),
               'card_sha256': args.card_sha256, 'tools_sha256': bindings()}
    try:
        link = RecoveryRallLink(args.dll.resolve(), args.out); receipt['board_open_attempted'] = True
        restore(link, binding, args.out); capture.collect(link, binding, args.out, receipt)
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
