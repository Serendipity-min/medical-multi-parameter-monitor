"""G3设备只读工人：固定B地址和C身份检查，禁止目标状态写入。"""
import argparse
import ctypes as C
import json
from pathlib import Path
import sys
import time

import b5_g3_contract as g
import b4_runtime as b
import b5_g2_site as c
import readback_b as raw
import runtime_state_b as runtime

READS={address:{4} for address in b.ro.SYSTEM.values()}
READS.update({0xe000ed00:{4},0xe0042000:{4},0x40023c14:{4},0x1fff7a10:{12},0x1fff7a22:{2},0x1fffc000:{16}})
READS.update({address:{size} for address,size in b.RAM.items()})
READS[0x08000000]={64,39948,1048576};READS[0]={64};READS[g.SLOTS]={g.BLOCK_BYTES}
C_READS={address:{4} for address in c.ro.SYSTEM.values()}
C_READS.update({0xe000ed00:{4},0xe0042000:{4},0x40023c14:{4},0x1fff7a10:{12},0x1fff7a22:{2},
                0x1fffc000:{16},0x08000000:{64,1048576},0:{64},c.RAM:{4}})
HOST_CANCELLATIONS={'G3_STOP_REQUESTED','G3_B_STOP','G3_B_SESSION_TIMEOUT','G3_B_CALL_BUDGET'}

class BLink(b.Link):
    def __init__(self,out,root,operator_wait_extra_s=0,host_cancel_cleanup_s=0,profile=None):
        self.root=root;self.final_close_verified=False;self.active_api=None;self.native_failed=False;self.host_cancel_close=False
        self.operator_wait_extra_s=operator_wait_extra_s;self.host_cancel_cleanup_s=host_cancel_cleanup_s
        self.allowed_reads={k:set(v) for k,v in READS.items()}
        if profile:
            for address,size in profile['RAM'].values():self.allowed_reads.setdefault(address,set()).add(size)
            self.allowed_reads.setdefault(profile['slots'],set()).add(g.BLOCK_BYTES)
            self.allowed_reads.setdefault(profile['UART_ring'],set()).add(1024)
        super().__init__(out)
        c.config.NativeLink.install_log_filters(self)
    def gate(self):
        g.require(self.host_cancel_close or not (self.root/'STOP').exists(),'G3_STOP_REQUESTED')
        arm=g.maybe(self.root/'ARM_ATTEMPT.json')
        extra=getattr(self,'operator_wait_extra_s',0)
        cleanup=getattr(self,'host_cancel_cleanup_s',0) if self.host_cancel_close else 0
        deadline=(arm['monotonic']+422 if arm else self.started+g.CRITERIA['prearm_s']+extra)+cleanup
        g.require(time.monotonic()<=deadline and time.monotonic()-self.started<=565+extra+cleanup,'G3_B_SESSION_TIMEOUT')
        g.require(not self.error,'G3_B_SDK_ERROR')
    def set_close_resume(self,enabled):
        if enabled and not self.final_close_verified:return
        return super().set_close_resume(enabled)
    def call(self,name,*args,timeout=5):
        g.require(name in runtime.CALLS-{'JLINKARM_GetRegisterList','JLINKARM_GetRegisterName','JLINKARM_ReadReg'},'G3_B_API_DENIED')
        g.require(self.sdk_calls<100000,'G3_B_CALL_BUDGET')
        if name=='JLINKARM_ExecCommand':
            command=args[0].decode('ascii')
            g.require(command in runtime.COMMANDS or command=='SetRestartOnClose = 1','G3_B_COMMAND_DENIED')
            if command=='SetRestartOnClose = 1':g.require(self.verified_running_flash and self.final_close_verified,'G3_B_CLOSE_NOT_VERIFIED')
        if name=='JLINKARM_ReadMemEx':
            g.require(args[1] in getattr(self,'allowed_reads',READS).get(args[0],set()) and args[3]==0,'G3_B_READ_SCOPE')
            if args[:2] in ((0x08000000,1048576),(0x1fffc000,16)):
                counts=getattr(self,'g3_read_counts',{});key=args[:2]
                g.require(counts.get(key,0)==0,'G3_B_ONE_READ_LIMIT');counts[key]=1;self.g3_read_counts=counts
        self.sdk_calls+=1;self.gate();self.active_api=name
        deadline=time.monotonic()+timeout
        self.events.write(json.dumps({'operation':name,'active':True,'deadline_monotonic':deadline})+'\n');self.events.flush()
        try:
            value=getattr(self.dll,name)(*args)
            row={'operation':name,'monotonic_s':time.monotonic(),'native_return_int':value if isinstance(value,int) else None}
            if name=='JLINKARM_ReadMemEx':row.update(address=hex(args[0]),requested=args[1])
            self.io.write(json.dumps(row)+'\n');self.io.flush()
            self.events.write(json.dumps({'operation':name,'active':False})+'\n');self.events.flush()
            g.require(time.monotonic()<=deadline,'G3_B_NATIVE_TIMEOUT');self.gate()
            return value
        except BaseException as error:
            self.verified_running_flash=False
            if str(error) not in HOST_CANCELLATIONS:self.native_failed=True
            raise
        finally:self.active_api=None
    def read(self,address,size):
        g.require(size in getattr(self,'allowed_reads',READS).get(address,set()),'G3_B_READ_SCOPE')
        buf=(C.c_uint8*size)();n=self.call('JLINKARM_ReadMemEx',address,size,buf,0,timeout=45 if size==1048576 else 5)
        if n!=size:self.native_failed=True;self.verified_running_flash=False
        g.require(n>=0,'G3_B_NATIVE_READ_ERROR');g.require(n==size,'G3_B_POSITIVE_SHORT_READ')
        return bytes(buf)
    def prepare_host_cancel_close(self,out):
        g.require(not self.error and not self.native_failed,'G3_B_HOST_CANCEL_NATIVE_UNHEALTHY')
        # 仅主机取消时补一次原白名单CPU核验；ROM/HALT/native失败不续跑、不发Go。
        self.host_cancel_close=True
        try:
            cpu=b.ro.snapshot(self);raw.write_json(out/'host-cancel-before-close-private.json',cpu)
            b.ro.check_running(self,cpu);self.final_close_verified=True;self.set_close_resume(True)
        finally:self.host_cancel_close=False
    def close(self):
        self.active_api='JLINKARM_Close'
        try:return super().close()
        finally:self.active_api=None

