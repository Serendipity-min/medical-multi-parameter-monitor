"""H2 A专用J-Link下载：备份/身份/镜像门禁后才loadbin，禁止整片erase。

原始Flash、UID及工具完整输出仅保存在调用者准备的受限本地目录。
失败不重刷，不自动运行目标；必须由现场恢复门禁决定后续动作。
"""
import argparse
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path
import subprocess

ROOT=Path(__file__).resolve().parents[3]
HERE=ROOT/'gateway/physical_can'
def digest(b):return hashlib.sha256(b).hexdigest()

def main():
    p=argparse.ArgumentParser();p.add_argument('--commit',required=True)
    p.add_argument('--backup-dir',type=Path,required=True);p.add_argument('--confirm-role',choices=['A'],required=True)
    args=p.parse_args();stamp=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    private=args.backup_dir.resolve()
    if private.is_relative_to(ROOT):raise SystemExit('PRIVATE_BACKUP_MUST_BE_OUTSIDE_REPOSITORY')
    report={'role':'A','interface':'JLINK_SWD_1000KHZ','exit_code':1,'flash_write_started':False,'stage':'OFFLINE_GATES'}
    def command(name,lines):
        assert all(c in ('connect','h','q') or c.startswith(('savebin ','loadbin ','verifybin ','w4 0xE0042008 ')) for c in lines)
        text='\n'.join(lines)+'\n';(private/(name+'-'+stamp+'.jlink')).write_text(text,encoding='ascii')
        r=subprocess.run(['D:/keil/ARM/Segger/JLink.exe','-device','STM32F407ZG','-if','SWD','-speed','1000'],input=text.encode('ascii'),capture_output=True,timeout=90,creationflags=subprocess.CREATE_NO_WINDOW)
        (private/(name+'-'+stamp+'.raw.log')).write_bytes(r.stdout+r.stderr)
        report[name+'_process_exit']=r.returncode
        if r.returncode:raise RuntimeError('JLINK_NONZERO')
    def file(name):return private/(name+'-'+stamp+'.bin')
    def save(name,address,length):return f'savebin {file(name).as_posix()}, {hex(address)}, {hex(length)}'
    def read(name,length):
        data=file(name).read_bytes()
        if len(data)!=length:raise RuntimeError('READ_LENGTH_MISMATCH')
        return data
    try:
        head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
        if head!=args.commit:raise RuntimeError('SOURCE_HEAD_CHANGED')
        if subprocess.run(['git','diff','--quiet','HEAD','--','gateway/physical_can/bench','node-a/STM32F407_HOSPITAL','gateway/physical_can/evidence/h2/node-a-image-plan.json'],cwd=ROOT).returncode:raise RuntimeError('UNCOMMITTED_SOURCE')
        proof=json.loads((private/'private-summary.json').read_text(encoding='utf-8'))
        backup=(private/'flash-first.bin').read_bytes()
        if proof.get('exit_code')!=0 or not proof.get('independent_reads_match') or len(backup)!=0x100000 or digest(backup)!=proof['backup_sha256']:
            raise RuntimeError('A_BACKUP_NOT_VERIFIED')
        if digest((private/'flash-second.bin').read_bytes())!=proof['backup_sha256']:raise RuntimeError('SECOND_BACKUP_CHANGED')
        plan=json.loads((HERE/'evidence/h2/node-a-image-plan.json').read_text(encoding='utf-8'))
        image=HERE/'build/bench/node_a_a1.bin';data=image.read_bytes()
        if plan['exit_code'] or not plan['original_A_source_unchanged'] or digest(data)!=plan['image_sha256'] or not 8<len(data)<=65536:
            raise RuntimeError('NODE_A_IMAGE_NOT_VERIFIED')
        sp=int.from_bytes(data[:4],'little');reset=int.from_bytes(data[4:8],'little')
        if not (0x20000000<sp<=0x20020000 and 0x08000000<reset<0x08000000+len(data) and reset&1):raise RuntimeError('NODE_A_VECTORS_INVALID')
        sectors=list(range((len(data)+16383)//16384))
        if sectors!=plan['affected_sectors'] or sectors[-1]>3:raise RuntimeError('A_RANGE_INVALID')
        report.update({'source_commit':head,'image_sha256':digest(data),'bytes':len(data),'start':'0x08000000','end_exclusive':hex(0x08000000+len(data)),'affected_sectors':sectors,'stage':'IDENTITY_RECHECK'})
        command('precheck',['connect','h',save('chip',0xE0042000,4),save('uid',0x1fff7a10,12),save('option-register',0x40023c14,4),save('debug-freeze',0xE0042008,4),save('before',0x08000000,0x100000),'q'])
        if int.from_bytes(read('chip',4),'little')&0xfff!=0x413 or read('uid',12)!=(private/'uid.bin').read_bytes():raise RuntimeError('A_IDENTITY_MISMATCH')
        opt=read('option-register',4)
        if (int.from_bytes(opt,'little')>>8)&255!=0xaa:raise RuntimeError('RDP_PROTECTED_STOP')
        if read('before',0x100000)!=backup:raise RuntimeError('A_FLASH_CHANGED_SINCE_BACKUP')
        freeze=int.from_bytes(read('debug-freeze',4),'little')|(1<<12)
        # 仅冻结调试暂停期间的IWDG，避免已启动看门狗打断Flash维护；不改运行喂狗策略。
        # 固定loadbin范围让SEGGER按受影响扇区下载；绝不发送独立erase命令。
        report['stage']='BOUNDED_LOADBIN';report['flash_write_started']=True
        command('download',['connect','h',f'w4 0xE0042008 {hex(freeze)}',f'loadbin {image.as_posix()}, 0x08000000','h',f'verifybin {image.as_posix()}, 0x08000000',save('after',0x08000000,0x100000),save('after-options',0x40023c14,4),'q'])
        after=read('after',0x100000)
        if after[:len(data)]!=data:raise RuntimeError('A_IMAGE_READBACK_MISMATCH_STOP')
        # 整个64KiB应用扇区以外必须与备份逐字节相同，证明未做mass erase。
        if after[0x10000:]!=backup[0x10000:]:raise RuntimeError('A_OUTSIDE_APPLICATION_CHANGED_STOP')
        if read('after-options',4)!=opt:raise RuntimeError('A_OPTIONS_CHANGED_STOP')
        report.update({'exit_code':0,'stage':'VERIFIED_NOT_RUN','image_readback_match':True,'outside_64KiB_unchanged':True,'options_unchanged':True,'after_flash_sha256':digest(after),'IWDG_debug_freeze_only':True,'target_execution':'HALT_REQUESTED_NO_GO_COMMAND'})
    except BaseException as error:
        report['failure_type']=type(error).__name__
        if type(error) is RuntimeError:report['failure_code']=str(error)
    finally:
        (private/('a-download-'+stamp+'.json')).write_text(json.dumps(report,indent=2),encoding='utf-8')
        (HERE/'evidence/h2'/('a-download-'+stamp+'.json')).write_text(json.dumps(report,indent=2),encoding='utf-8')
        print(json.dumps(report,indent=2))
    return report['exit_code']

if __name__=='__main__':raise SystemExit(main())
