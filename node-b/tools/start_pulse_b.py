"""唯一PG15 START低高脉冲；不碰SPI配置、Flash、其他GPIO或接源。"""
import argparse
import ctypes as C
import json
from pathlib import Path
import sys
import time
from adc_path_b import PathLink
from boot_check_b import core
from precheck_b import decode,assess
from readback_b import PRIVATE,HALT,LOCKUP,RESET,identity,check_identity,require,sha,write_json


def sample(link,out,index):
    a=time.monotonic()
    blobs=[link.read(addr,size) for addr,size in ((0x20001ae4,120),(0x2000018c,48),(0x200001bc,12))]
    b=time.monotonic()
    for label,blob in zip(('diag','stats','regs'),blobs):
        with (out/f'{index:02d}-{label}.bin').open('xb') as f:f.write(blob)
    o=decode(*blobs);o.update(host_mid_s=(a+b)/2,read_start_s=a,read_end_s=b)
    return o


def pulse(link,out,receipt):
    # 仅限当前PG15推挽输出且已高；BSRR原子置复位只影响这一位，不整写ODR。
    require((link.u32(0x40021800)>>30)&3==1,'PG15_NOT_OUTPUT')
    require(link.u32(0x40021814)&0x8000,'START_NOT_HIGH')
    require(not link.u32(0xe000edf0)&(HALT|LOCKUP|RESET),'NOT_RUNNING')
    before=sample(link,out,0);write_json(out/'before-private.json',before)
    require(before['adc']['init_errors']==0 and link.read(0x20000024,1)==b'\1','ADS_NOT_READY')
    if before['adc']['irq_count']:
        receipt.update(status='PULSE_NOT_NEEDED_IRQ_ALREADY_PRESENT',target_end_state='RUNNING_BEFORE_CLOSE')
        return
    link.dll.JLINKARM_WriteU32.argtypes=[C.c_uint32,C.c_uint32]
    link.dll.JLINKARM_WriteU32.restype=C.c_int
    for value,high in ((0x80000000,False),(0x00008000,True)):
        require(not link.u32(0xe000edf0)&(HALT|LOCKUP|RESET),'STATE_CHANGED')
        receipt['gpio_write_attempts']+=1
        require(link.call('JLINKARM_WriteU32',0x40021818,value)==0,'START_WRITE_FAILED')
        receipt['start_last_command']='HIGH' if high else 'LOW'
        require(bool(link.u32(0x40021814)&0x8000)==high,'START_LATCH_VERIFY')
        time.sleep(.02)
    observations=[];start=time.monotonic()
    for i in range(11):
        target=start+i*.5
        if time.monotonic()<target:time.sleep(target-time.monotonic())
        require(not link.u32(0xe000edf0)&(HALT|LOCKUP|RESET),'RUN_STATE_CHANGED')
        observations.append(sample(link,out,i+1))
    write_json(out/'observations-private.json',observations)
    receipt.update(assess(observations),target_end_state='RUNNING_BEFORE_CLOSE',
                   gpioa_idr_after=hex(link.u32(0x40020010)),gpiog_odr_after=hex(link.u32(0x40021814)))


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for n in ('dll','card','out','reference'):p.add_argument('--'+n,required=True,type=Path)
    p.add_argument('--card-sha256',required=True);args=p.parse_args()
    require(sha(args.card)==args.card_sha256,'CARD_SHA_MISMATCH')
    require(args.out.resolve().is_relative_to(PRIVATE.resolve()),'OUTPUT_NOT_RESTRICTED')
    reference=json.loads(args.reference.read_text('utf-8'));args.out.mkdir(exist_ok=False)
    receipt={'status':'STARTED','card_sha256':args.card_sha256,'tool_sha256':sha(__file__),
             'gpio_write_attempts':0,'start_last_command':'NONE','halt_requests':0,'reset_requests':0,
             'go_requests':0,'flash_write_requests':0,'target_end_state':'UNKNOWN'}
    link=None
    try:
        link=PathLink(args.dll.resolve(),args.out);link.open()
        seen=identity(link);check_identity(seen)
        require(seen['uid_hex']==reference['uid_hex'] and seen['optcr']==reference['optcr'],'BOARD_BINDING')
        state=link.u32(0xe000edf0)  # 建立旧RESET粘滞基线，保留实际暂停状态。
        write_json(args.out/'state-before-private.json',{'dhcsr':hex(state)})
        require(not state&LOCKUP,'LOCKUP')
        if state&HALT:
            # 同一会话内条件续跑后直接诊断，避免把会话间暂停算作START脉冲的结果。
            registers=core(link)
            write_json(args.out/'core-before-private.json',{k:hex(v) for k,v in registers.items()})
            require(0x08000000<=registers.get('R15',0)<0x080062c4,'PAUSED_OUTSIDE_BIO_V2')
            require(link.u32(0xe000ed28)==0 and link.u32(0xe000ed2c)==0,'ACTIVE_FAULT')
            link.call('JLINKARM_Go');receipt['go_requests']=1;time.sleep(.5)
        pulse(link,args.out,receipt)
    except BaseException as exc:receipt.update(status='START_PULSE_STOP',error=type(exc).__name__+': '+str(exc))
    finally:
        if link:
            try:link.close()
            except BaseException as exc:receipt.update(status='START_PULSE_STOP',close_error=type(exc).__name__)
        write_json(args.out/'receipt-private.json',receipt)
    print(json.dumps({k:receipt[k] for k in ('status','error','errors','gpio_write_attempts','start_last_command','target_end_state') if k in receipt}))
    return 0 if receipt['status'] in ('OPEN_INPUT_LINK_CHECK_PASS','PULSE_NOT_NEEDED_IRQ_ALREADY_PRESENT') else 1


if __name__=='__main__':sys.exit(main())
