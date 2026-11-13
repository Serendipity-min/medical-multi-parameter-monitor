"""PREC-001 P0单次原态取证；不复位/暂停/续跑，运行PCSR与已暂停真实PC分别留证。"""
import argparse
import ctypes as C
import hashlib
import json
from pathlib import Path
import stat
import sys
import time

import runtime_state_b as runtime
from readback_b import Link, HALT, LOCKUP, identity, check_identity, require, sha, write_json
from resp_exploratory import decode

ROOT = Path(__file__).resolve().parents[2]
PRIVATE = Path('E:/medical-monitor-node-b-precan-private/20261023')
SCOPE = 'PREC_P0_ONE_ATTACH_STATE_ONLY_10S_NO_RESET_HALT_GO'
READS = runtime.READS | {0x20000044: 4, 0x2000013c: 4}
LIMITS = {a: 1 for a in READS}
LIMITS.update({a: 3 for a in runtime.SYSTEM.values()})
LIMITS.update({0xe000edf0: 8, 0xe000101c: 15, 0x20001ae4: 3, 0x2000018c: 3,
               0x200001bc: 3, 0x20000044: 3, 0x2000013c: 3})
SDK_LIMIT, SESSION_LIMIT = 700, 180


def bindings():
    # 不修改旧工具。SDK包装及本次入口/监督/测试分别冻结，避免重用旧两次连接权限。
    paths = ['node-b/tools/precan_cpu_state_b.py', 'node-b/tools/supervise_precan_cpu_state_b.py',
             'node-b/tests/test_precan_cpu_state_b.py']
    return runtime.bindings() | {name: sha(ROOT/name) for name in paths}


def encrypted(path):
    return bool(path.stat().st_file_attributes & stat.FILE_ATTRIBUTE_ENCRYPTED)


class StateLink(runtime.RuntimeLink):
    def __init__(self, dll, out):
        self.read_counts = {}; self.function_counts = {}
        super().__init__(dll, out)
        self.journal = (out/'sdk-call-journal-private.jsonl').open('x', encoding='utf-8', newline='\n')

    def call(self, name, *args, timeout=5):
        require(name in runtime.CALLS, 'PREC_SDK_FUNCTION_DENIED')
        require(self.sdk_calls < SDK_LIMIT, 'PREC_SDK_BUDGET')
        if name == 'JLINKARM_ExecCommand':
            require(args[0].decode('ascii') in runtime.COMMANDS, 'PREC_POLICY_DENIED')
        if name == 'JLINKARM_ReadMemEx':
            address, size = args[:2]
            require(READS.get(address) == size and args[3] == 0, 'PREC_READ_SCOPE')
            count = self.read_counts.get(address, 0)
            require(count < LIMITS[address], 'PREC_READ_BUDGET')
            self.read_counts[address] = count+1
        limits = {'JLINKARM_OpenEx': 1, 'JLINKARM_Connect': 1, 'JLINKARM_GetRegisterList': 1,
                  'JLINKARM_GetRegisterName': 256, 'JLINKARM_ReadReg': 21}
        if name in limits:
            count = self.function_counts.get(name, 0)
            require(count < limits[name], 'PREC_FUNCTION_BUDGET')
            self.function_counts[name] = count+1
        if name in ('JLINKARM_GetRegisterList', 'JLINKARM_GetRegisterName', 'JLINKARM_ReadReg'):
            require(self.register_reads_allowed, 'PREC_CORE_READ_REQUIRES_ALREADY_HALTED')
        # 发出前计数且即时记录，SDK内部行为与本层显式命令严格区分，不能推断无任何硬件复位。
        self.sdk_calls += 1
        event = {'index': self.sdk_calls, 'operation': name, 'host_monotonic': time.monotonic(), 'phase': 'BEFORE_CALL'}
        if name == 'JLINKARM_ExecCommand': event['command'] = args[0].decode('ascii')
        if name == 'JLINKARM_ReadMemEx': event.update(address=hex(args[0]), bytes=args[1])
        self.journal.write(json.dumps(event)+'\n'); self.journal.flush()
        result = Link.call(self, name, *args, timeout=timeout)
        event.update(phase='AFTER_CALL', host_monotonic=time.monotonic(), result=result if isinstance(result, (int, type(None))) else 'NON_SCALAR')
        self.journal.write(json.dumps(event)+'\n'); self.journal.flush()
        return result

    def read(self, address, size):
        # 精确地址/长度在call再检查；不继承旧RuntimeLink更宽的取证次数。
        require(READS.get(address) == size, 'PREC_READ_SCOPE')
        blob = (C.c_uint8*size)()
        result = self.call('JLINKARM_ReadMemEx', address, size, blob, 0,
                           timeout=45 if size == 1048576 else (15 if size == 131072 else 5))
        self.io.write(json.dumps({'address': hex(address), 'bytes': size, 'returned': result,
                                  'u32': int.from_bytes(blob, 'little') if size == 4 else None})+'\n'); self.io.flush()
        require(result == size, 'PREC_PARTIAL_READ')
        return bytes(blob)

    def close(self):
        # 失败路径同样只关闭一次，不补go/reset；关闭后状态由后续独立卡取证。
        try:
            super().close()
        finally:
            self.journal.close()


