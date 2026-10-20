"""固定合成日志验证隔离Broker探针只保留必要的报文元数据。"""
import json
from cloud.deploy.h3.broker_probe import classify


def test_publish_and_puback_keep_only_metadata():
    line="Received PUBLISH from synthetic-gateway (d0, q1, r0, m42, 'private-topic', ... (251 bytes))"
    assert classify(line,'synthetic-gateway')=={'event':'publish_received','qos':1,'mid':42,'bytes':251}
    assert classify('Sending PUBACK to synthetic-gateway (m42, rc0)','synthetic-gateway')=={'event':'puback_sent','mid':42}
    assert 'private-topic' not in json.dumps(classify(line,'synthetic-gateway'))


def test_unrelated_clients_and_connection_details_are_discarded():
    assert classify('New connection from 192.0.2.10:555 on port 8884.','synthetic-gateway') is None
    assert classify("Received PUBLISH from another-client (d0, q1, r0, m42, 'x', ... (20 bytes))",'synthetic-gateway') is None
    assert classify('random binary or unknown broker detail','synthetic-gateway') is None
