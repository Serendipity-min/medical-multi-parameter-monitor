import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from r18_s1_capture import StopGate


def test_recorder_accepts_expected_recovery_and_flags_reset():
    gate = StopGate()
    assert gate.observe("B5 DIAG tick=5 uart_err=0 esr=0 overflow=0") is None
    assert gate.observe("GW PASS_HARD_RESET") is None
    assert gate.observe("GW PASS_HARD_RESET_OK") is None
    assert gate.observe("B5 DIAG tick=60000 uart_err=0 esr=0 overflow=0") is None
    assert gate.observe("B5 DIAG tick=5 uart_err=0 esr=0 overflow=0") == "UNEXPECTED_RESET"


def test_recorder_retains_r18_stops():
    gate = StopGate()
    assert gate.observe("GW PASS_BOOT_RESET_LOCKED") == "FIRMWARE_STOP"
    assert gate.observe("GW FAIL LINK") == "FIRMWARE_STOP"
    assert gate.observe("GW PASS_HARD_RESET_UNCONFIRMED") is None
    assert gate.observe("GW PASS_HARD_RESET_UNCONFIRMED") == "PERSISTENT_HARD_RESET_FAILURE"
    assert gate.observe("ABC A_CAN esr=4 overflow=0") == "CAN_BUSOFF_OR_OVERFLOW"
    assert gate.observe("B5 DIAG tick=5 uart_err=2 esr=0 overflow=0") is None
    assert gate.observe("B5 DIAG tick=9 uart_err=7 esr=0 overflow=0") == "UART_ERROR_GROWTH"
