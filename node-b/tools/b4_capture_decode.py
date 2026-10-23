"""B4 C二进制取证解码与有限窗裁定；纯文件处理，不接串口或调试器。"""
import argparse
import binascii
from collections import Counter, defaultdict, deque
import json
from pathlib import Path
import struct
import b4_recovery as pkg

MAGIC=b'\xb4\xc4';SIZE=32
class Parser:
    def __init__(self):self.buffer=bytearray();self.discarded=0;self.crc_errors=0
    def feed(self,data):
        self.buffer.extend(data);rows=[]
        while len(self.buffer)>=SIZE:
            i=self.buffer.find(MAGIC)
            if i<0:
                self.discarded+=len(self.buffer)-1;del self.buffer[:-1];break
            if i:self.discarded+=i;del self.buffer[:i]
            if len(self.buffer)<SIZE:break
            packet=bytes(self.buffer[:SIZE])
            if packet[2]!=1 or not 1<=packet[3]<=10 or packet[4]>1 or packet[5]>8:
                self.discarded+=1;del self.buffer[0];continue
            if binascii.crc_hqx(packet[:30],0xffff)!=int.from_bytes(packet[30:],'little'):
                self.crc_errors+=1;del self.buffer[0];continue
            rows.append({'kind':packet[3],'bus':packet[4],'dlc':packet[5],
                         'id':int.from_bytes(packet[6:8],'little'),'tick':int.from_bytes(packet[8:12],'little'),
                         'seq':int.from_bytes(packet[12:16],'little'),'data':packet[16:24].hex(),
                         'flags':int.from_bytes(packet[24:28],'little'),
                         'wire_crc_before':self.crc_errors,'wire_discarded_before':self.discarded})
            del self.buffer[:SIZE]
        return rows

def signed_delta(a,b):return ((a-b+0x80000000)&0xffffffff)-0x80000000
def value_hash(values):
    h=2166136261
    for value in values:
        for byte in struct.pack('<I',value&0xffffffff):h=((h^byte)*16777619)&0xffffffff
    return h

