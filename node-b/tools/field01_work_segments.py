"""从 FIELD01 串口原件和逐秒到达表生成工作段、全窗统计。"""

import argparse
import csv
import json
from pathlib import Path
import re


WORK_MS = 142_000
FULL_MS = 150_000
STREAM_COUNT = 12


def summarize(lines, arrivals):
    if [int(row["seconds_from_t0"]) for row in arrivals] != list(range(FULL_MS // 1000)):
        raise ValueError("ARRIVAL_SECONDS_REQUIRE_0_TO_149")
    counts = [int(row["total"]) for row in arrivals]
    if min(counts) < 0:
        raise ValueError("NEGATIVE_ARRIVALS")

    t0 = stop = cut = None
    queues, flows, diag = {}, {}, []
    for line in lines:
        fields = {name: int(value) for name, value in re.findall(r"\b(\w+)=(\d+)", line)}
        if line.startswith("FIELD01 AT ") and t0 is None:
            t0 = fields["tick"] - fields["elapsed"]
        elif line.startswith("B5 STOP_STATE "):
            stop = fields
        elif line.startswith("FIELD01 WORK_CUT "):
            if cut is not None:
                raise ValueError("DUPLICATE_WORK_CUT")
            cut = fields
        elif line.startswith("FIELD01 QUEUE "):
            queues[fields["tick"]] = fields
        elif line.startswith("FIELD01 FLOW "):
            flows.setdefault(fields["tick"], {}).update(
                (int(stream), int(enqueued)) for stream, enqueued in re.findall(r" (\d+)=(\d+)/", line)
            )
        elif line.startswith("B5 DIAG ") and "svc_max_cyc" in fields:
            diag.append(fields)

    if t0 is None or stop is None or stop["reason"] != 10 or stop["tick"] - t0 != FULL_MS:
        raise ValueError("NEED_FULL_FIRMWARE_TIMER_WINDOW")
    if cut is not None and (cut["tick"] - t0 != cut["elapsed"] or not WORK_MS <= cut["elapsed"] < FULL_MS):
        raise ValueError("WORK_CUT_OUTSIDE_BOUNDARY")
    totals = sorted((tick, sum(streams.values())) for tick, streams in flows.items()
                    if set(streams) == set(range(STREAM_COUNT)))
    if not totals or totals[-1][0] < stop["tick"] or max(queues, default=0) < stop["tick"]:
        raise ValueError("NEED_FINAL_FLOW_AND_QUEUE")
    base = cut["base"] if cut else totals[0][1]
    early_ticks = [tick for tick in queues if 140_000 <= tick - t0 < WORK_MS]
    near_140 = queues[min(early_ticks)] if early_ticks else None
    flow_by_tick = dict(totals)
    at_140 = None
    if near_140:
        tick = near_140["tick"]
        entered = flow_by_tick.get(tick)
        at_140 = dict(elapsed_ms=tick - t0, queue=near_140, enqueued=entered - base if entered is not None else None)

    def window(ms, queue, entered):
        received = sum(counts[:ms // 1000])
        return dict(duration_ms=ms, broker_batches=received, broker_batches_per_s=received * 1000 / ms,
                    enqueued=entered, delivery_ratio=received / entered if entered else None,
                    queue_high=queue["high"] if queue else None,
                    overflow=queue["overflow"] if queue else None,
                    replaced=queue["replaced"] if queue else None, dropped=queue["drop"] if queue else None)

    # 晚于边界的累计入队是上界，实收/入队是下界；旧窗口没有这项快照。
    working = window(WORK_MS, cut, cut["enqueued"] - base if cut else None)
    working["cut_ms"] = cut["elapsed"] if cut else None
    working["delivery_ratio_is_lower_bound"] = bool(cut and cut["elapsed"] > WORK_MS)
    if cut:
        working["tx_cycles_per_byte"] = cut["tx_cyc"] / cut["tx_b"] if cut["tx_b"] else None
        working["tx_cpu_fraction"] = cut["tx_cyc"] / (cut["elapsed"] * 8_000)
    full = window(FULL_MS, queues[max(queues)], totals[-1][1] - base)
    full["enqueue_snapshot_ms"] = totals[-1][0] - t0

    peak = None
    if diag:
        index = max(range(len(diag)), key=lambda i: diag[i]["svc_max_cyc"])
        peak = dict(cycles=diag[index]["svc_max_cyc"],
                    previous_snapshot_ms=diag[index - 1]["tick"] - t0 if index else None,
                    first_observed_ms=diag[index]["tick"] - t0)
    return dict(working=working, full=full, drain_broker_batches=full["broker_batches"] - working["broker_batches"],
                at_140_s=at_140, service_peak=peak)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--uart", type=Path, required=True)
    parser.add_argument("--arrivals", type=Path, required=True)
    parser.add_argument("--out-csv", type=Path, required=True)
    args = parser.parse_args()
    with args.arrivals.open(encoding="utf-8-sig", newline="") as stream:
        rows = list(csv.DictReader(stream))
    with args.uart.open(encoding="utf-8-sig") as stream:
        summary = summarize((json.loads(line)["line"] for line in stream), rows)
    with args.out_csv.open("x", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=[*rows[0], "working_arrivals", "full_arrivals"], lineterminator="\n")
        writer.writeheader()
        for second, row in enumerate(rows):
            writer.writerow(dict(row, working_arrivals=row["total"] if second * 1000 < WORK_MS else "",
                                 full_arrivals=row["total"]))
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
