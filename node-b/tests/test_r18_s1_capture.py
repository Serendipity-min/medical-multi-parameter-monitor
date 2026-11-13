import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from r18_s1_capture import StopGate
import r18_s1_capture as recorder


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


def test_recorder_detects_boot_stop_without_banner():
    assert StopGate().observe(
        "B5 DIAG tick=5000 uart_err=225 stop=1 boot_escape=0 boot_at=0"
    ) == "FIRMWARE_STOP"


def test_recorder_uses_confirmed_r19_boot_baseline_after_summary_expires():
    gate = StopGate()
    assert gate.observe("B5 DIAG tick=0 uart_err=8 boot_at=0 boot_uart_err0=0") is None
    assert gate.observe("B5 DIAG tick=5000 uart_err=225 boot_at=1 boot_uart_err0=225") is None
    assert gate.observe("B5 DIAG tick=60000 uart_err=226") == "UART_ERROR_GROWTH"
    assert StopGate().observe(
        "B5 DIAG tick=5000 uart_err=226 boot_at=1 boot_uart_err0=225"
    ) == "UART_ERROR_GROWTH"
    assert StopGate().observe("GW PASS_BOOT_UART_STORM") == "FIRMWARE_STOP"
    assert StopGate().observe("GW PASS_BOOT_RX_TIMEOUT") == "FIRMWARE_STOP"


def test_recorder_follows_firmware_rebase_but_stops_on_later_increment():
    gate = StopGate()
    assert gate.observe("B5 DIAG tick=5000 uart_err=222 boot_at=1 boot_uart_err0=222") is None
    assert gate.observe("GW PASS_HARD_RESET") is None
    assert gate.observe("B5 DIAG tick=10000 uart_err=223 boot_at=1 boot_uart_err0=222") is None
    assert gate.observe("GW PASS_RESET_UART_REBASE before=222 after=223") is None
    assert gate.observe("GW PASS_HARD_RESET_OK") is None
    assert gate.observe("B5 DIAG tick=15000 uart_err=223 boot_at=1 boot_uart_err0=222") is None
    assert gate.observe("B5 DIAG tick=20000 uart_err=224") == "UART_ERROR_GROWTH"


def test_recorder_unconfirmed_reset_leaves_old_baseline():
    gate = StopGate()
    assert gate.observe("B5 DIAG tick=5000 uart_err=222 boot_at=1 boot_uart_err0=222") is None
    assert gate.observe("GW PASS_HARD_RESET") is None
    assert gate.observe("GW PASS_HARD_RESET_UNCONFIRMED") is None
    assert gate.observe("B5 DIAG tick=10000 uart_err=223") == "UART_ERROR_GROWTH"
    assert gate.observe("GW PASS_LOCAL_FAULT baseline=222 total=223 ore=0 ne=0 fe=1 overflow=0") == "FIRMWARE_STOP"


def test_absolute_deadline_caps_capture_after_late_port_open(tmp_path, monkeypatch):
    now = [0.0]
    markers = {}

    class Port:
        is_open = False

        def open(self):
            self.is_open = True

        def read_until(self, *_):
            now[0] += .1
            return b"B5 DIAG tick=5 uart_err=0\r\n"

        def close(self):
            self.is_open = False

    (tmp_path / "ARM").touch()
    monkeypatch.setattr(recorder, "protected", lambda *_: None)
    monkeypatch.setattr(recorder, "present", lambda _: now[0] >= .7)
    monkeypatch.setattr(recorder.serial, "Serial", lambda **_: Port())
    monkeypatch.setattr(recorder.time, "monotonic", lambda: now[0])
    monkeypatch.setattr(recorder.time, "sleep", lambda seconds: now.__setitem__(0, now[0] + seconds))
    monkeypatch.setattr(recorder, "mark", lambda _, name, **data: markers.update({name: data}))
    assert recorder.capture(tmp_path, "COM15", deadline=1.0) == 2
    assert "UART_OPEN" in markers
    assert markers["HOST_ENDED"]["reason"] == "HOST_TIME_LIMIT"
    assert 1.0 <= now[0] < 1.101


def test_r40_recorder_can_run_past_default_but_honors_absolute_deadline(tmp_path, monkeypatch):
    now = [0]
    markers = {}

    class Port:
        is_open = False

        def open(self):
            self.is_open = True

        def read_until(self, *_):
            now[0] += 100
            return b"B5 DIAG tick=5 uart_err=0\r\n"

        def close(self):
            self.is_open = False

    (tmp_path / "ARM").touch()
    monkeypatch.setattr(recorder, "protected", lambda *_: None)
    monkeypatch.setattr(recorder, "present", lambda _: "HOST_READY" in markers)
    monkeypatch.setattr(recorder.serial, "Serial", lambda **_: Port())
    monkeypatch.setattr(recorder.time, "monotonic", lambda: now[0])
    monkeypatch.setattr(recorder, "mark", lambda _, name, **data: markers.update({name: data}))
    assert recorder.capture(tmp_path, "COM15", deadline=2500, capture_seconds=2700) == 2
    assert markers["HOST_ENDED"]["reason"] == "HOST_TIME_LIMIT"
    assert now[0] == 2500
