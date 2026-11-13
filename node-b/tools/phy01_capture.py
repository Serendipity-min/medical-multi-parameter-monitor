"""PHY01 固定单窗串口取证；默认只给计划，不复位、不刷写、不重试。"""
from collections import Counter
import argparse
import json
from pathlib import Path
import struct
import time

import b4_capture_decode as codec
import b4_recovery as recovery
from b4_serial_capture import open_port, need

PROFILES={'B60':(60000,0),'D60':(60000,0),'BD15':(15000,1),'BD300':(300000,1)}


def check_row(row,profile):
    kind=row['kind'];data=bytes.fromhex(row['data'])
    if kind==4:raise ValueError('C_TX_FAILURE')
    if kind==1:
        need(row['bus']==1,'UNEXPECTED_CAN1_RX')
        need(not row['flags']&0xffff0004,'C_RX_ERROR_COUNTER_OR_BUSOFF')
        if profile.startswith('BD'):need(row['id'] not in (0x182,0x282),'ECG_STREAM_IN_SMALL_FRAME_WINDOW')
        if row['id'] in (0x82,0x84):need(not int.from_bytes(data[:2],'little') and not data[2],'SOURCE_EMCY_ERROR')
    if kind==5:
        a,b=struct.unpack('<II',data)
        if row['id']==1:need(not(a&0xffff0004) and not row['flags'],'C_CAN2_ERROR_OR_OVERFLOW')
        if row['id']==2:need(not a and not row['flags'],'C_CAPTURE_OR_INIT_ERROR')
        if row['id']==4:need(codec.vector_diagnostic_ok(a,b,row['flags'],True),'C_VECTOR_OR_FAULT')
        if row['id']==5:need(not b and not row['flags'],'C_TX_FAILED_OR_BUSOFF')
        if row['id']==7:need((a,row['flags'])==PROFILES[profile] and b==500000,'C_WRONG_PROFILE')


