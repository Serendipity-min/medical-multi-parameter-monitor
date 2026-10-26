"""B4受限SWD安装/恢复：每个授权仅一次连接、下载和复位；失败不自动回滚。"""
import argparse
import ctypes as C
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time

import b4_recovery as package
import c_b4_readonly as readonly
import readback_b as raw
import runtime_state_b as runtime
from live_state_b import LiveLink

ROOT = Path(__file__).resolve().parents[2]
SCOPE = 'B4_ONE_SWD_SECTOR_INSTALL_OR_RESTORE_NO_OPTIONS_NO_MASS_ERASE'
DLL = readonly.DLL
LIMITS = {'JLINKARM_Halt': 1, 'JLINKARM_BeginDownload': 1, 'JLINKARM_WriteMem': 1,
          'JLINKARM_EndDownload': 1, 'JLINKARM_Reset': 1, 'JLINKARM_Go': 1}


def require(value, reason):
    if not value:
        raise ValueError(reason)


def bindings():
    return {n: raw.sha(ROOT / 'node-b/tools' / n) for n in
            ('b4_swd_install.py', 'b4_recovery.py', 'c_b4_readonly.py', 'readback_b.py',
             'runtime_state_b.py', 'live_state_b.py', 'resp_exploratory.py')}


def site_ready(board,site):
    # 安装C可让B保持断电；CAN窗口另行要求B上电，不把电源来源写成历史USB状态。
    common={'P4_RX_PB12_TX_PB13': True, 'B_P6_CAN1': True,
            'ESP_isolated': True, 'A_bus_disconnected': True, 'termination_ohms': 60.8,
            'no_human': True, 'target_power_ready': True}
    choices=[{'B':'J5','C':'USB_UART'}]
    if board=='C':choices += [{'B':'OFF','C':'J5'},{'B':'J5','C':'J5'}]
    return any(site==dict(common,power_sources=power) for power in choices)


def authorize(a):
    require(a.get('enabled') is True and a.get('owner_approved') is True
            and a.get('scope') == SCOPE, 'INSTALL_OWNER_AUTH_REQUIRED')
    require(a.get('tools_sha256') == bindings() and a.get('DLL_sha256') == raw.DLL_SHA,
            'INSTALL_TOOL_DRIFT')
    require(time.time() < a.get('expires_unix', 0), 'INSTALL_AUTH_EXPIRED')
    require(a.get('phase') in ('install', 'restore'), 'INSTALL_PHASE')
    require(a.get('board') in ('B', 'C'), 'INSTALL_BOARD')
    require(site_ready(a['board'],a.get('site')),'INSTALL_SITE_NOT_READY')
    m, payload = package.load_package(Path(a['package']), a['manifest_sha256'], False)
    require(m['board_role'] == a['board'] and m['candidate_sha256'] == a['candidate_sha256'],
            'INSTALL_PACKAGE_BINDING')
    require(m['sectors'] == ([0, 1, 2] if a['board'] == 'B' else [0, 1]), 'INSTALL_SECTOR_SCOPE')
    require(m['options_write_allowed'] is False and m['unlock_or_mass_erase_allowed'] is False,
            'INSTALL_PROTECTION_POLICY')
    require(a.get('installed_full_sha256') == m['files']['expected-full-private.bin']['sha256'],
            'INSTALL_EXPECTED_IMAGE_BINDING')
    return m, payload


