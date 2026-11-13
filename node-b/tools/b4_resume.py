"""只从已核验B4 Flash暂停态恢复一次Go；不提供reset/halt/download接口。"""
import argparse
import ctypes as C
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time
import b4_recovery as pkg
import b4_runtime as b
import c_b4_readonly as ro
import readback_b as raw
import runtime_state_b as runtime
from live_state_b import LiveLink

SCOPE='B4_B_ONE_GO_FROM_VERIFIED_FLASH_HALT_ONLY_NO_RESET_OR_DOWNLOAD'
READS={a:set(n) for a,n in ro.READS.items()};READS[0x20001d14]={120}
def need(ok,reason):
    if not ok:raise ValueError(reason)

def gate_core(s,core):
    need(s['DHCSR'] & raw.HALT and not s['DHCSR'] & (raw.LOCKUP|raw.RESET),'RESUME_NOT_STABLE_HALT')
    need(s['VTOR']==0x08000000 and not(s['CFSR']|s['HFSR']),'RESUME_NOT_HEALTHY_FLASH')
    regs=core.get('registers',{});pc=regs.get('R15',0)&~1;sp=regs.get('MSP',0)
    need(0x08000000<=pc<0x08000000+39948,'RESUME_CORE_PC_NOT_CANDIDATE_FLASH')
    need(0x20000000<sp<=0x20020000 or 0x10000000<sp<=0x10010000,'RESUME_CORE_STACK')

class Link(LiveLink):
    def __init__(self,out):
        self.go_count=0;self.resume_allowed=False;super().__init__(ro.DLL,out)
    def call(self,name,*args,timeout=5):
        need(name in runtime.CALLS|{'JLINKARM_Go'},'RESUME_FUNCTION_DENIED')
        need(self.sdk_calls<800,'RESUME_SDK_BUDGET')
        if name=='JLINKARM_ExecCommand':
            cmd=args[0].decode('ascii');need(cmd in runtime.COMMANDS or cmd=='SetRestartOnClose = 1','RESUME_POLICY')
            if cmd=='SetRestartOnClose = 1':need(self.verified_running_flash,'RESUME_CLOSE_UNVERIFIED')
        if name=='JLINKARM_ReadMemEx':need(args[1] in READS.get(args[0],set()) and args[3]==0,'RESUME_READ_SCOPE')
        if name in ('JLINKARM_GetRegisterList','JLINKARM_GetRegisterName','JLINKARM_ReadReg'):
            need(self.register_reads_allowed,'RESUME_REG_NOT_HALTED')
        if name=='JLINKARM_Go':
            need(self.resume_allowed and self.go_count==0,'RESUME_GO_GATE_OR_BUDGET');self.go_count+=1
        self.sdk_calls+=1;return raw.Link.call(self,name,*args,timeout=timeout)
    def read(self,a,n):
        need(n in READS.get(a,set()),'RESUME_READ_SCOPE');buf=(C.c_uint8*n)()
        got=self.call('JLINKARM_ReadMemEx',a,n,buf,0,timeout=45 if n==1048576 else 5)
        need(got==n,'RESUME_PARTIAL_READ');return bytes(buf)

