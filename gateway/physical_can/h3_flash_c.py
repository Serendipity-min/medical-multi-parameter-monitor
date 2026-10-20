"""H3隔离候选受限下载：只擦应用0..2，配置只入RAM，保护7/11及选项字节。"""
import argparse
from contextlib import redirect_stderr,redirect_stdout
from datetime import datetime,timezone
import hashlib
import io
import json
from pathlib import Path
import subprocess
import sys
import time

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
from gateway.physical_can.bench.flash_c import (GateError,external_identity,verify_f4_identity,
                                               read_exact,protected_hashes)
PRIVATE=Path('E:/medical-monitor-h3-private')
START=0x08000000


def sha(data):return hashlib.sha256(data).hexdigest()


def verify_plan(manifest,image,config):
    plan=manifest['image']
    if manifest.get('exit_code')!=0 or manifest.get('feature')!='H3_NETWORK_IRQ':raise GateError('UNVERIFIED_ARM')
    if manifest.get('volatile_config')!={'address':0x2001FE00,'bytes':312,'reserved_bytes':512,'flash_configuration_written':False}:raise GateError('VOLATILE_CONFIG_NOT_RESERVED')
    if plan['erase_sectors']!=[0,1,2] or not 0<len(image)<=0xC000:raise GateError('APPLICATION_RANGE_CHANGED')
    if plan['start']!=START or plan['end_exclusive']!=START+len(image) or sha(image)!=plan['sha256']:raise GateError('IMAGE_MISMATCH')
    if int.from_bytes(image[:4],'little')!=0x2001FE00 or not plan['CAN1_RX0_vector']['strong_handler']:raise GateError('VECTOR_MISMATCH')
    if len(config)!=312 or int.from_bytes(config[:4],'little')!=0x31435747:raise GateError('VOLATILE_CONFIG_FORMAT')
    if not time.time()-172800 <= int.from_bytes(config[4:8],'little') <= time.time()+3600:raise GateError('VOLATILE_TIME_FLOOR_STALE')
    offset=8
    for size in (33,65,65,33,65,41):
        value=config[offset:offset+size];offset+=size
        if value[-1] or not value[0] or any(c in value.split(b'\0')[0] for c in (b'"',b'\\',b'\r',b'\n')):raise GateError('VOLATILE_CONFIG_FIELD')
    return plan


def program(boot,image,plan,config,baseline,backup,progress,current_application=None):
    # 所有只读身份/原件/保护摘要验证通过后，才发第一条擦除命令。
    if not boot.extended_erase:raise GateError('EXTENDED_ERASE_REQUIRED')
    options=read_exact(boot,0x1FFFC000,16)
    if options[1]!=0xAA or sha(options)!=baseline['options_sha256']:raise GateError('OPTION_BASELINE_CHANGED')
    before=protected_hashes(boot)
    if before!=baseline['protected']:raise GateError('PROTECTED_BASELINE_CHANGED')
    expected=backup if current_application is None else current_application
    if read_exact(boot,START,len(expected))!=expected:raise GateError('EXPECTED_CURRENT_APPLICATION_DOES_NOT_MATCH_BOARD')
    progress('ERASE_APPLICATION_0_1_2',{'flash_write_started':True})
    boot.extended_erase_memory([0,1,2])
    padded=image+b'\xff'*((-len(image))%4)
    boot.write_memory_data(START,padded)
    if read_exact(boot,START,len(padded))!=padded:raise GateError('APPLICATION_READBACK_FAILED')
    after=protected_hashes(boot)
    if after!=before:raise GateError('PROTECTED_CHANGED_STOP')
    if read_exact(boot,0x1FFFC000,16)!=options:raise GateError('OPTIONS_CHANGED_STOP')
    progress('APPLICATION_VERIFIED_INJECT_RAM_CONFIG',{'image_readback_match':True,'protected_unchanged':True,'options_unchanged':True})
    boot.write_memory_data(0x2001FE00,config)
    if read_exact(boot,0x2001FE00,len(config))!=config:raise GateError('RAM_CONFIG_READBACK_FAILED')
    return {'protected_before':before,'protected_after':after,'options_sha256':sha(options),
            'configuration_flash_written':False,'volatile_config_readback_match':True}


