"""C启动/挂接监控；无软件复位、Halt、Go、UART和NVM写入。"""
import argparse
import ctypes as C
import json
from pathlib import Path
import sys
import time
import subprocess

import b4_recovery as recovery
import b5_g3_contract as g
import b5_g2ro as ro
import b5_sector3_write_supervisor as supervision
import readback_b as raw
import runtime_state_b as runtime
from live_state_b import LiveLink

SCOPE='B5_C_BOOT_ATTACH_WATCH_TWO_CONNECTIONS_NO_NVM'
FULL_SHA='81b1808f9936b02f115cef99a47059417eec99eb80dff4ca4cf1f103392588d7'
UPTIME=0x2001200c
FLAGS=0x20001e6a
SDK_LIMIT=4096
CLOSE_RESERVE=384
MAX_SAMPLES=600
FAST={'DHCSR':0xe000edf0,'VTOR':0xe000ed08,'DWT_PCSR':0xe000101c,'uptime':UPTIME,'flags':FLAGS}
SLOW={n:runtime.SYSTEM[n] for n in ('CFSR','HFSR','DFSR','DEMCR','RCC_CSR','RCC_APB2ENR','SYSCFG_MEMRMP','GPIOB_IDR')}
READS={**raw.REGIONS,**{a:4 for a in (*FAST.values(),*SLOW.values())},0:64,0x08000000:64}
CORE={'JLINKARM_GetRegisterList','JLINKARM_GetRegisterName','JLINKARM_ReadReg'}
CALLS=runtime.CALLS
# 本机SDK不支持可选日志增强命令；保留OpenEx原生回调及API时序。
EXTRA_POLICIES=()
require=recovery.require
sha=g.sha


def bindings():
    return {n:sha((g.ROOT/'node-b/tools'/n).read_bytes()) for n in
            ('b5_c_boot_watch.py','readback_b.py','runtime_state_b.py','live_state_b.py',
             'b4_recovery.py','b5_sector3_write_supervisor.py','b5_g2ro.py',
             'b5_g3_contract.py','b5_g0_readonly.py','c_b4_closeout_readonly.py','c_b4_readonly.py')}


def authorize(a,out):
    require(a.get('enabled') is True and a.get('owner_approved') is True and a.get('scope')==SCOPE,'BOOT_WATCH_OWNER')
    require(a.get('tools_sha256')==bindings() and a.get('DLL_sha256')==raw.DLL_SHA,'BOOT_WATCH_TOOL_DRIFT')
    require(a.get('session_timeout_s')==170 and a.get('connections_max')==2 and a.get('connection_s')==75 and
            a.get('manual_RESET_max')==1 and a.get('explicit_halt_reset_go_UART_NVM_writes')==0 and
            a.get('healthy_flash_close_resume_allowed') is True and a.get('retries')==0 and
            a.get('connection_slots_remaining',2) in (1,2) and a.get('expires_unix',0)>time.time(),'BOOT_WATCH_LIMITS')
    require(Path(a['output']).resolve()==out.resolve(),'BOOT_WATCH_OUTPUT')
    for key in ('identity','full','options'):
        require(sha(recovery.read(Path(a[key]),False))==a[key+'_sha256'],'BOOT_WATCH_REFERENCE')
    require(a['full_sha256']==FULL_SHA,'BOOT_WATCH_DEPLOYED_C49048')
    site=g.load(a['site'])
    require(sha(recovery.read(Path(a['site']),False))==a['site_sha256'] and
            all(site.get(k) is True for k in ('C_J5','JTAG_on_C','C_USB_off','B_off','all_dark_10s',
            'C_first_JLink_USB_later','wiring_source_unchanged','ESP_present_powered_exception',
            'no_other_debug_or_serial_program')),'BOOT_WATCH_SITE')
    recovery.protected(out.parent,False)


def kind(s,alias_flash):
    if s['DHCSR']&raw.HALT:return 'HALT'
    if s['DHCSR']&raw.LOCKUP or s.get('CFSR',0) or s.get('HFSR',0):return 'FAULT'
    pc=s['DWT_PCSR']
    if s['VTOR']==0x1fff0000 or 0x1fff0000<=pc<0x1fff7800:return 'ROM'
    if (s['VTOR']==0x08000000 or (s['VTOR']==0 and alias_flash)) and 0x08000000<=pc<0x08000000+49048:return 'FLASH'
    return 'UNKNOWN'


