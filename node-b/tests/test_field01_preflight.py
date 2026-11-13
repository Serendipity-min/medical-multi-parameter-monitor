import json
import sys
from collections import deque
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import field01_preflight as pre

BASE = [
    b"PRE BEGIN boot_ms=100 target=230400\n",
    b"PRE AT ok=1\n",
    b"PRE GMR ver=2.3.0.0\n",
    b"PRE UART_CUR baud=115200 data=8 stop=1 parity=0 flow=0\n",
    b"PRE WIFI ok=1 code=NONE ms=200\n",
    b"PRE WIFI_SIGNAL channel=11 rssi=-29\n",
    b"PRE IPV4 ready=1\n",
    b"PRE RETIME reason=OK\n",
    b"PRE NEGOTIATE target=230400 result=OK actual=230400\n",
    b"PRE STRESS rate=230400 n=50 fail=0 uart_err=0 rx_high=5 ms=500\n",
    b"PRE RESTORE result=OK\n",
    b"PRE END result=PASS reason=NONE uart_err=0\n",
]
BANNER = pre.BOOT_BANNER.encode() + b"\r\n"


@pytest.fixture
def run_pre(tmp_path, monkeypatch):
    def run(lines, *, short=False, allow=True, no_banner=False, trigger=True,
            after_write=(), evidence=None, target=230400):
        now = 0.0
        writes = []
        flushes = []
        original_mark = pre.mark

        def tick(seconds):
            nonlocal now
            now += seconds

        def mark(job, name, **fields):
            original_mark(job, name, **fields)
            if name == "HOST_READY" and allow:
                (job / "POWER_ALLOWED").touch()
                if trigger == "immediate":
                    (job / "PRE_ALLOWED").touch()

        class Port:
            is_open = False
            data = deque(lines)

            def open(self):
                assert not self.dtr and not self.rts
                self.is_open = True

            def close(self):
                self.is_open = False

            def read_all(self):
                buffered = b"".join(self.data)
                self.data.clear()
                return buffered

            def reset_input_buffer(self):
                flushes.append(True)
                self.data.clear()

            def read_until(self, *, expected, size):
                assert expected == b"\n" and size == 512
                tick(.1 if self.data else 30)
                if self.data:
                    return self.data.popleft()
                if no_banner and trigger and not writes:
                    (tmp_path / "PRE_ALLOWED").touch()
                return b""

            def write(self, command):
                assert (tmp_path / "PRE_SENT.json").is_file()
                if no_banner:
                    assert flushes == [True]
                writes.append(command)
                self.data.extend(after_write)
                return len(command) - int(short)

        monkeypatch.setattr(pre, "protected", lambda path, synthetic: path)
        monkeypatch.setattr(pre, "mark", mark)
        monkeypatch.setattr(pre.time, "monotonic", lambda: now)
        monkeypatch.setattr(pre.time, "sleep", tick)
        monkeypatch.setattr(pre.serial, "Serial", lambda **kwargs: Port())
        rc = pre.capture(tmp_path, "COM-SYNTHETIC", target, "a" * 64, no_banner=no_banner)
        public = (tmp_path / "PRE-RESULT-public.json").read_text()
        assert "synthetic-secret" not in public and "192.0.2.1" not in public
        receipt = json.loads(public)
        assert receipt["native_exit"] == rc and receipt["power_off"] == "PENDING"
        if evidence is not None:
            assert (receipt["banner_seen"], receipt["bound_by"]) == evidence
        return rc, writes, receipt["reason"]

    return run


def test_success_split_banner_and_private_noise(run_pre):
    lines = [b"synthetic-secret 192.0.2.1\n", b"x" * 512, b"x" * 50 + b"\n",
             BANNER[:14], BANNER[14:], *BASE]
    assert run_pre(lines, evidence=(True, "BANNER")) == (0, [b"FIELD01 PRE 230\n"], "NONE")


@pytest.mark.parametrize(("lines", "short", "expected"), [
    ([], False, "BOOT_NOT_CONFIRMED"),
    ([BANNER, BANNER], False, "UNEXPECTED_BOOT"),
    ([BANNER], True, "UART_SHORT_WRITE"),
    ([BANNER], False, "PRE_END_NOT_CONFIRMED"),
    ([BANNER, BASE[0], BASE[0]], False, "PRE_INVALID_RECEIPT"),
    ([BANNER, b"PRE GMR ver=2.3.0.0 synthetic-secret\n"], False, "PRE_INVALID_RECEIPT"),
    ([BANNER, BASE[-1]], False, "PRE_INVALID_RECEIPT"),
    ([BANNER, *BASE[:-2], b"PRE RESTORE result=FAIL\n",
      b"PRE END result=BLOCKED reason=NEED_POWER_CYCLE uart_err=0\n"], False, "NEED_POWER_CYCLE"),
])
def test_failures_are_one_shot(run_pre, lines, short, expected):
    code, writes, reason = run_pre(lines, short=short)
    assert (code, reason) == (2, expected)
    assert writes == ([b"FIELD01 PRE 230\n"] if lines else [])


