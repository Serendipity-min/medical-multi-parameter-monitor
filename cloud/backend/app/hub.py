"""单事件循环内维护状态；逐流去重、过期，补传与当前读数分开。"""

import asyncio
import time
from .models import Telemetry, CHANNELS


class Hub:
    # Hub 只由 asyncio 事件循环读写；注入两种时钟便于独立验证采集时间与接收过期。
    def __init__(self, gateways: list[str], clock=time.time, monotonic=time.monotonic):
        self.gateways = gateways
        self.clock, self.monotonic = clock, monotonic
        self.current: dict[tuple, tuple[Telemetry, float]] = {}
        self.replays: dict[str, Telemetry] = {}
        self.events: dict[str, Telemetry] = {}
        self.subscribers: dict[asyncio.Queue, str] = {}
        self.broker_connected = False
        self.accepted = self.rejected = 0

    def ingest(self, message: Telemetry) -> bool:
        if (
            message.gateway_id not in self.gateways
            or message.timestamp > self.clock() * 1000 + 5000
        ):
            raise ValueError('gateway or future timestamp')
        if message.source == 'REPLAY':
            # 历史数据不能续活设备，也不能覆盖实时序列窗口。
            self.replays[message.gateway_id] = message
        elif message.stream == 'FAULT':
            self.events[message.gateway_id] = message
        else:
            key = (message.gateway_id, message.node_id, message.stream)
            previous = self.current.get(key)
            if previous:
                old = previous[0]
                # 同会话拒绝 QoS1 重复消息，新会话也不能用旧采集时间回退读数。
                # LWT 在 CONNECT 时预先生成，其时间早于最后心跳；只允许当前会话的 Will 下线。
                is_will = (
                    message.stream == 'GATEWAY_STATUS'
                    and message.value == 'OFFLINE'
                    and message.session_id == old.session_id
                )
                # 同一进程自动重连后 Will 的保留序号不能永久挡住新 ONLINE。
                recovering = (
                    message.stream == 'GATEWAY_STATUS'
                    and old.value == 'OFFLINE'
                    and message.value == 'ONLINE'
                    and message.timestamp > old.timestamp
                )
                if not (is_will or recovering) and (
                    message.timestamp < old.timestamp
                    or (message.session_id == old.session_id and message.seq <= old.seq)
                ):
                    return False
            self.current[key] = (message, self.monotonic())
        self.accepted += 1
        return True

    def _state(self, gateway: str, node: str) -> str:
        stream = 'GATEWAY_STATUS' if node == 'GATEWAY' else 'NODE_STATUS'
        entry = self.current.get((gateway, node, stream))
        if not self.broker_connected or not entry:
            return 'OFFLINE'
        message, received = entry
        if message.value == 'OFFLINE' or message.validity == 'OFFLINE':
            return 'OFFLINE'
        if (
            message.validity != 'VALID'
            or self.monotonic() - received > 15
            or self.clock() * 1000 - message.timestamp > 15000
        ):
            return 'STALE'
        return 'ONLINE'

    # 返回快照副本时派生过期状态，不改写原消息；实时值、历史补传和事件分别输出。
    def snapshot(self, gateway: str) -> dict:
        gateway_state = self._state(gateway, 'GATEWAY')
        nodes, streams = {}, []
        for node, names in CHANNELS.items():
            state = self._state(gateway, node) if gateway_state == 'ONLINE' else gateway_state
            nodes[node] = state
            for name in sorted(names):
                entry = self.current.get((gateway, node, name))
                if not entry:
                    continue
                message, received = entry
                data = message.model_dump()
                limit = 90 if name == 'NIBP' else 5
                if state != 'ONLINE':
                    data['validity'] = 'OFFLINE' if state == 'OFFLINE' else 'STALE'
                elif (
                    self.monotonic() - received > limit
                    or self.clock() * 1000 - message.timestamp > limit * 1000
                ):
                    data['validity'] = 'STALE'
                if data['validity'] != 'VALID':
                    data['value'], data['samples'] = None, []
                streams.append(data)
        replay, event = self.replays.get(gateway), self.events.get(gateway)
        return {
            'type': 'snapshot',
            'schema_version': 1,
            'gateway_id': gateway,
            'gateways': self.gateways,
            'gateway_state': gateway_state,
            'broker_connected': self.broker_connected,
            'nodes': nodes,
            'server_time': int(self.clock() * 1000),
            'streams': streams,
            'replay': replay.model_dump() if replay else None,
            'event': event.model_dump() if event else None,
        }

    def publish(self):
        snapshots = {}
        for queue, gateway in tuple(self.subscribers.items()):
            if gateway not in snapshots:
                snapshots[gateway] = self.snapshot(gateway)
            # 慢浏览器只保留最新快照，不能阻塞 MQTT 或增长内存。
            if queue.full():
                queue.get_nowait()
            queue.put_nowait(snapshots[gateway])
