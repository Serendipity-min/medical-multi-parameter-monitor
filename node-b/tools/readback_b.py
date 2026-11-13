"""B板只读身份/Flash双读；唯一硬件入口受卡SHA、DLL SHA及固定地址限制。"""
import argparse
import ctypes as C
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import sys
import time

DLL_SHA = '632d0d78e72b8a55c65945a0c393a9f081082c725fff4ba3081b0a565fd58cff'
PRIVATE = Path('E:/medical-monitor-node-b-field-private/field-r3')
HALT, LOCKUP, RESET = 1 << 17, 1 << 19, 1 << 25
REGIONS = {0xE000ED00: 4, 0xE000EDF0: 4, 0xE0042000: 4,
           0x1FFF7A10: 12, 0x1FFF7A22: 2, 0x40023C0C: 4,
           0x40023C14: 4, 0x1FFFC000: 16, 0x08000000: 1048576}
POLICY = ['SuppressGUI 1', 'DisableAutoUpdateFW = 1', 'SetRestartOnClose 0',
          'InhibitConnectRetries = 1', 'ForceAttachTarget = 1',
          'ExcludeFlashCacheRange 0x08000000-0x080FFFFF',
          'ExcludeFlashCacheRange 0x1FFFC000-0x1FFFC00F']


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def require(ok, reason):
    if not ok:
        raise RuntimeError(reason)


def write_json(path, data):
    # 独占创建，失败回执、原件及重复轮次不得互相覆盖。
    with Path(path).open('x', encoding='utf-8', newline='\n') as stream:
        json.dump(data, stream, indent=2, ensure_ascii=False)
        stream.write('\n')


class HWStatus(C.Structure):
    _fields_ = [('voltage_mv', C.c_uint16)] + [(n, C.c_uint8) for n in
                 ('tck', 'tdi', 'tdo', 'tms', 'tres', 'trst')]


