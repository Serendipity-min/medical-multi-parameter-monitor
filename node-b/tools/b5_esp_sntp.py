"""一次易失SNTP启用及固定时间观察，不启动MQTT/B5。"""
import argparse
import ipaddress
import json
from pathlib import Path
import re
import subprocess
import sys
import time

import b5_esp_time as t
q=t.q;g=t.g
SCOPE='B5_ESP_VOLATILE_SNTP_ENABLE_READBACK_TIME_OBSERVATION'
CARD='AUTH-B5-ESP-SNTP-001-R1.md'
DNS_SCOPE='B5_ESP_EXISTING_NTP_THREE_DNS_READ_QUERIES'
DNS_CARD='AUTH-B5-ESP-NTP-DNS-001-R1.md'
SELECT_SCOPE='B5_ESP_EXISTING_SECOND_NTP_VOLATILE_SELECTION_AND_G3_REPLAY'
SELECT_CARD='AUTH-B5-ESP-NTP-SELECT-001-R1.md'
OFFSETS=(0,5,15,30)


def bindings():return {**t.bindings(),'b5_esp_sntp.py':g.sha(Path(__file__).read_bytes())}


def command_plan(full,dns_names=None,selected_server=None):
    g.require(g.sha(full)==g.C_FULL,'SNTP_REFERENCE_IMAGE')
    _,minimum,fields=t.parse_record(full[49152:49152+336])
    if selected_server is not None:
        g.require(re.fullmatch(r'[A-Za-z0-9.-]{1,64}',selected_server) is not None,'SNTP_SELECTED_TARGET')
        return (b'AT+SYSSTORE?\r\n',b'AT+CIPSNTPCFG=1,0,"'+selected_server.encode()+b'"\r\n',
          b'AT+CIPSNTPCFG?\r\n')+(b'AT+SYSTIMESTAMP?\r\n',)*4+(
          b'AT+CIPSNTPCFG=1,0\r\n',b'AT+CIPSNTPCFG?\r\n',b'AT+SYSTIMESTAMP?\r\n',
          b'AT+CIPSNTPCFG=0\r\n',b'AT+CIPSNTPCFG?\r\n'),minimum
    if dns_names is not None:
        g.require(1<=len(dns_names)<=3 and all(re.fullmatch(r'[A-Za-z0-9.-]{1,64}',n) for n in dns_names),'SNTP_DNS_TARGET')
        return tuple(b'AT+CIPDOMAIN="'+n.encode('ascii')+b'"\r\n' for n in dns_names),minimum
    wifi=b'AT+CWJAP="'+fields['ssid']+b'","'+fields['wifi_password']+b'"\r\n'
    commands=(b'AT+SYSSTORE=0\r\n',b'AT+SYSSTORE?\r\n',b'AT+CWMODE=1\r\n',wifi,
              b'AT+SLEEP=0\r\n',b'AT+CIPSNTPCFG=1,0\r\n',b'AT+CIPSNTPCFG?\r\n')+(b'AT+SYSTIMESTAMP?\r\n',)*4+(
              b'AT+CIPSNTPCFG=0\r\n',b'AT+CIPSNTPCFG?\r\n')
    return commands,minimum


class SyncLink(q.QueryLink):
    def __init__(self,out,commands):
        self.BYTE_COMMANDS=tuple(commands);super().__init__(out)


