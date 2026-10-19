"""解析 A1 被动观测日志：CAN 传输统计 + TPDO3 生命体征解码。

映射依据 node-a/STM32F407_HOSPITAL/HARDWARE/CANopen/OD.c 的 0x1A02：
  applicationObject1..4 = 0x2120:01 SpO2, :02 PR, :03 NIBP_SYS, :04 NIBP_DIA（各 16 bit）
  => 0x381 载荷 [SpO2][PR][SYS][DIA]，小端，DLC=8
"""
import json
import re
from datetime import datetime
from pathlib import Path

OUT = Path(r'E:\多参数心电监护仪系统-样机开发\doc\A\实测数据\A1_NodeA_CAN_20261019T192020')
TXT = OUT / 'com15_text.log'

text = TXT.read_text(encoding='utf-8', errors='replace')
lines = text.splitlines()

BENCH = re.compile(
    r'BENCH ms=(\d+) armed=(\d+) fault=(\d+) PCLK1=(\d+) BTR=(\w+) TEC=(\d+) REC=(\d+) '
    r'LEC=(\d+) BOFF=(\d+) TXOK=(\d+) NMT_START=(\d+) NMT_TXOK=(\d+) A=(\d+) B=(\d+) '
    r'time=(\S+) paused=(\d+) diag_ms=(\d+)')
RX = re.compile(r'RX id=(\w+) n=(\d+) first=(\d+) last=(\d+) dt_min=(\d+) dt_max=(\d+) dlc=(\d+) data=(\w+)')
RXQ = re.compile(r'RXQ hw_fovr=(\d+) sw_over=(\d+) depth=(\d+) high=(\d+) hw_full=(\d+)')
MODEL = re.compile(r'MODEL frames=(\d+) invalid=(\d+) .*?valid=(\d+) synthetic=(\d+)')

bench, first_data = [], {}
rx_start, rx_end, rx_seen = {}, {}, {}
vitals_series = []
errors = {'TEC': 0, 'REC': 0, 'LEC_max': 0, 'BOFF_max': 0, 'hw_fovr_max': 0, 'sw_over_max': 0, 'hw_full_max': 0}
model_last = None


def s16le(hexpayload, offset):
    raw = bytes.fromhex(hexpayload)
    return int.from_bytes(raw[offset:offset + 2], 'little')


for line in lines:
    match = BENCH.search(line)
    if match:
        g = match.groups()
        bench.append({'ms': int(g[0]), 'armed': int(g[1]), 'fault': int(g[2]), 'PCLK1': int(g[3]),
                      'TEC': int(g[5]), 'REC': int(g[6]), 'LEC': int(g[7]), 'BOFF': int(g[8]),
                      'TXOK': int(g[9]), 'NMT_START': int(g[10]), 'NMT_TXOK': int(g[11]),
                      'A': int(g[12]), 'B': int(g[13]), 'time': g[14], 'paused': int(g[15])})
        errors['TEC'] = max(errors['TEC'], int(g[5]))
        errors['REC'] = max(errors['REC'], int(g[6]))
        errors['LEC_max'] = max(errors['LEC_max'], int(g[7]))
        errors['BOFF_max'] = max(errors['BOFF_max'], int(g[8]))
        continue

    match = RX.search(line)
    if match:
        ident, n, first, last, dt_min, dt_max, dlc, data = match.groups()
        key = ident
        rx_end[key] = {'n': int(n), 'first': int(first), 'last': int(last),
                       'dt_min': int(dt_min), 'dt_max': int(dt_max), 'dlc': int(dlc), 'data': data}
        rx_start.setdefault(key, dict(rx_end[key]))
        if ident == '381' and len(data) == 16:
            vitals_series.append({
                'spo2_raw': s16le(data, 0), 'pr_raw': s16le(data, 2),
                'sys_raw': s16le(data, 4), 'dia_raw': s16le(data, 6),
                'raw_hex': data, 'c_ms': bench[-1]['ms'] if bench else None})
        continue

    match = RXQ.search(line)
    if match:
        errors['hw_fovr_max'] = max(errors['hw_fovr_max'], int(match.group(1)))
        errors['sw_over_max'] = max(errors['sw_over_max'], int(match.group(2)))
        errors['hw_full_max'] = max(errors['hw_full_max'], int(match.group(5)))
        continue

    match = MODEL.search(line)
    if match:
        model_last = {'frames': int(match.group(1)), 'invalid': int(match.group(2)),
                      'valid': int(match.group(3)), 'synthetic': int(match.group(4))}

