"""A1 时序细化：生命体征变化轨迹、血压出现时刻、稳定窗口众数。"""
import json
import re
from collections import Counter
from pathlib import Path

OUT = Path(r'E:\多参数心电监护仪系统-样机开发\doc\A\实测数据\A1_NodeA_CAN_20261019T192020')
lines = (OUT / 'com15_text.log').read_text(encoding='utf-8', errors='replace').splitlines()

BENCH = re.compile(r'BENCH ms=(\d+)')
RX = re.compile(r'RX id=(\w+) n=\d+ .*? data=(\w+)')

rows = []
c_ms = None
for line in lines:
    match = BENCH.search(line)
    if match:
        c_ms = int(match.group(1))
        continue
    match = RX.search(line)
    if match and match.group(1) == '381' and c_ms is not None:
        data = match.group(2)
        raw = bytes.fromhex(data)
        rows.append({'c_ms': c_ms,
                     'spo2': int.from_bytes(raw[0:2], 'little') / 100.0,
                     'pr': int.from_bytes(raw[2:4], 'little') / 100.0,
                     'sys': int.from_bytes(raw[4:6], 'little') / 10.0,
                     'dia': int.from_bytes(raw[6:8], 'little') / 10.0})

t0 = rows[0]['c_ms']
for row in rows:
    row['t_s'] = round((row['c_ms'] - t0) / 1000.0, 1)

# 压缩成"变化点"序列
changes = []
previous = None
for row in rows:
    key = (row['spo2'], row['pr'], row['sys'], row['dia'])
    if key != previous:
        changes.append(row)
        previous = key

print(f'共解码 {len(rows)} 帧 0x381，覆盖 {rows[-1]["t_s"]:.1f} s')
print(f'状态变化点 {len(changes)} 个\n')
print(f'{"t(s)":>7} {"SpO2%":>7} {"PR":>6} {"SYS":>6} {"DIA":>6}')
print('-' * 40)
for row in changes:
    print(f'{row["t_s"]:>7.1f} {row["spo2"]:>7.2f} {row["pr"]:>6.2f} {row["sys"]:>6.1f} {row["dia"]:>6.1f}')

spo2_valid = [r['spo2'] for r in rows if r['spo2'] > 0]
pr_valid = [r['pr'] for r in rows if r['pr'] > 0]
bp_rows = [r for r in rows if r['sys'] > 0]
bp_first = bp_rows[0] if bp_rows else None
bp_last = bp_rows[-1] if bp_rows else None

summary = {
    'decoded_frames': len(rows),
    'tracks_s': rows[-1]['t_s'],
    'state_changes': len(changes),
    'spo2_valid_frames': len(spo2_valid),
    'spo2_mode': Counter(spo2_valid).most_common(3) if spo2_valid else None,
    'spo2_range': [min(spo2_valid), max(spo2_valid)] if spo2_valid else None,
    'pr_valid_frames': len(pr_valid),
    'pr_mode': Counter(pr_valid).most_common(3) if pr_valid else None,
    'pr_range': [min(pr_valid), max(pr_valid)] if pr_valid else None,
    'bp_result_frames': len(bp_rows),
    'bp_value': [bp_first['sys'], bp_first['dia']] if bp_first else None,
    'bp_first_seen_t_s': bp_first['t_s'] if bp_first else None,
    'bp_last_seen_t_s': bp_last['t_s'] if bp_last else None,
    'bp_duration_s': round(bp_last['t_s'] - bp_first['t_s'], 1) if bp_first and bp_last else None,
    'spo2_pr_at_bp_moment': None,
    'change_series': [{k: r[k] for k in ('t_s', 'spo2', 'pr', 'sys', 'dia')} for r in changes],
}
if bp_first:
    window = [r for r in rows if abs(r['t_s'] - bp_first['t_s']) < 5 and r['spo2'] > 0]
    if window:
        summary['spo2_pr_at_bp_moment'] = {
            'spo2': Counter(r['spo2'] for r in window).most_common(2),
            'pr': Counter(r['pr'] for r in window if r['pr'] > 0).most_common(2)}

(OUT / 'vitals_timeline.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding='utf-8')
print()
print(json.dumps({k: v for k, v in summary.items() if k != 'change_series'}, ensure_ascii=False, indent=2))
