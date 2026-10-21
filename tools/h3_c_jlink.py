"""C专用J-Link当前原件核验及一次隔离应用重刷；配置和保护区只读。

所有原始UID、Flash和工具输出只进入仓库外私有窗口。不自动重试、恢复或GO，
不发送独立erase、RAM配置注入、options写入或入口强设命令。
"""
import argparse
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path
import re
import subprocess

from stm32loader.bootloader import Stm32Bootloader
from gateway.physical_can.bench.flash_c import external_identity
from tools import h3_c_readonly as expected

ROOT=Path(__file__).resolve().parents[1]
JLINK=Path('D:/keil/ARM/Segger/JLink.exe')


def sha(data):return hashlib.sha256(data).hexdigest()


def plan(image):
    if any(c in image.as_posix() for c in (' ', ',', '\n','\r')):raise ValueError('C_IMAGE_PATH_INVALID')
    data=image.read_bytes()
    if len(data)!=43172 or sha(data)!=expected.IMAGE:raise ValueError('ISOLATED_C_IMAGE_MISMATCH')
    return {'role':'C','method':'JLINK_SWD_1000KHZ','image_sha256':expected.IMAGE,'image_bytes':len(data),
        'start':0x08000000,'end_exclusive':0x08000000+len(data),'erase_sectors':[0,1,2],
        'config_sector':3,'config_write':False,'expected_record_sha256':expected.RECORD,
        'expected_current_64k_sha256':expected.FULL,'protected_sectors':[7,11],
        'options_write':False,'mass_erase':False,'automatic_go':False,'automatic_restore':False,
        'temporary_debug_IWDG_freeze_register':'0xE0042008_BIT12_RESTORE_AFTER_READBACK',
        'flash_algorithm_RAM_only':'SEGGER_TEMPORARY_ALGORITHM_NO_CREDENTIAL_INJECTION',
        'jlink_sha256':sha(JLINK.read_bytes()),
        'support_source_sha256':{name:sha((ROOT/name).read_bytes()) for name in (
            'tools/h3_c_readonly.py','gateway/physical_can/bench/flash_c.py',
            'gateway/physical_can/r2_config_record.py')}}


def authorize(card,image,identity):
    if card.get('auth_id')!='AUTH-AC-C-ISOLATED-JLINK' or card.get('approved_by_owner') is not True:
        raise ValueError('EXPLICIT_C_JLINK_WINDOW_REQUIRED')
    expiry=datetime.fromisoformat(card['expires_utc'])
    if expiry.tzinfo is None or datetime.now(timezone.utc)>=expiry:raise ValueError('C_JLINK_WINDOW_EXPIRED')
    if card.get('tool_sha256')!=sha(Path(__file__).read_bytes()) or card.get('plan')!=plan(image):
        raise ValueError('C_JLINK_SCOPE_CHANGED')
    if card.get('source_commit')!=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip():
        raise ValueError('C_JLINK_SOURCE_CHANGED')
    if identity.resolve().is_relative_to(ROOT) or sha(identity.read_bytes())!=card.get('identity_source_sha256'):
        raise ValueError('C_JLINK_EXTERNAL_IDENTITY_CHANGED')
    if card.get('field_state')!='OWNER_JLINK_CONNECTED_C_A_OFF_CAN_SEPARATED':
        raise ValueError('C_JLINK_FIELD_SCOPE_REQUIRED')


