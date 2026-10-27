"""电脑侧一次UDP参考探测；仅既有ESP DNS回复中的三个地址，不给设备灌时间。"""
import argparse
import ipaddress
import json
from pathlib import Path
import re
import secrets
import socket
import struct
import time
import b5_g3_contract as g


def address_from_reply(raw):
    match=re.search(rb'(?:^|\n)\+CIPDOMAIN:([^\r\n]+)',raw)
    g.require(match is not None and b'\r\nOK\r\n' in raw,'NTP_REF_DNS_REPLY')
    address=ipaddress.ip_address(match[1].strip(b'"').decode('ascii'))
    g.require(address.version==4 and not address.is_unspecified and not address.is_multicast,'NTP_REF_ADDRESS')
    return str(address)


def packet_check(reply,nonce,rtt):
    if len(reply)!=48:return {'valid':False,'reason':'LENGTH'}
    if reply[24:32]!=nonce:return {'valid':False,'reason':'NONCE'}
    if reply[0]>>6==3 or reply[0]&7!=4 or not 1<=reply[1]<=15:return {'valid':False,'reason':'UNSYNCHRONIZED_OR_KOD'}
    seconds,fraction=struct.unpack_from('!II',reply,40);utc=seconds-2208988800+fraction/4294967296
    return {'valid':utc>=1700000000 and rtt<=1,'epoch_s':utc,'rtt_s':rtt,'stratum':reply[1],
            'reason':None if utc>=1700000000 and rtt<=1 else 'TIME_OR_RTT'}


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--authorization',type=Path,required=True);a_path=parser.parse_args().authorization
    a=g.load(a_path);g.require(a.get('enabled') and a.get('owner_approved') and a.get('scope')=='B5_PC_THREE_EXISTING_NTP_REFERENCE_PACKETS','NTP_REF_OWNER_SCOPE')
    g.require(a.get('tool_sha256')==g.sha(Path(__file__).read_bytes()) and time.time()<a.get('expires_unix',0),'NTP_REF_BINDING')
    g.require(len(a['DNS_replies'])==3 and a.get('retries')==0,'NTP_REF_PACKET_LIMIT')
    targets=[]
    for entry in a['DNS_replies']:
        raw=g.private.read(Path(entry['path']),False);g.require(g.sha(raw)==entry['sha256'],'NTP_REF_SOURCE_DRIFT');targets.append(address_from_reply(raw))
    out=Path(a['output']);g.private.protected(out.parent,False);g.require(not out.exists(),'NTP_REF_OUTPUT_EXISTS')
    g.save(a_path.with_suffix('.used'),{'authorization_sha256':g.sha(a_path.read_bytes())});out.mkdir(exist_ok=False)
    results=[]
    for i,target in enumerate(targets):
        packet=bytearray(48);packet[0]=0x23;nonce=struct.pack('!II',int(time.time())+2208988800,secrets.randbits(32));packet[40:48]=nonce
        g.write_private(out/f'request-{i}-private.bin',bytes(packet));started=time.monotonic()
        try:
            with socket.socket(socket.AF_INET,socket.SOCK_DGRAM) as sock:
                sock.settimeout(2);sock.connect((target,123));g.require(sock.send(packet)==48,'NTP_REF_SEND')
                reply=sock.recv(512)
            rtt=time.monotonic()-started;g.write_private(out/f'reply-{i}-private.bin',reply)
            result=packet_check(reply,nonce,rtt)
        except (TimeoutError,OSError) as error:result={'valid':False,'reason':type(error).__name__,'errno':getattr(error,'errno',None)}
        result.update(index=i,target_sha256=g.sha(target.encode()),request_packets=1,path='PC_NOT_ESP_WIFI');results.append(result)
    receipt={'status':'PC_NTP_REFERENCE_PROBES_CAPTURED','exit_code':0,'results':results,'packets_sent_max':3,
             'device_access':0,'device_time_writes':0,'formal_cloud_changes':0,'not_module_reachability_proof':True}
    g.save(out/'receipt-private.json',receipt);print(json.dumps(receipt));return 0


if __name__=='__main__':raise SystemExit(main())
