"""B5 G2-RO：C24104新鲜双读，单会话、零目标写入；监督器是唯一执行入口。"""
import argparse
import ctypes as C
import hashlib
import json
from pathlib import Path
import struct
import sys
import time
import zlib

import b4_recovery as recovery
import c_b4_closeout_readonly as old
import readback_b as raw

ROOT = Path(__file__).resolve().parents[2]
SCOPE = 'B5_G2RO_C24104_DOUBLE_BACKUP_NO_TARGET_ACTION'
DLL = old.DLL
CURRENT_SHA = 'b460d917e1d454fdb0882d1f837d91c606363179b817a3896a1df6897b2dcb98'
OPTIONS_SHA = '52d5979da03bd7be45e385920ec7d5901793bab3f6bc1daa0c1c1997f9e91687'
READS = {address: set(sizes) for address, sizes in old.READS.items()}
SYSTEM, REGIONS = old.SYSTEM, old.REGIONS
COMMANDS = tuple(old.runtime.COMMANDS) + ('SetRestartOnClose = 1',)
CALLS = old.runtime.CALLS - {'JLINKARM_GetRegisterList', 'JLINKARM_GetRegisterName', 'JLINKARM_ReadReg'}


def require(ok, reason):
    if not ok: raise ValueError(reason)


def digest(blob): return hashlib.sha256(blob).hexdigest()


def bindings():
    names = ('b5_g2ro.py', 'b5_g2ro_supervisor.py', 'c_b4_closeout_readonly.py',
             'readback_b.py', 'runtime_state_b.py', 'live_state_b.py', 'resp_exploratory.py', 'b4_recovery.py')
    return {n: digest((ROOT/'node-b/tools'/n).read_bytes()) for n in names}


def plan():
    return {'scope': SCOPE, 'enabled': False, 'owner_approved': False, 'tools_sha256': bindings(),
            'DLL_sha256': raw.DLL_SHA, 'expected_full_sha256': CURRENT_SHA,
            'expected_options_sha256': OPTIONS_SHA, 'session_timeout_s': 180, 'probe_sessions': 1,
            'flash_read_bytes': 1048576, 'flash_read_count': 2, 'options_read_bytes': 16, 'options_read_count': 2,
            'explicit_reset_halt_go_and_target_writes': 0, 'retries': 0,
            'policy_before_Device': list(old.raw.POLICY) + ['SetSkipDebugDeInit = 1'],
            'SetRestartOnClose_0_native_calls_max': 6,
            'SetRestartOnClose_1_native_calls_max': 1,
            'previous_value_policy_confirmation_is_not_a_retry': True,
            'close_resume_only_after_verified_running_flash': True,
            'PC_MSP': 'NOT_OBSERVED_RUNNING_NONINTRUSIVE_DWT_PCSR_SAMPLES_ONLY'}


def private_read(path): return recovery.read(Path(path), False)


