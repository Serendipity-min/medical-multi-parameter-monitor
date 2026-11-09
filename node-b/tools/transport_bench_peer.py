"""R8 对端 MQTT 观察与独立复算。record 只在批次放行后使用，verify 只读本地输入。"""
import argparse
from collections import defaultdict
from decimal import Decimal
import json
import os
from pathlib import Path
import re
import time

ROOT_TOPIC = "mpm/bench/v1/GW-B5-001"
DURATION_MS = 120_000
T0 = re.compile(r"^BENCH T0 mode=([NP](?:115|230)) tick=\d+ session=(can-\d+-\d+) utc=(\d+)$")
ACK = re.compile(r"^BENCH ACK node=(\d+) stream=(\d+) seq=(\d+) replay=([01]) ms=(\d+)$")
STREAMS = {
    (2, 4): ("ecg", "mV", 400, 250, 100, 1103, 1000),
    (2, 6): ("resp", "relative", 1000, 50, 50, 10000, 1000000),
    (1, 0): ("ppg", "relative", 1000, 50, 50, 1230000, 1000000),
    (1, 1): ("spo2", "%", 1000, 0, 1, 9750, 100),
    (1, 2): ("pr", "bpm", 1000, 0, 1, 7200, 100),
    (2, 5): ("hr", "bpm", 1000, 0, 1, 6000, 100),
    (2, 7): ("rr", "breaths/min", 1000, 0, 1, 1800, 100),
    (4, 8): ("temp", "degC", 1000, 0, 1, 2450, 100),
    (3, 11): ("status", "state", 5000, 0, 1, 1, 1),
    **{(node, 9): ("status", "state", 5000, 0, 1, 1, 1) for node in (1, 2, 4, 5)},
    (5, 3): ("nibp", "mmHg", 0, 0, 2, 1180, 10),
}


def stream_topic(key, replay=False):
    node, stream = key
    if stream == 11:
        return ROOT_TOPIC + "/status"
    node_topic = f"{ROOT_TOPIC}/NODE-{chr(64 + node)}"
    if stream == 9:
        return node_topic + "/status"
    return f"{node_topic}/{'replay' if replay else 'telemetry'}/{STREAMS[key][0]}"


def expected(key, seq, session, start):
    name, unit, period, rate, count, value, scale = STREAMS[key]
    tick = seq * period if period else 2000
    limit = DURATION_MS // period if period else 1
    if not 1 <= seq <= limit:
        return None
    result = {"timestamp": start + tick, "seq": seq, "session_id": session,
              "validity": "VALID", "source": "MOCK", "synthetic": True, "unit": unit}
    if rate:
        samples = [(value + i + seq % 10) * (-1 if name != "ppg" and i % 2 else 1)
                   for i in range(count)]
        result.update(value=None, sample_rate=rate, samples=[Decimal(x) / scale for x in samples])
    elif name == "nibp":
        result["value"] = [Decimal(value) / scale, Decimal(760) / scale]
    elif name == "status":
        result["value"] = "ONLINE"
    else:
        result["value"] = Decimal(value) / scale
    return result


