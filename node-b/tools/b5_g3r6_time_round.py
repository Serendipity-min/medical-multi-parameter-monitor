"""一次有界易失授时及单包验证；默认禁用，不启动B5或写NVM。"""
import argparse
import ctypes as C
import ipaddress
import json
import math
from pathlib import Path
import re
import subprocess
import sys
import time
import b5_g3r5_time_precheck as p
import b5_esp_net_pc as lan
from b5_esp_budget import CommandBudget,command_calls
u=p.u;q=p.q;g=p.g
SCOPE='B5_G3R6_VOLATILE_TIME_CLEAN_AND_ONE_FRESH_UDP'
FAST_SCOPE='B5_G3R6_FUTURE_FAST_SINGLE_UDP_NO_WIFI_OR_SNTP_ENABLE'
SAMPLES=12
MINIMUM=1792977536


def bindings():
    return {**p.bindings(),'b5_esp_net_pc.py':g.sha(Path(lan.__file__).read_bytes()),
        'b5_g3r6_time_round.py':g.sha(Path(__file__).read_bytes()),
        'b5_esp_fast_uart.py':g.sha(Path(__file__).with_name('b5_esp_fast_uart.py').read_bytes()),
        'sntp_sample.h':g.sha((g.ROOT/'gateway/mqtt/src/sntp_sample.h').read_bytes()),
        'b5_sntp_host_bridge.c':g.sha((g.ROOT/'node-b/tests/b5_sntp_host_bridge.c').read_bytes())}


def sntp_plan(wifi,server):
    g.require(re.fullmatch(r'[A-Za-z0-9.-]{1,64}',server) is not None,'ROUND_SERVER')
    return (b'AT+SYSSTORE?\r\n',b'AT+SYSSTORE=0\r\n',b'AT+SYSSTORE?\r\n',b'AT+CIPSNTPCFG=0\r\n',b'AT+CIPSNTPCFG?\r\n',
        b'AT+CIPSTATUS\r\n',b'AT+CWMODE=1\r\n',b'AT+CWJAP="'+lan.at_string(wifi['ssid'])+b'","'+lan.at_string(wifi['password'])+b'"\r\n',
        b'AT+CWJAP?\r\n',b'AT+CIPSTA?\r\n',b'AT+CIPMODE?\r\n',b'AT+CIPMUX?\r\n',b'AT+CIPRECVMODE?\r\n',
        b'AT+CIPSNTPCFG=1,0\r\n',b'AT+CIPSNTPCFG?\r\n')+(b'AT+SYSTIMESTAMP?\r\n',)*SAMPLES+(
        b'AT+CIPDOMAIN="'+server.encode()+b'"\r\n',b'AT+CIPSNTPCFG=0\r\n',b'AT+CIPSNTPCFG?\r\n',b'AT+CIPSTATUS\r\n')


def udp_plan(address,packet,receive_mode):
    ip=ipaddress.IPv4Address(address)
    g.require(ip.is_global and len(packet)==48 and packet[0]==0x23 and receive_mode in (0,1),'ROUND_UDP_INPUT')
    return (b'AT+SYSSTORE?\r\n',b'AT+CIPSNTPCFG?\r\n',b'AT+CIPMODE?\r\n',b'AT+CIPMUX?\r\n',b'AT+CIPRECVMODE?\r\n',
        b'AT+CIPSTATUS\r\n',b'AT+CIPRECVMODE=1\r\n',b'AT+CIPSTART="UDP","'+str(ip).encode()+b'",123,42024,0\r\n',
        b'AT+CIPSEND=48\r\n',packet,b'AT+CIPRECVDATA=48\r\n',b'AT+CIPCLOSE\r\n',b'AT+CIPSTATUS\r\n',
        b'AT+CIPRECVMODE='+str(receive_mode).encode()+b'\r\n',b'AT+CIPRECVMODE?\r\n')


def timeout_for(phase,index):
    return 15 if phase=='sntp' and index==7 else 5 if (phase,index) in (('sntp',27),('udp',7)) else 2


def sdk_bound(commands,phase,fast=False):
    tail=28 if phase=='sntp' else 11
    if fast:
        import b5_esp_fast_uart as accelerated
        return 512+sum(accelerated.command_calls(c,timeout_for(phase,i)) for i,c in enumerate(commands))+accelerated.FastBudget(None,commands[tail:]).cleanup_reserve
    reserve=CommandBudget(None,commands[tail:]).cleanup_reserve
    return 512+sum(command_calls(c,timeout_for(phase,i)) for i,c in enumerate(commands))+reserve