def validate_authorization(auth, out, now=None):
    require(auth.get('enabled') is True and auth.get('owner_approved') is True and auth.get('scope') == SCOPE,
            'G2RO_OWNER_AUTH_REQUIRED')
    require(auth.get('tools_sha256') == bindings() and auth.get('DLL_sha256') == raw.DLL_SHA,
            'G2RO_TOOL_OR_DLL_DRIFT')
    require((time.time() if now is None else now) < auth.get('expires_unix', 0), 'G2RO_EXPIRED')
    require(auth.get('session_timeout_s') == 180 and auth.get('probe_sessions') == 1,
            'G2RO_SESSION_LIMIT')
    require(auth.get('explicit_reset_halt_go_and_target_writes') == 0 and auth.get('retries') == 0,
            'G2RO_ACTION_LIMIT')
    require(Path(auth.get('output', '')).resolve() == Path(out).resolve(), 'G2RO_OUTPUT_BINDING')
    site = json.loads(private_read(auth['site_record']))
    require(digest(private_read(auth['site_record'])) == auth.get('site_record_sha256'), 'G2RO_SITE_BINDING')
    required = ('HW0_completed', 'cold_transfer_completed', 'no_hot_transfer', 'C_power_ready',
                'C_USB_unchanged_for_session', 'BOOT_and_RESET_untouched', 'readback_only_no_power_change')
    require(site.get('JLink_target') == 'C' and all(site.get(k) is True for k in required),
            'G2RO_SITE_NOT_READY')
    require(bool(site.get('cold_transfer_authorization_id')), 'G2RO_TRANSFER_AUTH_REQUIRED')
    reference = {}
    for key in ('identity_reference', 'flash_reference', 'options_reference'):
        blob = private_read(auth[key]); require(digest(blob) == auth.get(key+'_sha256'), 'G2RO_REFERENCE_BINDING')
        reference[key] = blob
    full, options = reference['flash_reference'], reference['options_reference']
    require(len(full) == 1048576 and digest(full) == CURRENT_SHA, 'G2RO_C24104_REFERENCE')
    require(len(options) == 16 and digest(options) == OPTIONS_SHA, 'G2RO_OPTIONS_REFERENCE')
    ident = json.loads(reference['identity_reference']); recovery.identity_check(ident)
    require(auth.get('expected_full_sha256') == CURRENT_SHA and auth.get('expected_options_sha256') == OPTIONS_SHA,
            'G2RO_EXPECTED_IDENTITY')
    recovery.protected(Path(out).parent, False)
    return ident, full, options


class ReadLink(old.CReadLink):
    def __init__(self, out):
        super().__init__(out)
        self.install_log_filters()

    def install_log_filters(self):
        # SDK文本可能带设备细节；日志留指纹/长度和真实API返回，不记录UID或内存内容。
        callback = C.CFUNCTYPE(None, C.c_char_p)
        def logged(data):
            if data:
                self.log.write((json.dumps({'sdk_text_sha256': digest(data), 'bytes': len(data)})+'\n').encode())
                self.log.flush()
        def failed(data):
            logged(data); self.error = True
        self.logger, self.error_callback = callback(logged), callback(failed)

    def call(self, name, *args, timeout=5):
        require(name in CALLS, 'G2RO_SDK_FUNCTION_DENIED')
        require(self.sdk_calls < 300, 'G2RO_SDK_BUDGET')
        if name == 'JLINKARM_ExecCommand':
            command = args[0].decode('ascii')
            require(command in COMMANDS, 'G2RO_POLICY_DENIED')
            if command == 'SetRestartOnClose = 1':
                require(self.verified_running_flash, 'G2RO_CLOSE_NOT_VERIFIED')
            if command in ('SetRestartOnClose 0', 'SetRestartOnClose = 1'):
                counts = getattr(self, 'policy_counts', {})
                limit = 6 if command == 'SetRestartOnClose 0' else 1
                require(counts.get(command, 0) < limit, 'G2RO_CLOSE_POLICY_LIMIT')
                counts[command] = counts.get(command, 0)+1
                self.policy_counts = counts
        if name == 'JLINKARM_ReadMemEx':
            address, size = args[:2]
            require(size in READS.get(address, set()) and args[3] == 0, 'G2RO_ADDRESS_DENIED')
            if size == 1048576 or address == 0x1fffc000:
                key = (address, size)
                require(self.counts.get(key, 0) < 2, 'G2RO_DOUBLE_READ_LIMIT')
                self.counts[key] = self.counts.get(key, 0) + 1
        self.sdk_calls += 1
        result = raw.Link.call(self, name, *args, timeout=timeout)
        self.io.write(json.dumps({'operation': name, 'native_return_int': result if isinstance(result, int) else None,
                                  'native_return_type': type(result).__name__})+'\n'); self.io.flush()
        return result

    def policy(self, command):
        output = C.create_string_buffer(2048)
        result = self.call('JLINKARM_ExecCommand', command.encode('ascii'), output, len(output))
        self.io.write(json.dumps({'policy': command, 'native_return': result,
                                  'output_bytes': len(output.value), 'output_sha256': digest(output.value)})+'\n')
        self.io.flush()
        if command == 'SetRestartOnClose 0' and result == 1 and not output.value:
            result = self.call('JLINKARM_ExecCommand', command.encode('ascii'), output, len(output))
        require(result == 0 and not output.value, 'G2RO_POLICY_NOT_ACCEPTED')

    def read(self, address, size):
        require(size in READS.get(address, set()), 'G2RO_ADDRESS_DENIED')
        blob = (C.c_uint8 * size)()
        n = self.call('JLINKARM_ReadMemEx', address, size, blob, 0, timeout=45 if size == 1048576 else 5)
        self.io.write(json.dumps({'address': hex(address), 'requested': size, 'returned': n})+'\n'); self.io.flush()
        require(n == size, 'G2RO_PARTIAL_READ')
        return bytes(blob)