# ---- 汇总 ----
window_ms = (bench[-1]['ms'] - bench[0]['ms']) if len(bench) >= 2 else 0
frames = {}
for key in sorted(rx_end):
    start, end = rx_start[key], rx_end[key]
    delta = end['n'] - start['n']
    frames[key] = {
        'count_start': start['n'], 'count_end': end['n'], 'frames_in_window': delta,
        'rate_hz': round(delta / (window_ms / 1000.0), 3) if window_ms else None,
        'dlc': end['dlc'], 'dt_min_ms': end['dt_min'], 'dt_max_ms': end['dt_max'],
        'last_payload_hex': end['data'],
    }

def summarise(values):
    values = [v for v in values]
    return {'min': min(values), 'max': max(values), 'distinct': sorted(set(values))[:12]} if values else None

vitals = {
    'blocks_decoded': len(vitals_series),
    'SpO2_percent': summarise([v['spo2_raw'] / 100.0 for v in vitals_series]),
    'PR_bpm': summarise([v['pr_raw'] / 100.0 for v in vitals_series]),
    'NIBP_SYS_mmHg': summarise([v['sys_raw'] / 10.0 for v in vitals_series]),
    'NIBP_DIA_mmHg': summarise([v['dia_raw'] / 10.0 for v in vitals_series]),
    'non_zero_NIBP_blocks': sum(1 for v in vitals_series if v['sys_raw'] or v['dia_raw']),
    'non_zero_PR_blocks': sum(1 for v in vitals_series if v['pr_raw']),
    'non_zero_SpO2_blocks': sum(1 for v in vitals_series if v['spo2_raw']),
}

result = {
    'capture_dir': str(OUT),
    'diag_blocks': len(bench),
    'capture_window_s': round(window_ms / 1000.0, 3),
    'board_uptime_ms': [bench[0]['ms'], bench[-1]['ms']] if bench else None,
    'c_board_state': {
        'armed': sorted({b['armed'] for b in bench}),
        'fault': sorted({b['fault'] for b in bench}),
        'paused': sorted({b['paused'] for b in bench}),
        'A_online': sorted({b['A'] for b in bench}),
        'B_online': sorted({b['B'] for b in bench}),
        'time_state': sorted({b['time'] for b in bench}),
        'PCLK1': bench[0]['PCLK1'] if bench else None,
        'NMT_START_total': bench[-1]['NMT_START'] if bench else None,
        'NMT_TXOK_total': bench[-1]['NMT_TXOK'] if bench else None,
        'TXOK_total': bench[-1]['TXOK'] if bench else None,
    },
    'can_errors_max': errors,
    'frames_per_id': frames,
    'vitals_from_0x381': vitals,
    'model_state_last': model_last,
    'decode_rule': '0x381 = [SpO2 u16 /100][PR u16 /100][NIBP_SYS u16 /10][NIBP_DIA u16 /10], little-endian',
    'parsed_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
}
(OUT / 'parse_summary.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')

print(json.dumps({k: result[k] for k in ['diag_blocks', 'capture_window_s', 'board_uptime_ms',
                                         'c_board_state', 'can_errors_max', 'frames_per_id',
                                         'vitals_from_0x381', 'model_state_last']},
                 ensure_ascii=False, indent=2))
print()
print('=== 首批与末批生命体征原始字节 ===')
for item in vitals_series[:3] + vitals_series[-3:]:
    print(f"  c_ms={item['c_ms']} hex={item['raw_hex']} "
          f"-> SpO2={item['spo2_raw']/100:.2f}% PR={item['pr_raw']/100:.2f} "
          f"SYS={item['sys_raw']/10:.1f} DIA={item['dia_raw']/10:.1f}")