class Bridge:
    def __init__(self,private):self.private=private;self.index=0;self.voltages=[];self.download_observation='NO_LOAD_REQUEST'
    def validate_commands(self,commands,write=False):
        # 子类只能显式扩展维护事务；旧隔离入口维持原命令白名单。
        allowed=('savebin ','loadbin ','verifybin ','w4 0xE0042008 ') if write else ('savebin ',)
        if not all(s in ('connect','h','q') or s.startswith(allowed) for s in commands):
            raise ValueError('COMMAND_OUTSIDE_C_SCOPE')
    def execute(self,commands,write=False):
        self.validate_commands(commands,write)
        self.index+=1;text='\n'.join(commands)+'\n';stem=self.private/('jlink-'+str(self.index))
        with stem.with_suffix('.commands').open('x') as f:f.write(text)
        r=subprocess.run([str(JLINK),'-device','STM32F407ZG','-if','SWD','-speed','1000'],
            input=text.encode('ascii'),capture_output=True,timeout=90,
            creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
        raw=r.stdout+r.stderr;stem.with_suffix('.raw.log').write_bytes(raw)
        if any(s.startswith('loadbin ') for s in commands):
            # loadbin提交不等于物理擦写；SEGGER对相同内容会跳过，必须如实区分。
            self.download_observation=('SKIPPED_IDENTICAL' if b'flash download skipped. flash contents already match' in raw.lower()
                else 'NOT_DETERMINED_FROM_SDK_LOG')
        match=re.search(rb'VTref\s*=\s*([0-9.]+)V',raw)
        if r.returncode:raise RuntimeError('JLINK_PROCESS_NONZERO')
        if not match or not 3.0<=float(match[1])<=3.6:raise RuntimeError('C_VTREF_NOT_VERIFIED_STOP')
        self.voltages.append(float(match[1]))


class Window:
    def __init__(self,private,bridge,identity):self.private=private;self.bridge=bridge;self.identity=identity
    def read(self,label,specs,extra=()):
        commands=['connect','h',*extra]
        for name,address,length in specs:
            p=self.private/(label+'-'+name+'.bin')
            if p.exists() or any(c in p.as_posix() for c in (' ', ',', '\n','\r')):
                raise ValueError('C_PRIVATE_PATH_OCCUPIED_OR_INVALID')
            commands.append(f'savebin {p.as_posix()}, {hex(address)}, {hex(length)}')
        self.bridge.execute([*commands,'q'],write=bool(extra))
        result={}
        for name,_,length in specs:
            data=(self.private/(label+'-'+name+'.bin')).read_bytes()
            if len(data)!=length:raise RuntimeError('C_JLINK_READ_LENGTH_MISMATCH')
            result[name]=data
        return result
    def identity_read(self,label):
        data=self.read(label,[('chip',0xE0042000,4),('size',0x1FFF7A22,2),
            ('uid',0x1FFF7A10,12),('options',0x1FFFC000,16),('freeze',0xE0042008,4),
            ('boot-alias',0x00000000,8),('system-rom',0x1FFF0000,8)])
        if int.from_bytes(data['chip'],'little')&0xFFF!=int(self.identity['EXPECTED_CHIP_ID'],16) or int.from_bytes(data['size'],'little')!=1024:
            raise RuntimeError('C_JLINK_CHIP_OR_CAPACITY_MISMATCH')
        if Stm32Bootloader.format_uid(data['uid'])!=self.identity['EXPECTED_UID']:
            raise RuntimeError('C_JLINK_UID_MISMATCH_STOP')
        if data['options'][1]!=0xAA or sha(data['options'])!=expected.OPTIONS:
            raise RuntimeError('C_JLINK_OPTIONS_MISMATCH_STOP')
        return data
    def protection(self,label):
        data=self.read(label,[('sector7',0x08060000,0x20000),('sector11',0x080E0000,0x20000),
            ('options',0x1FFFC000,16)])
        if any(sha(data[k])!=expected.PROTECTED for k in ('sector7','sector11')) or sha(data['options'])!=expected.OPTIONS:
            raise RuntimeError('C_JLINK_PROTECTION_MISMATCH_STOP')
        return data
    def run(self,image,write,progress):
        data=image.read_bytes();plan(image)
        identity=self.identity_read('identity-before');protected=self.protection('protected-before')
        freeze=int.from_bytes(identity['freeze'],'little')|(1<<12)
        # 只冻结调试暂停时的IWDG，避免应用已启动时复位打断维护；不改运行喂狗。
        first=self.read('first',[('flash64k',0x08000000,65536)],
            [f'w4 0xE0042008 {hex(freeze)}'])['flash64k']
        second=self.read('second',[('flash64k',0x08000000,65536)])['flash64k']
        if first!=second or (self.private/'first-flash64k.bin').read_bytes()!=first or (self.private/'second-flash64k.bin').read_bytes()!=first:
            raise RuntimeError('C_JLINK_DOUBLE_BACKUP_MISMATCH_STOP')
        if sha(first)!=expected.FULL or sha(first[:43172])!=expected.IMAGE or sha(first[49152:49152+336])!=expected.RECORD or expected.validate(first[49152:49152+336])!=2:
            raise RuntimeError('C_JLINK_CURRENT_STATE_MISMATCH_STOP_NO_WRITE')
        proof={'backup_sha256':sha(first),'backup_bytes_each':65536,'double_read_match':True,
            'image_sha256':sha(data),'record_sha256':expected.RECORD,'options_sha256':expected.OPTIONS,
            'protected_sha256':expected.PROTECTED,'generation':2,'device_identity_match':True,
            'boot_alias_matches_system_rom_before':identity['boot-alias']==identity['system-rom']}
        (self.private/'fresh-backup.json').write_text(json.dumps(proof,indent=2))
        if write:
            if sha(image.read_bytes())!=expected.IMAGE:raise RuntimeError('C_IMAGE_CHANGED_BEFORE_LOAD')
            progress['flash_write_started']=True
            (self.private/'flash-write-attempt.json').write_text(json.dumps({**proof,**progress},indent=2))
            # loadbin范围止于sector2；sector3整16KiB与7/11/options均只读核对。
            after=self.read('after',[('flash64k',0x08000000,65536)],
                [f'loadbin {image.as_posix()}, 0x08000000','h',f'verifybin {image.as_posix()}, 0x08000000'])['flash64k']
            if after!=data.ljust(49152,b'\xff')+first[49152:]:raise RuntimeError('C_JLINK_APPLICATION_OR_CONFIG_READBACK_FAILED')
        else:after=first
        final_protection=self.protection('protected-after');final_identity=self.identity_read('identity-after')
        if protected!=final_protection or any(identity[k]!=final_identity[k] for k in ('chip','size','uid','options')):
            raise RuntimeError('C_JLINK_IDENTITY_OR_PROTECTION_CHANGED')
        restored=self.read('debug-restored',[('freeze',0xE0042008,4)],
            [f'w4 0xE0042008 {hex(int.from_bytes(identity["freeze"],"little"))}'])['freeze']
        if restored!=identity['freeze']:raise RuntimeError('C_DEBUG_REGISTER_RESTORE_FAILED')
        observation=getattr(self.bridge,'download_observation','NOT_DETERMINED_FROM_TEST_BRIDGE')
        return {**proof,'exit_code':0,'gate':'C_ISOLATED_IMAGE_LOAD_VERIFY_MATCH' if write else 'C_CURRENT_PAIR_READONLY_VERIFIED',
            'flash_write_started':write,'loadbin_submitted':write,'SDK_download_observation':observation,
            'actual_flash_erase_or_program':False if observation=='SKIPPED_IDENTICAL' or not write else None,
            'actual_64k_sha256':sha(after),'config_sector3_unchanged':True,
            'sector7_11_options_unchanged':True,'target_execution':'HALT_REQUESTED_NO_GO',
            'debug_register_restored_verified':True,
            'cold_boot':'NOT_OBSERVED','application_network_test':'NOT_RUN'}


def main():
    p=argparse.ArgumentParser();p.add_argument('action',choices=('plan','read','program'))
    p.add_argument('--image',type=Path,required=True);p.add_argument('--auth',type=Path)
    p.add_argument('--identity-source',type=Path);p.add_argument('--private-dir',type=Path);args=p.parse_args()
    if args.action=='plan':print(json.dumps(plan(args.image),indent=2));return 0
    card=json.loads(args.auth.read_text());authorize(card,args.image,args.identity_source)
    if card.get('action')!=args.action or (args.action=='program' and card.get('flash_once_approved') is not True):
        raise ValueError('C_SINGLE_FLASH_ACTION_NOT_APPROVED')
    private=args.private_dir.resolve()
    if private.is_relative_to(ROOT) or not private.is_dir() or any(private.iterdir()):raise ValueError('C_EMPTY_PRIVATE_DIRECTORY_REQUIRED')
    progress={'exit_code':1,'flash_write_started':False,'automatic_restore':False}
    try:
        bridge=Bridge(private)
        result=Window(private,bridge,external_identity(args.identity_source)).run(args.image,args.action=='program',progress)
        result['VTref_voltages']=bridge.voltages
    except Exception as error:
        result={**progress,'gate':'STOPPED_NO_AUTO_RETRY_OR_RESTORE','failure_type':type(error).__name__}
        if type(error) in (RuntimeError,ValueError):result['failure_code']=str(error)
    (private/'result.json').write_text(json.dumps(result,indent=2));print(json.dumps(result,indent=2));return result['exit_code']


if __name__=='__main__':raise SystemExit(main())
