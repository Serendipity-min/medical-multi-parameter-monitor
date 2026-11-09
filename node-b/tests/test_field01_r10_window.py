import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from field01_r10_window import BOOT_BANNER, STOP_BANNER, Gate


def test_fresh_reset_binding_and_one_start():
    g = Gate(100)
    g.observe(BOOT_BANNER, 101)
    assert not g.can_start(True, 102)
    g.cue = 104
    g.observe(BOOT_BANNER, 103)
    assert not g.can_start(True, 104)
    g.observe(BOOT_BANNER, 105)
    assert not g.can_start(False, 106)
    assert g.can_start(True, 106)
    g.sent = True
    assert not g.can_start(True, 107)
    g.observe("FIELD01 T0", 107)
    assert g.t0 is None
    g.observe("FIELD01 START_ACCEPTED", 108)
    g.observe("FIELD01 T0", 109)
    g.observe(STOP_BANNER, 259)
    g.observe("B5 STOP_STATE tick=158000 reason=10 phase=0", 259.1)
    assert (g.t0, g.stopped, g.stop_reason) == (109, 259, 10)


def test_expired_boot_or_power_reserve():
    g = Gate(100)
    g.cue = 101
    g.observe(BOOT_BANNER, 102)
    assert not g.can_start(True, 147)
    g = Gate(100)
    g.cue = 148
    g.observe(BOOT_BANNER, 149)
    assert not g.can_start(True, 150)


def test_extended_power_keeps_boot_deadline_and_shutdown_reserve():
    g = Gate(100, max_power_s=240)
    assert g.end == 330
    g.cue = 126
    g.observe(BOOT_BANNER, 127)
    assert g.can_start(True, 171)
    assert not g.can_start(True, 172)


def test_repeated_boot_and_can_uart_guards():
    g = Gate(100)
    g.cue = 101
    g.observe(BOOT_BANNER, 102)
    g.sent = True
    g.observe(BOOT_BANNER, 103)
    assert g.fault == "UNEXPECTED_RESET"
    g.fault = None
    g.observe("B5 DIAG uart_err=20", 110)
    g.observe("B5 DIAG uart_err=24", 111)
    assert g.fault is None
    g.observe("B5 DIAG uart_err=25", 112)
    assert g.fault == "UART_ERROR_GROWTH"
    g.fault = None
    for count in range(4):
        g.observe(f"FIELD01 CAN bus=0 busoff=0 overflow=0 esr={count << 16}", 113 + count)
    assert g.fault == "CAN_ERROR_GROWTH"
    g.observe("FIELD01 CAN bus=1 busoff=1 overflow=0 esr=0", 120)
    assert g.fault == "CAN_BUSOFF_OR_OVERFLOW"
