"""独立ESP版本查询：默认计划；固定UART字节写入，不烧录、不启动B5。"""
import argparse
import ctypes as C
import json
from pathlib import Path
import re
import struct
import subprocess
import sys
import time

import b5_g3_contract as g
import b5_g3_devices as previous
import b5_g2_site as site
import runtime_state_b as runtime
from b5_sector3_write_protocol import DapBridge, CR, SR

SCOPE='B5_ESP_GMR_FIXED_UART_QUERY_NO_FLASH_NO_CPU_CONTROL'
CARD='AUTH-B5-ESP-GMR-001-R4.md'
ELF_SHA='3c726f61f76eadac4909826203ca84dee65521aec448ad477ddca0c3c58795d8'
UART=0x40004800; DR=UART+4
STATS=0x2000f6c0; RING=0x2000f6d4; CAPACITY=8192; UPTIME=0x2001170c
COMMANDS=(b'AT\r\n',b'AT+GMR\r\n')
READS={a:set(n) for a,n in previous.C_READS.items()}
READS.update({UART:{4},UART+8:{4},UART+12:{4},UART+16:{4},UART+20:{4},
              0x40023800:{4},0x40023808:{4},STATS:{20},RING:{CAPACITY},UPTIME:{4}})
RX_ROUTE_REGISTERS={'GPIOB_MODER':0x40020400,'GPIOB_IDR':0x40020410,'GPIOB_AFRH':0x40020424,
    'RCC_AHB1ENR':0x40023830,'RCC_APB1ENR':0x40023840,'NVIC_ISER1':0xe000e104,
    'NVIC_ISPR1':0xe000e204,'NVIC_IABR1':0xe000e304,'USART3_SR':UART}
READS.update({a:{4} for a in RX_ROUTE_REGISTERS.values()})


def bindings():return {**g.bindings(),'b5_esp_gmr.py':g.sha(Path(__file__).read_bytes())}


def extract_version(data):
    text=data.decode('ascii',errors='replace')
    match=re.search(r'(?:^|\n)AT version:([0-9]+(?:\.[0-9]+){1,4}(?:[-+][A-Za-z0-9_.-]+)?)',text)
    g.require(match is not None and b'\r\nOK\r\n' in data,'ESP_GMR_VERSION_OR_OK_MISSING')
    sdk=re.search(r'(?:^|\n)SDK version:([A-Za-z0-9_.+-]+)',text)
    return {'AT_version':match[1],'SDK_version':sdk[1] if sdk else None,
            'physical_module_age_or_flash_capacity':'NOT_ESTABLISHED_BY_GMR'}


class ByteGrant:
    def __init__(self,commands=COMMANDS):
        self.allowed_commands=tuple(commands);self.command=b'';self.index=0;self.history=[];self.commands=0
    def begin(self,command):
        g.require(self.commands<len(self.allowed_commands) and command==self.allowed_commands[self.commands]
                  and self.index==len(self.command),'ESP_COMMAND_SEQUENCE')
        self.command=command;self.index=0;self.commands+=1
    def check(self,address,value):
        g.require(address==DR and self.index<len(self.command) and value==self.command[self.index],
                  'ESP_UART_BYTE_WRITE_DENIED')
        self.history.append(value);self.index+=1


def circular_delta(before,after,blob):
    g.require(0<=before<CAPACITY and 0<=after<CAPACITY and len(blob)==CAPACITY,'ESP_RING_GEOMETRY')
    return blob[before:after] if after>=before else blob[before:]+blob[:after]


def baud_from_registers(cfgr,brr):
    g.require(cfgr&12==4 and brr>0,'ESP_UART_CLOCK_SOURCE')
    ahb=(1,1,1,1,1,1,1,1,2,4,8,16,64,128,256,512)[(cfgr>>4)&15]
    apb=(1,1,1,1,2,4,8,16)[(cfgr>>10)&7]
    return 8000000/ahb/apb/brr


