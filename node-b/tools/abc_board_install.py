"""三板候选恢复薄入口：复用原SWD安装器；仅sector0/1/2，不使用签名或nonce。"""
import argparse
import ctypes as C
import json
from pathlib import Path
import sys

import abc_board_backup as backup
import b4_recovery as recovery
import b4_swd_install as install

FREEZE=0xe0042008


class Link(install.InstallLink):
    def __init__(self,out,board,size=49152):
        self.board=board;self.original_freeze=None;self.debug_freeze_writes=0
        super().__init__(out,size)

    def freeze_read(self):
        value=(C.c_uint8*4)()
        n=install.raw.Link.call(self,'JLINKARM_ReadMemEx',FREEZE,4,value,0)
        install.require(n==4,'ABC_DEBUG_FREEZE_READ')
        return int.from_bytes(bytes(value),'little')

    def freeze_write(self,value):
        blob=(C.c_uint8*4).from_buffer_copy(value.to_bytes(4,'little'))
        n=install.raw.Link.call(self,'JLINKARM_WriteMem',FREEZE,4,blob)
        install.require(n==4 and self.freeze_read()==value,'ABC_DEBUG_FREEZE_WRITE')
        self.debug_freeze_writes+=1

    def call(self,name,*args,timeout=5):
        if self.board=='A' and name=='JLINKARM_Halt':
            self.original_freeze=self.freeze_read()
            self.freeze_write(self.original_freeze|(1<<12))
        result=super().call(name,*args,timeout=timeout)
        if self.board=='A' and name=='JLINKARM_Go' and self.original_freeze is not None:
            self.freeze_write(self.original_freeze)
        return result


def prepare(board,reference,image,expected_sha):
    reference=recovery.protected(reference,False)
    proof=json.loads((reference/'receipt-private.json').read_text())
    install.require(proof['board']==board and proof['exit_code']==0 and proof['independent_reads_match']
                    and proof['Close_completed'],'ABC_CURRENT_BACKUP_REQUIRED')
    probe=reference/'probe'
    files=[recovery.read(probe/name,False) for name in
        ('flash-1-private.bin','flash-2-private.bin','options-1-private.bin','options-2-private.bin',
         'identity-private.json','identity-after-private.json')]
    candidate=image.read_bytes();install.require(recovery.digest(candidate)==expected_sha,'ABC_CANDIDATE_SHA')
    # A复用相同48KiB三扇区几何；原安装CLI的B/C授权范围保持不变。
    plan,payload=recovery.make_plan('B' if board=='A' else 'C',*files[:4],
        json.loads(files[4]),json.loads(files[5]),candidate,expected_sha)
    plan['board_role']=board;plan['scope']='ABC_OWNER_B_TEMP_SCREEN_APPLICATION_48K' if board=='B' else 'ABC_OWNER_RESTORE_APPLICATION_48K'
    end=plan['erase_end_exclusive']-0x08000000
    install.require((plan['sectors']==[0,1,2] or board=='C' and plan['sectors'] in ([0],[0,1]))
                    and payload['expected-full-private.bin'][end:]==files[0][end:],
                    'ABC_CONFIG_SECTOR_PRESERVATION')
    return plan,payload


def worker(a,out):
    plan,payload=prepare(a.board,a.backup,a.image,a.image_sha256)
    out.mkdir();probe=out/'probe';probe.mkdir();link=None
    result={'status':'STOP','exit_code':1,'board':a.board,'automatic_reflash_or_rollback':False}
    install.raw.write_json(out/'image-plan-private.json',plan)
    try:
        link=Link(probe,a.board,plan['erase_end_exclusive']-0x08000000)
        result.update(install.execute(link,probe,{'phase':'install','board':a.board},plan,payload))
        result['status']='ABC_'+a.board+'_APP'+''.join(map(str,plan['sectors']))+'_FULL_VERIFY_BOOT_PASS'
    except (Exception,KeyboardInterrupt) as error:
        if link:link.verified_running_flash=False
        install.raw.write_json(out/'failure-private.json',{'type':type(error).__name__,'reason':str(error)})
        result.update(status='STOP',exit_code=1,error_type=type(error).__name__,error_sha256=recovery.digest(str(error).encode()))
    finally:
        if link:
            try:
                if not link.verified_running_flash and link.close_resume_enabled:link.set_close_resume(False)
                link.close();result['Close_completed']=True
            except Exception as error:result.update(status='STOP',exit_code=1,Close_completed=False,close_error_type=type(error).__name__)
            result.update(native_actions=link.counts,download_started=link.download_started,
                debug_IWDG_freeze_writes=link.debug_freeze_writes,
                debug_IWDG_freeze_restored=link.debug_freeze_writes==2 if a.board=='A' else True)
        install.raw.write_json(out/'receipt-private.json',result)
    print(json.dumps(result));return result['exit_code']


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--board',choices=('A','B','C'),required=True)
    for name in ('backup','image','out'):p.add_argument('--'+name,type=Path,required=True)
    p.add_argument('--image-sha256',required=True);p.add_argument('--execute',action='store_true');p.add_argument('--worker',action='store_true')
    a=p.parse_args();out=a.out.resolve()
    recovery.protected(out.parent,False);install.require(not out.exists(),'ABC_OUTPUT_EXISTS')
    plan,payload=prepare(a.board,a.backup,a.image,a.image_sha256)
    if not(a.execute or a.worker):
        print(json.dumps({'status':'PLAN_ONLY','board':a.board,'candidate_bytes':plan['candidate_bytes'],
            'sectors':plan['sectors'],'config_preserved':True}));return 0
    if a.worker:return worker(a,out)
    cmd=[sys.executable,'-X','utf8',str(Path(__file__)),'--worker','--board',a.board,
         '--backup',str(a.backup),'--image',str(a.image),'--image-sha256',a.image_sha256,'--out',str(out)]
    return backup.supervise(cmd,out)


if __name__=='__main__':raise SystemExit(main())
