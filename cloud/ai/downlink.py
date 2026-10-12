"""专用 voice/reply 协议：有界 UTF-8、短寿命、QoS1；PUBACK 仅表示 Broker 接收。"""
import asyncio
import re
import struct
import threading
import time

HEADER = struct.Struct('!4sQQ16s16sH')
MAX_TEXT = 240
TTL_MS = 15000


def short_text(text: str) -> str:
    # 禁止 TW-TTS 内嵌控制标签及控制字符，截断只落在完整字符边界。
    if any(ord(c) < 32 or ord(c) == 127 or c in '[]' for c in text):
        raise ValueError('VOICE_TEXT')
    raw = text.encode('utf-8', errors='strict')
    return raw[:MAX_TEXT].decode('utf-8', errors='ignore')


def encode(turn_id: str, fact_digest: str, text: str, issued_ms: int) -> bytes:
    if not re.fullmatch('[0-9a-f]{32}', turn_id) or not re.fullmatch('[0-9a-f]{32}', fact_digest):
        raise ValueError('VOICE_ID')
    raw = short_text(text).encode()
    if not raw:
        raise ValueError('VOICE_EMPTY')
    return HEADER.pack(b'P6V1', issued_ms, issued_ms + TTL_MS, bytes.fromhex(turn_id), bytes.fromhex(fact_digest), len(raw)) + raw


def decode(payload: bytes, now_ms: int) -> dict:
    if not HEADER.size < len(payload) <= HEADER.size + MAX_TEXT:
        raise ValueError('VOICE_SIZE')
    magic, issued, expires, turn, provenance, length = HEADER.unpack(payload[:HEADER.size])
    if magic != b'P6V1' or length != len(payload) - HEADER.size or not issued <= now_ms + 1000 or not now_ms < expires or not 0 < expires - issued <= TTL_MS:
        raise ValueError('VOICE_FRAME')
    text = payload[HEADER.size:].decode('utf-8', errors='strict')
    if text != short_text(text):
        raise ValueError('VOICE_TEXT')
    return dict(turn_id=turn.hex(), fact_digest=provenance.hex(), text=text, issued_ms=issued, expires_ms=expires)


class SimulatedGateway:
    def __init__(self, gateway: str):
        self.topic = f'mpm/v1/{gateway}/voice/reply'
        self.last_issued = 0
        self.ids: list[str] = []

    def receive(self, topic: str, payload: bytes, qos: int, retain: bool, now_ms: int) -> dict:
        if topic != self.topic or qos != 1 or retain:
            raise ValueError('VOICE_AUTHORITY')
        message = decode(payload, now_ms)
        if message['turn_id'] in self.ids or message['issued_ms'] <= self.last_issued:
            raise ValueError('VOICE_REPLAY')
        if self.last_issued and message['issued_ms'] - self.last_issued < 5000:
            raise ValueError('VOICE_RATE')
        self.last_issued = message['issued_ms']
        self.ids = (self.ids + [message['turn_id']])[-8:]
        return dict(message, status='SIMULATED_DOWNLINK')


class IsolatedPublisher:
    def __init__(self, port: int, username: str, password: str):
        if not 1024 < port <= 65535 or not username or not password:
            raise ValueError('ISOLATED_MQTT_CONFIG')
        self.port, self.username, self.password = port, username, password
        self.lock = asyncio.Lock()
        self.last_sent = 0.0

    async def publish(self, gateway: str, payload: bytes) -> str:
        if gateway not in ('GW-C-001', 'GW-DEV-001'):
            raise ValueError('VOICE_DEVICE')
        async with self.lock:
            if time.monotonic() - self.last_sent < 5:
                return 'RATE_LIMITED'
            self.last_sent = time.monotonic()
            await asyncio.to_thread(self._send, f'mpm/v1/{gateway}/voice/reply', payload)
        return 'BROKER_PUBACK_ONLY'

    def _send(self, topic: str, payload: bytes):
        import paho.mqtt.client as mqtt
        connected = threading.Event()
        accepted = []
        client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, protocol=mqtt.MQTTv311)
        client.username_pw_set(self.username, self.password)
        def on_connect(_client, _userdata, _flags, reason, _properties):
            accepted.append(not reason.is_failure)
            connected.set()
        client.on_connect = on_connect
        # 本轮仅允许进程自有的 loopback Broker；不得把环境变量当作生产目标授权。
        try:
            client.connect('127.0.0.1', self.port, keepalive=15)
            client.loop_start()
            if not connected.wait(2) or not accepted or not accepted[0]:
                raise RuntimeError('ISOLATED_MQTT_CONNECT')
            info = client.publish(topic, payload, qos=1, retain=False)
            info.wait_for_publish(timeout=2)
            if info.rc or not info.is_published():
                raise RuntimeError('ISOLATED_MQTT_PUBACK')
        finally:
            client.disconnect()
            client.loop_stop()
