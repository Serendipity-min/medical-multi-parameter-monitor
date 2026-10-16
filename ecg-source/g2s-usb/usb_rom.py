"""S板专用USB串口ROM下载流程：身份先验、全片双读、sector0最小写入、完整回读。

不调用原控制台MCP，不修改其固定固件/目标；不解除读保护，不写Option/OTP。
所有硬件动作必须在G2-S现场门禁通过后明确调用；导入模块不会打开串口。
"""
from pathlib import Path
import argparse
import contextlib
import datetime
import hashlib
import importlib.metadata
import io
import json
import sys

BASE = 0x08000000
SIZE = 1024 * 1024
SECTOR0 = 16384
ROOT = Path(__file__).resolve().parents[2]


def manual_connection(port):
    from stm32loader.uart import SerialConnection
    import serial

    class ManualConnection(SerialConnection):
        def connect(self):
            # 手动BOOT时，在打开端口前释放RESET并禁用自动BOOT0输出。
            # 不用Serial(port=...)的默认DTR/RTS状态触发额外复位。
            obj=serial.Serial(port=None, baudrate=self.baud_rate, bytesize=8,
                              parity=self.parity, stopbits=1, timeout=5,
                              write_timeout=5, xonxoff=False, rtscts=False, dsrdtr=False)
            obj.port=self.serial_port;obj.dtr=True;obj.rts=False
            obj.open();self.serial_connection=obj

        def enable_reset(self, enable=True):
            # 由现场明确按RESET，工具不切换DTR，避免重用不稳定的自动时序。
            pass

        def enable_boot0(self, enable=True):
            # BOOT0由断电时装好的跳帽决定；不冒称软件能恢复Flash启动。
            pass

    return ManualConnection(port,115200,'E')


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def restore_capabilities(boot):
    # 只发送ROM GET查询。擦写前确认同一连接真实支持READ/WRITE/ERASE，
    # 不用库函数存在或Host模拟通过来代替设备自身能力声明。
    boot.command(0x00, 'Get supported commands')
    count = bytes(boot.connection.read(1))
    if len(count) != 1:
        raise RuntimeError('ROM GET头短读，拒绝擦写')
    payload = bytes(boot.connection.read(count[0] + 1))
    if len(payload) != count[0] + 1:
        raise RuntimeError('ROM GET能力短读，拒绝擦写')
    boot._wait_for_ack('GET supported commands end')
    commands = set(payload[1:])
    if not {0x00, 0x02, 0x11, 0x31}.issubset(commands) or not ({0x43, 0x44} & commands):
        raise RuntimeError('ROM缺少恢复所需命令，拒绝擦写')
    boot.extended_erase = 0x44 in commands
    return {'ROM_version': payload[0], 'ROM_supported_commands': sorted(commands),
            'ROM_restore_commands_verified': True}


def identity(boot):
    # 芯片类别与Flash容量不能只由端口号推断；UID只进入本地私有绑定文件。
    chip = boot.get_id()
    if chip != 0x413:
        raise RuntimeError('源板芯片类别不符，未擦写')
    # 已安装stm32loader 0.7.1的get_flash_size_and_uid明确记录F4拒绝12/2字节
    # 分散读取的兼容性问题。采用相同的256字节对齐读取，再提取UID与容量；
    # 首次短读NACK失败证据保留，不把它误判为读保护，也不解除任何保护。
    signature = bytes(boot.read_memory(0x1FFF7A00, 256))
    if len(signature) != 256:
        raise RuntimeError('电子签名块短读，未擦写')
    uid = signature[0x10:0x1C]
    capacity = signature[0x22:0x24]
    if len(uid) != 12 or uid in (b'\0' * 12, b'\xff' * 12):
        raise RuntimeError('无法可靠取得源板身份，未擦写')
    if len(capacity) != 2 or int.from_bytes(capacity, 'little') != 1024:
        raise RuntimeError('源板Flash容量不为1MiB，未擦写')
    return {'chip': chip, 'uid_private_hex': uid.hex(), 'flash_bytes': SIZE}


def read_flash(boot, dest=None):
    data = bytearray()
    # 每块检查真实长度，防止把串口短读或未读保护区填充成成功备份。
    handle = dest.open('xb') if dest else contextlib.nullcontext()
    with handle as stream:
        for offset in range(0, SIZE, 256):
            part = bytes(boot.read_memory(BASE + offset, 256))
            if len(part) != 256:
                raise RuntimeError('Flash短读，保留部分文件并停止')
            data.extend(part)
            if dest:
                stream.write(part)
    return bytes(data)


