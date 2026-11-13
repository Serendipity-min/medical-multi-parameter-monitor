"""一次固定时间查询；原始回复仅存EFS，不配置SNTP或启动B5。"""
import argparse
import json
from pathlib import Path
import re
import subprocess
import sys
import time

import b5_esp_gmr as q
import b5_g3_contract as g
from b5_sector3_plan import parse_record

SCOPE='B5_ESP_TIME_TWO_FIXED_READ_QUERIES_NO_FLASH_NO_START'
CARD='AUTH-B5-ESP-TIME-DIAG-001-R1.md'
COMMANDS=(b'AT+CIPSNTPCFG?\r\n',b'AT+SYSTIMESTAMP?\r\n')
MAX_BYTES=sum(map(len,COMMANDS))


def bindings():return {**q.bindings(),'b5_esp_time.py':g.sha(Path(__file__).read_bytes())}


class TimeLink(q.QueryLink):
    BYTE_COMMANDS=COMMANDS


def interpret(config_reply,timestamp_reply,minimum_epoch):
    cfg=re.search(rb'(?:^|\n)\+CIPSNTPCFG:([01])(?:,(-?[0-9]+)([^\r\n]*))?\r?\n',config_reply)
    stamp=re.search(rb'(?:^|\n)\+SYSTIMESTAMP:([0-9]+)\r?\n',timestamp_reply)
    epoch=int(stamp[1]) if stamp else None
    return {'SNTP_enabled_observed':bool(int(cfg[1])) if cfg else None,
       'SNTP_timezone_observed':int(cfg[2]) if cfg and cfg[2] is not None else None,
       'SNTP_server_details':('RAW_PRIVATE_ONLY' if cfg[3] else 'NOT_REPORTED') if cfg else 'NOT_PARSED',
       'SYSTIMESTAMP_epoch_observed':epoch,'minimum_epoch':minimum_epoch,
       'timestamp_meets_C_gate_now':epoch is not None and epoch>=minimum_epoch,
       'config_query_OK':b'\r\nOK\r\n' in config_reply,
       'config_query_ERROR':b'\r\nERROR\r\n' in config_reply,
       'timestamp_query_OK':b'\r\nOK\r\n' in timestamp_reply,
       'timestamp_query_ERROR':b'\r\nERROR\r\n' in timestamp_reply,
       'prior_G3_TIME_root_cause':'NOT_PROVEN_BY_POST_POWER_CYCLE_QUERY',
       'cold_boot_ROM_fix':'NOT_VALIDATED'}


def validate(a):
    g.require(a.get('enabled') is True and a.get('owner_approved') is True and a.get('scope')==SCOPE,'TIME_OWNER_SCOPE')
    g.require(a.get('tools_sha256')==bindings() and a.get('expires_unix',0)>time.time(),'TIME_TOOL_OR_EXPIRY')
    g.require(a.get('card_sha256')==g.sha((g.ROOT/'node-b/docs'/CARD).read_bytes()),'TIME_CARD_DRIFT')
    g.require(a.get('commands_hex')==[x.hex() for x in COMMANDS] and a.get('volatile_UART_bytes_approved')==MAX_BYTES
       and a.get('reset_halt_go')==0 and a.get('retries')==0 and a.get('session_timeout_s')==180,'TIME_EXACT_BYTE_SCOPE')
    g.require(g.sha(g.private.read(Path(a['C_ELF']),False))==q.ELF_SHA,'TIME_ELF_DRIFT')
    raw=g.private.read(Path(a['bundle']),False)
    g.require(g.sha(raw)==a['bundle_sha256'],'TIME_BUNDLE_DRIFT');bundle=json.loads(raw)
    for key in ('C_identity','C_options','C_full'):
        g.require(g.sha(g.private.read(Path(bundle[key]['path']),False))==bundle[key]['sha256'],'TIME_REFERENCE_DRIFT')
    g.require(bundle['C_full']['sha256']==g.C_FULL,'TIME_EXPECTED_IMAGE')
    raw=g.private.read(Path(a['site_record']),False);g.require(g.sha(raw)==a['site_sha256'],'TIME_SITE_DRIFT')
    site=json.loads(raw)
    g.require(all(site.get(k) is True for k in ('JLink_on_C','C_J5_only','B_off','C_USB_disconnected',
       'all_dark_10s_before_transfer','JTAG_direction_verified','ESP_present_powered','P5_unchanged','no_RESET','no_human')),
       'TIME_SITE_INCOMPLETE')
    g.private.protected(Path(a['output']).parent,False)
    return bundle


def verify_exit(link,out,full,options,label):
    after=link.read(0x08000000,1048576);opts=link.read(0x1fffc000,16)
    g.write_private(out/'after-full-private.bin',after);g.write_private(out/'after-options-private.bin',opts)
    g.require(after==full and opts==options and link.read(q.site.RAM,4)==bytes(4),'TIME_POST_IMAGE_OR_DISARMED')
    state=q.site.ro.old.snapshot(link);g.save(out/(label+'-private.json'),state);q.site.ro.old.check_running(link,state)
    link.set_close_resume(True)


