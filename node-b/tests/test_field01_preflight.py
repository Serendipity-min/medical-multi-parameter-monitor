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
    b"PRE NEGOTIATE target=230400 result=OK actual=230400\n",
    b"PRE STRESS rate=230400 n=50 fail=0 uart_err=0 rx_high=5 ms=500\n",
    b"PRE RESTORE result=OK\n",
    b"PRE END result=PASS reason=NONE uart_err=0\n",
]
BANNER = pre.BOOT_BANNER.encode() + b"\r\n"


@pytest.fixture
def run_pre(tmp_path, monkeypatch):
    def run(lines, *, short=False, allow=True):
        now = 0.0
        writes = []
        original_mark = pre.mark

        def tick(seconds):
            nonlocal now
            now += seconds

        def mark(job, name, **fields):
            original_mark(job, name, **fields)
            if name == "HOST_READY" and allow:
                (job / "POWER_ALLOWED").touch()

        class Port:
            is_open = False
            data = deque(lines)

            def open(self):
                assert not self.dtr and not self.rts
                self.is_open = True

            def close(self):
                self.is_open = False

            def read_until(self, *, expected, size):
                assert expected == b"\n" and size == 512
                tick(.1 if self.data else 30)
                return self.data.popleft() if self.data else b""

            def write(self, command):
                assert (tmp_path / "PRE_SENT.json").is_file()
                writes.append(command)
                return len(command) - int(short)

        monkeypatch.setattr(pre, "protected", lambda path, synthetic: path)
        monkeypatch.setattr(pre, "mark", mark)
        monkeypatch.setattr(pre.time, "monotonic", lambda: now)
        monkeypatch.setattr(pre.time, "sleep", tick)
        monkeypatch.setattr(pre.serial, "Serial", lambda **kwargs: Port())
        rc = pre.capture(tmp_path, "COM-SYNTHETIC", 230400, "a" * 64)
        public = (tmp_path / "PRE-RESULT-public.json").read_text()
        assert "synthetic-secret" not in public and "192.0.2.1" not in public
        receipt = json.loads(public)
        assert receipt["native_exit"] == rc and receipt["power_off"] == "PENDING"
        return rc, writes, receipt["reason"]

    return run


def test_success_split_banner_and_private_noise(run_pre):
    lines = [b"synthetic-secret 192.0.2.1\n", b"x" * 512, b"x" * 50 + b"\n",
             BANNER[:14], BANNER[14:], *BASE]
    assert run_pre(lines) == (0, [b"FIELD01 PRE 230\n"], "NONE")


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
