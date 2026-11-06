"""P1原件只读预算/真实帧回放；不连接串口、调试器、网络或服务。"""
import argparse
import ctypes as c
from collections import Counter, defaultdict
from decimal import Decimal
import hashlib
import json
from pathlib import Path
import re
import statistics
import subprocess

ROOT = Path(__file__).resolve().parents[2]
BASE = 'e8804f8a8092a38a8a5ff9be2f7162dfbcd091e3'
STREAMS = ['ppg', 'spo2', 'pr', 'nibp', 'ecg', 'hr', 'resp', 'rr', 'temp', 'node_status', 'fault', 'gateway_status']
SCALES = [1000000, 100, 100, 10, 1000, 100, 1000000, 100, 100, 1, 1, 1]


class Frame(c.Structure):
    _fields_ = [('timestamp', c.c_uint64), ('seq', c.c_uint32), ('epoch', c.c_uint32),
                ('boot', c.c_uint32), ('values', c.c_int32 * 100), ('count', c.c_uint16),
                ('rate', c.c_uint16), ('node', c.c_uint8), ('stream', c.c_uint8),
                ('valid', c.c_bool), ('synthetic', c.c_bool), ('replay', c.c_bool)]


def fields(frame):
    return (frame.timestamp, frame.seq, frame.epoch, frame.boot, tuple(frame.values[:frame.count]),
            frame.count, frame.rate, frame.node, frame.stream, frame.valid, frame.synthetic, frame.replay)


def decode(row):
    raw = bytes.fromhex(row['payload_hex'])
    d = json.loads(raw, parse_float=Decimal)
    topic = row['topic'].split('/')
    stream = topic[-1]
    if stream == 'status':
        stream = 'node_status' if topic[-2].startswith('NODE-') else 'gateway_status'
    if stream == 'event':
        stream = 'fault'
    f = Frame()
    f.timestamp, f.seq = d['timestamp'], d['seq']
    _, epoch, boot = d['session_id'].split('-')
    f.epoch, f.boot = int(epoch), int(boot)
    f.node = ord(topic[-3][-1]) - ord('A') + 1 if stream not in ('node_status', 'gateway_status', 'fault') else 0
    if stream in ('node_status', 'fault'):
        f.node = ord(topic[-2][-1]) - ord('A') + 1
    f.stream = STREAMS.index(stream)
    f.rate = d.get('sample_rate', 0)
    f.valid, f.synthetic, f.replay = d['validity'] == 'VALID', d['synthetic'], d['source'] == 'REPLAY'
    if f.rate:
        values = d['samples']
    elif stream in ('node_status', 'gateway_status'):
        values = [1 if d['value'] == 'ONLINE' else 0]
    elif stream == 'fault':
        values = [int(d['value'][5:], 16)]
    elif stream == 'nibp' and d['value'] is not None:
        values = d['value']
    else:
        values = [d['value']] if d['value'] is not None else []
    f.count = len(values)
    for i, v in enumerate(values):
        scaled = Decimal(str(v)) * (1 if stream in ('node_status', 'gateway_status', 'fault') else SCALES[f.stream])
        assert scaled == scaled.to_integral_value(), 'NON_FIXED_POINT_SOURCE'
        f.values[i] = int(scaled)
    # MQTT包长：固定头/RemainingLength、Topic、可选QoS1标识与真实JSON字节。
    qos1 = not f.rate or f.replay
    remaining = 2 + len(row['topic'].encode()) + (2 if qos1 else 0) + len(raw)
    n, width = remaining, 1
    while n >= 128:
        n //= 128
        width += 1
    return f, len(raw), 1 + width + remaining


def load_dll(path):
    dll = c.CDLL(str(path))
    assert dll.p1_frame_bytes() == c.sizeof(Frame), 'FRAME_ABI_MISMATCH'
    dll.p1_put.argtypes = [c.POINTER(Frame), c.c_uint32, c.c_uint64]
    dll.p1_take.argtypes = [c.POINTER(Frame), c.c_uint32, c.c_uint64, c.c_int]
    return dll