def reset_event(previous,current):
    if current['DHCSR']&raw.RESET:return 'DHCSR_RESET_STICKY_OBSERVED'
    difference=previous['uptime']-current['uptime']
    if 0<difference<0x80000000:return 'APPLICATION_UPTIME_DECREASE_NOT_WRAP'
    return None


def launch_popup(root,now):
    g.save(root/'RESET_INTENT.json',dict(action='OWNER_C_RESET_ONCE',monotonic=now,lease_s=30))
    return subprocess.Popen([sys.executable,'-X','utf8',str(Path(__file__).resolve()),'--popup',str(root)],
                            creationflags=subprocess.CREATE_NO_WINDOW)


def popup(root):
    import tkinter as tk
    intent=g.load(root/'RESET_INTENT.json');expires=intent['monotonic']+intent['lease_s']
    window=tk.Tk();window.title('C板启动调查：仅一次人工复位');window.attributes('-topmost',True)
    window.geometry('650x250');label=tk.Label(window,font=('Microsoft YaHei',13),wraplength=610);label.pack(padx=15,pady=20)
    def done():
        g.save(root/'OWNER_RESET_DONE.json',{'monotonic':time.monotonic(),'fact':'OWNER_REPORT_ONLY'})
        window.destroy()
    def cancel():
        g.save(root/'RESET_CANCELLED.json',{'monotonic':time.monotonic()});window.destroy()
    tk.Button(window,text='已短按一次 RESET',command=done).pack(side='left',padx=70)
    tk.Button(window,text='取消本次操作',command=cancel).pack(side='right',padx=70)
    window.protocol('WM_DELETE_WINDOW',cancel)
    def tick():
        remaining=expires-time.monotonic()
        if remaining<=0 or any((root/n).exists() for n in ('RESET_OBSERVED.json','POPUP_END','STOP')):
            window.destroy();return
        label.config(text=f'C已确认在Flash正常运行。请在{remaining:.0f}秒内仅短按C实体RESET一次。\n不要按第二次；B、供电及接线不动。\n按完点击下方按钮，无需等待聊天回复。')
        window.after(100,tick)
    g.save(root/'POPUP_SHOWN.json',{'monotonic':time.monotonic()});tick();window.mainloop();return 0


