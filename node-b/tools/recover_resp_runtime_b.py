"""仅在独立复位卡获批后：一次正常复位核对Flash入口，同一连接内有条件采10秒RESP。"""
import argparse
import ctypes as C
import hashlib
import json
from pathlib import Path
import sys
import time

import capture_resp_b as capture
import runtime_state_b as runtime
from readback_b import Link, PRIVATE, POLICY, HALT, LOCKUP, RESET, identity, check_identity, require, sha, write_json
from resp_exploratory import validate_source, decode

ROOT = Path(__file__).resolve().parents[2]
CALLS = capture.CALLS | {'JLINKARM_Reset'}
COMMANDS = set(POLICY) | {'SetSkipDebugDeInit = 1', 'Device = STM32F407ZG', 'SetResetType = 0'}
READS = runtime.READS | capture.READS


def bindings():
    # 包装层与共享采集层分别冻结；不改已经执行过的R3工具或阈值。
    return capture.bindings() | runtime.bindings() | {
        str(p.relative_to(ROOT)).replace('\\', '/'): sha(p) for p in
        (Path(__file__), ROOT/'node-b/tools/supervise_resp_recovery_b.py')}


def verify_reset_entry(registers, vectors, alias):
    """复位后必须实际停在候选入口及正确栈，不能写PC/SP或从ROM直接go。"""
    sp = int.from_bytes(vectors[:4], 'little'); pc = int.from_bytes(vectors[4:8], 'little')
    require((sp, pc) == (0x20002f30, 0x080001a1), 'RECOVERY_CANDIDATE_VECTOR_DRIFT')
    require(registers.get('R15', 0) & ~1 in (pc & ~1, 0x1a0), 'RECOVERY_RESET_PC_NOT_FLASH_ENTRY')
    require(registers.get('MSP', registers.get('R13')) == sp, 'RECOVERY_RESET_STACK_MISMATCH')
    require(alias == vectors, 'RECOVERY_ALIAS_NOT_FLASH_VECTOR')


class RecoveryLink(capture.RespLink):
    def __init__(self, dll, out):
        self.register_reads_allowed = False
        super().__init__(dll, out)

    def call(self, name, *args, timeout=5):
        require(name in CALLS, 'RECOVERY_SDK_FUNCTION_DENIED')
        require(self.counts['sdk_calls'] < 4000, 'RECOVERY_SDK_BUDGET')
        if name == 'JLINKARM_ExecCommand':
            require(args[0].decode('ascii') in COMMANDS, 'RECOVERY_COMMAND_DENIED')
        if name == 'JLINKARM_ReadMemEx':
            require(READS.get(args[0]) == args[1] and args[3] == 0, 'RECOVERY_READ_SCOPE')
        if name in ('JLINKARM_GetRegisterList', 'JLINKARM_GetRegisterName', 'JLINKARM_ReadReg'):
            require(self.register_reads_allowed, 'RECOVERY_CORE_READ_REQUIRES_HALT')
        limits = {'JLINKARM_Reset': ('reset_requests', 1), 'JLINKARM_Halt': ('halt_requests', 1),
                  'JLINKARM_Go': ('go_requests', 2)}
        if name in limits:
            key, limit = limits[name]
            require(self.counts[key] < limit, 'RECOVERY_EXECUTION_BUDGET')
            self.counts[key] += 1  # 发出前记录尝试；SDK报错也不能抹掉已发出的复位。
        self.counts['sdk_calls'] += 1
        # 直接进入冻结SDK包装层；不能再次经过RespLink计数或被其reset=0白名单拦截。
        return Link.call(self, name, *args, timeout=timeout)

    def open(self):
        # 恢复和采集在同一连接内连续完成，collect再次调用open不产生第二次连接。
        if not self.opened:
            runtime.RuntimeLink.open(self)

    def read(self, address, size):
        require(READS.get(address) == size, 'RECOVERY_READ_SCOPE')
        blob = (C.c_uint8*size)()
        count = self.call('JLINKARM_ReadMemEx', address, size, blob, 0,
                          timeout=45 if size == 1048576 else (15 if size == 131072 else 5))
        self.io.write(json.dumps({'address': hex(address), 'bytes': size, 'returned': count,
                                 'u32': int.from_bytes(blob, 'little') if size == 4 else None,
                                 'host_monotonic': time.monotonic()})+'\n'); self.io.flush()
        require(count == size, 'RECOVERY_PARTIAL_READ')
        return bytes(blob)


