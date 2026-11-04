"""单事件循环内维护状态；逐流去重、过期，补传与当前读数分开。"""

import asyncio
import time
from .models import Telemetry, CHANNELS, NODE_PROFILE


class Hub:
    # Hub 只由 asyncio 事件循环读写；注入两种时钟便于独立验证采集时间与接收过期。
    def __init__(self, gateways: list[str], clock=time.time, monotonic=time.monotonic, *, wave_batches=False):
        self.wave_batches = wave_batches
        self.gateways = gateways
        self.clock, self.monotonic = clock, monotonic
        self.current: dict[tuple, tuple[Telemetry, float]] = {}
        # 网关会话变化是整机重启边界；记录接收代次，避免新ONLINE重新激活旧节点/读数。
        # 两个字典均按已配置网关和current固定通道有界，不创建后台任务或无限历史。
        self.gateway_generation: dict[str, int] = {}
        self.current_generation: dict[tuple, int] = {}
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
            if (message.stream == 'GATEWAY_STATUS' and previous
                    and message.session_id != previous[0].session_id):
                self.gateway_generation[message.gateway_id] = self.gateway_generation.get(message.gateway_id, 0) + 1
            self.current[key] = (message, self.monotonic())
            self.current_generation[key] = self.gateway_generation.get(message.gateway_id, 0)
        self.accepted += 1
        if self.wave_batches and message.source != 'REPLAY' and message.stream in ('ECG', 'RESP', 'PPG'):
            self.publish(message.gateway_id)
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
            self.current_generation.get((gateway, node, stream), 0) != self.gateway_generation.get(gateway, 0)
            or message.validity != 'VALID'
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
            node_state = self._state(gateway, node)
            # 缺席/明确OFFLINE的节点不能因网关陈旧变为STALE；只有原在线节点继承网关不可用状态。
            state = node_state if node_state == 'OFFLINE' or gateway_state == 'ONLINE' else gateway_state
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
                    self.current_generation.get((gateway, node, name), 0) != self.gateway_generation.get(gateway, 0)
                    or (status := self.current.get((gateway, node, 'NODE_STATUS')))
                    and message.session_id != status[0].session_id
                ):
                    # 节点新Boot-up已反映到状态流后，旧会话高seq/延迟帧也不能借新ONLINE续活。
                    # 只收紧输出，不改采集timestamp；同值的新测量必须凭当前会话重新到达。
                    data['validity'] = 'STALE'
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
            'node_profile': NODE_PROFILE,
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

    def publish(self, only_gateway=None):
        snapshots = {}
        for queue, gateway in tuple(self.subscribers.items()):
            if only_gateway is not None and gateway != only_gateway:
                continue
            if gateway not in snapshots:
                snapshots[gateway] = self.snapshot(gateway)
            # 慢浏览器只保留最新快照，不能阻塞 MQTT 或增长内存。
            if queue.full():
                if self.wave_batches:
                    # 波形客户端来不及消费时明确关闭，不能静默覆盖有效批次。
                    self.subscribers.pop(queue)
                    while not queue.empty():
                        queue.get_nowait()
                    queue.put_nowait(None)
                    continue
                queue.get_nowait()
            queue.put_nowait(snapshots[gateway])
