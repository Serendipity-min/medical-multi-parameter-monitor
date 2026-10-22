"""BIO_V2固定地址采集；原槽块/非原子诊断/确认暂停尾段分别留证。"""
import argparse
import csv
import ctypes as C
import hashlib
import json
from pathlib import Path
import struct
import sys
import time
from adc_path_b import PathLink
from boot_check_b import core
from precheck_b import EXPECTED_FLASH,decode
from readback_b import PRIVATE,HALT,LOCKUP,RESET,identity,check_identity,require,sha,write_json
from field_profile import validate_profile

ROOT=Path(__file__).resolve().parents[2]
ARM=ROOT/'node-b/build/arm-20261022T074340122429Z'
sys.path.insert(0,str(ROOT/'node-b/acquisition/工具'))
from stable_slot_export import StableSlots,unpack_slot_fields


def bindings():
    paths=[Path(__file__),*[(ROOT/'node-b/tools'/n) for n in
           ('readback_b.py','precheck_b.py','adc_path_b.py','boot_check_b.py','fault_snapshot_b.py','field_profile.py','supervise_readback.py')],
           ROOT/'node-b/acquisition/工具/stable_slot_export.py']
    return {p.relative_to(ROOT).as_posix():sha(p) for p in paths}


def validate(profile):
    require(profile['schema']=='BIO_V2_CAPTURE_1','OLD_CAPTURE_PROFILE')
    offline=json.loads((ROOT/'node-b/acquisition/field-biov2/profile.offline.json').read_text('utf-8'))
    abi=json.loads((ROOT/'node-b/evidence/B-ALG-002/abi-receipt.json').read_text('utf-8'))
    validate_profile(offline,ARM,abi)
    require(profile['offline_profile_sha256']==sha(ROOT/'node-b/acquisition/field-biov2/profile.offline.json'),'OFFLINE_PROFILE_DRIFT')
    require(profile['tools_sha256']==bindings(),'CAPTURE_TOOL_DRIFT')
    require(profile['layout']==offline['layout'],'CAPTURE_LAYOUT_DRIFT')
    require(profile['flash_sha256']==EXPECTED_FLASH,'CAPTURE_FLASH_BINDING')
    require(sha(Path(profile['identity_reference']))==profile['identity_reference_sha256'],'IDENTITY_REFERENCE_DRIFT')
    require(profile['data_source']=='ENGINEERING_NONHUMAN','SOURCE_CLASS')


def prepare(path):
    offline=ROOT/'node-b/acquisition/field-biov2/profile.offline.json'
    reference=PRIVATE/'readback-r3-02/identity-before-private.json'
    profile={'schema':'BIO_V2_CAPTURE_1','data_source':'ENGINEERING_NONHUMAN',
             'offline_profile_sha256':sha(offline),'layout':json.loads(offline.read_text('utf-8'))['layout'],
             'tools_sha256':bindings(),'identity_reference':str(reference),'identity_reference_sha256':sha(reference),
             'flash_sha256':EXPECTED_FLASH,'options_sha256':sha(PRIVATE/'readback-r3-02/options-read-1.bin'),
             'poll_interval_s':.05,'duration_choices_s':[10,90],'live_diag':'NONATOMIC_OBSERVATION',
             'end_snapshot':'CONFIRMED_HALTED_SINGLE_128K_RAM','peak_events':'OFFLINE_REPLAY_ONLY'}
    validate(profile);write_json(path,profile)
    return profile


class CaptureLink(PathLink):
    def gate(self):
        # 90秒窗口加两次整片读和尾段，独立总上限240秒；其他入口仍为180秒。
        require(not (self.out/'STOP').exists(),'OWNER_STOP')
        require(time.monotonic()-self.started<=240,'SESSION_TIMEOUT')
        require(not self.error,'SDK_ERROR_SEE_PRIVATE_LOG')

    def read(self,address,size):
        if (address,size) not in ((0x20001f30,3072),(0x20000000,131072)):
            return super().read(address,size)
        buffer=(C.c_uint8*size)();start=time.monotonic()
        count=self.call('JLINKARM_ReadMemEx',address,size,buffer,0,timeout=15)
        self.io.write(json.dumps({'address':hex(address),'bytes':size,'returned':count,
                                  'start_s':start,'end_s':time.monotonic()})+'\n');self.io.flush()
        require(count==size,'CAPTURE_PARTIAL_READ')
        return bytes(buffer)


def snapshot(link,out,index):
    a=time.monotonic()
    blobs=[link.read(addr,size) for addr,size in ((0x20001ae4,120),(0x2000018c,48),(0x200001bc,12))]
    b=time.monotonic()
    for label,blob in zip(('diag','stats','rreg-cache'),blobs):
        with (out/f'{index:04d}-{label}.bin').open('xb') as f:f.write(blob)
    obs=decode(*blobs);obs.update(host_start_s=a,host_end_s=b)
    return obs


