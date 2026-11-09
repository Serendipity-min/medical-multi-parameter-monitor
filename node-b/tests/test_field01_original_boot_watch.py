import json
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import field01_original_boot_watch as watch


@pytest.mark.parametrize(("lines", "allowed", "expected"), [
    ([watch.BOOT_BANNER[:10], watch.BOOT_BANNER[10:] + b"\r\n"], True, "ORIGINAL_BOOT_BANNER_SEEN"),
    ([watch.BOOT_BANNER + b" extra\n"], True, "BOOT_BANNER_NOT_SEEN"),
    ([b"FIELD01 DISARMED C_ONLY_INSTALL TLS_28895 NO_AUTORETRY\r\n"], True, "BOOT_BANNER_NOT_SEEN"),
    ([], False, "POWER_NOT_CONFIRMED"),
])
def test_original_boot_is_passive_and_bounded(tmp_path, monkeypatch, lines, allowed, expected):
    now = 0.0
    fragments = iter(lines)

    def tick(seconds):
        nonlocal now
        now += seconds

    def mark(job, name, **fields):
        assert name == "HOST_READY" and fields["max_physical_power_s"] == 60
        if allowed:
            (job / "POWER_ALLOWED").touch()

    class Port:
        is_open = False

        def open(self):
            assert not self.dtr and not self.rts
            self.is_open = True

        def read_until(self, **kwargs):
            tick(.1)
            return next(fragments, b"")

        def close(self):
            self.is_open = False

    monkeypatch.setattr(watch, "protected", lambda path, synthetic: path)
    monkeypatch.setattr(watch, "mark", mark)
    monkeypatch.setattr(watch.time, "monotonic", lambda: now)
    monkeypatch.setattr(watch.time, "sleep", tick)
    monkeypatch.setattr(watch.serial, "Serial", lambda **kwargs: Port())
    rc = watch.capture(tmp_path, "COM-TEST")
    result = json.loads((tmp_path / "ORIGINAL-BOOT-RESULT-public.json").read_text())
    assert result["reason"] == expected and result["power_off"] == "PENDING"
    assert rc == (0 if expected == "ORIGINAL_BOOT_BANNER_SEEN" else 2)
    assert not allowed or now <= 60
