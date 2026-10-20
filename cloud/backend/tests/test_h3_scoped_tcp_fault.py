"""丢包试验必须唯一命中现场隔离连接；零个/多个候选都不得猜测或扩大范围。"""
import ipaddress
import pytest
from cloud.deploy.h3.scoped_tcp_fault import select_peer_port


def test_selects_only_existing_field_connection():
    peer=ipaddress.ip_address('192.0.2.5')
    lines=('0 0 198.51.100.1:8884 192.0.2.5:12345\n'
           '0 0 198.51.100.1:8884 127.0.0.1:12346\n'
           '0 0 198.51.100.1:8883 192.0.2.5:12347\n')
    assert select_peer_port(lines,peer)==12345
    for text in ('',lines+lines):
        with pytest.raises(ValueError,match='EXACTLY_ONE'):select_peer_port(text,peer)
