"""FIELD01 C-only 单次预检记录器，现场供断电由负责人操作。"""
import argparse
import hashlib
import json
import platform
import re
import time
import uuid
from pathlib import Path

import serial

from b4_recovery import protected
from field01_short_window import BOOT_BANNER, MAX_POWER_S, OPERATOR_READY_S, PREP_S, mark

COMMANDS = {
    115200: b"FIELD01 PRE\n",
    230400: b"FIELD01 PRE 230\n",
    500000: b"FIELD01 PRE 500\n",
}
UINT = r"[0-9]{1,10}"
FIELDS = [
    ("BEGIN", rf"boot_ms=(?P<boot_ms>{UINT}) target=(?P<target>{UINT})"),
    ("AT", r"ok=(?P<ok>[01])"),
    ("GMR", r"ver=(?P<ver>NONE|[0-9][0-9.]{0,30})"),
    ("UART_CUR", rf"baud=(?P<baud>{UINT}) data=(?P<data>[5-8]) stop=(?P<stop>[1-3]) parity=(?P<parity>[0-2]) flow=(?P<flow>[0-3])|baud=(?P<missing>NONE)"),
    ("WIFI", rf"ok=(?P<ok>[01]) code=(?P<code>[1-4]|NONE) ms=(?P<ms>{UINT})"),
    ("WIFI_SIGNAL", r"channel=(?P<channel>[0-9]{1,2}) rssi=(?P<rssi>-?[0-9]{1,3})"),
    ("IPV4", r"ready=(?P<ready>[01])"),
    ("NEGOTIATE", rf"target=(?P<target>{UINT}) result=(?P<result>OK|NO_REPLY|NO_SWITCH|MISMATCH|RESYNC_FAIL) actual=(?P<actual>{UINT}|NONE)"),
    ("STRESS", rf"rate=(?P<rate>{UINT}) n=(?P<n>{UINT}) fail=(?P<fail>{UINT}) uart_err=(?P<uart_err>{UINT}) rx_high=(?P<rx_high>{UINT}) ms=(?P<ms>{UINT})"),
    ("RESTORE", r"result=(?P<result>OK|FAIL)"),
    ("END", rf"result=(?P<result>PASS|BLOCKED) reason=(?P<reason>NONE|NEED_POWER_CYCLE|STOP|TIMEOUT|AT|GMR|UART_CUR|CONFIG|NEGOTIATE|WIFI|IPV4|STRESS) uart_err=(?P<uart_err>{UINT})"),
]
PRE_LINES = {tag: re.compile(pattern) for tag, pattern in FIELDS}
PRE_ORDER = [tag for tag, _ in FIELDS]


def parse_line(line):
    prefix, _, payload = line.partition(" ")
    tag, _, fields = payload.partition(" ")
    if prefix != "PRE" or tag not in PRE_LINES:
        return None
    match = PRE_LINES[tag].fullmatch(fields)
    if not match:
        return None
    data = {}
    for name, value in match.groupdict().items():
        if value is None:
            continue
        data["baud" if name == "missing" else name] = int(value) if name != "ver" and value.lstrip("-").isdigit() else value
    return tag, data


def complete(records, target):
    order = [tag for tag in PRE_ORDER if tag != "WIFI_SIGNAL" or tag in records]
    if list(records) != order:
        return False
    begin, wifi, neg, stress, restore, end = (
        records[tag] for tag in ("BEGIN", "WIFI", "NEGOTIATE", "STRESS", "RESTORE", "END")
    )
    if (begin["target"] != target or neg["target"] != target or begin["boot_ms"] >= PREP_S * 1000
            or stress["rate"] not in COMMANDS or not 0 <= stress["fail"] <= stress["n"] <= 50
            or stress["rx_high"] > 8191 or stress["ms"] > 60000 or wifi["ms"] > 20000
            or (wifi["ok"] and wifi["code"] != "NONE")
            or (not wifi["ok"] and records["IPV4"]["ready"])
            or (neg["result"] == "OK" and (neg["actual"] == "NONE" or stress["rate"] != target))
            or (neg["result"] != "OK" and stress["n"])
            or (restore["result"] == "FAIL") != (end["reason"] == "NEED_POWER_CYCLE")
            or (end["result"] == "PASS") != (end["reason"] == "NONE")):
        return False
    signal = records.get("WIFI_SIGNAL")
    if signal and (not wifi["ok"] or not 1 <= signal["channel"] <= 14 or not -127 <= signal["rssi"] <= 0):
        return False
    return end["result"] != "PASS" or (
        records["AT"]["ok"] and records["GMR"]["ver"] != "NONE" and records["UART_CUR"]["baud"] != "NONE"
        and wifi["ok"] and records["IPV4"]["ready"] and neg["result"] == "OK" and restore["result"] == "OK"
        and stress["n"] == 50 and not stress["fail"] and not stress["uart_err"]
    )


