import hashlib
import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import r83_mqtt_readonly_capture as r83


class SimulatedClient:
    def __init__(self, messages=(), rejected=False):
        self.messages = messages
        self.rejected = rejected
        self.subscriptions = []
        self.closed = False

    def connect(self, host, port, keepalive):
        self.on_connect(self, None, None, SimpleNamespace(is_failure=False), None)
        return 0

    def subscribe(self, topics):
        self.subscriptions.extend(topics)
        return 0, 1

    def loop(self, timeout):
        reasons = [SimpleNamespace(is_failure=self.rejected), SimpleNamespace(is_failure=False)]
        self.on_subscribe(self, None, 1, reasons, None)
        for topic, payload in self.messages:
            self.on_message(self, None, SimpleNamespace(topic=topic, payload=payload))
        return 0

    def disconnect(self):
        self.closed = True


class TestCapture(unittest.TestCase):
    def record(self, client):
        with tempfile.TemporaryDirectory() as folder:
            target = Path(folder) / 'capture.jsonl'
            with patch.object(r83, 'create_client', return_value=client), \
                    patch.object(r83.time, 'monotonic', side_effect=(0, 0, 0, 2)):
                receipt = r83.capture({'host': '127.0.0.1'}, target, 1)
            raw = target.read_bytes()
            self.assertEqual(receipt['sha256'], hashlib.sha256(raw).hexdigest())
            self.assertTrue(client.closed)
            return receipt, [json.loads(row) for row in raw.splitlines()]

    def test_only_node_b_and_preserve_invalid_payload(self):
        payload = b'{ "validity": "INVALID", "samples": [1,-2] }'
        topic = r83.BASE + '/telemetry/RESP'
        client = SimulatedClient([(topic, payload), (r83.BASE + '/status', b'{"online":true}')])
        receipt, rows = self.record(client)
        self.assertEqual(client.subscriptions, [(r83.BASE + '/telemetry/+', 0), (r83.BASE + '/status', 0)])
        self.assertEqual(receipt['state'], 'COMPLETE')
        self.assertEqual(receipt['lines'], 2)
        self.assertEqual(rows[0]['topic'], topic)
        self.assertEqual(rows[0]['payload'], payload.decode('ascii'))
        self.assertIsInstance(rows[0]['ts_ms'], int)

    def test_subscription_rejection_stops(self):
        receipt, rows = self.record(SimulatedClient(rejected=True))
        self.assertEqual(receipt['error'], 'SUBSCRIBE_REJECTED')
        self.assertEqual(rows, [])

    def test_unexpected_topic_is_not_written(self):
        receipt, rows = self.record(SimulatedClient([(r83.BASE + '/event', b'{}')]))
        self.assertEqual(receipt['error'], 'UNEXPECTED_TOPIC')
        self.assertEqual(rows, [])


if __name__ == '__main__':
    unittest.main()
