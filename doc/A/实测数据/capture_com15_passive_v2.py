"""A2：Node-A → Gateway-C 单向被动观测（第二轮，由操作员对照触发）。

改进点（相对 A1）：
  1. 边采边落盘：每个读取周期立即 append 到 raw/text 文件，进程中途被杀也不丢已采数据；
  2. 实时解析 0x381：把 SpO2/PR/SYS/DIA 解码后打出，血压一出现立刻报告；
  3. DTR/RTS 保持 False，全程不向端口写入任何字节。
"""
import json
import re
import time
from datetime import datetime
from pathlib import Path

import serial

DURATION_S = 300
STAMP = datetime.now().strftime('%Y%m%dT%H%M%S')
OUT = Path(r'E:\多参数心电监护仪系统-样机开发\doc\A\实测数据') / f'A2_NodeA_CAN_{STAMP}'
OUT.mkdir(parents=True, exist_ok=True)
RAW_PATH = OUT / 'com15_raw.bin'
TXT_PATH = OUT / 'com15_text.log'
RECEIPT = OUT / 'capture_receipt.json'

RX381 = re.compile(r'RX id=381 .*?data=([0-9a-fA-F]{16})')

print(f'OUT={OUT}', flush=True)

port = serial.Serial(port=None, baudrate=115200, bytesize=8, parity='N',
                     stopbits=1, timeout=0.2)
port.dtr = False
port.rts = False
port.port = 'COM15'

receipt = {'round': 'A2', 'port': 'COM15', 'baud': 115200, 'duration_s': DURATION_S,
           'mode': 'PASSIVE_RX_ONLY_NO_BYTES_WRITTEN', 'dtr': False, 'rts': False,
           'started': STAMP, 'opened': False}
line_buffer = bytearray()
total_bytes = 0
total_lines = 0
frames_381 = 0
latest = None
bp_first = None
bp_events = []

began = time.monotonic()
next_beat = 0.0
try:
    port.open()
    receipt['opened'] = True
    print('READY: COM15 opened, passive recording started, no bytes written', flush=True)
    with RAW_PATH.open('ab') as raw_handle, TXT_PATH.open('a', encoding='utf-8') as txt_handle:
        while True:
            elapsed = time.monotonic() - began
            if elapsed >= DURATION_S:
                break
            chunk = port.read(4096)
            if chunk:
                raw_handle.write(chunk)
                raw_handle.flush()
                total_bytes += len(chunk)
                line_buffer.extend(chunk)
                while True:
                    idx = line_buffer.find(b'\n')
                    if idx < 0:
                        break
                    line = bytes(line_buffer[:idx]).decode('utf-8', errors='replace')
                    del line_buffer[:idx + 1]
                    total_lines += 1
                    txt_handle.write(line + '\n')
                    match = RX381.search(line)
                    if match:
                        frames_381 += 1
                        raw = bytes.fromhex(match.group(1))
                        values = {
                            'spo2': int.from_bytes(raw[0:2], 'little') / 100.0,
                            'pr': int.from_bytes(raw[2:4], 'little') / 100.0,
                            'sys': int.from_bytes(raw[4:6], 'little') / 10.0,
                            'dia': int.from_bytes(raw[6:8], 'little') / 10.0,
                            't_s': round(elapsed, 1),
                        }
                        latest = values
                        if values['sys'] > 0 and bp_first is None:
                            bp_first = values
                            bp_events.append(dict(values, event='BP_FIRST_SEEN'))
                            print(f'[BP!] t={values["t_s"]}s  '
                                  f'SYS/DIA={values["sys"]:.0f}/{values["dia"]:.0f} mmHg  '
                                  f'SpO2={values["spo2"]:.0f}%  PR={values["pr"]:.0f}', flush=True)
                        elif values['sys'] == 0 and bp_first is not None and (
                                not bp_events or bp_events[-1].get('event') != 'BP_EXPIRED'):
                            bp_events.append(dict(values, event='BP_EXPIRED'))
                            print(f'[BP]  t={values["t_s"]}s 血压已归零（时效）', flush=True)
                txt_handle.flush()
            if elapsed >= next_beat:
                brief = ('-' if latest is None else
                         f"SpO2={latest['spo2']:.0f}% PR={latest['pr']:.0f} "
                         f"BP={latest['sys']:.0f}/{latest['dia']:.0f}")
                print(f'[{elapsed:6.1f}s] bytes={total_bytes} lines={total_lines} '
                      f'0x381={frames_381} {brief}', flush=True)
                next_beat = elapsed + 5.0
except Exception as exc:
    receipt['error'] = repr(exc)
    print(f'ERROR {exc!r}', flush=True)
finally:
    if port.is_open:
        port.close()
    receipt.update({'bytes': total_bytes, 'lines': total_lines, 'frames_381': frames_381,
                    'latest_vitals': latest, 'bp_first_seen': bp_first,
                    'bp_events': bp_events,
                    'finished': datetime.now().strftime('%Y%m%dT%H%M%S')})
    RECEIPT.write_text(json.dumps(receipt, ensure_ascii=False, indent=2), encoding='utf-8')
    print('DONE ' + json.dumps(receipt, ensure_ascii=False), flush=True)
