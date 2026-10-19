"""Node-A → Gateway-C 单向被动观测（A1）。

严格只读：打开 COM15 后不发送任何字节，DTR/RTS 保持 False（避免串口电平扰动目标板）。
用于观察 C 台架版每秒诊断里的 0x181/0x381/0x481/0x681 帧与载荷。
"""
import json
import time
from datetime import datetime
from pathlib import Path

import serial

STAMP = datetime.now().strftime('%Y%m%dT%H%M%S')
OUT = Path(r'E:\多参数心电监护仪系统-样机开发\doc\A\实测数据') / f'A1_NodeA_CAN_{STAMP}'
OUT.mkdir(parents=True, exist_ok=True)
RAW = OUT / 'com15_raw.bin'
TXT = OUT / 'com15_text.log'
RECEIPT = OUT / 'capture_receipt.json'

DURATION_S = 150
PORT = 'COM15'
BAUD = 115200

print(f'OUT={OUT}', flush=True)

port = serial.Serial(port=None, baudrate=BAUD, bytesize=8, parity='N',
                     stopbits=1, timeout=0.2)
port.dtr = False
port.rts = False
port.port = PORT

receipt = {'port': PORT, 'baud': BAUD, 'duration_s': DURATION_S,
           'mode': 'PASSIVE_RX_ONLY_NO_BYTES_WRITTEN',
           'dtr': False, 'rts': False, 'started': STAMP, 'bytes': 0, 'lines': 0,
           'opened': False, 'finished': None}

raw = bytearray()
text_parts = []
began = time.monotonic()
next_beat = 0.0
try:
    port.open()
    receipt['opened'] = True
    print('PORT OPENED, passive listening', flush=True)
    while True:
        elapsed = time.monotonic() - began
        if elapsed >= DURATION_S:
            break
        data = port.read(4096)
        if data:
            raw.extend(data)
            text_parts.append(data.decode('utf-8', errors='replace'))
        if elapsed >= next_beat:
            lines = sum(part.count('\n') for part in text_parts)
            print(f'[{elapsed:6.1f}s] bytes={len(raw)} newlines={lines}', flush=True)
            next_beat = elapsed + 5.0
except Exception as exc:
    receipt['error'] = repr(exc)
    print(f'ERROR {exc!r}', flush=True)
finally:
    if port.is_open:
        port.close()
    RAW.write_bytes(bytes(raw))
    joined = ''.join(text_parts)
    TXT.write_text(joined, encoding='utf-8')
    receipt['bytes'] = len(raw)
    receipt['lines'] = joined.count('\n')
    receipt['finished'] = datetime.now().strftime('%Y%m%dT%H%M%S')
    RECEIPT.write_text(json.dumps(receipt, ensure_ascii=False, indent=2), encoding='utf-8')
    print('DONE ' + json.dumps(receipt, ensure_ascii=False), flush=True)
    print('--- first 1500 chars ---', flush=True)
    print(joined[:1500], flush=True)