def rx_route_snapshot(link):
    raw={name:link.u32(address) for name,address in RX_ROUTE_REGISTERS.items()}
    first=link.u32(UPTIME);time.sleep(.02);last=link.u32(UPTIME)
    return {'registers':raw,'uptime_samples':[first,last],'uptime_advances':g.signed(last,first)>0,
       'PB10_PB11_AF7':all((raw['GPIOB_MODER']>>(pin*2))&3==2 and (raw['GPIOB_AFRH']>>((pin-8)*4))&15==7 for pin in (10,11)),
       'GPIOB_clock_enabled':bool(raw['RCC_AHB1ENR']&2),'USART3_clock_enabled':bool(raw['RCC_APB1ENR']&(1<<18)),
       'USART3_IRQ_enabled':bool(raw['NVIC_ISER1']&(1<<7)),
       'USART3_IRQ_pending':bool(raw['NVIC_ISPR1']&(1<<7)),
       'USART3_IRQ_active':bool(raw['NVIC_IABR1']&(1<<7)),
       'RXNE':bool(raw['USART3_SR']&(1<<5)),'ORE':bool(raw['USART3_SR']&(1<<3)),
       'DR_reads_or_target_writes':0}


class QueryLink(site.BridgeLink):
    BYTE_COMMANDS=COMMANDS
    def __init__(self,out):
        self.byte_grant=ByteGrant(self.BYTE_COMMANDS);self.query_before_verified=False;self.native_UART_writes=0
        super().__init__(out);self.sdk_limit=6000;self.memory_counts={}
    def call(self,name,*args,timeout=5):
        return site.config.NativeLink.call(self,name,*args,timeout=timeout)
    def _call_native(self,name,*args,timeout=5):
        g.require(name in site.ro.CALLS|{'JLINKARM_CORESIGHT_ReadAPDPReg','JLINKARM_CORESIGHT_WriteAPDPReg'},'ESP_NATIVE_API_DENIED')
        g.require(not getattr(self,'read_failed',False),'ESP_READ_STOP_LATCHED')
        g.require(self.sdk_calls<self.sdk_limit,'ESP_API_BUDGET')
        if name=='JLINKARM_ExecCommand':
            command=args[0].decode('ascii');g.require(command in site.ro.COMMANDS,'ESP_POLICY_DENIED')
            if command=='SetRestartOnClose = 1':g.require(self.verified_running_flash,'ESP_CLOSE_UNVERIFIED')
        if name=='JLINKARM_ReadMemEx':
            address,size=args[:2];g.require(size in READS.get(address,set()) and args[3]==0,'ESP_READ_SCOPE')
            if (address,size) in ((0x08000000,1048576),(0x1fffc000,16)):
                n=self.memory_counts.get((address,size),0);g.require(n<2,'ESP_FULL_OPTIONS_READ_LIMIT')
                self.memory_counts[address,size]=n+1
        if name.endswith('APDPReg'):
            reg,ap=args[:2]
            g.require((ap==0 and reg==2 and name.endswith('WriteAPDPReg')) or (ap==1 and reg in (0,1,3)), 'ESP_DAP_REGISTER_DENIED')
            if name.endswith('WriteAPDPReg'):
                value=args[2]
                if ap==0:g.require(value in (0,0xf0),'ESP_DAP_SELECT')
                if ap==1 and reg==3:
                    g.require(self.query_before_verified and self.dap_select==0 and self.dap_csw is not None and self.dap_csw&0x37==2
                              and self.dap_tar==DR and self.raw_target_grant==(DR,value)
                              and self.native_UART_writes<len(self.byte_grant.history)<=sum(map(len,self.BYTE_COMMANDS))
                              and self.byte_grant.history[self.native_UART_writes]==value,'ESP_DAP_TARGET_WRITE_DENIED')
                    self.native_UART_writes+=1
            elif reg==3 and self.dap_select==0:
                g.require(self.dap_tar in (0xe000ed00,CR,SR) or 0x08000000<=self.dap_tar<0x08000040,'ESP_DAP_READ_SCOPE')
        self.sdk_calls+=1;self.gate();deadline=time.monotonic()+timeout
        self.events.write(json.dumps({'operation':name,'active':True,'deadline_monotonic':deadline})+'\n');self.events.flush()
        result=getattr(self.dll,name)(*args)
        row={'operation':name,'native_return_int':result if isinstance(result,int) else None,'monotonic':time.monotonic()}
        if name=='JLINKARM_ReadMemEx':row.update(address=hex(args[0]),requested=args[1])
        if name.endswith('WriteAPDPReg'):row.update(reg=args[0],AP=args[1],value=args[2])
        self.io.write(json.dumps(row)+'\n');self.io.flush()
        self.events.write(json.dumps({'operation':name,'active':False})+'\n');self.events.flush()
        g.require(time.monotonic()<=deadline,'ESP_NATIVE_TIMEOUT');self.gate()
        if name.endswith('APDPReg') and result>=0:
            v=args[2] if name.endswith('WriteAPDPReg') else C.cast(args[2],C.POINTER(C.c_uint32)).contents.value
            if args[1]==0 and args[0]==2:self.dap_select=v
            if args[1]==1 and self.dap_select==0:
                if args[0]==0:self.dap_csw=v
                if args[0]==1:self.dap_tar=v
        return result
    def read(self,address,size):
        g.require(size in READS.get(address,set()),'ESP_READ_SCOPE');buf=(C.c_uint8*size)()
        try:
            n=self.call('JLINKARM_ReadMemEx',address,size,buf,0,timeout=45 if size==1048576 else 5)
            g.require(n>=0,'ESP_NATIVE_READ_ERROR');g.require(n==size,'ESP_NATIVE_SHORT_READ');return bytes(buf)
        except BaseException:
            self.read_failed=True;self.verified_running_flash=False;raise


