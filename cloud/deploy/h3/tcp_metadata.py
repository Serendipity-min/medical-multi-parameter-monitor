"""仅观察隔离8884的TCP头元数据；不保存地址、端口、TLS字节或监护载荷。"""
import json
import re
import selectors
import subprocess
import time
from datetime import datetime, timezone


class Trace:
    def __init__(self):
        self.flows = {}
        self.events = []

    def accept(self, line):
        # Linux any接口在方向前后可输出多个空格，不能把已采集数据静默漏掉。
        match = re.search(r'^(\d+\.\d+)\s+(?:\S+\s+(?:In|Out)\s+)?IP\s+(\S+) > (\S+): Flags \[([^]]*)\].*?length (\d+)', line)
        if not match:
            return
        stamp, src, dst, flags, size = match.groups()
        src_host, src_port = src.rsplit('.', 1)
        dst_host, dst_port = dst.rsplit('.', 1)
        if src_port != '8884' and dst_port != '8884':
            return
        up = dst_port == '8884'
        # 连接端点只用于进程内分组，不进入事件或结果文件。
        key = (src_host, src_port) if up else (dst_host, dst_port)
        flow = self.flows.setdefault(key, {'id': len(self.flows) + 1,
            'side': 'LOCAL' if key[0].startswith('127.') or src_host == dst_host else 'REMOTE',
            'seen': set(), 'up_bytes': 0, 'down_bytes': 0, 'repeated_segments': 0})
        seq = re.search(r'\bseq (\d+)(?::(\d+))?', line)
        ack = re.search(r'\back (\d+)', line)
        length = int(size)
        repeated = False
        if length and seq:
            mark = (up, int(seq[1]), int(seq[2] or seq[1]))
            repeated = mark in flow['seen']
            flow['seen'].add(mark)
            flow['repeated_segments'] += int(repeated)
        flow['up_bytes' if up else 'down_bytes'] += length
        self.events.append({'utc_epoch': float(stamp), 'flow': flow['id'],
            'side': flow['side'], 'direction': 'UP' if up else 'DOWN', 'flags': flags,
            'seq': int(seq[1]) if seq else None, 'seq_end': int(seq[2]) if seq and seq[2] else None,
            'ack': int(ack[1]) if ack else None, 'bytes': length, 'repeated_range': repeated})

    def result(self):
        return {'flows': [{k: v for k, v in flow.items() if k != 'seen'} for flow in self.flows.values()],
                'events': self.events, 'addresses_saved': False, 'payloads_saved': False}


def socket_snapshot():
    result = subprocess.run(['ss', '-tinH', 'sport = :8884'], capture_output=True, text=True)
    if result.returncode:
        raise RuntimeError('SOCKET_METADATA_UNAVAILABLE')
    records = []
    side = 'UNKNOWN'
    for line in result.stdout.splitlines():
        if 'rto:' not in line:
            endpoints = re.search(r'(\S+):8884\s+(\S+):\d+', line)
            # 同机服务可能经本机公网地址回连；不能只用127.0.0.1区分对照组。
            side = ('LOCAL' if endpoints and (endpoints[1] == endpoints[2] or
                    endpoints[2].startswith('127.')) else 'REMOTE' if endpoints else 'UNKNOWN')
            continue
        fields = {'side': side}
        for key in ('rto', 'rtt', 'ato', 'cwnd', 'bytes_sent', 'bytes_retrans', 'bytes_acked',
                    'bytes_received', 'segs_out', 'segs_in', 'data_segs_out', 'data_segs_in', 'retrans'):
            match = re.search(r'\b' + key + r':([0-9./]+)', line)
            if match:
                fields[key] = match[1]
        records.append(fields)
    return {'utc': datetime.now(timezone.utc).isoformat(), 'connections': records}


def observe(seconds=600):
    if not 30 <= seconds <= 1200:
        raise ValueError('BOUNDED_TRACE_REQUIRED')
    trace = Trace()
    # 不使用-w、不输出十六进制；过滤范围固定为隔离端口，原文仅在管道内存中。
    child = subprocess.Popen(['tcpdump', '-i', 'any', '-l', '-nn', '-tt', '-S',
        'ip and tcp port 8884'], stdout=subprocess.PIPE, stderr=subprocess.PIPE, bufsize=0)
    selector = selectors.DefaultSelector()
    selector.register(child.stdout, selectors.EVENT_READ)
    started = time.monotonic()
    snapshots = []
    next_snapshot = started
    try:
        while time.monotonic() - started < seconds:
            if time.monotonic() >= next_snapshot:
                snapshots.append(socket_snapshot())
                next_snapshot = time.monotonic() + 5
            if child.poll() is not None:
                raise RuntimeError('TRACE_EXITED')
            if selector.select(.2):
                line = child.stdout.readline()
                trace.accept(line.decode('ascii', errors='replace'))
    finally:
        child.terminate()
        # 结束时排空管道，保留tcpdump自身报告的内核丢包数，不把观察遗漏当网络丢包。
        rest, error = child.communicate(timeout=5)
        for line in rest.decode('ascii', errors='replace').splitlines():
            trace.accept(line)
        selector.close()
    dropped = re.search(rb'(\d+) packets dropped by kernel', error)
    result = trace.result()
    result['socket_snapshots'] = snapshots
    result.update(elapsed_s=round(time.monotonic()-started, 3),
        finished_utc=datetime.now(timezone.utc).isoformat(),
        capture_kernel_drops=int(dropped[1]) if dropped else None)
    result['exit_code'] = int(not result['events'] or result['capture_kernel_drops'] != 0)
    return result


if __name__ == '__main__':
    print(json.dumps(observe()))