def backup(boot, out):
    found = identity(boot)
    (out / 'identity-private.json').write_text(json.dumps(found, indent=2), encoding='utf-8')
    first = read_flash(boot, out / 'original-a.bin')
    second = read_flash(boot, out / 'original-b.bin')
    if first != second or identity(boot) != found:
        raise RuntimeError('源板身份或双读不一致，停止且未擦写')
    record = {'action': 'backup', 'status': 'PASS', 'flash_bytes': SIZE,
              'sha256': digest(first), 'copies_equal': True,
              'option_OTP_modified': False, 'flash_modified': False}
    (out / 'backup.json').write_text(json.dumps(record, indent=2), encoding='utf-8')
    return record


def bound_original(boot, folder):
    saved = json.loads((folder / 'backup.json').read_text(encoding='utf-8'))
    expected = json.loads((folder / 'identity-private.json').read_text(encoding='utf-8'))
    if saved.get('status') != 'PASS' or saved.get('action') != 'backup' or not saved.get('copies_equal'):
        raise RuntimeError('没有合格双读备份，拒绝擦写')
    a = (folder / 'original-a.bin').read_bytes()
    b = (folder / 'original-b.bin').read_bytes()
    if a != b or len(a) != SIZE or digest(a) != saved['sha256']:
        raise RuntimeError('备份文件完整性不符，拒绝擦写')
    if identity(boot) != expected:
        raise RuntimeError('源板与备份绑定身份不符，拒绝擦写')
    return a


def candidate(build, expected_sha):
    # 仅接受本独立变体的真实构建目录，不接收其它工程固件；先核对产物与输入。
    build = build.resolve()
    if build.parent != (ROOT / 'ecg-source/build').resolve() or not build.name.startswith('usb-arm-'):
        raise RuntimeError('固件不在S专用USB构建目录')
    receipt = json.loads((build / 'receipt.json').read_text(encoding='utf-8'))
    if receipt.get('status') != 'PASS' or receipt.get('exit_code') != 0 or receipt.get('errors') != 0:
        raise RuntimeError('候选没有通过真实ARM构建')
    raw = (build / 'MPM_ECG_SOURCE_USB.bin').read_bytes()
    actual = digest(raw)
    if actual != expected_sha or receipt['outputs']['MPM_ECG_SOURCE_USB.bin']['sha256'] != actual:
        raise RuntimeError('固件SHA不符，拒绝擦写')
    for f in json.loads((build / 'input-manifest.json').read_text(encoding='utf-8'))['files']:
        if f['path'].endswith(('.c', '.h', '.s')):
            if digest((build / f['path']).read_bytes()) != f['sha256']:
                raise RuntimeError('归档源码身份不符')
            if digest((ROOT / 'ecg-source' / f['path']).read_bytes()) != f['sha256']:
                raise RuntimeError('当前源码已偏离构建输入，拒绝擦写')
    if not 8 <= len(raw) <= SECTOR0:
        raise RuntimeError('候选越过已限定sector0，停止')
    sp = int.from_bytes(raw[:4], 'little')
    entry = int.from_bytes(raw[4:8], 'little')
    if not 0x20000000 < sp <= 0x20020000 or not entry & 1 or not BASE <= (entry & ~1) < BASE + len(raw):
        raise RuntimeError('固件向量不符合本源板布局')
    return raw


def flash(boot, folder, raw, out):
    original = bound_original(boot, folder)
    # 擦除前同一连接内再次全读，确认用户备份后未更换/改写源板。
    current = read_flash(boot, out / 'pre-flash.bin')
    if current != original:
        raise RuntimeError('备份后Flash发生漂移，停止且未擦写')
    planned = raw + b'\xff' * (SECTOR0 - len(raw)) + original[SECTOR0:]
    (out / 'erase-started.marker').write_text('S sector0 only\n', encoding='utf-8')
    boot.erase_memory([0])
    boot.write_memory_data(BASE, bytearray(raw))
    actual = read_flash(boot, out / 'post-flash.bin')
    if actual != planned:
        raise RuntimeError('全片回读与计划不一致，保留ROM模式等待恢复')
    return {'action': 'flash', 'status': 'PASS', 'bin_sha256': digest(raw),
            'verified_full_flash_sha256': digest(actual), 'original_sha256': digest(original),
            'erased_sectors': [0], 'untouched_sectors_equal': actual[SECTOR0:] == original[SECTOR0:]}