def capture(link,bridge,command,out,index,accept_error=False):
    baseline=struct.unpack('<5I',link.read(STATS,20));cursor=baseline[4]
    g.save(out/f'query-{index}-baseline-private.json',{'UART_stats':baseline})
    g.save(out/f'query-{index}-route-before-private.json',rx_route_snapshot(link))
    link.byte_grant.begin(command)
    for value in command:
        until=time.monotonic()+.5
        while not link.u32(UART)&(1<<7):
            g.require(time.monotonic()<=until,'ESP_UART_TX_NOT_READY');time.sleep(.005)
        bridge.write32(DR,value)
    until=time.monotonic()+(2 if index==0 else 3);data=b'';last_changed=time.monotonic();last_head=cursor
    while time.monotonic()<until:
        state=struct.unpack('<5I',link.read(STATS,20))
        if state[:4]!=baseline[:4]:g.save(out/f'query-{index}-changed-state-private.json',{'UART_stats':state})
        g.require(state[:3]==baseline[:3] and state[3]==baseline[3],'ESP_UART_ERROR_OR_OTHER_CONSUMER')
        if state[4]!=last_head:last_changed=time.monotonic();last_head=state[4]
        if time.monotonic()-last_changed>=.1:
            blob=link.read(RING,CAPACITY);after=struct.unpack('<5I',link.read(STATS,20))
            g.require(after[:4]==baseline[:4],'ESP_UART_ERROR_OR_OTHER_CONSUMER')
            if after[4]!=last_head:continue
            data=circular_delta(cursor,last_head,blob)
            if b'\r\nOK\r\n' in data or b'\r\nERROR\r\n' in data or b'\r\nFAIL\r\n' in data:break
        time.sleep(.02)
    g.write_private(out/f'query-{index}-response-private.bin',data)
    meta={'command_hex':command.hex(),'bytes_received':len(data),'sha256':g.sha(data),
          'OK':b'\r\nOK\r\n' in data,'ERROR':b'\r\nERROR\r\n' in data,'UART_new_errors':0}
    g.save(out/f'query-{index}-meta-private.json',meta)
    g.save(out/f'query-{index}-route-after-private.json',rx_route_snapshot(link))
    g.require(meta['OK'] or accept_error and meta['ERROR'],
              'ESP_NO_BYTES' if not data and last_head==cursor else 'ESP_RESPONSE_NOT_OK')
    return data


