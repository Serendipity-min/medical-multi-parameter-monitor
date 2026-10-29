"""已冻结B4固件的只读ADC/CAN运行取证；无halt/go/reset或目标写入口。"""
import argparse
import ctypes as C
import hashlib
import json
from pathlib import Path
import struct
import subprocess
import sys
import time

import b4_recovery as pkg
import c_b4_readonly as ro
import readback_b as raw
import runtime_state_b as runtime
from live_state_b import LiveLink
from resp_exploratory import decode

ROOT=Path(__file__).resolve().parents[2]
SCOPE='B4_RUNNING_B_ADC_CAN_READONLY_NO_RESET_HALT_GO'
IMAGE_SHA='676eb7a46ad9cd15c7bf93db51a1931d7711d37c6f2fd636197dc4a85b339b82'
RAM={0x20001d14:120,0x20000608:48,0x20000638:12,0x20003770:44,0x40006418:4}
READS={a:set(n) for a,n in ro.READS.items()}; READS[0x08000000]={39948}
READS.update({a:{n} for a,n in RAM.items()})
CAN_FIELDS='offered enqueued sent_ecg sent_resp overflow expired comm_reset app_reset_rejected high_water error discontinuities'.split()


def need(ok,reason):
    if not ok: raise ValueError(reason)


def validate(a):
    need(a.get('enabled') is True and a.get('owner_approved') is True and a.get('scope')==SCOPE,
         'B4_RUNTIME_OWNER_AUTH')
    need(a.get('tool_sha256')==raw.sha(__file__) and a.get('image_sha256')==IMAGE_SHA,
         'B4_RUNTIME_BINDINGS')
    need(a.get('seconds') in (3,150) and time.time()<a.get('expires_unix',0),'B4_RUNTIME_WINDOW')
    need(a.get('JLink_on_B') is True,'B4_RUNTIME_TARGET_ROUTE')


class Link(LiveLink):
    def __init__(self,out): super().__init__(ro.DLL,out)
    def call(self,name,*args,timeout=5):
        need(name in runtime.CALLS-{'JLINKARM_GetRegisterList','JLINKARM_GetRegisterName','JLINKARM_ReadReg'},
             'B4_RUNTIME_FUNCTION_DENIED')
        need(self.sdk_calls<24000,'B4_RUNTIME_BUDGET')
        if name=='JLINKARM_ExecCommand':
            command=args[0].decode('ascii')
            need(command in runtime.COMMANDS or command=='SetRestartOnClose = 1','B4_RUNTIME_POLICY')
            if command=='SetRestartOnClose = 1':need(self.verified_running_flash,'B4_RUNTIME_CLOSE')
        if name=='JLINKARM_ReadMemEx':need(args[1] in READS.get(args[0],set()) and args[3]==0,'B4_RUNTIME_READ_SCOPE')
        self.sdk_calls+=1
        return raw.Link.call(self,name,*args,timeout=timeout)
    def read(self,address,size):
        need(size in READS.get(address,set()),'B4_RUNTIME_READ_SCOPE')
        data=(C.c_uint8*size)();n=self.call('JLINKARM_ReadMemEx',address,size,data,0)
        need(n==size,'B4_RUNTIME_PARTIAL_READ');return bytes(data)


