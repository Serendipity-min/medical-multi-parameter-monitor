"""B板启动/运行状态只读核验；两次计划连接，禁止halt/go/reset及目标数据写入。"""
import argparse
import ctypes as C
import hashlib
import json
from pathlib import Path
import re
import sys
import time

from readback_b import Link, HWStatus, PRIVATE, POLICY, REGIONS, HALT, LOCKUP, RESET
from readback_b import identity, check_identity, require, sha, write_json
from resp_exploratory import decode

ROOT = Path(__file__).resolve().parents[2]
SYSTEM = {'DHCSR': 0xe000edf0, 'ICSR': 0xe000ed04, 'VTOR': 0xe000ed08,
          'SHCSR': 0xe000ed24, 'CFSR': 0xe000ed28, 'HFSR': 0xe000ed2c,
          'DFSR': 0xe000ed30, 'DEMCR': 0xe000edfc, 'DWT_CTRL': 0xe0001000,
          'DWT_CYCCNT': 0xe0001004, 'DWT_PCSR': 0xe000101c,
          'SYSCFG_MEMRMP': 0x40013800, 'RCC_CSR': 0x40023874,
          'RCC_APB2ENR': 0x40023844, 'GPIOB_IDR': 0x40020410}
READS = {**REGIONS, **{a: 4 for a in SYSTEM.values()}, 0: 64, 0x1fff0000: 64,
         0x20000000: 131072, 0x20001ae4: 120, 0x2000018c: 48, 0x200001bc: 12}
# 主Flash向量从本次完整Flash缓冲区切片，避免同地址不同长度扩大读取白名单。
COMMANDS = tuple(POLICY) + ('SetSkipDebugDeInit = 1', 'Device = STM32F407ZG')
CALLS = {'JLINKARM_ExecCommand', 'JLINKARM_EMU_GetNumDevices', 'JLINKARM_SelectUSB',
         'JLINKARM_OpenEx', 'JLINKARM_GetHWStatus', 'JLINKARM_TIF_Select',
         'JLINKARM_SetSpeed', 'JLINKARM_IsConnected', 'JLINKARM_Connect',
         'JLINKARM_ReadMemEx', 'JLINKARM_GetRegisterList',
         'JLINKARM_GetRegisterName', 'JLINKARM_ReadReg'}
FLASH_SHA = 'f713277a50a5ec8d8a93317f412d5ab1b754e5d619918e57e9efe9dceef24cbb'
OPTIONS_SHA = '52d5979da03bd7be45e385920ec7d5901793bab3f6bc1daa0c1c1997f9e91687'


def bindings():
    # 冻结本工具及实际依赖，不修改之前已经执行的采集工具和历史profile。
    return {str(p.relative_to(ROOT)).replace('\\', '/'): sha(p) for p in
            (Path(__file__), ROOT/'node-b/tools/supervise_runtime_state_b.py',
             ROOT/'node-b/tools/readback_b.py', ROOT/'node-b/tools/resp_exploratory.py')}


def register_name(name):
    """SDK名称可能带括号别名；PC统一保存为R15，避免漏掉关键寄存器。"""
    found = re.match(r'^(R(?:1[0-5]|[0-9])|PC|SP|LR|MSP|PSP|XPSR|CONTROL|PRIMASK)\b', name.upper())
    return {'PC': 'R15', 'SP': 'R13', 'LR': 'R14'}.get(found[1], found[1]) if found else None


def pc_region(value):
    value &= ~1
    if 0x08000000 <= value < 0x080062c4:
        return 'BIO_V2_FLASH'
    if 0x1fff0000 <= value < 0x1fff7800:
        return 'SYSTEM_ROM'
    if value in (0, 0xfffffffe):
        return 'UNAVAILABLE'
    return 'OTHER'