def reference_check(dll,packet,request,rtt_ms):
    check=dll.b5_check;check.argtypes=[C.c_void_p,C.c_size_t,C.c_void_p,C.c_uint32,C.c_uint32,C.POINTER(C.c_uint64)];check.restype=C.c_int
    sample=C.c_uint64();ok=check(C.create_string_buffer(packet),len(packet),C.create_string_buffer(request),rtt_ms,MINIMUM,C.byref(sample))
    return {'C_sntp_sample_pass':bool(ok),'rtt_upper_bound_ms':rtt_ms,'server_received_estimate_ms':sample.value if ok else None,
        'MCU_time_installation':'NOT_PERFORMED','wire_RTT':'NOT_DIRECTLY_MEASURED_HOST_INTERVAL_IS_CONSERVATIVE'}


def worker(a,phase,out):
    out.mkdir();g.private.protected(out,False);link=None;bridge=None;cleaned=False;cleanup_attempted=False
    commands=tuple(bytes.fromhex(x) for x in a['commands_hex']);tail=28 if phase=='sntp' else 11
    fast=a.get('scope')==FAST_SCOPE
    if fast:import b5_esp_fast_uart as accelerated
    r={'status':'STOP','exit_code':1,'phase':phase,'cleanup_verified':False,'manual_packets_attempted':0,
        'SNTP_enables_attempted':0,'Flash_sector3_reset_Go_B5START':0,'UID_image_options_reads':0}
    def X(index,**kw):
        command=commands[index]
        if fast:return accelerated.exchange(link,bridge,command,out,index,timeout=timeout_for(phase,index),budget=budget,**kw)[0]
        budget.admit(command,timeout_for(phase,index),link.byte_grant.cleanup_started)
        return u.exchange(link,bridge,command,out,index,timeout=timeout_for(phase,index),budget=budget,**kw)[0]
    def cleanup():
        nonlocal cleaned,cleanup_attempted
        cleanup_attempted=True;link.byte_grant.cleanup();replies=[X(i,allow_error=(phase=='udp' and i==11)) for i in range(tail,len(commands))]
        if phase=='sntp':
            cleaned=re.search(rb'\+CIPSNTPCFG:0\r?\n',replies[1]) is not None and u.no_socket(replies[2])
        else:
            cleaned=u.no_socket(replies[1]) and re.search(rb'\+CIPRECVMODE:'+str(a['receive_mode']).encode()+rb'\r?\n',replies[3]) is not None
        r['cleanup_verified']=cleaned;g.require(cleaned,'ROUND_CLEANUP_UNVERIFIED')
    try:
        link=(accelerated.FastLink if fast else u.UdpLink)(out,commands);link.sdk_limit=a['SDK_limit'];link.byte_grant=p.Grant(commands);link.byte_grant.cleanup_index=tail
        budget=(accelerated.FastBudget if fast else CommandBudget)(link,commands[tail:]);link.open();g.save(out/'sticky-private.json',{'DHCSR':link.u32(u.CORE['DHCSR'])})
        u.runtime(link,out,'entry');route=q.rx_route_snapshot(link);g.save(out/'UART-route-private.json',route)
        g.require(all(route[k] for k in ('PB10_PB11_AF7','GPIOB_clock_enabled','USART3_clock_enabled','USART3_IRQ_enabled','uptime_advances')),'ROUND_UART_ROUTE')
        uart=[link.u32(q.UART+i) for i in (8,12,16,20)]
        g.require(abs(q.baud_from_registers(link.u32(0x40023808),uart[0])-115200)<=1152 and uart[1]&0xb42c==0x202c
            and not uart[2]&0x3000 and not uart[3]&0x300,'ROUND_UART_CONFIG')
        bridge=(accelerated.FastBridge if fast else u.UartBridge)(q.site.config.NativeBus(link));bridge.prove_control_path(link.u32(q.CR),link.u32(q.SR));bridge.guard=link.byte_grant.check;link.query_before_verified=True
        if phase=='sntp':
            pre=[]
            for i in range(13):
                if i==1 and store==0:
                    # 只跳过已由刚才查询证明无需执行的SYSSTORE写命令。
                    g.require(link.byte_grant.commands==1 and link.byte_grant.index==len(commands[0]),'ROUND_STORE_SKIP_SEQUENCE')
                    link.byte_grant.commands=2;pre.append(None);r['store_set_skipped_already_zero']=True;continue
                raw=X(i);pre.append(raw)
                if i==0:
                    match=re.search(rb'\+SYSSTORE:([01])\r?\n',raw);g.require(match is not None,'ROUND_STORE_QUERY');store=int(match[1])
                if i==2:g.require(b'+SYSSTORE:0' in raw,'ROUND_VOLATILE_REQUIRED')
                if i==4:g.require(b'+CIPSNTPCFG:0' in raw,'ROUND_INITIAL_SNTP_OFF')
                if i==5:g.require(lan.prejoin_no_socket(raw),'ROUND_PREEXISTING_SOCKET')
                if i==8:g.require(p.same_network(raw,a['ssid']),'ROUND_NETWORK_MISMATCH')
            g.require(b'+CIPMODE:0' in pre[10] and b'+CIPMUX:0' in pre[11],'ROUND_UDP_MODE')
            mode=re.search(rb'\+CIPRECVMODE:([01])',pre[12]);g.require(mode is not None,'ROUND_RECEIVE_MODE')
            r['receive_mode']=int(mode[1]);r['SNTP_enables_attempted']=1;X(13);cfg=X(14)
            g.require(b'+CIPSNTPCFG:1,' in cfg and re.findall(rb'"([A-Za-z0-9.-]{1,64})"',cfg)==[s.encode() for s in a['dns_names']],'ROUND_SERVER_READBACK')
            values=[];start=time.monotonic()
            for i in range(SAMPLES):
                if i:time.sleep(max(0,start+i*3-time.monotonic()))
                raw=X(15+i,allow_error=True);values.append(p.epoch(raw))
            g.save(out/'time-samples-private.json',values)
            dns=X(27);ip=u.reference.address_from_reply(dns)
            g.require(ipaddress.IPv4Address(ip).is_global,'ROUND_DNS_NOT_GLOBAL')
            cleanup();r.update(time_epochs=values,time_progression_pass=p.time_gate(values,MINIMUM,True,True))
            g.require(r['time_progression_pass'],'ROUND_TIME_NOT_VALID')
        else:
            pre=[X(i) for i in range(6)]
            g.require(b'+SYSSTORE:0' in pre[0] and b'+CIPSNTPCFG:0' in pre[1] and b'+CIPMODE:0' in pre[2]
                and b'+CIPMUX:0' in pre[3] and b'+CIPRECVMODE:'+str(a['receive_mode']).encode() in pre[4] and u.no_socket(pre[5]),'ROUND_UDP_PRECONDITION')
            r['receive_mode_changed']=True;X(6);r['UDP_open_attempted']=True;X(7);start=time.monotonic();X(8,mode='PROMPT')
            with (Path(a['root'])/'payload.used').open('x') as f:f.write('one48\n')
            r['manual_packets_attempted']=1;X(9,mode='SEND');raw=X(10,allow_error=True);received=time.monotonic()
            packets,_,partial=u.framed(raw);r['packet_count']=len(packets)
            g.write_private(out/'passive-wire-private.bin',raw)
            checks=[]
            for body,_,_,_ in packets:
                g.write_private(out/f'packet-{len(checks)}-private.bin',body)
                checks.append(reference_check(C.CDLL(a['host_reference_DLL']),body,commands[9],math.ceil((received-start)*1000)))
            r['NTP_checks']=checks;cleanup()
            g.require(not partial and len(checks)==1 and checks[0]['C_sntp_sample_pass'],'ROUND_NO_VALID_FRESH_REPLY')
        g.require([link.u32(q.UART+i) for i in (8,12,16,20)]==uart,'ROUND_UART_DRIFT')
        u.runtime(link,out,'exit');link.set_close_resume(True);r.update(status='TIME_CLEAN_PASS' if phase=='sntp' else 'FRESH_PUBLIC_NTP_PASS',exit_code=0)
    except Exception as error:
        r.update(g.error_record(error));r['failure_class']=type(error).__name__
        if re.fullmatch(r'(ROUND|UDP|ESP|P0A|FAST)_[A-Z0-9_]+',str(error)):r['reason']=str(error)
        if p.healthy(link):
            try:
                u.runtime(link,out,'failure-exit')
                if not cleanup_attempted:cleanup()
                link.set_close_resume(True)
            except Exception as failure:r['cleanup_error_class']=type(failure).__name__;link.verified_running_flash=False
    finally:
        if link:
            p.close_receipt(link,r);r['UART_bytes']=link.native_UART_writes
        if r['exit_code']:r['status']='STOP'
        r['physical_stop_required']=bool(not r['cleanup_verified'] and (r['SNTP_enables_attempted'] or r.get('UDP_open_attempted') or r.get('receive_mode_changed'))
            or r.get('SDK_close_error') or r.get('cleanup_error_class') or r.get('failure_class') in ('NativeReadFailed','NativeCallUncertain'))
        g.save(out/'receipt-private.json',r)
    print(json.dumps({k:r[k] for k in ('status','exit_code','reason','cleanup_verified','physical_stop_required','SDK_calls') if k in r}),flush=True)
    return r['exit_code']


