"""复位后的C只读核对并恢复RAM配置；不擦写Flash，复位脉冲须显式选择。"""
import argparse
from contextlib import redirect_stderr, redirect_stdout
from datetime import datetime, timezone
import io
import json
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from gateway.physical_can.h3_flash_c import PRIVATE, START, sha, verify_plan
from gateway.physical_can.bench.flash_c import GateError, external_identity, verify_f4_identity, read_exact, protected_hashes


def resume_verified(boot, image, config, baseline):
    # 所有Flash/选项字节只读检查通过后，才允许写已预留的312B SRAM。
    options = read_exact(boot, 0x1FFFC000, 16)
    if options[1] != 0xAA or sha(options) != baseline['options_sha256']:
        raise GateError('RESUME_OPTIONS_CHANGED')
    if protected_hashes(boot) != baseline['protected']:
        raise GateError('RESUME_PROTECTED_CHANGED')
    if read_exact(boot, START, len(image)) != image:
        raise GateError('RESUME_APPLICATION_CHANGED')
    boot.write_memory_data(0x2001FE00, config)
    if read_exact(boot, 0x2001FE00, len(config)) != config:
        raise GateError('RESUME_RAM_READBACK_FAILED')
    # 标准ROM GO仍执行应用向量与启动代码；不能以调试器强设寄存器替代启动。
    boot.go(START)
    return {'application_readback_match': True, 'protected_unchanged': True,
            'options_unchanged': True, 'RAM_config_readback_match': True, 'go_sent': True}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--config', type=Path, required=True)
    parser.add_argument('--observe-seconds', type=int, default=1200)
    parser.add_argument('--reset-c', action='store_true')
    args = parser.parse_args()
    if not 0 <= args.observe_seconds <= 1800:
        parser.error('observe range 0..1800')
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    target = ROOT/'gateway/physical_can/evidence/h3'/('c-resume-'+stamp+'.json')
    result = {'action': 'C_VERIFY_RAM_RESUME', 'flash_write_started': False,
              'reset_sent': False, 'exit_code': 1}
    capture = io.StringIO()
    uart = None
    try:
        import serial
        from stm32loader.uart import SerialConnection
        from stm32loader.bootloader import Stm32Bootloader
        manifest = json.loads((ROOT/'gateway/physical_can/evidence/h3/isolated-arm-result.json').read_text())
        image = (ROOT/'gateway/physical_can/build/h3-isolated/gateway_physical_can.bin').read_bytes()
        if args.config.resolve().is_relative_to(ROOT):
            raise GateError('CONFIG_MUST_BE_EXTERNAL')
        config = args.config.read_bytes()
        result['image'] = verify_plan(manifest, image, config)
        for group in ('source_sha256', 'build_input_sha256'):
            for name, digest in manifest[group].items():
                if not name.startswith('external-sdk/') and sha((ROOT/name).read_bytes()) != digest:
                    raise GateError('BUILD_INPUT_CHANGED')
        baseline = json.loads((ROOT/'gateway/physical_can/evidence/h3/c-read-20261019T122613Z.json').read_text())
        if baseline.get('exit_code') != 0 or not baseline.get('C_identity_match'):
            raise GateError('PREFLIGHT_NOT_VERIFIED')
        # 本机C下载线reset_active_high=True：DTR=True才是释放NRST；
        # boot0_active_low=True对应RTS=True保持下载状态。不能套用两线均False。
        uart = serial.Serial(port=None, baudrate=115200, parity='E', timeout=2, write_timeout=2)
        uart.dtr = True
        uart.rts = True
        uart.port = 'COM15'
        with redirect_stdout(capture), redirect_stderr(capture):
            uart.open()
            connection = SerialConnection('COM15', 115200, 'E')
            connection.serial_connection = uart
            connection.reset_active_high = True
            connection.boot0_active_low = True
            boot = Stm32Bootloader(connection, device_family='F4', verbosity=0)
            if args.reset_c:
                # 现场已确认A断电时，复用本轮成功的C下载线复位极性和握手时序。
                result['reset_sent'] = True
                boot.reset_from_system_memory()
            else:
                uart.write(b'\x7f')
                if uart.read(1) not in (b'\x79', b'\x1f'):
                    raise GateError('ROM_SYNC_NOT_CONFIRMED')
            boot.get()
            verify_f4_identity(boot, external_identity(Path('E:/stm32/ai_serial_console/tools/flash.py')))
            result['C_identity_match'] = True
            result.update(resume_verified(boot, image, config, baseline))
            target.write_text(json.dumps(result, indent=2), encoding='utf-8')
            uart.parity = 'N'
            uart.timeout = .1
            time.sleep(.3)
            initial = uart.read(uart.in_waiting)
            if args.observe_seconds:
                # 保留同一个串口句柄，防止关闭/重开导致刚注入的RAM配置丢失。
                from gateway.physical_can.h3_observe import observe
                result['observation_exit_code'] = observe(uart, args.observe_seconds, PRIVATE, initial)
        result['exit_code'] = 0
    except Exception as exc:
        result['failure_type'] = type(exc).__name__
        if isinstance(exc, GateError):
            result['failure_code'] = str(exc)
        capture.write('\n'+repr(exc))
    finally:
        if uart:
            uart.close()
        (PRIVATE/('c-resume-'+stamp+'.raw.log')).write_text(capture.getvalue(), encoding='utf-8')
        target.write_text(json.dumps(result, indent=2), encoding='utf-8')
        print(json.dumps(result, indent=2))
    return result['exit_code']


if __name__ == '__main__':
    raise SystemExit(main())