def assess(rows,crc_errors=0,tail_bytes=0,discarded_after_boot=0):
    errors=[];counts=Counter();eval_counts=Counter();models=Counter();valids=Counter()
    boot=None;start=None;stop=None;last_seq=None;sequence_errors=0;start_seq=None
    anchor=None;waves=defaultdict(list);wave_times=defaultdict(list);scalars=defaultdict(lambda:deque(maxlen=10))
    matched=0;unmatched=0;pending=None;peak_tec=0;peak_rec=0;capture_drop=0;fifo_overflow=0
    eval_hr=[];eval_rr=[];quality_last=0
    for row in rows:
        kind=row['kind'];data=bytes.fromhex(row['data']);tick=row['tick']
        if kind==7:
            if boot is not None:errors.append('SECOND_BOOT_OBSERVED')
            boot=row
            if data[:4]!=b'B4C4' or row['flags']:errors.append('BOOT_IDENTITY_OR_INIT_ERROR')
        if boot is None:continue
        if last_seq is not None and row['seq']!=last_seq+1:sequence_errors+=1
        last_seq=row['seq']
        if kind==9:
            if start is not None:errors.append('SECOND_START')
            start=row;start_seq=row['seq']
            if row['flags']:errors.append('START_INIT_ERROR')
        elapsed=signed_delta(tick,start['tick']) if start else None
        evaluate=elapsed is not None and 45000<=elapsed<135000
        if kind==6:
            stop=row
            # 最后一条STOP也携带丢弃累计值，不能只相信上一个整秒的DIAG。
            capture_drop=max(capture_drop,int.from_bytes(data[4:8],'little'))
        if kind in (1,2,3,4):
            counts[(kind,row['bus'],row['id'])]+=1
            if evaluate:eval_counts[(kind,row['bus'],row['id'])]+=1
        if start is None:continue
        if kind==4 and evaluate:errors.append('C_TX_FAILURE_IN_EVALUATION')
        if kind==1:
            if row['bus']!=1:errors.append('UNEXPECTED_A_BUS_RX')
            if row['id']==0x482 and row['dlc']==8:anchor=struct.unpack('<II',data)
            if row['id'] in (0x182,0x282) and row['dlc']==8:
                stream=4 if row['id']==0x182 else 6;value,btick=struct.unpack('<iI',data)
                utc=anchor[0]*1000+signed_delta(btick,anchor[1]) if anchor else None
                waves[stream].append((utc,value,btick))
                if evaluate:wave_times[stream].append(btick)
            if row['id']==0x382 and row['dlc']==8:
                hr,rr,temp,reserved=struct.unpack('<4H',data)
                for stream,value in ((5,hr),(7,rr),(8,temp)):scalars[stream].append(value)
                if temp or reserved:errors.append('TEMP_OR_RESERVED_NOT_ZERO')
                if evaluate:eval_hr.append(hr);eval_rr.append(rr)
            if row['id']==0x682 and row['dlc']==8:
                quality_last=struct.unpack('<II',data)[0]
                if quality_last & 0x80000010:errors.append('SYNTHETIC_OR_TEMP_VALID_ON_REAL_B')
            if row['id']==0x702 and (row['dlc']!=1 or data[0] not in (0,4,5,127)):
                errors.append('BAD_HEARTBEAT')
        if kind==5:
            a,b=struct.unpack('<II',data)
            if row['id']==1:
                peak_tec=max(peak_tec,(a>>16)&255);peak_rec=max(peak_rec,a>>24)
                if a&4:errors.append('C_CAN2_BUS_OFF')
                if evaluate and a&0xffff0007:errors.append('C_CAN2_ERROR_COUNTER_IN_EVALUATION')
                fifo_overflow=max(fifo_overflow,row['flags'])
            if row['id']==2:capture_drop=max(capture_drop,a)
            if row['id']==4 and (a!=0x08000000 or b or row['flags']):errors.append('C_VECTOR_OR_FAULT')
        if kind==8:
            pending=row
        if kind==10:
            if pending is None or pending['id']!=row['id'] or pending['seq']+1!=row['seq']:
                errors.append('MODEL_METADATA_PAIR');continue
            model=pending;pending=None;stream=row['id'];n=model['flags']>>16
            last,crc=struct.unpack('<iI',bytes.fromhex(model['data']));utc=int.from_bytes(data,'little')
            if evaluate:
                models[stream]+=1;valids[(stream,bool(model['flags']&256))]+=1
            if model['flags']&0x600:errors.append('SYNTHETIC_OR_REPLAY_MODEL')
            if stream==8 and model['flags']&256:errors.append('MODEL_TEMP_VALID')
            if stream in (4,6):
                points=waves[stream];found=False
                for end in range(len(points)-1,max(-1,len(points)-250),-1):
                    if points[end][0]!=utc or points[end][1]!=last or end+1<n:continue
                    values=[p[1] for p in points[end-n+1:end+1]]
                    if value_hash(values)==crc:found=True;break
                if evaluate:
                    if found:matched+=1
                    else:unmatched+=1
            elif stream in (5,7,8) and n==1:
                if evaluate:
                    if last in scalars[stream] and value_hash([last])==crc:matched+=1
                    else:unmatched+=1
            if evaluate and not (1577836800000<=utc<1577836800000+600000):errors.append('MODEL_NOT_LOCAL_TEST_TIME')
    if boot is None:errors.append('BOOT_NOT_CAPTURED')
    if start is None:errors.append('START_NOT_CAPTURED')
    if stop is None:errors.append('STOP_NOT_CAPTURED')
    elif int.from_bytes(bytes.fromhex(stop['data'])[:4],'little')!=180000 or stop['flags']:
        errors.append('STOP_DURATION_OR_INIT_ERROR')
    if crc_errors:errors.append('SERIAL_CRC_ERROR')
    if discarded_after_boot:errors.append('SERIAL_RESYNC_AFTER_BOOT')
    if tail_bytes:errors.append('TRUNCATED_SERIAL_PACKET')
    if sequence_errors:errors.append('SERIAL_SEQUENCE_GAP')
    if capture_drop:errors.append('CAPTURE_RING_DROP')
    if fifo_overflow:errors.append('C_CAN_RX_OVERFLOW')
    if unmatched:errors.append('MODEL_VALUE_OR_SAMPLE_TIME_MISMATCH')
    if matched<100:errors.append('MODEL_EVIDENCE_INSUFFICIENT')
    for ident,low,high in ((0x182,22275,22725),(0x282,4455,4545)):
        n=eval_counts[(1,1,ident)]
        if not low<=n<=high:errors.append('EVALUATION_COUNT_'+hex(ident))
    for ident in (0x382,0x482,0x682):
        if eval_counts[(1,1,ident)]<85:errors.append('MISSING_PERIODIC_PDO_'+hex(ident))
    if eval_counts[(1,1,0x702)]<170:errors.append('HEARTBEAT_INSUFFICIENT')
    if not counts[(3,1,0)]:errors.append('NMT_START_TX_ACK_NOT_PROVEN')
    if not counts[(3,1,0x100)]:errors.append('TIME_TX_ACK_NOT_PROVEN')
    for stream,step in ((4,4),(6,20)):
        ticks=wave_times[stream]
        if any(not step-1<=signed_delta(y,x)<=step+1 for x,y in zip(ticks,ticks[1:])):
            errors.append('WAVEFORM_TIME_GAP_'+str(stream))
    return {'status':'CAN_SAVED_BASELINE_PASS_B_ADC_REVIEW_REQUIRED' if not errors else 'NOT_PASS',
            'failures':sorted(set(errors)),'raw_packet_count':len(rows),'sequence_errors':sequence_errors,
            'CRC_errors':crc_errors,'discarded_bytes_after_BOOT':discarded_after_boot,
            'capture_drops':capture_drop,'C_RX_overflow':fifo_overflow,
            'C_CAN2_peak_TEC':peak_tec,'C_CAN2_peak_REC':peak_rec,
            'evaluation_counts':{f'{k[0]}:bus{k[1]}:0x{k[2]:03x}':v for k,v in sorted(eval_counts.items())},
            'model_value_time_checks_passed':matched,'model_value_time_checks_failed':unmatched,
            'model_valid_observations':{f'{stream}:{valid}':n for (stream,valid),n in sorted(valids.items())},
            'HR_RR_simultaneous_engineering_pass':False,'source_absolute_impedance_calibrated':False,
            'window':{'warmup_ms':45000,'evaluation_ms':90000,'CAN_limit_ms':180000},
            'diagnostic_only':{'last_quality_flags':quality_last,'vitals_rows_in_evaluation':len(eval_hr)}}

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--input',type=Path,required=True)
    p.add_argument('--out',type=Path,required=True);p.add_argument('--synthetic',action='store_true');a=p.parse_args()
    source=pkg.protected(a.input,a.synthetic);pkg.protected(a.out.parent,a.synthetic)
    parser=Parser();rows=parser.feed(source.read_bytes());boot=next((r for r in rows if r['kind']==7),{})
    r=assess(rows,parser.crc_errors-boot.get('wire_crc_before',0),len(parser.buffer),
             parser.discarded-boot.get('wire_discarded_before',0))
    with a.out.open('x',encoding='utf-8') as f:json.dump(r,f,indent=2)
    print(json.dumps({'status':r['status'],'failures':r['failures']}));return 0 if not r['failures'] else 3
if __name__=='__main__':raise SystemExit(main())