def snapshot(link, folder, label):
    started = time.monotonic()
    system = {key: link.u32(address) for key, address in runtime.SYSTEM.items()}
    pcs = [system['DWT_PCSR']]
    for _ in range(4):
        time.sleep(.02); pcs.append(link.u32(0xe000101c))
    clocks = {'application_ms': link.u32(0x20000044), 'HMI_10ms_ticks': link.u32(0x2000013c)}
    blobs = [link.read(a, n) for a, n in ((0x20001ae4, 120), (0x2000018c, 48), (0x200001bc, 12))]
    for suffix, blob in zip(('diag', 'stats', 'rreg-cache'), blobs):
        with (folder/f'{label}-{suffix}.bin').open('xb') as stream: stream.write(blob)
    try:
        bio = decode(*blobs); error = None
    except RuntimeError as exc:
        bio = None; error = str(exc)
    result = {'label': label, 'host_start_s': started, 'host_end_s': time.monotonic(), 'system': system,
              'clocks': clocks, 'pc_samples': pcs, 'pc_regions': [runtime.pc_region(x) for x in pcs],
              'bio': bio, 'bio_decode_error': error, 'boot_latch': 'NOT_OBSERVED_GPIO_IS_CURRENT_LEVEL',
              'reset_flags': 'STICKY_NOT_CLEARED_NOT_A_RESET_TIMESTAMP',
              'DHCSR_note': 'RESET_ST_READ_TO_CLEAR_AND_SDK_MAY_HAVE_READ_FIRST'}
    write_json(folder/f'{label}-snapshot-private.json', result)
    return result


def runtime_assessment(observations):
    reasons = []
    for d in observations:
        if d['system']['VTOR'] != 0x08000000: reasons.append('VTOR_NOT_APPLICATION')
        if d['system']['DHCSR'] & (HALT | LOCKUP): reasons.append('HALTED_OR_LOCKUP')
        if 'BIO_V2_FLASH' not in d['pc_regions']: reasons.append('NO_APPLICATION_PCSR_EVIDENCE')
        if d['system']['CFSR'] or d['system']['HFSR']: reasons.append('FAULT_PRESENT')
        if d['bio'] is None: reasons.append('BIO_ABI_NOT_READY')
    if all(d['bio'] for d in observations):
        for before, after in zip(observations, observations[1:]):
            if after['bio']['samples'] <= before['bio']['samples']: reasons.append('BIO_NOT_ADVANCING')
            if after['bio']['adc']['captured'] <= before['bio']['adc']['captured']: reasons.append('ADC_NOT_ADVANCING')
    return {'application_observed_running': not reasons, 'reasons': sorted(set(reasons)),
            'root_cause': 'CPU_ROOT_CAUSE_UNRESOLVED', 'P0_closeout_pass': False}


