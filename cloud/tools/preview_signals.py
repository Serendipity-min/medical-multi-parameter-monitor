"""只供本机预览的确定性 MOCK 场景；数值变化与发送节奏不影响真实设备。"""
import math


# 间歇血压每 30 秒产生一组结果；其他标量按 1/2 秒更新，波形仍按 200ms 分包。
INTERVALS = {'NIBP': 30.0, 'TEMP': 2.0, 'HR': 1.0, 'PR': 1.0, 'RR': 1.0, 'SPO2': 1.0}
FIXED_VALUES = {'HR': 72.0, 'RR': 15.0, 'SPO2': 98.0, 'PR': 72.0, 'TEMP': 36.6, 'NIBP': [118.0, 76.0]}
BP_PAIRS = ((118.0, 76.0), (124.0, 80.0), (112.0, 72.0), (121.0, 78.0), (116.0, 74.0), (128.0, 82.0))


def scalar_value(stream, elapsed, fixed=False):
    """在该通道的采集时刻计算样例值；不预填任何浏览器历史。"""
    if fixed:
        return FIXED_VALUES.get(stream)
    if stream == 'NIBP':
        return list(BP_PAIRS[int(elapsed // INTERVALS['NIBP']) % len(BP_PAIRS)])
    if stream in ('HR', 'PR'):
        value = 74 + 11 * math.sin(2 * math.pi * elapsed / 41) + 4 * math.sin(2 * math.pi * elapsed / 13)
        if stream == 'PR':
            value += math.sin(2 * math.pi * elapsed / 17)
        return float(round(value))
    if stream == 'RR':
        return float(round(17 + 3 * math.sin(2 * math.pi * elapsed / 47) + math.sin(2 * math.pi * elapsed / 19)))
    if stream == 'SPO2':
        return float(round(97 + 1.4 * math.sin(2 * math.pi * elapsed / 34) + .6 * math.sin(2 * math.pi * elapsed / 13)))
    if stream == 'TEMP':
        return round(36.6 + .45 * math.sin(2 * math.pi * elapsed / 67) + .15 * math.sin(2 * math.pi * elapsed / 23), 1)
    return None


def _phase(t, baseline, components):
    # 对缓慢变化的频率积分，避免更新心率/呼吸率时波形相位突然跳变。
    result = baseline * t / 60
    for amplitude, period in components:
        omega = 2 * math.pi / period
        result += amplitude * (1 - math.cos(omega * t)) / (60 * omega)
    return result


def waveform(stream, end_time, fixed=False):
    rate = 250 if stream == 'ECG' else 50
    samples = []
    for i in range(rate // 5):
        t = end_time - .2 + (i + 1) / rate
        cardiac = (t * 1.2 if fixed else _phase(t, 74, ((11, 41), (4, 13)))) % 1
        drift = .015 * math.sin(2 * math.pi * t / 7)
        if stream == 'ECG':
            value = (.10 * math.exp(-((cardiac - .12) / .045) ** 2)
                     + math.exp(-((cardiac - .28) / .018) ** 2)
                     - .22 * math.exp(-((cardiac - .32) / .02) ** 2)
                     + .20 * math.exp(-((cardiac - .56) / .10) ** 2) + drift)
        elif stream == 'PPG':
            value = ((math.exp(-((cardiac - .35) / .16) ** 2)
                      + .20 * math.exp(-((cardiac - .65) / .10) ** 2))
                     * (1 + .08 * math.sin(t / 4)) + drift)
        else:
            respiratory = t * .25 if fixed else _phase(t, 17, ((3, 47), (1, 19)))
            value = .8 * math.sin(2 * math.pi * respiratory) + .035 * math.sin(4 * math.pi * respiratory)
        samples.append(round(value, 5))
    return {'sample_rate': rate, 'samples': samples}


class PreviewTimeline:
    def __init__(self):
        self.sent = {}

    def capture(self, stream, elapsed, signature=None):
        """每个采集时间槽最多发送一次；故障控制变化可立即发出新状态。"""
        interval = INTERVALS.get(stream, .2)
        bucket = int((elapsed + 1e-7) // interval)
        key = (bucket, signature)
        if self.sent.get(stream) == key:
            return None
        self.sent[stream] = key
        return bucket * interval
