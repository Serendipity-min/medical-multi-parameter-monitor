"""ESP单个UDP/NTP请求；沿用既有设备证据，不重读UID/Flash/options。"""
import argparse
import ctypes as C
import json
from pathlib import Path
import re
import secrets
import struct
import subprocess
import sys
import time

import b5_esp_gmr as q
import b5_ntp_reference_probe as reference
from b5_esp_budget import TX_POLLS, RX_INTERVAL, response_polls
g=q.g
SCOPE='B5_ESP_ONE_UDP_NTP_PACKET_NO_IDENTITY_OR_FULL_FLASH_RESCAN'
CARD='AUTH-B5-ESP-UDP-NTP-001-R2.md'
CORE={'DHCSR':0xe000edf0,'VTOR':0xe000ed08,'CFSR':0xe000ed28,'HFSR':0xe000ed2c,
      'DWT_PCSR':0xe000101c,'FLASH_CR':q.CR,'FLASH_SR':q.SR}
READS={a:{4} for a in (*CORE.values(),*q.RX_ROUTE_REGISTERS.values(),q.UPTIME,q.site.RAM,
                       q.UART+8,q.UART+12,q.UART+16,q.UART+20,0x40023808)}
READS.update({q.STATS:{20},q.RING:{q.CAPACITY}})
FRAME=re.compile(rb'\+IPD,([0-9]{1,4}):|\+CIPRECVDATA:([0-9]{1,4}),|\+CIPRECVDATA,([0-9]{1,4}):')


def bindings():return {**q.bindings(),'b5_ntp_reference_probe.py':g.sha(Path(reference.__file__).read_bytes()),
                       'b5_esp_udp_ntp.py':g.sha(Path(__file__).read_bytes())}


def plan(address,packet):
    g.require(len(packet)==48 and packet[0]==0x23,'UDP_REQUEST_FORMAT')
    # 地址只来自既有私有DNS回执，禁止把任意字符串拼进AT命令。
    address=str(reference.ipaddress.IPv4Address(address))
    return (b'AT+CIPSNTPCFG?\r\n',b'AT+CIPMUX?\r\n',b'AT+CIPRECVMODE?\r\n',b'AT+CIPDINFO?\r\n',
       b'AT+CIPSTATUS\r\n',b'AT+CIPSTART="UDP","'+address.encode()+b'",123\r\n',
       b'AT+CIPSEND=48\r\n',bytes(packet),b'AT+CIPRECVDATA=48\r\n',b'AT+CIPCLOSE\r\n',b'AT+CIPSTATUS\r\n')


class UdpLink(q.QueryLink):
    def __init__(self,out,commands):self.BYTE_COMMANDS=commands;super().__init__(out)
    def _call_native(self,name,*args,timeout=5):
        if name=='JLINKARM_ReadMemEx':g.require(args[1] in READS.get(args[0],set()),'UDP_MINIMAL_READ_SCOPE')
        if name=='JLINKARM_CORESIGHT_ReadAPDPReg' and args[:2]==(3,1) and self.dap_select==0:
            g.require(self.dap_tar in (q.CR,q.SR),'UDP_NO_IDENTITY_DAP_READ')
        return super()._call_native(name,*args,timeout=timeout)
    def read(self,address,size):
        g.require(size in READS.get(address,set()),'UDP_MINIMAL_READ_SCOPE')
        return super().read(address,size)


class UartBridge(q.DapBridge):
    def read32(self,address):
        g.require(address in (q.CR,q.SR),'UDP_BRIDGE_CONTROL_READ_ONLY')
        return super().read32(address)
    def prove_control_path(self,cr,sr):
        with self.window(0xf0):identifier=self.bus.read(3,True)
        g.require(identifier not in (0,0xffffffff) and (identifier>>13)&15==8 and identifier&15==1,'UDP_NOT_MEMAP')
        g.require(self.read32(q.CR)==cr and self.read32(q.SR)==sr and self.state_restored,'UDP_BRIDGE_CROSSCHECK')
        self.proven=True