class CLink(c.BridgeLink):
    def __init__(self,out,flags_address=c.RAM):
        self.flags_address=flags_address
        super().__init__(out)
    def read(self,address,size):
        if (address,size)==(self.flags_address,4):
            data=(C.c_uint8*4)()
            g.require(self.call('JLINKARM_ReadMemEx',address,size,data,0)==size,'G3_C_FLAGS_SHORT_READ')
            return bytes(data)
        return super().read(address,size)
    def call(self,name,*args,timeout=5):
        g.require(name in c.ro.CALLS,'G3_C_READONLY_API')
        if name=='JLINKARM_ReadMemEx':
            allowed={**C_READS,self.flags_address:{4}}
            g.require(args[1] in allowed.get(args[0],set()) and args[3]==0,'G3_C_READ_SCOPE')
            if args[:2] in ((0x08000000,1048576),(0x1fffc000,16)):
                counts=getattr(self,'g3_read_counts',{});key=args[:2]
                g.require(counts.get(key,0)==0,'G3_C_ONE_READ_LIMIT');counts[key]=1;self.g3_read_counts=counts
        g.require(time.monotonic()-self.started<=90,'G3_C_PREFLIGHT_TIMEOUT')
        if name=='JLINKARM_ReadMemEx' and args[:2]==(self.flags_address,4) and self.flags_address!=c.RAM:
            # 旧sector3桥的底层白名单只认旧ABI；新应用只单独放行冻结的四字节状态。
            g.require(self.sdk_calls<self.sdk_limit,'G3_C_SDK_BUDGET');self.sdk_calls+=1
            value=raw.Link.call(self,name,*args,timeout=timeout)
            self.io.write(json.dumps({'operation':name,'address':hex(args[0]),'requested':4,'native_return_int':value})+'\n');self.io.flush()
            return value
        return super().call(name,*args,timeout=timeout)


