"""单次PC局域网UDP原码对照；默认禁用，不设置模块时间。"""
import argparse
import ipaddress
import json
from pathlib import Path
import re
import select
import socket
import struct
import subprocess
import sys
import time

import b5_esp_udp_ntp as u
q=u.q;g=u.g
SCOPE='B5_ESP_PC_CONNECTED_UDP_ONE48_APPLICATION_EVIDENCE'
PC_PORT=42023
ESP_PORT=42024


def bindings():
    return {**u.bindings(),'b5_esp_net_pc.py':g.sha(Path(__file__).read_bytes())}


def at_string(value):
    g.require(isinstance(value,str) and not any(c in value for c in "\r\n\0"),'LAN_WIFI_STRING')
    return value.replace("\\","\\\\").replace('"','\\"').replace(',','\\,').encode('utf-8')


def commands(ip,request,wifi=None):
    ip=str(ipaddress.IPv4Address(ip));g.require(len(request)==48 and request[0]==0x23,'LAN_REQUEST')
    prefix=()
    if wifi is not None:
        prefix=(b'AT+CIPSNTPCFG?\r\n',b'AT+CIPSTATUS\r\n',b'AT+SYSSTORE=0\r\n',b'AT+SYSSTORE?\r\n',
            b'AT+CWJAP="'+at_string(wifi['ssid'])+b'","'+at_string(wifi['password'])+b'"\r\n')
    return prefix+(b'AT+CIPSTA?\r\n',b'AT+CIPSNTPCFG?\r\n',b'AT+CIPMUX?\r\n',b'AT+CIPRECVMODE?\r\n',
        b'AT+CIPDINFO?\r\n',b'AT+CIPMODE?\r\n',b'AT+CIPSTATUS\r\n',
        b'AT+CIPSTART="UDP","'+ip.encode()+b'",42023,42024,0\r\n',b'AT+CIPSTATUS\r\n',
        b'AT+CIPSEND=48\r\n',request,b'AT+CIPCLOSE\r\n',b'AT+CIPSTATUS\r\n')


def station_ip(raw,pc,prefix):
    m=re.search(rb'\+CIPSTA:ip:"([0-9.]+)"',raw);g.require(m is not None,'LAN_NO_STATION_IP')
    ip=ipaddress.IPv4Address(m[1].decode());host=ipaddress.IPv4Address(pc)
    g.require(ip!=host and ip in ipaddress.IPv4Network(f'{pc}/{prefix}',strict=False)
        and not(ip.is_unspecified or ip.is_multicast or ip.is_loopback),'LAN_NOT_LOCAL_PEER')
    return str(ip)


def prejoin_no_socket(raw):
    return re.search(rb'(?:^|\n)STATUS:[245]\r?\n',raw) is not None and b'+CIPSTATUS:' not in raw


def socket_tuple(raw,pc):
    m=re.search(rb'\+CIPSTATUS:0,"UDP","([0-9.]+)",(\d+),(\d+),0',raw)
    return m is not None and m[1].decode()==pc and int(m[2])==PC_PORT and int(m[3])==ESP_PORT