class WatchLink(LiveLink):
    def __init__(self,out,heartbeat):
        self.native_read_failed=False;self.native_calls=0
        super().__init__(ro.DLL,out)
        # 原生回调原文仅EFS，保留挂接/关闭上下文；不把它当作完整SWD波形。
        self.events.close();self.events=heartbeat.open('a',encoding='utf8')

    def call(self,name,*args,timeout=5):
        require(name in CALLS,'BOOT_WATCH_FUNCTION_DENIED')
        require(self.sdk_calls<SDK_LIMIT,'BOOT_WATCH_HOST_SDK_BUDGET')
        require(time.monotonic()-self.started<75,'BOOT_WATCH_CONNECTION_LIMIT')
        if name in CORE:require(self.register_reads_allowed,'BOOT_WATCH_CORE_REQUIRES_HALT')
        if name=='JLINKARM_ExecCommand':
            cmd=args[0].decode('ascii')
            require(cmd in runtime.COMMANDS or cmd in EXTRA_POLICIES or
                    (cmd=='SetRestartOnClose = 1' and self.verified_running_flash),'BOOT_WATCH_POLICY_DENIED')
        if name=='JLINKARM_ReadMemEx':require(READS.get(args[0])==args[1] and args[3]==0,'BOOT_WATCH_READ_DENIED')
        event={'phase':'before_native','operation':name,'monotonic':time.monotonic()}
        if name=='JLINKARM_ExecCommand':event['policy']=args[0].decode('ascii')
        if name=='JLINKARM_ReadMemEx':event.update(address=hex(args[0]),bytes=args[1])
        g.append(self.io,'API',event);self.sdk_calls+=1
        self.gate()
        heartbeat={'operation':name,'active':True,'deadline_monotonic':time.monotonic()+timeout}
        self.events.write(json.dumps(heartbeat)+'\n');self.events.flush()
        self.native_calls+=1
        result=getattr(self.dll,name)(*args)
        g.append(self.io,'API_RETURN',{'operation':name,'native_return':result if isinstance(result,int) else None,
                                     'SDK_error_latched':self.error})
        self.events.write(json.dumps({'operation':name,'active':False})+'\n');self.events.flush()
        if name=='JLINKARM_ReadMemEx' and result!=args[1]:self.native_read_failed=True
        require(time.monotonic()<=heartbeat['deadline_monotonic'],'BOOT_WATCH_NATIVE_CALL_TIMEOUT')
        self.gate()
        if name=='JLINKARM_GetHWStatus' and result==0:
            s=args[0]._obj
            g.append(self.io,'PROBE_STATIC_PINS',{n:getattr(s,n) for n,_ in raw.HWStatus._fields_})
        return result

    def policy(self,command):
        if command=='Device = STM32F407ZG':
            for extra in EXTRA_POLICIES:super().policy(extra)
            g.append(self.io,'PRE_DEVICE_STATE',{'CPU_state':'NOT_OBSERVED_NO_PRECONNECT_READ'})
        return super().policy(command)

    def read(self,address,size):
        require(READS.get(address)==size,'BOOT_WATCH_READ_DENIED')
        blob=(C.c_uint8*size)();count=self.call('JLINKARM_ReadMemEx',address,size,blob,0)
        if count!=size:
            self.native_read_failed=True
            require(False,'BOOT_WATCH_NATIVE_NEGATIVE_READ' if count<0 else 'BOOT_WATCH_NATIVE_SHORT_READ')
        return bytes(blob)


def sample(link,slow=False):
    start=time.monotonic();row={k:link.u32(a) for k,a in FAST.items()}
    if slow:row.update({k:link.u32(a) for k,a in SLOW.items()})
    row.update(monotonic_start=start,monotonic_end=time.monotonic(),UTC_ms=int(time.time()*1000))
    return row


