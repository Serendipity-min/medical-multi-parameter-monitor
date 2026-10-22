"""固定候选一次复位入口核验；入口符合Flash向量才go，并检查未接源链路。"""
import argparse
import ctypes as C
import hashlib
import json
from pathlib import Path
import sys
import time
from fault_snapshot_b import FaultLink
from precheck_b import RAM, EXPECTED_FLASH, decode, assess
from readback_b import PRIVATE, HALT, LOCKUP, RESET, identity, check_identity, sha, require, write_json


class BootLink(FaultLink):
    def read(self,address,size):
        if RAM.get(address)!=size:return super().read(address,size)
        buffer=(C.c_uint8*size)()
        require(self.call('JLINKARM_ReadMemEx',address,size,buffer,0)==size,'BIO_PARTIAL_READ')
        return bytes(buffer)


def core(link):
    link.dll.JLINKARM_GetRegisterList.argtypes=[C.POINTER(C.c_uint32),C.c_uint32]
    link.dll.JLINKARM_GetRegisterName.argtypes=[C.c_uint32]
    link.dll.JLINKARM_GetRegisterName.restype=C.c_char_p
    link.dll.JLINKARM_ReadReg.argtypes=[C.c_int]
    link.dll.JLINKARM_ReadReg.restype=C.c_uint32
    ids=(C.c_uint32*256)()
    count=link.call('JLINKARM_GetRegisterList',ids,256);require(0<count<=256,'REGISTER_LIST')
    result={}
    for index in ids[:count]:
        name=link.call('JLINKARM_GetRegisterName',index).decode('ascii').upper().split()[0]
        if name in ('R13','R15','MSP','XPSR'):result[name]=link.call('JLINKARM_ReadReg',index)
    return result


def boot(link,reference,out,result):
    link.open();seen=identity(link);check_identity(seen)
    require(seen['uid_hex']==reference['uid_hex'] and seen['optcr']==reference['optcr'],'BOARD_BINDING')
    require(link.u32(0xE000EDF0)&HALT,'PREVIOUS_HALT_CHANGED')
    require(hashlib.sha256(link.read(0x08000000,1048576)).hexdigest()==EXPECTED_FLASH,'FLASH_DRIFT')
    vectors=link.read(0x08000000,64)
    sp,pc=int.from_bytes(vectors[:4],'little'),int.from_bytes(vectors[4:8],'little')
    require((sp,pc)==(0x20002f30,0x080001a1),'VECTOR_DRIFT')
    # 固定正常整器件复位策略，不使用仅改PC/SP的“软件启动”掩盖真实启动路径。
    link.policy('SetResetType = 0')
    require(link.call('JLINKARM_Reset',timeout=5)==0,'RESET_FAILED');result['reset_requests']=1
    require(link.u32(0xE000EDF0)&HALT,'RESET_NOT_HALTED')
    after=core(link);result['core_after_reset']={k:hex(v) for k,v in after.items()}
    write_json(out/'reset-entry-private.json',result['core_after_reset'])
    require(after.get('R15',0)&0xfffffffe in (pc&0xfffffffe,0x1a0),'RESET_ENTRY_NOT_BIO_V2')
    require(after.get('MSP',after.get('R13'))==sp,'RESET_STACK_NOT_BIO_V2')
    link.call('JLINKARM_Go');result['go_requests']=1
    time.sleep(3)
    require(not link.u32(0xE000EDF0)&(HALT|LOCKUP),'POST_GO_NOT_RUNNING')
    observations=[];start=time.monotonic()
    for index in range(11):
        target=start+index*.5
        if time.monotonic()<target:time.sleep(target-time.monotonic())
        require(not link.u32(0xE000EDF0)&(HALT|LOCKUP|RESET),'RUN_STATE_CHANGED')
        a=time.monotonic()
        blobs=[link.read(addr,size) for addr,size in RAM.items()]
        b=time.monotonic()
        for label,blob in zip(('diag','stats','regs'),blobs):
            with (out/f'{index:02d}-{label}.bin').open('xb') as f:f.write(blob)
        o=decode(*blobs);o.update(host_mid_s=(a+b)/2,read_start_s=a,read_end_s=b);observations.append(o)
    write_json(out/'observations-private.json',observations)
    result.update(assess(observations),target_end_state='RUNNING_CONFIRMED')


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for n in ('dll','card','out','reference'):p.add_argument('--'+n,required=True,type=Path)
    p.add_argument('--card-sha256',required=True);args=p.parse_args()
    require(sha(args.card)==args.card_sha256,'CARD_SHA_MISMATCH')
    require(args.out.resolve().is_relative_to(PRIVATE.resolve()),'OUTPUT_NOT_RESTRICTED')
    reference=json.loads(args.reference.read_text('utf-8'));args.out.mkdir(exist_ok=False)
    result={'status':'STARTED','card_sha256':args.card_sha256,'tool_sha256':sha(__file__),
            'halt_requests':0,'reset_requests':0,'go_requests':0,'flash_write_requests':0,'target_end_state':'UNKNOWN'}
    link=None
    try:
        link=BootLink(args.dll.resolve(),args.out);boot(link,reference,args.out,result)
    except BaseException as exc:
        result.update(status='BOOT_CHECK_STOP',error=type(exc).__name__+': '+str(exc),target_end_state='UNKNOWN_NO_AUTOMATIC_RECOVERY')
    finally:
        if link:
            try:link.close()
            except BaseException as exc:result.update(status='BOOT_CHECK_STOP',close_error=type(exc).__name__)
        write_json(args.out/'receipt-private.json',result)
    print(json.dumps({k:result[k] for k in ('status','error','core_after_reset','target_end_state') if k in result}))
    return 0 if result['status']=='OPEN_INPUT_LINK_CHECK_PASS' else 1


if __name__=='__main__':sys.exit(main())
