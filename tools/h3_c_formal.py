"""C正式MOCK的J-Link事务：应用/未提交配置先读回，最后仅编程配置commit字。

原件、UID与凭据只保存在仓库外。无mass erase、options写入、自动GO或自动恢复。
commit的32位编程序列依据STM32F4 SPL FLASH_ProgramWord与RM0090；错误标志不清零。
"""
import argparse
from datetime import datetime,timezone
import json,struct,subprocess
from pathlib import Path
from tools import h3_c_jlink as previous
from gateway.physical_can import r2_flash_c as transaction
from gateway.physical_can.r2_config_record import validate,COMMITTED

ROOT=previous.ROOT
SR=0x40023C0C;CR=0x40023C10;KEYR=0x40023C04;COMMIT=0x0800C014
ERRORS=0xF2;BUSY=1<<16


def checked_idle(sr,cr):
    # 不以清除SR掩盖既有错误；PG/SER/MER/STRT均须已关闭。
    if sr&(ERRORS|BUSY) or cr&0x10007:raise ValueError('FLASH_NOT_IDLE_OR_ERROR_STOP')


def restore_commands(original_cr):
    # 先在未锁定状态恢复PG/PSIZE等低位，再单独LOCK；合并写在本板保留了旧PG。
    lower=original_cr&~(1<<31)
    return [f'w4 {hex(CR)} {hex(lower)}',*([f'w4 {hex(CR)} {hex(original_cr)}'] if original_cr&(1<<31) else [])]


class Bridge(previous.Bridge):
    def __init__(self,private):super().__init__(private);self.exact_transaction=None
    def validate_commands(self,commands,write=False):
        if self.exact_transaction is not None:
            if not write or commands!=self.exact_transaction:raise ValueError('EXACT_COMMIT_TRANSACTION_REQUIRED')
        else:super().validate_commands(commands,write)
    def exact(self,commands):
        # 只允许本模块构造的解锁/commit序列临时进入白名单，finally恢复旧白名单。
        self.exact_transaction=list(commands)
        try:self.execute(commands,write=True)
        finally:self.exact_transaction=None


def scope(manifest,image,record):
    p=transaction.offline_plan(manifest,image,record,'formal-synthetic')
    if len(image)!=43172 or previous.sha(image)!='b9b25b186c3b40d62b4a1c1919e09f27b639806271a3b20ae7fc80ea4cda1efe':raise ValueError('FROZEN_FORMAL_IMAGE_REQUIRED')
    if validate(record)!=3 or previous.sha(record)!='395c6a36d7c4a636b34a72eacd1ccc2a2fc7f025df7089f3d94e1d2de14c5a3b':raise ValueError('FROZEN_FORMAL_CONFIG_REQUIRED')
    return {**p,'method':'JLINK_SWD_1000KHZ','expected_current_64k_sha256':previous.expected.FULL,
            'expected_current_record_sha256':previous.expected.RECORD,'commit_word_address':COMMIT,
            'flash_control_registers':[KEYR,SR,CR],'mass_erase':False,'automatic_go':False,'automatic_restore':False,
            'jlink_sha256':previous.sha(previous.JLINK.read_bytes()),
            'support_source_sha256':{name:previous.sha((ROOT/name).read_bytes()) for name in
                ('tools/h3_c_jlink.py','tools/h3_c_readonly.py','gateway/physical_can/r2_flash_c.py','gateway/physical_can/r2_config_record.py')}}


