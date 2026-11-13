"""G3原件离线联评：B原码/实际CAN队列→Broker→实际Backend计数/WSS，绝不连接设备。"""
import argparse
from collections import Counter
import json
from pathlib import Path
import struct
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from cloud.backend.app.adapters import decode_mqtt
import b5_g3_contract as g


def match_batch(message,index,can_rows,raw_rows):
    stream=message['stream'];rate,count,scale,stride=(250,100,1000,1) if stream=='ECG' else (50,50,1000000,5)
    g.require(message['sample_rate']==rate and len(message['samples'])==count,'G3_BATCH_RATE_COUNT')
    values=[g.fixed(x,scale) for x in message['samples']]
    candidates=index.get((stream,message['timestamp'],values[-1]),set());matched=[]
    for end in candidates:
        seqs=[end-(count-1-i)*stride for i in range(count)]
        if not all(s in can_rows and s in raw_rows for s in seqs):continue
        rows=[struct.unpack('<iiIIBB2x',can_rows[s]) for s in seqs]
        if [r[0 if stream=='ECG' else 1] for r in rows]!=values:continue
        if any(r[5] or struct.unpack_from('<I',raw_rows[s],20)[0]!=r[2] or raw_rows[s][9] for s,r in zip(seqs,rows)):continue
        # 网关只传最后一点UTC和名义率；C代码允许相位±1ms，反推两端最坏±2ms。
        if any(abs(g.signed(r[2],rows[-1][2])+(count-1-i)*(1000//rate))>2 for i,r in enumerate(rows)):continue
        matched.append([(s,message['timestamp']+g.signed(r[2],rows[-1][2]),v) for s,r,v in zip(seqs,rows,values)])
    g.require(len(matched)==1,'G3_WAVE_SOURCE_MISSING_OR_AMBIGUOUS')
    return matched[0]


def reconstruct(folder):
    raw=g.Versions();can=g.Versions();clocks=set();blocks=0;last_max=0
    rows=[json.loads(s)['data'] for s in (folder/'B/blocks-private.jsonl').read_text('utf8').splitlines()]
    with (folder/'B/blocks-private.bin').open('rb') as f:
        for row in rows:
            blob=f.read(g.BLOCK_BYTES)
            g.require(g.sha(blob)==row['sha256'] and row['offset']==blocks*g.BLOCK_BYTES,'G3_BLOCK_HASH_OR_OFFSET')
            rr,cc,clock=g.decode_block(blob)
            high=max([x[0] for x in rr],default=last_max)
            g.require(high>=last_max,'G3_RAW_BOOT_OR_SEQUENCE_RESTART');last_max=high
            for seq,b,position in rr:raw.add(seq,b,row['offset']+position)
            for seq,b,position in cc:can.add(seq,b,row['offset']+position)
            clocks.add(clock);blocks+=1
        g.require(not f.read(1),'G3_EXTRA_UNINDEXED_BYTES')
    raw_rows,raw_bad=raw.stable();can_rows,can_bad=can.stable()
    # 所有版本与冲突仍在二进制原件，认证只使用至少两次一致且无双重复冲突的版本。
    return raw_rows,can_rows,clocks,{'blocks':blocks,'raw_stable':len(raw_rows),'CAN_stable':len(can_rows),
       'raw_unqualified_sequences':len(raw_bad),'CAN_unqualified_sequences':len(can_bad),
       'raw_version_conflicts':sum(len(c)>1 for c in raw.rows.values()),'CAN_version_conflicts':sum(len(c)>1 for c in can.rows.values())}


def assess_b(diagnostics,t0):
    chosen=[x for x in diagnostics if t0['monotonic']+45<=x['host_monotonic']<t0['monotonic']+345]
    fail=[]
    if len(chosen)<590:fail.append('B_SAVED_OBSERVATIONS')
    if not chosen:return {'failures':fail,'saved':0}
    times=[x['host_monotonic'] for x in chosen]
    if times[0]>t0['monotonic']+46.5 or times[-1]<t0['monotonic']+343.5 or any(b-a>1.5 for a,b in zip(times,times[1:])):fail.append('B_DIAGNOSTIC_COVERAGE')
    if any(not x['bio']['hr_valid'] or x['bio']['hr_reason'] or not 58<=x['bio']['hr']<=62 for x in chosen):fail.append('B_HR_VALID60')
    if any(x['bio']['rpm_valid'] for x in chosen):fail.append('B_RR_EXPECTED_INVALID')
    first,last=chosen[0],chosen[-1]
    delta={k:last['CAN'][k]-first['CAN'][k] for k in first['CAN'] if k!='high_water'}
    if any(delta[k] for k in ('overflow','expired','comm_reset','app_reset_rejected','error','discontinuities')):fail.append('B_NEW_CAN_FAILURES')
    adc={k:last['bio']['adc'][k]-first['bio']['adc'][k] for k in ('bad_status','spi_errors','queue_overflow','init_errors','long_gap_count')}
    if any(adc.values()):fail.append('B_NEW_ADC_ERRORS')
    elapsed=last['bio']['last_sample_ms']-first['bio']['last_sample_ms'];samples=last['bio']['samples']-first['bio']['samples']
    sps=samples*1000/elapsed if elapsed>0 else 0
    if not 247.5<=sps<=252.5:fail.append('B_NOT_250SPS')
    if any((x['CAN1_ESR']&7) or (x['CAN1_ESR']>>16) for x in chosen):fail.append('B_TEC_REC_BOFF')
    return {'failures':fail,'saved':len(chosen),'device_domain_SPS':sps,'CAN_evaluation_increments':delta,
            'ADC_evaluation_increments':adc,'HR_values':dict(Counter(x['bio']['hr'] for x in chosen)),
            'RR_reason_masks':dict(Counter(x['bio']['rpm_reason'] for x in chosen)),
            'clipped_counter_increment':last['bio']['clipped_samples']-first['bio']['clipped_samples']}


def review(folder):
    joint=g.load(folder/'joint-receipt-private.json');supervisor=g.load(folder/'supervisor-private.json')
    g.require(joint['status']=='G3_FILES_CAPTURED_REVIEW_PENDING' and joint['exit_code']==0
              and supervisor['supervisor_exit_code']==supervisor['worker_exit_code']==0,'G3_CAPTURE_END_NOT_COMPLETE')
    g.require(g.load(folder/'B/receipt-private.json')['exit_code']==0 and g.load(folder/'cloud-receipt-private.json')['exit_code']==0,
              'G3_CHILD_END_NOT_COMPLETE')
    t0=g.load(folder/'T0.json');arm=g.load(folder/'ARM_ATTEMPT.json');start,end=t0['evaluation_UTC_ms']
    g.require(joint.get('B5START_attempts')==1 and arm.get('bytes')==8
              and arm.get('command_sha256')==g.sha(b'B5START\n'),'G3_START_RECEIPT_NOT_EXACTLY_ONCE')
    g.require(end-start==300000 and t0['evaluation']==[t0['monotonic']+45,t0['monotonic']+345]
              and t0['tail_end']<=arm['monotonic']+420,'G3_WINDOW_CHANGED')
    raw_rows,can_rows,clocks,recon=reconstruct(folder);point_index=g.can_utc_points(can_rows,clocks)
    events=[json.loads(x) for x in (folder/'cloud-events-private.jsonl').read_text('utf8').splitlines()]
    failures=[];messages={};payloads={};duplicates=0;max_bytes=0;ecg_points={};resp_points={};transport_failures=[];expected_ecg=set()
    for row in events:
        if row['kind']!='BROKER_RAW' or row['monotonic']<arm['monotonic'] or row['data']['retain']:continue
        x=row['data'];blob=bytes.fromhex(x['payload_hex']);max_bytes=max(max_bytes,len(blob))
        message=decode_mqtt(x['topic'],blob).model_dump();key=g.telemetry_key(message)
        expected_qos=0 if message['stream'] in ('ECG','RESP') and message['source']=='MOCK' else 1
        if x.get('qos')!=expected_qos:failures.append('BROKER_QOS_POLICY_MISMATCH')
        if key in messages:
            g.require(payloads[key]==blob,'G3_DUPLICATE_KEY_PAYLOAD_CONFLICT');duplicates+=1;continue
        messages[key]=message;payloads[key]=blob
        if message['source']!='MOCK' or not message['synthetic']:failures.append('BROKER_NOT_MOCK')
        if message['node_id']=='NODE-B' and message['stream'] in ('ECG','RESP'):
            rate,count=(250,100) if message['stream']=='ECG' else (50,50)
            g.require(message['sample_rate']==rate and len(message['samples'])==count,'G3_BATCH_RATE_COUNT')
            if message['timestamp']<start or message['timestamp']-(count-1)*(1000//rate)>=end:continue
            try:
                points=match_batch(message,point_index,can_rows,raw_rows)
                if message['stream']=='ECG':expected_ecg.add(key)
                target=ecg_points if message['stream']=='ECG' else resp_points
                for seq,utc,value in points:
                    if start<=utc<end:
                        if seq in target and target[seq]!=(utc,value):raise ValueError('G3_POINT_REUSED_CONFLICT')
                        target[seq]=(utc,value)
            except ValueError as e:transport_failures.append(str(e))
    if max_bytes>2047:failures.append('MQTT_BUFFER_2048')
    if transport_failures:failures.append('B_QUEUE_TO_BROKER_WAVE_MAPPING')
    for label,points,minimum,stride in [('ECG',ecg_points,74250,1),('RESP',resp_points,14850,5)]:
        seqs=sorted(points)
        if len(points)<minimum or any(b-a!=stride for a,b in zip(seqs,seqs[1:])):failures.append(label+'_SOURCE_COVERAGE_OR_GAP')
    near=0
    for seq in ecg_points:
        b=raw_rows[seq];v=int.from_bytes(b[6:9],'big');v=v-(1<<24) if v&0x800000 else v
        near+=abs(v)>=8220835
    if near:failures.append('CH2_NEAR_RAIL')
    selected=[m for m in messages.values() if start<=m['timestamp']<end]
    if any(m['validity']!='VALID' for m in selected if m['stream']=='ECG'):failures.append('BROKER_ECG_NOT_ALL_VALID')
    if any(m['session_id']!=t0['B_session'] for m in selected if m['node_id']=='NODE-B'):failures.append('BROKER_B_SESSION_CHANGED')
    for stream in ('HR','RR','TEMP'):
        rows=[m for m in selected if m['node_id']=='NODE-B' and m['stream']==stream]
        if len(rows)<295:failures.append(stream+'_BROKER_COVERAGE')
        if stream=='HR' and any(m['validity']!='VALID' or not 58<=m['value']<=62 for m in rows):failures.append('BROKER_HR_VALID60')
        if stream!='HR' and any(m['validity']!='INVALID' or m['value'] is not None for m in rows):failures.append('BROKER_'+stream+'_INVALID')
    wss=[x for x in events if x['kind']=='WSS_RAW' and start<=x['data']['server_time']<end]
    seen=set()
    if len(wss)<2900:failures.append('WSS_COVERAGE')
    for row in wss:
        snap=row['data'];g.assert_snapshot(snap)
        if snap['gateway_state']!='ONLINE' or snap['nodes']['NODE-B']!='ONLINE':failures.append('WSS_NODE_NOT_ONLINE')
        streams={x['stream']:x for x in snap['streams'] if x['node_id']=='NODE-B'}
        if not {'ECG','HR','RR','TEMP'}<=streams.keys():failures.append('WSS_MISSING_STREAM');continue
        if streams['HR']['validity']!='VALID' or not 58<=streams['HR']['value']<=62:failures.append('WSS_HR_VALID60')
        if streams['ECG']['validity']!='VALID' or len(streams['ECG']['samples'])!=100 or streams['ECG']['sample_rate']!=250:failures.append('WSS_ECG_NOT_VALID100_250')
        for m in streams.values():
            key=g.telemetry_key(m);original=messages.get(key)
            if original is None:failures.append('WSS_MESSAGE_NOT_IN_BROKER');continue
            if m['validity']=='VALID':
                if m['value']!=original['value'] or m['samples']!=original['samples']:failures.append('BROKER_WSS_VALUE_MISMATCH')
                seen.add(key)
    # 15秒尾段用于收齐跨源UTC边界的完整批次；不扩大300秒生理评价窗口。
    for row in events:
        if row['kind']!='WSS_RAW' or not start<=row['data']['server_time']<end+15000:continue
        for m in row['data'].get('streams',[]):
            key=g.telemetry_key(m);original=messages.get(key)
            if (m['stream']=='ECG' and m['validity']=='VALID' and original is not None
                    and m['samples']==original['samples'] and m['value']==original['value']):seen.add(key)
    if not expected_ecg or not expected_ecg<=seen:failures.append('ECG_BATCH_NOT_OBSERVED_IN_WSS')
    before=g.load(folder/'ARM_BACKEND_BASELINE.json')['health']
    after=next(x['data'] for x in reversed(events) if x['kind']=='BACKEND_HEALTH_AFTER')
    backend_delta={k:after[k]-before[k] for k in ('accepted','rejected','dropped')}
    if backend_delta['accepted']!=len(messages) or backend_delta['rejected'] or backend_delta['dropped']:failures.append('ACTUAL_BACKEND_ACCEPTANCE_OR_DROP')
    diagnostics=[json.loads(x)['data'] for x in (folder/'B/diagnostics-private.jsonl').read_text('utf8').splitlines()]
    b_result=assess_b(diagnostics,t0);failures.extend(b_result['failures'])
    serial=[json.loads(x) for x in (folder/'C-lines-private.jsonl').read_text('utf8').splitlines()]
    cdiag=[(x,g.parse_diag(x['data'])) for x in serial if x['data'].startswith('B5 DIAG ')]
    cs=[(x,d) for x,d in cdiag if t0['monotonic']+45<=x['monotonic']<t0['monotonic']+345]
    if len(cs)<58:failures.append('C_DIAG_COVERAGE')
    if any(b[0]['monotonic']-a[0]['monotonic']>8 for a,b in zip(cs,cs[1:])):failures.append('C_DIAG_GAP')
    cdelta={}
    if cs:
        cdelta={k:cs[-1][1][k]-cs[0][1][k] for k in ('rx','txack','txfail','overflow','uart_err','dropped','mqtt_fail','q0_transport','q1_puback')}
        if any(cdelta[k] for k in ('txfail','overflow','uart_err','dropped','mqtt_fail')) or cdelta['rx']<=0 or cdelta['txack']<=0:failures.append('C_CAN_OR_QUEUE_FAILURE')
        sessions={d['session'] for x,d in cs}
        if len(sessions)!=1 or next(iter(sessions))==0:failures.append('C_GATEWAY_SESSION_CHANGED')
        elif any(not m['session_id'].startswith('can-'+str(next(iter(sessions)))+'-') for m in selected):failures.append('C_BROKER_SESSION_NOT_MATCHED')
    stop_proof=g.load(folder/'C_STOP_BANNER.json')
    if not arm['monotonic']+419<=stop_proof['monotonic']<=arm['monotonic']+422:failures.append('MCU_STOP_NOT_IN_FROZEN_BOUND')
    post=[x['data'] for x in events if x['kind']=='WSS_RAW' and x['monotonic']>=arm['monotonic']+435]
    if not post or not any(x['gateway_state'] in ('OFFLINE','STALE') for x in post):failures.append('NATURAL_OFFLINE_NOT_OBSERVED')
    failures=sorted(set(failures))
    return {'status':'B5_G3_ECG60_MOCK_ENGINEERING_PASS' if not failures else 'B5_G3_NOT_PASS','exit_code':0 if not failures else 3,
      'failures':failures,'criteria':g.CRITERIA,'evaluation_UTC_ms':[start,end],'raw_reconstruction':recon,
      'ECG_source_points':len(ecg_points),'RESP_source_points':len(resp_points),'CH2_near_rail':near,
      'exact_value_mapping':'Actual B CAN queue fixed point -> observed Broker payload; ±2ms nominal-grid phase only, no voltage tolerance',
      'mapping_failures':dict(Counter(transport_failures)),'wave_units':'ECG nominal mV; RESP relative, not ohms',
      'Broker_unique_messages_after_arm':len(messages),'Broker_identical_duplicates':duplicates,'MQTT_max_payload_bytes':max_bytes,
      'actual_Backend_counter_delta':backend_delta,'Backend_evidence_limit':'Aggregate acceptance + actual WSS, not a server per-message acceptance trace',
      'WSS_evaluation_snapshots':len(wss),'ECG_batches_observed_in_WSS':len(expected_ecg&seen),
      'B':b_result,'C_evaluation_counter_delta':cdelta,'C_saved_diagnostics':len(cs),
      'NMT_TIME_payload_log':'NOT_AVAILABLE_IN_FROZEN_42552B; immutable path + ACK/counters/B_TIME_anchor observed',
      'AI_calls':'NOT_RUN','formal_cloud_changes':0,'CPU_ROM_ROOT_CAUSE':'UNRESOLVED',
      'independent_cold_boot':'NOT_VALIDATED','same_window_HR_RR':'NOT_VALIDATED','impedance':'NOT_CALIBRATED'}


def main():
    p=argparse.ArgumentParser();p.add_argument('--folder',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args()
    g.private.protected(a.folder,False);g.private.protected(a.out.parent,False)
    try:r=review(a.folder)
    except BaseException as e:r={'status':'G3_REVIEW_STOP','exit_code':1,'error_type':type(e).__name__,'error_text_sha256':g.sha(str(e).encode())}
    g.save(a.out,r);print(json.dumps({'status':r['status'],'exit_code':r['exit_code']}));return r['exit_code']

if __name__=='__main__':raise SystemExit(main())