def findings(enable_reply,config_reply,samples,minimum):
    parsed=t.interpret(config_reply,samples[-1]['raw'],minimum)
    values=[t.interpret(config_reply,x['raw'],minimum)['SYSTIMESTAMP_epoch_observed'] for x in samples]
    valid=[(x,v) for x,v in zip(samples,values) if v is not None and v>=minimum]
    progresses=len(valid)>=2 and valid[-1][1]>valid[0][1]
    skews=[abs(x['UTC_ms']/1000-v) for x,v in valid]
    ok=b'\r\nOK\r\n' in enable_reply and parsed['SNTP_enabled_observed'] is True and progresses and max(skews,default=999999)<=5
    return {'enable_OK':b'\r\nOK\r\n' in enable_reply,'enable_ERROR':b'\r\nERROR\r\n' in enable_reply,
       'readback_SNTP_enabled':parsed['SNTP_enabled_observed'],'timestamp_epochs':values,
       'sample_offsets_s':[x['elapsed_s'] for x in samples],'minimum_epoch':minimum,
       'time_progresses':progresses,'max_host_skew_s':max(skews) if skews else None,
       'coarse_UTC_observation_pass':ok,'fresh_nonce_UDP_SNTP_TLS_validation':'RESERVED_FOR_G3_NOT_PROVEN_HERE'}


def dns_findings(replies):
    out=[]
    for raw in replies:
        match=re.search(rb'(?:^|\n)\+CIPDOMAIN:([^\r\n]+)',raw);address=None
        if match:
            try:address=ipaddress.ip_address(match[1].strip(b'"').decode('ascii'))
            except ValueError:pass
        out.append({'OK':b'\r\nOK\r\n' in raw,'ERROR':b'\r\nERROR\r\n' in raw,
                    'IP_parsed':address is not None,'IP_sha256':g.sha(str(address).encode()) if address else None})
    return {'DNS_queries':out,'all_resolved':all(x['OK'] and x['IP_parsed'] for x in out),
            'UDP_123_reachability':'NOT_PROVEN_BY_DNS'}


def validate(a):
    g.require(a.get('enabled') is True and a.get('owner_approved') is True and a.get('scope') in (SCOPE,DNS_SCOPE,SELECT_SCOPE),'SNTP_OWNER_SCOPE')
    dns=a['scope']==DNS_SCOPE;selected=a['scope']==SELECT_SCOPE
    g.require(a.get('tools_sha256')==bindings() and a.get('expires_unix',0)>time.time(),'SNTP_SOURCE_EXPIRY')
    g.require(a.get('card_sha256')==g.sha((g.ROOT/'node-b/docs'/(DNS_CARD if dns else SELECT_CARD if selected else CARD)).read_bytes()),'SNTP_CARD_DRIFT')
    g.require(a.get('reset_halt_go')==0 and a.get('retries')==0 and a.get('session_timeout_s')==180
              and a.get('offsets_s')==([] if dns else list(OFFSETS)),'SNTP_BUDGET')
    raw=g.private.read(Path(a['bundle']),False);g.require(g.sha(raw)==a['bundle_sha256'],'SNTP_BUNDLE_DRIFT');bundle=json.loads(raw)
    for key in ('C_identity','C_full','C_options'):
        g.require(g.sha(g.private.read(Path(bundle[key]['path']),False))==bundle[key]['sha256'],'SNTP_REFERENCE_DRIFT')
    g.require(g.sha(g.private.read(Path(a['C_ELF']),False))==q.ELF_SHA,'SNTP_ELF_DRIFT')
    if dns or selected:
        raw=g.private.read(Path(a['source_config_reply']),False)
        g.require(g.sha(raw)==a.get('source_config_reply_sha256'),'SNTP_DNS_SOURCE_DRIFT')
        names=[x.decode('ascii') for x in re.findall(rb'"([^"\r\n]+)"',raw)]
        if dns:g.require(names==a.get('dns_names'),'SNTP_DNS_SOURCE_TARGETS')
        if selected:
            g.require(len(names)>=2 and a.get('selected_server')==names[1],'SNTP_ONLY_EXISTING_SECOND_SERVER')
            proof=g.private.read(Path(a['PC_reference_receipt']),False)
            g.require(g.sha(proof)==a.get('PC_reference_receipt_sha256') and json.loads(proof)['results'][1]['valid'] is True,'SNTP_REFERENCE_NOT_VALID')
    commands,_=command_plan(g.private.read(Path(bundle['C_full']['path']),False),a.get('dns_names') if dns else None,
                           a.get('selected_server') if selected else None)
    g.require(a.get('commands_sha256')==g.sha(b''.join(commands))
       and a.get('volatile_UART_bytes_approved')==sum(map(len,commands)),'SNTP_EXACT_COMMAND_GRANT')
    raw=g.private.read(Path(a['site_record']),False);g.require(g.sha(raw)==a['site_sha256'],'SNTP_SITE_DRIFT')
    site=json.loads(raw)
    g.require(all(site.get(k) is True for k in ('JLink_on_C','C_J5_only','B_off','C_USB_disconnected',
       'ESP_present_powered','P5_unchanged','no_additional_RESET','no_human')),'SNTP_SITE')
    g.private.protected(Path(a['output']).parent,False)
    return bundle,commands