class RuntimeLink(Link):
    def __init__(self, dll, out):
        self.sdk_calls = 0
        self.register_reads_allowed = False
        super().__init__(dll, out)

    def call(self, name, *args, timeout=5):
        require(name in CALLS, 'RUNTIME_SDK_FUNCTION_DENIED')
        require(self.sdk_calls < 700, 'RUNTIME_SDK_BUDGET')
        if name == 'JLINKARM_ExecCommand':
            require(args[0].decode('ascii') in COMMANDS, 'RUNTIME_COMMAND_DENIED')
        if name == 'JLINKARM_ReadMemEx':
            require(READS.get(args[0]) == args[1] and args[3] == 0, 'RUNTIME_READ_SCOPE')
        if name in ('JLINKARM_GetRegisterList', 'JLINKARM_GetRegisterName', 'JLINKARM_ReadReg'):
            require(self.register_reads_allowed, 'RUNTIME_CORE_READ_REQUIRES_ALREADY_HALTED')
        self.sdk_calls += 1
        return super().call(name, *args, timeout=timeout)

    def open(self):
        # 所有保护策略在Device选择之前落地；Device可能已经执行连接，不能事后补guard。
        guards = [*POLICY, 'SetSkipDebugDeInit = 1']
        for command in [*POLICY[:5], 'SetSkipDebugDeInit = 1']:
            self.policy(command)
        require(self.call('JLINKARM_EMU_GetNumDevices') == 1, 'PROBE_COUNT_NOT_ONE')
        require(self.call('JLINKARM_SelectUSB', 0) == 0, 'PROBE_SELECTION_FAILED')
        require(self.call('JLINKARM_OpenEx', self.logger, self.error_callback) is None, 'PROBE_OPEN_FAILED')
        self.opened = True
        for command in guards:
            self.policy(command)
        status = HWStatus()
        require(self.call('JLINKARM_GetHWStatus', C.byref(status)) == 0, 'PROBE_STATUS_FAILED')
        write_json(self.out/'probe-status-private.json', {'voltage_mv': status.voltage_mv})
        require(3000 <= status.voltage_mv <= 3600, 'TARGET_REFERENCE_NOT_3V3')
        require(self.call('JLINKARM_TIF_Select', 1) == 0, 'SWD_SELECTION_FAILED')
        self.call('JLINKARM_SetSpeed', 1000)
        self.policy('Device = STM32F407ZG')
        if not self.call('JLINKARM_IsConnected'):
            require(self.call('JLINKARM_Connect') >= 0, 'TARGET_ATTACH_FAILED')

    def read(self, address, size):
        require(READS.get(address) == size, 'RUNTIME_READ_SCOPE')
        blob = (C.c_uint8*size)()
        result = self.call('JLINKARM_ReadMemEx', address, size, blob, 0,
                           timeout=45 if size == 1048576 else (15 if size == 131072 else 5))
        self.io.write(json.dumps({'address': hex(address), 'bytes': size, 'returned': result,
                                 'u32': int.from_bytes(blob, 'little') if size == 4 else None})+'\n')
        self.io.flush()
        require(result == size, 'RUNTIME_PARTIAL_READ')
        return bytes(blob)


def core_if_halted(link):
    # 读取前再次核对，运行态绝不调用ReadReg；不以SDK隐式暂停换取PC。
    state = link.u32(SYSTEM['DHCSR'])
    if not state & HALT:
        return {'status': 'NOT_READ_RUNNING_USE_PCSR'}
    require(not state & LOCKUP, 'RUNTIME_LOCKUP')
    link.register_reads_allowed = True
    try:
        link.dll.JLINKARM_GetRegisterList.argtypes = [C.POINTER(C.c_uint32), C.c_uint32]
        link.dll.JLINKARM_GetRegisterName.argtypes = [C.c_uint32]
        link.dll.JLINKARM_GetRegisterName.restype = C.c_char_p
        link.dll.JLINKARM_ReadReg.argtypes = [C.c_int]
        link.dll.JLINKARM_ReadReg.restype = C.c_uint32
        ids = (C.c_uint32*256)()
        count = link.call('JLINKARM_GetRegisterList', ids, 256)
        require(0 < count <= 256, 'RUNTIME_REGISTER_LIST')
        result = {}; names = []
        for index in ids[:count]:
            literal = link.call('JLINKARM_GetRegisterName', index).decode('ascii')
            names.append(literal); name = register_name(literal)
            if name and name not in result:
                result[name] = link.call('JLINKARM_ReadReg', index)
        require(link.u32(SYSTEM['DHCSR']) & HALT, 'RUNTIME_HALT_CHANGED_DURING_CORE_READ')
        return {'status': 'READ_ALREADY_HALTED_NO_CONTROL', 'registers': result,
                'SDK_names': names, 'PC_status': 'READ' if 'R15' in result else 'SDK_DID_NOT_ENUMERATE_PC'}
    finally:
        link.register_reads_allowed = False