def config_record(sector):
    record = sector[:336]
    require(len(record) == 336, 'G2RO_CONFIG_SIZE')
    magic, version, header, size, generation, crc, committed = struct.unpack_from('<IHHIIII', record)
    crc_ok = zlib.crc32(record[:16]+record[24:]) == crc
    valid = (magic == 0x32433348 and version == 1 and header == 24 and size == 312 and
             generation != 0 and committed == 0x54494D43 and crc_ok)
    payload = record[24:]
    return {'header_committed_CRC_valid': valid, 'CRC_matches': crc_ok,
            'B5_identity_matches': payload[171:204].split(b'\0', 1)[0] == b'b5-gateway' and
                                   payload[269:310].split(b'\0', 1)[0] == b'b5-c-isolated'}


def save(out, name, blob):
    with (out/name).open('xb') as f: f.write(blob)
    recovery.protected(out/name, False)
    require((out/name).read_bytes() == blob, 'G2RO_DISK_VERIFY')


def capture(link, out, reference):
    ident, expected_full, expected_options = reference
    link.open()
    first = raw.identity(link); recovery.identity_check(first)
    raw.write_json(out/'identity-a-private.json', first)
    require(first == ident, 'G2RO_WRONG_C_IDENTITY_OR_PROTECTION')
    raw.write_json(out/'entry-sticky-private.json', {'DHCSR': link.u32(SYSTEM['DHCSR'])})
    state = old.snapshot(link); raw.write_json(out/'entry-private.json', state); old.check_running(link, state)
    link.set_close_resume(True)
    full, options = [], []
    for index in (1, 2):
        # 每份均由独立ReadMemEx实际返回后独占落盘；不拷贝首份充第二份。
        option = link.read(0x1fffc000, 16); save(out, f'options-{index}-private.bin', option); options.append(option)
        require(option == expected_options, 'G2RO_OPTIONS_DRIFT')
        image = link.read(0x08000000, 1048576); save(out, f'flash-{index}-private.bin', image); full.append(image)
        require(image == expected_full, 'G2RO_CURRENT_C24104_FLASH_DRIFT')
        state = old.snapshot(link); raw.write_json(out/f'after-read-{index}-private.json', state); old.check_running(link, state)
    last = raw.identity(link); recovery.identity_check(last)
    raw.write_json(out/'identity-b-private.json', last)
    require(first == last == ident, 'G2RO_IDENTITY_OR_PROTECTION_DRIFT')
    require(full[0] == full[1] and options[0] == options[1], 'G2RO_DOUBLE_READ_MISMATCH')
    regions = {}
    for name, (a, b) in REGIONS.items():
        for index, image in enumerate(full, 1): save(out, f'{name}-{index}-private.bin', image[a:b])
        regions[name] = {'bytes': b-a, 'sha256': digest(full[0][a:b]), 'double_read_identical': True}
    config = config_record(full[0][49152:65536])
    require(config['header_committed_CRC_valid'], 'G2RO_CONFIG_RECORD_INVALID')
    require(not config['B5_identity_matches'], 'G2RO_EXISTING_CONFIG_UNEXPECTEDLY_B5')
    return {'scope': SCOPE, 'status': 'C24104_FRESH_DOUBLE_READ_PASS', 'exit_code': 0,
            'full_flash_sha256': digest(full[0]), 'options_sha256': digest(options[0]), 'regions': regions,
            'config': config, 'real_PC': 'NOT_OBSERVED_RUNNING_NO_HALT', 'real_MSP': 'NOT_OBSERVED_RUNNING_NO_HALT',
            'DWT_PCSR_is_PC_sample_only': True, 'explicit_reset_halt_go_and_target_writes': 0,
            'independent_flash_ReadMemEx_calls': 2, 'independent_options_ReadMemEx_calls': 2,
            'board_sessions': 1, 'retries': 0, 'C_install': 'NOT_RUN', 'ROM_root_cause': 'UNRESOLVED'}