def c_preflight(a,base,bundle):
    out=base/'C-preflight';out.mkdir(exist_ok=False);g.private.protected(out,False)
    link=None;r={'status':'STOP','exit_code':1}
    try:
        flags_address=bundle.get('_C_flags_address',c.RAM)
        link=CLink(out,flags_address);link.open();ident=raw.identity(link)
        raw.write_json(out/'identity-private.json',ident)
        g.require(ident==g.load(bundle['C_identity']['path']),'G3_C_IDENTITY')
        raw.write_json(out/'entry-sticky-private.json',{'DHCSR':link.u32(c.ro.SYSTEM['DHCSR'])})
        state=c.ro.old.snapshot(link);raw.write_json(out/'entry-private.json',state);c.ro.old.check_running(link,state)
        full=link.read(0x08000000,1048576);opts=link.read(0x1fffc000,16);flags=link.read(flags_address,4)
        g.write_private(out/'full-private.bin',full);g.write_private(out/'options-private.bin',opts);g.write_private(out/'flags-private.bin',flags)
        g.require(g.sha(full)==bundle.get('_expected_C_full_sha256',g.C_FULL) and g.sha(opts)==bundle['C_options']['sha256'] and flags==bytes(4),'G3_C_FULL_OPTIONS_DISARMED')
        state=c.ro.old.snapshot(link);raw.write_json(out/'exit-private.json',state);c.ro.old.check_running(link,state)
        link.set_close_resume(True)
        r.update(status='C_CURRENT_B5_CONFIG_DISARMED_READONLY_PASS',exit_code=0,full_sha256=g.sha(full),
                 options_sha256=g.sha(opts),DISARMED_hex=flags.hex(),observed_unix=time.time())
    except BaseException as e:
        if link:link.verified_running_flash=False
        r.update(g.error_record(e))
    finally:
        if link:
            try:link.close()
            except BaseException as e:r.update(exit_code=1,close_error_type=type(e).__name__)
        g.save(out/'receipt-private.json',r)
    return r['exit_code']