def snapshot(link,out=None,label='snapshot',addresses=None):
    state=ro.snapshot(link)
    if out:raw.write_json(out/(label+'-state-private.json'),state)
    ro.check_running(link,state)
    # CPU状态先于后续RAM/质量解析独立确认，任何解析负例也必须保留健康Flash续跑。
    if not link.close_resume_enabled:link.set_close_resume(True)
    addresses=addresses or {'bio':(0x20001d14,120),'adc':(0x20000608,48),'registers':(0x20000638,12),'CAN':(0x20003770,44)}
    blobs=[link.read(*addresses[name]) for name in ('bio','adc','registers')]
    if out:
        # 判据失败前先保留实际诊断字节，不能只留下异常名称而丢弃触发依据。
        for name,blob in zip(('bio','adc','registers'),blobs):
            with (out/(label+'-'+name+'-private.bin')).open('xb') as f:f.write(blob)
    bio=decode(*blobs)
    can=dict(zip(CAN_FIELDS,struct.unpack('<11I',link.read(*addresses['CAN']))))
    result={'host_monotonic':time.monotonic(),'state':state,'bio':bio,'CAN':can,
            'CAN1_ESR':link.u32(0x40006418),'coherence':'LIVE_NONATOMIC_NO_HALT'}
    if 'temperature' in addresses:
        import b5_b_temp_readonly as temp
        blob=link.read(*addresses['temperature'])
        result['temperature']=temp.decode_temp(blob)
        if out:raw.write_json(out/(label+'-temperature-private.json'),result['temperature'])
    if out:raw.write_json(out/(label+'-decoded-private.json'),result)
    # 初始化失败不能带入台架；历史累计的帧/队列错误则保留原值，由评价窗增量判定。
    # 这样不会把此前暂停留下的一次状态错误误报为当前仍在发生的新错误。
    need(bio['adc']['init_errors']==0,'B4_RUNTIME_ADC_INIT_ERRORS')
    need(can['error']==0,'B4_RUNTIME_CAN_APP_ERRORS')
    return result


def assess(first,last):
    need(last['bio']['samples']>first['bio']['samples'],'B4_RUNTIME_NO_SAMPLES')
    need(last['bio']['last_sequence']>first['bio']['last_sequence'],'B4_RUNTIME_SEQUENCE_RESTART')
    # 削顶属于输入/算法质量，保留并单独裁定，不能冒充ADC采样丢失或迫使调低BIO阈值。
    for key in ('discontinuities',):
        need(last['bio'][key]==first['bio'][key],'B4_RUNTIME_NEW_'+key.upper())
    need(last['bio']['adc']['long_gap_count']==first['bio']['adc']['long_gap_count'],'B4_RUNTIME_NEW_ADC_GAP')
    for key in ('bad_status','spi_errors','queue_overflow','init_errors'):
        need(last['bio']['adc'][key]==first['bio']['adc'][key],'B4_RUNTIME_NEW_ADC_'+key.upper())
    for key in ('overflow','discontinuities','comm_reset'):
        need(last['CAN'][key]==first['CAN'][key],'B4_RUNTIME_NEW_CAN_'+key.upper())
    elapsed=last['bio']['last_sample_ms']-first['bio']['last_sample_ms']
    need(elapsed>0,'B4_RUNTIME_TIME_RESTART')
    rate=(last['bio']['samples']-first['bio']['samples'])*1000/elapsed
    # 运行中120B快照非原子，短间隔只判断推进；至少2秒跨度再裁定名义采样率。
    if elapsed>=2000:need(247.5<=rate<=252.5,'B4_RUNTIME_NOT_250SPS')
    return rate


