"""单连接运行核验：不复位、不暂停、不烧录；正常 Flash 退出时明确续跑。"""
import argparse
import ctypes as C
import hashlib
import json
from pathlib import Path
import stat
import subprocess
import sys
import time

import runtime_state_b as old
from readback_b import Link, HALT, LOCKUP, RESET, identity, check_identity, require, write_json, sha

PRIVATE = Path('E:/medical-monitor-node-b-precan-private/20261023')
CANDIDATE_SHA = '438a8120f6df06ce219cdc30c0e5b697ac0e993f98d5a80521b10361536ae3ae'
REGS = old.SYSTEM | {'application_ms': 0x20000044, 'HMI_10ms_ticks': 0x2000013c}
READS = {a: n for a, n in old.REGIONS.items() if a != 0x08000000}
READS.update({a: 4 for a in REGS.values()})
READS.update({0x08000000: 25284, 0x20001ae4: 120, 0x2000018c: 48, 0x200001bc: 12,
              0x1fff0000: 30720})
RESUME_CLOSE = 'SetRestartOnClose = 1'


def normal_flash(s):
    """PCSR 是运行采样而非暂停后的 R15；不可用时不冒充真实 PC。"""
    r = s['system']
    return (r['VTOR'] == 0x08000000 and not (r['CFSR'] | r['HFSR'])
            and not ((r['DHCSR'] | s['DHCSR_after']) & (HALT | LOCKUP | RESET))
            and 'BIO_V2_FLASH' in s['pc_regions']
            and 'SYSTEM_ROM' not in s['pc_regions'])


def snapshot(link, out, label):
    # 复用冻结的 BIO 解码，同时单独留存应用时基，避免改动旧快照格式。
    s = old.snapshot(link, out, label)
    clocks = {name: link.u32(REGS[name]) for name in ('application_ms', 'HMI_10ms_ticks')}
    write_json(out/(label + '-clocks-private.json'), clocks)
    s['application_clocks'] = clocks
    return s


class LiveLink(old.RuntimeLink):
    def __init__(self, dll, out):
        self.verified_running_flash = False
        self.close_resume_enabled = False
        super().__init__(dll, out)

    def call(self, name, *args, timeout=5):
        # 保留历史工具原件，新入口单独收紧地址；不读 UART DR，不读取整块 RAM。
        require(name in old.CALLS, 'LIVE_FUNCTION_DENIED')
        require(self.sdk_calls < 500, 'LIVE_SDK_BUDGET')
        if name == 'JLINKARM_ExecCommand':
            command = args[0].decode('ascii')
            require(command in old.COMMANDS or command == RESUME_CLOSE, 'LIVE_COMMAND_DENIED')
            if command == RESUME_CLOSE:
                require(self.verified_running_flash, 'LIVE_CLOSE_REQUIRES_VERIFIED_RUNNING_FLASH')
        if name == 'JLINKARM_ReadMemEx':
            require(READS.get(args[0]) == args[1] and args[3] == 0, 'LIVE_READ_SCOPE')
        if name in ('JLINKARM_GetRegisterList', 'JLINKARM_GetRegisterName', 'JLINKARM_ReadReg'):
            require(self.register_reads_allowed, 'LIVE_CORE_REQUIRES_ALREADY_HALTED')
        self.sdk_calls += 1
        return Link.call(self, name, *args, timeout=timeout)

    def read(self, address, size):
        require(READS.get(address) == size, 'LIVE_READ_SCOPE')
        blob = (C.c_uint8 * size)()
        n = self.call('JLINKARM_ReadMemEx', address, size, blob, 0)
        require(n == size, 'LIVE_PARTIAL_READ')
        return bytes(blob)

    def set_close_resume(self, enabled):
        if not enabled:
            self.policy('SetRestartOnClose 0')
        else:
            # SDK 返回此前开关值，0/1 都可能成功；必须没有错误文本。
            output = C.create_string_buffer(2048)
            result = self.call('JLINKARM_ExecCommand', RESUME_CLOSE.encode(), output, len(output))
            require(result in (0, 1) and not output.value, 'LIVE_CLOSE_POLICY_FAILED')
        self.close_resume_enabled = enabled


