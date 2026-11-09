import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from field01_work_segments import summarize


def test_work_cut_and_tail_use_separate_counters():
    t0 = 1_000
    lines = ["FIELD01 AT tick=1001 elapsed=1"]
    for tick, enqueued, high, dropped in ((1001, 2, 1, 0), (141001, 1402, 5, 0), (151005, 1502, 24, 20)):
        lines.append(f"FIELD01 QUEUE tick={tick} high={high} overflow=0 replaced=0 drop={dropped}")
        flow = " ".join(f"{i}={enqueued if i == 0 else 0}/0" for i in range(12))
        lines.append(f"FIELD01 FLOW tick={tick} {flow}")
    lines.extend(("B5 DIAG tick=141004 svc_max_cyc=48553", "B5 DIAG tick=151006 svc_max_cyc=169670",
                  f"B5 STOP_STATE tick={t0+150000} reason=10"))
    rows = [dict(seconds_from_t0=i, total=10 if i < 142 else 0) for i in range(150)]
    old = summarize(lines, rows)
    assert old["working"]["enqueued"] is None
    assert old["at_140_s"]["enqueued"] == 1400
    assert old["service_peak"] == dict(cycles=169670, previous_snapshot_ms=140004, first_observed_ms=150006)
    cut = "FIELD01 WORK_CUT tick=143001 elapsed=142001 enqueued=1423 base=2 high=5 overflow=0 replaced=0 drop=0 tx_cyc=900 tx_b=1"
    measured = summarize([*lines, cut], rows)
    assert measured["working"]["delivery_ratio"] == 1420 / 1421
    assert measured["working"]["delivery_ratio_is_lower_bound"]
    assert measured["working"]["tx_cycles_per_byte"] == 900
    assert measured["working"]["dropped"] == 0 and measured["full"]["dropped"] == 20