def worker(args,a):
    args.out.mkdir(exist_ok=False);link=None;result={'status':'STOP','exit_code':1}
    try:
        reference=json.loads(pkg.protected(Path(a['identity']),False).read_text('utf-8'))
        link=Link(args.out);link.open();seen=raw.identity(link);raw.check_identity(seen)
        need(seen==reference,'B4_RUNTIME_IDENTITY')
        raw.write_json(args.out/'identity-private.json',seen)
        need(hashlib.sha256(link.read(0x08000000,39948)).hexdigest()==IMAGE_SHA,'B4_RUNTIME_FIRMWARE')
        raw.write_json(args.out/'entry-sticky-private.json',{'DHCSR':link.u32(ro.SYSTEM['DHCSR'])})
        first=snapshot(link,args.out,'0000')
        # 一旦确认CPU在Flash正常运行就锁定退出续跑；后续质量判据失败也不遗留SDK暂停。
        link.set_close_resume(True)
        # READY之前先取得至少2秒的连续性与速率证据；不能只靠半秒非原子快照放行。
        time.sleep(2);last=snapshot(link,args.out,'0001');assess(first,last)
        # 只有身份、真实BIN及ADC推进通过后才给C采集器发本机READY；不通过串口自动复位。
        raw.write_json(args.out/'READY.json',{'host_monotonic':time.monotonic(),'B4_image_sha256':IMAGE_SHA,
                                           'samples':last['bio']['samples']})
        start=time.monotonic();rows=[first,last]
        with (args.out/'snapshots-private.jsonl').open('x',encoding='utf-8') as log:
            for row in rows:log.write(json.dumps(row)+'\n')
            while time.monotonic()-start<a['seconds']:
                time.sleep(.5);current=snapshot(link,args.out,f'{len(rows):04d}');assess(last,current)
                need(current['bio']['samples']>=last['bio']['samples'],'B4_RUNTIME_COUNTER_RESTART')
                last=current;rows.append(current);log.write(json.dumps(current)+'\n');log.flush()
        rate=assess(first,last)
        result={'status':'B4_B_ADC_RUNTIME_OBSERVED_PASS','exit_code':0,'snapshots':len(rows),
                'device_sps':rate,'samples_advanced':last['bio']['samples']-first['bio']['samples'],
                'clipped_samples_advanced':last['bio']['clipped_samples']-first['bio']['clipped_samples'],
                'first':first,'last':last,'HR_RR_simultaneous_acceptance':False,
                'CPU_ROM_root_cause':'UNRESOLVED','explicit_target_reset_halt_go_writes':0}
    except BaseException as e:
        raw.write_json(args.out/'failure-private.json',{'type':type(e).__name__,'reason':str(e)})
    finally:
        if link:
            try:
                if not link.verified_running_flash and link.close_resume_enabled:link.set_close_resume(False)
            except BaseException as e:result.update(exit_code=1,close_policy_error=type(e).__name__)
            finally:
                try:link.close()
                except BaseException as e:result.update(exit_code=1,close_error=type(e).__name__)
            result.update(sdk_calls=link.sdk_calls,close_resume=link.close_resume_enabled)
        raw.write_json(args.out/'receipt-private.json',result)
        for p in args.out.iterdir():
            if p.is_file():pkg.protected(p,False)
    print(json.dumps({'status':result['status'],'exit_code':result['exit_code']}));return result['exit_code']


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--authorization',type=Path)
    p.add_argument('--out',type=Path);p.add_argument('--worker',action='store_true',help=argparse.SUPPRESS)
    args=p.parse_args()
    try:
        need(args.authorization is not None and args.out is not None,'B4_RUNTIME_AUTH_OUT')
        a=json.loads(pkg.protected(args.authorization,False).read_text('utf-8'));validate(a)
        pkg.protected(args.out.parent,False);need(not args.out.exists(),'B4_RUNTIME_OUTPUT_EXISTS')
        if args.worker:return worker(args,a)
        with args.authorization.with_suffix('.used').open('x',encoding='utf-8') as f:json.dump({'scope':SCOPE},f)
        cmd=[sys.executable,'-X','utf8',str(Path(__file__)),'--worker','--authorization',str(args.authorization),'--out',str(args.out)]
        reason=None;start=time.monotonic()
        with args.out.with_name(args.out.name+'-worker.log').open('xb') as log:
            child=subprocess.Popen(cmd,stdout=log,stderr=subprocess.STDOUT)
            try:
                while child.poll() is None:
                    if time.monotonic()-start>180:reason='SESSION_TIMEOUT'
                    if (args.out/'STOP').exists():reason='OWNER_STOP'
                    try:
                        lines=(args.out/'heartbeat-events.jsonl').read_text('utf-8').splitlines();e=json.loads(lines[-1]) if lines else {}
                        if e.get('active') and time.monotonic()>e['deadline_monotonic']:reason='SDK_TIMEOUT'
                    except (OSError,ValueError):pass
                    if reason:child.kill();break
                    time.sleep(.05)
            finally:
                if child.poll() is None:child.kill()
                child.wait(timeout=5)
        args.out.mkdir(exist_ok=True);raw.write_json(args.out/'supervisor-private.json',{'reason':reason,'worker_exit_code':child.returncode})
        return 1 if reason else child.returncode
    except (ValueError,RuntimeError,OSError,KeyError,TypeError):
        print(json.dumps({'status':'STOP_BEFORE_SDK','exit_code':1}));return 1


if __name__=='__main__':sys.exit(main())