class InstallLink(LiveLink):
    def __init__(self, out, size):
        self.counts = {}; self.program_size = size
        self.program_sha = None; self.fully_verified = False; self.download_started = False
        super().__init__(DLL, out)
        self.dll.JLINKARM_BeginDownload.argtypes = [C.c_uint32]
        self.dll.JLINKARM_BeginDownload.restype = None
        self.dll.JLINKARM_WriteMem.argtypes = [C.c_uint32, C.c_uint32, C.c_void_p]
        self.dll.JLINKARM_WriteMem.restype = C.c_int
        self.dll.JLINKARM_EndDownload.restype = C.c_int

    def call(self, name, *args, timeout=5):
        require(name in runtime.CALLS | set(LIMITS), 'INSTALL_FUNCTION_DENIED')
        require(self.sdk_calls < 1600, 'INSTALL_SDK_BUDGET')
        if name == 'JLINKARM_ExecCommand':
            cmd = args[0].decode('ascii')
            require(cmd in runtime.COMMANDS or cmd in ('SetRestartOnClose = 1', 'SetResetType = 0'),
                    'INSTALL_POLICY_DENIED')
            if cmd == 'SetRestartOnClose = 1':
                require(self.verified_running_flash, 'INSTALL_CLOSE_NOT_VERIFIED')
        if name == 'JLINKARM_ReadMemEx':
            require(args[1] in readonly.READS.get(args[0], set()) and args[3] == 0,
                    'INSTALL_READ_SCOPE')
        if name in ('JLINKARM_GetRegisterList', 'JLINKARM_GetRegisterName', 'JLINKARM_ReadReg'):
            require(self.register_reads_allowed, 'INSTALL_CORE_REQUIRES_HALT')
        if name in LIMITS:
            require(self.counts.get(name, 0) < LIMITS[name], 'INSTALL_ACTION_BUDGET')
            if name in ('JLINKARM_BeginDownload', 'JLINKARM_WriteMem', 'JLINKARM_EndDownload'):
                require(self.program_sha is not None, 'INSTALL_BEFORE_IMAGE_NOT_VERIFIED')
            if name == 'JLINKARM_BeginDownload':
                require(args == (0,), 'INSTALL_DOWNLOAD_FLAGS')
                self.download_started = True
            if name == 'JLINKARM_WriteMem':
                require(args[:2] == (0x08000000, self.program_size), 'INSTALL_WRITE_SCOPE')
                require(hashlib.sha256(C.string_at(args[2], self.program_size)).hexdigest()
                        == self.program_sha, 'INSTALL_WRITE_BYTES')
            if name in ('JLINKARM_Reset', 'JLINKARM_Go'):
                require(self.fully_verified, 'INSTALL_BOOT_BEFORE_FULL_VERIFY')
            # 尝试本身即消耗预算；原生错误不能换参数再次执行。
            self.counts[name] = self.counts.get(name, 0) + 1
        self.sdk_calls += 1
        return raw.Link.call(self, name, *args, timeout=timeout)

    def read(self, address, size):
        require(size in readonly.READS.get(address, set()), 'INSTALL_READ_SCOPE')
        data = (C.c_uint8 * size)()
        n = self.call('JLINKARM_ReadMemEx', address, size, data, 0,
                      timeout=45 if size == 1048576 else 5)
        require(n == size, 'INSTALL_PARTIAL_READ')
        return bytes(data)


def save(out, name, data):
    with (out / name).open('xb') as f:
        f.write(data)
    require((out / name).read_bytes() == data, 'INSTALL_DISK_VERIFY')