def observe_times(link,bridge,commands,out,start_index):
    g.require(time.monotonic()-link.started<95,'SNTP_POSTVERIFY_BUDGET')
    start=time.monotonic();samples=[]
    for i,offset in enumerate(OFFSETS):
        while time.monotonic()<start+offset:
            link.gate();remaining=start+offset-time.monotonic()
            if remaining>0:time.sleep(min(.05,remaining))
        raw=q.capture(link,bridge,commands[start_index+i],out,start_index+i,accept_error=True)
        row={'elapsed_s':time.monotonic()-start,'UTC_ms':int(time.time()*1000),'raw':raw};samples.append(row)
        g.save(out/f'time-{i}-timing-private.json',{k:v for k,v in row.items() if k!='raw'})
    return samples


def observe_selected(link,bridge,commands,out,minimum,r,selected_server):
    store=q.capture(link,bridge,commands[0],out,0)
    g.require(re.search(rb'(?:^|\n)\+SYSSTORE:0\r?\n',store) is not None,'SNTP_VOLATILE_NOT_VERIFIED')
    r.pop('NTP_server_changes',None)
    r['SNTP_enable_attempted']=True;r['NTP_volatile_server_selection_attempts']=1
    r['NTP_selection_scope']='VOLATILE_EXISTING_SECOND_PLUS_EXACT_G3_DEFAULT_REPLAY'
    enabled=q.capture(link,bridge,commands[1],out,1,accept_error=True)
    cfg=q.capture(link,bridge,commands[2],out,2,accept_error=True)
    samples=observe_times(link,bridge,commands,out,3);result=findings(enabled,cfg,samples,minimum);r['findings']=result
    replay=q.capture(link,bridge,commands[7],out,7,accept_error=True)
    cfg_after=q.capture(link,bridge,commands[8],out,8,accept_error=True)
    stamp=q.capture(link,bridge,commands[9],out,9,accept_error=True)
    hosts=re.findall(rb'"([^"\r\n]+)"',cfg_after)
    result.update(exact_G3_enable_OK=b'\r\nOK\r\n' in replay,
       exact_G3_preserves_selected_primary=bool(hosts) and hosts[0]==selected_server.encode(),
       after_G3_replay_time=t.interpret(cfg_after,stamp,minimum)['SYSTIMESTAMP_epoch_observed'])
    disabled=q.capture(link,bridge,commands[10],out,10,accept_error=True)
    cfg_stop=q.capture(link,bridge,commands[11],out,11,accept_error=True)
    r['SNTP_stop_verified']=b'\r\nOK\r\n' in disabled and t.interpret(cfg_stop,stamp,minimum)['SNTP_enabled_observed'] is False
    g.require(r['SNTP_stop_verified'],'SNTP_STOP_NOT_VERIFIED')
    return result


