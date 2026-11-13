"""G3R6批量C诊断：默认禁用；最多三连接，显式Go全批至多一次。"""
import argparse
import ctypes as C
import json
from pathlib import Path
import subprocess
import sys
import time

import b5_esp_gmr as q
import b5_g3r5_time_precheck as supervision
from b5_esp_budget import HostBudgetExhausted
g=q.g
SCOPE='B5_G3R6_C_DIAGNOSTIC_BATCH_NO_UART_NO_NVM'
REGS={'DHCSR':0xe000edf0,'VTOR':0xe000ed08,'CFSR':0xe000ed28,'HFSR':0xe000ed2c,
    'DFSR':0xe000ed30,'DEMCR':0xe000edfc,'DWT_PCSR':0xe000101c,'DWT_CTRL':0xe0001000,
    'RCC_CSR':0x40023874,'MEMRMP':0x40013800,'FP_CTRL':0xe0002000,
    'FLASH_CR':q.CR,'FLASH_SR':q.SR,'uptime':q.UPTIME}
READS={a:{4} for a in (*REGS.values(),q.site.RAM,0xe000ed00,0xe0042000,0x40023c14)}
READS.update({0x1fff7a10:{12},0x1fff7a22:{2},0x1fffc000:{16},0x08000000:{64,42552},0x0800c000:{336,16384}})
READS.update({0xe0002008+4*i:{4} for i in range(8)})
CORE_CALLS={'JLINKARM_GetRegisterList','JLINKARM_GetRegisterName','JLINKARM_ReadReg'}


def bindings():
    return {**q.bindings(),'b5_g3r5_time_precheck.py':g.sha(Path(supervision.__file__).read_bytes()),
        'b5_g3r6_batch_diag.py':g.sha(Path(__file__).read_bytes())}


def claim(path,data):
    with Path(path).open('x',encoding='utf8') as f:json.dump(data,f,indent=2)


class DiagnosticLink(q.QueryLink):
    READ_SCOPE=READS
    NATIVE_SCOPE=q.site.ro.CALLS|CORE_CALLS|{'JLINKARM_Go'}
    def __init__(self,out,batch):
        super().__init__(out);self.sdk_limit=1400;self.batch=batch
        self.register_reads_allowed=False;self.resume_eligible=False
        self.dll.JLINKARM_GetRegisterList.argtypes=[C.POINTER(C.c_uint32),C.c_uint32]
        self.dll.JLINKARM_GetRegisterList.restype=C.c_int
        self.dll.JLINKARM_GetRegisterName.argtypes=[C.c_uint32];self.dll.JLINKARM_GetRegisterName.restype=C.c_char_p
        self.dll.JLINKARM_ReadReg.argtypes=[C.c_int];self.dll.JLINKARM_ReadReg.restype=C.c_uint32
    def gate(self):
        g.require(not (self.out/'STOP').exists(),'DIAG_OWNER_STOP')
        g.require(time.monotonic()-self.started<120,'DIAG_SESSION_TIMEOUT')
        g.require(not self.error,'DIAG_SDK_CALLBACK')
    def _call_native(self,name,*args,timeout=5):
        if name in CORE_CALLS:g.require(self.register_reads_allowed,'DIAG_RUNNING_CORE_READ_DENIED')
        if name=='JLINKARM_Go':
            g.require(self.resume_eligible and self.batch['Go_max']==1,'DIAG_GO_PREREQUISITES')
            claim(Path(self.batch['root'])/'Go.used',{'scope':SCOPE,'attempted_before_native':True})
            self.resume_eligible=False
        return super()._call_native(name,*args,timeout=timeout)


def snapshot(link,out,label):
    state={k:link.u32(address) for k,address in REGS.items()}
    state['DISARMED']=link.read(q.site.RAM,4)==bytes(4)
    state['pc_samples']=[state['DWT_PCSR'],link.u32(REGS['DWT_PCSR']),link.u32(REGS['DWT_PCSR'])]
    count=(state['FP_CTRL']>>4)&15|((state['FP_CTRL']>>12)&7)<<4
    state['FP_code_comparators']=count
    g.require(count<=8,'DIAG_FPB_GEOMETRY')
    state['FP_COMP']=[link.u32(0xe0002008+4*i) for i in range(count)]
    state['DHCSR_after']=link.u32(REGS['DHCSR'])
    g.save(out/(label+'-private.json'),state)
    return state