class Link:
    def __init__(self, dll, out):
        require(sha(dll) == DLL_SHA, 'DLL_IDENTITY_MISMATCH')
        self.out = out
        self.opened = False
        self.error = False
        self.started = time.monotonic()
        self.log = (out/'sdk-private.log').open('xb')
        self.io = (out/'io-private.jsonl').open('x', encoding='utf-8')
        self.events = (out/'heartbeat-events.jsonl').open('x', encoding='utf-8')
        # 精确目录加载，不依赖全局PATH或改变已安装J-Link版本。
        self.directory = os.add_dll_directory(str(dll.parent))
        self.dll = C.CDLL(str(dll))
        callback = C.CFUNCTYPE(None, C.c_char_p)

        def log(data):
            if data:
                self.log.write(data+b'\n')
                self.log.flush()

        def error(data):
            log(data)
            self.error = True

        self.logger, self.error_callback = callback(log), callback(error)
        self.dll.JLINKARM_OpenEx.argtypes = [callback, callback]
        self.dll.JLINKARM_OpenEx.restype = C.c_char_p
        self.dll.JLINKARM_ExecCommand.argtypes = [C.c_char_p, C.c_char_p, C.c_int]
        self.dll.JLINKARM_ExecCommand.restype = C.c_int
        self.dll.JLINKARM_ReadMemEx.argtypes = [C.c_uint32, C.c_uint32, C.c_void_p, C.c_uint32]
        self.dll.JLINKARM_ReadMemEx.restype = C.c_int
        self.dll.JLINKARM_GetHWStatus.argtypes = [C.POINTER(HWStatus)]
        self.dll.JLINKARM_GetHWStatus.restype = C.c_int
        self.dll.JLINKARM_Close.restype = None
        self.dll.JLINKARM_Go.restype = None

    def gate(self):
        require(not (self.out/'STOP').exists(), 'OWNER_STOP')
        require(time.monotonic()-self.started <= 180, 'SESSION_TIMEOUT')
        require(not self.error, 'SDK_ERROR_SEE_PRIVATE_LOG')

    def call(self, name, *args, timeout=5):
        self.gate()
        # 监督进程据此在DLL阻塞时终止本进程；不能仅在函数返回后才发现超时。
        heartbeat = {'operation': name, 'active': True, 'deadline_monotonic': time.monotonic()+timeout}
        self.events.write(json.dumps(heartbeat)+'\n')
        self.events.flush()
        result = getattr(self.dll, name)(*args)
        require(time.monotonic() <= heartbeat['deadline_monotonic'], 'SDK_CALL_TIMEOUT')
        self.events.write(json.dumps({'operation': name, 'active': False})+'\n')
        self.events.flush()
        self.gate()
        return result

    def policy(self, command):
        self.gate()
        output = C.create_string_buffer(2048)
        result = self.call('JLINKARM_ExecCommand', command.encode('ascii'), output, len(output))
        self.io.write(json.dumps({'policy': command, 'result': result,
                                  'output': output.value.decode(errors='replace')})+'\n')
        self.io.flush()
        if command == 'SetRestartOnClose 0' and result == 1 and not output.value:
            # 此命令返回此前开关值：首次1并非错误；重复设置必须回报此前已为0。
            result = self.call('JLINKARM_ExecCommand', command.encode('ascii'), output, len(output))
            self.io.write(json.dumps({'policy_confirm': command, 'previous_value': result,
                                      'output': output.value.decode(errors='replace')})+'\n')
            self.io.flush()
        require(result == 0 and not output.value, 'POLICY_NOT_ACCEPTED')
        self.gate()

    def open(self):
        for command in POLICY[:5]:
            self.policy(command)
        self.gate()
        require(self.call('JLINKARM_EMU_GetNumDevices') == 1, 'PROBE_COUNT_NOT_ONE')
        require(self.call('JLINKARM_SelectUSB', 0) == 0, 'PROBE_SELECTION_FAILED')
        result = self.call('JLINKARM_OpenEx', self.logger, self.error_callback)
        require(result is None, 'PROBE_OPEN_FAILED_SEE_PRIVATE_LOG')
        self.opened = True
        # 某些策略在Open前仅解析；Open后、任何目标Device/Connect前再次全部确认。
        for command in [POLICY[2], POLICY[1], *POLICY[3:]]:
            self.policy(command)
        status = HWStatus()
        require(self.call('JLINKARM_GetHWStatus', C.byref(status)) == 0, 'PROBE_STATUS_FAILED')
        write_json(self.out/'probe-status-private.json', {'voltage_mv': status.voltage_mv})
        require(3000 <= status.voltage_mv <= 3600, 'TARGET_REFERENCE_NOT_3V3')
        require(self.call('JLINKARM_TIF_Select', 1) == 0, 'SWD_SELECTION_FAILED')
        self.call('JLINKARM_SetSpeed', 1000)
        # Device选择可能自动连接，所以所有guard必须先就位，不再做第二次Connect重试。
        self.policy('Device = STM32F407ZG')
        if not self.call('JLINKARM_IsConnected'):
            require(self.call('JLINKARM_Connect') >= 0, 'TARGET_ATTACH_FAILED')
        self.gate()

    def read(self, address, size):
        self.gate()
        require(REGIONS.get(address) == size, 'READ_RANGE_DENIED')
        buffer = (C.c_uint8*size)()
        before = time.monotonic()
        result = self.call('JLINKARM_ReadMemEx', address, size, buffer, 0,
                           timeout=45 if size == 1048576 else 5)
        elapsed = time.monotonic()-before
        self.io.write(json.dumps({'address': hex(address), 'bytes': size,
                                  'returned': result, 'elapsed_s': elapsed})+'\n')
        self.io.flush()
        require(result == size, 'PARTIAL_READ')
        require(elapsed <= (45 if size == 1048576 else 5), 'READ_TIMEOUT')
        self.gate()
        return bytes(buffer)

    def u32(self, address):
        return int.from_bytes(self.read(address, 4), 'little')

    def stable_halt(self):
        state = self.u32(0xE000EDF0)
        require(state & HALT and not state & (LOCKUP | RESET), 'HALT_LOST_OR_RESET')

    def close(self):
        # 错误路径不发go/reset，不在finally中“恢复”；Close已被guard禁止自动go。
        if self.opened:
            self.events.write(json.dumps({'operation': 'JLINKARM_Close', 'active': True,
                                         'deadline_monotonic': time.monotonic()+5})+'\n')
            self.events.flush()
            self.dll.JLINKARM_Close()
            self.events.write(json.dumps({'operation': 'JLINKARM_Close', 'active': False})+'\n')
            self.events.flush()
            self.opened = False
        self.io.close()
        self.log.close()
        self.events.close()
        self.directory.close()


def identity(link):
    return {'cpuid': link.u32(0xE000ED00), 'device_id': link.u32(0xE0042000),
            'uid_hex': link.read(0x1FFF7A10, 12).hex(),
            'capacity_kib': int.from_bytes(link.read(0x1FFF7A22, 2), 'little'),
            'optcr': link.u32(0x40023C14), 'flash_sr': link.u32(0x40023C0C)}