def worker(args,a):
    args.out.mkdir(exist_ok=False);link=None;r={'status':'STOP','exit_code':1}
    try:
        m,payload=pkg.load_package(Path(a['package']),a['manifest_sha256'],False)
        need(m['board_role']=='B' and m['candidate_sha256']==b.IMAGE_SHA,'RESUME_B_PACKAGE')
        ref=json.loads(payload['identity-private.json']);link=Link(args.out);link.open()
        seen=raw.identity(link);raw.check_identity(seen);need(seen==ref,'RESUME_IDENTITY')
        raw.write_json(args.out/'identity-private.json',seen)
        blob=link.read(0x08000000,1048576)
        with (args.out/'actual-full-private.bin').open('xb') as f:f.write(blob)
        need(blob==payload['expected-full-private.bin'],'RESUME_FIRMWARE_DRIFT')
        need(link.read(0x1fffc000,16)==payload['options-private.bin'],'RESUME_OPTIONS')
        raw.write_json(args.out/'entry-sticky-private.json',{'DHCSR':link.u32(ro.SYSTEM['DHCSR'])})
        state=ro.snapshot(link);core=runtime.core_if_halted(link)
        raw.write_json(args.out/'halt-state-private.json',state);raw.write_json(args.out/'halt-core-private.json',core)
        gate_core(state,core)
        before=link.read(0x20001d14,120)
        with (args.out/'bio-before-private.bin').open('xb') as f:f.write(before)
        # 只释放当前已证实的Flash指令；绝不改PC/MSP/VTOR或通过复位代替Go。
        link.resume_allowed=True;link.call('JLINKARM_Go');time.sleep(1)
        end=ro.snapshot(link);raw.write_json(args.out/'running-state-private.json',end);ro.check_running(link,end)
        # CPU健康即保持续跑；后续ADC判据即使失败也不能再由Close遗留暂停。
        link.set_close_resume(True)
        after=link.read(0x20001d14,120)
        with (args.out/'bio-after-private.bin').open('xb') as f:f.write(after)
        need(int.from_bytes(after[8:12],'little')>int.from_bytes(before[8:12],'little'),'RESUME_ADC_NOT_ADVANCING')
        r={'status':'B4_B_ONE_GO_FLASH_AND_ADC_ADVANCE_PASS','exit_code':0,'explicit_go':1,
           'reset_halt_download_writes':0,'historical_ROM_root_cause':'UNRESOLVED'}
    except BaseException as e:raw.write_json(args.out/'failure-private.json',{'type':type(e).__name__,'reason':str(e)})
    finally:
        if link:
            try:
                if not link.verified_running_flash and link.close_resume_enabled:link.set_close_resume(False)
            except BaseException as e:r.update(exit_code=1,close_policy_error=type(e).__name__)
            finally:
                try:link.close()
                except BaseException as e:r.update(exit_code=1,close_error=type(e).__name__)
            r.update(go_attempts=link.go_count,close_resume=link.close_resume_enabled,sdk_calls=link.sdk_calls)
        raw.write_json(args.out/'receipt-private.json',r)
        for p in args.out.iterdir():
            if p.is_file():pkg.protected(p,False)
    return r['exit_code']

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--authorization',type=Path);p.add_argument('--out',type=Path)
    p.add_argument('--worker',action='store_true',help=argparse.SUPPRESS);args=p.parse_args()
    try:
        need(args.authorization is not None and args.out is not None,'RESUME_EXPLICIT_AUTH_REQUIRED')
        a=json.loads(pkg.protected(args.authorization,False).read_text('utf-8'))
        need(a.get('enabled') is True and a.get('owner_approved') is True and a.get('scope')==SCOPE,
             'RESUME_EXPLICIT_AUTH_REQUIRED')
        need(a.get('tool_sha256')==raw.sha(__file__) and a.get('expires_unix',0)>time.time(),'RESUME_TOOL_OR_EXPIRY')
        pkg.protected(args.out.parent,False);need(not args.out.exists(),'RESUME_OUTPUT_EXISTS')
        if args.worker:return worker(args,a)
        with args.authorization.with_suffix('.used').open('x',encoding='utf-8') as f:json.dump({'scope':SCOPE},f)
        cmd=[sys.executable,'-X','utf8',str(Path(__file__)),'--worker','--authorization',str(args.authorization),'--out',str(args.out)]
        reason=None;start=time.monotonic()
        with args.out.with_name(args.out.name+'-worker.log').open('xb') as log:
            child=subprocess.Popen(cmd,stdout=log,stderr=subprocess.STDOUT)
            try:
                while child.poll() is None:
                    if time.monotonic()-start>90:reason='SESSION_TIMEOUT'
                    if (args.out/'STOP').exists():reason='OWNER_STOP'
                    try:
                        lines=(args.out/'heartbeat-events.jsonl').read_text('utf-8').splitlines();e=json.loads(lines[-1]) if lines else {}
                        if e.get('active') and time.monotonic()>e['deadline_monotonic']:reason='SDK_TIMEOUT'
                    except (OSError,ValueError):pass
                    if reason:child.kill();break
                    time.sleep(.05)
            finally:
                if child.poll() is None:child.kill()
                child.wait(timeout=5)
        args.out.mkdir(exist_ok=True);raw.write_json(args.out/'supervisor-private.json',{'reason':reason,'worker_exit_code':child.returncode})
        return 1 if reason else child.returncode
    except (ValueError,RuntimeError,OSError,KeyError,TypeError):return 1
if __name__=='__main__':sys.exit(main())
