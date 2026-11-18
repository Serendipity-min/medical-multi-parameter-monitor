import hashlib
import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import r85_mqtt_readonly_capture as r85


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
        reasons = [SimpleNamespace(is_failure=(self.rejected and i == 0))
                   for i in range(len(self.subscriptions))]
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
            with patch.object(r85, 'create_client', return_value=client), \
                    patch.object(r85.time, 'monotonic', side_effect=(0, 0, 0, 2)):
                receipt = r85.capture({'host': '127.0.0.1'}, target, 1)
            raw = target.read_bytes()
            self.assertEqual(receipt['sha256'], hashlib.sha256(raw).hexdigest())
            self.assertTrue(client.closed)
            return receipt, [json.loads(row) for row in raw.splitlines()]

    def test_only_nodes_a_b_and_preserve_payloads(self):
        payload = b'{ "validity": "INVALID", "samples": [1,-2] }'
        pr = b'{ "validity": "VALID", "value": 74.0 }'
        topic = r85.BASE + '/NODE-B/telemetry/resp'
        pr_topic = r85.BASE + '/NODE-A/telemetry/pr'
        client = SimulatedClient([(topic, payload), (pr_topic, pr),
                                  (r85.BASE + '/NODE-A/status', b'{"online":true}'),
                                  (r85.BASE + '/NODE-B/status', b'{"online":true}')])
        receipt, rows = self.record(client)
        self.assertEqual(client.subscriptions, [
            (r85.BASE + '/NODE-A/telemetry/+', 0), (r85.BASE + '/NODE-A/status', 0),
            (r85.BASE + '/NODE-B/telemetry/+', 0), (r85.BASE + '/NODE-B/status', 0)])
        self.assertEqual(receipt['state'], 'COMPLETE')
        self.assertEqual(receipt['lines'], 4)
        self.assertEqual(rows[0]['topic'], topic)
        self.assertEqual(rows[0]['payload'], payload.decode('ascii'))
        self.assertEqual(rows[1]['topic'], pr_topic)
        self.assertEqual(rows[1]['payload'], pr.decode('ascii'))
        self.assertIsInstance(rows[0]['ts_ms'], int)

    def test_subscription_rejection_stops(self):
        receipt, rows = self.record(SimulatedClient(rejected=True))
        self.assertEqual(receipt['error'], 'SUBSCRIBE_REJECTED')
        self.assertEqual(rows, [])

    def test_unexpected_topic_is_not_written(self):
        for topic in (r85.BASE + '/NODE-D/status', r85.BASE + '/NODE-B/event',
                      r85.BASE + '/NODE-A/telemetry/pr/extra', 'NODE-A/status',
                      'mpm/v1/OTHER/NODE-B/status'):
            with self.subTest(topic=topic):
                receipt, rows = self.record(SimulatedClient([(topic, b'{}')]))
                self.assertEqual(receipt['error'], 'UNEXPECTED_TOPIC')
                self.assertEqual(rows, [])


if __name__ == '__main__':
    unittest.main()