def check_identity(value):
    require(value['device_id'] & 0xfff == 0x413, 'DEVICE_ID_MISMATCH')
    require(value['cpuid'] >> 4 & 0xfff == 0xc24, 'CORE_NOT_M4')
    require(value['capacity_kib'] == 1024, 'FLASH_CAPACITY_MISMATCH')
    require((value['optcr'] >> 8) & 255 == 0xaa, 'RDP_NOT_LEVEL_ZERO')
    require(value['flash_sr'] & 0x100f2 == 0, 'FLASH_BUSY_OR_ERROR')
    require(value['uid_hex'] not in ('00'*12, 'ff'*12), 'INVALID_UID')


def acquire(link, out, receipt):
    link.open()
    initial = link.u32(0xE000EDF0)
    require(not initial & LOCKUP, 'INITIAL_LOCKUP')
    first = identity(link)
    check_identity(first)
    write_json(out/'identity-before-private.json', first)
    receipt['initial_state'] = 'HALTED' if initial & HALT else 'RUNNING'
    if not initial & HALT:
        link.gate()
        require(link.call('JLINKARM_Halt', timeout=3) == 0, 'HALT_REQUEST_FAILED')
        receipt['halt_requests'] += 1
    # 启动前复位粘滞状态先记录并建立基准，不将其冒充本窗口新增复位。
    require(link.u32(0xE000EDF0) & HALT, 'HALT_NOT_CONFIRMED')
    link.stable_halt()
    second = identity(link)
    check_identity(second)
    require(second == first, 'IDENTITY_OR_PROTECTION_DRIFT')
    for index in (1, 2):
        for address, size, name in [(0x1FFFC000, 16, 'options'), (0x08000000, 1048576, 'flash')]:
            link.stable_halt()
            data = link.read(address, size)
            with (out/('{}-read-{}.bin'.format(name, index))).open('xb') as stream:
                stream.write(data)
            link.stable_halt()
    check_identity(identity(link))
    require(identity(link) == second, 'FINAL_IDENTITY_DRIFT')
    for name, size in [('options', 16), ('flash', 1048576)]:
        paths = [out/('{}-read-{}.bin'.format(name, i)) for i in (1, 2)]
        require(all(p.stat().st_size == size for p in paths), 'BACKUP_SIZE')
        require(paths[0].read_bytes() == paths[1].read_bytes(), 'BACKUP_DIFFERENCE')
        receipt[name+'_sha256'] = sha(paths[0])
    link.stable_halt()
    if not initial & HALT:
        link.gate()
        link.call('JLINKARM_Go')
        receipt['go_requests'] += 1
        for _ in range(2):
            time.sleep(.02)
            require(not link.u32(0xE000EDF0) & (HALT | LOCKUP | RESET), 'RESUME_NOT_CONFIRMED')
        receipt['target_end_state'] = 'RUNNING_CONFIRMED'
    else:
        receipt['target_end_state'] = 'HALTED_AS_FOUND'
    receipt['status'] = 'BACKUP_DOUBLE_READ_PASS'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dll', type=Path, required=True)
    parser.add_argument('--card', type=Path, required=True)
    parser.add_argument('--card-sha256', required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    require(sha(args.card) == args.card_sha256, 'CARD_SHA_MISMATCH')
    require(args.out.resolve().is_relative_to(PRIVATE.resolve()), 'OUTPUT_NOT_RESTRICTED')
    args.out.mkdir(exist_ok=False)
    receipt = {'status': 'STARTED', 'hardware_access': True, 'halt_requests': 0, 'go_requests': 0,
               'reset_requests': 0, 'flash_write_requests': 0, 'target_end_state': 'UNKNOWN',
               'card_sha256': args.card_sha256, 'tool_sha256': sha(__file__),
               'dll_sha256': DLL_SHA, 'started_utc': dt.datetime.now(dt.timezone.utc).isoformat()}
    link = None
    try:
        link = Link(args.dll.resolve(), args.out)
        acquire(link, args.out, receipt)
    except BaseException as exc:
        receipt.update(status='STOP_OR_INCOMPLETE', error=type(exc).__name__+': '+str(exc),
                       target_end_state='UNKNOWN_NO_AUTOMATIC_RECOVERY')
    finally:
        if link is not None:
            try:
                link.close()
            except BaseException as exc:
                receipt.update(status='STOP_OR_INCOMPLETE', close_error=type(exc).__name__,
                               target_end_state='UNKNOWN_AFTER_CLOSE_ERROR')
        receipt['ended_utc'] = dt.datetime.now(dt.timezone.utc).isoformat()
        write_json(args.out/'receipt-private.json', receipt)
    print(json.dumps({'status': receipt['status'], 'error': receipt.get('error'),
                      'target_end_state': receipt['target_end_state'], 'hardware_write': False}))
    return 0 if receipt['status'] == 'BACKUP_DOUBLE_READ_PASS' else 1


if __name__ == '__main__':
    sys.exit(main())
