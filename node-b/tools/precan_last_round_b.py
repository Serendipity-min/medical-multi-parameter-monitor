"""负责人授权的最后一轮：双读备份、固定修正版一次烧录及有限屏重启/ROM核验。"""
import argparse
import ctypes as C
import hashlib
import json
from pathlib import Path
import stat
import subprocess
import sys
import time

import runtime_state_b as runtime
from live_state_b import LiveLink
from readback_b import Link, REGIONS, HALT, LOCKUP, RESET, identity, check_identity, require, sha, write_json
from resp_exploratory import decode

PRIVATE = Path('E:/medical-monitor-node-b-precan-private/20261023/last-round')
DLL = Path('E:/medical-monitor-node-b-field-private/field-r3/jlink-986a-portable/JLink_x64.dll')
REFERENCE = Path('E:/medical-monitor-node-b-field-private/field-r3/readback-r3-02/identity-before-private.json')
IMAGE = PRIVATE/'candidate/BIO_V2.bin'
IMAGE_SHA = 'b8e74577dae7a5a1f6caa27687193f5128f89bd70781f06a1d80b0c74d409b44'
IMAGE_BYTES = 25488
OLD_FULL_SHA = runtime.FLASH_SHA
SYSTEM = {k: runtime.SYSTEM[k] for k in ('DHCSR', 'VTOR', 'CFSR', 'HFSR', 'RCC_CSR', 'DWT_PCSR')}
FIELDS = {'application_ms': 0x20000044, 'screen_reports': 0x2000013c,
          'last_screen_report_ms': 0x20000140, 'HMI_ticks': 0x20000144}
READS = {a: {n} for a, n in REGIONS.items()}
READS[0x08000000] = {1048576, IMAGE_BYTES}
READS.update({a: {4} for a in (SYSTEM | FIELDS).values()})
READS.update({a: {n} for a, n in ((0x20000000, 131072), (0x20001aec, 120),
                               (0x20000194, 48), (0x200001c4, 12))})
POLICIES = set(runtime.COMMANDS) | {'SetRestartOnClose = 1', 'SetResetType = 0'}


def digest(b):
    return hashlib.sha256(b).hexdigest()


def payload_for(image, backup):
    # 扇区0/1之外及新BIN末尾均保留现场原件，禁止以FF重填旧配置或扩大擦除。
    require(len(image) == IMAGE_BYTES and digest(image) == IMAGE_SHA, 'NEW_IMAGE_IDENTITY')
    require(len(backup) == 1048576 and digest(backup) == OLD_FULL_SHA, 'CURRENT_IMAGE_DRIFT')
    return image + backup[len(image):]


class LastLink(LiveLink):
    def __init__(self, out, action):
        self.action = action
        self.counts = {}
        self.download_payload_sha = None
        self.download_verified = False
        super().__init__(DLL, out)

    def call(self, name, *args, timeout=5):
        allowed = set(runtime.CALLS)
        limits = {'JLINKARM_Halt': 1, 'JLINKARM_Reset': 1, 'JLINKARM_Go': 1,
                  'JLINKARM_BeginDownload': 1, 'JLINKARM_WriteMem': 1, 'JLINKARM_EndDownload': 1}
        if self.action == 'install':
            allowed.update(limits)
        require(name in allowed, 'LAST_FUNCTION_DENIED')
        require(self.sdk_calls < 15000, 'LAST_SDK_BUDGET')
        if name == 'JLINKARM_ExecCommand':
            command = args[0].decode('ascii')
            require(command in POLICIES, 'LAST_POLICY_DENIED')
            if command == 'SetRestartOnClose = 1':
                require(self.verified_running_flash, 'LAST_UNVERIFIED_CLOSE_RESUME')
        if name == 'JLINKARM_ReadMemEx':
            require(args[1] in READS.get(args[0], set()) and args[3] == 0, 'LAST_READ_SCOPE')
        if name in ('JLINKARM_GetRegisterList', 'JLINKARM_GetRegisterName', 'JLINKARM_ReadReg'):
            require(self.register_reads_allowed, 'LAST_CORE_REQUIRES_HALT')
        if name in limits:
            require(self.counts.get(name, 0) < limits[name], 'LAST_ACTION_BUDGET')
            if name in ('JLINKARM_BeginDownload', 'JLINKARM_WriteMem', 'JLINKARM_EndDownload'):
                require(self.download_payload_sha is not None, 'LAST_BACKUP_NOT_VERIFIED')
            if name == 'JLINKARM_WriteMem':
                require(args[:2] == (0x08000000, 32768), 'LAST_PROGRAM_SCOPE')
                require(digest(C.string_at(args[2], 32768)) == self.download_payload_sha, 'LAST_PROGRAM_BYTES')
            if name in ('JLINKARM_Reset', 'JLINKARM_Go'):
                require(self.download_verified, 'LAST_BOOT_REQUIRES_FULL_VERIFY')
        # 原生错误也计入已经发出的尝试，不为失败重试腾出预算。
        self.counts[name] = self.counts.get(name, 0) + 1
        self.sdk_calls += 1
        return Link.call(self, name, *args, timeout=timeout)

    def read(self, address, size):
        require(size in READS.get(address, set()), 'LAST_READ_SCOPE')
        blob = (C.c_uint8 * size)()
        n = self.call('JLINKARM_ReadMemEx', address, size, blob, 0,
                      timeout=40 if size == 1048576 else (15 if size == 131072 else 5))
        self.io.write(json.dumps({'address': hex(address), 'bytes': size, 'returned': n}) + '\n')
        self.io.flush()
        require(n == size, 'LAST_PARTIAL_READ')
        return bytes(blob)


