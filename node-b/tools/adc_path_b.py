"""已启动BIO_V2的START/DRDY/SPI/EXTI路径只读核验；保留应用使用的DWT。"""
import argparse
import ctypes as C
import json
from pathlib import Path
import sys
import time
from precheck_b import BioLink,decode
from boot_check_b import core
from readback_b import PRIVATE,HALT,LOCKUP,RESET,identity,check_identity,require,sha,write_json

PATH_REGS={
 'GPIOA_MODER':0x40020000,'GPIOA_PUPDR':0x4002000c,'GPIOA_IDR':0x40020010,
 'GPIOA_ODR':0x40020014,'GPIOA_AFRL':0x40020020,
 'GPIOG_MODER':0x40021800,'GPIOG_PUPDR':0x4002180c,'GPIOG_IDR':0x40021810,'GPIOG_ODR':0x40021814,
 'SPI1_CR1':0x40013000,'SPI1_CR2':0x40013004,'SPI1_SR':0x40013008,
 'EXTI_IMR':0x40013c00,'EXTI_RTSR':0x40013c08,'EXTI_FTSR':0x40013c0c,'EXTI_PR':0x40013c14,
 'SYSCFG_EXTICR1':0x40013808,'NVIC_ISER0':0xe000e100,'NVIC_ISPR0':0xe000e200,'NVIC_IABR0':0xe000e300,
 'RCC_AHB1ENR':0x40023830,'RCC_APB2ENR':0x40023844,
 'DWT_CTRL':0xe0001000,'DWT_CYCCNT':0xe0001004,'DEMCR':0xe000edfc,
 'CFSR':0xe000ed28,'HFSR':0xe000ed2c,'VTOR':0xe000ed08}
EXTRA={a:4 for a in PATH_REGS.values()}
EXTRA[0x20000024]=1


class PathLink(BioLink):
    def read(self,address,size):
        if EXTRA.get(address)!=size:return super().read(address,size)
        data=(C.c_uint8*size)()
        require(self.call('JLINKARM_ReadMemEx',address,size,data,0)==size,'PATH_PARTIAL_READ')
        self.io.write(json.dumps({'address':hex(address),'bytes':size})+'\n');self.io.flush()
        return bytes(data)

    def open(self):
        super().open()
        # 固件用DWT做SPI微秒时序；默认Close清TRCENA会干扰应用，不能将其误判为硬件失败。
        self.policy('SetSkipDebugDeInit = 1')


def inspect(link,reference,out,receipt):
    link.open();seen=identity(link);check_identity(seen)
    require(seen['uid_hex']==reference['uid_hex'] and seen['optcr']==reference['optcr'],'BOARD_BINDING')
    state=link.u32(0xe000edf0)
    write_json(out/'state-before-private.json',{'dhcsr':hex(state)})
    require(not state&LOCKUP,'LOCKUP')
    if state&HALT:
        # 会话间出现暂停时仅允许无fault的已核Flash应用续跑一次，不重新复位或跳PC。
        registers=core(link)
        write_json(out/'core-before-private.json',{k:hex(v) for k,v in registers.items()})
        require(0x08000000<=registers.get('R15',0)<0x080062c4,'PAUSED_OUTSIDE_BIO_V2')
        require(link.u32(0xe000ed28)==0 and link.u32(0xe000ed2c)==0,'ACTIVE_FAULT')
        link.call('JLINKARM_Go');receipt['go_requests']+=1
        time.sleep(.5)
    require(not link.u32(0xe000edf0)&(HALT|LOCKUP),'NOT_RUNNING')
    results=[]
    for i in range(3):
        if i:time.sleep(.5)
        require(not link.u32(0xe000edf0)&(HALT|LOCKUP|RESET),'STATE_CHANGED')
        regs={k:hex(link.u32(a)) for k,a in PATH_REGS.items()}
        blobs=[link.read(a,n) for a,n in ((0x20001ae4,120),(0x2000018c,48),(0x200001bc,12))]
        for label,blob in zip(('diag','stats','rreg-cache'),blobs):
            with (out/f'{i:02d}-{label}.bin').open('xb') as f:f.write(blob)
        results.append({'host_monotonic':time.monotonic(),'path':regs,
                        'ready_byte':link.read(0x20000024,1).hex(),'bio':decode(*blobs)})
    write_json(out/'observations-private.json',results)
    require(not link.u32(0xe000edf0)&(HALT|LOCKUP|RESET),'FINAL_STATE_CHANGED')
    return results


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
        link=PathLink(args.dll.resolve(),args.out);observations=inspect(link,reference,args.out,result)
        result.update(status='ADC_PATH_SAVED',target_end_state='RUNNING_CONFIRMED',last=observations[-1])
    except BaseException as exc:result.update(status='ADC_PATH_STOP',error=type(exc).__name__+': '+str(exc))
    finally:
        if link:
            try:link.close()
            except BaseException as exc:result.update(status='ADC_PATH_STOP',close_error=type(exc).__name__)
        write_json(args.out/'receipt-private.json',result)
    print(json.dumps({k:result[k] for k in ('status','error','target_end_state') if k in result}))
    return 0 if result['status']=='ADC_PATH_SAVED' else 1


if __name__=='__main__':sys.exit(main())