def verify(capture, serial):
    anchors = [m.groups() for line in serial.splitlines() if (m := T0.fullmatch(line))]
    if len(anchors) != 1:
        raise ValueError("BENCH_T0_COUNT")
    mode, session, start = anchors[0]
    start = int(start)
    topics = {stream_topic(key): (key, False) for key in STREAMS}
    topics.update({stream_topic(key, True): (key, True) for key in STREAMS if key[1] not in (9, 11)})
    live, replayed, arrivals, acks = (defaultdict(dict) for _ in range(4))
    errors = stale = 0
    for row in capture:
        topic = topics.get(row["topic"])
        if topic is None:
            errors += 1
            continue
        key, replay = topic
        try:
            payload = json.loads(row["payload"], parse_float=Decimal)
        except json.JSONDecodeError:
            errors += 1
            continue
        if not isinstance(payload, dict):
            errors += 1
            continue
        # 忽略 Broker 订阅时投递的旧保留值，以及本镜像的离线遗嘱。
        if row["retained"] and payload.get("session_id") != session:
            stale += 1
            continue
        if key == (3, 11) and payload == {
            "timestamp": 0, "seq": 0, "session_id": "can-0-0", "validity": "OFFLINE",
            "source": "MOCK", "synthetic": True, "unit": "state", "value": "OFFLINE",
        }:
            continue
        seq = payload.get("seq")
        wanted = expected(key, seq, session, start) if type(seq) is int else None
        qos = int(not STREAMS[key][3] or replay)
        if wanted is None or payload.get("synthetic") is not True or payload != wanted or row["qos"] != qos:
            errors += 1
            continue
        table = replayed if replay else live
        if seq in table[key]:
            table[key][seq] += 1
        else:
            table[key][seq] = 1
            if not replay:
                arrivals[key][seq] = (int(row["mono_ns"]), int(row["utc_ms"]))
    for line in serial.splitlines():
        if m := ACK.fullmatch(line):
            node, stream, seq, replay, ms = map(int, m.groups())
            acks[(node, stream)][(seq, replay)] = ms
    diag = []
    for line in serial.splitlines():
        if line.startswith("B5 DIAG "):
            diag.append({key: int(value) for key, value in re.findall(r"(\w+)=(\d+)", line)})
    produced_ms = min(DURATION_MS, max((d["offered_ms"] for d in diag), default=0))
    streams = {}
    for key, spec in STREAMS.items():
        name, _, period, *_ = spec
        offered = produced_ms // period if period else int(produced_ms >= 2000)
        received = live[key]
        replay = replayed[key]
        times = sorted(a[0] for a in arrivals[key].values())
        max_gap = max((b - a for a, b in zip(times, times[1:])), default=0) / 1_000_000
        missing = sorted(set(range(1, offered + 1)) - received.keys())
        ack = sorted(acks[key].values())
        late = sum(utc - expected(key, seq, session, start)["timestamp"] >=
                   (90000 if name == "nibp" else 5000)
                   for seq, (_, utc) in arrivals[key].items())
        streams[f"{key[0]}/{name}"] = {
            "offered": offered, "live": len(received), "replayed": len(replay),
            "delivered_including_replay": len(received.keys() | replay.keys()),
            "live_missing_seq": missing, "duplicates": sum(received.values()) - len(received),
            "max_gap_ms": max_gap, "late_by_observer_utc": late,
            "publisher_puback_n": len(ack), "publisher_puback_max_ms": max(ack, default=None),
        }
    return {"mode": mode, "complete_source_window": produced_ms == DURATION_MS,
            "payload_errors": errors, "old_retained": stale, "streams": streams,
            "last_diagnostics": diag[-12:]}


def record(config_path, output, seconds, ready):
    import paho.mqtt.client as mqtt

    if os.name == "posix" and config_path.stat().st_mode & 0o077:
        raise ValueError("CONFIG_FILE_PERMISSIONS")
    cfg = json.loads(config_path.read_text(encoding="utf-8"))
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=cfg["observer_client_id"],
                         protocol=mqtt.MQTTv311, reconnect_on_failure=False)
    client.username_pw_set(cfg["username"], cfg["password"])
    client.tls_set(ca_certs=cfg["cafile"])
    def on_connect(client, _userdata, _flags, reason, _properties):
        if not reason.is_failure:
            client.subscribe(ROOT_TOPIC + "/#", qos=1)
    def on_subscribe(_client, _userdata, _mid, reasons, _properties):
        if not reasons or reasons[0].is_failure or reasons[0].value != 1:
            raise ValueError("OBSERVER_SUBACK")
        with ready.open("x", encoding="utf-8") as f:
            f.write("READY\n")
    descriptor = os.open(output, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "w", encoding="utf-8") as out:
        def on_message(_client, _userdata, msg):
            row = {"mono_ns": time.monotonic_ns(), "utc_ms": time.time_ns() // 1_000_000,
                   "topic": msg.topic, "qos": msg.qos, "retained": msg.retain,
                   "payload": msg.payload.decode("utf-8", errors="replace")}
            out.write(json.dumps(row) + "\n")
            out.flush()
        client.on_connect, client.on_subscribe, client.on_message = on_connect, on_subscribe, on_message
        try:
            client.connect(cfg["host"], 28895, keepalive=15)
            until = time.monotonic() + seconds
            while time.monotonic() < until:
                if client.loop(timeout=0.25) != mqtt.MQTT_ERR_SUCCESS:
                    raise ValueError("OBSERVER_CONNECTION_LOST")
        except OSError:
            raise ValueError("OBSERVER_IO_FAILED") from None
        finally:
            client.disconnect()
    if not ready.exists():
        raise ValueError("OBSERVER_NOT_READY")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    r = sub.add_parser("record")
    for name in ("config", "capture", "ready"):
        r.add_argument(name, type=Path)
    r.add_argument("--seconds", type=int, required=True)
    v = sub.add_parser("verify")
    for name in ("capture", "serial", "report"):
        v.add_argument(name, type=Path)
    args = parser.parse_args()
    if args.command == "record":
        if not 1 <= args.seconds <= 14400:
            parser.error("--seconds must be in [1, 14400]")
        record(args.config, args.capture, args.seconds, args.ready)
        return 0
    with args.capture.open(encoding="utf-8") as f:
        result = verify((json.loads(line) for line in f), args.serial.read_text(encoding="utf-8"))
    with args.report.open("x", encoding="utf-8") as f:
        json.dump(result, f, indent=2)
        f.write("\n")
    return int(bool(result["payload_errors"]))


if __name__ == "__main__":
    raise SystemExit(main())
