"""隔离诊断只解析TCP头；地址、端口和任意原始行不得进入报告。"""
import json
from cloud.deploy.h3.tcp_metadata import Trace, socket_snapshot


def test_flows_directions_repeated_data_and_redaction():
    trace = Trace()
    prefix = '1792000000.100001 '
    up = 'IP 192.0.2.7.45678 > 198.51.100.9.8884: Flags [P.], seq 100:200, ack 800, win 10, length 100'
    trace.accept(prefix + up)
    trace.accept(prefix + up)
    trace.accept(prefix + 'eth0  Out  IP 198.51.100.9.8884 > 192.0.2.7.45678: Flags [.], ack 200, win 10, length 0')
    trace.accept(prefix + 'lo In IP 127.0.0.1.45679 > 127.0.0.1.8884: Flags [S], seq 42, win 10, length 0')
    result = trace.result()
    assert len(result['flows']) == 2
    assert result['flows'][0]['repeated_segments'] == 1
    assert [e['direction'] for e in result['events']] == ['UP', 'UP', 'DOWN', 'UP']
    assert result['flows'][1]['side'] == 'LOCAL'
    encoded = json.dumps(result)
    for literal in ('192.0.2.', '198.51.100.', '127.0.0.', '45678', '45679'):
        assert literal not in encoded


def test_unrelated_and_malformed_lines_are_ignored():
    trace = Trace()
    for line in ('arbitrary sensitive raw text',
                 '1.0 IP 192.0.2.1.123 > 198.51.100.1.443: Flags [.], ack 20, length 0'):
        trace.accept(line)
    assert trace.result()['events'] == []


def test_local_public_address_connection_is_not_remote(monkeypatch):
    from types import SimpleNamespace
    text=('ESTAB 0 0 198.51.100.9:8884 198.51.100.9:45670\n'
          ' rto:204 rtt:3.9/0.1 bytes_retrans:0 retrans:0/0\n'
          'ESTAB 0 0 198.51.100.9:8884 192.0.2.7:45671\n'
          ' rto:400 rtt:120.0/30.0 bytes_retrans:99 retrans:0/3\n')
    monkeypatch.setattr('cloud.deploy.h3.tcp_metadata.subprocess.run',lambda *a,**k:SimpleNamespace(returncode=0,stdout=text))
    rows=socket_snapshot()['connections']
    assert [r['side'] for r in rows]==['LOCAL','REMOTE']
    assert rows[1]['bytes_retrans']=='99'