def classify(s):
    if s['VTOR']==0x1fff0000 or any(0x1fff0000<=p<0x1fff7800 for p in s['pc_samples']):return 'ROM'
    if (s['DHCSR']|s['DHCSR_after'])&((1<<19)|(1<<25)) or s['CFSR']|s['HFSR']:return 'FAULT_RESET_OR_LOCKUP'
    if not s['DISARMED'] or s['VTOR']!=0x08000000:return 'UNKNOWN'
    if (s['DHCSR']^s['DHCSR_after'])&(1<<17):return 'UNKNOWN'
    if s['DHCSR']&(1<<17):return 'HALT'
    if not any(0x08000000<=p<0x0800a638 for p in s['pc_samples']):return 'UNKNOWN'
    if not s['FLASH_CR']&0x80000000 or s['FLASH_CR']&0x10007 or s['FLASH_SR']&0x100f2:return 'UNKNOWN'
    return 'RUNNING_FLASH'


def identity(link,reference,out):
    seen=q.site.ro.raw.identity(link)
    g.save(out/'identity-private.json',seen)
    g.require(seen==reference,'DIAG_IDENTITY_OR_PROTECTION_DRIFT')


def resume_check(s,core,image_matches):
    regs=core.get('registers',{});pc=regs.get('R15',0)&~1;msp=regs.get('MSP',0);xpsr=regs.get('XPSR',0)
    return bool(classify(s)=='HALT' and image_matches and 0x08000000<=pc<0x0800a638
        and 0x20000000<msp<=0x20020000 and msp%4==0 and xpsr&(1<<24) and not xpsr&0x1ff
        and not s['DFSR']&0x1e and not s['DEMCR']&0x7f1 and not any(v&1 for v in s['FP_COMP'])
        and s['FLASH_CR']&0x80000000 and not s['FLASH_CR']&0x10007 and not s['FLASH_SR']&0x100f2)


def run_session(a,index,out):
    out.mkdir();g.private.protected(out,False);link=None
    r={'status':'STOP_TARGET','exit_code':1,'session':index,'explicit_Go_attempts':0,'UART_bytes':0,
        'Flash_sector3_options_writes':0,'reset_halt':0,'B5START':0}
    try:
        link=DiagnosticLink(out,a);link.open()
        g.save(out/'sticky-private.json',{'DHCSR':link.u32(REGS['DHCSR'])})
        state=snapshot(link,out,'entry');entry_state=state;kind=classify(state);r['entry_state']=kind
        r['entry_PC_evidence']='DWT_SAMPLING_ONLY_NOT_REAL_PC'
        if kind not in ('RUNNING_FLASH','HALT'):raise ValueError('DIAG_'+kind+'_STOP')
        reference=g.load(a['identity_reference']);identity(link,reference,out)
        expected=g.private.read(Path(a['image_reference']),False);options=g.private.read(Path(a['options_reference']),False)
        g.require(link.read(0x08000000,64)==expected[:64] and link.read(0x0800c000,336)==expected[49152:49488]
            and link.read(0x1fffc000,16)==options,'DIAG_IMAGE_CONFIG_OR_OPTIONS_DRIFT')
        if kind=='HALT':
            core=q.runtime.core_if_halted(link);g.save(out/'halt-core-private.json',core)
            image=link.read(0x08000000,42552);sector=link.read(0x0800c000,16384)
            g.write_private(out/'halt-application-private.bin',image);g.write_private(out/'halt-sector3-private.bin',sector)
            state=snapshot(link,out,'pre-go')
            eligible=resume_check(state,core,image==expected[:42552] and sector==expected[49152:65536])
            r['Go_prerequisites_pass']=eligible
            g.require(eligible and not (Path(a['root'])/'Go.used').exists(),'DIAG_HALT_NO_ELIGIBLE_RESUME')
            # 再确认HALT和复位/捕获线索没有在取证过程中变化，才消费唯一Go。
            g.require(all(state[k]==entry_state[k] for k in ('RCC_CSR','DFSR','DEMCR','FP_COMP')),'DIAG_DEBUG_OR_RESET_CHANGED')
            link.resume_eligible=True;r['explicit_Go_attempts']=1;link.call('JLINKARM_Go')
            time.sleep(.1);after=snapshot(link,out,'after-go')
            g.require(classify(after)=='RUNNING_FLASH','DIAG_GO_NOT_RUNNING')
            state=after
        else:
            # 仅主机合成配额拒绝；不改真实配额，不发送UART/目标RAM字节。
            from b5_esp_budget import CommandBudget
            import types
            probe=types.SimpleNamespace(sdk_calls=5999,sdk_limit=6000)
            try:CommandBudget(probe,(b'AT+CIPSNTPCFG=0\r\n',b'AT+CIPSNTPCFG?\r\n')).admit(b'AT\r\n',3)
            except HostBudgetExhausted:r['host_budget_rejection_verified']=True
            g.require(r.get('host_budget_rejection_verified'),'DIAG_HOST_REJECTION_TEST')
        start=state['uptime'];time.sleep(.1);end=snapshot(link,out,'exit')
        g.require(classify(end)=='RUNNING_FLASH' and g.signed(end['uptime'],start)>0
            and end['RCC_CSR']==state['RCC_CSR'],'DIAG_NO_PROGRESS_OR_RESET')
        link.verified_running_flash=True;link.set_close_resume(True)
        r.update(status='RUNNING_AND_EXIT_VERIFIED',exit_code=0,entry_uptime=state['uptime'],exit_uptime=end['uptime'])
    except Exception as error:
        r.update(g.error_record(error))
        if str(error).startswith(('DIAG_','ESP_')) and str(error).replace('_','').isalnum():r['reason']=str(error)
    finally:
        if link:
            supervision.close_receipt(link,r)
            r['UART_bytes']=link.native_UART_writes
            if r['exit_code']:r['status']='STOP_TARGET'
        g.save(out/'receipt-private.json',r)
    print(json.dumps({k:r[k] for k in ('status','exit_code','entry_state','reason','explicit_Go_attempts','SDK_calls') if k in r}),flush=True)
    return r['exit_code']


