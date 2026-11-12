"""确定性播报规则，使用采集时间判新鲜度、单调时间判持续和限频。"""

from collections import deque
from dataclasses import dataclass, field
from itertools import count
from statistics import median

from .models import Telemetry

GATEWAY = 'GW-C-001'
DISCLAIMER = '仅供参考，不构成医疗建议，如有不适请咨询医生'
NIBP_MAX_AGE_MS = 90_000
SCALAR_MAX_AGE_S = 5
SCALAR_MAX_AGE_MS = SCALAR_MAX_AGE_S * 1000
MEDIAN_WINDOW_S = 60
SUSTAINED_S = 120
TEMP_READY_S = 60
REPEAT_INTERVAL_S = 300
LATEST_MAX_AGE_MS = 600_000
HISTORY_SIZE = 10
SYS_LOW, DIA_LOW = 90, 60
SYS_HIGH_NORMAL, DIA_HIGH_NORMAL = 120, 80
SYS_HIGH, DIA_HIGH = 140, 90
SPO2_LOW = 90
PULSE_LOW, PULSE_HIGH = 60, 100
IDS = count(1)


def blood_pressure(systolic: float, diastolic: float) -> tuple[str, str]:
    if systolic < SYS_LOW or diastolic < DIA_LOW:
        return '偏低', 'notice'
    if systolic >= SYS_HIGH or diastolic >= DIA_HIGH:
        return '偏高', 'notice'
    if systolic >= SYS_HIGH_NORMAL or diastolic >= DIA_HIGH_NORMAL:
        return '正常高值', 'info'
    return '在一般参考范围内', 'info'


@dataclass
class Window:
    session: str
    started: float
    received: float
    timestamp: int
    samples: deque[tuple[float, float]] = field(default_factory=deque)
    outside_since: float | None = None


class BroadcastEngine:
    def __init__(self, clock, monotonic, *, hr=False):
        self.clock, self.monotonic = clock, monotonic
        self.params = {'NIBP', 'SPO2', 'PR', 'TEMP'}
        if hr:
            self.params.add('HR')
        self.windows: dict[str, Window] = {}
        self.history: deque[dict] = deque(maxlen=HISTORY_SIZE)
        self.emitted_at: dict[str, float] = {}
        self.last_nibp: tuple[str, int] | None = None
        self.gateway_session: str | None = None
        self.online_since: int | None = None

    def sync_gateway(self, online: Telemetry | None):
        if online is None or online.session_id != self.gateway_session:
            self.windows.clear()
            self.history.clear()
            self.gateway_session = online.session_id if online else None
            self.online_since = online.timestamp if online else None

    def expire_windows(self, now: float, now_ms: int):
        if any(now - w.received >= SCALAR_MAX_AGE_S or now_ms - w.timestamp >= SCALAR_MAX_AGE_MS
               for w in self.windows.values()):
            self.windows.clear()

    def ingest(self, message: Telemetry):
        param = message.stream
        if (param not in self.params or message.source != 'LIVE' or message.synthetic
                or self.online_since is None or message.timestamp < self.online_since):
            return
        now, now_ms = self.monotonic(), int(self.clock() * 1000)
        self.expire_windows(now, now_ms)
        age_ms = now_ms - message.timestamp
        if param == 'NIBP':
            result = (message.session_id, message.timestamp)
            if message.validity == 'VALID' and age_ms < NIBP_MAX_AGE_MS and result != self.last_nibp:
                self.last_nibp = result
                sys, dia = message.value
                label, level = blood_pressure(sys, dia)
                self.emit(param, level, f'本次血压约 {sys:g}/{dia:g} mmHg，{label}。建议静坐 5 分钟后复测。',
                          now, now_ms)
            return
        if age_ms >= SCALAR_MAX_AGE_MS or message.validity in ('STALE', 'OFFLINE'):
            self.windows.clear()
            return
        if message.validity != 'VALID':
            self.windows.pop(param, None)
            return

        window = self.windows.get(param)
        if (window is None or window.session != message.session_id
                or message.timestamp - window.timestamp >= SCALAR_MAX_AGE_MS):
            window = Window(message.session_id, now, now, message.timestamp)
            self.windows[param] = window
        elif message.timestamp <= window.timestamp:
            return
        window.timestamp, window.received = message.timestamp, now
        if param == 'TEMP':
            if now - window.started >= TEMP_READY_S:
                self.emit(param, 'info', f'当前体表温度约 {message.value:.1f} °C（体表温度低于体温，不作判断）。',
                          now, now_ms)
            return

        window.samples.append((now, message.value))
        while window.samples[0][0] <= now - MEDIAN_WINDOW_S:
            window.samples.popleft()
        if now - window.started < MEDIAN_WINDOW_S:
            return
        middle = median(value for _, value in window.samples)
        outside = middle < SPO2_LOW if param == 'SPO2' else not PULSE_LOW <= middle <= PULSE_HIGH
        if not outside:
            window.outside_since = None
        elif window.outside_since is None:
            window.outside_since = now
        elif now - window.outside_since >= SUSTAINED_S:
            text = {'SPO2': '请检查指夹佩戴后复测。', 'PR': '请静坐后复测脉率。', 'HR': '请静坐后复测心率。'}
            self.emit(param, 'notice', text[param], now, now_ms)

    def emit(self, param, level, text, now, now_ms):
        if param != 'NIBP':
            if now - self.emitted_at.get(param, float('-inf')) < REPEAT_INTERVAL_S:
                return
            self.emitted_at[param] = now
        self.history.appendleft({'id': str(next(IDS)), 'ts': now_ms, 'param': param, 'level': level,
                                 'text': text, 'disclaimer': DISCLAIMER})

    def fields(self, now_ms: int) -> dict:
        self.expire_windows(self.monotonic(), now_ms)
        history = [item.copy() for item in self.history]
        latest = history[0] if history and now_ms - history[0]['ts'] <= LATEST_MAX_AGE_MS else None
        return {'broadcast': latest, 'broadcast_history': history}