def execute(link, out, a, m, payload):
    original = payload['before-full-private.bin']
    installed = payload['expected-full-private.bin']
    before, expected = (original, installed) if a['phase'] == 'install' else (installed, original)
    reference = json.loads(payload['identity-private.json'])
    size = m['erase_end_exclusive'] - 0x08000000
    link.open()
    seen = raw.identity(link); raw.check_identity(seen)
    require(seen == reference, 'INSTALL_WRONG_BOARD_OR_PROTECTION')
    raw.write_json(out / 'identity-before-private.json', seen)
    raw.write_json(out / 'entry-sticky-private.json', {'DHCSR': link.u32(readonly.SYSTEM['DHCSR'])})
    state = readonly.snapshot(link); raw.write_json(out / 'entry-private.json', state)
    readonly.check_running(link, state)
    link.set_close_resume(True)
    actual = link.read(0x08000000, 1048576); save(out, 'before-full-private.bin', actual)
    require(actual == before, 'INSTALL_CURRENT_FLASH_DRIFT')
    require(link.read(0x1fffc000, 16) == payload['options-private.bin'], 'INSTALL_OPTIONS_BEFORE')
    # 直到真实身份、原件和options全部通过，才允许唯一一次暂停/下载。
    readonly.check_running(link, readonly.snapshot(link))
    link.set_close_resume(False)
    require(link.call('JLINKARM_Halt', timeout=3) == 0, 'INSTALL_HALT_FAILED')
    require(link.u32(readonly.SYSTEM['DHCSR']) & raw.HALT, 'INSTALL_HALT_NOT_CONFIRMED')
    link.u32(readonly.SYSTEM['DHCSR']); link.stable_halt()
    link.verified_running_flash = False
    image = expected[:size]
    link.program_sha = hashlib.sha256(image).hexdigest()
    raw.write_json(out / 'program-intent-private.json', {'phase': a['phase'], 'sectors': m['sectors'],
            'start': 0x08000000, 'bytes': size, 'payload_sha256': link.program_sha,
            'no_options_or_mass_erase': True})
    buf = (C.c_uint8 * size).from_buffer_copy(image)
    link.call('JLINKARM_BeginDownload', 0)
    require(link.call('JLINKARM_WriteMem', 0x08000000, size, buf) == size, 'INSTALL_WRITE_COUNT')
    require(link.call('JLINKARM_EndDownload', timeout=45) >= 0, 'INSTALL_LOADER_FAILED')
    require(link.u32(readonly.SYSTEM['DHCSR']) & raw.HALT, 'INSTALL_LOADER_NOT_HALTED')
    actual = link.read(0x08000000, 1048576); save(out, 'after-full-private.bin', actual)
    require(actual == expected and actual[size:] == before[size:], 'INSTALL_FULL_VERIFY_FAILED')
    options = link.read(0x1fffc000, 16); save(out, 'after-options-private.bin', options)
    require(options == payload['options-private.bin'], 'INSTALL_OPTIONS_AFTER')
    seen_after = raw.identity(link); raw.check_identity(seen_after)
    raw.write_json(out / 'identity-after-private.json', seen_after)
    require(seen_after == reference, 'INSTALL_POST_IDENTITY_OR_PROTECTION')
    link.fully_verified = True
    link.policy('SetResetType = 0')
    require(link.call('JLINKARM_Reset') == 0, 'INSTALL_RESET_FAILED')
    core = runtime.core_if_halted(link); raw.write_json(out / 'reset-core-private.json', core)
    regs = core.get('registers', {})
    require((regs.get('R15', 0) & ~1) == (int.from_bytes(expected[4:8], 'little') & ~1)
            and regs.get('MSP') == int.from_bytes(expected[:4], 'little'), 'INSTALL_RESET_VECTOR')
    link.call('JLINKARM_Go')
    time.sleep(1)
    link.u32(readonly.SYSTEM['DHCSR'])  # 仅消费本次明确发出的复位粘滞位，后续新复位仍拒绝。
    states = []
    for _ in range(3):
        s = readonly.snapshot(link); states.append(s); readonly.check_running(link, s); time.sleep(.2)
    raw.write_json(out / 'running-after-private.json', states)
    link.set_close_resume(True)
    return {'status': 'B4_' + a['phase'].upper() + '_FULL_VERIFY_AND_FLASH_BOOT_PASS',
            'exit_code': 0, 'phase': a['phase'], 'board': a['board'], 'sectors': m['sectors'],
            'full_flash_sha256': hashlib.sha256(actual).hexdigest(), 'options_unchanged': True,
            'outside_affected_sectors_unchanged': True, 'reset_requests': 1,
            'CAN_or_physiology_acceptance': False}


