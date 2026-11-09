"""R10 FIELD01 串口控制器。COM 打开后绑定纯复位证据，只发送 START/STOP。"""
import argparse
import json
from pathlib import Path
import re
import time

import serial

from b4_recovery import protected
from field01_short_window import BOOT_BANNER, STOP_BANNER, START, STOP, command, mark


class Gate:
    def __init__(self, power, max_power_s=210):
        self.end = power + max_power_s - 10
        self.cue = None
        self.boot = None
        self.sent = False
        self.accepted = False
        self.t0 = None
        self.stopped = None
        self.stop_reason = None
        self.fault = None
        self.uart = None
        self.can = {}

    def observe(self, line, now):
        if line == BOOT_BANNER:
            if self.boot is not None:
                self.fault = "UNEXPECTED_RESET"
            elif self.cue is not None and now >= self.cue:
                self.boot = now
        if not self.sent:
            return
        if line == "FIELD01 START_ACCEPTED":
            self.accepted = True
        elif line == "FIELD01 T0" and self.accepted and self.t0 is None:
            self.t0 = now
        elif line == STOP_BANNER and self.stopped is None:
            self.stopped = now
        elif line.startswith("B5 STOP_STATE "):
            reason = re.search(r"\breason=(\d+)", line)
            if reason:
                self.stop_reason = int(reason[1])
        elif line.startswith(("FIELD01 CAN ", "B5 DIAG ")):
            data = {k: int(v) for k, v in re.findall(r"(\w+)=(\d+)", line)}
            if "uart_err" in data:
                count = data["uart_err"]
                if self.uart is None:
                    self.uart = count
                elif count - self.uart >= 5:
                    self.fault = "UART_ERROR_GROWTH"
            if "busoff" in data:
                if data["busoff"] or data["overflow"]:
                    self.fault = "CAN_BUSOFF_OR_OVERFLOW"
                bus = data["bus"]
                esr = data["esr"]
                errors = ((esr >> 16) & 255, esr >> 24)
                prev, run = self.can.get(bus, (errors, (0, 0)))
                run = tuple(n + 1 if new > old else 0 for new, old, n in zip(errors, prev, run))
                self.can[bus] = errors, run
                if max(run) >= 3:
                    self.fault = "CAN_ERROR_GROWTH"

    def can_start(self, reset_verified, now):
        return bool(reset_verified and self.boot is not None and not self.sent and not self.fault
                    and now < min(self.boot + 45, self.end - 153))


def capture(job, port_name, max_power_s):
    protected(job, False)
    receiver = job / "receiver"
    if not (receiver / "READY.json").is_file():
        raise ValueError("RECEIVER_NOT_READY")
    power = json.loads((job / "POWER.json").read_text())["monotonic"]
    gate = Gate(power, max_power_s)
    port = serial.Serial(port=None, baudrate=115200, timeout=.1, write_timeout=.5)
    port.dtr = port.rts = False
    port.port = port_name
    stop_sent = False
    reason = "RESET_GATE_NOT_COMPLETED"
    pending = b""
    try:
        with (job / "uart-private.jsonl").open("x", encoding="utf-8") as log:
            port.open()
            port.reset_input_buffer()
            mark(job, "UART_OPEN", dtr=False, rts=False)
            while time.monotonic() < gate.end:
                now = time.monotonic()
                cue = job / "RESET_CUE.json"
                if gate.cue is None and cue.exists():
                    gate.cue = json.loads(cue.read_text())["monotonic"]
                if (job / "ABORT").exists() or gate.fault:
                    reason = gate.fault or "OPERATOR_ABORT"
                    break
                if gate.can_start((job / "RESET_VERIFIED").is_file(), now):
                    mark(job, "START_SENT")
                    gate.sent = True
                    command(port, START)
                    reason = "T0_NOT_CONFIRMED"
                if not gate.sent and now >= gate.end - 153:
                    break
                if gate.sent and gate.t0 is None and now >= min(gate.boot + 45, gate.end - 150):
                    break
                if gate.stopped is not None and now >= gate.stopped + 3:
                    reason = ("WINDOW_STOP_OBSERVED" if gate.t0 is not None and
                              gate.stopped - gate.t0 >= 149 and
                              (gate.stop_reason == 10 or (stop_sent and gate.stop_reason == 11))
                              else "EARLY_OR_UNVERIFIED_STOP")
                    break
                if gate.t0 is not None and gate.stopped is None and now >= gate.t0 + 151 and not stop_sent:
                    stop_sent = True
                    command(port, STOP)
                pending += port.read_until(b"\n", 4096)
                if not pending.endswith(b"\n"):
                    if len(pending) >= 8192:
                        reason = "OVERSIZE_UART_LINE"
                        break
                    continue
                line = pending.decode("ascii", errors="replace").rstrip("\r\n")
                pending = b""
                arrival = time.monotonic()
                log.write(json.dumps(dict(monotonic=arrival, line=line)) + "\n")
                log.flush()
                prev_t0, prev_stop = gate.t0, gate.stopped
                gate.observe(line, arrival)
                if gate.t0 is not None and prev_t0 is None:
                    mark(job, "T0", utc_ns=time.time_ns())
                    reason = "WINDOW_END_NOT_CONFIRMED"
                if gate.stopped is not None and prev_stop is None:
                    mark(job, "C_STOPPED", utc_ns=time.time_ns())
    finally:
        if gate.sent and gate.stopped is None and not stop_sent and port.is_open and time.monotonic() < gate.end:
            try:
                stop_sent = True
                command(port, STOP)
            except serial.SerialException:
                pass
        port.close()
        (receiver / "STOP_RECEIVER").touch()
        mark(job, "HOST_ENDED", reason=reason, sent=gate.sent, accepted=gate.accepted,
             t0=gate.t0, stopped=gate.stopped, stop_reason=gate.stop_reason, stop_sent=stop_sent, boot=gate.boot)
    return 0 if reason == "WINDOW_STOP_OBSERVED" else 2


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--job", required=True, type=Path)
    p.add_argument("--port", default="COM15")
    p.add_argument("--max-power-s", type=int, choices=(210, 240), default=210)
    p.add_argument("--execute", action="store_true")
    args = p.parse_args()
    if args.execute:
        raise SystemExit(capture(args.job, args.port, args.max_power_s))