def validate(a):
    g.require(a.get('enabled') is True and a.get('owner_approved') is True and a.get('scope')==SCOPE,'DIAG_NOT_AUTHORIZED')
    g.require(a['tools_sha256']==bindings() and time.time()<a['expires_unix'],'DIAG_BINDING_OR_EXPIRY')
    g.require(a['sessions_max']==3 and a['session_timeout_s']==120 and a['Go_max']==1
        and a['exit_resume_policy_max']==3,'DIAG_LIMITS')
    g.private.protected(Path(a['root']),False)
    for key in ('identity_reference','image_reference','options_reference'):
        g.require(g.sha(g.private.read(Path(a[key]),False))==a['reference_sha256'][key],'DIAG_PRIVATE_REFERENCE_DRIFT')


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--authorization',type=Path);parser.add_argument('--execute',action='store_true')
    parser.add_argument('--worker',type=int);args=parser.parse_args()
    if not args.execute and args.worker is None:print(json.dumps({'enabled':False,'scope':SCOPE,'sessions_max':3,'Go_max':1,'UART':0}));return 0
    a=g.load(args.authorization);validate(a);root=Path(a['root'])
    if args.worker is not None:
        g.require(1<=args.worker<=3,'DIAG_SESSION_INDEX')
        marker=g.load(root/f'session-{args.worker}.used');g.require(marker['authorization_sha256']==g.sha(args.authorization.read_bytes()),'DIAG_WORKER_BINDING')
        claim(root/f'session-{args.worker}.connection-used',{'worker_started':True})
        return run_session(a,args.worker,root/f'session-{args.worker}')
    results=[];resumed=False
    for index in range(1,4):
        if index==3 and not resumed:break
        claim(root/f'session-{index}.used',{'authorization_sha256':g.sha(args.authorization.read_bytes())})
        out=root/f'session-{index}';start=time.monotonic()
        with (root/f'worker-{index}-private.log').open('xb') as stream:
            child=subprocess.Popen([sys.executable,'-X','utf8',__file__,'--worker',str(index),'--authorization',str(args.authorization)],stdout=stream,stderr=subprocess.STDOUT)
            reason=supervision.supervise(child,out,120,start)
        receipt=g.maybe(out/'receipt-private.json') or {}
        results.append({'session':index,'worker_exit_code':child.returncode,'supervisor_reason':reason,'receipt':receipt})
        g.save(root/f'supervisor-{index}-private.json',results[-1])
        if reason or child.returncode!=0:break
        if len(results)>1:
            previous=results[-2]['receipt']
            if g.signed(receipt['entry_uptime'],previous['exit_uptime'])<=0:break
            if resumed:break
        resumed=bool(receipt['explicit_Go_attempts'])
    ok=len(results)>=2 and all(not r['supervisor_reason'] and r['worker_exit_code']==0 for r in results)
    if ok:ok=g.signed(results[-1]['receipt']['entry_uptime'],results[-2]['receipt']['exit_uptime'])>0
    summary={'status':'BATCH_DIAGNOSTIC_PASS' if ok else 'STOP_TARGET','exit_code':0 if ok else 1,
        'sessions_consumed':len(results),'Go_consumed':int((root/'Go.used').exists()),'UART_bytes':0,
        'HALT_unique_root_cause':'UNRESOLVED','new_Flash_sector3_reset_B5START':0}
    g.save(root/'batch-receipt-private.json',summary);print(json.dumps(summary));return summary['exit_code']


if __name__=='__main__':raise SystemExit(main())