class Window(previous.Window):
    def commit(self,original_cr):
        # LOCK只能通过KEYR解锁；先读回解锁结果，再设置x32/PG。电压由Bridge约束为3.0–3.6V。
        keyread=self.private/'commit-unlocked-cr.bin'
        keys=[f'w4 {hex(KEYR)} 0x45670123',f'w4 {hex(KEYR)} 0xcdef89ab'] if original_cr&(1<<31) else []
        self.bridge.exact(['connect','h',*keys,f'savebin {keyread.as_posix()}, {hex(CR)}, 0x4','q'])
        unlocked=int.from_bytes(keyread.read_bytes(),'little')
        if unlocked&(1<<31) or unlocked!=(original_cr&~(1<<31)):raise ValueError('FLASH_UNLOCK_READBACK_FAILED')
        pg=(unlocked&~0x300)|0x201
        status=self.private/'commit-final-status.bin'
        # 只在已验证的擦除态commit地址写一个word；等待后恢复原CR（含LOCK），再读SR/CR。
        commands=['connect','h',f'w4 {hex(CR)} {hex(pg)}',f'w4 {hex(COMMIT)} {hex(COMMITTED)}','sleep 10',
                  *restore_commands(original_cr),f'savebin {status.as_posix()}, {hex(SR)}, 0x8','q']
        self.bridge.exact(commands)
        raw=status.read_bytes()
        if len(raw)!=8:raise ValueError('FLASH_STATUS_READ_LENGTH')
        sr,cr=struct.unpack('<II',raw);checked_idle(sr,cr)
        if cr!=original_cr:raise ValueError('FLASH_CR_RESTORE_FAILED')
        return {'FLASH_SR_after':sr,'FLASH_CR_restored':True,'commit_programmed_last':True}
    def restore_control_only(self,expected_flash,original_cr,original_freeze):
        """仅修正已确认的PG/LOCK恢复问题；当前新镜像、UID、保护及错误状态缺一即停。"""
        before=self.identity_read('control-identity-before');protected=self.protection('control-protected-before')
        current=self.read('control-current',[('flash64k',transaction.START,65536),('status',SR,8)])
        sr,cr=struct.unpack('<II',current['status'])
        if current['flash64k']!=expected_flash or sr or cr!=(original_cr|0x201):raise ValueError('RECOVERY_CURRENT_STATE_MISMATCH_NO_WRITE')
        if int.from_bytes(before['freeze'],'little')!=(original_freeze|(1<<12)):raise ValueError('RECOVERY_DEBUG_BASELINE_CHANGED')
        unlocked=self.private/'recovery-unlocked-cr.bin'
        self.bridge.exact(['connect','h',f'w4 {hex(KEYR)} 0x45670123',f'w4 {hex(KEYR)} 0xcdef89ab',f'savebin {unlocked.as_posix()}, {hex(CR)}, 0x4','q'])
        if int.from_bytes(unlocked.read_bytes(),'little')!=(cr&~(1<<31)):raise ValueError('RECOVERY_UNLOCK_FAILED')
        status=self.private/'recovery-final-status.bin'
        self.bridge.exact(['connect','h',*restore_commands(original_cr),f'savebin {status.as_posix()}, {hex(SR)}, 0x8','q'])
        sr,cr=struct.unpack('<II',status.read_bytes());checked_idle(sr,cr)
        if cr!=original_cr:raise ValueError('RECOVERY_CR_RESTORE_FAILED')
        final=self.read('control-final',[('flash64k',transaction.START,65536),('freeze',0xE0042008,4)],
                        [f'w4 0xE0042008 {hex(original_freeze)}'])
        if final['flash64k']!=expected_flash or int.from_bytes(final['freeze'],'little')!=original_freeze:raise ValueError('RECOVERY_FINAL_READBACK_FAILED')
        if self.protection('control-protected-final')!=protected:raise ValueError('RECOVERY_PROTECTION_CHANGED')
        return {'exit_code':0,'gate':'REGISTER_ONLY_CORRECTION_AND_FORMAL_64K_VERIFIED','FLASH_SR_after':sr,
                'FLASH_CR_after':hex(cr),'actual_64k_sha256':previous.sha(expected_flash),'sector7_11_options_unchanged':True,
                'debug_register_restored':True,'flash_program_or_erase_commands':0,'original_program_exit':1,
                'automatic_go':False,'cold_boot':'NOT_YET_OBSERVED'}
    def run_formal(self,manifest,image,record,progress):
        plan=scope(manifest,image,record)
        identity=self.identity_read('identity-before');protected=self.protection('protected-before')
        freeze=int.from_bytes(identity['freeze'],'little')|(1<<12)
        first=self.read('first',[('flash64k',transaction.START,65536)],
                        [f'w4 0xE0042008 {hex(freeze)}'])['flash64k']
        second=self.read('second',[('flash64k',transaction.START,65536)])['flash64k']
        if first!=second or previous.sha(first)!=previous.expected.FULL:raise ValueError('CURRENT_DOUBLE_BACKUP_MISMATCH_STOP')
        if any((self.private/(label+'-flash64k.bin')).read_bytes()!=first for label in ('first','second')):raise ValueError('BACKUP_DISK_READBACK_FAILED')
        if previous.sha(first[49152:49152+336])!=previous.expected.RECORD or validate(first[49152:49152+336])!=2:raise ValueError('CURRENT_GENERATION2_REQUIRED')
        pending_record=record[:20]+b'\xff'*4+record[24:]
        pending=image.ljust(49152,b'\xff')+pending_record.ljust(16384,b'\xff')
        expected=image.ljust(49152,b'\xff')+record.ljust(16384,b'\xff')
        target=self.private/'formal-pending64k.bin';target.write_bytes(pending)
        progress.update(flash_write_started=True,backup_sha256=previous.sha(first),plan=plan)
        (self.private/'write-started.json').write_text(json.dumps(progress,indent=2))
        after=self.read('pending',[('flash64k',transaction.START,65536)],
                        [f'loadbin {target.as_posix()}, 0x08000000','h',f'verifybin {target.as_posix()}, 0x08000000'])['flash64k']
        if after!=pending:raise ValueError('PENDING_64K_READBACK_FAILED_STOP')
        if self.protection('protected-pending')!=protected:raise ValueError('PROTECTION_CHANGED_BEFORE_COMMIT')
        status=self.read('flash-idle',[('status',SR,8)])['status'];sr,cr=struct.unpack('<II',status);checked_idle(sr,cr)
        commit=self.commit(cr)
        final=self.read('final',[('flash64k',transaction.START,65536)])['flash64k']
        if final!=expected or validate(final[49152:49152+336])!=3:raise ValueError('COMMITTED_64K_READBACK_FAILED_STOP')
        if self.protection('protected-final')!=protected:raise ValueError('PROTECTION_CHANGED_AFTER_COMMIT')
        end=self.identity_read('identity-final')
        if any(end[k]!=identity[k] for k in ('chip','size','uid','options')):raise ValueError('DEVICE_IDENTITY_CHANGED')
        restored=self.read('debug-restored',[('freeze',0xE0042008,4)],[f'w4 0xE0042008 {hex(int.from_bytes(identity["freeze"],"little"))}'])['freeze']
        if restored!=identity['freeze']:raise ValueError('DEBUG_RESTORE_FAILED')
        return {'exit_code':0,'gate':'FORMAL_SYNTHETIC_C_FULL_READBACK_MATCH','image_sha256':previous.sha(image),
                'record_sha256':previous.sha(record),'generation':3,'backup_sha256':previous.sha(first),
                'actual_64k_sha256':previous.sha(final),'protected_sha256':previous.expected.PROTECTED,
                'options_sha256':previous.expected.OPTIONS,'sector7_11_options_unchanged':True,
                'debug_register_restored':True,'cold_boot':'NOT_YET_OBSERVED','automatic_go':False,**commit}


