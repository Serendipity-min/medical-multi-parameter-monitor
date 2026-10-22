"""固定BIO_V2未接源五秒检查；依R2卡条件go一次，不halt/reset或写Flash。"""
import argparse
import ctypes as C
import datetime as dt
import hashlib
import json
from pathlib import Path
import struct
import sys
import time
from readback_b import Link, PRIVATE, REGIONS, HALT, LOCKUP, RESET, identity, check_identity, require, sha, write_json

EXPECTED_FLASH='f713277a50a5ec8d8a93317f412d5ab1b754e5d619918e57e9efe9dceef24cbb'
RAM={0x20001AE4:120,0x2000018C:48,0x200001BC:12}
STATS=('irq_count','captured','delivered','bad_status','spi_errors','queue_overflow',
       'queue_peak','init_errors','long_gap_count','min_irq_gap_cycles','max_irq_gap_cycles','max_read_cycles')


class BioLink(Link):
    def read(self,address,size):
        if address in REGIONS:return super().read(address,size)
        require(RAM.get(address)==size,'BIO_READ_RANGE_DENIED')
        buffer=(C.c_uint8*size)()
        before=time.monotonic()
        count=self.call('JLINKARM_ReadMemEx',address,size,buffer,0)
        self.io.write(json.dumps({'address':hex(address),'bytes':size,'returned':count,
                                  'elapsed_s':time.monotonic()-before})+'\n');self.io.flush()
        require(count==size,'BIO_PARTIAL_READ')
        return bytes(buffer)


def decode(diag,stats,registers):
    require(len(diag)==120 and len(stats)==48 and len(registers)==12,'BIO_LENGTH')
    values=struct.unpack('<26I4f',diag)
    require(values[:2]==(0x324f4942,2),'BIO_ABI_MISMATCH')
    return {'samples':values[2],'last_sequence':values[3],'last_sample_ms':values[4],
            'hr':values[12],'hr_valid':values[14],'hr_reason':values[16],
            'adc':dict(zip(STATS,struct.unpack('<12I',stats))),
            'registers_hex':registers.hex()}


def assess(observations):
    first,last=observations[0],observations[-1]
    errors=[]
    expected={0:0x73,1:0x01,2:0xe0,3:0xf0,4:0x40,5:0x40,6:0xec,7:0,9:0xea,10:3,11:0x0c}
    for o in observations:
        registers=bytes.fromhex(o['registers_hex'])
        for offset,value in expected.items():
            mask=0xfc if offset==11 else 0xff
            if registers[offset]&mask!=value:errors.append('ADS_REGISTER_'+str(offset))
        for key in ('init_errors','spi_errors','bad_status','queue_overflow'):
            if o['adc'][key]:errors.append('ADC_'+key.upper())
    elapsed=last['host_mid_s']-first['host_mid_s']
    rate=(last['adc']['captured']-first['adc']['captured'])/elapsed
    if not 240<=rate<=260:errors.append('CAPTURE_RATE_NOT_250')
    if last['samples']<=first['samples']:errors.append('BIO_NOT_ADVANCING')
    return {'status':'OPEN_INPUT_LINK_CHECK_PASS' if not errors else 'OPEN_INPUT_LINK_CHECK_FAIL',
            'errors':sorted(set(errors)),'observed_capture_sps':rate,
            'elapsed_s':elapsed,'first':first,'last':last,
            'hr_accuracy':'NOT_EVALUATED_OPEN_UNKNOWN_INPUT',
            'register_evidence':'REAL_INIT_RREG_CACHE_NOT_FRESH_SPI_READ',
            'coherence':'LIVE_UNCOORDINATED_OBSERVATIONAL_ONLY'}