def save(out, name, b):
    with (out/name).open('xb') as f:
        f.write(b)


def board(link, out):
    seen = identity(link)
    check_identity(seen)
    ref = json.loads(REFERENCE.read_text('utf-8'))
    require(seen['uid_hex'] == ref['uid_hex'] and seen['optcr'] == ref['optcr'], 'LAST_WRONG_BOARD')
    write_json(out/'identity-private.json', seen)
    return seen


def sample(link, out, index):
    s = {k: link.u32(a) for k, a in (SYSTEM | FIELDS).items()}
    blobs = [link.read(a, n) for a, n in ((0x20001aec, 120), (0x20000194, 48), (0x200001c4, 12))]
    for label, b in zip(('diag', 'stats', 'cache'), blobs):
        save(out, f'{index:04d}-{label}.bin', b)
    s['bio'] = decode(*blobs)
    s['host_monotonic'] = time.monotonic()
    with (out/'samples-private.jsonl').open('a', encoding='utf-8') as f:
        f.write(json.dumps(s) + '\n')
    return s


def running(s):
    require(not s['DHCSR'] & (HALT | LOCKUP | RESET), 'LAST_NOT_RUNNING_OR_RESET_OBSERVED')
    require(s['VTOR'] == 0x08000000 and not (s['CFSR'] | s['HFSR']), 'LAST_ROM_OR_FAULT')
    require(0x08000000 <= s['DWT_PCSR'] < 0x08000000 + IMAGE_BYTES, 'LAST_PC_NOT_FLASH')