def main():
    p=argparse.ArgumentParser();p.add_argument('action',choices=('plan','program','restore-control'))
    for name in ('manifest','image','record'):p.add_argument('--'+name,type=Path,required=True)
    for name in ('auth','identity-source','private-dir'):p.add_argument('--'+name,type=Path)
    p.add_argument('--original-window',type=Path)
    a=p.parse_args()
    if a.record.resolve().is_relative_to(ROOT):raise ValueError('EXTERNAL_PRIVATE_RECORD_REQUIRED')
    manifest=json.loads(a.manifest.read_text());image=a.image.read_bytes();record=a.record.read_bytes();plan=scope(manifest,image,record)
    if a.action=='plan':print(json.dumps(plan));return 0
    card=json.loads(a.auth.read_text());identity_path=a.identity_source.resolve()
    if card.get('auth_id')!='MPM-H3-004_OWNER_CONTINUOUS_AUTHORIZATION_AMENDMENT' or card.get('owner_approved_scope') is not True or card.get('plan')!=plan:raise ValueError('FORMAL_SCOPE_CARD_MISMATCH')
    if card.get('action','program')!=a.action:raise ValueError('EXACT_ACTION_SCOPE_REQUIRED')
    if card.get('tool_sha256')!=previous.sha(Path(__file__).read_bytes()) or card.get('source_commit')!=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip():raise ValueError('FROZEN_TOOL_SOURCE_CHANGED')
    if identity_path.is_relative_to(ROOT) or previous.sha(identity_path.read_bytes())!=card.get('identity_source_sha256'):raise ValueError('EXTERNAL_IDENTITY_CHANGED')
    if datetime.now(timezone.utc)>=datetime.fromisoformat(card['expires_utc']):raise ValueError('MAINTENANCE_WINDOW_EXPIRED')
    transaction.verify_sources(manifest,card['source_commit'],Path(card['sdk_root']))
    private=a.private_dir.resolve()
    if private.is_relative_to(ROOT) or not private.is_dir() or any(private.iterdir()):raise ValueError('NEW_EMPTY_PRIVATE_DIRECTORY_REQUIRED')
    progress={'exit_code':1,'flash_write_started':False,'automatic_restore':False}
    try:
        bridge=Bridge(private);window=Window(private,bridge,previous.external_identity(identity_path))
        if a.action=='restore-control':
            old=a.original_window.resolve()
            if old.is_relative_to(ROOT) or card.get('original_window')!=str(old):raise ValueError('EXTERNAL_ORIGINAL_WINDOW_REQUIRED')
            for name,digest in card['original_control_source_sha256'].items():
                if previous.sha((old/name).read_bytes())!=digest:raise ValueError('RECOVERY_ORIGINAL_CHANGED')
            if json.loads((old/'result.json').read_text()).get('exit_code')!=1:raise ValueError('FAILED_ORIGINAL_REQUIRED')
            original_cr=struct.unpack('<II',(old/'flash-idle-status.bin').read_bytes())[1]
            original_freeze=int.from_bytes((old/'identity-before-freeze.bin').read_bytes(),'little')
            result=window.restore_control_only(image.ljust(49152,b'\xff')+record.ljust(16384,b'\xff'),original_cr,original_freeze)
        else:result=window.run_formal(manifest,image,record,progress)
        result['VTref_voltages']=bridge.voltages
    except Exception as e:result={**progress,'exit_code':1,'failure_type':type(e).__name__,'failure_code':str(e) if isinstance(e,ValueError) else 'DETAILS_PRIVATE','automatic_restore':False}
    (private/'result.json').write_text(json.dumps(result,indent=2));print(json.dumps(result));return result['exit_code']


if __name__=='__main__':raise SystemExit(main())