def watch(link,folder,root,stage,alias_flash,clock=time.monotonic,sleep=time.sleep):
    began=clock();deadline=min(began+(60 if stage==1 else 15),link.started+70)
    previous=None;slow_at=0;ready=False;invited_at=None;event=None;after_event=None;healthy_clock=False;cached={};lease=30
    status='MONITOR_LIMIT';rows=0;last_kind=None
    with (folder/'samples-private.jsonl').open('x',encoding='utf8') as stream:
        while clock()<deadline and rows<MAX_SAMPLES:
            if (root/'STOP').exists():status='OWNER_STOP';break
            if (root/'RESET_CANCELLED.json').exists():status='OWNER_CANCELLED_RESET';break
            if link.sdk_calls>=SDK_LIMIT-CLOSE_RESERVE:status='HOST_BUDGET_REFUSAL';break
            now=clock();slow=now>=slow_at
            s=sample(link,slow);rows+=1
            if slow:cached={k:s[k] for k in SLOW};slow_at=now+1
            observed_reset=reset_event(previous,s) if previous else None
            if s['VTOR']==0 and (previous is None or previous['VTOR']!=0 or observed_reset):
                alias=link.read(0,64);alias_flash=alias==link.expected_vectors
                s.update(alias_refreshed=True,alias_sha256=sha(alias),alias_matches_expected_Flash=alias_flash)
                g.save(folder/('alias-sample-'+str(rows)+'-private.json'),{'sha256':sha(alias),'matches_Flash':alias_flash})
            observed=dict(s,**cached);s['kind']=kind(observed,alias_flash);last_kind=s['kind'];stream.write(json.dumps(s)+'\n');stream.flush()
            intent=g.maybe(root/'RESET_INTENT.json')
            if stage==1 and ready and intent and invited_at is None:
                require(intent.get('action')=='OWNER_C_RESET_ONCE' and began<=intent['monotonic']<=now,'BOOT_WATCH_RESET_INTENT')
                invited_at=intent['monotonic']
                lease=intent.get('lease_s',30);require(lease in (15,30),'BOOT_WATCH_RESET_LEASE')
            if observed_reset and stage==1 and invited_at is not None and now-invited_at<=lease and event is None:
                event=observed_reset;after_event=now
                g.save(root/'RESET_OBSERVED.json',dict(event=event,monotonic=now,
                       owner_causation='REQUIRES_OWNER_FACT_NOT_PROVEN_BY_REGISTER_FLAGS'))
            # 人工复位边沿可能恰落在向量/计数清零期间；只读观察最多2秒，不做恢复。
            transition=(s['kind']=='UNKNOWN' and event is not None and now-after_event<=2 and
                        s['VTOR']==0 and s['DWT_PCSR']==0 and not observed.get('CFSR',0) and not observed.get('HFSR',0))
            if transition:
                with (folder/'reset-transitions-private.jsonl').open('a',encoding='utf8') as transitions:
                    g.append(transitions,'READONLY_RESET_TRANSITION',s)
                previous=s;sleep(.1);continue
            if s['kind']!='FLASH':
                status=s['kind']+'_OBSERVED'
                if s['kind']=='HALT':g.save(folder/'already-halted-core-private.json',runtime.core_if_halted(link))
                break
            require(s['flags']==0,'BOOT_WATCH_NOT_DISARMED')
            if previous and 0<((s['uptime']-previous['uptime'])&0xffffffff)<0x80000000:healthy_clock=True
            if observed_reset and (stage==2 or invited_at is None or (event is not None and now-after_event>2)):
                status='RESET_OBSERVED_OUTSIDE_OWNER_INVITATION'
                g.save(folder/'unplanned-reset-private.json',dict(event=observed_reset,monotonic=now));break
            if stage==1 and now-began>=5 and not healthy_clock:status='FLASH_CLOCK_NOT_ADVANCING';break
            if stage==1 and now-began>=5 and healthy_clock and not ready:
                if deadline-now<45:status='INSUFFICIENT_OWNER_WINDOW_BUDGET';break
                g.save(root/'RESET_READY.json',{'stage':1,'monotonic':now,'monitor_deadline':deadline,
                       'state':'HEALTHY_FLASH_ONLY_OWNER_RESET_MAX1','NOT_A_RESET_COMMAND':True});ready=True
                if getattr(link,'native_popup_allowed',False):launch_popup(root,now)
            if stage==1 and invited_at is not None and event is None and now-invited_at>lease:
                status='RESET_INVITATION_EXPIRED_NO_CONFIRMED_EVENT';break
            if stage==1 and after_event is not None and now-after_event>=15:
                status='NORMAL_FLASH_RESET_OBSERVED_MONITOR_COMPLETE';break
            previous=s;sleep(.1)
        else:
            if stage==2 and previous and healthy_clock:status='NORMAL_FLASH_REATTACH_MONITOR_COMPLETE'
    return dict(status=status,samples=rows,reset_event=event,last_kind=last_kind,app_clock_advanced=healthy_clock)