def authorize(args):
    m = json.loads(args.manifest.read_text('utf-8'))
    require(m.get('enabled') is True and m.get('owner_state_authorized') is True, 'PREC_NOT_AUTHORIZED')
    require(m.get('scope') == SCOPE and m.get('tools_sha256') == bindings(), 'PREC_SCOPE_TOOLS')
    require(sha(args.card) == args.card_sha256 == m.get('card_sha256'), 'PREC_CARD_SHA')
    require(args.out.resolve() == Path(m['out']).resolve() and args.out.resolve().is_relative_to(PRIVATE.resolve())
            and not args.out.exists(), 'PREC_PRIVATE_EXCLUSIVE_OUTPUT')
    require(args.dll.resolve() == Path(m['dll']).resolve() and sha(args.dll) == m['dll_sha256'], 'PREC_DLL_SHA')
    owner = Path(m['owner_authorization_record'])
    require(owner.is_file() and sha(owner) == m['owner_authorization_sha256']
            and owner.read_text('utf-8') == m['owner_authorization'] and bool(m['owner_authorization']), 'PREC_OWNER_BINDING')
    site = Path(m['site_state_record'])
    require(sha(site) == m['site_state_sha256'], 'PREC_CURRENT_SITE_BINDING')
    reference = Path(m['identity_reference'])
    require(sha(reference) == m['identity_reference_sha256'], 'PREC_IDENTITY_REFERENCE')
    require(encrypted(args.out.parent), 'PREC_EFS_REQUIRED_BEFORE_SDK')
    return m, json.loads(reference.read_text('utf-8'))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('dll', 'card', 'manifest', 'out'): parser.add_argument('--'+name, required=True, type=Path)
    parser.add_argument('--card-sha256', required=True)
    args = parser.parse_args(); m, reference = authorize(args); check_identity(reference)
    args.out.mkdir(); require(encrypted(args.out), 'PREC_OUTPUT_NOT_ENCRYPTED')
    receipt = {'scope': SCOPE, 'status': 'STATE_STARTED', 'process_exit_code': 1,
        'explicit_reset_requests': 0, 'explicit_halt_requests': 0, 'explicit_go_requests': 0,
        'explicit_target_data_write_requests': 0, 'root_cause': 'CPU_ROOT_CAUSE_UNRESOLVED',
        'card_sha256': args.card_sha256, 'tools_sha256': bindings(), 'post_close_target_state': 'UNKNOWN_NOT_RECONNECTED'}
    link = None
    try:
        link = StateLink(args.dll.resolve(), args.out); link.open()
        seen = identity(link); check_identity(seen)
        require(seen['uid_hex'] == reference['uid_hex'] and seen['optcr'] == reference['optcr'], 'PREC_BOARD_BINDING')
        write_json(args.out/'identity-private.json', seen)
        # 身份先核验，再保存首次状态；它已在连接后，不能写成介入前的真实PC/BOOT状态。
        first = snapshot(link, args.out, 'attach-entry')
        receipt['core_at_entry'] = runtime.core_if_halted(link)
        flash = link.read(0x08000000, 1048576); options = link.read(0x1fffc000, 16)
        for name, blob in (('full-flash', flash), ('options', options), ('alias-vectors', link.read(0, 64)),
                           ('rom-vectors', link.read(0x1fff0000, 64))):
            with (args.out/f'{name}-private.bin').open('xb') as stream: stream.write(blob)
        receipt.update(flash_sha256=hashlib.sha256(flash).hexdigest(), options_sha256=hashlib.sha256(options).hexdigest())
        require(receipt['flash_sha256'] == runtime.FLASH_SHA and receipt['options_sha256'] == runtime.OPTIONS_SHA, 'PREC_IMAGE_DRIFT')
        second = snapshot(link, args.out, 'after-image')
        time.sleep(10)
        third = snapshot(link, args.out, 'before-close')
        with (args.out/'ram-128k-private.bin').open('xb') as stream: stream.write(link.read(0x20000000, 131072))
        assessment = runtime_assessment([first, second, third])
        receipt.update(status='STATE_RECORDED_NOT_ROOT_CAUSE_PASS', snapshots=[first, second, third], assessment=assessment,
                       process_exit_code=0 if assessment['application_observed_running'] else 3)
    except BaseException as error:
        receipt.update(status='STATE_STOP', error=type(error).__name__+': '+str(error), process_exit_code=1)
    finally:
        if link:
            receipt.update(sdk_calls=link.sdk_calls, read_counts={hex(a): n for a, n in link.read_counts.items()},
                           function_counts=link.function_counts)
            try: link.close()
            except BaseException as error: receipt.update(status='STATE_STOP', close_error=str(error), process_exit_code=1)
    # 加密核验失败也写入真实失败回执，不能留下exit0摘要而进程实际非0。
    if not all(encrypted(p) for p in args.out.iterdir() if p.is_file()):
        receipt.update(status='STATE_STOP', error='PREC_PRIVATE_FILE_ENCRYPTION_FAILED', process_exit_code=1)
    write_json(args.out/'receipt-private.json', receipt)
    print(json.dumps({k: receipt[k] for k in ('status', 'process_exit_code', 'root_cause')}))
    return receipt['process_exit_code']


if __name__ == '__main__':
    sys.exit(main())
