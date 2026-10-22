"""独立RESP_EXPLORATORY入口；复用经核验的连接/槽重建，禁止冒用ECG profile。"""
import argparse
import hashlib
import json
from pathlib import Path
import time

from capture_b import CaptureLink, export
from boot_check_b import core
from field_profile import validate_profile
from precheck_b import EXPECTED_FLASH
from readback_b import PRIVATE, REGIONS, HALT, LOCKUP, RESET, POLICY, identity, check_identity, require, sha, write_json
from resp_exploratory import ROOT, SCHEMA, STAGES, decode, validate_source

ARM = ROOT / 'node-b/build/arm-20261022T074340122429Z'
OFFLINE = ROOT / 'node-b/acquisition/field-biov2/profile.offline.json'
ABI = ROOT / 'node-b/evidence/B-ALG-002/abi-receipt.json'
READS = {**REGIONS, 0xe000ed28: 4, 0xe000ed2c: 4, 0x20001ae4: 120,
         0x2000018c: 48, 0x200001bc: 12, 0x20001f30: 3072, 0x20000000: 131072}
CALLS = {'JLINKARM_ExecCommand', 'JLINKARM_EMU_GetNumDevices', 'JLINKARM_SelectUSB',
         'JLINKARM_OpenEx', 'JLINKARM_GetHWStatus', 'JLINKARM_TIF_Select', 'JLINKARM_SetSpeed',
         'JLINKARM_IsConnected', 'JLINKARM_Connect', 'JLINKARM_ReadMemEx',
         'JLINKARM_GetRegisterList', 'JLINKARM_GetRegisterName', 'JLINKARM_ReadReg',
         'JLINKARM_Go', 'JLINKARM_Halt'}


def bindings():
    # 同时绑定全部共享连接、解析、分析和监督代码，保持旧ECG文件原字节不变。
    names = ('capture_resp_b.py', 'resp_exploratory.py', 'analyze_resp_b.py', 'supervise_resp_b.py',
             'capture_b.py', 'readback_b.py', 'precheck_b.py', 'adc_path_b.py', 'boot_check_b.py',
             'fault_snapshot_b.py', 'field_profile.py')
    paths = [ROOT / 'node-b/tools' / n for n in names]
    paths.append(ROOT / 'node-b/acquisition/工具/stable_slot_export.py')
    return {p.relative_to(ROOT).as_posix(): sha(p) for p in paths}


def validate(profile):
    require(profile.get('schema') == SCHEMA, 'RESP_PROFILE_SCHEMA_NO_ECG_REUSE')
    require(profile.get('data_source') == 'ENGINEERING_NONHUMAN'
            and profile.get('data_class') == 'RESP_EXPLORATORY_NOT_Z_CALIBRATED', 'RESP_PROFILE_DATA_CLASS')
    offline = json.loads(OFFLINE.read_text('utf-8'))
    validate_profile(offline, ARM, json.loads(ABI.read_text('utf-8')))
    require(profile.get('offline_ABI_profile_sha256') == sha(OFFLINE), 'RESP_ABI_PROFILE_DRIFT')
    require(profile.get('tools_sha256') == bindings(), 'RESP_TOOL_DRIFT')
    require(profile.get('layout') == offline['layout'], 'RESP_ABI_LAYOUT')
    require(profile.get('flash_sha256') == EXPECTED_FLASH, 'RESP_FLASH_BINDING')
    reference = Path(profile.get('identity_reference', ''))
    require(reference.is_file() and sha(reference) == profile.get('identity_reference_sha256'), 'RESP_IDENTITY_REFERENCE')
    check_identity(json.loads(reference.read_text('utf-8')))
    require(profile.get('options_sha256') == sha(PRIVATE / 'readback-r3-02/options-read-1.bin'), 'RESP_OPTIONS_BINDING')
    stage = profile.get('stage')
    require(stage in STAGES and profile.get('duration_choices_s') == list(STAGES[stage]), 'RESP_STAGE_DURATION')
    require(profile.get('read_regions') == {hex(k): v for k, v in READS.items()}, 'RESP_READ_SCOPE')
    require(profile.get('sdk_call_limit') == 4000 and profile.get('session_timeout_s') == 240
            and profile.get('slot_block_limit') == 201, 'RESP_COMMAND_BUDGET')
    require(stage == 'E1', 'RESP_ONLY_E1_IMPLEMENTED_NO_LATER_STAGE_AUTH')
    return 'RESP_PROFILE_BOUND_NOT_AUTHORIZATION'