def validate(a):
    g.require(a.get('enabled') is True and a.get('owner_approved') is True and a.get('scope')==SCOPE,'ESP_OWNER_SCOPE')
    g.require(a.get('tools_sha256')==bindings() and a.get('expires_unix',0)>time.time(),'ESP_TOOL_OR_TIME_DRIFT')
    g.require(a.get('card_sha256')==g.sha((g.ROOT/'node-b/docs'/CARD).read_bytes()),'ESP_CARD_DRIFT')
    g.require(a.get('volatile_UART_bytes_approved')==12 and a.get('reset_halt_go')==0 and a.get('retries')==0,'ESP_WRITE_SCOPE_NOT_APPROVED')
    g.require(g.sha(g.private.read(Path(a['C_ELF']),False))==ELF_SHA,'ESP_ELF_IDENTITY')
    bundle=g.load(a['bundle']);g.require(g.sha(g.private.read(Path(a['bundle']),False))==a['bundle_sha256'],'ESP_BUNDLE_DRIFT')
    for key in ('C_identity','C_options'):
        g.require(g.sha(g.private.read(Path(bundle[key]['path']),False))==bundle[key]['sha256'],'ESP_REFERENCE_DRIFT')
    site_record=g.load(a['site_record'])
    g.require(g.sha(g.private.read(Path(a['site_record']),False))==a['site_sha256'] and all(site_record.get(k) is True for k in
       ('JLink_on_C','C_J5_only','B_off','C_USB_disconnected','P5_unchanged_confirmed','ESP_present_powered','no_human',
        'reseat_owner_reported','photo_P5_WB_route_observed','photo_module_in_P1_observed')),'ESP_SITE_INCOMPLETE')
    return bundle


def worker(a,bundle,out):
    out.mkdir(exist_ok=False);g.private.protected(out,False);link=None
    r={'status':'STOP','exit_code':1,'B5START':0,'Flash_options_config_writes':0,'halt_go_reset':0,'baud_register_writes':0}
    try:
        link=QueryLink(out);link.open();ident=site.ro.raw.identity(link);g.save(out/'identity-private.json',ident)
        g.require(ident==g.load(bundle['C_identity']['path']),'ESP_WRONG_C_IDENTITY')
        link.u32(site.ro.SYSTEM['DHCSR']);state=site.ro.old.snapshot(link);g.save(out/'entry-private.json',state);site.ro.old.check_running(link,state)
        full=link.read(0x08000000,1048576);options=link.read(0x1fffc000,16)
        g.write_private(out/'before-full-private.bin',full);g.write_private(out/'before-options-private.bin',options)
        g.require(g.sha(full)==g.C_FULL and g.sha(options)==bundle['C_options']['sha256'] and link.read(site.RAM,4)==bytes(4),'ESP_CURRENT_FULL_OR_DISARMED')
        brr=link.u32(UART+8);cr1=link.u32(UART+12);cr2=link.u32(UART+16);cr3=link.u32(UART+20)
        cfgr=link.u32(0x40023808);baud=baud_from_registers(cfgr,brr)
        g.save(out/'UART-before-private.json',{'BRR':brr,'CR1':cr1,'CR2':cr2,'CR3':cr3,'RCC_CR':link.u32(0x40023800),'RCC_CFGR':cfgr,'register_implied_baud':baud})
        g.require(abs(baud-115200)<=1152 and cr1&0xb42c==0x202c and not cr2&0x3000 and not cr3&0x300,'ESP_UART_NOT_FROZEN_115200_8N1_RXIRQ')
        g.require(link.call('JLINKARM_IsConnected')==1,'ESP_SDK_NOT_CONNECTED')
        bridge=DapBridge(site.config.NativeBus(link));bridge.probe(link.u32(0xe000ed00),link.read(0x08000000,64),link.u32(CR),link.u32(SR))
        link.query_before_verified=True;bridge.guard=link.byte_grant.check
        capture(link,bridge,COMMANDS[0],out,0);reply=capture(link,bridge,COMMANDS[1],out,1)
        version=extract_version(reply)
        after=link.read(0x08000000,1048576);opts_after=link.read(0x1fffc000,16)
        g.write_private(out/'after-full-private.bin',after);g.write_private(out/'after-options-private.bin',opts_after)
        g.require(after==full and opts_after==options and link.read(site.RAM,4)==bytes(4),'ESP_POST_IMAGE_OR_DISARMED_DRIFT')
        g.require([link.u32(UART+x) for x in (8,12,16,20)]==[brr,cr1,cr2,cr3],'ESP_UART_CONFIG_CHANGED')
        state=site.ro.old.snapshot(link);g.save(out/'exit-private.json',state);site.ro.old.check_running(link,state);link.set_close_resume(True)
        r.update(status='ESP_ACTUAL_GMR_READ_PASS',exit_code=0,**version,full_sha256=g.sha(after),options_sha256=g.sha(opts_after))
    except BaseException as e:
        r.update(g.error_record(e))
        if re.fullmatch(r'(?:ESP|S3)_[A-Z0-9_]+',str(e)):r['reason']=str(e)
        # 查询拒绝不当成CPU故障；只有仍有健康Flash状态才保留正常退出续跑。
        protocol_failure=r.get('reason') in ('ESP_NO_BYTES','ESP_RESPONSE_NOT_OK','ESP_GMR_VERSION_OR_OK_MISSING','ESP_UART_ERROR_OR_OTHER_CONSUMER')
        if protocol_failure and link and not link.error and not getattr(link,'raw_failed',False) and not getattr(link,'read_failed',False):
            try:
                state=site.ro.old.snapshot(link);g.save(out/'failure-exit-private.json',state);site.ro.old.check_running(link,state)
                if link.query_before_verified and r.get('reason') in ('ESP_NO_BYTES','ESP_RESPONSE_NOT_OK','ESP_GMR_VERSION_OR_OK_MISSING','ESP_UART_ERROR_OR_OTHER_CONSUMER'):
                    after=link.read(0x08000000,1048576);opts_after=link.read(0x1fffc000,16)
                    g.write_private(out/'after-full-private.bin',after);g.write_private(out/'after-options-private.bin',opts_after)
                    g.require(after==full and opts_after==options and link.read(site.RAM,4)==bytes(4),'ESP_FAILURE_POST_IMAGE_DRIFT')
                    r['failure_post_full_options_DISARMED_match']=True
                    state=site.ro.old.snapshot(link);g.save(out/'failure-post-verify-state-private.json',state);site.ro.old.check_running(link,state)
                link.set_close_resume(True)
            except BaseException as cleanup:r['failure_exit_check_error_type']=type(cleanup).__name__;link.verified_running_flash=False
    finally:
        if link:
            r.update(UART_byte_permissions_consumed=len(link.byte_grant.history),UART_native_write_attempts=link.native_UART_writes,SDK_calls=link.sdk_calls)
            try:link.close()
            except BaseException as e:r.update(exit_code=1,close_error_type=type(e).__name__)
        g.save(out/'receipt-private.json',r)
    print(json.dumps({k:r[k] for k in ('status','exit_code','AT_version','SDK_version','reason') if k in r}));return r['exit_code']


