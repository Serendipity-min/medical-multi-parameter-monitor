"""A2 实测：真实 AI HTTP 应用→真实 Mosquitto→模拟 Gateway；不触碰生产。"""
import argparse
import asyncio
import hashlib
import json
from pathlib import Path
import queue
import sys
import threading
import time
import uuid

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from fastapi.testclient import TestClient
import paho.mqtt.client as mqtt
from cloud.ai.app import Settings, create_app
from cloud.ai.downlink import IsolatedPublisher, SimulatedGateway, encode
from cloud.ai.tests.broker_runtime import BrokerRuntime


def main():
    parser = argparse.ArgumentParser(); parser.add_argument('--runtime', type=Path, required=True)
    args = parser.parse_args()
    out = ROOT / 'build/p6/evidence/isolated-a2'; broker = BrokerRuntime(args.runtime, out)
    messages = queue.Queue(); ready = threading.Event()
    subscriber = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, protocol=mqtt.MQTTv311)
    subscriber.username_pw_set('synthetic-gateway', broker.password)
    topic = 'mpm/v1/GW-C-001/voice/reply'
    subscriber.on_connect = lambda c, *_: c.subscribe(topic, qos=1)
    subscriber.on_subscribe = lambda *_: ready.set()
    subscriber.on_message = lambda _c, _u, m: messages.put((m.topic, m.payload, m.qos, m.retain))
    checks = []
    try:
        subscriber.connect('127.0.0.1', broker.port); subscriber.loop_start(); assert ready.wait(5)
        publisher = IsolatedPublisher(broker.port, 'synthetic-ai', broker.password)
        token = 'synthetic-ai-token-for-isolated-test'
        app = create_app(Settings(token, snapshot_mode='MOCK'), publisher=publisher)
        c = TestClient(app)
        response = c.post('/api/v1/text', headers={'Authorization': 'Bearer ' + token}, json={
            'session_id': uuid.uuid4().hex, 'gateway_id': 'GW-C-001', 'question': '现在心率多少', 'voice': True})
        assert response.status_code == 200
        answer = response.json(); assert answer['voice_status'] == 'BROKER_PUBACK_ONLY'
        wire = messages.get(timeout=5)
        sim = SimulatedGateway('GW-C-001'); received = sim.receive(*wire, int(time.time() * 1000))
        assert received['turn_id'] == answer['turn_id'] and received['fact_digest'] == answer['fact_digest'] and received['text'] == answer['voice_text']
        checks.append('HTTP_answer_and_SIMULATED_DOWNLINK_share_turn_and_facts')
        try: sim.receive(*wire, int(time.time() * 1000)); raise AssertionError('duplicate accepted')
        except ValueError: checks.append('duplicate_refused')
        assert asyncio.run(publisher.publish('GW-C-001', wire[1])) == 'RATE_LIMITED'
        checks.append('publisher_rate_bounded')
        subscriber.disconnect(); subscriber.loop_stop()
        messages = queue.Queue(); ready.clear()
        subscriber.connect('127.0.0.1', broker.port); subscriber.loop_start(); assert ready.wait(5)
        try: messages.get(timeout=.5); raise AssertionError('retained voice found')
        except queue.Empty: checks.append('late_subscriber_no_retained_voice')
        report = dict(result='PASS', exit_code=0, mode='MOCK', downlink='SIMULATED_DOWNLINK',
                      broker='Mosquitto 2.0.21 loopback', checks=checks, answer=answer, received=received,
                      wire_sha256=hashlib.sha256(wire[1]).hexdigest(), packet_bytes=len(wire[1]), cleanup='owned_process_stopped')
        (out / 'result.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
        print('A2 PASS', len(checks), 'SIMULATED_DOWNLINK, no speaker claim')
    finally:
        subscriber.disconnect(); subscriber.loop_stop(); broker.close()
    return 0


if __name__ == '__main__': raise SystemExit(main())
