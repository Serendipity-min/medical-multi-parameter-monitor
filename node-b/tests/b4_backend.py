"""真实C输出经既有Backend解码/Hub；离线运行，不创建服务器或修改云代码。"""
from pathlib import Path
import json
import sys
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'cloud/backend'))
from app.adapters import decode_mqtt
from app.hub import Hub


def main():
    hub = Hub(['GW-C-001'], clock=lambda: 1792713692.0)
    seen = set(); count = 0; ecg = 0; temperature = 0
    for line in Path(sys.argv[1]).read_text(encoding='utf-8').splitlines():
        topic, payload = line.split('\t', 1)
        message = decode_mqtt(topic, payload.encode())
        hub.ingest(message); seen.add(message.stream); count += 1
        if message.stream == 'ECG':
            assert message.sample_rate == 250 and len(message.samples) == 100
            ecg += 1
        if message.stream == 'TEMP':
            assert message.validity == 'INVALID' and message.value is None
            temperature += 1
    assert {'PPG', 'SPO2', 'PR', 'NIBP', 'ECG', 'HR', 'RESP', 'RR', 'TEMP', 'NODE_STATUS'} <= seen
    assert ecg > 200 and temperature > 80
    print(json.dumps({'c_to_backend': count, 'ecg_100_sample_batches': ecg,
                      'invalid_temperature_records': temperature, 'streams': sorted(seen),
                      'schema_version': hub.snapshot('GW-C-001')['schema_version'],
                      'network_access': False}))


if __name__ == '__main__':
    main()
