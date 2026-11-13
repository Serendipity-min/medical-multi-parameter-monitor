"""PHY01 的 D 首写入口：仅 sector0/1，旧应用不另行备份；默认不执行。"""
import argparse
import ctypes as C
import json
from pathlib import Path
import sys
import time

import abc_board_backup as supervisor
import b4_swd_install as engine

ROOT=Path(__file__).resolve().parents[2]
need=engine.require


def plan(before,options,identity,candidate,expected_sha):
    need(len(before)==1048576 and len(options)==16,'D_FULL_FLASH_OR_OPTIONS_LENGTH')
    engine.package.identity_check(identity)
    need(16384<len(candidate)<=32768 and engine.package.digest(candidate)==expected_sha,'D_IMAGE_SIZE_OR_SHA')
    engine.package.vector_check(candidate)
    need(all(identity['optcr']&(1<<(16+i)) for i in (0,1)),'D_WRITE_PROTECTED_NO_UNLOCK')
    return candidate+before[len(candidate):]


def worker(out,image,sha,excluded,reference=None):
    out.mkdir();probe=out/'probe';probe.mkdir();link=None
    result={'board':'D','exit_code':1,'status':'STOP','sectors':[0,1],
            'original_application_backup_required':False,'automatic_retry_or_restore':False}
    try:
        candidate=image.read_bytes();need(engine.package.digest(candidate)==sha,'D_CANDIDATE_DRIFT')
        link=engine.InstallLink(probe,32768);link.open();seen=engine.raw.identity(link)
        engine.raw.check_identity(seen)
        need(seen['uid_hex'] not in excluded,'D_ROUTE_IS_KNOWN_C_OR_B')
        if reference is not None:need(seen==reference,'D_CURRENT_IDENTITY_MISMATCH')
        engine.raw.write_json(probe/'identity-before-private.json',seen)
        engine.raw.write_json(probe/'entry-sticky-private.json',{'DHCSR':link.u32(engine.readonly.SYSTEM['DHCSR'])})
        state=engine.readonly.snapshot(link);engine.raw.write_json(probe/'entry-state-private.json',state)
        engine.readonly.check_running(link,state);link.set_close_resume(True)
        before=link.read(0x08000000,1048576);options=link.read(0x1fffc000,16)
        expected=plan(before,options,seen,candidate,sha)
        engine.raw.write_json(probe/'before-fingerprints-private.json',{'full_SHA256':engine.package.digest(before),
            'outside_sectors_SHA256':engine.package.digest(before[32768:]),'original_application_not_saved':True})
        engine.readonly.check_running(link,engine.readonly.snapshot(link));link.set_close_resume(False)
        need(link.call('JLINKARM_Halt',timeout=3)==0,'D_HALT_FAILED')
        need(link.u32(engine.readonly.SYSTEM['DHCSR'])&engine.raw.HALT,'D_HALT_NOT_CONFIRMED')
        link.u32(engine.readonly.SYSTEM['DHCSR']);link.stable_halt();link.verified_running_flash=False
        data=expected[:32768];link.program_sha=engine.package.digest(data)
        engine.raw.write_json(probe/'program-intent-private.json',{'sectors':[0,1],'address':0x08000000,
            'bytes':32768,'candidate_bytes':len(candidate),'candidate_SHA256':sha,'payload_SHA256':link.program_sha})
        link.call('JLINKARM_BeginDownload',0);buf=(C.c_uint8*len(data)).from_buffer_copy(data)
        need(link.call('JLINKARM_WriteMem',0x08000000,len(data),buf)==len(data),'D_SHORT_WRITE')
        need(link.call('JLINKARM_EndDownload',timeout=45)>=0,'D_LOADER_FAILED')
        need(link.u32(engine.readonly.SYSTEM['DHCSR'])&engine.raw.HALT,'D_LOADER_NOT_HALTED')
        actual=link.read(0x08000000,1048576);engine.save(probe,'after-full-private.bin',actual)
        need(actual==expected and actual[32768:]==before[32768:],'D_FULL_VERIFY_FAILED')
        after_options=link.read(0x1fffc000,16);engine.save(probe,'after-options-private.bin',after_options)
        need(after_options==options,'D_OPTIONS_CHANGED')
        after_identity=engine.raw.identity(link);engine.raw.write_json(probe/'identity-after-private.json',after_identity)
        need(after_identity==seen,'D_IDENTITY_CHANGED');link.fully_verified=True
        link.policy('SetResetType = 0');need(link.call('JLINKARM_Reset')==0,'D_RESET_FAILED')
        core=engine.runtime.core_if_halted(link);engine.raw.write_json(probe/'reset-core-private.json',core)
        regs=core.get('registers',{})
        need((regs.get('R15',0)&~1)==(int.from_bytes(actual[4:8],'little')&~1)
             and regs.get('MSP')==int.from_bytes(actual[:4],'little'),'D_RESET_VECTOR')
        link.call('JLINKARM_Go');time.sleep(1);link.u32(engine.readonly.SYSTEM['DHCSR'])
        state=engine.readonly.snapshot(link);engine.raw.write_json(probe/'running-after-private.json',state)
        engine.readonly.check_running(link,state);link.set_close_resume(True)
        result.update(status='D_M1_SECTOR01_FULL_VERIFY_BOOT_PASS',exit_code=0,
            full_flash_sha256=engine.package.digest(actual),candidate_sha256=sha,candidate_bytes=len(candidate),
            options_unchanged=True,outside_affected_sectors_unchanged=True)
    except (Exception,KeyboardInterrupt) as error:
        if link:link.verified_running_flash=False
        engine.raw.write_json(out/'failure-private.json',{'type':type(error).__name__,'reason':str(error)})
        result.update(error_type=type(error).__name__,error_SHA256=engine.package.digest(str(error).encode()))
    finally:
        if link:
            try:
                if not link.verified_running_flash and link.close_resume_enabled:link.set_close_resume(False)
                link.close();result['Close_completed']=True
            except Exception as error:result.update(exit_code=1,Close_completed=False,close_error_type=type(error).__name__)
            result['native_actions']=link.counts
        engine.raw.write_json(out/'receipt-private.json',result)
    print(json.dumps(result));return result['exit_code']


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--out',type=Path)
    p.add_argument('--C-identity',type=Path);p.add_argument('--B-identity',type=Path)
    p.add_argument('--image',type=Path);p.add_argument('--image-sha256');p.add_argument('--reference-identity',type=Path)
    p.add_argument('--execute',action='store_true');p.add_argument('--worker',action='store_true');a=p.parse_args()
    base=ROOT/'node-b/docs/FIVE-NODE-MIGRATION/M1-20261104'
    artifact=json.loads((base/'RELEASE-MANIFEST.json').read_text())['applications']['D']['artifacts']['FIVE_NODE_D.bin']
    need((a.image is None)==(a.image_sha256 is None),'D_IMAGE_AND_SHA_REQUIRED_TOGETHER')
    image=a.image or base/artifact['path'];sha=a.image_sha256 or artifact['sha256']
    candidate=image.read_bytes();need(16384<len(candidate)<=32768 and engine.package.digest(candidate)==sha,'D_MANIFEST_SHA')
    engine.package.vector_check(candidate)
    if not(a.execute or a.worker):
        print(json.dumps({'status':'PLAN_ONLY','board':'D','sectors':[0,1],'candidate_bytes':image.stat().st_size,
            'candidate_sha256':sha,'original_application_backup_required':False}));return 0
    need(a.out is not None and a.C_identity is not None and a.B_identity is not None,'D_OUTPUT_AND_KNOWN_IDENTITIES_REQUIRED')
    engine.package.protected(a.out.parent,False);need(not a.out.exists(),'D_NEW_OUTPUT_REQUIRED')
    excluded={json.loads(engine.package.read(f,False))['uid_hex'] for f in (a.C_identity,a.B_identity)}
    need(a.image is None or a.reference_identity is not None,'D_UPDATE_REQUIRES_KNOWN_D_IDENTITY')
    reference=json.loads(engine.package.read(a.reference_identity,False)) if a.reference_identity else None
    if a.worker:return worker(a.out,image,sha,excluded,reference)
    return supervisor.supervise([sys.executable,'-X','utf8',str(Path(__file__)),*sys.argv[1:],'--worker'],a.out)


if __name__=='__main__':raise SystemExit(main())
