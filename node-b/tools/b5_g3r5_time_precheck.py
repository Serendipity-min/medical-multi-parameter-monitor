"""G3R5 P0-A：现有正确网络的一次SNTP启用/时间观察；默认禁用。"""
import argparse
import json
from pathlib import Path
import re
import subprocess
import sys
import time

import b5_esp_udp_ntp as u
q=u.q;g=u.g
SCOPE='B5_G3R5_P0A_CURRENT_WIFI_SNTP_TIME_NO_IMAGE_RESCAN'
CARD='AUTH-B5-G3R5-P0A-TIME-001-R1.md'
FINALIZE_SCOPE='B5_G3R5_P0A_REMAINING_DNS_AND_SNTP_STOP_ONLY'
FINALIZE_CARD='AUTH-B5-G3R5-P0A-FINALIZE-001-R1.md'
SDK_LIMIT=12000
CLEANUP_RESERVE=3200
SAMPLES=15


def bindings():
    return {**u.bindings(),'b5_g3r5_time_precheck.py':g.sha(Path(__file__).read_bytes())}


def plan(names):
    g.require(1<=len(names)<=3 and all(re.fullmatch(r'[A-Za-z0-9.-]{1,64}',n) for n in names),'P0A_DNS_NAMES')
    return (b'AT+SYSSTORE?\r\n',b'AT+CWJAP?\r\n',b'AT+CIPSTA?\r\n',b'AT+CIPMODE?\r\n',
       b'AT+CIPMUX?\r\n',b'AT+CIPRECVMODE?\r\n',b'AT+CIPSTATUS\r\n',b'AT+CIPSNTPCFG?\r\n',
       b'AT+SYSTIMESTAMP?\r\n',b'AT+CIPSNTPCFG=1,0\r\n',b'AT+CIPSNTPCFG?\r\n')+(b'AT+SYSTIMESTAMP?\r\n',)*SAMPLES+tuple(
       b'AT+CIPDOMAIN="'+n.encode('ascii')+b'"\r\n' for n in names)+(b'AT+CIPSNTPCFG=0\r\n',b'AT+CIPSNTPCFG?\r\n')


def finalize_plan(names):
    dns=plan(names)[26:-2]
    return (b'AT+SYSSTORE?\r\n',b'AT+CWJAP?\r\n',b'AT+CIPSTATUS\r\n',b'AT+CIPSNTPCFG?\r\n',b'AT+SYSTIMESTAMP?\r\n')+dns+(b'AT+CIPSNTPCFG=0\r\n',b'AT+CIPSNTPCFG?\r\n',b'AT+SYSTIMESTAMP?\r\n')


def exchange(link,bridge,command,out,index,**kw):
    if not getattr(link.byte_grant,'cleanup_started',False):
        g.require(link.sdk_limit-link.sdk_calls>=CLEANUP_RESERVE,'P0A_API_CLEANUP_RESERVE')
    return u.exchange(link,bridge,command,out,index,**kw)


class Grant(q.ByteGrant):
    def __init__(self,commands):super().__init__(commands);self.cleanup_index=len(commands)-2;self.cleanup_started=False
    def cleanup(self):
        g.require(not self.cleanup_started and self.index==len(self.command) and self.commands<=self.cleanup_index,'P0A_CLEANUP_SEQUENCE')
        self.commands=self.cleanup_index;self.cleanup_started=True


def epoch(raw):
    m=re.search(rb'(?:^|\n)\+SYSTIMESTAMP:(\d+)\r?\n',raw)
    return int(m[1]) if m is not None else None


def same_network(raw,ssid):
    m=re.search(rb'\+CWJAP:"([^"\r\n]+)","[^"\r\n]+",(\d+),-?\d+',raw)
    return m is not None and m[1]==ssid.encode('utf-8') and 1<=int(m[2])<=14


def time_gate(values,minimum,enable_ok,readback):
    accepted=[(i,v) for i,v in enumerate(values) if v is not None and v>=minimum]
    return bool(enable_ok and readback and len(accepted)>=2 and accepted[-1][1]>accepted[0][1])