def assess(rows,profile,crc_errors=0,discarded=0,tail_bytes=0):
    failures=[];start=next((r for r in rows if r['kind']==9),None)
    stop=next((r for r in rows if r['kind']==6),None);limit,_=PROFILES[profile]
    if not start or sum(r['kind']==9 for r in rows)!=1:failures.append('START_EVIDENCE')
    if not stop or sum(r['kind']==6 for r in rows)!=1:failures.append('STOP_EVIDENCE')
    elif int.from_bytes(bytes.fromhex(stop['data'])[:4],'little')!=limit or stop['flags']:failures.append('STOP_LIMIT_OR_ERROR')
    if any(b['seq']!=a['seq']+1 for a,b in zip(rows,rows[1:])):failures.append('SERIAL_SEQUENCE_GAP')
    if crc_errors or discarded or tail_bytes:failures.append('SERIAL_INTEGRITY')
    for row in rows:
        try:check_row(row,profile)
        except ValueError as e:failures.append(str(e))
    counts=Counter(hex(r['id']) for r in rows if r['kind']==1)
    result={'profile':profile,'window_ms':limit,'CAN_RX_counts':dict(counts),'CRC_errors':crc_errors,
            'discarded_bytes':discarded,'truncated_bytes':tail_bytes,'scope':'REAL_CAN_ONLY_NOT_CLOUD_OR_ANALOG_EYE'}
    if profile=='B60':
        body=[r for r in rows if r['kind']!=7]
        old=codec.assess(body,crc_errors,tail_bytes,discarded,True,False,
                         window_ms=60000,warmup_ms=20000,evaluation_ms=35000)
        failures.extend(old['failures']);result['B_capture_review']=old
        selected=[r for r in rows if start and 20000<=r['tick']-start['tick']<55000]
        hr=[struct.unpack('<4H',bytes.fromhex(r['data']))[0] for r in selected if r['kind']==1 and r['id']==0x382]
        quality=[struct.unpack('<II',bytes.fromhex(r['data']))[0] for r in selected if r['kind']==1 and r['id']==0x682]
        if len(hr)<30 or any(not 5800<=v<=6200 for v in hr):failures.append('HR_NOT_VALID_NOMINAL60')
        if len(quality)<30 or any(q&5!=5 for q in quality):failures.append('ECG_HR_QUALITY_NOT_VALID')
        result['HR_centi_bpm_values']=dict(Counter(map(str,hr)))
    else:
        minimum=60 if profile=='D60' else 8
        hbs=[r for r in rows if r['kind']==1 and r['id']==0x704 and bytes.fromhex(r['data'])[0]==5]
        if len(hbs)<minimum:failures.append('D_OPERATIONAL_HEARTBEAT_INSUFFICIENT')
        if profile.startswith('BD'):
            b=[r for r in rows if r['kind']==1 and r['id']==0x702 and bytes.fromhex(r['data'])[0]==127]
            if len(b)<8:failures.append('B_PREOP_HEARTBEAT_INSUFFICIENT')
            for command in (b'\x80\x02',b'\x01\x04'):
                if not any(r['kind']==3 and r['id']==0 and bytes.fromhex(r['data'])[:2]==command for r in rows):failures.append('SMALL_FRAME_NMT_ACK_MISSING')
        raw_values=[];qualities=[];valid_models=[];matched=0;last_model=None
        for r in rows:
            if r['kind']==1 and r['id']==0x684:qualities.append(struct.unpack('<II',bytes.fromhex(r['data']))[0])
            if r['kind']==1 and r['id']==0x384:
                hr,rr,temp,age=struct.unpack('<4H',bytes.fromhex(r['data']))
                if hr or rr:failures.append('D_WRONG_ROLE_VITALS')
                raw_values.append((r['tick'],temp,age))
            if r['kind']==8:last_model=r
            if r['kind']==10 and last_model and last_model['seq']+1==r['seq']:
                f=last_model
                if f['id']==8 and f['flags']&255==4 and f['flags']&256:
                    value,hashed=struct.unpack('<iI',bytes.fromhex(f['data']))
                    candidates=[v for t,v,age in raw_values[-5:] if age<=2500 and 0<=r['tick']-t<=1500]
                    good=f['flags']>>16==1 and value in candidates and codec.value_hash([value])==hashed and not f['flags']&0x600
                    if good:matched+=1
                    else:failures.append('D_MODEL_RAW_VALUE_MISMATCH')
                    stamp=int.from_bytes(bytes.fromhex(r['data']),'little')
                    if not 1577836800000-2500<=stamp<1577836800000+limit+10000:failures.append('D_MODEL_TIME_OUTSIDE_LOCAL_TEST')
                    valid_models.append(value)
        if not any(q&16 for q in qualities):failures.append('NO_D_VALID_TEMPERATURE_QUALITY')
        if len(valid_models)<(40 if profile=='D60' else 5):failures.append('D_VALID_MODEL_INSUFFICIENT')
        if not counts.get('0x484'):failures.append('D_TIME_ANCHOR_MISSING')
        result.update(D_valid_models=len(valid_models),D_raw_model_matches=matched,
            D_received_temperature_C_range=[min(valid_models)/100,max(valid_models)/100] if valid_models else None,
            D_raw_max_age_ms=max((age for _,_,age in raw_values),default=None))
    esr=[];ack=None;drop=overflow=0
    for r in rows:
        if r['kind']==5:
            a,b=struct.unpack('<II',bytes.fromhex(r['data']))
            if r['id']==1:esr.append(a);overflow=max(overflow,r['flags'])
            if r['id']==2:drop=max(drop,a)
            if r['id']==5:ack={'acked':a,'failed':b,'busoff':r['flags']}
        if r['kind']==6:drop=max(drop,int.from_bytes(bytes.fromhex(r['data'])[4:8],'little'))
    if drop or overflow:failures.append('CAPTURE_OR_FIFO_DROP')
    if not ack or not ack['acked']:failures.append('C_ACK_EVIDENCE_MISSING')
    result.update(C_peak_TEC=max(((x>>16)&255 for x in esr),default=None),
        C_peak_REC=max((x>>24 for x in esr),default=None),C_TX=ack,C_capture_drop=drop,C_RX_overflow=overflow,
        failures=sorted(set(failures)),status='CAPTURE_PASS' if not failures else 'NOT_PASS')
    return result