def b_worker(a,root,bundle,*,start_record_name='B-worker.used'):
    g.save(root/start_record_name,{'role':'B','authorization_sha256':g.sha(json.dumps(a,sort_keys=True).encode())})
    out=root/'B';out.mkdir(exist_ok=False);g.private.protected(out,False)
    link=None;r={'status':'STOP','exit_code':1,'explicit_reset_halt_go_target_writes':0}
    try:
        profile=bundle.get('_B_profile')
        link=BLink(out,root,a.get('operator_wait_extra_s',0),a.get('host_cancel_cleanup_s',0),profile);link.open();ident=raw.identity(link);raw.write_json(out/'identity-private.json',ident)
        g.require(ident==g.load(bundle['B_identity']['path']),'G3_B_IDENTITY')
        raw.write_json(out/'entry-sticky-private.json',{'DHCSR':link.u32(b.ro.SYSTEM['DHCSR'])})
        cpu=b.ro.snapshot(link);raw.write_json(out/'entry-cpu-private.json',cpu);b.ro.check_running(link,cpu)
        full=link.read(0x08000000,1048576);options=link.read(0x1fffc000,16)
        g.write_private(out/'full-private.bin',full);g.write_private(out/'options-private.bin',options)
        size=profile['BIN_bytes'] if profile else 39948;image=profile['BIN_sha256'] if profile else g.B_IMAGE
        g.require(g.sha(full)==bundle['B_full']['sha256'] and g.sha(full[:size])==image
                  and g.sha(options)==bundle['B_options']['sha256'],'G3_B_FULL_OPTIONS')
        def snapshot(label):return b.snapshot(link,out,label,profile['RAM'] if profile else None,
            stable_temperature=bool(bundle.get('_ABC_stable_temperature_read')))
        first=snapshot('entry');time.sleep(2);last=snapshot('ready');b.assess(first,last)
        slots=profile['slots'] if profile else g.SLOTS
        anchor_block=link.read(slots,g.BLOCK_BYTES);g.write_private(out/'prearm-anchor-block-private.bin',anchor_block)
        epoch,anchor,received,valid=g.decode_block(anchor_block)[2]
        g.require(valid==0 or g.signed(last['bio']['last_sample_ms'],received)>31000,'G3_B_UNEXPECTED_FRESH_TIME_BEFORE_ARM')
        g.save(root/'B_READY.json',{'monotonic':time.monotonic(),'image_sha256':image,'samples':last['bio']['samples']})
        with (out/'blocks-private.bin').open('xb') as blocks,(out/'blocks-private.jsonl').open('x',encoding='utf8') as indices, \
             (out/'diagnostics-private.jsonl').open('x',encoding='utf8') as diagnostics, \
             (out/'UART4-ring-private.bin').open('xb') as uart, \
             (out/'UART4-ring-private.jsonl').open('x',encoding='utf8') as uart_indices:
            g.append(diagnostics,'B_DIAG',first);g.append(diagnostics,'B_DIAG',last)
            n=0;uart_n=0;next_diag=time.monotonic()
            while not (root/'END_B').exists():
                g.require(not (root/'STOP').exists(),'G3_B_STOP')
                started=time.monotonic();state=link.u32(b.ro.SYSTEM['DHCSR'])
                if state&(raw.HALT|raw.LOCKUP|raw.RESET):
                    link.verified_running_flash=False;g.save(out/'changed-state.json',{'DHCSR':state});raise ValueError('G3_B_CPU_CHANGED')
                block=link.read(slots,g.BLOCK_BYTES)
                blocks.write(block);blocks.flush();g.append(indices,'B_BLOCK',{'index':n,'offset':n*g.BLOCK_BYTES,
                    'read_start':started,'read_end':time.monotonic(),'sha256':g.sha(block)})
                n+=1
                if profile and n%3==0:
                    ub=link.read(profile['UART_ring'],1024)+link.read(*profile['RAM']['temperature'])
                    uart.write(ub);uart.flush();g.append(uart_indices,'UART4_RING',{'index':uart_n,
                        'offset':uart_n*1088,'sha256':g.sha(ub),'read_end':time.monotonic()});uart_n+=1
                if time.monotonic()>=next_diag:
                    current=snapshot('d'+str(n));g.append(diagnostics,'B_DIAG',current)
                    b.assess(last,current);last=current;next_diag+=.5
                g.require(n<=12000,'G3_B_BLOCK_BUDGET')
                time.sleep(max(0,.05-(time.monotonic()-started)))
            final=snapshot('final');b.assess(last,final);g.append(diagnostics,'B_DIAG',final)
        link.final_close_verified=True;link.set_close_resume(True)
        r.update(status='B_G3_READONLY_CAPTURED_REVIEW_PENDING',exit_code=0,blocks=n)
    except BaseException as e:
        r.update(g.error_record(e))
        if link and str(e) in HOST_CANCELLATIONS:
            try:link.prepare_host_cancel_close(out);r['host_cancel_close_running_verified']=True
            except BaseException as cleanup:r['host_cancel_close_error']=g.error_record(cleanup)
        if not (root/'B_FAULT.json').exists():g.save(root/'B_FAULT.json',{'reason':'B_READONLY_WORKER_FAILED'})
    finally:
        if link:
            try:link.close()
            except BaseException as e:r.update(exit_code=1,close_error_type=type(e).__name__)
            r.update(sdk_calls=link.sdk_calls,close_resume=link.close_resume_enabled)
        g.save(out/'receipt-private.json',r)
    return r['exit_code']


def main():
    p=argparse.ArgumentParser();p.add_argument('--authorization',type=Path);p.add_argument('--b-worker',action='store_true')
    args=p.parse_args()
    if not args.b_worker:return 0
    a=g.load(args.authorization);bundle,site=g.validate(a,g.G3);root=Path(a['output'])
    g.require(args.authorization.with_suffix('.used').exists(),'G3_PARENT_MARKER_REQUIRED')
    return b_worker(a,root,bundle)

if __name__=='__main__':raise SystemExit(main())