def replay(rows, dll):
    dll.p1_init()
    waves, points, mismatches = 0, Counter(), 0
    previous = 0
    # 按原始Broker收包顺序逐帧通过Router；这是幸存者控制，不冒充C全量入站。
    for row in rows:
        assert row['arrival_unix_ns'] >= previous, 'BROKER_ORDER_REVERSED'
        previous = row['arrival_unix_ns']
        f, _, _ = decode(row)
        if not f.rate:
            continue
        now = row['arrival_unix_ns'] // 1000000
        dll.p1_put(c.byref(f), now & 0xffffffff, now)
        out = Frame()
        assert dll.p1_take(c.byref(out), now & 0xffffffff, now, 1)
        mismatches += fields(f) != fields(out)
        waves += 1
        points[STREAMS[f.stream]] += f.count
    # 将真实PPG幸存批组成有空位的短突发；时间安排为合成压力，点值/身份取自原件。
    pp = [decode(row)[0] for row in rows if '/telemetry/ppg' in row['topic']][:12]
    assert len(pp) == 12
    dll.p1_init()
    current = max(f.timestamp for f in pp)
    for f in pp:
        dll.p1_put(c.byref(f), 10000, current)
    live, replaced = dll.p1_counter(0), dll.p1_counter(2)
    returned = []
    out = Frame()
    while dll.p1_take(c.byref(out), 10000, current, 1):
        returned.append(fields(out))
    return dict(observed_wave_batches=waves, observed_wave_points=dict(points), field_mismatches=mismatches,
                PPG_recorded_payload_synthetic_burst=dict(input=12, live=live, replaced=replaced,
                    FIFO_identity_equal=returned == [fields(f) for f in pp]))


