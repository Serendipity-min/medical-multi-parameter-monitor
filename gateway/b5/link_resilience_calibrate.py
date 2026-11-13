"""只读已有 UART 原件，导出不含原始行的 PUBACK 阈值证据。"""
import argparse
import hashlib
import json
import re
from pathlib import Path

BOUNDS = (1, 5, 10, 25, 50, 100, 250, 500, 1000, 1500, 2516)


def fields(line):
    return {key: int(value) for key, value in re.findall(r'(\w+)=([+-]?\d+)(?:\s|$)', line)}


def analyze(path, seconds):
    raw = path.read_bytes()
    rows = [json.loads(line) for line in raw.decode('utf-8-sig').splitlines() if line]
    start = next(row['monotonic'] for row in rows if row.get('line') == 'GW MQTT_CONNECTED')
    end = start + seconds
    window = [row for row in rows if start <= row['monotonic'] <= end]
    acks = [row for row in window if row.get('line', '').startswith('B5 PROD_ACK ')]
    bins = None
    if acks:
        last = acks[-1]
        bins = [int(value) for value in last['line'].split('bins=')[1].split(',')]
    else:
        last = [row for row in window if row.get('line', '').startswith('B5 LAT stage=6 ')][-1]
    sample = fields(last['line'])
    exit_acks = [(row['monotonic'], tuple(map(int, value.split('/')))) for row in rows
                 if row.get('line', '').startswith('B5 TXACK rows=')
                 for value in row['line'].split('rows=')[1].split(',')]
    gaps = [fields(row['line'])['ack_gap_ms'] for row in window
            if row.get('line', '').startswith('B5 TXCHK ')]
    sensitivity = {}
    for threshold in (600, 800, 1000, 1500):
        upper = sample['n']
        if bins:
            upper = sum(count for count, bound in zip(bins, (*BOUNDS, sample['max'])) if bound > threshold)
        if sample['max'] <= threshold:
            upper = 0
        sensitivity[str(threshold)] = dict(
            possible_slow_transactions_upper=upper,
            predicted_triggers_upper=0 if not upper else 'UNKNOWN',
            paused_bytes_upper=0 if not upper else 'UNKNOWN')
    return dict(sha256=hashlib.sha256(raw).hexdigest(), seconds=seconds,
                observed_to_end=rows[-1]['monotonic'] >= end,
                last_ack_snapshot_s=round(last['monotonic']-start, 3),
                ack_transactions=sample['n'], transaction_max_ms=sample['max'],
                p50_upper_ms=sample['p50_upper'], p95_upper_ms=sample['p95_upper'],
                p99_upper_ms=sample['p99_upper'], bins=bins,
                steady_adjacent_ack_max_ms=max(gaps, default=None),
                explicit_ack_rows=sum(start <= at <= end for at, _ in exit_acks),
                exit_ack_rows=len(exit_acks), sensitivity=sensitivity,
                waiting_time_distribution='UNKNOWN_WITHOUT_CONTINUOUS_ACK_AND_PENDING_EVENTS')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--window', nargs=3, action='append', metavar=('LABEL', 'UART', 'SECONDS'), required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    result = {label: analyze(Path(path), int(seconds)) for label, path, seconds in args.window}
    args.out.write_text(json.dumps(dict(scope='OFFLINE_EXISTING_EVIDENCE', windows=result), indent=2) + '\n', encoding='utf-8')
    print(json.dumps(result))


if __name__ == '__main__':
    main()