def validate(a):
    g.require(a.get('enabled') is True and a.get('owner_approved') is True and a.get('scope') in (SCOPE,FINALIZE_SCOPE),'P0A_NOT_AUTHORIZED')
    g.require(a.get('tools_sha256')==bindings() and time.time()<a.get('expires_unix',0),'P0A_SOURCE_OR_EXPIRY')
    final=a['scope']==FINALIZE_SCOPE
    g.require(a.get('session_timeout_s')==(90 if final else 180) and a.get('SNTP_enable_max')==(0 if final else 1) and a.get('manual_UDP_payloads')==0
        and a.get('timestamp_queries')==(2 if final else 15) and a.get('reset_halt_go')==0 and a.get('retries')==0,'P0A_LIMITS')
    g.require(a.get('ESP_present_powered_owner_exception') is True and a.get('owner_no_UID_image_hash_rescan') is True,'P0A_SITE_EXCEPTIONS')
    g.require(g.sha((g.ROOT/'node-b/docs'/(FINALIZE_CARD if final else CARD)).read_bytes())==a['card_sha256'],'P0A_CARD')
    network=g.load(a['network_reference']);g.require(network['persist'] is False,'P0A_NETWORK_REFERENCE')
    source=g.private.read(Path(a['servers_reply_reference']),False)
    names=[s.decode('ascii') for s in re.findall(rb'"([A-Za-z0-9.-]{1,64})"',source)]
    g.require(names==a['dns_names'],'P0A_SERVER_REFERENCE')
    commands=finalize_plan(names) if final else plan(names);g.require(g.sha(b''.join(commands))==a['commands_sha256'],'P0A_COMMANDS')
    g.require(a['minimum_epoch']==1792977536 and a['configuration_generation_reference']==4,'P0A_FROZEN_MINIMUM')
    g.private.protected(Path(a['output']).parent,False)
    return commands,network['ssid']


