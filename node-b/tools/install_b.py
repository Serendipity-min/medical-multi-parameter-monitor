"""仅允许本次已备份B板sector0/1的固定BIO_V2候选下载与全片核验。"""
import argparse
import ctypes as C
import datetime as dt
import hashlib
import json
from pathlib import Path
import sys
import time
from readback_b import Link, PRIVATE, HALT, RESET, LOCKUP, require, sha, write_json, identity, check_identity

CANDIDATE = '438a8120f6df06ce219cdc30c0e5b697ac0e993f98d5a80521b10361536ae3ae'
ORIGINAL = '69d9efb0ce0a9228138ea3cc21adbb09c09a15a8b6dbf0d9a1d1ff861a32fc2a'
ROOT = Path(__file__).resolve().parents[2]


def prepare(binary, backup, out):
    image, original = binary.read_bytes(), (backup/'flash-read-1.bin').read_bytes()
    require(len(image) == 25284 and sha(binary) == CANDIDATE, 'CANDIDATE_IDENTITY')
    require(len(original) == 1048576 and sha(backup/'flash-read-1.bin') == ORIGINAL, 'BACKUP_IDENTITY')
    require(original == (backup/'flash-read-2.bin').read_bytes(), 'BACKUP_DOUBLE_READ')
    out.mkdir(exist_ok=False)
    # 原BIN外的扇区尾部保持当次原件，不能用FF填满扇区；整个其余Flash同样保持。
    expected = image+original[len(image):]
    for name, data in [('candidate-sectors0-1.bin', expected[:32768]),
                        ('rollback-sectors0-1.bin', original[:32768]),
                        ('expected-full-flash.bin', expected)]:
        with (out/name).open('xb') as f:f.write(data)
    plan = {'candidate_bin_sha256': CANDIDATE, 'original_flash_sha256': ORIGINAL,
            'expected_full_flash_sha256': hashlib.sha256(expected).hexdigest(),
            'program_start': 0x08000000, 'program_bytes': 32768, 'sector_ids': [0,1],
            'candidate_payload_bytes': len(image), 'preserved_sector_tail_bytes': 32768-len(image),
            'backup_directory': str(backup.resolve()),
            'identity_file_sha256': sha(backup/'identity-before-private.json'),
            'files': {n:sha(out/n) for n in ['candidate-sectors0-1.bin','rollback-sectors0-1.bin',
                                          'expected-full-flash.bin']}}
    write_json(out/'install-plan-private.json', plan)
    return plan


