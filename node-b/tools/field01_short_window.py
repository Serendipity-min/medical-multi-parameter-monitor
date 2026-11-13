"""Issue #8 单次串口记录器。现场供断电由人员操作，观察器必须先就绪。"""
import argparse
import json
from pathlib import Path
import time

import serial
from b4_recovery import protected

MAX_POWER_S = 210
PREP_S = 45
WINDOW_S = 150
OPERATOR_READY_S = 180
SHUTDOWN_RESERVE_S = 10
BOOT_BANNER = "FIELD01 DISARMED C_ONLY_INSTALL TLS_28895 NO_AUTORETRY"
STOP_BANNER = "B5 STOPPED NO_AUTOREARM"
START = b'FIELD01 START\n'
STOP = b'FIELD01 STOP\n'
KEY = b'FIELD01 KEY\n'


def mark(job, name, **fields):
    with (job / (name + '.json')).open('x', encoding='utf-8') as out:
        json.dump(dict(monotonic=time.monotonic(), **fields), out)
        out.write('\n')
    print(name, flush=True)


def command(port, payload):
    if port.write(payload) != len(payload):
        raise OSError('FIELD01_UART_SHORT_WRITE')


def capture(job, device, enable_key, wait_disarmed=False, usb_powers_c=False):
    protected(job, False)
    if usb_powers_c and not wait_disarmed:
        raise ValueError('FIELD01_USB_POWER_REQUIRES_FRESH_BOOT_GATE')
    preopen = wait_disarmed and not usb_powers_c
    if not (job / 'receiver/READY.json').is_file():
        raise ValueError('FIELD01_RECEIVER_NOT_READY')
    # 上电许可文件须在本进程启动后由现场协调员创建。重启或中途退出保留消费标记。
    if any((job / name).exists() for name in ('POWER_ALLOWED', 'START_SENT.json', 'HOST_READY.json')):
        raise ValueError('FIELD01_NEW_TRANSACTION_REQUIRED')
    port = serial.Serial(port=None, baudrate=115200, timeout=.1, write_timeout=1)
    port.dtr = port.rts = False
    port.port = device
    sent = accepted = stopped = tts_idle = stop_sent = False
    t0 = None
    reason = 'POWER_NOT_CONFIRMED'
    attach_failures = 0
    last_attach_error = None
    with (job / 'C-uart-private.jsonl').open('x', encoding='utf-8') as raw:
        partial = b''

        def read_line():
            nonlocal partial
            partial += port.read_until(expected=b'\n', size=2048)
            if not partial.endswith(b'\n') and len(partial) < 2048:
                return ''
            line = partial.decode('ascii', errors='replace').rstrip()
            partial = b''
            raw.write(json.dumps(dict(monotonic=time.monotonic(), line=line)) + '\n')
            raw.flush()
            return line

        try:
            if preopen:
                reason = 'UART_PREOPEN_FAILED'
                port.open()
                port.reset_input_buffer()
                reason = 'POWER_NOT_CONFIRMED'
            mark(job, 'HOST_READY', uart_preopened=preopen, usb_powers_c=usb_powers_c)
            wait = time.monotonic() + OPERATOR_READY_S
            while not (job / 'POWER_ALLOWED').exists():
                if (job / 'ABORT').exists() or time.monotonic() >= wait:
                    return 2
                if preopen:
                    line = read_line()
                    if line == BOOT_BANNER or line.startswith('B5 STOP'):
                        reason = 'C_ACTIVITY_BEFORE_POWER_CUE'
                        return 2
                else:
                    time.sleep(.05)
            power = time.monotonic()
            # 从上电口令计全组硬限时，保留完整观察窗和人工收尾余量。
            ready_deadline = power + MAX_POWER_S - WINDOW_S - SHUTDOWN_RESERVE_S
            reason = 'UART_ATTACH_NOT_CONFIRMED'
            attach_deadline = ready_deadline if usb_powers_c else power + 15
            while not port.is_open and time.monotonic() < attach_deadline:
                if (job / 'ABORT').exists():
                    return 2
                try:
                    port.open()
                except serial.SerialException as error:
                    attach_failures += 1
                    cause = next((item for item in error.args if isinstance(item, OSError)), error)
                    detail = str(error)
                    kind = ('PORT_NOT_FOUND' if isinstance(cause, FileNotFoundError) or 'FileNotFoundError' in detail
                            else 'PORT_ACCESS_DENIED' if isinstance(cause, PermissionError) or 'PermissionError' in detail
                            else 'OTHER_SERIAL_ERROR')
                    last_attach_error = dict(kind=kind, errno=cause.errno,
                                             winerror=getattr(cause, 'winerror', None))
                    time.sleep(.1)
            if not port.is_open:
                return 2
            if wait_disarmed:
                reason = 'C_BOOT_BANNER_NOT_SEEN'
                while time.monotonic() < ready_deadline and not (job / 'ABORT').exists():
                    line = read_line()
                    if line == STOP_BANNER:
                        reason = 'C_ALREADY_STOPPED_BEFORE_START'
                        stopped = True
                        mark(job, 'C_STOPPED')
                        return 2
                    if line == BOOT_BANNER:
                        boot = time.monotonic()
                        ready_deadline = min(ready_deadline, boot + PREP_S)
                        mark(job, 'C_BOOT_BANNER')
                        break
                else:
                    return 2
            else:
                ready_deadline = min(ready_deadline, power + PREP_S)
            reason = 'START_OR_T0_NOT_CONFIRMED'
            mark(job, 'START_SENT')
            sent = True
            command(port, START)
            key_cue = False
            while time.monotonic() < power + MAX_POWER_S - 2:
                now = time.monotonic()
                if (job / 'ABORT').exists():
                    reason = 'OPERATOR_ABORT'
                    break
                if t0 is None and now >= ready_deadline:
                    break
                if t0 is not None and enable_key and not key_cue and now >= t0 + 35:
                    key_cue = True
                    mark(job, 'K1_T35')
                if t0 is not None and not stop_sent and now >= t0 + WINDOW_S:
                    command(port, STOP)
                    stop_sent = True
                line = read_line()
                if not line:
                    continue
                if line == 'FIELD01 START_ACCEPTED':
                    accepted = True
                if line == 'FIELD01 T0' and accepted and t0 is None:
                    t0 = time.monotonic()
                    mark(job, 'T0')
                    reason = 'END_NOT_CONFIRMED'
                    if enable_key:
                        command(port, KEY)
                if line == STOP_BANNER and not stopped:
                    stopped = True
                    mark(job, 'C_STOPPED')
                if stopped and line.startswith('UNI AUDIO') and ' stop_idle=1 ' in line:
                    tts_idle = True
                if stopped and (tts_idle or t0 is None or now < t0 + WINDOW_S - 1):
                    reason = 'CAPTURE_ENDED_REQUIRES_REVIEW'
                    break
            return 0 if t0 is not None and stopped else 2
        finally:
            if sent and not stopped and not stop_sent and port.is_open:
                try:
                    command(port, STOP)
                    stop_sent = True
                except serial.SerialException:
                    pass
            if port.is_open:
                port.close()
            (job / 'receiver/STOP_RECEIVER').touch()
            mark(job, 'HOST_ENDED', reason=reason, start_attempted=sent,
                 start_accepted=accepted, t0_seen=t0 is not None, stop_attempted=stop_sent,
                 C_stop_seen=stopped, tts_idle_seen=tts_idle,
                 uart_attach_failures=attach_failures, last_uart_attach_error=last_attach_error)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--job', type=Path, required=True)
    parser.add_argument('--port', default='COM15')
    parser.add_argument('--enable-key', action='store_true', help='现场已确认 K1 对应 PE3')
    parser.add_argument('--wait-disarmed', action='store_true', help='C 独立断电时预开串口，收到上电启动标记后才发 START')
    parser.add_argument('--usb-powers-c', action='store_true', help='仅用于现场已确认 USB_UART 是 C 的正常供电方式')
    parser.add_argument('--execute', action='store_true')
    args = parser.parse_args()
    if args.execute:
        raise SystemExit(capture(args.job, args.port, args.enable_key, args.wait_disarmed, args.usb_powers_c))
    print(json.dumps(dict(execute=False, max_power_s=MAX_POWER_S, prep_s=PREP_S, window_s=WINDOW_S,
                          operator_ready_s=OPERATOR_READY_S, shutdown_reserve_s=SHUTDOWN_RESERVE_S,
                          automatic_retry=False, key_requires_confirmation=True)))