def restore(boot, folder, out):
    original = bound_original(boot, folder)
    (out / 'erase-started.marker').write_text('S full Flash restore, no Option/OTP\n', encoding='utf-8')
    boot.erase_memory()
    # 整片恢复保留原镜像；全FF块不必编程，但仍通过最终完整回读检查。
    for offset in range(0, SIZE, 256):
        part = original[offset:offset + 256]
        if part != b'\xff' * len(part):
            boot.write_memory(BASE + offset, bytearray(part))
    actual = read_flash(boot, out / 'restored-readback.bin')
    if actual != original:
        raise RuntimeError('原Flash恢复核验失败，保留ROM模式并停止')
    return {'action': 'restore', 'status': 'PASS', 'full_flash_sha256': digest(actual),
            'restored_bytes': SIZE, 'option_OTP_modified': False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['probe', 'backup', 'flash', 'restore'])
    parser.add_argument('--port', required=True)
    parser.add_argument('--source-S-only', action='store_true', required=True)
    parser.add_argument('--manual-boot', action='store_true', help='须现场已设置S.B0=3V3/B1=GND并按RESET；不自动切BOOT/RESET')
    parser.add_argument('--backup', type=Path)
    parser.add_argument('--build', type=Path)
    parser.add_argument('--sha256')
    args = parser.parse_args()
    if importlib.metadata.version('stm32loader') != '0.7.1' or importlib.metadata.version('pyserial') != '3.5':
        raise RuntimeError('串口依赖版本与已核验版本不符')
    raw = candidate(args.build, args.sha256) if args.action == 'flash' and args.build and args.sha256 else None
    if args.action in ('flash', 'restore') and not args.backup:
        raise RuntimeError('擦写必须提供源板完整双读备份')
    if args.action == 'flash' and raw is None:
        raise RuntimeError('缺少固件构建与准确SHA')
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    out = ROOT / 'local-evidence/G2S-20261015' / (args.action + '-' + stamp)
    out.mkdir(parents=True)
    from stm32loader.uart import SerialConnection
    from stm32loader.bootloader import Stm32Bootloader
    connection = manual_connection(args.port) if args.manual_boot else SerialConnection(args.port, 115200, 'E')
    connection.reset_active_high = True
    connection.boot0_active_low = True
    boot = None
    ok = False
    report = {'action': args.action, 'status': 'FAIL', 'port': args.port,
              'source': 'S_CONFIRMED_BY_OPERATOR', 'run_directory': out.name,
              'tool_sha256': digest(Path(__file__).read_bytes()),
              'stm32loader_version': '0.7.1', 'pyserial_version': '3.5',
              'boot_control': 'OPERATOR_MANUAL' if args.manual_boot else 'CH340_AUTOMATIC'}
    try:
        # 第三方信息可能含UID；不回显原始输出，异常详情仅留本地私有日志。
        with (out / 'transport-private.log').open('x', encoding='utf-8') as log:
            with contextlib.redirect_stdout(log), contextlib.redirect_stderr(log):
                connection.connect()
                boot = Stm32Bootloader(connection, device_family='F4', verbosity=10 if args.action == 'probe' else 0)
                report['phase'] = 'ROM_RESET'
                boot.reset_from_system_memory()
                report['phase'] = 'ROM_INITIAL_GET'
                report['ROM_initial_version'] = boot.get()
                if args.action in ('probe', 'flash', 'restore'):
                    report['phase'] = 'RESTORE_CAPABILITIES_GET'
                    report.update(restore_capabilities(boot))
                report['phase'] = 'BOUND_IDENTITY_AND_FLASH_OPERATION'
                if args.action == 'probe':
                    identity(boot)
                    report.update(status='PASS', flash_modified=False)
                elif args.action == 'backup':
                    report.update(backup(boot, out))
                elif args.action == 'flash':
                    report.update(flash(boot, args.backup, raw, out))
                else:
                    report.update(restore(boot, args.backup, out))
                ok = True
    except BaseException as error:
        report['error_type'] = type(error).__name__
        (out / 'failure-private.txt').write_text(str(error), encoding='utf-8')
    finally:
        # 擦写失败时不启动部分固件；保持ROM供恢复。未擦写或成功时恢复Flash启动。
        try:
            if args.manual_boot:
                report['manual_BOOT0_GND_and_RESET_required_for_application'] = True
            elif boot and (ok or not (out / 'erase-started.marker').exists()):
                boot.reset_from_flash()
                report['reset_to_flash'] = True
            elif boot:
                report['kept_ROM_for_recovery'] = True
        except Exception as error:
            report.update(status='FAIL', cleanup_error_type=type(error).__name__)
        if connection.serial_connection:
            connection.serial_connection.close()
        (out / 'result.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(report, ensure_ascii=True), flush=True)
    return 0 if report.get('status') == 'PASS' else 1


if __name__ == '__main__':
    sys.exit(main())
