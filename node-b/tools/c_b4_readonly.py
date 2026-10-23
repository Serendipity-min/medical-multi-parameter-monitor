"""C当次完整Flash只读取证。默认关闭；只读SDK在负责人独立授权且现场就绪后才加载。"""
import argparse
import ctypes as C
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time

import readback_b as raw
import runtime_state_b as runtime
from live_state_b import LiveLink
from b4_recovery import protected

ROOT = Path(__file__).resolve().parents[2]
DLL = Path('E:/medical-monitor-node-b-field-private/field-r3/jlink-986a-portable/JLink_x64.dll')
B_REFERENCE = Path('E:/medical-monitor-node-b-field-private/field-r3/readback-r3-02/identity-before-private.json')
SCOPE = 'C_B4_03_ONE_ATTACH_TWO_FULL_READS_NO_RESET_HALT_GO_WRITE'
CURRENT_STATE = 'C_EXISTING_POWER_USB_UART_UNCHANGED_JTAG_C_CAN_OFF_ESP_PRESENT_NETWORK_UNVERIFIED'
OWNER_REQUEST_SHA = '95cbc5507940b39ae790c4d89d9fdc995393a30f8956b31e09caaa833635437c'
SYSTEM = {k: runtime.SYSTEM[k] for k in ('DHCSR', 'VTOR', 'CFSR', 'HFSR', 'RCC_CSR', 'DWT_PCSR',
                                        'RCC_APB2ENR', 'SYSCFG_MEMRMP')}
SYSTEM.update(FLASH_CR=0x40023c10, FLASH_SR=0x40023c0c)
READS = {a: {n} for a, n in raw.REGIONS.items()}
READS[0x08000000] = {64, 1048576}; READS[0] = {64}
READS.update({a: {4} for a in SYSTEM.values()})
REGIONS = {'sector3': (49152, 65536), 'sector7': (393216, 524288), 'sector11': (917504, 1048576)}
H3_APP = 'b9b25b186c3b40d62b4a1c1919e09f27b639806271a3b20ae7fc80ea4cda1efe'
H3_RECORD = '395c6a36d7c4a636b34a72eacd1ccc2a2fc7f025df7089f3d94e1d2de14c5a3b'


def digest(data): return hashlib.sha256(data).hexdigest()
def require(ok, reason):
    if not ok: raise ValueError(reason)


def bindings():
    names = ('c_b4_readonly.py', 'readback_b.py', 'runtime_state_b.py', 'live_state_b.py',
             'resp_exploratory.py', 'b4_recovery.py')
    return {n: digest((ROOT / 'node-b/tools' / n).read_bytes()) for n in names}


def plan():
    return {'scope': SCOPE, 'enabled': False, 'tools_sha256': bindings(), 'DLL_sha256': raw.DLL_SHA,
            'full_flash_range': [0x08000000, 0x08100000], 'flash_reads': 2,
            'options_range': [0x1fffc000, 0x1fffc010], 'options_reads': 2,
            'private_root': 'E:/medical-monitor-node-b-precan-private/20261023',
            'session_timeout_s': 180, 'explicit_reset_halt_go_and_target_writes': 0,
            'probe_sessions': 1, 'retries': 0,
            'protected_regions': {k: [0x08000000 + a, 0x08000000 + b] for k, (a, b) in REGIONS.items()}}