def capture(job, device, target, image_sha256):
    protected(job, False)
    if any(job.iterdir()):
        raise ValueError("PRE_NEW_TRANSACTION_REQUIRED")
    transaction = uuid.uuid4().hex
    records = {}
    raw_path = job / "C-uart-private.bin"
    reason, result = "POWER_NOT_CONFIRMED", "BLOCKED"
    sent = False
    port = serial.Serial(port=None, baudrate=115200, timeout=.1, write_timeout=1)
    port.dtr = port.rts = False
    port.port = device
    raw = raw_path.open("xb")
    try:
        with raw:
            mark(job, "HOST_READY", transaction_id=transaction, image_sha256=image_sha256, target=target)
            gate = time.monotonic() + OPERATOR_READY_S
            while not (job / "POWER_ALLOWED").is_file():
                if (job / "ABORT").exists() or time.monotonic() >= gate:
                    break
                time.sleep(.05)
            else:
                power = time.monotonic()
                ready, end = power + PREP_S, power + MAX_POWER_S
                reason = "BOOT_NOT_CONFIRMED"
                while not port.is_open and time.monotonic() < ready and not (job / "ABORT").exists():
                    try:
                        port.open()
                    except serial.SerialException:
                        time.sleep(.1)
                partial, oversized = b"", False
                while port.is_open and time.monotonic() < (end if sent else ready):
                    if (job / "ABORT").exists():
                        reason = "OPERATOR_ABORT"
                        break
                    part = port.read_until(expected=b"\n", size=512)
                    if not part:
                        continue
                    raw.write(part)
                    raw.flush()
                    partial = b"" if oversized else partial + part
                    oversized |= len(partial) > 512
                    if not part.endswith(b"\n"):
                        if oversized:
                            partial = b""
                        continue
                    line = "" if oversized else partial.rstrip(b"\r\n").decode("ascii", errors="replace")
                    partial, oversized = b"", False
                    if line == BOOT_BANNER:
                        if sent:
                            reason = "UNEXPECTED_BOOT"
                            break
                        if time.monotonic() >= ready or (job / "ABORT").exists():
                            break
                        mark(job, "PRE_SENT", target=target)
                        sent = True
                        reason = "PRE_END_NOT_CONFIRMED"
                        command = COMMANDS[target]
                        if port.write(command) != len(command):
                            reason = "UART_SHORT_WRITE"
                            break
                    elif sent and line.startswith("PRE "):
                        parsed = parse_line(line)
                        if not parsed or parsed[0] in records:
                            reason = "PRE_INVALID_RECEIPT"
                            break
                        tag, data = parsed
                        records[tag] = data
                        if tag == "END":
                            if complete(records, target):
                                result, reason = data["result"], data["reason"]
                            else:
                                reason = "PRE_INVALID_RECEIPT"
                            break
                    elif line.startswith("B5 STOPPED"):
                        reason = "C_STOPPED"
                        break
    except serial.SerialException:
        reason, result = "SERIAL_ERROR", "BLOCKED"
    finally:
        if port.is_open:
            try:
                port.close()
            except serial.SerialException:
                reason, result = "SERIAL_CLOSE_ERROR", "BLOCKED"
        with raw_path.open("rb") as raw:
            digest = hashlib.file_digest(raw, "sha256").hexdigest()
        code = 0 if result == "PASS" else 2
        public = dict(transaction_id=transaction, image_sha256=image_sha256, target=target,
                      boot_ms=records.get("BEGIN", {}).get("boot_ms"), records=records,
                      result=result, reason=reason, native_exit=code, sent=sent,
                      raw_sha256=digest, power_off="PENDING",
                      tool=dict(python=platform.python_version(), pyserial=serial.VERSION,
                                script_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()))
        with (job / "PRE-RESULT-public.json").open("x", encoding="utf-8") as output:
            json.dump(public, output, indent=2)
            output.write("\n")
    return code


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--job", type=Path, required=True)
    parser.add_argument("--port", default="COM15")
    parser.add_argument("--target", type=int, choices=COMMANDS, default=115200)
    parser.add_argument("--image-sha256", required=True)
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args()
    if not re.fullmatch("[0-9a-f]{64}", args.image_sha256):
        parser.error("--image-sha256 requires a lowercase SHA-256")
    if args.execute:
        return capture(args.job, args.port, args.target, args.image_sha256)
    print(json.dumps(dict(execute=False, target=args.target, max_power_s=MAX_POWER_S)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