def runtime(link,out,label):
    link.verified_running_flash=False
    state={k:link.u32(a) for k,a in CORE.items()}
    state['pc_samples']=[state['DWT_PCSR'],link.u32(CORE['DWT_PCSR']),link.u32(CORE['DWT_PCSR'])]
    state['uptime']=link.u32(q.UPTIME);flags=link.read(q.site.RAM,4);state['DISARMED']=flags==bytes(4)
    g.save(out/(label+'-private.json'),state)
    g.require(not state['DHCSR']&(q.site.ro.raw.HALT|q.site.ro.raw.LOCKUP|q.site.ro.raw.RESET),'UDP_CPU_STATE_STOP')
    g.require(not any(0x1fff0000<=p<0x1fff7800 for p in state['pc_samples']),'UDP_ROM_STOP')
    g.require(state['VTOR']==0x08000000 and any(0x08000000<=p<0x0800a638 for p in state['pc_samples']),'UDP_FLASH_RUNTIME_NOT_PROVEN')
    g.require(not(state['CFSR']|state['HFSR']) and state['DISARMED'],'UDP_FAULT_OR_ARMED')
    g.require(state['FLASH_CR']&0x80000000 and not state['FLASH_CR']&0x10007 and not state['FLASH_SR']&0x100f2,'UDP_FLASH_NOT_IDLE_LOCKED')
    link.verified_running_flash=True
    return state


def framed(data):
    packets=[];spans=[];partial=False;position=0
    while True:
        match=FRAME.search(data,position)
        if match is None:break
        count=int(next(x for x in match.groups() if x is not None));g.require(count<=512,'UDP_FRAME_LENGTH_BOUND')
        start=match.end();end=start+count;spans.append((start,min(end,len(data))))
        if end>len(data):partial=True;break
        if count:packets.append((data[start:end],start,end,'IPD_ACTIVE' if match[1] is not None else 'CIPRECVDATA'))
        position=end if end>start else start
    return packets,spans,partial


def terminal(data,mode):
    packets,spans,partial=framed(data);masked=bytearray(data)
    for start,end in spans:masked[start:end]=b'\0'*(end-start)
    safe=bytes(masked)
    if any(x in safe for x in (b'\r\nERROR\r\n',b'\r\nFAIL\r\n',b'SEND FAIL\r\n')):return 'ERROR'
    if mode=='PROMPT' and safe.rstrip(b' ').endswith(b'>'):return 'PROMPT'
    if mode=='SEND' and b'SEND OK\r\n' in safe:return 'SEND_OK'
    if mode=='OK' and not partial and b'\r\nOK\r\n' in safe:return 'OK'
    return None


def ring_since(link,baseline):
    state=struct.unpack('<5I',link.read(q.STATS,20))
    g.require(state[:4]==baseline[:4],'UDP_UART_ERROR_OR_OTHER_CONSUMER')
    blob=link.read(q.RING,q.CAPACITY);after=struct.unpack('<5I',link.read(q.STATS,20))
    g.require(after[:4]==baseline[:4],'UDP_UART_ERROR_OR_OTHER_CONSUMER')
    if after[4]!=state[4]:return None
    return q.circular_delta(baseline[4],after[4],blob)


def exchange(link,bridge,command,out,index,mode='OK',timeout=3,allow_error=False,budget=None):
    baseline=struct.unpack('<5I',link.read(q.STATS,20));g.save(out/f'query-{index}-baseline-private.json',{'stats':baseline})
    link.byte_grant.begin(command);started=time.monotonic()
    for offset,value in enumerate(command):
        if budget:
            budget.byte(len(command)-offset,response_polls(timeout))
        until=time.monotonic()+.5
        if budget:
            for poll in range(TX_POLLS):
                if link.u32(q.UART)&(1<<7):break
                if poll+1<TX_POLLS:time.sleep(.005)
            else:raise ValueError('UDP_TX_NOT_READY')
        else:
            while not link.u32(q.UART)&(1<<7):
                g.require(time.monotonic()<=until,'UDP_TX_NOT_READY');time.sleep(.005)
        bridge.write32(q.DR,value)
    sent=time.monotonic();until=sent+timeout;data=b'';kind=None
    polls=0
    while time.monotonic()<until and (budget is None or polls<response_polls(timeout)):
        polls+=1
        received=ring_since(link,baseline)
        if received is not None:
            data=received;kind=terminal(data,mode)
            if kind:break
        time.sleep(RX_INTERVAL)
    g.write_private(out/f'query-{index}-response-private.bin',data)
    g.save(out/f'query-{index}-meta-private.json',{'command_bytes':len(command),'response_bytes':len(data),
        'terminal':kind,'mode':mode,'sent_monotonic':sent,'observed_monotonic':time.monotonic(),'elapsed_s':time.monotonic()-started})
    g.require(kind=={'OK':'OK','PROMPT':'PROMPT','SEND':'SEND_OK'}[mode] or allow_error and kind=='ERROR','UDP_NO_EXPECTED_TERMINAL')
    return data,baseline,sent