def observe_sntp(link,bridge,commands,out,minimum,r):
    replies=[]
    for i in range(7):
        if i==5:r['SNTP_enable_attempted']=True
        raw=q.capture(link,bridge,commands[i],out,i,accept_error=i>=5,response_timeout_s=30 if i==3 else 3)
        replies.append(raw)
        if i==1:g.require(re.search(rb'(?:^|\n)\+SYSSTORE:0\r?\n',raw) is not None,'SNTP_VOLATILE_NOT_VERIFIED')
    samples=observe_times(link,bridge,commands,out,7)
    result=findings(replies[5],replies[6],samples,minimum);r['findings']=result
    disabled=q.capture(link,bridge,commands[11],out,11,accept_error=True)
    stopped_cfg=q.capture(link,bridge,commands[12],out,12,accept_error=True)
    r['SNTP_stop_verified']=b'\r\nOK\r\n' in disabled and t.interpret(stopped_cfg,samples[-1]['raw'],minimum)['SNTP_enabled_observed'] is False
    g.require(r['SNTP_stop_verified'],'SNTP_STOP_NOT_VERIFIED')
    return result


def worker(a,bundle,commands,out):
    out.mkdir(exist_ok=False);g.private.protected(out,False);link=None;full=None;options=None
    r={'status':'STOP','exit_code':1,'B5START':0,'Flash_options_sector3_writes':0,'agent_reset_halt_go':0,
       'manual_time_set':0,'NTP_server_changes':0,'formal_cloud_changes':0,'SNTP_enable_attempted':False,'SNTP_stop_verified':False}
    try:
        link=SyncLink(out,commands);link.open();ident=q.site.ro.raw.identity(link);g.save(out/'identity-private.json',ident)
        g.require(ident==g.load(bundle['C_identity']['path']),'SNTP_C_IDENTITY')
        link.u32(q.site.ro.SYSTEM['DHCSR']);state=q.site.ro.old.snapshot(link);g.save(out/'entry-private.json',state);q.site.ro.old.check_running(link,state)
        full=link.read(0x08000000,1048576);options=link.read(0x1fffc000,16)
        g.write_private(out/'before-full-private.bin',full);g.write_private(out/'before-options-private.bin',options)
        g.require(g.sha(full)==g.C_FULL and g.sha(options)==bundle['C_options']['sha256'] and link.read(q.site.RAM,4)==bytes(4),'SNTP_IMAGE_DISARMED')
        dns=a.get('scope')==DNS_SCOPE;selected=a.get('scope')==SELECT_SCOPE
        actual,minimum=command_plan(full,a.get('dns_names') if dns else None,a.get('selected_server') if selected else None);g.require(actual==commands,'SNTP_COMMAND_IMAGE_DRIFT')
        uart=[link.u32(q.UART+x) for x in (8,12,16,20)];brr,cr1,cr2,cr3=uart
        baud=q.baud_from_registers(link.u32(0x40023808),brr)
        g.require(abs(baud-115200)<=1152 and cr1&0xb42c==0x202c and not cr2&0x3000 and not cr3&0x300,'SNTP_UART_CONFIG')
        g.require(link.call('JLINKARM_IsConnected')==1,'SNTP_SDK_CONNECTED')
        bridge=q.DapBridge(q.site.config.NativeBus(link));bridge.probe(link.u32(0xe000ed00),link.read(0x08000000,64),link.u32(q.CR),link.u32(q.SR))
        link.query_before_verified=True;bridge.guard=link.byte_grant.check
        result=(dns_findings([q.capture(link,bridge,c,out,i,accept_error=True,response_timeout_s=10)
                for i,c in enumerate(commands)]) if dns else observe_selected(link,bridge,commands,out,minimum,r,a['selected_server'])
                if selected else observe_sntp(link,bridge,commands,out,minimum,r))
        g.require([link.u32(q.UART+x) for x in (8,12,16,20)]==uart,'SNTP_UART_DRIFT')
        t.verify_exit(link,out,full,options,'exit')
        r.update(status='DNS_FIXED_DIAGNOSTIC_CAPTURED' if dns else 'SELECTED_SNTP_G3_REPLAY_CAPTURED' if selected else 'SNTP_FIXED_DIAGNOSTIC_CAPTURED',exit_code=0,findings=result,
                 full_sha256=g.sha(full),options_sha256=g.sha(options),DISARMED=True)
    except BaseException as error:
        r.update(g.error_record(error))
        if re.fullmatch(r'(?:SNTP|ESP|S3)_[A-Z0-9_]+',str(error)):r['reason']=str(error)
        if (link and full is not None and link.query_before_verified and not link.error
            and not getattr(link,'raw_failed',False) and not getattr(link,'read_failed',False)
            and r.get('reason') in ('ESP_NO_BYTES','ESP_RESPONSE_NOT_OK','ESP_UART_ERROR_OR_OTHER_CONSUMER','SNTP_VOLATILE_NOT_VERIFIED')):
            try:t.verify_exit(link,out,full,options,'protocol-failure-exit')
            except BaseException as cleanup:r['exit_check_error_type']=type(cleanup).__name__;link.verified_running_flash=False
    finally:
        if link:
            r.update(UART_native_attempts=link.native_UART_writes,UART_granted_bytes=len(link.byte_grant.history),SDK_calls=link.sdk_calls,close_resume=link.close_resume_enabled)
            try:link.close()
            except BaseException as error:r.update(exit_code=1,close_error_type=type(error).__name__)
        g.save(out/'receipt-private.json',r)
    if r['SNTP_enable_attempted'] and not r['SNTP_stop_verified']:
        print(json.dumps({'event':'MANUAL_C_J5_JLINK_USB_OFF_REQUIRED_SNTP_STOP_UNKNOWN'}),flush=True)
    print(json.dumps({k:r[k] for k in ('status','exit_code','findings','reason') if k in r}));return r['exit_code']


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--execute',action='store_true');parser.add_argument('--worker',action='store_true');parser.add_argument('--authorization',type=Path);args=parser.parse_args()
    if not args.execute and not args.worker:
        print(json.dumps({'enabled':False,'scope':SCOPE,'session_timeout_s':180,'offsets_s':OFFSETS,'B5START':0}));return 0
    try:
        a=g.load(args.authorization);bundle,commands=validate(a);out=Path(a['output'])
        if args.worker:
            marker=g.load(args.authorization.with_suffix('.used'));g.require(marker['authorization_sha256']==g.sha(args.authorization.read_bytes()),'SNTP_PARENT_BINDING')
            return worker(a,bundle,commands,out)
        g.require(not out.exists(),'SNTP_OUTPUT_EXISTS');g.save(args.authorization.with_suffix('.used'),{'authorization_sha256':g.sha(args.authorization.read_bytes())})
        log=out.with_name(out.name+'-worker-private.log');g.write_private(log,b'');start=time.monotonic();reason=None
        with log.open('ab') as f:
            child=subprocess.Popen([sys.executable,'-X','utf8',__file__,'--worker','--authorization',str(args.authorization)],stdout=f,stderr=subprocess.STDOUT)
            while child.poll() is None:
                if time.monotonic()-start>180:reason='SNTP_SESSION_180S'
                if (out/'STOP').exists():reason='SNTP_OWNER_STOP'
                event=__import__('b5_g3_joint').last_event(out/'heartbeat-events.jsonl')
                if event.get('active') and time.monotonic()>event['deadline_monotonic']:reason='SNTP_NATIVE_DEADLINE'
                if reason:child.kill();break
                time.sleep(.05)
            child.wait(timeout=5)
        out.mkdir(exist_ok=True);g.save(out/'supervisor-private.json',{'reason':reason,'worker_exit_code':child.returncode,'exit_code':1 if reason else child.returncode,'retry':False})
        receipt=g.maybe(out/'receipt-private.json')
        if reason and (receipt is None or receipt.get('SNTP_enable_attempted') and not receipt.get('SNTP_stop_verified')):
            print(json.dumps({'event':'MANUAL_C_J5_JLINK_USB_OFF_REQUIRED_SNTP_STOP_UNKNOWN'}),flush=True)
        return 1 if reason else child.returncode
    except BaseException as error:
        print(json.dumps({'status':'STOP','exit_code':1,'error_type':type(error).__name__}));return 1


if __name__=='__main__':raise SystemExit(main())