def worker(a,commands,ssid,out):
    out.mkdir(exist_ok=False);g.private.protected(out,False);link=None;bridge=None
    r={'status':'STOP','exit_code':1,'SNTP_enable_attempts':0,'SNTP_disable_attempts':0,'SNTP_stop_verified':False,
       'manual_UDP_payloads':0,'B5START':0,'UID_Flash_options_reads':0,'device_image_hash_checks':0,'reset_halt_go':0,
       'Flash_sector3_writes':0,'device_time_writes':0,'C_DISARMED':False}
    def cleanup():
        link.byte_grant.cleanup();r['SNTP_disable_attempts']+=1
        stopped=exchange(link,bridge,commands[-2],out,len(commands)-2)[0]
        cfg=exchange(link,bridge,commands[-1],out,len(commands)-1)[0]
        r['SNTP_stop_verified']=b'\r\nOK\r\n' in stopped and re.search(rb'\+CIPSNTPCFG:0\r?\n',cfg) is not None
        g.require(r['SNTP_stop_verified'],'P0A_STOP_UNVERIFIED')
    try:
        link=u.UdpLink(out,commands);link.sdk_limit=SDK_LIMIT;link.byte_grant=Grant(commands);link.open()
        g.save(out/'entry-sticky-private.json',{'DHCSR':link.u32(u.CORE['DHCSR'])})
        u.runtime(link,out,'entry');route=q.rx_route_snapshot(link);g.save(out/'route-private.json',route)
        g.require(all(route[k] for k in ('PB10_PB11_AF7','GPIOB_clock_enabled','USART3_clock_enabled','USART3_IRQ_enabled','uptime_advances')),'P0A_UART_ROUTE')
        uart=[link.u32(q.UART+x) for x in (8,12,16,20)];brr,cr1,cr2,cr3=uart
        g.require(abs(q.baud_from_registers(link.u32(0x40023808),brr)-115200)<=1152 and cr1&0xb42c==0x202c
            and not cr2&0x3000 and not cr3&0x300,'P0A_UART_CONFIG')
        g.require(link.call('JLINKARM_IsConnected')==1,'P0A_CONNECTED')
        bridge=u.UartBridge(q.site.config.NativeBus(link));bridge.prove_control_path(link.u32(q.CR),link.u32(q.SR))
        link.query_before_verified=True;bridge.guard=link.byte_grant.check
        pre=[exchange(link,bridge,c,out,i)[0] for i,c in enumerate(commands[:9])]
        g.require(re.search(rb'\+SYSSTORE:0\r?\n',pre[0]) is not None and same_network(pre[1],ssid),'P0A_WIFI_OR_STORE_MISMATCH')
        for idx,pattern in ((3,rb'\+CIPMODE:0\r?\n'),(4,rb'\+CIPMUX:0\r?\n'),(5,rb'\+CIPRECVMODE:[01]\r?\n'),(7,rb'\+CIPSNTPCFG:0\r?\n')):
            g.require(re.search(pattern,pre[idx]) is not None,'P0A_PRECONDITION')
        g.require(u.no_socket(pre[6]),'P0A_SOCKET_OR_WIFI')
        r['receive_mode']=int(re.search(rb'\+CIPRECVMODE:([01])',pre[5])[1]);r['initial_epoch']=epoch(pre[8])
        r['SNTP_enable_attempts']=1;start=time.monotonic()
        enabled=exchange(link,bridge,commands[9],out,9,allow_error=True)[0]
        g.require(b'\r\nOK\r\n' in enabled,'P0A_ENABLE_ERROR')
        cfg=exchange(link,bridge,commands[10],out,10,allow_error=True)[0]
        on=re.search(rb'\+CIPSNTPCFG:1,',cfg) is not None
        names=[n.decode('ascii') for n in re.findall(rb'"([A-Za-z0-9.-]{1,64})"',cfg)]
        g.require(on and names==a['dns_names'],'P0A_READBACK_MISMATCH')
        samples=[]
        for index in range(SAMPLES):
            raw=exchange(link,bridge,commands[11+index],out,11+index,timeout=2,allow_error=True)[0]
            samples.append({'index':index,'epoch':epoch(raw),'elapsed_s':time.monotonic()-start,'host_UTC_ms_reference_only':int(time.time()*1000)})
            if index+1<SAMPLES:time.sleep(1)
        g.save(out/'time-samples-private.json',samples)
        dns=[]
        for index in range(len(a['dns_names'])):
            slot=26+index;raw=exchange(link,bridge,commands[slot],out,slot,timeout=5,allow_error=True)[0]
            m=re.search(rb'\+CIPDOMAIN:"?([0-9.]+)"?\r?\n',raw);ip=None
            if m is not None:
                try:ip=u.reference.ipaddress.IPv4Address(m[1].decode())
                except ValueError:pass
            dns.append({'index':index,'OK':b'\r\nOK\r\n' in raw,'IPv4_parsed':ip is not None,'global_IPv4':bool(ip and ip.is_global)})
        cleanup()
        g.require([link.u32(q.UART+x) for x in (8,12,16,20)]==uart,'P0A_UART_DRIFT')
        u.runtime(link,out,'exit');link.set_close_resume(True)
        values=[s['epoch'] for s in samples];passed=time_gate(values,a['minimum_epoch'],True,on)
        r.update(status='P0A_FIRST_TIME_GATE_PASS' if passed else 'TIME_PRECHECK_BLOCKED',exit_code=0 if passed else 2,
          module_epochs=values,minimum_epoch=a['minimum_epoch'],time_progression_pass=passed,DNS=dns,
          capture_elapsed_s=time.monotonic()-start,C_DISARMED=True,public_fresh_UDP_sample='NOT_RUN_REQUIRES_SEPARATE_P0B_APPROVAL')
    except BaseException as e:
        r.update(g.error_record(e))
        if isinstance(e,ValueError) and re.fullmatch(r'(P0A|UDP|ESP)_[A-Z0-9_]+',str(e)):r['reason']=str(e)
        healthy=link and link.query_before_verified and not link.error and not getattr(link,'read_failed',False) and not getattr(link,'raw_failed',False)
        if healthy:
            try:
                u.runtime(link,out,'failure-exit')
                if r['SNTP_enable_attempts'] and not r['SNTP_disable_attempts']:cleanup()
                link.set_close_resume(True);r['C_DISARMED']=True
            except BaseException:r['failure_cleanup_unverified']=True;link.verified_running_flash=False
    finally:
        if link:
            r.update(UART_native_attempts=link.native_UART_writes,SDK_calls=link.sdk_calls,close_resume=link.close_resume_enabled)
            try:link.close()
            except BaseException:r['exit_code']=1;r['SDK_close_error']=True
        g.save(out/'receipt-private.json',r)
    print(json.dumps({k:r[k] for k in ('status','exit_code','reason','SNTP_stop_verified','SNTP_enable_attempts') if k in r}));return r['exit_code']