def no_socket(raw):return re.search(rb'(?:^|\n)STATUS:[24]\r?\n',raw) is not None and b'+CIPSTATUS:' not in raw


def dinfo_disabled(raw):return re.search(rb'(?:^|\n)\+CIPDINFO:(?:0|false)\r?\n',raw,re.I) is not None


def claim_payload(a):
    g.save(Path(a['payload_once_marker']),{'scope':SCOPE,'payload_attempt_max':1,'claimed_monotonic':time.monotonic()})


def inspect_packet(packet,request,observed_UTC_ms):
    if len(packet)!=48:return {'packet_fields_valid':False,'reason':'LENGTH'}
    if packet[24:32]!=request[40:48]:return {'packet_fields_valid':False,'reason':'NONCE'}
    li,version,mode=packet[0]>>6,(packet[0]>>3)&7,packet[0]&7
    if li==3 or version not in (3,4) or mode!=4 or not 1<=packet[1]<=15:
        return {'packet_fields_valid':False,'reason':'LI_VERSION_MODE_STRATUM','LI':li,'version':version,'mode':mode,'stratum':packet[1]}
    tx,txf=struct.unpack_from('!II',packet,40);rx,rxf=struct.unpack_from('!II',packet,32)
    epoch=tx-2208988800+txf/4294967296;server_rx=rx-2208988800+rxf/4294967296
    skew=abs(observed_UTC_ms/1000-epoch)
    valid=rx>=2208988800 and epoch>=1792977536 and 0<=epoch-server_rx<=2 and skew<=10
    return {'packet_fields_valid':valid,'reason':None if valid else 'SERVER_TIME_OR_HOST_FRESHNESS',
       'nonce_matches':True,'LI':li,'version':version,'mode':mode,'stratum':packet[1],
       'epoch_s':epoch,'host_skew_s_at_capture':skew,'server_processing_s':epoch-server_rx,
       'G3_RTT_1S_and_clock_installation':'NOT_VALIDATED_NOT_PERFORMED'}


def validate(a):
    g.require(a.get('enabled') is True and a.get('owner_approved') is True and a.get('scope')==SCOPE,'UDP_OWNER_SCOPE')
    g.require(a.get('tools_sha256')==bindings() and a.get('expires_unix',0)>time.time(),'UDP_TOOL_OR_EXPIRY')
    g.require(a.get('card_sha256')==g.sha((g.ROOT/'node-b/docs'/CARD).read_bytes()),'UDP_CARD_DRIFT')
    g.require(a.get('packets_max')==1 and a.get('session_timeout_s')==180 and a.get('reset_halt_go')==0 and a.get('retries')==0,'UDP_LIMITS')
    g.require(not Path(a['payload_once_marker']).exists(),'UDP_SINGLE_PACKET_PERMISSION_CONSUMED')
    g.private.protected(Path(a['payload_once_marker']).parent,False)
    source=g.private.read(Path(a['DNS_reply']),False);address=reference.address_from_reply(source)
    request=g.private.read(Path(a['request_packet']),False);commands=plan(address,request)
    g.require(a.get('commands_sha256')==g.sha(b''.join(commands)) and a.get('UART_bytes_max')==sum(map(len,commands)),'UDP_EXACT_BYTE_PLAN')
    site=g.load(a['site_record']);g.require(all(site.get(k) is True for k in ('JLink_on_C','C_J5','B_off','C_USB_disconnected','unchanged_owner_confirmed')),'UDP_SITE')
    g.private.protected(Path(a['output']).parent,False)
    return commands,request