class CReadLink(LiveLink):
    def __init__(self, out):
        self.counts = {}; super().__init__(DLL, out)

    def call(self, name, *args, timeout=5):
        # 白名单不含Reset/Halt/Go/寄存器写、Flash写或看门狗冻结，不能靠参数扩大权限。
        require(name in runtime.CALLS - {'JLINKARM_GetRegisterList', 'JLINKARM_GetRegisterName', 'JLINKARM_ReadReg'},
                'C_RO_FUNCTION_DENIED')
        require(self.sdk_calls < 300, 'C_RO_SDK_BUDGET')
        if name == 'JLINKARM_ExecCommand':
            command = args[0].decode('ascii')
            require(command in runtime.COMMANDS or command == 'SetRestartOnClose = 1', 'C_RO_POLICY_DENIED')
            if command == 'SetRestartOnClose = 1': require(self.verified_running_flash, 'C_RO_CLOSE_NOT_VERIFIED')
        if name == 'JLINKARM_ReadMemEx':
            address, size = args[:2]
            require(size in READS.get(address, set()) and args[3] == 0, 'C_RO_ADDRESS_DENIED')
            if size == 1048576 or address == 0x1fffc000:
                key = (address, size); require(self.counts.get(key, 0) < 2, 'C_RO_DOUBLE_READ_LIMIT')
                self.counts[key] = self.counts.get(key, 0) + 1
        self.sdk_calls += 1
        return raw.Link.call(self, name, *args, timeout=timeout)

    def read(self, address, size):
        require(size in READS.get(address, set()), 'C_RO_ADDRESS_DENIED')
        blob = (C.c_uint8 * size)()
        n = self.call('JLINKARM_ReadMemEx', address, size, blob, 0, timeout=45 if size == 1048576 else 5)
        require(n == size, 'C_RO_PARTIAL_READ')
        self.io.write(json.dumps({'address': hex(address), 'bytes': size, 'returned': n}) + '\n'); self.io.flush()
        return bytes(blob)


def snapshot(link):
    s = {name: link.u32(address) for name, address in SYSTEM.items()}
    s['pc_samples'] = [s['DWT_PCSR'], link.u32(SYSTEM['DWT_PCSR']), link.u32(SYSTEM['DWT_PCSR'])]
    return s


def check_running(link, s):
    link.verified_running_flash = False
    require(not s['DHCSR'] & (raw.HALT | raw.LOCKUP | raw.RESET), 'C_RO_HALTED_LOCKUP_OR_NEW_RESET')
    require(not (s['CFSR'] | s['HFSR']), 'C_RO_FAULT')
    require(s['FLASH_CR'] & 0x80000000 and not s['FLASH_CR'] & 0x10007,
            'C_RO_FLASH_CONTROL_NOT_IDLE_LOCKED')
    require(not any(0x1fff0000 <= p < 0x1fff7800 for p in s['pc_samples']), 'C_RO_ROM_STOP')
    require(any(0x08000000 <= p < 0x08100000 for p in s['pc_samples']), 'C_RO_RUNNING_PC_NOT_PROVEN_NO_HALT')
    require(s['VTOR'] in (0, 0x08000000), 'C_RO_UNREVIEWED_VTOR')
    if s['VTOR'] == 0:
        # Cortex-M复位后VTOR=0且Flash映射到0是合法路径；用真实别名数据佐证，不强写VTOR。
        require(link.read(0, 64) == link.read(0x08000000, 64), 'C_RO_VECTOR_ALIAS_NOT_FLASH')
    link.verified_running_flash = True


