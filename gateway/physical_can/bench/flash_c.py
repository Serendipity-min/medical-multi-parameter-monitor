"""H2 C专用：只准受核验bench镜像及sector0..3；按用户指令不备份C Flash。

只读配置摘要留在内存，绝不保存配置正文。设备UID从外部既有身份文件注入，
仅在内存比较。任何门禁失败均停止，不解除RDP、不写选项字节、不做整片擦除。
"""
import argparse
import ast
from contextlib import redirect_stdout, redirect_stderr
from datetime import datetime, timezone
import hashlib
import io
import json
from pathlib import Path
import subprocess

ROOT=Path(__file__).resolve().parents[3]
HERE=ROOT/'gateway/physical_can'
START=0x08000000
LIMIT=0x08010000
PROTECTED=((0x08060000,0x20000),(0x080E0000,0x20000))

class GateError(RuntimeError):
    """异常消息只用预定义状态码，不携带任何原始读回数据。"""

def digest(data):return hashlib.sha256(data).hexdigest()

def image_plan(image,expected):
    if not 8<=len(image)<=LIMIT-START:raise GateError('IMAGE_SIZE_OUTSIDE_APPLICATION')
    if digest(image)!=expected:raise GateError('IMAGE_SHA_MISMATCH')
    sp=int.from_bytes(image[:4],'little');reset=int.from_bytes(image[4:8],'little')
    if not (0x20000000<sp<=0x20020000 and START<reset<START+len(image) and reset&1):raise GateError('BAD_VECTORS')
    if b'CAN_ONLY_BENCH' not in image or b'OFFLINE_NO_CONFIG' not in image:raise GateError('NOT_BENCH')
    padded=image+b'\xff'*((-len(image))%4)
    sectors=list(range((len(padded)+16383)//16384))
    if not sectors or sectors[-1]>3:raise GateError('PROTECTED_SECTOR')
    return {'start':START,'end_exclusive':START+len(padded),'sectors':sectors,'bytes':len(image),'sha256':digest(image)}

def read_exact(boot,address,length):
    data=bytes(boot.read_memory_data(address,length))
    if len(data)!=length:raise GateError('READ_LENGTH_MISMATCH')
    return data

def protected_hashes(boot):
    result={}
    for address,length in PROTECTED:
        # 同时保护合同sector7及原代码宏指向sector11；不把任何原始字节写入磁盘。
        h=hashlib.sha256();prefix=bytearray()
        for offset in range(0,length,256):
            chunk=read_exact(boot,address+offset,min(256,length-offset));h.update(chunk)
            if len(prefix)<312:prefix.extend(chunk[:312-len(prefix)])
        result[hex(address)]={'sector_sha256':h.hexdigest(),'first_312B_sha256':digest(prefix)}
    return result

def program_verified(boot,image,plan,progress=None):
    progress=progress or (lambda stage,details:None)
    if image_plan(image,plan['sha256'])!=plan:raise GateError('PLAN_CHANGED')
    if not boot.extended_erase:raise GateError('EXTENDED_ERASE_UNSUPPORTED')
    options=read_exact(boot,0x40023C14,4)
    if (int.from_bytes(options,'little')>>8)&255!=0xAA:raise GateError('RDP_NOT_LEVEL_ZERO')
    before=protected_hashes(boot)
    progress('PROTECTED_HASHES_VERIFIED',{'protected_before':before})
    # 必须传非空、明确的扇区列表；库中None/空列表会触发整片擦除，绝不使用。
    progress('ERASE_ATTEMPTED',{'flash_write_started':True})
    boot.extended_erase_memory(list(plan['sectors']))
    progress('ERASE_COMPLETED',{})
    padded=image+b'\xff'*((-len(image))%4)
    boot.write_memory_data(START,padded)
    progress('PROGRAM_COMPLETED',{})
    if read_exact(boot,START,len(padded))!=padded:raise GateError('READBACK_MISMATCH')
    after=protected_hashes(boot)
    if after!=before:raise GateError('PROTECTED_DATA_CHANGED_STOP')
    if read_exact(boot,0x40023C14,4)!=options:raise GateError('OPTIONS_CHANGED_STOP')
    return {'protected_before':before,'protected_after':after,'protected_unchanged':True,'image_readback_match':True,'options_unchanged':True}

def external_identity(path):
    # literal_eval只读取声明值，不执行外部脚本，且不输出UID。
    tree=ast.parse(path.read_text(encoding='utf-8'))
    wanted={}
    for n in tree.body:
        if isinstance(n,ast.Assign):
            for target in n.targets:
                if isinstance(target,ast.Name) and target.id in ('EXPECTED_UID','EXPECTED_CHIP_ID'):
                    wanted[target.id]=ast.literal_eval(n.value)
    if set(wanted)!=set(('EXPECTED_UID','EXPECTED_CHIP_ID')):raise GateError('IDENTITY_SOURCE_INVALID')
    return wanted

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--manifest',type=Path,required=True)
    parser.add_argument('--commit',required=True);parser.add_argument('--identity-source',type=Path,required=True)
    parser.add_argument('--a-backup-dir',type=Path,required=True)
    parser.add_argument('--flash-confirm-role',choices=['C'],required=True)
    args=parser.parse_args()
    stamp=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    result={'role':'C','port':'COM15','mode':'CAN_ONLY_BENCH_USB_RANGE_DOWNLOAD','C_full_backup':'WAIVED_BY_USER','exit_code':1,'stage':'OFFLINE_GATES','flash_write_started':False}
    connection=None
    try:
        head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
        if head!=args.commit:raise GateError('SOURCE_COMMIT_CHANGED')
        manifest=json.loads(args.manifest.read_text(encoding='utf-8'))
        if manifest['mode']!='CAN_ONLY_BENCH_ARM' or manifest['exit_code']!=0:raise GateError('ARM_NOT_VERIFIED')
        for key in ('source_sha256','build_input_sha256'):
            for rel,sha in manifest[key].items():
                if not rel.startswith('external-sdk/') and digest((ROOT/rel).read_bytes())!=sha:raise GateError('SOURCE_BYTES_CHANGED')
        if subprocess.run(['git','diff','--quiet','HEAD','--','gateway/physical_can/bench','gateway/physical_can/src','gateway/physical_can/bench_build.py'],cwd=ROOT).returncode:raise GateError('UNCOMMITTED_CODE')
        image=(HERE/'build/bench/can_only_bench.bin').read_bytes();plan=image_plan(image,manifest['image']['sha256'])
        if plan['sectors']!=manifest['image']['erase_sectors']:raise GateError('ARM_SECTOR_PLAN_MISMATCH')
        proof=json.loads((args.a_backup_dir/'private-summary.json').read_text(encoding='utf-8'))
        if proof.get('exit_code')!=0 or not proof.get('independent_reads_match'):raise GateError('A_BACKUP_NOT_VERIFIED')
        for name in ('flash-first.bin','flash-second.bin'):
            if digest((args.a_backup_dir/name).read_bytes())!=proof['backup_sha256']:raise GateError('A_BACKUP_MISSING_OR_CHANGED')
        identity=external_identity(args.identity_source)
        result.update({'source_commit':head,'plan':plan,'A_backup_verified':True,'stage':'C_IDENTITY_READ_ONLY'})
        from importlib.metadata import version
        if version('stm32loader')!='0.7.1':raise GateError('LOADER_VERSION_CHANGED')
        from stm32loader.uart import SerialConnection
        from stm32loader.bootloader import Stm32Bootloader
        connection=SerialConnection('COM15',115200,'E');connection.reset_active_high=True;connection.boot0_active_low=True
        # 底层输出留在内存且丢弃，防止设备标识或原始内容进入日志。
        with redirect_stdout(io.StringIO()),redirect_stderr(io.StringIO()):
            connection.connect();boot=Stm32Bootloader(connection,device_family='F4',verbosity=0)
            boot.reset_from_system_memory();boot.get()
            if boot.get_id()!=int(identity['EXPECTED_CHIP_ID'],16) or boot.get_flash_size()!=1024:raise GateError('C_CHIP_SIZE_MISMATCH')
            if Stm32Bootloader.format_uid(boot.get_uid())!=identity['EXPECTED_UID']:raise GateError('C_UID_MISMATCH')
            result['C_identity_match']=True;result['stage']='PROTECTED_RANGE_PROGRAM'
            def progress(stage,details):result.update({'stage':stage,**details})
            result.update(program_verified(boot,image,plan,progress))
            connection.enable_reset(True)
        result.update({'exit_code':0,'stage':'VERIFIED_RESET_ASSERTED_BEFORE_CLOSE','physical_CAN':'NOT_TESTED','reset_asserted_before_port_close':True})
    except BaseException as error:
        result['failure_type']=type(error).__name__
        if isinstance(error,GateError):result['failure_code']=str(error)
    finally:
        if connection and connection.serial_connection:connection.serial_connection.close()
        # 只保存脱敏结果；没有C Flash原件/配置正文/UID，也不自动恢复运行原网关。
        (HERE/'evidence/h2'/('c-download-'+stamp+'.json')).write_text(json.dumps(result,indent=2),encoding='utf-8')
        print(json.dumps(result,indent=2))
    return result['exit_code']

if __name__=='__main__':raise SystemExit(main())
