"""Paho 网络线程与 asyncio 状态层之间使用有界队列隔离。"""
import asyncio
import json
import os
import queue
import ssl
from pathlib import Path
import paho.mqtt.client as mqtt
from .adapters import decode_mqtt
from .diagnostics import EventLog

def configured_client(config: dict, client_id: str):
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=client_id,
                         protocol=mqtt.MQTTv311, clean_session=True)
    client.username_pw_set(config['username'], config['password'])
    context = ssl.create_default_context(cafile=config.get('ca_file') or None)
    context.minimum_version = ssl.TLSVersion.TLSv1_2
    client.tls_set_context(context)
    client.reconnect_delay_set(1, 15)
    client.max_queued_messages_set(256)
    client.max_inflight_messages_set(16)
    client.connect_timeout = 8
    return client

class MqttAdapter:
    def __init__(self, hub, config_path: str):
        self.hub = hub
        self.config = json.loads(Path(config_path).read_text(encoding='utf-8-sig'))
        self.pending = queue.Queue(maxsize=256)
        self.connected = False
        self.dropped = 0
        self.attempts = 0
        self.log = EventLog('backend', os.environ.get('MONITOR_LOG_DIR'))
        self.client = configured_client(self.config, self.config['client_id'])
        self.client.on_connect = self.on_connect
        self.client.on_disconnect = self.on_disconnect
        self.client.on_message = self.on_message
        self.client.on_subscribe = self.on_subscribe
        self.client.on_connect_fail = self.on_connect_fail

    def on_connect_fail(self, client, userdata):
        self.attempts += 1
        self.log.emit('mqtt_connect_failed', 'warning', attempts=self.attempts)

    def on_connect(self, client, userdata, flags, reason_code, properties):
        self.log.emit('mqtt_connected' if not reason_code.is_failure else 'mqtt_connect_failed',
                      'notice' if not reason_code.is_failure else 'warning', code=reason_code.value)
        if not reason_code.is_failure:
            topics = []
            for gateway in self.hub.gateways:
                base = f'mpm/v1/{gateway}'
                topics.extend((base + suffix, 1) for suffix in
                              ['/status', '/+/status', '/+/telemetry/+', '/+/replay/+', '/+/event'])
            client.subscribe(topics)

    def on_subscribe(self, client, userdata, mid, reason_codes, properties):
        self.connected = bool(reason_codes) and all(not code.is_failure for code in reason_codes)
        self.log.emit('mqtt_subscribed', 'notice' if self.connected else 'warning', code=0 if self.connected else 1)

    def on_disconnect(self, client, userdata, flags, reason_code, properties):
        self.connected = False
        self.log.emit('mqtt_disconnected', 'warning', code=reason_code.value)
        # 重连期间丢弃队列旧消息，避免旧 ONLINE 延迟复活设备。
        while True:
            try:
                self.pending.get_nowait()
            except queue.Empty:
                break

    def on_message(self, client, userdata, message):
        try:
            if len(message.payload) > 32768:
                self.dropped += 1
                return
            self.pending.put_nowait((message.topic, bytes(message.payload)))
        except queue.Full:
            self.dropped += 1

    async def run(self):
        self.client.connect_async(self.config['host'], self.config.get('port', 8883), keepalive=15)
        self.client.loop_start()
        next_metrics = 0.0
        try:
            while True:
                self.hub.broker_connected = self.connected
                now = asyncio.get_running_loop().time()
                if now >= next_metrics:
                    # 每分钟保留状态计数；不逐条记录遥测载荷，避免高频写盘。
                    self.log.emit('mqtt_metrics', accepted=self.hub.accepted, rejected=self.hub.rejected,
                                  dropped=self.dropped, queue_depth=self.pending.qsize(), attempts=self.attempts)
                    next_metrics = now + 60
                for _ in range(64):
                    try:
                        topic, payload = self.pending.get_nowait()
                    except queue.Empty:
                        break
                    try:
                        self.hub.ingest(decode_mqtt(topic, payload))
                    except (ValueError, TypeError, UnicodeError):
                        # 不记录可能含设备数据或凭据的载荷和异常详情。
                        self.hub.rejected += 1
                await asyncio.sleep(.025)
        finally:
            self.hub.broker_connected = False
            self.client.disconnect()
            await asyncio.to_thread(self.client.loop_stop)
            self.log.emit('backend_stopped')
            self.log.close()