def prepare(path):
    reference = PRIVATE / 'readback-r3-02/identity-before-private.json'
    profile = {'schema': SCHEMA, 'data_source': 'ENGINEERING_NONHUMAN', 'stage': 'E1',
               'offline_ABI_profile_sha256': sha(OFFLINE), 'tools_sha256': bindings(),
               'layout': json.loads(OFFLINE.read_text('utf-8'))['layout'],
               'identity_reference': str(reference), 'identity_reference_sha256': sha(reference),
               'flash_sha256': EXPECTED_FLASH, 'options_sha256': sha(PRIVATE / 'readback-r3-02/options-read-1.bin'),
               'read_regions': {hex(k): v for k, v in READS.items()}, 'duration_choices_s': [10],
               'sdk_call_limit': 4000, 'slot_block_limit': 201, 'session_timeout_s': 240,
               'data_class': 'RESP_EXPLORATORY_NOT_Z_CALIBRATED', 'authorization': 'CARD_AND_READY_SOURCE_REQUIRED'}
    validate(profile);write_json(path, profile)
    return profile


class RespLink(CaptureLink):
    def __init__(self, dll, out):
        self.counts = {'sdk_calls': 0, 'halt_requests': 0, 'go_requests': 0,
                       'reset_requests': 0, 'flash_write_requests': 0}
        super().__init__(dll, out)

    def call(self, name, *args, timeout=5):
        require(name in CALLS, 'RESP_SDK_FUNCTION_DENIED')
        require(self.counts['sdk_calls'] < 4000, 'RESP_SDK_CALL_BUDGET')
        if name == 'JLINKARM_ReadMemEx':
            require(READS.get(args[0]) == args[1], 'RESP_READ_SCOPE')
            if args[1] == 3072:
                timeout = min(timeout, 5)  # 运行态槽块不能继承共享类给完整RAM的15秒超时。
        if name == 'JLINKARM_ExecCommand':
            allowed = set(POLICY) | {'Device = STM32F407ZG', 'SetSkipDebugDeInit = 1'}
            require(args[0].decode('ascii') in allowed, 'RESP_DEBUG_POLICY_DENIED')
        key, limit = ('go_requests', 2) if name == 'JLINKARM_Go' else ('halt_requests', 1)
        if name in ('JLINKARM_Go', 'JLINKARM_Halt'):
            require(self.counts[key] < limit, 'RESP_EXECUTION_BUDGET')
            self.counts[key] += 1  # 在SDK调用前记录尝试，失败不能抹掉已发出的动作。
        self.counts['sdk_calls'] += 1
        return super().call(name, *args, timeout=timeout)

    def read(self, address, size):
        require(READS.get(address) == size, 'RESP_READ_SCOPE')
        return super().read(address, size)


def snapshot(link, out, index):
    start = time.monotonic()
    blobs = [link.read(a, n) for a, n in ((0x20001ae4, 120), (0x2000018c, 48), (0x200001bc, 12))]
    end = time.monotonic()
    for label, blob in zip(('diag', 'stats', 'rreg-cache'), blobs):
        (out / f'{index:04d}-{label}.bin').write_bytes(blob)
    result = decode(*blobs)
    result.update(host_start_s=start, host_end_s=end, coherence='LIVE_NONATOMIC_OBSERVATION',
                  register_origin='INIT_RREG_CACHE_NOT_FRESH_SPI')
    return result