def recover(link, reference, out, receipt):
    preflight = out/'recovery-preflight'; preflight.mkdir(exist_ok=False)
    link.open(); seen = identity(link); check_identity(seen)
    require(seen['uid_hex'] == reference['uid_hex'] and seen['optcr'] == reference['optcr'], 'RECOVERY_BOARD_BINDING')
    state = link.u32(0xe000edf0); vtor = link.u32(0xe000ed08)
    core = runtime.core_if_halted(link)
    write_json(out/'recovery-entry-private.json', {'DHCSR': state, 'VTOR': vtor, 'core': core})
    require(state & HALT and not state & LOCKUP and vtor == 0x1fff0000, 'RECOVERY_EXPECTED_HALTED_ROM_STATE_CHANGED')
    require(runtime.pc_region(core.get('registers', {}).get('R15', 0)) == 'SYSTEM_ROM', 'RECOVERY_INITIAL_PC_NOT_ROM')
    flash = link.read(0x08000000, 1048576)
    require(hashlib.sha256(flash).hexdigest() == runtime.FLASH_SHA, 'RECOVERY_START_FLASH_DRIFT')
    require(hashlib.sha256(link.read(0x1fffc000, 16)).hexdigest() == runtime.OPTIONS_SHA, 'RECOVERY_START_OPTIONS_DRIFT')
    link.policy('SetResetType = 0')
    require(link.call('JLINKARM_Reset', timeout=5) == 0, 'RECOVERY_RESET_FAILED')
    require(link.u32(0xe000edf0) & HALT, 'RECOVERY_RESET_NOT_HALTED')
    after = runtime.core_if_halted(link)
    write_json(out/'recovery-reset-entry-private.json', after)
    verify_reset_entry(after.get('registers', {}), flash[:64], link.read(0, 64))
    link.call('JLINKARM_Go'); time.sleep(3)
    observations = []
    for index in (0, 1):
        if index:
            time.sleep(.5)
        require(not link.u32(0xe000edf0) & (HALT | LOCKUP | RESET), 'RECOVERY_POST_GO_STATE_CHANGED')
        # 前检诊断单列子目录，不能混入10秒窗口诊断的计数及离线周期估计。
        s = runtime.snapshot(link, preflight, f'recovery-ready-{index}')
        observations.append(s)
        require(s['system']['VTOR'] == 0x08000000 and not s['system']['CFSR'] and not s['system']['HFSR'], 'RECOVERY_VTOR_OR_FAULT')
        require(s['bio'] is not None, 'RECOVERY_BIO_NOT_INITIALIZED')
        require('SYSTEM_ROM' not in s['pc_regions'], 'RECOVERY_PC_RETURNED_TO_ROM')
        d = s['bio']
        require(not any(d['adc'][k] for k in ('init_errors', 'spi_errors', 'bad_status', 'queue_overflow')), 'RECOVERY_ADC_ERROR')
        registers = bytes.fromhex(d['registers_hex'])
        expected = {0: 0x73, 1: 1, 2: 0xe0, 3: 0xf0, 4: 0x40, 5: 0x40, 6: 0xec, 7: 0, 9: 0xea, 10: 3, 11: 0x0c}
        require(all(registers[k] & (0xfc if k == 11 else 255) == v for k, v in expected.items()), 'RECOVERY_INIT_CACHE_MISMATCH')
    require(observations[-1]['bio']['samples'] > observations[0]['bio']['samples']
            and observations[-1]['bio']['adc']['captured'] > observations[0]['bio']['adc']['captured'], 'RECOVERY_ADC_OR_BIO_NOT_ADVANCING')
    receipt['recovery_phase'] = 'FLASH_ENTRY_AND_INITIALIZATION_CONFIRMED_NO_CLOSE_BEFORE_CAPTURE'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('dll', 'card', 'manifest', 'out'):
        parser.add_argument('--'+name, required=True, type=Path)
    parser.add_argument('--card-sha256', required=True)
    args = parser.parse_args()
    require(args.out.resolve().is_relative_to(PRIVATE.resolve()) and not args.out.exists(), 'RECOVERY_PRIVATE_EXCLUSIVE_OUTPUT')
    manifest = json.loads(args.manifest.read_text('utf-8'))
    require(manifest['enabled'] is True and manifest['owner_reset_authorized'] is True, 'RECOVERY_RESET_NOT_AUTHORIZED')
    require(sha(args.card) == args.card_sha256 == manifest['card_sha256'], 'RECOVERY_CARD_SHA')
    require(bindings() == manifest['tools_sha256'], 'RECOVERY_TOOL_DRIFT')
    require(args.out.resolve() == Path(manifest['out']).resolve(), 'RECOVERY_OUTPUT_BINDING')
    require(args.dll.resolve() == Path(manifest['dll']).resolve() and sha(args.dll) == manifest['dll_sha256'], 'RECOVERY_DLL_BINDING')
    approval = Path(manifest['owner_approval_record'])
    require(sha(approval) == manifest['owner_approval_sha256'], 'RECOVERY_APPROVAL_BINDING')
    profile_path = Path(manifest['profile']); source_path = Path(manifest['source_record'])
    require(sha(profile_path) == manifest['profile_sha256'] and sha(source_path) == manifest['source_record_sha256'], 'RECOVERY_PROFILE_SOURCE_DRIFT')
    profile = json.loads(profile_path.read_text('utf-8')); capture.validate(profile)
    source = json.loads(source_path.read_text('utf-8')); validate_source(source, 'E1', ready=True)
    reference = json.loads(Path(profile['identity_reference']).read_text('utf-8'))
    args.out.mkdir()
    receipt = {'status': 'RESP_CAPTURE_STARTED', 'process_exit_code': 1, 'tail_halt_confirmed': False,
               'resume_confirmed': False, 'target_end_state': 'UNKNOWN', 'board_open_attempted': False,
               'profile_sha256': sha(profile_path), 'source_record_sha256': sha(source_path),
               'card_sha256': args.card_sha256, 'tools_sha256': capture.bindings(),
               'recovery_tools_sha256': bindings(), 'stage': 'E1', 'source_type': 'RESP_EXPLORATORY',
               'reset_scope': 'ONE_PRE_WINDOW_RESET_NO_RESET_DURING_10S_CAPTURE'}
    link = None
    try:
        link = RecoveryLink(args.dll.resolve(), args.out); receipt['board_open_attempted'] = True
        recover(link, reference, args.out, receipt)
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
