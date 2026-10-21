"""C sector0..3受限台架工具；默认隔离/离线，正式MOCK需显式配置，不自动GO或复位。"""
import argparse
from contextlib import redirect_stdout,redirect_stderr
from datetime import datetime,timezone
import hashlib
import io
import json
from pathlib import Path
import struct
import subprocess
import time

from gateway.physical_can.bench.flash_c import GateError,read_exact,protected_hashes,external_identity,verify_f4_identity
from gateway.physical_can.r2_config_record import validate,RecordError

ROOT=Path(__file__).resolve().parents[2]
START=0x08000000
CONFIG=0x0800C000
SPAN=0x10000


def sha(data):return hashlib.sha256(data).hexdigest()


def offline_plan(manifest,image,record,profile='isolated'):
    validate(record)
    if manifest.get('exit_code')!=0 or manifest.get('feature')!='H3_NETWORK_IRQ' or not manifest.get('fresh_sntp'):
        raise GateError('VERIFIED_FRESH_SNTP_IRQ_REQUIRED')
    # 端口与来源必须显式配对；旧入口仍只接受8884，正式台架入口不接受LIVE或隐含端口覆盖。
    if profile=='isolated':
        if not any('-DMP_MQTT_TLS_PORT=8884' in c and '-DMP_H3_TEST_SOURCE' in c and '-DMP_H3_PERSISTENT_CONFIG' in c for c in manifest.get('commands',[])):
            raise GateError('ISOLATED_8884_PROFILE_REQUIRED')
    elif profile=='formal-synthetic':
        flags=[f for c in manifest.get('commands',[]) for f in c]
        if (manifest.get('compiled_MQTT_port')!=8883 or manifest.get('synthetic_source') is not True
            or '-DMP_H3_TEST_SOURCE' not in flags or '-DMP_H3_PERSISTENT_CONFIG' not in flags
            or any(f.startswith('-DMP_MQTT_TLS_PORT=') and f!='-DMP_MQTT_TLS_PORT=8883' for f in flags)):
            raise GateError('FORMAL_8883_SYNTHETIC_PROFILE_REQUIRED')
    else:raise GateError('UNKNOWN_DOWNLOAD_PROFILE')
    p=manifest.get('persistent_config',{})
    if (p.get('address'),p.get('sector'),p.get('record_bytes'),p.get('erase_bytes'),p.get('runtime_flash_writes'))!=(CONFIG,3,336,0x4000,False):
        raise GateError('PERSISTENT_PROFILE_REQUIRED')
    if manifest.get('volatile_config') or not 148<=len(image)<=CONFIG-START:raise GateError('APPLICATION_RANGE')
    plan=manifest['image']
    if (plan['start'],plan['end_exclusive'],plan['bytes'],plan['sha256'],plan['erase_sectors'])!=(START,START+len(image),len(image),sha(image),[0,1,2]):
        raise GateError('IMAGE_MANIFEST_MISMATCH')
    sp,reset=struct.unpack_from('<II',image)
    vector=struct.unpack_from('<I',image,36*4)[0]
    if sp!=0x20020000 or plan['initial_sp']!=sp or not reset&1 or not START<=reset-1<START+len(image) or plan['reset_vector']!=reset:
        raise GateError('APPLICATION_VECTOR')
    irq=plan.get('CAN1_RX0_vector',{})
    if not irq.get('strong_handler') or irq.get('address')!=vector or not vector&1 or not START<=vector-1<START+len(image):
        raise GateError('IRQ_VECTOR')
    if plan.get('protected_sectors')!=[7,11] or plan.get('mass_erase') is not False or plan.get('option_bytes_write') is not False:
        raise GateError('PROTECTION_PLAN')
    for segment in plan.get('load_segments',[]):
        if not START<=segment['start']<segment['end_exclusive']<=START+len(image):raise GateError('LOAD_SEGMENT_RANGE')
    return {'role':'C','port':'COM15','image_sha256':sha(image),'image_bytes':len(image),
            'record_sha256':sha(record),'record_bytes':336,'application_sectors':[0,1,2],
            'config_sector':3,'config_erase_bytes':0x4000,'backup_bytes':SPAN,
            'commit_written_last':True,'ram_injection':False,'automatic_go':False,
            'protected_sectors':[7,11],'option_bytes_write':False,
            'mqtt_tls_port':8883 if profile=='formal-synthetic' else 8884,'profile':profile}