def install(link, out, result):
    image = IMAGE.read_bytes()
    require(digest(image) == IMAGE_SHA and len(image) == IMAGE_BYTES, 'LAST_IMAGE_DRIFT')
    link.open()
    board(link, out)
    result['entry_system'] = {k: link.u32(a) for k, a in SYSTEM.items()}
    require(link.call('JLINKARM_Halt') == 0, 'LAST_HALT_FAILED')
    require(link.u32(SYSTEM['DHCSR']) & HALT, 'LAST_HALT_NOT_CONFIRMED')
    result['before_program_core'] = runtime.core_if_halted(link)
    backups, options = [], []
    for i in (1, 2):
        b = link.read(0x08000000, 1048576)
        o = link.read(0x1fffc000, 16)
        save(out, f'before-full-{i}.bin', b)
        save(out, f'before-options-{i}.bin', o)
        backups.append(b)
        options.append(o)
    require(backups[0] == backups[1] and options[0] == options[1], 'LAST_BACKUP_DISAGREEMENT')
    require(digest(options[0]) == runtime.OPTIONS_SHA, 'LAST_OPTIONS_DRIFT')
    save(out, 'before-RAM-private.bin', link.read(0x20000000, 131072))
    expected = payload_for(image, backups[0])
    payload = expected[:32768]
    save(out, 'expected-full-private.bin', expected)
    save(out, 'rollback-sectors01-private.bin', backups[0][:32768])
    result.update(backup_full_sha256=digest(backups[0]), backup_options_sha256=digest(options[0]),
                  expected_full_sha256=digest(expected), candidate_sha256=IMAGE_SHA)
    write_json(out/'verified-backup-plan-private.json', result)
    link.download_payload_sha = digest(payload)
    link.dll.JLINKARM_BeginDownload.argtypes = [C.c_uint32]
    link.dll.JLINKARM_BeginDownload.restype = None
    link.dll.JLINKARM_WriteMem.argtypes = [C.c_uint32, C.c_uint32, C.c_void_p]
    link.dll.JLINKARM_WriteMem.restype = C.c_int
    link.dll.JLINKARM_EndDownload.restype = C.c_int
    buf = (C.c_uint8 * 32768).from_buffer_copy(payload)
    link.stable_halt()
    link.call('JLINKARM_BeginDownload', 0)
    require(link.call('JLINKARM_WriteMem', 0x08000000, 32768, buf) == 32768, 'LAST_WRITE_COUNT')
    require(link.call('JLINKARM_EndDownload', timeout=45) >= 0, 'LAST_DOWNLOAD_FAILED')
    require(link.u32(SYSTEM['DHCSR']) & HALT, 'LAST_LOADER_NOT_HALTED')
    actual = link.read(0x08000000, 1048576)
    save(out, 'after-full-private.bin', actual)
    require(actual == expected and actual[32768:] == backups[0][32768:], 'LAST_FULL_VERIFY_FAILED')
    require(link.read(0x1fffc000, 16) == options[0], 'LAST_OPTIONS_CHANGED')
    after_identity = identity(link)
    check_identity(after_identity)
    ref = json.loads(REFERENCE.read_text('utf-8'))
    require(after_identity['uid_hex'] == ref['uid_hex'] and after_identity['optcr'] == ref['optcr'],
            'LAST_POST_PROGRAM_IDENTITY_DRIFT')
    link.download_verified = True
    link.policy('SetResetType = 0')
    require(link.call('JLINKARM_Reset') == 0, 'LAST_RESET_FAILED')
    core = runtime.core_if_halted(link)
    result['after_reset_core'] = core
    regs = core.get('registers', {})
    sp, pc = int.from_bytes(image[:4], 'little'), int.from_bytes(image[4:8], 'little')
    require(regs.get('R15', 0) & ~1 == pc & ~1 and regs.get('MSP') == sp, 'LAST_RESET_ENTRY_NOT_FLASH')
    link.call('JLINKARM_Go')
    time.sleep(3)
    link.u32(SYSTEM['DHCSR'])  # 记录/消费本次已明确发出的复位粘滞位。
    observations = []
    for i in range(3):
        s = sample(link, out, i)
        running(s)
        observations.append(s)
        time.sleep(1)
    require(observations[-1]['bio']['samples'] > observations[0]['bio']['samples'], 'LAST_NO_ADC_PROGRESS')
    result.update(status='INSTALLED_BACKUP_AND_FULL_VERIFY_PASS', exit_code=0,
                  observations=observations, options_unchanged=True, outside_sector01_unchanged=True)


def observe(link, out, result, action):
    plan = json.loads((PRIVATE/'install-01/verified-backup-plan-private.json').read_text('utf-8'))
    link.open()
    board(link, out)
    require(digest(link.read(0x08000000, IMAGE_BYTES)) == IMAGE_SHA, 'LAST_CANDIDATE_DRIFT')
    require(digest(link.read(0x1fffc000, 16)) == plan['backup_options_sha256'], 'LAST_OBSERVE_OPTIONS_DRIFT')
    link.u32(SYSTEM['DHCSR'])
    first = sample(link, out, 0)
    running(first)
    link.verified_running_flash = True
    link.set_close_resume(True)
    write_json(out/'READY.json', {'action': action, 'screen_reports_at_entry': first['screen_reports']})
    last, event = first, None
    start = time.monotonic()
    for i in range(1, 241 if action == 'screen' else 7):
        time.sleep(.5)
        now = sample(link, out, i)
        running(now)
        require(now['application_ms'] >= last['application_ms'] and now['bio']['samples'] >= last['bio']['samples'],
                'LAST_MCU_COUNTER_RESTARTED')
        if now['screen_reports'] > first['screen_reports'] and event is None:
            event = now['host_monotonic']
            result['screen_event'] = now
        last = now
        if action == 'screen' and event and time.monotonic() - event >= 15:
            break
        require(time.monotonic() - start <= 125, 'LAST_OBSERVATION_DEADLINE')
    require(last['bio']['samples'] > first['bio']['samples'], 'LAST_OBSERVE_NO_SAMPLES')
    if action == 'screen':
        require(event is not None and time.monotonic() - event >= 15, 'LAST_SCREEN_EVENT_NOT_CONFIRMED')
    result.update(status='SCREEN_RESTART_WITHOUT_MCU_RESET_PASS' if action == 'screen' else 'FINAL_FLASH_RUNTIME_OBSERVED',
                  exit_code=0, first=first, last=last, ROM_root_cause='CPU_ROOT_CAUSE_UNRESOLVED')