def finalize_worker(a,commands,ssid,out):
    out.mkdir(exist_ok=False);g.private.protected(out,False);link=None;bridge=None
    r={'status':'STOP','exit_code':1,'SNTP_enable_attempts':0,'SNTP_disable_attempts':0,'SNTP_stop_verified':False,
       'manual_UDP_payloads':0,'B5START':0,'UID_Flash_options_reads':0,'device_image_hash_checks':0,
       'reset_halt_go':0,'Flash_sector3_writes':0,'device_time_writes':0}
    def stop():
        link.byte_grant.cleanup();r['SNTP_disable_attempts']+=1
        exchange(link,bridge,commands[-3],out,len(commands)-3)
        raw=exchange(link,bridge,commands[-2],out,len(commands)-2)[0]
        r['SNTP_stop_verified']=re.search(rb'\+CIPSNTPCFG:0\r?\n',raw) is not None
        g.require(r['SNTP_stop_verified'],'P0A_STOP_UNVERIFIED')
        return exchange(link,bridge,commands[-1],out,len(commands)-1)[0]
    try:
        link=u.UdpLink(out,commands);link.sdk_limit=SDK_LIMIT;link.byte_grant=Grant(commands)
        link.byte_grant.cleanup_index=len(commands)-3;link.open()
        g.save(out/'entry-sticky-private.json',{'DHCSR':link.u32(u.CORE['DHCSR'])})
        u.runtime(link,out,'entry');g.save(out/'route-private.json',q.rx_route_snapshot(link))
        g.require(link.call('JLINKARM_IsConnected')==1,'P0A_CONNECTED')
        bridge=u.UartBridge(q.site.config.NativeBus(link));bridge.prove_control_path(link.u32(q.CR),link.u32(q.SR))
        link.query_before_verified=True;bridge.guard=link.byte_grant.check
        pre=[exchange(link,bridge,c,out,i)[0] for i,c in enumerate(commands[:5])]
        g.require(re.search(rb'\+SYSSTORE:0\r?\n',pre[0]) is not None and same_network(pre[1],ssid)
            and u.no_socket(pre[2]),'P0A_FINALIZE_PRECONDITION')
        r['initial_epoch']=epoch(pre[4]);dns=[]
        for i in range(len(a['dns_names'])):
            index=5+i;raw=exchange(link,bridge,commands[index],out,index,timeout=5,allow_error=True)[0]
            m=re.search(rb'\+CIPDOMAIN:"?([0-9.]+)"?\r?\n',raw);ip=None
            if m is not None:
                try:ip=u.reference.ipaddress.IPv4Address(m[1].decode())
                except ValueError:pass
            dns.append({'index':i,'OK':b'\r\nOK\r\n' in raw,'IPv4_parsed':ip is not None,'global_IPv4':bool(ip and ip.is_global)})
        stamp=stop();r['final_epoch']=epoch(stamp);r['DNS']=dns
        u.runtime(link,out,'exit');link.set_close_resume(True)
        r.update(status='P0A_REMAINING_DNS_AND_SNTP_STOP_PASS',exit_code=0,C_DISARMED=True)
    except BaseException as e:
        r.update(g.error_record(e))
        if isinstance(e,ValueError) and re.fullmatch(r'(P0A|UDP|ESP)_[A-Z0-9_]+',str(e)):r['reason']=str(e)
        if link and link.query_before_verified and not link.error and not getattr(link,'read_failed',False) and not getattr(link,'raw_failed',False):
            try:
                u.runtime(link,out,'failure-exit')
                if not r['SNTP_disable_attempts']:stop()
                link.set_close_resume(True)
            except BaseException:r['cleanup_unverified']=True;link.verified_running_flash=False
    finally:
        if link:
            r.update(SDK_calls=link.sdk_calls,SDK_limit=link.sdk_limit,UART_native_attempts=link.native_UART_writes,close_resume=link.close_resume_enabled)
            try:link.close()
            except BaseException:r['exit_code']=1;r['SDK_close_error']=True
        g.save(out/'receipt-private.json',r)
    print(json.dumps({k:r[k] for k in ('status','exit_code','reason','SNTP_stop_verified') if k in r}));return r['exit_code']


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--authorization',type=Path);parser.add_argument('--execute',action='store_true');parser.add_argument('--worker',action='store_true');args=parser.parse_args()
    if not args.execute and not args.worker:print(json.dumps({'enabled':False,'scope':SCOPE,'manual_UDP_payloads':0,'B5START':0}));return 0
    try:
        a=g.load(args.authorization);commands,ssid=validate(a);out=Path(a['output'])
        if args.worker:
            used=g.load(args.authorization.with_suffix('.used'));g.require(used['authorization_sha256']==g.sha(args.authorization.read_bytes()),'P0A_PARENT_BINDING')
            return finalize_worker(a,commands,ssid,out) if a['scope']==FINALIZE_SCOPE else worker(a,commands,ssid,out)
        g.require(not out.exists(),'P0A_OUTPUT_EXISTS');g.save(args.authorization.with_suffix('.used'),{'authorization_sha256':g.sha(args.authorization.read_bytes())})
        logfile=out.with_name(out.name+'-worker-private.log');g.write_private(logfile,b'');start=time.monotonic();reason=None
        with logfile.open('ab') as log:
            child=subprocess.Popen([sys.executable,'-X','utf8',__file__,'--worker','--authorization',str(args.authorization)],stdout=log,stderr=subprocess.STDOUT)
            while child.poll() is None:
                if time.monotonic()-start>=a['session_timeout_s']:reason='P0A_HARD_180S'
                if (out/'STOP').exists():reason='P0A_OWNER_STOP'
                event=__import__('b5_g3_joint').last_event(out/'heartbeat-events.jsonl')
                if event.get('active') and time.monotonic()>event['deadline_monotonic']:reason='P0A_NATIVE_DEADLINE'
                if reason:child.kill();break
                time.sleep(.05)
            child.wait(timeout=5)
        out.mkdir(exist_ok=True);receipt=g.maybe(out/'receipt-private.json') or {}
        summary={'reason':reason,'worker_exit_code':child.returncode,'exit_code':1 if reason else child.returncode,'retry':False,
            'SNTP_stop_verified':receipt.get('SNTP_stop_verified',False),'B5START':0,'manual_UDP_payloads':0}
        g.save(out/'supervisor-private.json',summary)
        if receipt.get('SNTP_enable_attempts') and not receipt.get('SNTP_stop_verified'):print(json.dumps({'event':'C_POWER_OFF_REQUIRED_SNTP_STATE_UNKNOWN'}),flush=True)
        return summary['exit_code']
    except BaseException as e:print(json.dumps({'status':'STOP','error_type':type(e).__name__,'exit_code':1}));return 1


if __name__=='__main__':raise SystemExit(main())
