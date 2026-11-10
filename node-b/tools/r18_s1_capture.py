"""R18 S1 冷启动长窗被动记录。该程序没有串口发送入口。"""
import argparse
import json
from pathlib import Path
import re
import time

import serial
from serial.tools import list_ports

from b4_recovery import protected
from field01_short_window import mark


class StopGate:
    def __init__(self):
        self.tick = self.uart = None
        self.uart_limit = 5
        self.can = {}
        self.hard_failed = 0

    def observe(self, line):
        if line.startswith(("GW PASS_BOOT_AT_UNCONFIRMED", "GW PASS_BOOT_RESET_LOCKED",
                            "GW PASS_BOOT_UART_STORM", "GW PASS_BOOT_RX_TIMEOUT",
                            "GW PASS_RST_STRAP_LOW_HOLD", "GW FAIL LINK", "B5 STOPPED")):
            return "FIRMWARE_STOP"
        if line.startswith(("GW PASS_HARD_RESET_UNAVAILABLE", "GW PASS_HARD_RESET_UNCONFIRMED")):
            self.hard_failed += 1
            if self.hard_failed >= 2:
                return "PERSISTENT_HARD_RESET_FAILURE"
        elif line == "GW PASS_HARD_RESET_OK":
            self.hard_failed = 0
        if not line.startswith(("B5 DIAG ", "ABC A_CAN ")):
            return None
        data = {key: int(value) for key, value in re.findall(r"(\w+)=(\d+)\b", line)}
        if data.get("stop"):
            return "FIRMWARE_STOP"
        if line.startswith("B5 DIAG ") and "tick" in data:
            tick = data["tick"]
            if self.tick is not None and tick < self.tick:
                return "UNEXPECTED_RESET"
            self.tick = tick
            if "uart_err" in data and ("boot_uart_err0" not in data or data.get("boot_at")):
                if self.uart is None:
                    self.uart = data.get("boot_uart_err0", data["uart_err"])
                    if "boot_uart_err0" in data:
                        self.uart_limit = 1
                if data["uart_err"] - self.uart >= self.uart_limit:
                    return "UART_ERROR_GROWTH"
        if data.get("overflow") or data.get("esr", 0) & 4:
            return "CAN_BUSOFF_OR_OVERFLOW"
        if "esr" in data:
            bus = line.startswith("ABC A_CAN ")
            errors = ((data["esr"] >> 16) & 255, data["esr"] >> 24)
            previous, runs = self.can.get(bus, (errors, (0, 0)))
            runs = tuple(n + 1 if new > old else 0 for new, old, n in zip(errors, previous, runs))
            self.can[bus] = errors, runs
            if max(runs) >= 3:
                return "CAN_ERROR_GROWTH"
        return None


def present(device):
    return any(port.device.upper() == device.upper() for port in list_ports.comports())


def capture(job, device):
    protected(job, False)
    if present(device):
        raise ValueError("COM_ALREADY_PRESENT_COLD_BOOT_NOT_ARMED")
    port = serial.Serial(port=None, baudrate=115200, timeout=.1)
    port.dtr = port.rts = False
    port.port = device
    gate = StopGate()
    reason = "NO_POWER_OR_COM"
    pending = b""
    with (job / "uart-private.jsonl").open("x", encoding="utf-8") as log:
        try:
            mark(job, "HOST_READY", utc_ns=time.time_ns(), uart_write=False)
            end = time.monotonic() + 90
            while time.monotonic() < end and not (job / "ABORT").exists():
                if (job / "ARM").exists() and present(device):
                    try:
                        port.open()
                        break
                    except serial.SerialException:
                        pass
                time.sleep(.05)
            if port.is_open:
                mark(job, "UART_OPEN", utc_ns=time.time_ns())
                end = time.monotonic() + 1800
                reason = "HOST_TIME_LIMIT"
                while time.monotonic() < end:
                    if (job / "ABORT").exists():
                        reason = "OPERATOR_ABORT"
                        break
                    pending += port.read_until(b"\n", 4096)
                    if not pending.endswith(b"\n"):
                        if len(pending) >= 8192:
                            reason = "UART_LINE_TOO_LONG"
                            break
                        continue
                    line = pending.decode("ascii", errors="replace").rstrip("\r\n")
                    log.write(json.dumps(dict(monotonic=time.monotonic(), utc_ns=time.time_ns(),
                                              line=line, wire_hex=pending.hex())) + "\n")
                    log.flush()
                    pending = b""
                    fault = gate.observe(line)
                    if fault:
                        reason = fault
                        break
        except serial.SerialException:
            reason = "COM_REMOVED_FOR_OFF" if (job / "EXPECT_OFF").exists() else "UART_UNEXPECTED_LOSS"
        finally:
            if pending:
                log.write(json.dumps(dict(monotonic=time.monotonic(), utc_ns=time.time_ns(),
                                          partial_wire_hex=pending.hex())) + "\n")
            try:
                port.close()
            finally:
                mark(job, "HOST_ENDED", utc_ns=time.time_ns(), reason=reason)
    return 0 if reason == "COM_REMOVED_FOR_OFF" else 2


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--job", required=True, type=Path)
    parser.add_argument("--port", default="COM15")
    args = parser.parse_args()
    raise SystemExit(capture(args.job, args.port))