def worker(args):
    args.out.mkdir(exist_ok=False)
    result = {'status': 'STARTED', 'exit_code': 1, 'action': args.action,
              'tool_sha256': sha(__file__), 'automatic_retry': False, 'ROM_root_cause': 'CPU_ROOT_CAUSE_UNRESOLVED'}
    link = None
    try:
        link = LastLink(args.out, args.action)
        if args.action == 'install':
            install(link, args.out, result)
        else:
            observe(link, args.out, result, args.action)
        link.verified_running_flash = True
        link.set_close_resume(True)
    except BaseException as exc:
        result.update(status='STOP', exit_code=1, error=type(exc).__name__ + ': ' + str(exc))
        if str(exc) == 'LAST_SCREEN_EVENT_NOT_CONFIRMED':
            # 未等到人工重启不等于CPU异常；末次运行已核验时应保持续跑，但测试仍失败。
            result.update(status='SCREEN_EVENT_NOT_OBSERVED', keep_running_on_inconclusive=True)
    finally:
        if link:
            try:
                if (result['exit_code'] and link.close_resume_enabled
                        and not result.get('keep_running_on_inconclusive', False)):
                    link.set_close_resume(False)
            except BaseException as exc:
                result.update(exit_code=1, close_policy_error=str(exc))
            finally:
                try:
                    link.close()
                except BaseException as exc:
                    result.update(exit_code=1, close_error=str(exc))
            result.update(sdk_calls=link.sdk_calls, sdk_function_counts=link.counts,
                          close_resume_enabled=link.close_resume_enabled)
        write_json(args.out/'receipt-private.json', result)
    print(json.dumps({k: result.get(k) for k in ('status', 'exit_code', 'error', 'close_error')}))
    return result['exit_code']


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--action', required=True, choices=('install', 'screen', 'final'))
    p.add_argument('--out', required=True, type=Path)
    p.add_argument('--worker', action='store_true', help=argparse.SUPPRESS)
    args = p.parse_args()
    require(args.out.resolve().is_relative_to(PRIVATE.resolve()) and not args.out.exists(), 'LAST_PRIVATE_EXCLUSIVE_OUTPUT')
    require(args.out.parent.stat().st_file_attributes & stat.FILE_ATTRIBUTE_ENCRYPTED, 'LAST_EFS_REQUIRED')
    if args.worker:
        return worker(args)
    # 独立监督器不调用SDK；硬限180秒，超时只停进程，不重连或回滚烧录。
    command = [sys.executable, '-X', 'utf8', str(Path(__file__)), '--worker', '--action', args.action, '--out', str(args.out)]
    started, reason = time.monotonic(), None
    with args.out.with_name(args.out.name + '-worker.log').open('xb') as log:
        child = subprocess.Popen(command, stdout=log, stderr=subprocess.STDOUT)
        try:
            while child.poll() is None:
                if time.monotonic() - started > 180:
                    reason = 'SESSION_TIMEOUT'
                if (args.out/'STOP').exists():
                    reason = 'OWNER_STOP'
                try:
                    lines = (args.out/'heartbeat-events.jsonl').read_text('utf-8').splitlines()
                    e = json.loads(lines[-1]) if lines else {}
                    if e.get('active') and time.monotonic() > e['deadline_monotonic']:
                        reason = 'SDK_TIMEOUT'
                except (OSError, ValueError):
                    pass
                if reason:
                    child.kill()
                    break
                time.sleep(.05)
        finally:
            if child.poll() is None:
                child.kill()
            child.wait(timeout=5)
    args.out.mkdir(exist_ok=True)
    result = {'reason': reason, 'worker_exit_code': child.returncode, 'elapsed_s': time.monotonic() - started}
    write_json(args.out/'supervisor-private.json', result)
    print(json.dumps(result))
    return child.returncode if not reason else 1


if __name__ == '__main__':
    sys.exit(main())