def install(link, folder, plan, receipt):
    backup = Path(plan['backup_directory'])
    reference = json.loads((backup/'identity-before-private.json').read_text('utf-8'))
    require(sha(backup/'identity-before-private.json') == plan['identity_file_sha256'], 'IDENTITY_FILE_DRIFT')
    for name, digest in plan['files'].items():require(sha(folder/name) == digest, 'INSTALL_FILE_DRIFT')
    require(plan['program_start'] == 0x08000000 and plan['program_bytes'] == 32768
            and plan['sector_ids'] == [0,1], 'PROGRAM_RANGE')
    require(plan['candidate_bin_sha256'] == CANDIDATE and plan['original_flash_sha256'] == ORIGINAL,
            'PLAN_IDENTITY')
    payload = (folder/'candidate-sectors0-1.bin').read_bytes()
    expected = (folder/'expected-full-flash.bin').read_bytes()
    rollback = (folder/'rollback-sectors0-1.bin').read_bytes()
    require(len(payload) == len(rollback) == 32768 and len(expected) == 1048576, 'IMAGE_LENGTH')
    require(hashlib.sha256(payload[:25284]).hexdigest() == CANDIDATE
            and payload == expected[:32768] and payload[25284:] == rollback[25284:], 'PAYLOAD_SCOPE')
    link.open()
    seen = identity(link);check_identity(seen)
    require(seen['uid_hex'] == reference['uid_hex'] and seen['optcr'] == reference['optcr'], 'WRONG_BOARD_OR_OPTIONS')
    require(link.call('JLINKARM_Halt', timeout=3) == 0, 'HALT_FAILED')
    receipt['halt_requests'] += 1
    require(link.u32(0xE000EDF0) & HALT, 'HALT_NOT_CONFIRMED')
    link.stable_halt()
    current = link.read(0x08000000,1048576)
    with (link.out/'before-install-full.bin').open('xb') as f:f.write(current)
    require(hashlib.sha256(current).hexdigest() == ORIGINAL, 'CURRENT_FLASH_DRIFT')
    # SDK只接收一个固定32KiB地址区间；不导入chip erase、option写或任意寄存器写接口。
    link.dll.JLINKARM_BeginDownload.argtypes = [C.c_uint32]
    link.dll.JLINKARM_BeginDownload.restype = None
    link.dll.JLINKARM_WriteMem.argtypes = [C.c_uint32,C.c_uint32,C.c_void_p]
    link.dll.JLINKARM_WriteMem.restype = C.c_int
    link.dll.JLINKARM_EndDownload.restype = C.c_int
    buffer = (C.c_uint8*32768).from_buffer_copy(payload)
    link.stable_halt()
    link.call('JLINKARM_BeginDownload',0)
    require(link.call('JLINKARM_WriteMem',0x08000000,32768,buffer) == 32768, 'FLASH_BUFFER_COUNT')
    receipt['flash_program_requested'] = True
    require(link.call('JLINKARM_EndDownload',timeout=45) >= 0, 'FLASH_PROGRAM_FAILED')
    require(link.u32(0xE000EDF0) & HALT, 'POST_FLASH_NOT_HALTED')
    result = link.read(0x08000000,1048576)
    with (link.out/'after-install-full.bin').open('xb') as f:f.write(result)
    require(result == expected, 'FULL_FLASH_VERIFY_MISMATCH')
    require(result[32768:] == current[32768:], 'OUTSIDE_SECTOR01_CHANGED')
    after = identity(link)
    require(after['uid_hex'] == reference['uid_hex'] and after['optcr'] == reference['optcr'], 'POST_OPTIONS_DRIFT')
    require(link.read(0x1FFFC000,16) == (backup/'options-read-1.bin').read_bytes(), 'OPTIONS_BYTES_DRIFT')
    # Flashloader结束后原PC不能直接在新代码中续跑；只有全片核验后执行一次明确复位。
    require(link.call('JLINKARM_Reset',timeout=5) == 0, 'BOOT_RESET_FAILED')
    receipt['reset_requests'] += 1
    link.call('JLINKARM_Go');receipt['go_requests'] += 1
    time.sleep(.2)
    link.u32(0xE000EDF0)  # 记录本次明确复位的粘滞位，随后再确认运行。
    require(not link.u32(0xE000EDF0) & (HALT|LOCKUP|RESET), 'CANDIDATE_NOT_RUNNING')
    receipt.update(status='BIO_V2_INSTALLED_FULL_FLASH_VERIFIED',target_end_state='RUNNING_CONFIRMED',
                   expected_flash_sha256=plan['expected_full_flash_sha256'],outside_sector01_unchanged=True,
                   options_unchanged=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--prepare',action='store_true')
    parser.add_argument('--binary',type=Path)
    parser.add_argument('--backup',type=Path)
    parser.add_argument('--plan',type=Path)
    parser.add_argument('--dll',type=Path)
    parser.add_argument('--card',type=Path)
    parser.add_argument('--card-sha256')
    parser.add_argument('--out',required=True,type=Path)
    args = parser.parse_args()
    require(args.out.resolve().is_relative_to(PRIVATE.resolve()), 'OUTPUT_NOT_RESTRICTED')
    if args.prepare:
        p=prepare(args.binary,args.backup,args.out)
        print(json.dumps({'status':'OFFLINE_INSTALL_PREPARED','expected_flash_sha256':p['expected_full_flash_sha256']}))
        return 0
    require(sha(args.card)==args.card_sha256,'CARD_SHA_MISMATCH')
    plan=json.loads(args.plan.read_text('utf-8'))
    args.out.mkdir(exist_ok=False)
    receipt={'status':'STARTED','target_end_state':'UNKNOWN','halt_requests':0,'reset_requests':0,
             'go_requests':0,'flash_program_requested':False,'card_sha256':args.card_sha256,
             'tool_sha256':sha(__file__),'started_utc':dt.datetime.now(dt.timezone.utc).isoformat()}
    link=None
    try:
        link=Link(args.dll.resolve(),args.out)
        install(link,args.plan.parent,plan,receipt)
    except BaseException as exc:
        receipt.update(status='INSTALL_STOP_OR_INCOMPLETE',error=type(exc).__name__+': '+str(exc),
                       target_end_state='UNKNOWN_NO_AUTOMATIC_RECOVERY')
    finally:
        if link:
            try:link.close()
            except BaseException as exc:receipt.update(status='INSTALL_STOP_OR_INCOMPLETE',close_error=type(exc).__name__)
        receipt['ended_utc']=dt.datetime.now(dt.timezone.utc).isoformat()
        write_json(args.out/'receipt-private.json',receipt)
    print(json.dumps({'status':receipt['status'],'error':receipt.get('error'),
                      'target_end_state':receipt['target_end_state']}))
    return 0 if receipt['status']=='BIO_V2_INSTALLED_FULL_FLASH_VERIFIED' else 1


if __name__=='__main__':sys.exit(main())
