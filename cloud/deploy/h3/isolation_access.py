"""只对当前SSH现场出口开放隔离TLS端口，按完整规则精确撤销，不保存地址正文。"""
import ipaddress
import json
import os
import subprocess
import sys


def main():
    action=sys.argv[1]
    if action not in ('add','remove'):raise ValueError('ACTION')
    # sudo必须显式保留本次会话来源；不存在即停止，不能退化为任意公网来源。
    peer=ipaddress.ip_address(os.environ['SSH_CONNECTION'].split()[0])
    tool='iptables' if peer.version==4 else 'ip6tables'
    rule=['INPUT','-p','tcp','-s',str(peer), '--dport','8884','-m','comment',
          '--comment','medical-monitor-h3-isolation','-j','ACCEPT']
    exists=subprocess.run([tool,'-C',*rule],capture_output=True).returncode==0
    if action=='add' and not exists:subprocess.run([tool,'-I',rule[0],'1',*rule[1:]],check=True,capture_output=True)
    if action=='remove' and exists:subprocess.run([tool,'-D',*rule],check=True,capture_output=True)
    return {'action':action,'port':8884,'source':'CURRENT_SSH_PEER_SINGLE_ADDRESS',
            'production_ports_changed':False,'address_saved':False,'rule_present':action=='add'}


if __name__=='__main__':
    try:print(json.dumps(main()))
    except Exception as exc:
        print(json.dumps({'failure_type':type(exc).__name__,'details_suppressed':True}));raise SystemExit(1)