def collect(link, profile, out, receipt):
    link.open();seen = identity(link);check_identity(seen)
    reference = json.loads(Path(profile['identity_reference']).read_text('utf-8'))
    require(seen['uid_hex'] == reference['uid_hex'] and seen['optcr'] == reference['optcr'], 'RESP_BOARD_BINDING')
    write_json(out / 'identity-before-private.json', seen)
    state = link.u32(0xe000edf0);require(not state & LOCKUP, 'RESP_INITIAL_LOCKUP')
    require(hashlib.sha256(link.read(0x08000000, 1048576)).hexdigest() == profile['flash_sha256'], 'RESP_START_FLASH_DRIFT')
    require(hashlib.sha256(link.read(0x1fffc000, 16)).hexdigest() == profile['options_sha256'], 'RESP_START_OPTIONS_DRIFT')
    if state & HALT:
        registers = core(link);write_json(out / 'core-before-private.json', {k: hex(v) for k, v in registers.items()})
        require(0x08000000 <= registers.get('R15', 0) < 0x080062c4, 'RESP_PC_OUTSIDE_CANDIDATE')
        require(link.u32(0xe000ed28) == 0 and link.u32(0xe000ed2c) == 0, 'RESP_ACTIVE_FAULT')
        link.call('JLINKARM_Go');time.sleep(.5)
    started = time.monotonic();index = 0
    # 每个诊断点即时追加，STOP/进程超时亦保留已经取得的诊断，不等正常尾段才落盘。
    with (out / 'running-slots-private.bin').open('xb') as raw, \
            (out / 'chunks-private.jsonl').open('x', encoding='utf-8') as records, \
            (out / 'diagnostics-private.jsonl').open('x', encoding='utf-8') as diagnostics:
        while time.monotonic() - started < 10:
            require(index < 201, 'RESP_SLOT_BLOCK_BUDGET')
            target = started + index * .05
            if time.monotonic() < target:
                time.sleep(target - time.monotonic())
            require(not link.u32(0xe000edf0) & (HALT | LOCKUP | RESET), 'RESP_WINDOW_STATE_CHANGED')
            a = time.monotonic();blob = link.read(0x20001f30, 3072);b = time.monotonic()
            offset = raw.tell();raw.write(blob);raw.flush()
            records.write(json.dumps({'index': index, 'offset': offset, 'bytes': len(blob),
                                      'host_start_s': a, 'host_end_s': b, 'sha256': hashlib.sha256(blob).hexdigest()}) + '\n');records.flush()
            if index % 10 == 0:
                observed = snapshot(link, out, index)
                diagnostics.write(json.dumps(observed) + '\n');diagnostics.flush()
                # 原始诊断先落盘；异常输入不能靠继续采样或改阈值换取有效数字。
                require(not any(observed['adc'][k] for k in ('init_errors', 'spi_errors', 'bad_status', 'queue_overflow')), 'RESP_ADC_ERROR')
                require(abs(observed['resp_raw']) < 8220835 and abs(observed['ecg_raw']) < 8220835, 'RESP_LIVE_NEAR_RAIL')
                registers = bytes.fromhex(observed['registers_hex'])
                expected = {0: 0x73, 1: 1, 2: 0xe0, 3: 0xf0, 4: 0x40, 5: 0x40, 6: 0xec, 7: 0, 9: 0xea, 10: 3, 11: 0x0c}
                require(all(registers[k] & (0xfc if k == 11 else 0xff) == v for k, v in expected.items()), 'RESP_INIT_RREG_CACHE_DRIFT')
            index += 1
    receipt.update(window_elapsed_s=time.monotonic() - started, chunks=index)
    require(link.call('JLINKARM_Halt', timeout=3) == 0, 'RESP_TAIL_HALT_FAILED')
    require(link.u32(0xe000edf0) & HALT, 'RESP_TAIL_NOT_HALTED');link.stable_halt()
    ram = link.read(0x20000000, 131072)
    with (out / 'final-paused-ram-private.bin').open('xb') as stream:
        stream.write(ram)
    link.stable_halt();receipt['tail_halt_confirmed'] = True
    require(hashlib.sha256(link.read(0x08000000, 1048576)).hexdigest() == profile['flash_sha256'], 'RESP_END_FLASH_DRIFT')
    final = identity(link);check_identity(final)
    require(final['uid_hex'] == reference['uid_hex'] and final['optcr'] == reference['optcr'], 'RESP_END_IDENTITY_DRIFT')
    require(hashlib.sha256(link.read(0x1fffc000, 16)).hexdigest() == profile['options_sha256'], 'RESP_END_OPTIONS_DRIFT')
    link.stable_halt();link.call('JLINKARM_Go');time.sleep(.02)
    require(not link.u32(0xe000edf0) & (HALT | LOCKUP | RESET), 'RESP_RESUME_FAILED')
    receipt.update(status='RESP_CAPTURE_FILES_SAVED', resume_confirmed=True, target_end_state='RUNNING_BEFORE_CLOSE',
                   ram_sha256=sha(out / 'final-paused-ram-private.bin'))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--prepare', action='store_true')
    parser.add_argument('--profile', required=True, type=Path)
    for name in ('dll', 'card', 'source-record', 'out'):
        parser.add_argument('--' + name, type=Path)
    parser.add_argument('--card-sha256')
    parser.add_argument('--seconds', type=int, choices=(10,), default=10)
    args = parser.parse_args()
    require(args.profile.resolve().is_relative_to(PRIVATE.resolve()), 'RESP_PRIVATE_PROFILE_REQUIRED')
    if args.prepare:
        prepare(args.profile);print('RESP_PROFILE_PREPARED_NO_HARDWARE');return 0
    require(args.out is not None and args.out.resolve().is_relative_to(PRIVATE.resolve()), 'RESP_PRIVATE_OUTPUT_REQUIRED')
    args.out.mkdir(exist_ok=False)
    receipt = {'status': 'RESP_CAPTURE_STARTED', 'process_exit_code': 1, 'tail_halt_confirmed': False,
               'resume_confirmed': False, 'target_end_state': 'UNKNOWN', 'board_open_attempted': False}
    link = None
    try:
        require(sha(args.card) == args.card_sha256, 'RESP_CARD_SHA')
        profile = json.loads(args.profile.read_text('utf-8'));validate(profile)
        source = json.loads(args.source_record.read_text('utf-8'));validate_source(source, 'E1', ready=True)
        receipt.update(profile_sha256=sha(args.profile), source_record_sha256=sha(args.source_record),
                       card_sha256=args.card_sha256, tools_sha256=bindings(), source_type='RESP_EXPLORATORY', stage='E1')
        link = RespLink(args.dll.resolve(), args.out)
        receipt['board_open_attempted'] = True
        collect(link, profile, args.out, receipt)
    except BaseException as exc:
        receipt.update(status='RESP_CAPTURE_STOP', error=type(exc).__name__ + ': ' + str(exc))
    finally:
        if link:
            receipt.update(link.counts)
            try:
                link.close()
            except BaseException as exc:
                receipt.update(status='RESP_CAPTURE_STOP', close_error=type(exc).__name__ + ': ' + str(exc))
    if receipt['status'] == 'RESP_CAPTURE_FILES_SAVED':
        try:
            receipt['export'] = export(args.out)
            receipt['stable_raw_sha256'] = sha(args.out / 'stable-raw-private.csv')
            receipt['diagnostics_sha256'] = sha(args.out / 'diagnostics-private.jsonl')
            receipt['process_exit_code'] = 0
        except BaseException as exc:
            receipt.update(status='RESP_EXPORT_FAILED', error=type(exc).__name__ + ': ' + str(exc), process_exit_code=2)
    write_json(args.out / 'receipt-private.json', receipt)
    print(json.dumps({k: receipt[k] for k in ('status', 'process_exit_code', 'target_end_state', 'board_open_attempted')}))
    return receipt['process_exit_code']


if __name__ == '__main__':
    import sys
    sys.exit(main())
