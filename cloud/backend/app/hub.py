"""单进程内存状态，LIVE 与 REPLAY 完全分离，不持久化医疗记录。"""

import asyncio
import time
from .models import Frame


class Hub:
    def __init__(self, gateway_id: str, stale_seconds: float = 5):
        self.gateway_id = gateway_id
        self.stale_seconds = stale_seconds
        self.owner: object | None = None
        self.live: Frame | None = None
        self.replay: Frame | None = None
        self.live_received = 0.0
        self.last_received = 0.0
        self.session_id: str | None = None
        self.last_seq = -1
        self.subscribers: set[asyncio.Queue] = set()

    def connect(self, owner: object) -> bool:
        if self.owner is not None:
            return False
        self.owner = owner
        # 新连接不得沿用上一连接的在线状态和序列窗口。
        self.last_received = self.live_received = 0.0
        self.session_id = None
        self.last_seq = -1
        self.publish()
        return True

    def disconnect(self, owner: object):
        if self.owner is owner:
            self.owner = None
            self.publish()

    def ingest(self, frame: Frame) -> bool:
        if frame.gateway_id != self.gateway_id:
            raise ValueError('gateway mismatch')
        if self.session_id is not None and self.session_id != frame.session_id:
            raise ValueError('session cannot change within connection')
        if frame.captured_at > time.time() + self.stale_seconds:
            raise ValueError('future acquisition time')
        if frame.seq <= self.last_seq:
            return False
        self.session_id, self.last_seq = frame.session_id, frame.seq
        self.last_received = time.monotonic()
        if frame.mode == 'LIVE':
            self.live, self.live_received = frame, self.last_received
        else:
            self.replay = frame
        self.publish()
        return True

    def snapshot(self) -> dict:
        now = time.monotonic()
        online = self.owner is not None and self.last_received > 0 and now - self.last_received <= self.stale_seconds
        live_fresh = bool(online and self.live_received > 0 and
                          now - self.live_received <= self.stale_seconds and self.live and
                          time.time() - self.live.captured_at <= self.stale_seconds)
        live = self.live.model_dump() if self.live else None
        if live:
            for node in live['nodes'].values():
                node['online'] = node['online'] and live_fresh
                for signal in node['signals'].values():
                    if not node['online']:
                        signal['quality'] = 'STALE'
                    # 所有无效/过期数据在服务端就清空，前端不得显示旧正常值。
                    if signal['quality'] != 'VALID':
                        signal['value'], signal['samples'] = None, []
        return {'protocol': 'MVIEW/1', 'simulation': True,
                'gateway_id': self.gateway_id, 'gateway_online': online,
                'live_fresh': live_fresh, 'server_time': time.time(), 'live': live,
                'replay': self.replay.model_dump() if self.replay else None}

    def publish(self):
        message = self.snapshot()
        for queue in tuple(self.subscribers):
            # 每个浏览器只保留最新快照；慢客户端不能阻塞采集或无限占用内存。
            if queue.full():
                queue.get_nowait()
            queue.put_nowait(message)