def inspect(dll, reference, out, read_rom=False):
    result = {'status': 'STARTED', 'exit_code': 1, 'reset_requests': 0, 'halt_requests': 0,
              'explicit_go_requests': 0, 'target_data_writes': 0,
              'ROM_root_cause': 'CPU_ROOT_CAUSE_UNRESOLVED', 'P0_pass': False,
              'post_close_state': 'REQUIRES_INDEPENDENT_OBSERVATION'}
    link = None
    try:
        link = LiveLink(dll, out)
        link.open()
        seen = identity(link)
        check_identity(seen)
        require(seen['uid_hex'] == reference['uid_hex'] and seen['optcr'] == reference['optcr'],
                'LIVE_BOARD_IDENTITY')
        write_json(out/'identity-private.json', seen)
        first = snapshot(link, out, 'entry')
        # 如果进入时已经暂停，只取真实寄存器并停止，绝不自动 Go 或改向量。
        result['entry_core'] = old.core_if_halted(link)
        image = link.read(0x08000000, 25284)
        result['candidate_sha256'] = hashlib.sha256(image).hexdigest()
        require(result['candidate_sha256'] == CANDIDATE_SHA, 'LIVE_FIRMWARE_DRIFT')
        require(sha_bytes(link.read(0x1fffc000, 16)) == old.OPTIONS_SHA, 'LIVE_OPTIONS_DRIFT')
        # 首次 DHCSR 的复位粘滞位只能记录，另取即时状态后判断，不能冒充窗口内复位。
        first_check = snapshot(link, out, 'entry-check')
        result['snapshots'] = [first, first_check]
        require(normal_flash(first_check), 'LIVE_ENTRY_NOT_RUNNING_FLASH')
        link.verified_running_flash = True
        link.set_close_resume(True)
        if read_rom:
            # 仅导出 F407 固定系统 ROM 范围用于离线反汇编；绝不执行 ROM 或改 PC。
            rom = link.read(0x1fff0000, 30720)
            with (out/'system-ROM-private.bin').open('xb') as stream:
                stream.write(rom)
            result['system_ROM_sha256'] = sha_bytes(rom)
        time.sleep(3)
        last = snapshot(link, out, 'before-close')
        result['snapshots'].append(last)
        require(normal_flash(last), 'LIVE_END_NOT_RUNNING_FLASH')
        require(last['bio'] is not None and first_check['bio'] is not None
                and last['bio']['samples'] > first_check['bio']['samples'], 'LIVE_NO_BIO_PROGRESS')
        result.update(status='RUNNING_FLASH_OBSERVED', exit_code=0)
    except BaseException as exc:
        result.update(status='STOP', error=type(exc).__name__ + ': ' + str(exc))
    finally:
        if link:
            try:
                # 异常路径取消隐式续跑，保留异常现场；不会为了收尾恢复 ROM/故障态。
                if result['exit_code'] and link.close_resume_enabled:
                    link.set_close_resume(False)
            except BaseException as exc:
                result.update(status='CLOSE_POLICY_FAILED', exit_code=1, close_policy_error=str(exc))
            finally:
                # 取消策略失败也必须尝试唯一一次 Close，保留两项原生错误。
                try:
                    link.close()
                except BaseException as exc:
                    result.update(status='CLOSE_FAILED', exit_code=1, close_error=str(exc))
            result['close_resume_enabled'] = link.close_resume_enabled
            result['sdk_calls'] = link.sdk_calls
        write_json(out/'receipt-private.json', result)
    return result


def sha_bytes(blob):
    return hashlib.sha256(blob).hexdigest()


def supervise(args):
    """监督器只读磁盘心跳；DLL 卡死时结束子进程，不另连硬件补救。"""
    argv = [sys.executable, '-X', 'utf8', str(Path(__file__)), '--worker']
    for name in ('dll', 'reference', 'out'):
        argv.extend(['--' + name, str(getattr(args, name))])
    if args.read_rom:
        argv.append('--read-rom')
    started = time.monotonic()
    reason = None
    with args.out.with_name(args.out.name + '-worker.log').open('xb') as stream:
        child = subprocess.Popen(argv, stdout=stream, stderr=subprocess.STDOUT)
        try:
            while child.poll() is None:
                if time.monotonic() - started > 90:
                    reason = 'SESSION_DEADLINE'
                if (args.out/'STOP').exists():
                    reason = 'OWNER_STOP'
                heartbeat = args.out/'heartbeat-events.jsonl'
                try:
                    lines = heartbeat.read_text('utf-8').splitlines()
                    event = json.loads(lines[-1]) if lines else {}
                    if event.get('active') and time.monotonic() > event['deadline_monotonic']:
                        reason = 'SDK_DEADLINE'
                except (OSError, ValueError):
                    pass  # 正在追加的半行不表示成功，全会话硬限继续生效。
                if reason:
                    child.kill()
                    break
                time.sleep(.02)
        finally:
            if child.poll() is None:
                child.kill()
            child.wait(timeout=5)
    args.out.mkdir(exist_ok=True)
    result = {'reason': reason, 'worker_exit_code': child.returncode,
              'elapsed_s': time.monotonic() - started, 'automatic_hardware_recovery': False}
    write_json(args.out/'supervisor-private.json', result)
    print(json.dumps(result))
    return child.returncode if not reason else 1


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('dll', 'reference', 'out'):
        p.add_argument('--' + name, required=True, type=Path)
    p.add_argument('--worker', action='store_true', help=argparse.SUPPRESS)
    p.add_argument('--read-rom', action='store_true', help='保存固定30KiB系统ROM用于离线归因')
    args = p.parse_args()
    # 原始身份和内存诊断只写既有受限 EFS 目录；独占新目录避免覆盖旧窗口。
    require(args.out.resolve().is_relative_to(PRIVATE.resolve()), 'LIVE_PRIVATE_OUTPUT')
    require(args.out.parent.stat().st_file_attributes & stat.FILE_ATTRIBUTE_ENCRYPTED, 'LIVE_EFS_REQUIRED')
    require(not args.out.exists(), 'LIVE_OUTPUT_EXISTS')
    if not args.worker:
        return supervise(args)
    reference = json.loads(args.reference.read_text('utf-8'))
    args.out.mkdir(exist_ok=False)
    write_json(args.out/'tool-bindings.json', {p.name: sha(p) for p in
               (Path(__file__), Path(old.__file__), Path(__file__).with_name('readback_b.py'),
                Path(__file__).with_name('resp_exploratory.py'))})
    result = inspect(args.dll, reference, args.out, args.read_rom)
    print(json.dumps({k: result.get(k) for k in ('status', 'exit_code', 'error', 'close_error')}))
    return result['exit_code']


if __name__ == '__main__':
    sys.exit(main())
