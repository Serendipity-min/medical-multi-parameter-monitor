"""异常停止后只读快照；不halt、reset、go，不改故障寄存器或Flash。"""
import argparse
import ctypes as C
import json
from pathlib import Path
import sys
from readback_b import Link, REGIONS, PRIVATE, HALT, identity, check_identity, require, sha, write_json

EXTRA={0xE000ED04:4,0xE000ED08:4,0xE000ED24:4,0xE000ED28:4,0xE000ED2C:4,
       0xE000ED30:4,0xE000ED34:4,0xE000ED38:4,0xE000EDFC:4,0xE0001000:4,
       0x40013800:4,0x40020410:4,0x40023874:4,0x00000000:64,0x08000000:64,
       0x20000000:131072}


class FaultLink(Link):
    def read(self,address,size):
        if REGIONS.get(address)==size:return super().read(address,size)
        require(EXTRA.get(address)==size,'FAULT_READ_RANGE_DENIED')
        buffer=(C.c_uint8*size)()
        require(self.call('JLINKARM_ReadMemEx',address,size,buffer,0,timeout=15)==size,'FAULT_PARTIAL_READ')
        self.io.write(json.dumps({'address':hex(address),'bytes':size})+'\n');self.io.flush()
        return bytes(buffer)


def snapshot(link,reference,out):
    link.open()
    seen=identity(link);check_identity(seen)
    require(seen['uid_hex']==reference['uid_hex'] and seen['optcr']==reference['optcr'],'BOARD_BINDING')
    result={'dhcsr_before':hex(link.u32(0xE000EDF0))}
    result['system_registers']={hex(a):hex(link.u32(a)) for a,n in EXTRA.items() if n==4}
    for address,name in [(0,'alias-vectors-private.bin'),(0x08000000,'flash-vectors-private.bin')]:
        with (out/name).open('xb') as f:f.write(link.read(address,64))
    # 只有实际已暂停才读核寄存器，避免SDK为取PC隐式暂停运行中的目标。
    if int(result['dhcsr_before'],16)&HALT:
        link.dll.JLINKARM_GetRegisterList.argtypes=[C.POINTER(C.c_uint32),C.c_uint32]
        link.dll.JLINKARM_GetRegisterName.argtypes=[C.c_uint32]
        link.dll.JLINKARM_GetRegisterName.restype=C.c_char_p
        link.dll.JLINKARM_ReadReg.argtypes=[C.c_int]
        link.dll.JLINKARM_ReadReg.restype=C.c_uint32
        ids=(C.c_uint32*256)()
        count=link.call('JLINKARM_GetRegisterList',ids,256)
        require(0<count<=256,'REGISTER_LIST_COUNT')
        selected={}
        allowed={f'R{i}' for i in range(16)}|{'PC','SP','LR','XPSR','MSP','PSP','CONTROL','PRIMASK','BASEPRI','FAULTMASK'}
        for index in ids[:count]:
            # SDK名称可能为R15 (PC)，按返回的首个名称选择，不猜寄存器枚举编号。
            name=link.call('JLINKARM_GetRegisterName',index).decode('ascii').upper().split()[0]
            if name in allowed:selected[name]=hex(link.call('JLINKARM_ReadReg',index))
        result['core_registers']=selected
    ram=link.read(0x20000000,131072)
    with (out/'ram-128k-private.bin').open('xb') as f:f.write(ram)
    result['dhcsr_after']=hex(link.u32(0xE000EDF0))
    return result


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
        link=FaultLink(args.dll.resolve(),args.out)
        result.update(snapshot(link,reference,args.out),status='FAULT_SNAPSHOT_SAVED')
        result['target_end_state']='HALTED_OBSERVED' if int(result['dhcsr_after'],16)&HALT else 'NOT_HALTED_OBSERVED'
    except BaseException as exc:result.update(status='FAULT_SNAPSHOT_STOP',error=type(exc).__name__+': '+str(exc))
    finally:
        if link:
            try:link.close()
            except BaseException as exc:result.update(status='FAULT_SNAPSHOT_STOP',close_error=type(exc).__name__)
        write_json(args.out/'receipt-private.json',result)
    print(json.dumps({k:v for k,v in result.items() if k in ('status','error','target_end_state','dhcsr_before','dhcsr_after','system_registers','core_registers')}))
    return 0 if result['status']=='FAULT_SNAPSHOT_SAVED' else 1


if __name__=='__main__':sys.exit(main())