def acquire(link,reference,out):
    link.open()
    before=identity(link);check_identity(before)
    require(before['uid_hex']==reference['uid_hex'] and before['optcr']==reference['optcr'],'BOARD_BINDING')
    state=link.u32(0xE000EDF0)
    require(not state&LOCKUP,'LOCKUP')
    flash=link.read(0x08000000,1048576)
    require(hashlib.sha256(flash).hexdigest()==EXPECTED_FLASH,'INSTALLED_FLASH_DRIFT')
    if state&HALT:
        # 仅依R2卡条件续跑一次；取当前真实PC，不复位或把旧PC改成入口来制造通过。
        from boot_check_b import core
        registers=core(link)
        write_json(out/'core-before-private.json',{k:hex(v) for k,v in registers.items()})
        require(0x08000000<=registers.get('R15',0)<0x080062c4,'PAUSED_OUTSIDE_BIO_V2')
        require(link.u32(0xe000ed28)==0 and link.u32(0xe000ed2c)==0,'ACTIVE_FAULT')
        link.call('JLINKARM_Go');link.precheck_go_requests=1;time.sleep(.5)
    observations=[]
    start=time.monotonic()
    with (out/'observations-private.jsonl').open('x',encoding='utf-8') as stream:
        for index in range(11):
            target=start+index*.5
            if time.monotonic()<target:time.sleep(target-time.monotonic())
            require(not link.u32(0xE000EDF0)&(HALT|LOCKUP|RESET),'TARGET_STATE_CHANGED')
            a=time.monotonic()
            diag=link.read(0x20001AE4,120)
            stats=link.read(0x2000018C,48)
            regs=link.read(0x200001BC,12)
            b=time.monotonic()
            # 保留三次独立IO的原字节和区间；不得宣称活动RAM快照是原子状态。
            for label,blob in [('diag',diag),('stats',stats),('registers',regs)]:
                with (out/f'{index:02d}-{label}.bin').open('xb') as f:f.write(blob)
            o=decode(diag,stats,regs);o.update(host_mid_s=(a+b)/2,read_start_s=a,read_end_s=b)
            stream.write(json.dumps(o)+'\n');stream.flush();observations.append(o)
    final=identity(link);check_identity(final)
    require(final['uid_hex']==before['uid_hex'] and final['optcr']==before['optcr'],'FINAL_IDENTITY_DRIFT')
    require(not link.u32(0xE000EDF0)&(HALT|LOCKUP|RESET),'FINAL_STATE_CHANGED')
    return assess(observations)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('dll','card','out','reference'):parser.add_argument('--'+name,required=True,type=Path)
    parser.add_argument('--card-sha256',required=True)
    args=parser.parse_args()
    require(sha(args.card)==args.card_sha256,'CARD_SHA_MISMATCH')
    require(args.out.resolve().is_relative_to(PRIVATE.resolve()),'OUTPUT_NOT_RESTRICTED')
    reference=json.loads(args.reference.read_text('utf-8'))
    args.out.mkdir(exist_ok=False)
    result={'status':'PRECHECK_STARTED','card_sha256':args.card_sha256,'tool_sha256':sha(__file__),
            'reference_sha256':sha(args.reference),'started_utc':dt.datetime.now(dt.timezone.utc).isoformat(),
            'halt_requests':0,'reset_requests':0,'go_requests':0,'flash_write_requests':0,
            'input':'OPEN_UNKNOWN','target_end_state':'UNKNOWN'}
    link=None
    try:
        # 延迟导入避免工具之间模块初始化循环；复用已经实测的DWT保留策略/只读范围。
        from adc_path_b import PathLink
        link=PathLink(args.dll.resolve(),args.out)
        result.update(acquire(link,reference,args.out),target_end_state='RUNNING_CONFIRMED')
    except BaseException as exc:
        result.update(status='PRECHECK_STOP_OR_INCOMPLETE',error=type(exc).__name__+': '+str(exc))
    finally:
        if link:
            result['go_requests']=getattr(link,'precheck_go_requests',0)
            try:link.close()
            except BaseException as exc:result.update(status='PRECHECK_STOP_OR_INCOMPLETE',close_error=type(exc).__name__)
        result['ended_utc']=dt.datetime.now(dt.timezone.utc).isoformat()
        write_json(args.out/'receipt-private.json',result)
    print(json.dumps({'status':result['status'],'errors':result.get('errors'),
                      'error':result.get('error'),'target_end_state':result['target_end_state']}))
    return 0 if result['status']=='OPEN_INPUT_LINK_CHECK_PASS' else 1


if __name__=='__main__':sys.exit(main())