def assess(job, before, after):
    evidence = {}
    for relative in ('T0.json', 'C-observation/lines-private.jsonl', 'receiver/MQTT-private.jsonl'):
        blob = (job / relative).read_bytes()
        evidence[relative] = dict(bytes=len(blob), sha256=hashlib.sha256(blob).hexdigest())
    t0 = json.loads((job / 'T0.json').read_text())
    low, high = t0['UTC_ms'], t0['UTC_ms'] + 300000
    serial = [json.loads(x) for x in (job / 'C-observation/lines-private.jsonl').read_text().splitlines()]
    rows = [json.loads(x) for x in (job / 'receiver/MQTT-private.jsonl').read_text().splitlines()]
    rows = [x for x in rows if not x['retain'] and low <= json.loads(bytes.fromhex(x['payload_hex']))['timestamp'] < high]
    groups, packets, payloads = defaultdict(list), defaultdict(list), defaultdict(list)
    for row in rows:
        f, payload, packet = decode(row)
        groups[STREAMS[f.stream]].append(f)
        packets[STREAMS[f.stream]].append(packet)
        payloads[STREAMS[f.stream]].append(payload)
    def records(prefix):
        return [(x['UTC_ms'], {k: int(v) for k, v in re.findall(r'(\w+)=(\d+)', x['text'])})
                for x in serial if low <= x['UTC_ms'] < high and x['text'].startswith(prefix)]
    diag = records('B5 DIAG ')
    begin, end = diag[0], diag[-1]
    seconds = (end[1]['tick'] - begin[1]['tick']) / 1000
    q0 = end[1]['q0_transport'] - begin[1]['q0_transport']
    q1 = end[1]['q1_puback'] - begin[1]['q1_puback']
    offered = {}
    intervals = {}
    for name in ('ecg', 'resp', 'hr', 'rr', 'temp'):
        entries = records('B5 FLOW stream=' + str(STREAMS.index(name)) + ' ')
        offered[name] = entries[-1][1]['put'] - entries[0][1]['put']
        intervals[name] = (entries[-1][0] - entries[0][0]) / 1000
    # emit按节点/流递增seq。相同session内两个幸存seq之间的跨度，是已出批数量的下界。
    for name in ('ppg', 'spo2', 'pr'):
        sessions = defaultdict(list)
        for f in groups[name]:
            sessions[f.epoch, f.boot].append(f.seq)
        assert len(sessions) == 1, 'A_SESSION_CHANGED'
        seqs = next(iter(sessions.values()))
        assert max(seqs) - min(seqs) < 0x80000000
        offered[name] = max(seqs) - min(seqs) + 1
        intervals[name] = 300
    offered['node_status'] = len(groups['node_status'])
    offered['gateway_status'] = len(groups['gateway_status'])
    offered['nibp'] = len(groups['nibp'])
    for name in ('node_status', 'gateway_status', 'nibp'):
        intervals[name] = 300
    rates = {k: offered[k] / intervals[k] for k in offered}
    demand = sum(rates.values())
    service = (q0 + q1) / seconds
    sizes = {k: dict(count=len(v), min=min(v), mean=statistics.mean(v), max=max(v)) for k, v in packets.items()}
    projected = sum(rate * sizes[k]['mean'] for k, rate in rates.items())
    latencies = {str(i): records('B5 LAT stage=' + str(i) + ' ')[-1][1] for i in range(9)}
    queue = records('B5 QUEUE ')
    stream_bytes = sum(sum(v) for v in packets.values())
    io_rows = records('B5 IO ')
    return dict(scope='READ_ONLY_RECORDED_BROKER_ORDER_AND_C_COUNTERS_NOT_FULL_C_INGRESS', input_evidence=evidence,
        before=replay(rows, before), after=replay(rows, after),
        observed_service=dict(interval_s=seconds, diagnostic_observations=len(diag), Q0=q0, Q1_puback=q1, frames_per_s=service,
            live_min=min(x[1]['live'] for x in diag), live_max=max(x[1]['live'] for x in diag),
            historical_evictions=end[1]['dropped']-begin[1]['dropped'],
            overflow=queue[-1][1]['overflow']-queue[0][1]['overflow'],
            MQTT_packet_bytes_source_window=stream_bytes, MQTT_bytes_per_s_source_window=stream_bytes/300),
        input_count_lower_bound=offered, input_counter_intervals_s=intervals, input_rates_per_s=rates,
        total_input_lower_bound_per_s=demand, observed_service_margin_per_s=service-demand,
        accumulated_deficit_300s=(demand-service)*300,
        packet_sizes=sizes, projected_input_MQTT_bytes_per_s=projected,
        projected_UART_115200_8N1_payload_fraction=projected/11520,
        byte_budget_note='Missing-frame sizes estimated from same-stream survivors; not directly measured missing payload bytes. AT commands/replies/ACK/polls extra.',
        actual_AT_MQTT_latency_buckets=latencies,
        actual_AT_tx_ms_periodic=dict(min=min(x[1]['tx_ms'] for x in io_rows), max=max(x[1]['tx_ms'] for x in io_rows)),
        replay_limitations=['No complete ordered C ingress capture, especially A UART/PPG.',
            'Broker rows are survivors; interarrival gaps include network/TLS/observer effects, not per-transaction AT timings.',
            'Invalid scalar hidden values cannot be recovered from null; only wave payload identity is asserted.',
            'A seq-span and B put counters prove produced volume, not missing payload values or exact within-bin order.',
            'No fabricated missing samples, sequence numbers, qualities, timestamps, or exact-field overflow count reproduction.'],
        capacity_result='INSUFFICIENT_OBSERVED_SERVICE_NO_FIELD_CANDIDATE' if service < demand else 'MARGIN_NOT_PROVEN_INCOMPLETE_INGRESS')


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--paths', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    args = p.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    paths = json.loads(args.paths.read_text())
    baseline = args.output / 'baseline'
    for relative in ('gateway/storage/router.c', 'gateway/storage/router.h', 'gateway/b5/egress.h', 'gateway/data_model/model.h',
                     'gateway/data_model/roles.h', 'gateway/b5/egress_metrics.h'):
        dst = baseline / relative
        dst.parent.mkdir(parents=True, exist_ok=True)
        dst.write_bytes(subprocess.check_output(['git', 'show', BASE + ':' + relative], cwd=ROOT))
    dlls = {}
    builds = {}
    unit_results = {}
    for version, source in [('before', baseline / 'gateway/storage/router.c'), ('after', ROOT / 'gateway/storage/router.c')]:
        dll = args.output / (version + '.dll')
        flags = ['C:/mingw64/bin/gcc.exe', '-shared', '-std=c11', '-O2', '-Wall', '-Wextra', '-Werror',
            '-DMP_FRAME_MAX_SAMPLES=100', '-DMP_LIVE_CAPACITY=24', '-DMP_CACHE_CAPACITY=56',
            '-DMP_B5_EGRESS_FINAL', '-DMP_B5_CLOUD_CANDIDATE', '-DMP_ABC_TRI_CANDIDATE', '-DMP_FIVE_NODE']
        r = subprocess.run([*flags, ROOT / 'gateway/b5/test_five_node_p1_bridge.c', source, '-o', dll], capture_output=True, timeout=60)
        (args.output / (version + '-compile.log')).write_bytes(r.stdout + r.stderr)
        assert r.returncode == 0, 'NATIVE_DLL_BUILD_FAILED'
        builds[version] = dict(native_exit=r.returncode, router_sha256=hashlib.sha256(source.read_bytes()).hexdigest())
        dlls[version] = load_dll(dll)
        exe = args.output / (version + '-unit.exe')
        unit_flags = [x for x in flags if x != '-shared'] + ['-DMP_FINAL_UNIFIED',
            '-I' + str(ROOT / 'gateway/b5'), '-I' + str(ROOT / 'gateway/mqtt/src')]
        if version == 'before':
            unit_flags += ['-DP1_EGRESS_HEADER="' + (baseline / 'gateway/b5/egress.h').as_posix() + '"']
        r = subprocess.run([*unit_flags, ROOT / 'gateway/b5/test_five_node_p1.c', source,
            ROOT / 'gateway/b5/b5_policy.c', '-o', exe], capture_output=True, timeout=60)
        (args.output / (version + '-unit-compile.log')).write_bytes(r.stdout + r.stderr)
        assert r.returncode == 0, 'UNIT_BUILD_FAILED'
        unit_results[version] = []
        for mode in ('fifo', 'history', 'deadline', 'publisher'):
            r = subprocess.run([exe, mode], capture_output=True, timeout=10)
            log = r.stdout + r.stderr
            (args.output / (version + '-' + mode + '.log')).write_bytes(log)
            unit_results[version].append(dict(case=mode, native_exit=r.returncode, log_sha256=hashlib.sha256(log).hexdigest()))
            assert (r.returncode == 0) == (version == 'after'), 'BEFORE_AFTER_EXPECTATION_FAILED'
    result = dict(base=BASE, script_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                  scope='P1_OFFLINE_ONLY', hardware_operations=0, network_operations=0,
                  builds=builds, unit_results=unit_results, windows={})
    for name, key in [('ECG60', 'ECG60_completed_job'), ('RR18', 'RR18_completed_job')]:
        result['windows'][name] = assess(Path(paths[key]), dlls['before'], dlls['after'])
        check = result['windows'][name]
        index = json.loads((ROOT / 'node-b/docs/FIVE-NODE-MIGRATION/FIVE41-20261106/FIELD-WINDOW-EVIDENCE-INDEX.json').read_text())
        assert all(v == index[name]['files'][k] for k, v in check['input_evidence'].items()), 'RECORDED_INPUT_HASH_CHANGED'
        assert check['before']['field_mismatches'] == check['after']['field_mismatches'] == 0
        assert check['after']['PPG_recorded_payload_synthetic_burst']['FIFO_identity_equal']
        print(name, result['windows'][name]['capacity_result'], flush=True)
    (args.output / 'result.json').write_text(json.dumps(result, indent=2) + '\n')


if __name__ == '__main__':
    main()