def capture(link, out, blocked_b_uid):
    result = {'scope': SCOPE, 'status': 'STARTED', 'exit_code': 1, 'explicit_reset_halt_go_and_writes': 0,
              'ROM_root_cause': 'CPU_ROM_ROOT_CAUSE_UNRESOLVED', 'restore_exercised': False}
    link.open()
    first = raw.identity(link); raw.check_identity(first)
    require(first['uid_hex'] != blocked_b_uid, 'C_RO_PROBE_STILL_ON_B')
    raw.write_json(out / 'identity-a-private.json', first)
    # DHCSR初读的复位粘滞位单独保留，不能将旧粘滞位冒充窗口内复位。
    raw.write_json(out / 'entry-sticky-private.json', {'DHCSR': link.u32(SYSTEM['DHCSR'])})
    entry = snapshot(link); raw.write_json(out / 'entry-private.json', entry); check_running(link, entry)
    link.set_close_resume(True)
    full, options = [], []
    for n in (1, 2):
        o = link.read(0x1fffc000, 16); b = link.read(0x08000000, 1048576)
        # 原件先独占保存再判断；读取不一致也保留两份负例，不自动重试或重刷。
        for name, data in ((f'options-{n}-private.bin', o), (f'flash-{n}-private.bin', b)):
            with (out / name).open('xb') as f: f.write(data)
            require((out / name).read_bytes() == data, 'C_RO_DISK_VERIFY')
        full.append(b); options.append(o)
        s = snapshot(link); raw.write_json(out / f'after-read-{n}-private.json', s); check_running(link, s)
    second = raw.identity(link); raw.check_identity(second)
    raw.write_json(out / 'identity-b-private.json', second)
    require(first == second, 'C_RO_IDENTITY_OR_PROTECTION_DRIFT')
    require(len(full[0]) == 1048576 and full[0] == full[1], 'C_RO_FULL_DOUBLE_READ_MISMATCH')
    require(len(options[0]) == 16 and options[0] == options[1], 'C_RO_OPTIONS_DOUBLE_READ_MISMATCH')
    hashes = {}
    for name, (start, end) in REGIONS.items():
        region = full[0][start:end]
        with (out / (name + '-private.bin')).open('xb') as f: f.write(region)
        hashes[name] = digest(region)
    # 只读比较历史来源，不把历史SHA当今天的原件，也不打印配置正文/设备UID。
    h3_app = digest(full[0][:43172]) == H3_APP
    h3_config = digest(full[0][49152:49152 + 336]) == H3_RECORD
    result.update(status='C_CURRENT_DOUBLE_FULL_READ_PASS', exit_code=0, actual_full_sha256=digest(full[0]),
                  options_sha256=digest(options[0]), region_sha256=hashes,
                  historical_H3_application_match=h3_app, historical_H3_sector3_record_match=h3_config,
                  H3_restore_identity_eligible=h3_app and h3_config,
                  actual_state_note='Current bytes are the restore source; if H3 comparison fails, PI review required, no automatic reflash.')
    return result


def validate_authorization(a):
    require(a.get('enabled') is True and a.get('owner_approved') is True and a.get('scope') == SCOPE,
            'C_RO_OWNER_AUTHORIZATION_REQUIRED')
    require(a.get('tools_sha256') == bindings() and a.get('DLL_sha256') == raw.DLL_SHA, 'C_RO_TOOL_DRIFT')
    require(isinstance(a.get('expires_unix'), (int, float)) and time.time() < a['expires_unix'], 'C_RO_EXPIRED')
    if a.get('field_state') == CURRENT_STATE:
        # 负责人新授权按现状仅备份，不能虚填旧卡的USB断开/ESP隔离事实。
        # 此入口不切电源或控制线，也不授予任何CAN/烧录资格；底层读范围和停止条件不变。
        require(a.get('authorization_basis') == 'OWNER_CURRENT_STATE_BACKUP_ONLY'
                and a.get('owner_request_sha256') == OWNER_REQUEST_SHA, 'C_RO_CURRENT_OWNER_SCOPE')
        require(a.get('site_facts') == {'JLink': 'C', 'ESP8266': 'PRESENT_NETWORK_UNVERIFIED',
                'USB_UART': 'LAST_SEEN_COM15_NO_NEW_COMMANDS', 'CAN': 'DISCONNECTED',
                'INMP441': 'DISCONNECTED', 'TTS': 'DISCONNECTED', 'power_action': 'NONE'},
                'C_RO_CURRENT_SITE_FACTS')
        require(a.get('network_isolation_claimed') is False
                and a.get('bench_admission') is False, 'C_RO_NOT_BENCH_AUTHORIZATION')
    else:
        require(a.get('field_state') == 'C_J5_ONLY_USB_OFF_JTAG_C_CAN_OFF_NO_MIC_TTS_ESP_ISOLATED',
                'C_RO_FIELD_NOT_READY')
        require(a.get('card_sha256') == raw.sha(ROOT / 'node-b/docs/AUTH-C-B4-03-READONLY-001-R1.md'),
                'C_RO_CARD_DRIFT')
    require(a.get('B_reference_sha256') == raw.sha(B_REFERENCE), 'C_RO_B_EXCLUSION_REFERENCE_DRIFT')