def capture(port,out,profile,ready_path):
    parser=codec.Parser();rows=[];sent=False;start=None;stop=None;abort=False;begin=time.monotonic();last=None;diags=set();heartbeats={};last_temp=None
    result={'status':'STOP','exit_code':1,'profile':profile};limit,_=PROFILES[profile]
    with (out/'serial-raw-private.bin').open('xb') as raw,(out/'packets-private.jsonl').open('x') as log:
        try:
            while stop is None:
                now=time.monotonic();need(now-begin<limit/1000+15,'HOST_TIMEOUT')
                need(not ready_path.with_name('SOURCE-STOP').exists(),'SOURCE_MONITOR_STOP')
                if not sent:need(now-begin<10,'IDLE_OR_SOURCE_NOT_READY')
                elif start is None:need(now-sent_at<3,'START_ACK_TIMEOUT')
                data=port.read(8192);raw.write(data)
                for row in parser.feed(data):
                    log.write(json.dumps(row)+'\n');log.flush()
                    if last:need(row['seq']==last['seq']+1,'UART_SEQUENCE_GAP')
                    if row['kind']==7:need(not rows and bytes.fromhex(row['data'])[:4]==b'B4C4' and not row['flags'],'C_UNEXPECTED_BOOT')
                    rows.append(row);last=row;check_row(row,profile)
                    if row['kind']==1 and row['id'] in (0x702,0x704):heartbeats[row['id']]=time.monotonic()
                    if row['kind']==8 and row['id']==8 and row['flags']&255==4 and row['flags']&256:last_temp=time.monotonic()
                    if row['kind']==5:diags.add(row['id'])
                    if row['kind']==9:need(sent and start is None and not row['flags'],'UNEXPECTED_START');start=row
                    if row['kind']==6:stop=row;need(start is not None and not row['flags'],'EARLY_OR_ERROR_STOP')
                if rows:
                    need(parser.crc_errors==rows[0]['wire_crc_before'] and parser.discarded==rows[0]['wire_discarded_before'],'UART_CORRUPTION')
                if not sent and rows and last and last['tick']-rows[0]['tick']>=1000 and {1,2,4,5,6,7}<=diags:
                    ready=json.loads(ready_path.read_text()) if ready_path.exists() else None
                    if ready and ready.get('ready') and 0<=now-ready['host_monotonic']<(10 if profile.startswith('BD') else 3):
                        sent=True;sent_at=time.monotonic()
                        (out/'START-intent-private.json').write_text(json.dumps({'host_monotonic':sent_at,'command_hex':b'B4START\n'.hex(),'limit_ms':limit,'profile':profile}))
                        need(port.write(b'B4START\n')==8,'START_SHORT_WRITE');port.flush()
                if sent and stop is None and time.monotonic()-sent_at>3:
                    expected=(0x702,0x704) if profile.startswith('BD') else (0x702,) if profile=='B60' else (0x704,)
                    need(all(x in heartbeats and time.monotonic()-heartbeats[x]<=1.5 for x in expected),'SOURCE_HEARTBEAT_GAP')
                    if profile!='B60':need(last_temp is not None and time.monotonic()-last_temp<=2.5,'TEMPERATURE_MODEL_STALE_OR_INVALID')
            result=assess(rows,profile,parser.crc_errors-rows[0]['wire_crc_before'],
                          parser.discarded-rows[0]['wire_discarded_before'],len(parser.buffer))
            result['exit_code']=0 if not result['failures'] else 3
        except (Exception,KeyboardInterrupt) as error:
            result.update(status='STOP',exit_code=1,reason=str(error),error_type=type(error).__name__)
            if sent and stop is None:
                abort=True
                try:result['abort_bytes']=port.write(b'X');port.flush()
                except Exception as e:result['abort_error_type']=type(e).__name__
        result.update(START_attempts=int(sent),abort_attempts=int(abort),elapsed_host_seconds=time.monotonic()-begin,
                      target_reset_flash_commands=0)
    return result


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--profile',choices=PROFILES,required=True)
    p.add_argument('--port');p.add_argument('--out',type=Path);p.add_argument('--installation',type=Path)
    p.add_argument('--ready',type=Path);p.add_argument('--execute',action='store_true');a=p.parse_args()
    if not a.execute:
        print(json.dumps({'status':'PLAN_ONLY','profile':a.profile,'limit_ms':PROFILES[a.profile][0]}));return 0
    need(a.port and a.out and a.installation and a.ready,'CAPTURE_ARGUMENTS_REQUIRED')
    recovery.protected(a.out.parent,False);recovery.protected(a.installation,False);recovery.protected(a.ready.parent,False)
    install=json.loads(a.installation.read_text())
    need(install['board']=='C' and install['exit_code']==0 and install['Close_completed']
         and install['options_unchanged'] and install['all_other_sectors_unchanged'],'C_INSTALL_PROOF_REQUIRED')
    from serial.tools import list_ports
    import serial
    need(any(p.device==a.port and p.vid==0x1a86 and p.pid==0x7523 for p in list_ports.comports()),'C_PORT_NOT_CONFIRMED_CH340')
    a.out.mkdir();port=None
    try:
        port=open_port(serial.Serial,a.port);result=capture(port,a.out,a.profile,a.ready)
    finally:
        if port:port.close()
    result['serial_closed']=True;(a.out/'receipt-private.json').write_text(json.dumps(result,indent=2))
    print(json.dumps(result));return result['exit_code']


if __name__=='__main__':raise SystemExit(main())
