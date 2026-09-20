"""CANopen C 产物 → 现有 Python Topic/Schema/Hub 的边界回归，无联网。"""

import json
from pathlib import Path
import sys

# 使用真实 C 程序生成的消息喂给 Backend；不在 Python 中另造同形载荷来替代映射验证。
ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / 'cloud/backend'))
from app.adapters import decode_mqtt
from app.hub import Hub

hub = Hub(['GW-C-001'], clock=lambda: 1790000010.0)
hub.broker_connected = True
seen = set()
count = 0
for line in (
    (ROOT / 'gateway/canopen/build/canonical.jsonl').read_text(encoding='utf-8').splitlines()
):
    topic, body = line.split('\t', 1)
    message = decode_mqtt(topic, body.encode())
    hub.ingest(message)
    seen.add(message.stream)
    count += 1
    if message.stream == 'ECG':
        if message.sample_rate != 250 or len(message.samples) != 250:
            raise RuntimeError('ECG batching mismatch')
    if message.stream == 'RR' and message.validity != 'INVALID':
        raise RuntimeError('Unimplemented RR advertised VALID')
    if not message.synthetic:
        raise RuntimeError('Synthetic test source lost')
expected = {
    'PPG',
    'SPO2',
    'PR',
    'NIBP',
    'ECG',
    'HR',
    'RESP',
    'RR',
    'TEMP',
    'NODE_STATUS',
    'GATEWAY_STATUS',
}
if seen != expected:
    raise RuntimeError('Missing canonical streams')
snapshot = hub.snapshot('GW-C-001')
if len(snapshot['streams']) != 9:
    raise RuntimeError('Browser snapshot structure mismatch')
print(
    json.dumps(
        {
            'c_to_backend_messages': count,
            'streams': sorted(seen),
            'browser_schema_version': snapshot['schema_version'],
        }
    )
)
