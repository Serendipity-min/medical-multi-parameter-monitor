"""C当前ROM现场一次只读取证；不暂停、复位、续跑、读UART_DR或写目标。"""
import argparse
import ctypes as C
import json
from pathlib import Path
import sys
import time

import b5_g3_contract as g
import b5_g2ro as ro
import b5_sector3_write_supervisor as supervisor
import b4_recovery as recovery
import readback_b as raw
import runtime_state_b as runtime
from live_state_b import LiveLink

SCOPE='B5_C_ROM_READONLY_CURRENT_SCENE_120S'
sha=g.sha
require=recovery.require
REGS=dict(runtime.SYSTEM)
REGS.update(RCC_CR=0x40023800,RCC_CFGR=0x40023808,RCC_AHB1ENR=0x40023830,
            RCC_APB1ENR=0x40023840,GPIOB_MODER=0x40020400,GPIOB_PUPDR=0x4002040c,
            GPIOB_ODR=0x40020414,FLASH_CR=0x40023c10,SCB_AIRCR=0xe000ed0c)
for channel,base in ((1,0x40011000),(2,0x40004400),(3,0x40004800)):
    for name,offset in (('SR',0),('BRR',8),('CR1',12),('CR2',16),('CR3',20)):
        REGS[f'USART{channel}_{name}']=base+offset
READS={**raw.REGIONS,**{a:4 for a in REGS.values()},0:64,0x1fff0000:30720,0x20000000:131072}
CORE_READS={'JLINKARM_GetRegisterList','JLINKARM_GetRegisterName','JLINKARM_ReadReg'}
CALLS=runtime.CALLS


def bindings():
    return {n:sha((g.ROOT/'node-b/tools'/n).read_bytes()) for n in
        ('b5_c_rom_readonly.py','readback_b.py','runtime_state_b.py','live_state_b.py',
         'b5_g2ro.py','b4_recovery.py','b5_sector3_write_supervisor.py')}


def authorize(a,out):
    require(a.get('enabled') is True and a.get('owner_approved') is True and a.get('scope')==SCOPE,'ROM_OWNER')
    require(a.get('tools_sha256')==bindings() and a.get('DLL_sha256')==raw.DLL_SHA,'ROM_TOOL_DRIFT')
    require(a.get('probe_sessions')==1 and a.get('session_timeout_s')==120 and a.get('retries')==0 and
            a.get('reset_halt_go_target_writes')==0 and a.get('expires_unix',0)>time.time(),'ROM_SCOPE')
    require(str(out)==a.get('output'),'ROM_OUTPUT')
    for name in ('identity','full','options'):
        require(sha(recovery.read(Path(a[name]),False))==a[name+'_sha256'],'ROM_REFERENCE')
    recovery.protected(out.parent,False)


class RomLink(LiveLink):
    def __init__(self,out):
        self.counts={}
        super().__init__(ro.DLL,out)
        ro.ReadLink.install_log_filters(self)

    def call(self,name,*args,timeout=5):
        require(name in CALLS and self.sdk_calls<300,'ROM_SDK_DENIED_OR_BUDGET')
        if name in CORE_READS:require(self.register_reads_allowed,'ROM_CORE_READ_DENIED_RUNNING')
        if name=='JLINKARM_ExecCommand':
            command=args[0].decode('ascii')
            require(command in runtime.COMMANDS or
                    (command=='SetRestartOnClose = 1' and self.verified_running_flash),'ROM_POLICY')
        if name=='JLINKARM_ReadMemEx':
            address,size=args[:2]
            require(READS.get(address)==size and args[3]==0,'ROM_READ_RANGE')
            maximum=12 if address==runtime.SYSTEM['DWT_PCSR'] else 6 if address==runtime.SYSTEM['DHCSR'] else 3 if size==4 else 1
            require(self.counts.get(address,0)<maximum,'ROM_READ_COUNT')
            self.counts[address]=self.counts.get(address,0)+1
        event={'operation':name,'monotonic':time.monotonic(),'stage':'before_native'}
        if name=='JLINKARM_ReadMemEx':event.update(address=hex(args[0]),bytes=args[1])
        if name=='JLINKARM_ExecCommand':event['policy']=args[0].decode('ascii')
        self.io.write(json.dumps(event)+'\n');self.io.flush()
        self.sdk_calls+=1
        result=raw.Link.call(self,name,*args,timeout=timeout)
        self.io.write(json.dumps({'operation':name,'native_return':result if isinstance(result,int) else None})+'\n');self.io.flush()
        return result

    def read(self,address,size):
        require(READS.get(address)==size,'ROM_READ_RANGE')
        buffer=(C.c_uint8*size)()
        count=self.call('JLINKARM_ReadMemEx',address,size,buffer,0,timeout=40 if size==1048576 else 10)
        require(count==size,'ROM_NATIVE_SHORT_READ')
        return bytes(buffer)