def restore_application(boot,baseline,backup,current,progress):
    """同一C的受限原件回写与读回；任何检查失败都不继续重试/重刷。"""
    options=read_exact(boot,0x1FFFC000,16)
    if options[1]!=0xAA or sha(options)!=baseline['options_sha256']:raise GateError('ROLLBACK_OPTIONS_CHANGED')
    if protected_hashes(boot)!=baseline['protected']:raise GateError('ROLLBACK_PROTECTED_CHANGED')
    if not boot.extended_erase or read_exact(boot,START,len(current))!=current:raise GateError('ROLLBACK_CURRENT_IMAGE_MISMATCH')
    progress('VERIFY_APPLICATION_ROLLBACK_0_1_2',{'rollback_write_started':True})
    boot.extended_erase_memory([0,1,2]);boot.write_memory_data(START,backup)
    if read_exact(boot,START,len(backup))!=backup:raise GateError('ROLLBACK_READBACK_FAILED_STOP')
    if protected_hashes(boot)!=baseline['protected'] or read_exact(boot,0x1FFFC000,16)!=options:raise GateError('ROLLBACK_PROTECTION_FAILED_STOP')
    return {'application_rollback_readback_verified':True,'rollback_sectors':[0,1,2],
            'rollback_bytes':len(backup),'rollback_sha256':sha(backup),'rollback_application_executed':False}