def worker(a,bundle,out):
    out.mkdir(exist_ok=False);g.private.protected(out,False);link=None;full=None;options=None
    r={'status':'STOP','exit_code':1,'B5START':0,'Flash_options_config_writes':0,'halt_go_reset':0,
       'UART_configuration_GPIO_writes':0,'SNTP_config_time_setting_WIFI_commands':0}
    try:
        link=TimeLink(out);link.open();ident=q.site.ro.raw.identity(link);g.save(out/'identity-private.json',ident)
        g.require(ident==g.load(bundle['C_identity']['path']),'TIME_C_IDENTITY')
        link.u32(q.site.ro.SYSTEM['DHCSR']);state=q.site.ro.old.snapshot(link)
        g.save(out/'entry-private.json',state);q.site.ro.old.check_running(link,state)
        full=link.read(0x08000000,1048576);options=link.read(0x1fffc000,16)
        g.write_private(out/'before-full-private.bin',full);g.write_private(out/'before-options-private.bin',options)
        g.require(g.sha(full)==g.C_FULL and g.sha(options)==bundle['C_options']['sha256']
                  and link.read(q.site.RAM,4)==bytes(4),'TIME_IMAGE_OPTIONS_DISARMED')
        _,minimum_epoch,private_fields=parse_record(full[49152:49152+336]);del private_fields
        cfg=[link.u32(q.UART+x) for x in (8,12,16,20)];brr,cr1,cr2,cr3=cfg
        baud=q.baud_from_registers(link.u32(0x40023808),brr)
        g.require(abs(baud-115200)<=1152 and cr1&0xb42c==0x202c and not cr2&0x3000 and not cr3&0x300,'TIME_UART_CONFIG')
        g.save(out/'UART-before-private.json',{'BRR_CR1_CR2_CR3':cfg,'register_implied_baud':baud})
        g.require(link.call('JLINKARM_IsConnected')==1,'TIME_SDK_CONNECTED')
        bridge=q.DapBridge(q.site.config.NativeBus(link))
        bridge.probe(link.u32(0xe000ed00),link.read(0x08000000,64),link.u32(q.CR),link.u32(q.SR))
        link.query_before_verified=True;bridge.guard=link.byte_grant.check
        replies=[q.capture(link,bridge,command,out,i,accept_error=True) for i,command in enumerate(COMMANDS)]
        findings=interpret(*replies,minimum_epoch)
        g.require([link.u32(q.UART+x) for x in (8,12,16,20)]==cfg,'TIME_UART_CONFIG_CHANGED')
        verify_exit(link,out,full,options,'exit')
        r.update(status='TIME_QUERY_CAPTURE_COMPLETE_NOT_ROOT_CAUSE_PASS',exit_code=0,findings=findings,
                 full_sha256=g.sha(full),options_sha256=g.sha(options),DISARMED=True)
    except BaseException as error:
        r.update(g.error_record(error))
        if re.fullmatch(r'(?:TIME|ESP|S3)_[A-Z0-9_]+',str(error)):r['reason']=str(error)
        # 只在纯协议失败且SDK仍健康时读回退出证据，不重发任何命令。
        if (link and full is not None and link.query_before_verified and not link.error
            and not getattr(link,'raw_failed',False) and not getattr(link,'read_failed',False)
            and r.get('reason') in ('ESP_NO_BYTES','ESP_RESPONSE_NOT_OK','ESP_UART_ERROR_OR_OTHER_CONSUMER')):
            try:verify_exit(link,out,full,options,'protocol-failure-exit')
            except BaseException as cleanup:
                r['failure_exit_check_error_type']=type(cleanup).__name__;link.verified_running_flash=False
    finally:
        if link:
            r.update(UART_granted_bytes=len(link.byte_grant.history),UART_native_attempts=link.native_UART_writes,
                     SDK_calls=link.sdk_calls,close_resume=link.close_resume_enabled)
            try:link.close()
            except BaseException as error:r.update(exit_code=1,close_error_type=type(error).__name__)
        g.save(out/'receipt-private.json',r)
    print(json.dumps({k:r[k] for k in ('status','exit_code','findings','reason') if k in r}));return r['exit_code']


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--authorization',type=Path)
    parser.add_argument('--execute',action='store_true');parser.add_argument('--worker',action='store_true');args=parser.parse_args()
    if not args.execute and not args.worker:
        print(json.dumps({'enabled':False,'scope':SCOPE,'commands_hex':[x.hex() for x in COMMANDS],
                          'UART_bytes_max':MAX_BYTES,'B5START':0}));return 0
    try:
        a=g.load(args.authorization);bundle=validate(a);out=Path(a['output'])
        if args.worker:
            marker=g.load(args.authorization.with_suffix('.used'))
            g.require(marker['authorization_sha256']==g.sha(args.authorization.read_bytes()),'TIME_PARENT_BINDING')
            return worker(a,bundle,out)
        g.require(not out.exists(),'TIME_OUTPUT_EXISTS')
        g.save(args.authorization.with_suffix('.used'),{'authorization_sha256':g.sha(args.authorization.read_bytes())})
        log=out.with_name(out.name+'-worker-private.log');g.write_private(log,b'')
        started=time.monotonic();reason=None
        with log.open('ab') as f:
            child=subprocess.Popen([sys.executable,'-X','utf8',__file__,'--worker','--authorization',str(args.authorization)],stdout=f,stderr=subprocess.STDOUT)
            while child.poll() is None:
                if time.monotonic()-started>180:reason='TIME_SESSION_180S'
                if (out/'STOP').exists():reason='TIME_OWNER_STOP'
                event=__import__('b5_g3_joint').last_event(out/'heartbeat-events.jsonl')
                if event.get('active') and time.monotonic()>event['deadline_monotonic']:reason='TIME_NATIVE_DEADLINE'
                if reason:child.kill();break
                time.sleep(.05)
            child.wait(timeout=5)
        out.mkdir(exist_ok=True);g.save(out/'supervisor-private.json',{'reason':reason,'worker_exit_code':child.returncode,
            'exit_code':1 if reason else child.returncode,'retry':False,'MCU_stop_not_implied_by_process_exit':True})
        return 1 if reason else child.returncode
    except BaseException as error:
        print(json.dumps({'status':'STOP','exit_code':1,'error_type':type(error).__name__}));return 1


if __name__=='__main__':raise SystemExit(main())
