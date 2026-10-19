"""解析 Node-A → Gateway-C 被动观测日志（通用版，按目录传入）。

用法：python parse_nodeA_can.py <capture_dir>
映射依据 node-a/.../CANopen/OD.c 的 0x1A02：
  0x381 = [SpO2 u16 /100][PR u16 /100][NIBP_SYS u16 /10][NIBP_DIA u16 /10]，小端，DLC=8
"""
import json
import re
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path

capture_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(
    r'E:\多参数心电监护仪系统-样机开发\doc\A\实测数据\A2_NodeA_CAN_20261019T192617')
TXT = capture_dir / 'com15_text.log'
if not TXT.exists():
    raise SystemExit(f'日志不存在: {TXT}')

lines = TXT.read_text(encoding='utf-8', errors='replace').splitlines()

BENCH = re.compile(
    r'BENCH ms=(\d+) armed=(\d+) fault=(\d+) PCLK1=(\d+) BTR=(\w+) TEC=(\d+) REC=(\d+) '
    r'LEC=(\d+) BOFF=(\d+) TXOK=(\d+) NMT_START=(\d+) NMT_TXOK=(\d+) A=(\d+) B=(\d+) '
    r'time=(\S+) paused=(\d+)')
RX = re.compile(r'RX id=(\w+) n=(\d+) first=(\d+) last=(\d+) dt_min=(\d+) dt_max=(\d+) dlc=(\d+) data=(\w+)')
RXQ = re.compile(r'RXQ hw_fovr=(\d+) sw_over=(\d+) depth=(\d+) high=(\d+) hw_full=(\d+)')
MODEL = re.compile(r'MODEL frames=(\d+) invalid=(\d+) .*?valid=(\d+) synthetic=(\d+)')

bench, rx_start, rx_end, vitals = [], {}, {}, []
cyc_ms = None
errors = {'TEC': 0, 'REC': 0, 'LEC': 0, 'BOFF': 0, 'hw_fovr': 0, 'sw_over': 0, 'hw_full': 0}
model_last = None

for line in lines:
    m = BENCH.search(line)
    if m:
        g = m.groups()
        cyc_ms = int(g[0])
        bench.append({'ms': cyc_ms, 'armed': int(g[1]), 'fault': int(g[2]),
                      'A': int(g[12]), 'B': int(g[13]), 'time': g[14], 'paused': int(g[15])})
        for key, value in (('TEC', g[5]), ('REC', g[6]), ('LEC', g[7]), ('BOFF', g[8])):
            errors[key] = max(errors[key], int(value))
        continue
    m = RX.search(line)
    if m:
        ident, n, first, last, dt_min, dt_max, dlc, data = m.groups()
        entry = {'n': int(n), 'first': int(first), 'last': int(last), 'dt_min': int(dt_min),
                 'dt_max': int(dt_max), 'dlc': int(dlc), 'data': data}
        rx_end[ident] = entry
        rx_start.setdefault(ident, dict(entry))
        if ident == '381' and len(data) == 16:
            raw = bytes.fromhex(data)
            vitals.append({'c_ms': cyc_ms,
                           'spo2': int.from_bytes(raw[0:2], 'little') / 100.0,
                           'pr': int.from_bytes(raw[2:4], 'little') / 100.0,
                           'sys': int.from_bytes(raw[4:6], 'little') / 10.0,
                           'dia': int.from_bytes(raw[6:8], 'little') / 10.0})
        continue
    m = RXQ.search(line)
    if m:
        errors['hw_fovr'] = max(errors['hw_fovr'], int(m.group(1)))
        errors['sw_over'] = max(errors['sw_over'], int(m.group(2)))
        errors['hw_full'] = max(errors['hw_full'], int(m.group(5)))
        continue
    m = MODEL.search(line)
    if m:
        model_last = {'frames': int(m.group(1)), 'invalid': int(m.group(2)),
                      'valid': int(m.group(3)), 'synthetic': int(m.group(4))}

window_ms = (bench[-1]['ms'] - bench[0]['ms']) if len(bench) >= 2 else 0
t0 = vitals[0]['c_ms'] if vitals and vitals[0]['c_ms'] else (bench[0]['ms'] if bench else 0)
for row in vitals:
    row['t_s'] = round((row['c_ms'] - t0) / 1000.0, 1) if row['c_ms'] else None

frames = {}
for ident in sorted(rx_end):
    start, end = rx_start[ident], rx_end[ident]
    delta = end['n'] - start['n']
    frames[ident] = {'frames_in_window': delta,
                     'rate_hz': round(delta / (window_ms / 1000.0), 3) if window_ms else None,
                     'dlc': end['dlc'], 'dt_min_ms': end['dt_min'], 'dt_max_ms': end['dt_max'],
                     'last_payload_hex': end['data']}

spo2_valid = [r['spo2'] for r in vitals if r['spo2'] > 0]
pr_valid = [r['pr'] for r in vitals if r['pr'] > 0]
bp_rows = [r for r in vitals if r['sys'] > 0]
changes, previous = [], None
for row in vitals:
    key = (row['spo2'], row['pr'], row['sys'], row['dia'])
    if key != previous:
        changes.append(row)
        previous = key

summary = {
    'capture_dir': str(capture_dir),
    'diag_blocks': len(bench),
    'window_s': round(window_ms / 1000.0, 1),
    'board_uptime_ms': [bench[0]['ms'], bench[-1]['ms']] if bench else None,
    'c_state': {'paused': sorted({b['paused'] for b in bench}),
                'A_online': sorted({b['A'] for b in bench}),
                'B_online': sorted({b['B'] for b in bench}),
                'fault': sorted({b['fault'] for b in bench}),
                'time': sorted({b['time'] for b in bench})},
    'can_errors_max': errors,
    'frames_per_id': frames,
    'decoded_381_frames': len(vitals),
    'spo2': {'valid_frames': len(spo2_valid),
             'mode': Counter(spo2_valid).most_common(3) if spo2_valid else None,
             'range': [min(spo2_valid), max(spo2_valid)] if spo2_valid else None},
    'pr': {'valid_frames': len(pr_valid),
           'mode': Counter(pr_valid).most_common(3) if pr_valid else None,
           'range': [min(pr_valid), max(pr_valid)] if pr_valid else None},
    'bp': {'result_frames': len(bp_rows),
           'value': [bp_rows[0]['sys'], bp_rows[0]['dia']] if bp_rows else None,
           'first_t_s': bp_rows[0]['t_s'] if bp_rows else None,
           'last_t_s': bp_rows[-1]['t_s'] if bp_rows else None,
           'persist_s': round(bp_rows[-1]['t_s'] - bp_rows[0]['t_s'], 1) if bp_rows else None},
    'model_last': model_last,
    'decode_rule': '0x381 = SpO2 x100 | PR x100 | NIBP_SYS x10 | NIBP_DIA x10 (little-endian)',
    'state_changes': [{k: r[k] for k in ('t_s', 'spo2', 'pr', 'sys', 'dia')} for r in changes],
    'parsed_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
}
(capture_dir / 'parse_summary.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2),
                                                encoding='utf-8')
(capture_dir / 'vitals_timeline.json').write_text(
    json.dumps(summary['state_changes'], ensure_ascii=False, indent=2), encoding='utf-8')

print(json.dumps({k: v for k, v in summary.items() if k != 'state_changes'}, ensure_ascii=False, indent=2))