def read_current_candidate(boot,receipt,destination):
    """本地旧候选未保留时，只读原板并按既有回读回执验证，不能把未知镜像当原件。"""
    if not destination.resolve().is_relative_to(PRIVATE.resolve()) or destination.exists():
        raise GateError('CURRENT_READ_REQUIRES_NEW_PRIVATE_FILE')
    size=receipt['image']['bytes']
    if not 8<=size<=0xC000:raise GateError('CURRENT_READ_RANGE')
    current=read_exact(boot,START,size)
    if sha(current)!=receipt['image']['sha256']:raise GateError('CURRENT_READ_RECEIPT_MISMATCH')
    with destination.open('xb') as output:output.write(current)
    return current


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--commit',required=True);parser.add_argument('--preflight',type=Path,required=True)
    parser.add_argument('--config',type=Path,required=True)
    parser.add_argument('--current-receipt',type=Path);parser.add_argument('--current-image',type=Path)
    parser.add_argument('--read-current-image',action='store_true')
    parser.add_argument('--verify-rollback-first',action='store_true')
    parser.add_argument('--observe-seconds',type=int,default=0);args=parser.parse_args()
    if not 0<=args.observe_seconds<=1800:parser.error('observe range 0..1800')
    stamp=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    target=ROOT/'gateway/physical_can/evidence/h3'/('c-download-'+stamp+'.json')
    result={'role':'C','port':'COM15','action':'H3_ISOLATED_NETWORK_DOWNLOAD','exit_code':1,'flash_write_started':False}
    connection=None;capture=io.StringIO()

    def progress(stage,details):
        result.update(stage=stage,**details)
        target.write_text(json.dumps(result,indent=2),encoding='utf-8')

    try:
        if subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()!=args.commit:raise GateError('COMMIT_CHANGED')
        if subprocess.run(['git','diff','--quiet','HEAD','--','gateway/physical_can','gateway/mqtt'],cwd=ROOT).returncode:raise GateError('UNCOMMITTED_FIRMWARE')
        manifest=json.loads((ROOT/'gateway/physical_can/evidence/h3/isolated-arm-result.json').read_text())
        for group in ('source_sha256','build_input_sha256'):
            for name,digest in manifest[group].items():
                if not name.startswith('external-sdk/') and sha((ROOT/name).read_bytes())!=digest:raise GateError('BUILD_INPUT_CHANGED')
        image=(ROOT/'gateway/physical_can/build/h3-isolated/gateway_physical_can.bin').read_bytes()
        if args.config.resolve().is_relative_to(ROOT):raise GateError('CONFIG_MUST_BE_EXTERNAL')
        config=args.config.read_bytes();plan=verify_plan(manifest,image,config)
        baseline=json.loads(args.preflight.read_text())
        if baseline.get('exit_code')!=0 or not baseline.get('C_identity_match'):raise GateError('PREFLIGHT_NOT_VERIFIED')
        name=baseline['application_backup']['private_file']
        if Path(name).name!=name:raise GateError('BACKUP_PATH')
        backup=(PRIVATE/name).read_bytes()
        if sha(backup)!=baseline['application_backup']['sha256'] or len(backup)!=0xC000:raise GateError('BACKUP_BYTES_CHANGED')
        current_application=None;receipt=None
        if args.read_current_image and not (args.current_receipt and args.current_image):raise GateError('CURRENT_READ_RECEIPT_REQUIRED')
        if args.current_receipt or args.current_image:
            if not args.current_receipt or not args.current_image:raise GateError('CURRENT_IMAGE_AND_RECEIPT_REQUIRED')
            receipt=json.loads(args.current_receipt.read_text())
            # 只接受本轮已经回读验证且保护区未变的候选，原H2R恢复原件仍须保留。
            if not receipt.get('image_readback_match') or not receipt.get('protected_unchanged') or not receipt.get('options_unchanged') or receipt.get('protected_after')!=baseline['protected']:raise GateError('CURRENT_RECEIPT_NOT_VERIFIED')
            if not args.read_current_image:
                current_application=args.current_image.read_bytes()
                if sha(current_application)!=receipt['image']['sha256']:raise GateError('CURRENT_CANDIDATE_BYTES_CHANGED')
            result['previous_candidate_sha256']=receipt['image']['sha256']
        a=Path('E:/medical-monitor-node-a-handoff/h2-private/a-backup-20261019T074319128346Z')
        for name in ('flash-first.bin','flash-second.bin'):
            if sha((a/name).read_bytes())!='0fd4a4e8417b87a157fdf3e4f7c5a2a553c5aa9f69b4417fcac03c3a73d91516':raise GateError('A_ORIGINAL_BACKUP_CHANGED')
        result.update(source_commit=args.commit,image=plan,volatile_config_sha256=sha(config),A_original_backup_verified=True)
        from stm32loader.uart import SerialConnection
        from stm32loader.bootloader import Stm32Bootloader
        identity=external_identity(Path('E:/stm32/ai_serial_console/tools/flash.py'))
        connection=SerialConnection('COM15',115200,'E');connection.reset_active_high=True;connection.boot0_active_low=True
        with redirect_stdout(capture),redirect_stderr(capture):
            progress('CONNECT_ROM',{});connection.connect();boot=Stm32Bootloader(connection,device_family='F4',verbosity=0)
            boot.reset_from_system_memory();boot.get();verify_f4_identity(boot,identity)
            result['C_identity_match']=True
            if args.read_current_image:
                # 此处只读+保存；后续program仍会重核保护区/选项字节及当前应用，才允许擦除。
                current_application=read_current_candidate(boot,receipt,args.current_image)
                result['current_candidate_readback_verified']=True
            if args.verify_rollback_first:
                if current_application is None:raise GateError('ROLLBACK_REQUIRES_VERIFIED_CURRENT_CANDIDATE')
                result.update(restore_application(boot,baseline,backup,current_application,progress))
                current_application=None
                progress('ROLLBACK_VERIFIED_APPLY_FIXED_CANDIDATE',{'application_rollback_readback_verified':True})
            result.update(program(boot,image,plan,config,baseline,backup,progress,current_application))
            # ROM标准GO执行经核验应用向量，不向A写PC/MSP/VTOR，也不跳过C的启动代码。
            progress('GO_STANDARD_APPLICATION_VECTOR',{})
            boot.go(START)
            connection.serial_connection.parity='N'
            connection.serial_connection.timeout=.1;connection.serial_connection.write_timeout=1
            time.sleep(.3)
            raw=connection.serial_connection.read(connection.serial_connection.in_waiting)
            result['boot_wait_marker_seen']=b'GW WAIT_NODE_A_FIRST_HEARTBEAT' in raw
            capture.write('\nAPPLICATION_BOOT_OUTPUT_BYTES='+str(len(raw)))
            if args.observe_seconds:
                # 保持同一串口句柄，避免CH340关闭/重开时的DTR/RTS跳变误复位C。
                from gateway.physical_can.h3_observe import observe
                progress('CAPTURING_UART_WAIT_NODE_A',{'download_verified':True,'go_sent':True})
                result['observation_exit_code']=observe(connection.serial_connection,args.observe_seconds,PRIVATE,raw)
        result.update(exit_code=0,stage='APPLICATION_VERIFIED_RAM_CONFIG_ONLY_GO_SENT',physical_CAN='NOT_ACCEPTED',C_full_flash_backup=False)
    except BaseException as exc:
        result['failure_type']=type(exc).__name__
        if isinstance(exc,GateError):result['failure_code']=str(exc)
        capture.write('\n'+repr(exc))
    finally:
        if connection and connection.serial_connection:connection.serial_connection.close()
        (PRIVATE/('c-download-'+stamp+'.raw.log')).write_text(capture.getvalue(),encoding='utf-8')
        target.write_text(json.dumps(result,indent=2),encoding='utf-8');print(json.dumps(result,indent=2))
    return result['exit_code']


if __name__=='__main__':raise SystemExit(main())