def worker(args, authorization):
    out = args.out; out.mkdir(exist_ok=False)
    link = None; result = {'scope': SCOPE, 'status': 'STOP', 'exit_code': 1}
    try:
        link = CReadLink(out)
        result = capture(link, out, json.loads(B_REFERENCE.read_text('utf-8'))['uid_hex'])
        result.update(authorization_field_state=authorization['field_state'],
                      network_isolation_validated=False, CAN_bench_authorized=False)
    except BaseException as e:
        # 完整原生日志留EFS；公开仅错误类型，不能让SDK异常字符串泄漏身份或配置。
        result.update(status='STOP', exit_code=1, error_type=type(e).__name__)
        raw.write_json(out / 'failure-private.json', {'type': type(e).__name__, 'reason': str(e)})
    finally:
        if link:
            try:
                if not link.verified_running_flash and link.close_resume_enabled: link.set_close_resume(False)
            except BaseException as e: result.update(exit_code=1, close_policy_error_type=type(e).__name__)
            finally:
                # 策略设置失败也必须尝试唯一一次Close，不能跳过原生句柄清理。
                try: link.close()
                except BaseException as e: result.update(exit_code=1, close_error_type=type(e).__name__)
            result.update(sdk_calls=link.sdk_calls, close_resume_enabled=link.close_resume_enabled)
        for p in out.glob('*'):
            if p.is_file(): protected(p, False)
        raw.write_json(out / 'receipt-private.json', result)
    print(json.dumps({k: result[k] for k in ('status', 'exit_code')}))
    return result['exit_code']


def main():
    p = argparse.ArgumentParser(description=__doc__); p.add_argument('--plan', action='store_true')
    p.add_argument('--authorization', type=Path); p.add_argument('--out', type=Path)
    p.add_argument('--worker', action='store_true', help=argparse.SUPPRESS); args = p.parse_args()
    if args.plan:
        print(json.dumps(plan(), ensure_ascii=False, indent=2)); return 0
    try:
        require(args.authorization is not None and args.out is not None, 'C_RO_AUTHORIZATION_AND_OUTPUT_REQUIRED')
        auth = json.loads(protected(args.authorization, False).read_text('utf-8')); validate_authorization(auth)
        require(not args.out.exists(), 'C_RO_OUTPUT_EXISTS'); protected(args.out.parent, False)
        if args.worker: return worker(args, auth)
        # 授权仅消费一次；父进程启动前独占落盘，失败后也不能换目录重跑旧许可。
        with args.authorization.with_suffix('.used').open('x', encoding='utf-8') as mark:
            mark.write(json.dumps({'scope': SCOPE, 'started_unix': time.time()}))
        # 原生SDK阻塞由独立父进程看门；总硬限180秒，调用限45/5秒，不重连、不清故障。
        argv = [sys.executable, '-X', 'utf8', str(Path(__file__)), '--worker', '--authorization', str(args.authorization), '--out', str(args.out)]
        reason = None; start = time.monotonic()
        with args.out.with_name(args.out.name + '-worker.log').open('xb') as log:
            child = subprocess.Popen(argv, stdout=log, stderr=subprocess.STDOUT)
            try:
                while child.poll() is None:
                    if time.monotonic() - start > 180: reason = 'SESSION_TIMEOUT'
                    if (args.out / 'STOP').exists(): reason = 'OWNER_STOP'
                    try:
                        events = (args.out / 'heartbeat-events.jsonl').read_text('utf-8').splitlines()
                        e = json.loads(events[-1]) if events else {}
                        if e.get('active') and time.monotonic() > e['deadline_monotonic']: reason = 'SDK_TIMEOUT'
                    except (OSError, ValueError): pass
                    if reason: child.kill(); break
                    time.sleep(.05)
            finally:
                if child.poll() is None: child.kill()
                child.wait(timeout=5)
        args.out.mkdir(exist_ok=True)
        raw.write_json(args.out / 'supervisor-private.json', {'reason': reason, 'worker_exit_code': child.returncode})
        return child.returncode if not reason else 1
    except (ValueError, OSError, TypeError) as e:
        print(json.dumps({'status': 'STOP_BEFORE_SDK', 'error_type': type(e).__name__})); return 1


if __name__ == '__main__': sys.exit(main())