def capture(a,root,stage):
    folder=root/('attach-'+str(stage));folder.mkdir();recovery.protected(folder,False);link=None
    result={'stage':stage,'status':'STOP','close_resume':False}
    try:
        link=WatchLink(folder,root/'heartbeat-events.jsonl');link.native_popup_allowed=a.get('native_popup_allowed') is True;link.open()
        first={k:link.u32(FAST[k]) for k in ('DHCSR','VTOR','DWT_PCSR')}
        g.save(folder/'first-post-connect-state-private.json',first)
        seen=raw.identity(link);g.save(folder/'identity-private.json',seen);recovery.identity_check(seen)
        require(seen==g.load(a['identity']),'BOOT_WATCH_WRONG_C')
        vectors=link.read(0x08000000,64);options=link.read(0x1fffc000,16);alias=link.read(0,64)
        g.write_private(folder/'vectors-private.bin',vectors);g.write_private(folder/'options-private.bin',options)
        g.write_private(folder/'alias-private.bin',alias)
        require(vectors==recovery.read(Path(a['full']),False)[:64] and sha(options)==a['options_sha256'],'BOOT_WATCH_VECTORS_OR_OPTIONS_DRIFT')
        link.expected_vectors=vectors
        result.update(watch(link,folder,root,2 if a.get('observation_only') else stage,alias==vectors),first_post_connect=first,
                      full_image_read='NOT_REPEATED_ONLY64B_VECTORS_AND16B_OPTIONS',BOOT_edge='NOT_OBSERVED_NO_INSTRUMENT')
        safe_statuses=('NORMAL_FLASH_RESET_OBSERVED_MONITOR_COMPLETE','NORMAL_FLASH_REATTACH_MONITOR_COMPLETE',
                       'RESET_INVITATION_EXPIRED_NO_CONFIRMED_EVENT','MONITOR_LIMIT','HOST_BUDGET_REFUSAL',
                       'INSUFFICIENT_OWNER_WINDOW_BUDGET','OWNER_STOP','OWNER_CANCELLED_RESET')
        if result['status'] in safe_statuses and result.get('last_kind')=='FLASH' and not link.error and not link.native_read_failed:
            final=sample(link,True);g.save(folder/'before-close-private.json',final)
            if kind(final,alias==vectors)=='FLASH' and final['flags']==0 and not final['DHCSR']&raw.RESET:
                link.verified_running_flash=True;link.set_close_resume(True)
            else:result.update(status='STATE_CHANGED_BEFORE_CLOSE',last_kind=kind(final,alias==vectors))
    except Exception as error:
        result.update(g.error_record(error));text=str(error)
        if text.startswith('BOOT_WATCH_') and text.isupper() and text.replace('_','').isalnum():result['reason']=text
    finally:
        if link:
            result.update(SDK_calls=link.sdk_calls,close_resume=link.close_resume_enabled,
                          SDK_native_calls_excluding_Close=link.native_calls,native_read_failed=link.native_read_failed)
            try:link.close();result['Close_completed']=True
            except Exception as error:result.update(Close_completed=False,close_error=g.error_record(error))
        (root/'POPUP_END').touch(exist_ok=True)
        g.save(folder/'receipt-private.json',result)
    return result


def worker(a,out):
    out.mkdir();recovery.protected(out,False);(out/'heartbeat-events.jsonl').touch()
    results=[capture(a,out,1)]
    expected='NORMAL_FLASH_REATTACH_MONITOR_COMPLETE' if a.get('observation_only') else 'NORMAL_FLASH_RESET_OBSERVED_MONITOR_COMPLETE'
    if a.get('connection_slots_remaining',2)==2 and results[0]['status']==expected and results[0].get('Close_completed') and results[0].get('close_resume'):
        time.sleep(2);results.append(capture(a,out,2))
    result=dict(status='BOOT_WATCH_SAVED_NOT_ROOT_CAUSE_PASS',stages=results,
                explicit_halt_reset_go_UART_NVM_writes=0,manual_reset_is_owner_action=True,
                connections=len(results),reset_go_recovery=0,BOOT0_NRST_waveform='NOT_AVAILABLE',
                pre_connect_CPU_state='UNKNOWN',root_cause='UNRESOLVED')
    g.save(out/'receipt-private.json',result)
    return 0 if all(s.get('Close_completed') and s['status']!='STOP' for s in results) else 1


def main():
    if len(sys.argv)==3 and sys.argv[1]=='--popup':return popup(Path(sys.argv[2]))
    parser=argparse.ArgumentParser();parser.add_argument('--execute',action='store_true');parser.add_argument('--worker',action='store_true')
    parser.add_argument('--authorization',type=Path);parser.add_argument('--out',type=Path);args=parser.parse_args()
    if not args.execute and not args.worker:
        print(json.dumps(dict(enabled=False,scope=SCOPE,connections_max=2,monitor_s=60,SDK_LIMIT=SDK_LIMIT,tools_sha256=bindings())));return 0
    a=g.load(args.authorization);authorize(a,args.out)
    if args.worker:
        used=g.load(args.authorization.with_suffix('.used'))
        require(used.get('scope')==SCOPE and used.get('authorization_sha256')==sha(recovery.read(args.authorization,False)),
                'BOOT_WATCH_SUPERVISOR_TOKEN')
        return worker(a,args.out)
    return supervision.supervise(args.authorization,args.out,backend=sys.modules[__name__])


if __name__=='__main__':raise SystemExit(main())