def snapshot(link, folder, label):
    start = time.monotonic(); regs = {k: link.u32(a) for k, a in SYSTEM.items()}
    pcs = [regs['DWT_PCSR']]
    for _ in range(4):
        time.sleep(.02); pcs.append(link.u32(SYSTEM['DWT_PCSR']))
    blobs = [link.read(a, n) for a, n in ((0x20001ae4, 120), (0x2000018c, 48), (0x200001bc, 12))]
    for suffix, blob in zip(('diag', 'stats', 'rreg-cache'), blobs):
        with (folder/f'{label}-{suffix}.bin').open('xb') as f:
            f.write(blob)
    # ABI失败仍保存系统状态和原件，诊断本身不解释为有效ADC数据。
    try:
        bio = decode(*blobs); decode_error = None
    except RuntimeError as error:
        bio = None; decode_error = str(error)
    result = {'label': label, 'host_start_s': start, 'host_end_s': time.monotonic(),
              'system': regs, 'pc_samples': pcs, 'pc_regions': [pc_region(v) for v in pcs],
              'bio': bio, 'bio_decode_error': decode_error,
              'DHCSR_after': link.u32(SYSTEM['DHCSR']), 'coherence': 'LIVE_NONATOMIC_NO_HALT'}
    write_json(folder/f'{label}-snapshot-private.json', result)
    return result


def capture_gate(snapshots):
    """只判断能否准备新采集；ROM/无PC证据/诊断不符均不能自动复位或继续。"""
    failures = []
    for s in snapshots:
        if s['system']['VTOR'] != 0x08000000:
            failures.append('VTOR_NOT_BIO_V2_FLASH')
        if s['system']['CFSR'] or s['system']['HFSR']:
            failures.append('ACTIVE_FAULT')
        if (s['system']['DHCSR'] | s['DHCSR_after']) & (HALT | LOCKUP):
            failures.append('NOT_RUNNING')
        if s['label'] != 'attach-entry' and (s['system']['DHCSR'] | s['DHCSR_after']) & RESET:
            failures.append('RESET_OBSERVED_DURING_ATTACHMENT')
        if 'SYSTEM_ROM' in s['pc_regions']:
            failures.append('PC_IN_SYSTEM_ROM')
        if 'BIO_V2_FLASH' not in s['pc_regions']:
            failures.append('NO_BIO_V2_EXECUTION_PC_EVIDENCE')
        d = s['bio']
        if d is None:
            failures.append('BIO_DIAG_ABI_NOT_READY'); continue
        if any(d['adc'][k] for k in ('init_errors', 'spi_errors', 'bad_status', 'queue_overflow')):
            failures.append('ADC_ERROR')
        registers = bytes.fromhex(d['registers_hex'])
        expected = {0: 0x73, 1: 1, 2: 0xe0, 3: 0xf0, 4: 0x40, 5: 0x40, 6: 0xec, 7: 0, 9: 0xea, 10: 3, 11: 0x0c}
        if any(registers[k] & (0xfc if k == 11 else 255) != v for k, v in expected.items()):
            failures.append('INIT_RREG_CACHE_MISMATCH')
    if all(s['bio'] for s in snapshots):
        if any(b['bio']['samples'] <= a['bio']['samples'] for a, b in zip(snapshots, snapshots[1:])):
            failures.append('BIO_SAMPLES_NOT_ADVANCING')
    return {'status': 'READY_FOR_NEW_CAPTURE_CARD' if not failures else 'HOLD_RUNTIME_STATE',
            'failures': sorted(set(failures)), 'does_not_authorize_reset_or_capture': True}


