"""隔离8884 Broker的有界元数据诊断：原文仅在管道内存中，不输出地址/Topic/载荷。"""
from datetime import datetime,timezone
import json
from pathlib import Path
import re
import signal
import subprocess
import sys

STATE=Path('/var/lib/medical-monitor-p6/h3-20261019')


def classify(text,gateway):
    # 仅提取指定测试Gateway的MQTT报文编号和大小；任何原始连接信息都不透传。
    name=re.escape(gateway)
    found=re.search(r'Received PUBLISH from '+name+r' \(d[01], q([012]), r[01], m(\d+),.*\((\d+) bytes\)\)',text)
    if found:return {'event':'publish_received','qos':int(found[1]),'mid':int(found[2]),'bytes':int(found[3])}
    found=re.search(r'Sending PUBACK to '+name+r' \(m(\d+)',text)
    if found:return {'event':'puback_sent','mid':int(found[1])}
    if 'Client '+gateway+' ' in text and ('disconnected' in text or 'closed its connection' in text):
        return {'event':'gateway_disconnected'}
    if 'protocol error' in text.lower():return {'event':'protocol_error'}
    return None


def main():
    config=Path('/opt/medical-monitor-h3/broker/mosquitto-diagnostic.conf')
    lines=config.read_text().splitlines()
    # 固定仅隔离监听；绝不把此包装器用于正式Broker。
    if [l.strip() for l in lines if l.strip().startswith('listener ')]!=['listener 8884']:
        raise ValueError('ISOLATED_LISTENER_REQUIRED')
    gateway=json.loads((STATE/'gateway.json').read_text())['client_id']
    child=None
    try:
        child=subprocess.Popen(['/usr/sbin/mosquitto','-c',str(config)],stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
        def forward(number,_frame):
            if child.poll() is None:child.send_signal(number)
        for number in (signal.SIGINT,signal.SIGTERM,signal.SIGHUP):signal.signal(number,forward)
        print(json.dumps({'event':'diagnostic_broker_started','port':8884}),flush=True)
        while True:
            raw=child.stdout.readline(4096)
            if not raw:break
            item=classify(raw.decode('utf-8',errors='replace'),gateway)
            if item:
                item['utc']=datetime.now(timezone.utc).isoformat()
                print(json.dumps(item),flush=True)
        return int(child.wait()!=0)
    finally:
        if child and child.poll() is None:
            child.terminate()
            try:child.wait(timeout=5)
            except subprocess.TimeoutExpired:child.kill();child.wait()


if __name__=='__main__':
    try:raise SystemExit(main())
    except Exception as exc:
        print(json.dumps({'event':'diagnostic_broker_failed','failure_type':type(exc).__name__}),flush=True)
        raise SystemExit(1)