def worker(args, a, m, payload):
    args.out.mkdir(exist_ok=False); link = None
    result = {'status': 'STOP', 'exit_code': 1, 'automatic_retry_or_restore': False}
    try:
        link = InstallLink(args.out, m['erase_end_exclusive'] - 0x08000000)
        result = execute(link, args.out, a, m, payload)
    except BaseException as e:
        raw.write_json(args.out / 'failure-private.json', {'type': type(e).__name__, 'reason': str(e)})
    finally:
        if link:
            try:
                if not link.verified_running_flash and link.close_resume_enabled:
                    link.set_close_resume(False)
            except BaseException as e:
                result.update(exit_code=1, close_policy_error=type(e).__name__)
            finally:
                try: link.close()
                except BaseException as e: result.update(exit_code=1, close_error=type(e).__name__)
            result.update(sdk_calls=link.sdk_calls, actions=link.counts,
                          download_started=link.download_started, close_resume=link.close_resume_enabled)
        raw.write_json(args.out / 'receipt-private.json', result)
        for p in args.out.iterdir():
            if p.is_file(): package.protected(p, False)
    print(json.dumps({'status': result['status'], 'exit_code': result['exit_code']}))
    return result['exit_code']


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--authorization', type=Path); p.add_argument('--out', type=Path)
    p.add_argument('--worker', action='store_true', help=argparse.SUPPRESS)
    p.add_argument('--plan', action='store_true'); args = p.parse_args()
    if args.plan:
        print(json.dumps({'scope': SCOPE, 'enabled': False, 'tools_sha256': bindings(),
              'DLL_sha256': raw.DLL_SHA, 'limits': LIMITS, 'session_seconds': 180})); return 0
    try:
        require(args.authorization is not None and args.out is not None, 'INSTALL_AUTH_OUT_REQUIRED')
        a = json.loads(package.protected(args.authorization, False).read_text('utf-8'))
        m, payload = authorize(a)
        package.protected(args.out.parent, False); require(not args.out.exists(), 'INSTALL_OUTPUT_EXISTS')
        if args.worker: return worker(args, a, m, payload)
        with args.authorization.with_suffix('.used').open('x', encoding='utf-8') as f:
            json.dump({'scope': SCOPE, 'phase': a['phase'], 'started': time.time()}, f)
        # 父进程仅监督磁盘心跳；下载中超时只停止，不追加擦写、复位或补救连接。
        cmd = [sys.executable, '-X', 'utf8', str(Path(__file__)), '--worker',
               '--authorization', str(args.authorization), '--out', str(args.out)]
        reason = None; started = time.monotonic()
        with args.out.with_name(args.out.name + '-worker.log').open('xb') as log:
            child = subprocess.Popen(cmd, stdout=log, stderr=subprocess.STDOUT)
            try:
                while child.poll() is None:
                    if time.monotonic() - started > 180: reason = 'SESSION_TIMEOUT'
                    if (args.out / 'STOP').exists(): reason = 'OWNER_STOP'
                    try:
                        lines = (args.out / 'heartbeat-events.jsonl').read_text('utf-8').splitlines()
                        e = json.loads(lines[-1]) if lines else {}
                        if e.get('active') and time.monotonic() > e['deadline_monotonic']: reason = 'SDK_TIMEOUT'
                    except (OSError, ValueError): pass
                    if reason: child.kill(); break
                    time.sleep(.05)
            finally:
                if child.poll() is None: child.kill()
                child.wait(timeout=5)
        args.out.mkdir(exist_ok=True)
        raw.write_json(args.out / 'supervisor-private.json', {'reason': reason,
                       'worker_exit_code': child.returncode, 'target_state_after_kill': 'UNKNOWN' if reason else None})
        return 1 if reason else child.returncode
    except (ValueError, RuntimeError, OSError, KeyError, TypeError):
        print(json.dumps({'status': 'STOP_BEFORE_SDK', 'exit_code': 1})); return 1


if __name__ == '__main__': sys.exit(main())