def worker(auth, authorization, out):
    reference = validate_authorization(auth, out)
    marker = json.loads(private_read(Path(authorization).with_suffix('.used')))
    require(marker.get('authorization_sha256') == digest(private_read(authorization)), 'G2RO_SUPERVISOR_MARKER')
    out.mkdir(exist_ok=False); recovery.protected(out, False)
    link = None; result = {'scope': SCOPE, 'status': 'STOP', 'exit_code': 1,
                          'explicit_reset_halt_go_and_target_writes': 0}
    try:
        link = ReadLink(out)
        result = capture(link, out, reference)
    except BaseException as error:
        result.update(status='STOP', exit_code=1, error_type=type(error).__name__)
        # SDK原生日志只保留EFS；公开错误仅静态类型，不打印异常正文/UID/配置。
        reason = str(error)
        raw.write_json(out/'failure-private.json', {'error_type': type(error).__name__,
            'reason': reason if reason.replace('_', '').isalnum() and reason.isupper() else 'ERROR_TEXT_SUPPRESSED',
            'error_text_sha256': digest(reason.encode())})
    finally:
        if link:
            try:
                if not link.verified_running_flash and link.close_resume_enabled: link.set_close_resume(False)
            except BaseException as error: result.update(exit_code=1, close_policy_error_type=type(error).__name__)
            finally:
                try: link.close()
                except BaseException as error: result.update(exit_code=1, close_error_type=type(error).__name__)
            result.update(sdk_calls=link.sdk_calls, close_resume_policy=link.close_resume_enabled,
                          last_verified_running_Flash=link.verified_running_flash,
                          close_policy_counts=getattr(link, 'policy_counts', {}),
                          SDK_close_may_resume_verified_running_Flash=True)
        raw.write_json(out/'receipt-private.json', result)
        for path in out.iterdir():
            if path.is_file(): recovery.protected(path, False)
    print(json.dumps({k: result[k] for k in ('scope', 'status', 'exit_code')}))
    return result['exit_code']


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--plan', action='store_true'); parser.add_argument('--worker', action='store_true')
    parser.add_argument('--authorization', type=Path); parser.add_argument('--out', type=Path)
    args = parser.parse_args()
    if args.plan: print(json.dumps(plan(), indent=2)); return 0
    try:
        require(args.worker and args.authorization and args.out, 'G2RO_USE_INDEPENDENT_SUPERVISOR')
        auth = json.loads(private_read(args.authorization))
        return worker(auth, args.authorization, args.out)
    except BaseException as error:
        print(json.dumps({'status': 'STOP_BEFORE_SDK', 'error_type': type(error).__name__, 'exit_code': 1})); return 1


if __name__ == '__main__': raise SystemExit(main())