def worker(a,commands,request,out):
    out.mkdir(exist_ok=False);g.private.protected(out,False);link=None
    r={'status':'STOP','exit_code':1,'UDP_request_packets_max':1,'UDP_open_attempted':False,'UDP_payload_attempts':0,'socket_close_confirmed':False,
       'UID_reads':0,'Flash_options_reads':0,'device_image_hash_checks':0,'reset_halt_go':0,'Flash_writes':0,'B5START':0,'device_time_writes':0}
    try:
        link=UdpLink(out,commands);link.open();g.save(out/'entry-sticky-private.json',{'DHCSR':link.u32(CORE['DHCSR'])})
        runtime(link,out,'entry');g.save(out/'route-entry-private.json',q.rx_route_snapshot(link))
        uart=[link.u32(q.UART+x) for x in (8,12,16,20)];brr,cr1,cr2,cr3=uart
        g.require(abs(q.baud_from_registers(link.u32(0x40023808),brr)-115200)<=1152 and cr1&0xb42c==0x202c and not cr2&0x3000 and not cr3&0x300,'UDP_UART_CONFIG')
        g.require(link.call('JLINKARM_IsConnected')==1,'UDP_SDK_CONNECTED')
        bridge=UartBridge(q.site.config.NativeBus(link));bridge.prove_control_path(link.u32(q.CR),link.u32(q.SR))
        link.query_before_verified=True;bridge.guard=link.byte_grant.check
        pre=[exchange(link,bridge,c,out,i)[0] for i,c in enumerate(commands[:5])]
        g.require(re.search(rb'(?:^|\n)\+CIPSNTPCFG:0\r?\n',pre[0]) is not None,'UDP_SNTP_BACKGROUND_ACTIVE')
        g.require(re.search(rb'(?:^|\n)\+CIPMUX:0\r?\n',pre[1]) is not None,'UDP_MULTIPLEX_UNEXPECTED')
        recvmode=re.search(rb'(?:^|\n)\+CIPRECVMODE:([01])\r?\n',pre[2]);g.require(recvmode is not None,'UDP_RECVMODE_UNKNOWN')
        g.require(dinfo_disabled(pre[3]),'UDP_DINFO_UNREVIEWED')
        g.require(no_socket(pre[4]),'UDP_PREEXISTING_SOCKET_OR_NO_WIFI')
        r['UDP_open_attempted']=True
        exchange(link,bridge,commands[5],out,5,timeout=5)
        exchange(link,bridge,commands[6],out,6,mode='PROMPT')
        claim_payload(a);r['UDP_payload_attempts']=1
        sent_reply,baseline,sent=exchange(link,bridge,commands[7],out,7,mode='SEND',timeout=3)
        whole=sent_reply;received_UTC_ms=int(time.time()*1000);deadline=sent+2
        while time.monotonic()<deadline:
            data=ring_since(link,baseline)
            if data is not None:
                whole=data;received_UTC_ms=int(time.time()*1000)
                if any(len(x[0])==48 for x in framed(whole)[0]):break
            time.sleep(.03)
        g.write_private(out/'active-wire-private.bin',whole)
        passive,_,_=exchange(link,bridge,commands[8],out,8,allow_error=True)
        passive_UTC_ms=int(time.time()*1000)
        exchange(link,bridge,commands[9],out,9,allow_error=True)
        closed,_,_=exchange(link,bridge,commands[10],out,10)
        r['socket_close_confirmed']=no_socket(closed);g.require(r['socket_close_confirmed'],'UDP_SOCKET_NOT_CLOSED')
        packets=[]
        for origin,data,when in [('SEND_CAPTURE',whole,received_UTC_ms),('READ_COMMAND_CAPTURE',passive,passive_UTC_ms)]:
            found,_,partial=framed(data);g.require(not partial,'UDP_BINARY_FRAME_INCOMPLETE')
            for body,start,end,frame_format in found:
                g.write_private(out/f'packet-{len(packets)}-private.bin',body)
                packets.append({'origin':origin,'frame_format':frame_format,'bytes':len(body),'sha256':g.sha(body),'observed_UTC_ms':when,
                                'validation':inspect_packet(body,request,when)})
        r.update(receive_mode=int(recvmode[1]),received_packets=packets,
                 matching_valid_reply=any(x['validation']['packet_fields_valid'] for x in packets),
                 wire_RTT_measurement='SDK_READ_LATENCY_NOT_WIRE_RTT',receive_observation_s=2)
        g.require([link.u32(q.UART+x) for x in (8,12,16,20)]==uart,'UDP_UART_CONFIGURATION_DRIFT')
        runtime(link,out,'exit');link.set_close_resume(True)
        r.update(status='ESP_SINGLE_UDP_NTP_CAPTURED',exit_code=0)
    except BaseException as error:
        r.update(g.error_record(error))
        if re.fullmatch(r'UDP_[A-Z0-9_]+',str(error)):r['reason']=str(error)
        if (link and link.query_before_verified and not link.error and not getattr(link,'read_failed',False)
            and not getattr(link,'raw_failed',False) and r.get('reason','').startswith(('UDP_NO_EXPECTED','UDP_FRAME','UDP_BINARY','UDP_SOCKET','UDP_SNTP','UDP_MULTI','UDP_RECV','UDP_DINFO','UDP_PREEXISTING'))):
            try:runtime(link,out,'failure-exit');link.set_close_resume(True)
            except BaseException as cleanup:r['close_check_error_type']=type(cleanup).__name__;link.verified_running_flash=False
    finally:
        if link:
            r.update(UART_native_attempts=link.native_UART_writes,SDK_calls=link.sdk_calls,close_resume=link.close_resume_enabled)
            try:link.close()
            except BaseException as error:r.update(exit_code=1,close_error_type=type(error).__name__)
        g.save(out/'receipt-private.json',r)
    print(json.dumps({k:r[k] for k in ('status','exit_code','reason','matching_valid_reply','socket_close_confirmed') if k in r}));return r['exit_code']


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--execute',action='store_true');parser.add_argument('--worker',action='store_true');parser.add_argument('--authorization',type=Path);args=parser.parse_args()
    if not args.execute and not args.worker:
        print(json.dumps({'enabled':False,'scope':SCOPE,'packets_max':1,'UID_Flash_options_reads':0,'B5START':0}));return 0
    try:
        a=g.load(args.authorization);commands,request=validate(a);out=Path(a['output'])
        if args.worker:
            marker=g.load(args.authorization.with_suffix('.used'));g.require(marker['authorization_sha256']==g.sha(args.authorization.read_bytes()),'UDP_PARENT_BINDING')
            return worker(a,commands,request,out)
        g.require(not out.exists(),'UDP_OUTPUT_EXISTS');g.save(args.authorization.with_suffix('.used'),{'authorization_sha256':g.sha(args.authorization.read_bytes())})
        log=out.with_name(out.name+'-worker-private.log');g.write_private(log,b'');started=time.monotonic();reason=None
        with log.open('ab') as f:
            child=subprocess.Popen([sys.executable,'-X','utf8',__file__,'--worker','--authorization',str(args.authorization)],stdout=f,stderr=subprocess.STDOUT)
            while child.poll() is None:
                if time.monotonic()-started>180:reason='UDP_SESSION_180S'
                if (out/'STOP').exists():reason='UDP_OWNER_STOP'
                event=__import__('b5_g3_joint').last_event(out/'heartbeat-events.jsonl')
                if event.get('active') and time.monotonic()>event['deadline_monotonic']:reason='UDP_NATIVE_DEADLINE'
                if reason:child.kill();break
                time.sleep(.05)
            child.wait(timeout=5)
        out.mkdir(exist_ok=True);g.save(out/'supervisor-private.json',{'reason':reason,'worker_exit_code':child.returncode,'exit_code':1 if reason else child.returncode,'retry':False})
        receipt=g.maybe(out/'receipt-private.json')
        if (reason or child.returncode) and (receipt is None or receipt.get('UDP_open_attempted') and not receipt.get('socket_close_confirmed')):
            print(json.dumps({'event':'C_J5_JLINK_PC_USB_OFF_REQUIRED_SOCKET_STATE_UNKNOWN'}),flush=True)
        return 1 if reason else child.returncode
    except BaseException as error:
        print(json.dumps({'status':'STOP','exit_code':1,'error_type':type(error).__name__}));return 1


if __name__=='__main__':raise SystemExit(main())