def test_waits_for_operator(run_pre):
    assert run_pre([BANNER, *BASE], allow=False) == (2, [], "POWER_NOT_CONFIRMED")


def test_uart_gate_is_clean(run_pre):
    lines = [*BASE[:7], b"PRE NEGOTIATE target=230400 result=MISMATCH actual=115273\n",
             b"PRE STRESS rate=115200 n=0 fail=0 uart_err=0 rx_high=0 ms=0\n",
             b"PRE RESTORE result=OK\n", b"PRE END result=BLOCKED reason=UART_GATE uart_err=0\n"]
    lines[3] = b"PRE UART_CUR baud=115273 data=8 stop=1 parity=0 flow=2\n"
    assert run_pre([BANNER, *lines]) == (2, [b"FIELD01 PRE 230\n"], "UART_GATE")


@pytest.mark.parametrize("reason", ["OK", "TC", "RX_NOT_QUIET", "BRR", "STOP", "DEADLINE"])
def test_retime_parses_only_fixed_enum(reason):
    line = f"PRE RETIME reason={reason}"
    assert pre.parse_line(line) == ("RETIME", {"reason": reason})
    assert pre.parse_line(line + " extra") is None


def test_retime_required_for_candidate_success(run_pre):
    assert run_pre([BANNER, *BASE[:7], *BASE[8:]]) == (2, [b"FIELD01 PRE 230\n"], "PRE_INVALID_RECEIPT")


def test_no_banner_binds_to_fresh_begin(run_pre):
    assert run_pre([], no_banner=True, after_write=BASE, evidence=(False, "BOOT_MS")) == (
        0, [b"FIELD01 PRE 230\n"], "NONE"
    )


def test_no_banner_still_records_banner_before_trigger(run_pre):
    assert run_pre([BANNER], no_banner=True, after_write=BASE, evidence=(True, "BOOT_MS")) == (
        0, [b"FIELD01 PRE 230\n"], "NONE"
    )


def test_no_banner_requires_separate_send_trigger(run_pre):
    assert run_pre([BANNER], no_banner=True, trigger=False, evidence=(True, None)) == (
        2, [], "PRE_NOT_ALLOWED"
    )


@pytest.mark.parametrize(("reply", "short", "expected", "banner_seen", "binding"), [
    ([], False, "PRE_BEGIN_NOT_CONFIRMED", False, None),
    ([BASE[1]], False, "PRE_INVALID_RECEIPT", False, None),
    ([BASE[0].replace(b"100 ", b"45000 "), *BASE[1:]], False, "PRE_INVALID_RECEIPT", False, None),
    ([BASE[0].replace(b"230400", b"500000")], False, "PRE_INVALID_RECEIPT", False, None),
    ([BANNER, *BASE], False, "UNEXPECTED_BOOT", True, None),
    ([BASE[0], BANNER], False, "UNEXPECTED_BOOT", True, "BOOT_MS"),
    ([BASE[0], BASE[0]], False, "PRE_INVALID_RECEIPT", False, "BOOT_MS"),
    (BASE, True, "UART_SHORT_WRITE", False, None),
])
def test_no_banner_stops_after_one_attempt(run_pre, reply, short, expected, banner_seen, binding):
    assert run_pre([], short=short, no_banner=True, after_write=reply, evidence=(banner_seen, binding)) == (
        2, [b"FIELD01 PRE 230\n"], expected
    )


def test_legacy_baseline_without_optional_receipt_lines(run_pre):
    lines = [line.replace(b"230400", b"115200") for line in BASE
             if not line.startswith((b"PRE RETIME", b"PRE WIFI_SIGNAL"))]
    assert run_pre([BANNER, *lines], target=115200, evidence=(True, "BANNER")) == (
        0, [b"FIELD01 PRE\n"], "NONE"
    )


def test_no_banner_clears_stale_reply_and_preserves_queued_banner(run_pre):
    assert run_pre([*BASE, BANNER], no_banner=True, trigger="immediate", after_write=BASE,
                   evidence=(True, "BOOT_MS")) == (0, [b"FIELD01 PRE 230\n"], "NONE")


def test_no_banner_does_not_send_after_queued_stop(run_pre):
    assert run_pre([b"B5 STOPPED NO_AUTOREARM\r\n"], no_banner=True, trigger="immediate",
                   evidence=(False, None)) == (2, [], "C_STOPPED")


def test_no_banner_still_requires_power_gate(run_pre):
    assert run_pre([BANNER], no_banner=True, allow=False, evidence=(False, None)) == (
        2, [], "POWER_NOT_CONFIRMED"
    )
