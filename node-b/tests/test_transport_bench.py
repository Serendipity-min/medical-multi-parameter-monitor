import json
from pathlib import Path
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "node-b/tools"))
from transport_bench_peer import verify


@pytest.fixture(scope="module")
def source(tmp_path_factory):
    path = tmp_path_factory.mktemp("transport-bench")
    exe = path / "bench.exe"
    subprocess.run(["gcc", "-std=c11", "-Wall", "-Wextra", "-Werror", "-DMP_FRAME_MAX_SAMPLES=100",
                    "-DMP_TRANSPORT_BENCH", "-DMP_FIVE_NODE", "-DMP_B5_CLOUD_CANDIDATE",
                    '-DMP_MQTT_GATEWAY_ID="GW-B5-001"', "gateway/b5/test_transport_bench.c",
                    "gateway/data_model/model.c", "-o", str(exe)], cwd=ROOT, check=True)
    text = subprocess.check_output([str(exe)], text=True)
    result = []
    for line in text.splitlines():
        topic, body = line.split("\t", 1)
        payload = json.loads(body)
        result.append({"topic": topic, "payload": body, "retained": False,
                       "mono_ns": (payload["timestamp"] - 1800000000000) * 1_000_000,
                       "utc_ms": payload["timestamp"] + 100,
                       "qos": int("sample_rate" not in payload)})
    return result


SERIAL = """BENCH T0 mode=P230 tick=5000 session=can-1800000000-5000 utc=1800000000000
BENCH ACK node=4 stream=8 seq=1 replay=0 ms=250
B5 DIAG offered_ms=120000 live=0 drop=0 replace=0 late=0
"""


def test_full_capture_independent_verifier(source, tmp_path):
    capture, serial, output = [tmp_path / name for name in ("capture.jsonl", "serial.log", "report.json")]
    capture.write_text("".join(json.dumps(row) + "\n" for row in source), encoding="utf-8")
    serial.write_text(SERIAL, encoding="utf-8")
    subprocess.run([sys.executable, str(ROOT / "node-b/tools/transport_bench_peer.py"),
                    "verify", str(capture), str(serial), str(output)], check=True)
    report = json.loads(output.read_text(encoding="utf-8"))
    assert report["complete_source_window"] and report["payload_errors"] == 0
    assert sum(row["offered"] for row in report["streams"].values()) == 1261
    assert all(row["live"] == row["offered"] and not row["late_by_observer_utc"]
               for row in report["streams"].values())
    assert report["streams"]["4/temp"]["publisher_puback_max_ms"] == 250


def test_corrupt_missing_and_duplicate_capture(source):
    damaged = [{**source[0], "payload": "{"}, source[1], {**source[2], "qos": 1}, *source[3:], source[3]]
    report = verify(damaged, SERIAL)
    assert report["payload_errors"] == 2
    assert report["streams"]["2/ecg"]["live_missing_seq"] == [1]
    assert report["streams"]["2/resp"]["live_missing_seq"] == [1]
    assert report["streams"]["1/ppg"]["duplicates"] == 1


def test_requires_one_boot_anchor(source):
    for serial in ("", SERIAL + SERIAL):
        with pytest.raises(ValueError, match="BENCH_T0_COUNT"):
            verify(source, serial)
