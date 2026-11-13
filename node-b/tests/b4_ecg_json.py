"""实际C序列化结果经既有Backend解码；只验证固定点单位与序列，不建立网络。"""
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'cloud/backend'))
from app.adapters import decode_mqtt


def main():
    topic, text = Path(sys.argv[1]).read_text('utf-8').strip().split('\t', 1)
    payload = json.loads(text); message = decode_mqtt(topic, text.encode())
    expected_uv = [0, 0, 0, 1, -1, 1, -1, 120, -120, 121, -121,
                   605000, -605000, 1299227761, -1299227761]
    expected = [expected_uv[i % len(expected_uv)] / 1000 for i in range(100)]
    assert payload['unit'] == 'mV' and payload['source'] == 'MOCK' and payload['synthetic']
    assert payload['samples'] == expected and list(message.samples) == expected
    assert message.sample_rate == 250 and message.stream == 'ECG'
    print(json.dumps({'status': 'GAIN4_MV_BACKEND_SEQUENCE_PASS', 'samples': 100,
                      'network_access': False, 'absolute_voltage_calibration': False}))


if __name__ == '__main__':
    main()