def main():
    p=argparse.ArgumentParser();p.add_argument('--authorization',type=Path);p.add_argument('--execute',action='store_true');p.add_argument('--worker',action='store_true');args=p.parse_args()
    if not args.execute and not args.worker:
        print(json.dumps({'enabled':False,'scope':SCOPE,'UART_commands':[x.hex() for x in COMMANDS],'target_bytes_max':12,'B5START':0,'tools_sha256':bindings()}));return 0
    try:
        a=g.load(args.authorization);bundle=validate(a);out=Path(a['output']);g.private.protected(out.parent,False)
        if args.worker:
            mark=g.load(args.authorization.with_suffix('.used'));g.require(mark['authorization_sha256']==g.sha(args.authorization.read_bytes()),'ESP_PARENT_BINDING')
            return worker(a,bundle,out)
        g.require(not out.exists(),'ESP_OUTPUT_EXISTS');g.save(args.authorization.with_suffix('.used'),{'authorization_sha256':g.sha(args.authorization.read_bytes())})
        started=time.monotonic();reason=None
        with out.with_name(out.name+'-worker-private.log').open('xb') as f:
            child=subprocess.Popen([sys.executable,'-X','utf8',__file__,'--worker','--authorization',str(args.authorization)],stdout=f,stderr=subprocess.STDOUT)
            while child.poll() is None:
                if time.monotonic()-started>180:reason='ESP_SESSION_180S'
                e=previous.g.maybe(out/'STOP')
                if e:reason='ESP_OWNER_STOP'
                event=__import__('b5_g3_joint').last_event(out/'heartbeat-events.jsonl')
                if event.get('active') and time.monotonic()>event['deadline_monotonic']:reason='ESP_NATIVE_DEADLINE'
                if reason:child.kill();break
                time.sleep(.05)
            child.wait(timeout=5)
        out.mkdir(exist_ok=True);g.save(out/'supervisor-private.json',{'reason':reason,'worker_exit_code':child.returncode,'exit_code':1 if reason else child.returncode,'retry':False})
        return 1 if reason else child.returncode
    except BaseException as e:
        print(json.dumps({'status':'STOP','exit_code':1,'error_type':type(e).__name__}));return 1

if __name__=='__main__':raise SystemExit(main())