def collect(link,profile,out,seconds,receipt):
    link.open();seen=identity(link);check_identity(seen)
    reference=json.loads(Path(profile['identity_reference']).read_text('utf-8'))
    require(seen['uid_hex']==reference['uid_hex'] and seen['optcr']==reference['optcr'],'BOARD_BINDING')
    state=link.u32(0xe000edf0);require(not state&LOCKUP,'LOCKUP')
    require(hashlib.sha256(link.read(0x08000000,1048576)).hexdigest()==profile['flash_sha256'],'START_FLASH_DRIFT')
    require(hashlib.sha256(link.read(0x1fffc000,16)).hexdigest()==profile['options_sha256'],'OPTIONS_DRIFT')
    if state&HALT:
        registers=core(link)
        write_json(out/'core-before-private.json',{k:hex(v) for k,v in registers.items()})
        require(0x08000000<=registers.get('R15',0)<0x080062c4,'PAUSED_OUTSIDE_BIO_V2')
        require(link.u32(0xe000ed28)==0 and link.u32(0xe000ed2c)==0,'ACTIVE_FAULT')
        link.call('JLINKARM_Go');receipt['go_requests']+=1;time.sleep(.5)
    diagnostics=[];started=time.monotonic();index=0
    with (out/'running-slots-private.bin').open('xb') as raw,(out/'chunks-private.jsonl').open('x',encoding='utf-8') as records:
        while time.monotonic()-started<seconds:
            target=started+index*.05
            if time.monotonic()<target:time.sleep(target-time.monotonic())
            require(not link.u32(0xe000edf0)&(HALT|LOCKUP|RESET),'WINDOW_STATE_CHANGED')
            a=time.monotonic();blob=link.read(0x20001f30,3072);b=time.monotonic()
            offset=raw.tell();raw.write(blob);raw.flush()
            records.write(json.dumps({'index':index,'offset':offset,'bytes':len(blob),
                                      'host_start_s':a,'host_end_s':b,'sha256':hashlib.sha256(blob).hexdigest()})+'\n');records.flush()
            if index%10==0:diagnostics.append(snapshot(link,out,index))
            index+=1
    receipt.update(window_elapsed_s=time.monotonic()-started,chunks=index)
    write_json(out/'diagnostics-private.json',diagnostics)
    # 结束窗口之后才暂停：head与slots必须来自同一完整RAM文件，不能拼合运行时独立读取。
    require(link.call('JLINKARM_Halt',timeout=3)==0,'TAIL_HALT_FAILED');receipt['halt_requests']+=1
    require(link.u32(0xe000edf0)&HALT,'TAIL_NOT_HALTED');link.stable_halt()
    ram=link.read(0x20000000,131072)
    with (out/'final-paused-ram-private.bin').open('xb') as f:f.write(ram)
    link.stable_halt()
    require(hashlib.sha256(link.read(0x08000000,1048576)).hexdigest()==profile['flash_sha256'],'END_FLASH_DRIFT')
    final=identity(link);check_identity(final)
    require(final['uid_hex']==reference['uid_hex'] and final['optcr']==reference['optcr'],'END_IDENTITY_DRIFT')
    require(hashlib.sha256(link.read(0x1fffc000,16)).hexdigest()==profile['options_sha256'],'END_OPTIONS_DRIFT')
    link.stable_halt();link.call('JLINKARM_Go');receipt['go_requests']+=1
    time.sleep(.02)
    require(not link.u32(0xe000edf0)&(HALT|LOCKUP|RESET),'TAIL_RESUME_FAILED')
    receipt.update(status='CAPTURE_FILES_SAVED',tail_halt_confirmed=True,resume_confirmed=True,
                   target_end_state='RUNNING_BEFORE_CLOSE',ram_sha256=sha(out/'final-paused-ram-private.bin'))