def snapshot(link):
    result={k:link.u32(a) for k,a in REGS.items()}
    result['pc_samples']=[link.u32(runtime.SYSTEM['DWT_PCSR']) for _ in range(3)]
    result['host_monotonic']=time.monotonic()
    return result


def worker(a,out):
    out.mkdir();recovery.protected(out,False);link=None
    result=dict(status='STOP',exit_code=1,reset_halt_go_target_writes=0,root_cause='UNRESOLVED')
    try:
        link=RomLink(out);link.open()
        seen=raw.identity(link);g.save(out/'identity-private.json',seen);recovery.identity_check(seen)
        require(seen==g.load(a['identity']),'ROM_WRONG_IDENTITY')
        first=snapshot(link);g.save(out/'entry-private.json',first)
        if a.get('read_already_halted_core_only'):
            require(first['DHCSR']&raw.HALT,'ROM_CORE_ONLY_REQUIRES_ALREADY_HALTED')
            g.save(out/'halted-core-private.json',runtime.core_if_halted(link))
        else:
            for label,address,size in (('full',0x08000000,1048576),('options',0x1fffc000,16),
                                       ('rom',0x1fff0000,30720),('alias',0,64),('ram',0x20000000,131072)):
                blob=link.read(address,size);g.write_private(out/(label+'-private.bin'),blob)
                result[label+'_sha256']=sha(blob)
                if label in ('full','options'):require(sha(blob)==a[label+'_sha256'],'ROM_IMAGE_DRIFT')
        time.sleep(1)
        last=snapshot(link);g.save(out/'last-private.json',last)
        normal=lambda x:x['VTOR']==0x08000000 and not(x['CFSR']|x['HFSR']| (x['DHCSR']&(raw.HALT|raw.LOCKUP))) and all(0x08000000<=v<0x08100000 for v in x['pc_samples'])
        if normal(first) and normal(last):link.verified_running_flash=True;link.set_close_resume(True)
        result.update(status='ROM_READONLY_SCENE_SAVED_NOT_ROOT_CAUSE_PASS',exit_code=0)
    except Exception as error:
        result.update(g.error_record(error))
    finally:
        if link:
            result.update(SDK_calls=link.sdk_calls,close_resume=link.close_resume_enabled)
            try:link.close();result['Close_completed']=True
            except Exception as error:result.update(Close_completed=False,close_error=g.error_record(error))
        g.save(out/'receipt-private.json',result)
    return result['exit_code']


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--authorization',type=Path);parser.add_argument('--out',type=Path)
    parser.add_argument('--execute',action='store_true');parser.add_argument('--worker',action='store_true');args=parser.parse_args()
    if not args.execute and not args.worker:print(json.dumps(dict(enabled=False,scope=SCOPE,tools_sha256=bindings())));return 0
    a=g.load(args.authorization);authorize(a,args.out)
    if args.worker:return worker(a,args.out)
    return supervisor.supervise(args.authorization,args.out,backend=sys.modules[__name__])


if __name__=='__main__':raise SystemExit(main())