def response48(request,expected,peer,allowed,rx_ns,tx_ns):
    g.require(peer==allowed and len(request)==48 and request==expected,'LAN_PEER_OR_REQUEST_MISMATCH')
    g.require(tx_ns>=rx_ns,'LAN_PC_CLOCK_REVERSED')
    reply=bytearray(48);reply[0]=0xe4;reply[1]=16;reply[12:16]=b'TEST';reply[24:32]=request[40:48]
    for offset,nano in ((32,rx_ns),(40,tx_ns)):
        seconds,fraction=divmod(nano,1000000000)
        struct.pack_into('!II',reply,offset,(seconds+2208988800)&0xffffffff,fraction*(1<<32)//1000000000)
    return bytes(reply)


def validate(a):
    g.require(a.get('enabled') is True and a.get('owner_approved') is True and a.get('scope')==SCOPE,'LAN_NOT_AUTHORIZED')
    g.require(a.get('tools_sha256')==bindings() and time.time()<a.get('expires_unix',0),'LAN_BINDING_OR_EXPIRY')
    g.require(a.get('firewall_disabled_owner_exception') is True and a.get('application_only_no_pcap_owner_exception') is True,'LAN_EXCEPTIONS_REQUIRED')
    g.require(a.get('packets_max')==1 and a.get('reply_max')==1 and a.get('session_timeout_s')==180
        and a.get('receive_window_s')==10 and a.get('reset_halt_go')==0,'LAN_LIMITS')
    card=Path(a['card_snapshot']);g.require(g.sha(card.read_bytes())==a['card_sha256'],'LAN_CARD_DRIFT')
    request=g.private.read(Path(a['request_packet']),False)
    g.require(g.sha(request)==a['request_sha256'],'LAN_REQUEST_DRIFT')
    pc=ipaddress.IPv4Address(a['PC_IPv4']);g.require(pc.is_private and not pc.is_loopback,'LAN_PC_ADDRESS')
    wifi=None
    if a.get('WiFi_credentials'):
        g.require(a.get('owner_volatile_WiFi_join_approved') is True,'LAN_WIFI_PERMISSION')
        raw=g.private.read(Path(a['WiFi_credentials']),False)
        g.require(g.sha(raw)==a.get('WiFi_credentials_sha256'),'LAN_WIFI_BINDING')
        wifi=json.loads(raw)
    plan=commands(str(pc),request,wifi)
    g.require(g.sha(b''.join(plan))==a['commands_sha256'],'LAN_COMMAND_DRIFT')
    g.private.protected(Path(a['output']).parent,False)
    return plan,request


def wait_file(path,deadline,out):
    while not path.exists():
        g.require(time.monotonic()<deadline and not (out/'STOP').exists(),'LAN_WAIT_STOP_OR_TIMEOUT')
        time.sleep(.05)
    return g.load(path)


def pc_worker(a,request,out):
    r={'status':'STOP','exit_code':1,'reply_attempts':0,'capture':'APPLICATION_RAW_ONLY_NO_PCAP','firewall_changes':0}
    sock=None
    try:
        peer=wait_file(out/'ESP-peer-private.json',time.monotonic()+55,out);allowed=(peer['IP'],ESP_PORT)
        sock=socket.socket(socket.AF_INET,socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET,socket.SO_EXCLUSIVEADDRUSE,1)
        sock.bind((a['PC_IPv4'],PC_PORT));sock.connect(allowed);sock.settimeout(1)
        g.require(sock.getsockname()==(a['PC_IPv4'],PC_PORT) and sock.getpeername()==allowed,'LAN_SOCKET_BINDING')
        g.save(out/'PC_READY.json',{'exclusive_bind':True,'connected_fixed_peer':True,'ready_monotonic':time.monotonic()})
        deadline=time.monotonic()+60
        while not select.select([sock],[],[],.1)[0]:
            g.require(time.monotonic()<deadline and not (out/'STOP').exists(),'LAN_PC_WAIT_STOP_OR_TIMEOUT')
        data=sock.recv(49);received=time.time_ns();g.write_private(out/'PC-request48-private.bin',data)
        reply=response48(data,request,allowed,allowed,received,time.time_ns())
        g.write_private(out/'PC-reply48-private.bin',reply)
        g.save(out/'PC-reply.used',{'attempt_max':1});r['reply_attempts']=1
        sent=sock.send(reply);g.require(sent==48,'LAN_PC_SHORT_SEND')
        r.update(status='PC_SINGLE_REQUEST_RECEIVED_REPLY_ACCEPTED',exit_code=0,request_bytes=len(data),reply_bytes=sent,
            request_sha256=g.sha(data),reply_sha256=g.sha(reply),network_capture_not_available=True,
            received_monotonic=time.monotonic(),clock_authority=False)
        g.save(out/'PC_REPLY.json',{'reply_sha256':g.sha(reply),'bytes':48})
    except BaseException as e:r.update(g.error_record(e))
    finally:
        if sock:sock.close()
        r['socket_closed']=True;g.save(out/'PC-receipt-private.json',r)
    return r['exit_code']


def esp_worker(a,plan,request,out):
    r={'status':'STOP','exit_code':1,'payload_attempts':0,'socket_close_confirmed':False,'reset_halt_go':0,
        'UID_Flash_options_reads':0,'Flash_writes':0,'device_time_writes':0,'B5START':0};link=None
    try:
        link=u.UdpLink(out,plan);link.open();g.save(out/'entry-sticky-private.json',{'DHCSR':link.u32(u.CORE['DHCSR'])})
        u.runtime(link,out,'entry');route=q.rx_route_snapshot(link);g.save(out/'route-private.json',route)
        g.require(all(route[k] for k in ('PB10_PB11_AF7','GPIOB_clock_enabled','USART3_clock_enabled','USART3_IRQ_enabled','uptime_advances')),'LAN_UART_ROUTE')
        config=[link.u32(q.UART+x) for x in (8,12,16,20)];brr,cr1,cr2,cr3=config
        g.require(abs(q.baud_from_registers(link.u32(0x40023808),brr)-115200)<=1152 and cr1&0xb42c==0x202c
            and not cr2&0x3000 and not cr3&0x300,'LAN_UART_CONFIG')
        g.require(link.call('JLINKARM_IsConnected')==1,'LAN_CONNECTED_CONTEXT')
        bridge=u.UartBridge(q.site.config.NativeBus(link));bridge.prove_control_path(link.u32(q.CR),link.u32(q.SR))
        link.query_before_verified=True;bridge.guard=link.byte_grant.check
        offset=5 if a.get('WiFi_credentials') else 0
        for index,c in enumerate(plan[:offset]):
            raw=u.exchange(link,bridge,c,out,index,timeout=30 if index==4 else 3)[0]
            if index==0:g.require(re.search(rb'\+CIPSNTPCFG:0\r?\n',raw) is not None,'LAN_SNTP_MUST_STAY_DISABLED')
            if index==1:g.require(prejoin_no_socket(raw),'LAN_WIFI_PREEXISTING_SOCKET')
            if index==3:g.require(re.search(rb'\+SYSSTORE:0\r?\n',raw) is not None,'LAN_WIFI_NOT_VOLATILE')
        pre=[u.exchange(link,bridge,c,out,i)[0] for i,c in enumerate(plan[offset:offset+7],start=offset)]
        source=station_ip(pre[0],a['PC_IPv4'],a['PC_prefix_length'])
        for index,pattern in ((1,rb'\+CIPSNTPCFG:0\r?\n'),(2,rb'\+CIPMUX:0\r?\n'),
                              (3,rb'\+CIPRECVMODE:0\r?\n'),(5,rb'\+CIPMODE:0\r?\n')):
            g.require(re.search(pattern,pre[index]) is not None,'LAN_NETWORK_PRECONDITION')
        g.require(u.dinfo_disabled(pre[4]) and u.no_socket(pre[6]),'LAN_EXISTING_SOCKET_OR_DINFO')
        g.save(out/'ESP-peer-private.json',{'IP':source,'port':ESP_PORT})
        wait_file(out/'PC_READY.json',time.monotonic()+25,out)
        u.exchange(link,bridge,plan[offset+7],out,offset+7,timeout=5)
        status=u.exchange(link,bridge,plan[offset+8],out,offset+8)[0];g.require(socket_tuple(status,a['PC_IPv4']),'LAN_PORT_TUPLE')
        u.exchange(link,bridge,plan[offset+9],out,offset+9,mode='PROMPT')
        g.save(out/'ESP-payload.used',{'attempt_max':1});r['payload_attempts']=1
        raw,baseline,sent=u.exchange(link,bridge,plan[offset+10],out,offset+10,mode='SEND',timeout=3)
        latest=raw;deadline=sent+10
        while time.monotonic()<deadline:
            received=u.ring_since(link,baseline)
            if received is not None:latest=received
            g.require(not (out/'STOP').exists(),'LAN_SUPERVISOR_STOP');time.sleep(.03)
        g.write_private(out/'active-wire-private.bin',latest)
        before_close=struct.unpack('<5I',link.read(q.STATS,20));g.save(out/'pre-close-stats-private.json',{'stats':before_close})
        g.require((before_close[4]-baseline[4])%q.CAPACITY==len(latest),'LAN_RX_CAPTURE_GAP')
        u.exchange(link,bridge,plan[offset+11],out,offset+11)
        closed=u.exchange(link,bridge,plan[offset+12],out,offset+12)[0]
        r['socket_close_confirmed']=u.no_socket(closed);g.require(r['socket_close_confirmed'],'LAN_SOCKET_NOT_CLOSED')
        found,_,partial=u.framed(latest);g.require(not partial,'LAN_PARTIAL_BINARY')
        packets=[p[0] for p in found];r['received_packets']=len(packets)
        for index,p in enumerate(packets):g.write_private(out/f'ESP-packet-{index}-private.bin',p)
        if packets:
            pc=wait_file(out/'PC_REPLY.json',time.monotonic()+2,out)
            r['matching_PC_reply']=len(packets)==1 and len(packets[0])==48 and g.sha(packets[0])==pc['reply_sha256'] and packets[0][24:32]==request[40:48]
        else:r['matching_PC_reply']=False
        g.require([link.u32(q.UART+x) for x in (8,12,16,20)]==config,'LAN_UART_DRIFT')
        u.runtime(link,out,'exit');link.set_close_resume(True)
        r.update(status='ESP_PC_LAN_ONE_PACKET_CAPTURE_COMPLETE',exit_code=0,receive_window_s=10,
            active_bytes=len(latest),receive_head_gap=0,clock_authority=False)
    except BaseException as e:
        r.update(g.error_record(e))
        if isinstance(e,ValueError) and re.fullmatch(r'(LAN|UDP|ESP)_[A-Z0-9_]+',str(e)):r['reason']=str(e)
        if link and link.query_before_verified and not link.error and not getattr(link,'raw_failed',False) and not getattr(link,'read_failed',False):
            try:
                u.runtime(link,out,'failure-exit')
                if r['payload_attempts']==1 and link.byte_grant.commands==offset+11 and link.byte_grant.index==len(plan[offset+10]):
                    u.exchange(link,bridge,plan[offset+11],out,offset+11)
                    r['socket_close_confirmed']=u.no_socket(u.exchange(link,bridge,plan[offset+12],out,offset+12)[0])
                link.set_close_resume(True)
            except BaseException:link.verified_running_flash=False
    finally:
        if link:
            r.update(UART_native_attempts=link.native_UART_writes,SDK_calls=link.sdk_calls,close_resume=link.close_resume_enabled)
            try:link.close()
            except BaseException:r['exit_code']=1;r['close_error']=True
        g.save(out/'ESP-receipt-private.json',r)
    return r['exit_code']


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--authorization',type=Path);parser.add_argument('--execute',action='store_true');parser.add_argument('--worker',choices=('PC','ESP'));args=parser.parse_args()
    if not args.execute and not args.worker:print(json.dumps({'enabled':False,'scope':SCOPE,'packets_max':1}));return 0
    try:
        a=g.load(args.authorization);plan,request=validate(a);out=Path(a['output'])
        if args.worker:
            marker=g.load(args.authorization.with_suffix('.used'));g.require(marker['authorization_sha256']==g.sha(args.authorization.read_bytes()),'LAN_PARENT_BINDING')
            return pc_worker(a,request,out) if args.worker=='PC' else esp_worker(a,plan,request,out)
        g.require(not out.exists(),'LAN_OUTPUT_EXISTS');g.save(args.authorization.with_suffix('.used'),{'authorization_sha256':g.sha(args.authorization.read_bytes())})
        out.mkdir();g.private.protected(out,False);children={};logs=[];started=time.monotonic();reason=None
        try:
            for role in ('PC','ESP'):
                file=out/(role+'-worker-private.log');g.write_private(file,b'');stream=file.open('ab');logs.append(stream)
                children[role]=subprocess.Popen([sys.executable,'-X','utf8',__file__,'--worker',role,'--authorization',str(args.authorization)],stdout=stream,stderr=subprocess.STDOUT)
            while any(c.poll() is None for c in children.values()):
                if time.monotonic()-started>=180:reason='LAN_HARD_180S'
                if (out/'STOP').exists():reason=reason or 'LAN_STOP'
                for role,c in children.items():
                    if c.poll() is not None and c.returncode!=0:reason=reason or role+'_WORKER_FAILED'
                event=__import__('b5_g3_joint').last_event(out/'heartbeat-events.jsonl')
                if event.get('active') and time.monotonic()>event['deadline_monotonic']:reason='LAN_NATIVE_DEADLINE'
                if reason:
                    if not (out/'STOP').exists():g.write_private(out/'STOP',b'COOPERATIVE_STOP')
                    until=min(started+180,time.monotonic()+8)
                    while time.monotonic()<until and any(c.poll() is None for c in children.values()):time.sleep(.05)
                    break
                time.sleep(.05)
        finally:
            for c in children.values():
                if c.poll() is None:c.kill()
                c.wait(timeout=5)
            for stream in logs:stream.close()
        pc=g.maybe(out/'PC-receipt-private.json') or {};esp=g.maybe(out/'ESP-receipt-private.json') or {}
        good=not reason and pc.get('exit_code')==0 and esp.get('exit_code')==0
        receipt={'status':'CONTROLLED_LAN_UDP_BIDIRECTIONAL_PASS' if good and esp.get('matching_PC_reply') else 'LAN_TEST_NOT_PASS',
            'exit_code':0 if good and esp.get('matching_PC_reply') else 1,'reason':reason,'worker_exits':{role:c.returncode for role,c in children.items()},
            'ESP_payload_attempts':esp.get('payload_attempts',0),'PC_reply_attempts':pc.get('reply_attempts',0),
            'ESP_socket_close_confirmed':esp.get('socket_close_confirmed',False),'PC_socket_closed':pc.get('socket_closed',False),
            'PCAP':'NOT_RUN_OWNER_APPLICATION_ONLY_EXCEPTION','firewall':'DISABLED_UNCHANGED_OWNER_EXCEPTION',
            'NTP_UTC_or_G3_PASS':False,'reset_halt_go':0,'Flash_writes':0,'device_time_writes':0,'B5START':0,'retries':0,
            'all_host_sessions_ended':all(c.poll() is not None for c in children.values())}
        g.save(out/'supervisor-private.json',receipt);print(json.dumps(receipt));return receipt['exit_code']
    except BaseException as e:print(json.dumps({'status':'STOP','error_type':type(e).__name__,'exit_code':1}));return 1


if __name__=='__main__':raise SystemExit(main())