def protection(boot,baseline):
    options=read_exact(boot,0x1FFFC000,16)
    if options[1]!=0xAA or sha(options)!=baseline['options_sha256']:raise GateError('OPTIONS_BASELINE_CHANGED')
    if protected_hashes(boot)!=baseline['protected']:raise GateError('PROTECTED_BASELINE_CHANGED')
    return options


def capture_backup(boot,previous,private,identity_sha):
    """原件逐次读回，保护区不变后才独占落盘；失败不生成可用backup证明。"""
    if previous.get('role')!='C' or previous.get('exit_code')!=0 or not previous.get('image_readback_match') or not previous.get('protected_unchanged') or not previous.get('options_unchanged'):
        raise GateError('PREVIOUS_RECEIPT_REQUIRED')
    expected={'protected':previous['protected_after'],'options_sha256':previous['options_sha256']}
    protection(boot,expected)
    first=read_exact(boot,START,SPAN);second=read_exact(boot,START,SPAN)
    n=previous['image']['bytes']
    if not 8<=n<=CONFIG-START or sha(first[:n])!=previous['image']['sha256']:raise GateError('CURRENT_APPLICATION_MISMATCH')
    if first!=second:raise GateError('BACKUP_READS_DIFFER')
    protection(boot,expected)
    import os
    for name,data in (('c-sector0-3-first.bin',first),('c-sector0-3-second.bin',second)):
        fd=os.open(private/name,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
        with os.fdopen(fd,'wb') as f:f.write(data)
    # 读取磁盘原件而非只相信write成功；不输出任何配置内容/UID。
    if any((private/name).read_bytes()!=first for name in ('c-sector0-3-first.bin','c-sector0-3-second.bin')):
        raise GateError('BACKUP_DISK_READBACK_FAILED')
    return {**expected,'exit_code':0,'double_read_match':True,'bytes':SPAN,'sha256':sha(first),
            'identity_source_sha256':identity_sha,'private_files':['c-sector0-3-first.bin','c-sector0-3-second.bin']}


def checked_backup(baseline,backup):
    if baseline.get('exit_code')!=0 or baseline.get('double_read_match') is not True or baseline.get('bytes')!=SPAN or len(backup)!=SPAN or sha(backup)!=baseline.get('sha256'):
        raise GateError('WINDOW_BACKUP_REQUIRED')


def wifi_plan(manifest,image,old_record,record):
    """换网只允许两段Wi-Fi字段及递增代次变化，禁止顺带改MQTT身份或授时下限。"""
    plan=offline_plan(manifest,image,record)
    old_generation=validate(old_record);new_generation=validate(record)
    if new_generation!=old_generation+1:raise GateError('WIFI_GENERATION_SEQUENCE')
    before=old_record[24:];after=record[24:]
    if before[:8]!=after[:8] or before[106:]!=after[106:] or before[8:106]==after[8:106]:
        raise GateError('WIFI_ONLY_CHANGE_REQUIRED')
    return {**plan,'previous_record_sha256':sha(old_record),'erase_sectors':[3],
            'application_written':False,'generation':new_generation,
            'expected_previous_flash_sha256':sha(image.ljust(CONFIG-START,b'\xff')+old_record.ljust(0x4000,b'\xff'))}


def capture_wifi_backup(boot,plan,previous,private,identity_sha):
    # 上一窗口保护区摘要只作身份基线；这次换网回退原件必须重新从板上双读，不能复用首次烧录前的旧应用。
    expected={'protected':previous['protected'],'options_sha256':previous['options_sha256']}
    protection(boot,expected)
    first=read_exact(boot,START,SPAN);second=read_exact(boot,START,SPAN)
    if first!=second:raise GateError('BACKUP_READS_DIFFER')
    if sha(first)!=plan['expected_previous_flash_sha256']:raise GateError('CURRENT_WIFI_BASELINE_MISMATCH')
    protection(boot,expected)
    import os
    for name in ('c-sector0-3-first.bin','c-sector0-3-second.bin'):
        fd=os.open(private/name,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
        with os.fdopen(fd,'wb') as f:f.write(first)
    if any((private/name).read_bytes()!=first for name in ('c-sector0-3-first.bin','c-sector0-3-second.bin')):
        raise GateError('BACKUP_DISK_READBACK_FAILED')
    return {**expected,'exit_code':0,'double_read_match':True,'bytes':SPAN,'sha256':sha(first),
            'identity_source_sha256':identity_sha,'private_files':['c-sector0-3-first.bin','c-sector0-3-second.bin']}


def write_wifi_sector(boot,record,application,baseline,progress):
    """更新和失败恢复共用sector3事务；整应用区仅校验，不发任何应用擦写指令。"""
    validate(record)
    if not boot.extended_erase:raise GateError('EXTENDED_ERASE_REQUIRED')
    protection(boot,baseline)
    if read_exact(boot,START,CONFIG-START)!=application:raise GateError('WIFI_APPLICATION_CHANGED')
    progress('ERASE_WIFI_SECTOR3',{'flash_write_started':True,'application_written':False})
    boot.extended_erase_memory([3])
    boot.write_memory_data(CONFIG,record[:20]);boot.write_memory_data(CONFIG+24,record[24:])
    pending=record[:20]+b'\xff'*4+record[24:]
    if read_exact(boot,CONFIG,0x4000)!=pending.ljust(0x4000,b'\xff'):raise GateError('CONFIG_PENDING_READBACK_FAILED')
    boot.write_memory_data(CONFIG+20,record[20:24])
    expected=application+record.ljust(0x4000,b'\xff')
    if read_exact(boot,START,SPAN)!=expected:raise GateError('FINAL_64K_READBACK_FAILED')
    protection(boot,baseline)
    return {'exit_code':0,'flash_readback_sha256':sha(expected),'application_unchanged':True,
            'config_readback_match':True,'protected_unchanged':True,'options_unchanged':True,
            'automatic_go':False,'physical_cold_boot':'NOT_TESTED'}


def update_wifi(boot,manifest,image,old_record,record,baseline,backup,progress):
    plan=wifi_plan(manifest,image,old_record,record);checked_backup(baseline,backup)
    if sha(backup)!=plan['expected_previous_flash_sha256']:raise GateError('WIFI_WINDOW_BACKUP_MISMATCH')
    if read_exact(boot,START,SPAN)!=backup:raise GateError('CURRENT_64K_CHANGED')
    return write_wifi_sector(boot,record,backup[:CONFIG-START],baseline,progress)


def restore_wifi(boot,baseline,backup,current_sha,progress):
    checked_backup(baseline,backup)
    # 即使更新中途失败，也必须先知道当前完整摘要并双读一致；保护区或应用有变化时拒绝恢复。
    record=backup[CONFIG-START:CONFIG-START+336];validate(record)
    if backup[CONFIG-START+336:]!=b'\xff'*(0x4000-336):raise GateError('WIFI_BACKUP_PADDING')
    first=read_exact(boot,START,SPAN);second=read_exact(boot,START,SPAN)
    if first!=second or sha(first)!=current_sha:raise GateError('RESTORE_CURRENT_64K_MISMATCH')
    result=write_wifi_sector(boot,record,backup[:CONFIG-START],baseline,progress)
    return {**result,'restore_readback_match':True,'restored_sha256':sha(backup)}


def program(boot,manifest,image,record,baseline,backup,progress,profile='isolated'):
    offline_plan(manifest,image,record,profile);checked_backup(baseline,backup)
    if not boot.extended_erase:raise GateError('EXTENDED_ERASE_REQUIRED')
    protection(boot,baseline)
    if read_exact(boot,START,SPAN)!=backup:raise GateError('CURRENT_64K_CHANGED')
    application=image.ljust(CONFIG-START,b'\xff')
    # 第一条写指令前，原件和保护区已经齐备；从此失败只停止，不自动重试或跳转。
    progress('ERASE_APPLICATION',{'flash_write_started':True})
    boot.extended_erase_memory([0,1,2]);boot.write_memory_data(START,image+b'\xff'*((-len(image))%4))
    if read_exact(boot,START,CONFIG-START)!=application:raise GateError('APPLICATION_READBACK_FAILED')
    protection(boot,baseline)
    progress('ERASE_CONFIG_SECTOR3',{'application_readback_match':True})
    boot.extended_erase_memory([3])
    # commit位20..23保持擦除态，先写header/CRC和payload，整扇区核对后才提交。
    boot.write_memory_data(CONFIG,record[:20]);boot.write_memory_data(CONFIG+24,record[24:])
    pending=record[:20]+b'\xff'*4+record[24:]
    if read_exact(boot,CONFIG,0x4000)!=pending.ljust(0x4000,b'\xff'):raise GateError('CONFIG_PENDING_READBACK_FAILED')
    boot.write_memory_data(CONFIG+20,record[20:24])
    expected=application+record.ljust(0x4000,b'\xff')
    if read_exact(boot,START,SPAN)!=expected:raise GateError('FINAL_64K_READBACK_FAILED')
    protection(boot,baseline)
    progress('COMMITTED_READBACK_VERIFIED',{'config_readback_match':True,'protected_unchanged':True,'options_unchanged':True})
    return {'exit_code':0,'flash_readback_sha256':sha(expected),'automatic_go':False,'physical_cold_boot':'NOT_TESTED'}


def restore(boot,baseline,backup,current_sha,progress):
    checked_backup(baseline,backup)
    if not boot.extended_erase:raise GateError('EXTENDED_ERASE_REQUIRED')
    protection(boot,baseline)
    first=read_exact(boot,START,SPAN);second=read_exact(boot,START,SPAN)
    if first!=second or sha(first)!=current_sha:raise GateError('RESTORE_CURRENT_64K_MISMATCH')
    progress('RESTORE_WINDOW_BACKUP',{'flash_write_started':True})
    boot.extended_erase_memory([0,1,2,3]);boot.write_memory_data(START,backup)
    if read_exact(boot,START,SPAN)!=backup:raise GateError('RESTORE_READBACK_FAILED')
    protection(boot,baseline)
    return {'exit_code':0,'restored_sha256':sha(backup),'restore_readback_match':True,'automatic_go':False,'cold_boot':'NOT_TESTED'}


def check_window(window,action,plan,commit,identity_sha):
    # 文件只记录已在会话取得的许可，不能替代负责人授权；过期/别的板卡或范围一律拒绝。
    try:expires=datetime.fromisoformat(window['expires_utc'])
    except (KeyError,ValueError,TypeError):raise GateError('OWNER_WINDOW_EXPIRY_REQUIRED')
    if expires.tzinfo is None or expires<=datetime.now(timezone.utc):raise GateError('OWNER_WINDOW_EXPIRED')
    if window.get('role')!='C' or window.get('port')!='COM15' or window.get('source_commit')!=commit or action not in window.get('actions',[]):
        raise GateError('OWNER_WINDOW_SCOPE')
    wifi_action=action.startswith('wifi-')
    if window.get('erase_sectors')!=([3] if wifi_action else [0,1,2,3]) or window.get('image_sha256')!=plan['image_sha256'] or window.get('record_sha256')!=plan['record_sha256']:
        raise GateError('OWNER_WINDOW_IMAGE_CONFIG_SCOPE')
    if wifi_action and window.get('previous_record_sha256')!=plan.get('previous_record_sha256'):
        raise GateError('OWNER_WINDOW_PREVIOUS_CONFIG_SCOPE')
    if window.get('identity_source_sha256')!=identity_sha or window.get('mqtt_tls_port')!=plan.get('mqtt_tls_port',8884):
        raise GateError('OWNER_WINDOW_IDENTITY_NETWORK_SCOPE')


def verify_sources(manifest,commit,sdk):
    if subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()!=commit:raise GateError('SOURCE_COMMIT_CHANGED')
    paths=['gateway/physical_can','gateway/mqtt']
    if subprocess.run(['git','diff','--quiet','HEAD','--',*paths],cwd=ROOT).returncode:raise GateError('UNCOMMITTED_DOWNLOAD_CODE')
    for group in ('source_sha256','build_input_sha256'):
        if not manifest.get(group):raise GateError('BUILD_INPUTS_REQUIRED')
        for name,digest in manifest[group].items():
            external=name.startswith('external-sdk/')
            if external and sdk is None:raise GateError('EXTERNAL_SDK_ROOT_REQUIRED')
            parent=sdk.resolve() if external else ROOT
            path=(parent/(name[len('external-sdk/'):] if external else name)).resolve()
            if not path.is_relative_to(parent) or sha(path.read_bytes())!=digest:raise GateError('BUILD_INPUT_CHANGED')


def synchronize_ready_rom(uart,boot,reset_connection=None):
    # CH340打开可能释放NRST；复用旧工具的稳定等待，不能紧接open发送自动波特率字节。
    # 仅清空Host输入缓冲，再发同步字；不改变BOOT/复位电平、不清设备错误计数。
    from gateway.physical_can.h3_flash_c import synchronize_manual_rom
    if reset_connection is not None:
        # 仅显式C复位选项使用既有极性；不操作BOOT线，不把ROM复位当正常冷启动。
        reset_connection.enable_reset(True)
        time.sleep(.1)
        reset_connection.enable_reset(False)
    time.sleep(.3)
    uart.reset_input_buffer()
    synchronize_manual_rom(uart)
    boot.get()


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--action',choices=('plan','backup','program','restore','wifi-plan','wifi-backup','wifi-update','wifi-restore'),default='plan')
    parser.add_argument('--profile',choices=('isolated','formal-synthetic'),default='isolated')
    for flag in ('manifest','image','record'):parser.add_argument('--'+flag,type=Path,required=True)
    for flag in ('owner-window','private-dir','identity-source','previous-receipt','baseline','sdk-root','previous-record','previous-baseline'):
        parser.add_argument('--'+flag,type=Path)
    parser.add_argument('--commit');parser.add_argument('--expected-current-sha256')
    parser.add_argument('--reset-c',action='store_true')
    args=parser.parse_args();uart=None;capture=io.StringIO()
    result={'role':'C','exit_code':1,'action':args.action,'flash_write_started':False,'hardware_accessed':False}
    receipt=None
    try:
        if args.record.resolve().is_relative_to(ROOT):raise GateError('EXTERNAL_RECORD_REQUIRED')
        manifest=json.loads(args.manifest.read_text());image=args.image.read_bytes();record=args.record.read_bytes()
        wifi_action=args.action.startswith('wifi-')
        # 已有换网事务继续限定原隔离配置，正式身份切换不能伪装成仅Wi-Fi字段更新。
        if wifi_action and args.profile!='isolated':raise GateError('WIFI_ISOLATED_PROFILE_REQUIRED')
        if wifi_action:
            if not args.previous_record or args.previous_record.resolve().is_relative_to(ROOT):raise GateError('EXTERNAL_PREVIOUS_RECORD_REQUIRED')
            old_record=args.previous_record.read_bytes();plan=wifi_plan(manifest,image,old_record,record)
        else:plan=offline_plan(manifest,image,record,args.profile)
        result['plan']=plan
        if args.action in ('plan','wifi-plan'):
            result.update(exit_code=0,physical_actions_authorized=False);print(json.dumps(result));return 0
        if not all((args.owner_window,args.private_dir,args.identity_source,args.commit)):raise GateError('SEPARATE_OWNER_WINDOW_REQUIRED')
        for path in (args.owner_window,args.private_dir,args.identity_source,args.baseline,args.previous_baseline):
            if path and path.resolve().is_relative_to(ROOT):raise GateError('PRIVATE_PATH_REQUIRED')
        window=json.loads(args.owner_window.read_text())
        check_window(window,args.action,plan,args.commit,sha(args.identity_source.read_bytes()))
        if args.reset_c and not window.get('controlled_c_rom_reset'):raise GateError('EXPLICIT_C_RESET_WINDOW_REQUIRED')
        verify_sources(manifest,args.commit,args.sdk_root)
        if not args.private_dir.is_dir():raise GateError('PRIVATE_DIRECTORY_REQUIRED')
        if args.action in ('backup','wifi-backup'):
            if args.baseline or not (args.previous_baseline if wifi_action else args.previous_receipt):raise GateError('BACKUP_PREVIOUS_RECEIPT_REQUIRED')
            if any((args.private_dir/n).exists() for n in ('baseline.json','c-sector0-3-first.bin','c-sector0-3-second.bin')):raise GateError('BACKUP_DESTINATION_OCCUPIED')
            previous=json.loads((args.previous_baseline if wifi_action else args.previous_receipt).read_text())
            if wifi_action and previous.get('identity_source_sha256')!=sha(args.identity_source.read_bytes()):raise GateError('BACKUP_DEVICE_IDENTITY_CHANGED')
        else:
            if not args.baseline:raise GateError('WINDOW_BASELINE_REQUIRED')
            baseline=json.loads(args.baseline.read_text())
            if baseline['identity_source_sha256']!=sha(args.identity_source.read_bytes()):raise GateError('BACKUP_DEVICE_IDENTITY_CHANGED')
            backup=(args.baseline.parent/'c-sector0-3-first.bin').read_bytes();checked_backup(baseline,backup)
            if wifi_action and sha(backup)!=plan['expected_previous_flash_sha256']:raise GateError('WIFI_WINDOW_BACKUP_MISMATCH')
            if (args.baseline.parent/'c-sector0-3-second.bin').read_bytes()!=backup:raise GateError('SECOND_BACKUP_CHANGED')
            if args.action in ('restore','wifi-restore') and not args.expected_current_sha256:raise GateError('RESTORE_CURRENT_SHA_REQUIRED')
        stamp=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
        receipt=args.private_dir/('r2-c-'+args.action+'-'+stamp+'.json')
        def progress(stage,fields):
            result.update(stage=stage,**fields);receipt.write_text(json.dumps(result,indent=2))
        from importlib.metadata import version
        if version('stm32loader')!='0.7.1':raise GateError('LOADER_VERSION_CHANGED')
        identity=external_identity(args.identity_source)
        import serial
        from stm32loader.uart import SerialConnection
        from stm32loader.bootloader import Stm32Bootloader
        # 默认仅同步手动ROM；显式复位也只作用C，结束不GO、不改变BOOT接线。
        with redirect_stdout(capture),redirect_stderr(capture):
            uart=serial.Serial(port=None,baudrate=115200,parity='E',timeout=2,write_timeout=2)
            uart.dtr=True;uart.rts=True;uart.port='COM15';result['hardware_accessed']=True;uart.open()
            connection=SerialConnection('COM15',115200,'E');connection.serial_connection=uart
            connection.reset_active_high=True;connection.boot0_active_low=True
            boot=Stm32Bootloader(connection,device_family='F4',verbosity=0)
            result['controlled_c_reset_requested']=args.reset_c
            synchronize_ready_rom(uart,boot,connection if args.reset_c else None);verify_f4_identity(boot,identity)
            if args.action in ('backup','wifi-backup'):
                value=(capture_wifi_backup(boot,plan,previous,args.private_dir,sha(args.identity_source.read_bytes())) if wifi_action
                       else capture_backup(boot,previous,args.private_dir,sha(args.identity_source.read_bytes())))
                with (args.private_dir/'baseline.json').open('x') as f:json.dump(value,f,indent=2)
                result['backup']={k:v for k,v in value.items() if k!='private_files'}
            elif args.action=='program':result.update(program(boot,manifest,image,record,baseline,backup,progress,args.profile))
            elif args.action=='wifi-update':result.update(update_wifi(boot,manifest,image,old_record,record,baseline,backup,progress))
            elif args.action=='wifi-restore':result.update(restore_wifi(boot,baseline,backup,args.expected_current_sha256,progress))
            else:result.update(restore(boot,baseline,backup,args.expected_current_sha256,progress))
        result.update(exit_code=0,automatic_go=False,physical_cold_boot='NOT_TESTED')
    except BaseException as exc:
        result.update(exit_code=1,failure_code=str(exc) if isinstance(exc,(GateError,RecordError)) else type(exc).__name__)
    finally:
        if uart is not None:
            try:uart.close()
            except Exception:result.update(exit_code=1,close_failed=True)
        # 低层输出可能含UID/凭据，完全丢弃；只保存固定状态码和散列。
        if receipt:receipt.write_text(json.dumps(result,indent=2))
    print(json.dumps(result));return result['exit_code']


if __name__=='__main__':raise SystemExit(main())
