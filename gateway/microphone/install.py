"""MIC更新/恢复薄入口：复用已验证安装引擎，入口重新实读当前Flash；不重复创建假双读备份。"""
import argparse
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'node-b/tools'))
import abc_board_backup as backup
import b4_recovery as recovery
import b4_swd_install as engine


def prepare(a):
    proof=json.loads(recovery.read(a.current_install/'receipt-private.json',False))
    engine.require(proof['board']=='C' and proof['exit_code']==0 and proof['Close_completed'],'MIC_CURRENT_INSTALL_REQUIRED')
    probe=a.current_install/'probe'
    full=recovery.read(probe/'after-full-private.bin',False)
    options=recovery.read(probe/'after-options-private.bin',False)
    ident=json.loads(recovery.read(probe/'identity-after-private.json',False))
    engine.require(recovery.digest(full)==proof['full_flash_sha256'],'MIC_CURRENT_READBACK_CHANGED')
    original=json.loads(recovery.read(a.original_backup/'probe/identity-private.json',False))
    engine.require(ident['uid_hex']==original['uid_hex'],'MIC_WRONG_CURRENT_C')
    image=recovery.read(a.image,False)
    # 这里是单份已核验安装读回的离线计划；真实独立前读由engine.execute完成。
    plan,payload=recovery.make_plan('C',full,full,options,options,ident,ident,image,a.image_sha256)
    engine.require(set(plan['sectors'])<={0,1,2} and payload['expected-full-private.bin'][49152:]==full[49152:],'MIC_CONFIG_PRESERVATION')
    plan.update(scope='OWNER_VOICE_MIC_C_APPLICATION_ONLY',
                baseline_provenance='Previous actual post-install full readback; fresh independent preflight before Halt',
                independent_acquisition_proven=False)
    return plan,payload


def worker(a):
    plan,payload=prepare(a);a.out.mkdir();probe=a.out/'probe';probe.mkdir();link=None
    result={'status':'STOP','exit_code':1,'board':'C','automatic_retry_or_restore':False}
    engine.raw.write_json(a.out/'image-plan-private.json',plan)
    try:
        link=engine.InstallLink(probe,plan['erase_end_exclusive']-0x08000000)
        result.update(engine.execute(link,probe,{'phase':'install','board':'C'},plan,payload))
    except (Exception,KeyboardInterrupt) as error:
        if link:link.verified_running_flash=False
        engine.raw.write_json(a.out/'failure-private.json',{'type':type(error).__name__,'reason':str(error)})
        result.update(exit_code=1,error_type=type(error).__name__)
    finally:
        if link:
            try:
                if not link.verified_running_flash and link.close_resume_enabled:link.set_close_resume(False)
                link.close();result['Close_completed']=True
            except Exception as error:result.update(exit_code=1,Close_completed=False,close_error_type=type(error).__name__)
            result['native_actions']=link.counts
        engine.raw.write_json(a.out/'receipt-private.json',result)
    print(json.dumps(result));return result['exit_code']


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('current-install','original-backup','image','out'):p.add_argument('--'+name,type=Path,required=True)
    p.add_argument('--image-sha256',required=True);p.add_argument('--execute',action='store_true');p.add_argument('--worker',action='store_true')
    a=p.parse_args();recovery.protected(a.out.parent,False);engine.require(not a.out.exists(),'MIC_NEW_OUTPUT_REQUIRED')
    plan,_=prepare(a)
    if not(a.execute or a.worker):print(json.dumps({'status':'PLAN_ONLY','sectors':plan['sectors']}));return 0
    if a.worker:return worker(a)
    command=[sys.executable,'-X','utf8',str(Path(__file__)),'--worker','--current-install',str(a.current_install),
             '--original-backup',str(a.original_backup),'--image',str(a.image),'--image-sha256',a.image_sha256,'--out',str(a.out)]
    return backup.supervise(command,a.out)


if __name__=='__main__':raise SystemExit(main())
