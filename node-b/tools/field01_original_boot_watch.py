"""原五板 C 回退后的单次被动串口启动检查。"""
import argparse
import json
import time
from pathlib import Path

import serial

from b4_recovery import protected
from field01_short_window import OPERATOR_READY_S, mark

BOOT_BANNER = b"UNI DISARMED V1 C_BC_ABC NO_FLASH_WRITE"
OBSERVE_S = 59


def capture(job, device):
    protected(job, False)
    if any(job.iterdir()):
        raise ValueError("ORIGINAL_BOOT_NEW_TRANSACTION_REQUIRED")
    port = serial.Serial(port=None, baudrate=115200, timeout=.1)
    port.dtr = port.rts = False
    port.port = device
    reason = "POWER_NOT_CONFIRMED"
    seen_ms = None
    try:
        mark(job, "HOST_READY", max_physical_power_s=60)
        wait_until = time.monotonic() + OPERATOR_READY_S
        while not (job / "POWER_ALLOWED").is_file():
            if (job / "ABORT").exists() or time.monotonic() >= wait_until:
                break
            time.sleep(.05)
        else:
            started = time.monotonic()
            deadline = started + OBSERVE_S
            reason = "BOOT_BANNER_NOT_SEEN"
            pending = b""
            while time.monotonic() < deadline:
                if (job / "ABORT").exists():
                    reason = "OPERATOR_ABORT"
                    break
                if not port.is_open:
                    try:
                        port.open()
                    except serial.SerialException:
                        time.sleep(.05)
                        continue
                fragment = port.read_until(expected=b"\n", size=512)
                pending = (pending + fragment)[:len(BOOT_BANNER) + 3]
                if fragment.endswith(b"\n"):
                    now = time.monotonic()
                    if now < deadline and pending in (BOOT_BANNER + b"\n", BOOT_BANNER + b"\r\n"):
                        reason = "ORIGINAL_BOOT_BANNER_SEEN"
                        seen_ms = int((now - started) * 1000)
                        break
                    pending = b""
    except serial.SerialException:
        reason = "SERIAL_ERROR"
    finally:
        if port.is_open:
            try:
                port.close()
            except serial.SerialException:
                reason = "SERIAL_CLOSE_ERROR"
        status = "PASS" if reason == "ORIGINAL_BOOT_BANNER_SEEN" else "BLOCKED"
        with (job / "ORIGINAL-BOOT-RESULT-public.json").open("x", encoding="utf-8") as stream:
            json.dump(dict(status=status, reason=reason, seen_ms=seen_ms, power_off="PENDING"), stream)
            stream.write("\n")
    return 0 if status == "PASS" else 2


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--job", type=Path, required=True)
    parser.add_argument("--port", default="COM15")
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args()
    if not args.execute:
        print(json.dumps(dict(execute=False, max_physical_power_s=60)))
        return 0
    return capture(args.job, args.port)


if __name__ == "__main__":
    raise SystemExit(main())