def inspect_once(dll, reference, folder):
    folder.mkdir(exist_ok=False); link = RuntimeLink(dll, folder)
    result = {'status': 'RUNTIME_STARTED', 'halt_requests': 0, 'go_requests': 0,
              'reset_requests': 0, 'target_data_write_requests': 0,
              'sdk_close_calls': 0, 'sdk_close_attempts': 0}
    try:
        link.open(); seen = identity(link); check_identity(seen)
        require(seen['uid_hex'] == reference['uid_hex'] and seen['optcr'] == reference['optcr'], 'RUNTIME_BOARD_BINDING')
        write_json(folder/'identity-before-private.json', seen)
        observations = [snapshot(link, folder, 'attach-entry')]
        result['core_at_entry'] = core_if_halted(link)
        flash = link.read(0x08000000, 1048576); options = link.read(0x1fffc000, 16)
        result.update(flash_sha256=hashlib.sha256(flash).hexdigest(), options_sha256=hashlib.sha256(options).hexdigest())
        require(result['flash_sha256'] == FLASH_SHA and result['options_sha256'] == OPTIONS_SHA, 'RUNTIME_FLASH_OPTIONS_DRIFT')
        alias = link.read(0, 64); rom = link.read(0x1fff0000, 64)
        for name, blob in (('alias-vectors', alias), ('rom-vectors', rom), ('flash-vectors', flash[:64])):
            with (folder/f'{name}-private.bin').open('xb') as f:
                f.write(blob)
        result.update(alias_equals_flash=alias == flash[:64], alias_equals_ROM=alias == rom)
        observations.append(snapshot(link, folder, 'after-flash'))
        # 活动RAM完整保存，但不以非原子快照认证稳定原码或RR。
        with (folder/'ram-128k-private.bin').open('xb') as f:
            f.write(link.read(0x20000000, 131072))
        time.sleep(.5); observations.append(snapshot(link, folder, 'before-close'))
        result.update(status='RUNTIME_READS_SAVED', snapshots=observations, capture_gate=capture_gate(observations))
    except BaseException as exc:
        result.update(status='RUNTIME_STOP', error=type(exc).__name__+': '+str(exc))
    finally:
        result['sdk_calls'] = link.sdk_calls
        was_opened = link.opened
        result['sdk_close_attempts'] = int(was_opened)
        try:
            link.close(); result['sdk_close_calls'] = int(was_opened)
        except BaseException as exc:
            result.update(status='RUNTIME_STOP', close_error=type(exc).__name__+': '+str(exc))
        result['post_close_target_state'] = 'NOT_OBSERVED_WITH_THIS_CONNECTION'
        write_json(folder/'receipt-private.json', result)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('dll', 'card', 'manifest', 'out'):
        parser.add_argument('--'+name, required=True, type=Path)
    parser.add_argument('--card-sha256', required=True)
    args = parser.parse_args()
    require(args.out.resolve().is_relative_to(PRIVATE.resolve()), 'RUNTIME_PRIVATE_OUTPUT')
    require(not args.out.exists(), 'RUNTIME_OUTPUT_EXISTS')
    manifest = json.loads(args.manifest.read_text('utf-8'))
    require(sha(args.card) == args.card_sha256 == manifest['card_sha256'], 'RUNTIME_CARD_SHA')
    require(manifest['tools_sha256'] == bindings() and manifest['enabled'] is True, 'RUNTIME_MANIFEST_BINDING')
    require(args.out.resolve() == Path(manifest['out']).resolve(), 'RUNTIME_OUTPUT_BINDING')
    require(args.dll.resolve() == Path(manifest['dll']).resolve()
            and sha(args.dll) == manifest['dll_sha256'], 'RUNTIME_DLL_BINDING')
    ref = Path(manifest['identity_reference'])
    require(sha(ref) == manifest['identity_reference_sha256'], 'RUNTIME_IDENTITY_REFERENCE')
    reference = json.loads(ref.read_text('utf-8')); check_identity(reference)
    args.out.mkdir(); all_results = []
    # 第二次是预先列明的关闭/重连观察，只有第一次IO完整且Close成功才进行，不是故障重试。
    for index in (1, 2):
        result = inspect_once(args.dll, reference, args.out/f'attachment-{index:02d}')
        all_results.append(result)
        if result['status'] != 'RUNTIME_READS_SAVED':
            break
        if index == 1:
            time.sleep(.5)
    ready = len(all_results) == 2 and all(r.get('capture_gate', {}).get('status') == 'READY_FOR_NEW_CAPTURE_CARD'
                                        and r['status'] == 'RUNTIME_READS_SAVED' for r in all_results)
    cross_attachment_reset = False
    if ready:
        before = all_results[0]['snapshots'][-1]['bio']['samples']
        after = all_results[1]['snapshots'][0]['bio']['samples']
        cross_attachment_reset = after <= before
        ready = not cross_attachment_reset
    summary = {'status': 'RUNTIME_CAPTURE_READY' if ready else 'RUNTIME_HOLD',
               'attachment_count': len(all_results), 'process_exit_code': 0 if ready else 3,
               'results': all_results, 'close_reconnect_inseparable': True,
               'samples_reset_or_not_advancing_across_close_reconnect': cross_attachment_reset,
               'halt_requests': 0, 'go_requests': 0, 'reset_requests': 0, 'target_data_write_requests': 0}
    write_json(args.out/'runtime-summary-private.json', summary)
    print(json.dumps({k: summary[k] for k in ('status', 'attachment_count', 'process_exit_code')}))
    return summary['process_exit_code']


if __name__ == '__main__':
    sys.exit(main())
