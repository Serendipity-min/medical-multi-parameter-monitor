"""对当前现场唯一的8884连接注入6秒丢包；不触及其他连接或正式端口。"""
import ipaddress
from datetime import datetime,timezone
import json
import os
import re
import signal
import subprocess
import time


def select_peer_port(lines,peer):
    ports=[]
    for line in lines.splitlines():
        fields=line.split()
        if len(fields)<2:continue
        local,remote=fields[-2:]
        match=re.fullmatch(r'(\d+\.\d+\.\d+\.\d+):(\d+)',remote)
        if local.endswith(':8884') and match and match[1]==str(peer):ports.append(int(match[2]))
    if len(ports)!=1:raise ValueError('EXACTLY_ONE_FIELD_CONNECTION_REQUIRED')
    return ports[0]


def inject():
    peer=ipaddress.ip_address(os.environ['SSH_CONNECTION'].split()[0])
    if peer.version!=4:raise ValueError('FIELD_IPV4_REQUIRED')
    raw=subprocess.run(['ss','-tnH','state','established','sport = :8884'],capture_output=True,text=True,check=True)
    port=select_peer_port(raw.stdout,peer)
    comment='mpm-h3-mqtt-fault-'+str(time.time_ns())
    rule=['-p','tcp','-s',str(peer),'--sport',str(port),'--dport','8884',
          '-m','comment','--comment',comment,'-j','DROP']
    result={'action':'BOUNDED_ISOLATED_TCP_LOSS','seconds':6,'port':8884,
            'scope':'SINGLE_EXISTING_FIELD_CONNECTION','addresses_or_source_ports_saved':False,
            'production_ports_changed':False,'rule_removed':False,'exit_code':1,
            'started_utc':datetime.now(timezone.utc).isoformat()}
    def interrupted(_number,_frame):raise RuntimeError('FAULT_INTERRUPTED')
    previous={n:signal.signal(n,interrupted) for n in (signal.SIGINT,signal.SIGTERM)}
    installed=False
    try:
        # 置于INPUT首部以先于现有ESTABLISHED规则，仅命中已核对的单一连接。
        subprocess.run(['iptables','-I','INPUT','1',*rule],capture_output=True,check=True);installed=True
        started=time.monotonic();time.sleep(6)
        listing=subprocess.run(['iptables','-nvxL','INPUT'],capture_output=True,text=True,check=True).stdout
        for line in listing.splitlines():
            if comment in line:
                match=re.match(r'\s*(\d+)\s+(\d+)',line)
                if match:result['dropped_packets']=int(match[1]);result['dropped_bytes']=int(match[2])
        result['elapsed_s']=round(time.monotonic()-started,3)
    finally:
        if installed:
            removed=subprocess.run(['iptables','-D','INPUT',*rule],capture_output=True)
            result['rule_removed']=removed.returncode==0
        for number,handler in previous.items():signal.signal(number,handler)
    result['exit_code']=int(not result['rule_removed'] or not result.get('dropped_packets'))
    result['finished_utc']=datetime.now(timezone.utc).isoformat()
    return result


if __name__=='__main__':
    print(json.dumps(inject()))
