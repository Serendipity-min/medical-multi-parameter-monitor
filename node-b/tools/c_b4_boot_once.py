"""已知C ROM态的一次正常器件复位；只运行已完整核验的原固件，不下载、不强设入口。"""
import argparse
import ctypes as C
import json
from pathlib import Path
import subprocess
import sys
import time
import b4_recovery as pkg
import c_b4_readonly as ro
import readback_b as raw
import runtime_state_b as runtime

SCOPE='C_ONE_NORMAL_RESET_AND_CONDITIONAL_GO_ORIGINAL_ONLY_NO_DOWNLOAD'


def need(ok,reason):
    if not ok:raise ValueError(reason)


def bindings():
    return {name:raw.sha(Path(__file__).with_name(name)) for name in
            ('c_b4_boot_once.py','c_b4_readonly.py','b4_recovery.py','readback_b.py',
             'live_state_b.py','runtime_state_b.py','resp_exploratory.py')}


def site_ready(site):
    old={'JLink':'C','BOOT0_static_V':0,'BOOT0_BOOT1_jumpers':'GND',
         'ESP_isolated':True,'A_disconnected':True,'USB_UART':'COM15_RECONNECTED',
         'B_power':'J5','C_power':'USB_UART','no_source_or_wiring_change':True}
    # 本轮未重测BOOT0，不把三日前0V当今天测量；复位后仍必须真实向量匹配才Go。
    current={'JLink':'C','BOOT0_static_V':None,'BOOT_jumpers_last_report':'GND',
         'ESP_isolated':True,'speaker_isolated':True,'A_disconnected':True,
         'USB_UART':'DISCONNECTED','B_power':'OFF','C_power':'J5',
         'no_source_or_wiring_change':True}
    data_connected=dict(current,USB_UART='OWNER_CONFIRMED_DATA_PORT')
    return site in (old,current,data_connected)


def validate(a):
    need(a.get('enabled') is True and a.get('owner_approved') is True and a.get('scope')==SCOPE,
         'C_BOOT_OWNER_AUTH_REQUIRED')
    need(a.get('tools_sha256')==bindings() and a.get('DLL_sha256')==raw.DLL_SHA,'C_BOOT_TOOL_DRIFT')
    need(time.time()<a.get('expires_unix',0),'C_BOOT_AUTH_EXPIRED')
    need(site_ready(a.get('site')),'C_BOOT_SITE')


def entry_gate(state):
    # 负责人批准的是一次正常复位；原Flash或已记录ROM均可作为初态，未知映射仍拒绝。
    need(state['VTOR'] in (0x1fff0000,0x08000000),'C_BOOT_INITIAL_VECTOR_UNREVIEWED_NO_RESET')
    need(not state['DHCSR']&(raw.LOCKUP|raw.RESET) and not(state['CFSR']|state['HFSR']),
         'C_BOOT_INITIAL_FAULT_OR_NEW_RESET')


def protect_healthy_entry(link,state):
    # 先确认CPU并固定健康Flash退出策略，后面的镜像解析失败也不能重复遗留HALT。
    if state['VTOR']==0x08000000 and not state['DHCSR']&raw.HALT:
        ro.check_running(link,state);link.set_close_resume(True)


def reset_core_gate(state,core,original):
    need(state['DHCSR']&raw.HALT and not state['DHCSR']&raw.LOCKUP,'C_BOOT_RESET_NOT_HALTED')
    need(not(state['CFSR']|state['HFSR']),'C_BOOT_RESET_FAULT')
    sp=int.from_bytes(original[:4],'little');pc=int.from_bytes(original[4:8],'little')&~1
    regs=core.get('registers',{})
    # 检查硬件复位真正加载的向量，绝不靠WriteReg改PC/MSP来让判据通过。
    need(regs.get('R15',0)&~1==pc and regs.get('MSP')==sp,'C_BOOT_RESET_VECTOR_NOT_ORIGINAL_FLASH')
    need(state['VTOR'] in (0,0x08000000),'C_BOOT_RESET_VECTOR_TABLE_NOT_FLASH')


class Link(ro.CReadLink):
    def __init__(self,out):
        self.actions={};self.original_verified=False;self.go_allowed=False;super().__init__(out)
    def call(self,name,*args,timeout=5):
        need(self.sdk_calls<300,'C_BOOT_SDK_BUDGET')
        if name in ('JLINKARM_Reset','JLINKARM_Go'):
            need(self.actions.get(name,0)==0 and self.original_verified,'C_BOOT_ACTION_BUDGET_OR_IMAGE')
            if name=='JLINKARM_Go':need(self.go_allowed,'C_BOOT_GO_WITHOUT_VECTOR_PROOF')
            self.actions[name]=1;self.sdk_calls+=1
            return raw.Link.call(self,name,*args,timeout=timeout)
        if name in ('JLINKARM_GetRegisterList','JLINKARM_GetRegisterName','JLINKARM_ReadReg'):
            need(self.register_reads_allowed,'C_BOOT_CORE_REQUIRES_ALREADY_HALTED')
            self.sdk_calls+=1;return raw.Link.call(self,name,*args,timeout=timeout)
        if name=='JLINKARM_ExecCommand' and args[0]==b'SetResetType = 0':
            self.sdk_calls+=1;return raw.Link.call(self,name,*args,timeout=timeout)
        return super().call(name,*args,timeout=timeout)