def validate(a,phase):
    g.require(a.get('enabled') is True and a.get('owner_approved') is True and a.get('scope') in (SCOPE,FAST_SCOPE),'ROUND_NOT_AUTHORIZED')
    if a['scope']==FAST_SCOPE:g.require(phase=='udp' and a['manual_packets_max']==1,'ROUND_FAST_SCOPE')
    g.require(a['phase']==phase and a['tools_sha256']==bindings() and time.time()<a['expires_unix'],'ROUND_BINDING')
    g.require(a['session_timeout_s']==180 and a['reset_Go_Flash_sector3_B5START']==0,'ROUND_LIMITS')
    g.private.protected(Path(a['root']),False)
    commands=tuple(bytes.fromhex(x) for x in a['commands_hex'])
    g.require(g.sha(b''.join(commands))==a['commands_sha256'],'ROUND_COMMAND_BINDING')
    if phase=='sntp':
        raw=g.private.read(Path(a['WiFi_reference']),False)
        g.require(g.sha(raw)==a['WiFi_reference_sha256'],'ROUND_WIFI_REFERENCE')
        wifi=json.loads(raw);expected=sntp_plan(wifi,a['dns_names'][0])
        g.require(a['ssid']==wifi['ssid'],'ROUND_WIFI_NAME')
    else:
        source=g.private.read(Path(a['DNS_reply']),False);request=g.private.read(Path(a['request_packet']),False)
        g.require(g.sha(source)==a['DNS_reply_sha256'] and g.sha(request)==a['request_packet_sha256'],'ROUND_UDP_REFERENCE')
        expected=udp_plan(u.reference.address_from_reply(source),request,a['receive_mode'])
        g.require(g.sha(Path(a['host_reference_DLL']).read_bytes())==a['host_reference_DLL_sha256'],'ROUND_HOST_REFERENCE')
        receipt=g.private.read(Path(a['SNTP_receipt']),False)
        prior=json.loads(receipt)
        g.require(g.sha(receipt)==a['SNTP_receipt_sha256'] and prior['status']=='TIME_CLEAN_PASS'
            and prior['exit_code']==0 and prior['cleanup_verified'] and prior['Close_completed'],'ROUND_SNTP_NOT_PASS')
    g.require(commands==expected and a['SDK_limit']==sdk_bound(commands,phase,a['scope']==FAST_SCOPE) and a['SDK_limit']<=30000,'ROUND_PLAN_OR_SDK_BOUND')


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--authorization',type=Path);parser.add_argument('--phase',choices=['sntp','udp']);parser.add_argument('--execute',action='store_true');parser.add_argument('--worker',action='store_true');args=parser.parse_args()
    if not args.execute and not args.worker:print(json.dumps({'enabled':False,'manual_packets_max':1,'reset_Go_NVM_B5START':0}));return 0
    a=g.load(args.authorization);validate(a,args.phase);root=Path(a['root']);out=root/args.phase
    if args.worker:
        used=g.load(root/(args.phase+'.used'));g.require(used['authorization_sha256']==g.sha(args.authorization.read_bytes()),'ROUND_WORKER_BINDING')
        with (root/(args.phase+'.connection-used')).open('x') as f:f.write('one\n')
        return worker(a,args.phase,out)
    with (root/(args.phase+'.used')).open('x') as f:json.dump({'authorization_sha256':g.sha(args.authorization.read_bytes())},f)
    start=time.monotonic()
    with (root/(args.phase+'-worker-private.log')).open('xb') as log:
        child=subprocess.Popen([sys.executable,'-X','utf8',__file__,'--phase',args.phase,'--worker','--authorization',str(args.authorization)],stdout=log,stderr=subprocess.STDOUT)
        reason=p.supervise(child,out,180,start)
    r=g.maybe(out/'receipt-private.json') or {};summary={'reason':reason,'worker_exit_code':child.returncode,'exit_code':1 if reason else child.returncode,'physical_stop_required':bool(reason or r.get('physical_stop_required',True))}
    g.save(root/(args.phase+'-supervisor-private.json'),summary);print(json.dumps(summary));return summary['exit_code']


if __name__=='__main__':raise SystemExit(main())
