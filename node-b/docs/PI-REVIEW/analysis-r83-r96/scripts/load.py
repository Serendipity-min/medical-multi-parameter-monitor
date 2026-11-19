"""R83 MQTT 录制解析：拼接 ECG(250 Hz)/RESP(50 Hz) 滤波波形，换算回 bio_v2 内部量纲。只读。"""
import json, sys, datetime

TZ = datetime.timezone(datetime.timedelta(hours=8))
UV_PER_Y = 0.11920928955 * 126877696 / 209715175   # ecg_filtered=h*0.1192；uV=display*0.605
Y_PER_RESP_REL = 1000.0 / 0.11920928955            # rel=resp_filtered/1000 → r=resp_filtered/0.1192


def hms(ms):
    return datetime.datetime.fromtimestamp(ms / 1000, TZ).strftime('%H:%M:%S.%f')[:-3]


def load(path):
    ecg, resp, hr, rr = [], [], [], []
    for line in open(path, encoding='utf-8'):
        row = json.loads(line)
        p = json.loads(row['payload'])
        kind = row['topic'].rsplit('/', 1)[-1]
        if kind == 'ecg' or kind == 'resp':
            step = 1000.0 / p['sample_rate']
            dest = ecg if kind == 'ecg' else resp
            for i, v in enumerate(p['samples']):
                dest.append((p['timestamp'] + i * step, v, p['validity'] == 'VALID', p['seq']))
        elif kind == 'hr':
            hr.append((p['timestamp'], p['value'], p['validity']))
        elif kind == 'rr':
            rr.append((p['timestamp'], p['value'], p['validity']))
    for s in (ecg, resp, hr, rr):
        s.sort(key=lambda x: x[0])
    return ecg, resp, hr, rr


def gaps(series, step_ms, tol=1.6):
    out = []
    for a, b in zip(series, series[1:]):
        if b[0] - a[0] > step_ms * tol:
            out.append((a[0], b[0] - a[0]))
    return out


if __name__ == '__main__':
    ecg, resp, hr, rr = load(sys.argv[1])
    print('ECG samples', len(ecg), hms(ecg[0][0]), '→', hms(ecg[-1][0]), 'gaps>6ms', len(gaps(ecg, 4)))
    for t, d in gaps(ecg, 4)[:12]:
        print('  ecg gap at', hms(t), f'{d:.0f} ms')
    print('RESP samples', len(resp), hms(resp[0][0]), '→', hms(resp[-1][0]), 'gaps>32ms', len(gaps(resp, 20)))
    for t, d in gaps(resp, 20)[:12]:
        print('  resp gap at', hms(t), f'{d:.0f} ms')