def worker(args,a):
    args.out.mkdir(exist_ok=False);link=None;r={'status':'STOP','exit_code':1,'root_cause':'UNRESOLVED'}
    try:
        manifest,parts=pkg.load_package(Path(a['package']),a['manifest_sha256'],False)
        need(manifest['board_role']=='C','C_BOOT_WRONG_PACKAGE')
        reference=json.loads(parts['identity-private.json']);link=Link(args.out);link.open()
        seen=raw.identity(link);raw.check_identity(seen);need(seen==reference,'C_BOOT_WRONG_IDENTITY')
        raw.write_json(args.out/'identity-private.json',seen)
        raw.write_json(args.out/'entry-sticky-private.json',{'DHCSR':link.u32(ro.SYSTEM['DHCSR'])})
        entry=ro.snapshot(link);raw.write_json(args.out/'entry-private.json',entry)
        protect_healthy_entry(link,entry);entry_gate(entry)
        original=link.read(0x08000000,1048576);options=link.read(0x1fffc000,16)
        with (args.out/'before-full-private.bin').open('xb') as f:f.write(original)
        with (args.out/'before-options-private.bin').open('xb') as f:f.write(options)
        need(original==parts['before-full-private.bin'] and options==parts['options-private.bin'],
             'C_BOOT_ORIGINAL_OR_OPTIONS_DRIFT')
        link.original_verified=True;link.policy('SetResetType = 0')
        # 计划改变CPU状态前取消原态健康标记，复位失败不得沿用旧标记隐式续跑。
        if link.close_resume_enabled:link.set_close_resume(False)
        link.verified_running_flash=False
        need(link.call('JLINKARM_Reset')>=0,'C_BOOT_RESET_SDK_ERROR')
        # 正常复位的旧S_RESET_ST单独留存；不将该预期复位冒充第二次意外复位。
        raw.write_json(args.out/'post-reset-sticky-private.json',{'DHCSR':link.u32(ro.SYSTEM['DHCSR'])})
        state=ro.snapshot(link);raw.write_json(args.out/'post-reset-private.json',state)
        core=runtime.core_if_halted(link);raw.write_json(args.out/'post-reset-core-private.json',core)
        reset_core_gate(state,core,original)
        link.go_allowed=True;link.call('JLINKARM_Go')
        for index in range(4):
            time.sleep(.5);state=ro.snapshot(link)
            raw.write_json(args.out/f'running-{index}-private.json',state);ro.check_running(link,state)
            if not link.close_resume_enabled:link.set_close_resume(True)
        r.update(status='C_ORIGINAL_FLASH_BOOT_AFTER_ONE_NORMAL_RESET_PASS',exit_code=0,
                 original_full_sha256=pkg.digest(original),ROM_root_cause_closed=False,
                 flash_options_or_core_register_writes=0,C_candidate_installed=False)
    except BaseException as e:
        raw.write_json(args.out/'failure-private.json',{'type':type(e).__name__,'reason':str(e)})
    finally:
        if link:
            try:
                if not link.verified_running_flash and link.close_resume_enabled:link.set_close_resume(False)
            finally:link.close()
            r.update(actions=link.actions,sdk_calls=link.sdk_calls,close_resume=link.close_resume_enabled)
        raw.write_json(args.out/'receipt-private.json',r)
        for file in args.out.iterdir():
            if file.is_file():pkg.protected(file,False)
    print(json.dumps({'status':r['status'],'exit_code':r['exit_code']}));return r['exit_code']


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--authorization',type=Path)
    p.add_argument('--out',type=Path);p.add_argument('--worker',action='store_true',help=argparse.SUPPRESS)
    args=p.parse_args()
    try:
        need(args.authorization is not None and args.out is not None,'C_BOOT_AUTH_AND_OUTPUT_REQUIRED')
        a=json.loads(pkg.protected(args.authorization,False).read_text('utf-8'));validate(a)
        pkg.protected(args.out.parent,False);need(not args.out.exists(),'C_BOOT_OUTPUT_EXISTS')
        if args.worker:return worker(args,a)
        with args.authorization.with_suffix('.used').open('x') as f:f.write(SCOPE)
        with args.out.with_name(args.out.name+'-worker.log').open('xb') as log:
            child=subprocess.Popen([sys.executable,'-X','utf8',__file__,'--worker',
                  '--authorization',str(args.authorization),'--out',str(args.out)],stdout=log,stderr=subprocess.STDOUT)
            try:child.wait(timeout=90)
            except subprocess.TimeoutExpired:child.kill();child.wait(timeout=5);return 1
        return child.returncode
    except (ValueError,OSError,KeyError,TypeError):
        print(json.dumps({'status':'STOP_BEFORE_SDK','exit_code':1}));return 1


if __name__=='__main__':raise SystemExit(main())