def export(out):
    stable=StableSlots();raw=out/'running-slots-private.bin'
    with raw.open('rb') as stream:
        index=0
        while blob:=stream.read(3072):
            stable.add_running_chunk(blob,source_path=f'running-slots-private.bin@{index*3072}');index+=1
    ram=(out/'final-paused-ram-private.bin').read_bytes();head=struct.unpack_from('<I',ram,0x140)[0]
    stable.add_paused_snapshot(ram[0x1f30:0x1f30+3072],head,'final-paused-ram-private.bin',base_offset=0x1f30)
    selected=stable.select();require(len(selected.boots)==1,'CROSS_BOOT_CAPTURE')
    rows=[]
    with (out/'stable-raw-private.csv').open('x',newline='',encoding='utf-8') as stream:
        writer=csv.writer(stream);writer.writerow(['source_seq','device_ms','irq_cycles','status_raw','flags_raw','ch1_raw','ch2_raw','integrity'])
        for seq,blob in sorted(selected.frames.items()):
            f=unpack_slot_fields(blob);rows.append(f)
            writer.writerow([seq,f['device_tick_raw'],f['irq_cycles_raw'],f['status_raw'],f['flags_raw'],f['ch1_raw'],f['ch2_raw'],selected.integrity_by_seq[seq]])
    require(rows,'NO_STABLE_FRAMES')
    gaps=sum(max(0,b['source_seq']-a['source_seq']-1) for a,b in zip(rows,rows[1:]))
    summary={'stable_frames':len(rows),'first_sequence':rows[0]['source_seq'],'last_sequence':rows[-1]['source_seq'],
             'source_missing_within_span':gaps,'pending':len(selected.pending),
             'multi_repeat_conflicts':len(selected.multi_repeat_conflicts),'paused_conflicts':len(selected.paused_conflicts),
             'boot_count':len(selected.boots),'ch2_near_rail_fraction':sum(abs(f['ch2_raw'])>=8220835 for f in rows)/len(rows),
             'ch1_near_rail_fraction':sum(abs(f['ch1_raw'])>=8220835 for f in rows)/len(rows),
             'input_accuracy':'NOT_EVALUATED','peak_events':'NOT_LIVE_PER_BEAT_OFFLINE_REPLAY_REQUIRED'}
    # 每个槽版本/选择来源留存，后续精确C回放可追溯；绝不补点或以多数票掩盖双重复冲突。
    with (out/'slot-observations-private.jsonl').open('x',encoding='utf-8') as stream:
        from dataclasses import asdict
        for o in stable.observations:stream.write(json.dumps(asdict(o))+'\n')
    write_json(out/'export-summary-private.json',summary)
    return summary


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--prepare',action='store_true');p.add_argument('--profile',type=Path,required=True)
    for n in ('dll','card','out','source_record'):p.add_argument('--'+n.replace('_','-'),type=Path)
    p.add_argument('--card-sha256');p.add_argument('--seconds',type=int,choices=(10,90),default=10)
    args=p.parse_args()
    require(args.profile.resolve().is_relative_to(PRIVATE.resolve()),'PRIVATE_PROFILE_REQUIRED')
    if args.prepare:
        prepare(args.profile);print(json.dumps({'status':'CAPTURE_PROFILE_PREPARED','sha256':sha(args.profile)}));return 0
    require(args.out.resolve().is_relative_to(PRIVATE.resolve()),'OUTPUT_NOT_RESTRICTED')
    require(sha(args.card)==args.card_sha256,'CARD_SHA_MISMATCH')
    profile=json.loads(args.profile.read_text('utf-8'));validate(profile)
    source=json.loads(args.source_record.read_text('utf-8'))
    require(source['data_source']=='ENGINEERING_NONHUMAN' and source['operator_ready'] is True,'SOURCE_NOT_READY')
    require(source['mode'] in ('OPEN_UNKNOWN','ORDINARY_ECG'),'SOURCE_MODE')
    if source['mode']=='ORDINARY_ECG':
        require(source['reference_bpm'] in (60,90,120) and source['battery_only'] is True
                and source['usb_disconnected'] is True and source['leads']=={'R_red':'RA','L_yellow':'LA','F_green':'RL'},'SOURCE_BINDING')
    args.out.mkdir(exist_ok=False)
    receipt={'status':'STARTED','card_sha256':args.card_sha256,'tool_sha256':sha(__file__),
             'profile_sha256':sha(args.profile),'source_record_sha256':sha(args.source_record),
             'halt_requests':0,'reset_requests':0,'go_requests':0,'flash_write_requests':0,
             'tail_halt_confirmed':False,'resume_confirmed':False,'target_end_state':'UNKNOWN'}
    link=None
    try:
        link=CaptureLink(args.dll.resolve(),args.out);collect(link,profile,args.out,args.seconds,receipt)
    except BaseException as exc:receipt.update(status='CAPTURE_STOP',error=type(exc).__name__+': '+str(exc))
    finally:
        if link:
            try:link.close()
            except BaseException as exc:receipt.update(status='CAPTURE_STOP',close_error=type(exc).__name__)
    if receipt['status']=='CAPTURE_FILES_SAVED':
        try:receipt['export']=export(args.out)
        except BaseException as exc:receipt.update(status='CAPTURE_EXPORT_FAILED',error=type(exc).__name__+': '+str(exc))
    write_json(args.out/'receipt-private.json',receipt)
    print(json.dumps({k:receipt[k] for k in ('status','error','export','target_end_state') if k in receipt}))
    return 0 if receipt['status']=='CAPTURE_FILES_SAVED' else 1


if __name__=='__main__':sys.exit(main())
