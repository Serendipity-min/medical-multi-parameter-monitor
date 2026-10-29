"""分路窗口离线联评；原G3 review及历史NOT_PASS保持原样。"""
import argparse
from collections import Counter
import json
from pathlib import Path
import struct
import b5_g3_contract as g
import b5_g3_review as old
import b5_channel_profiles as profiles

def uart_frames(folder,clocks):
    versions=g.Versions();count=0
    with (folder/'B/UART4-ring-private.bin').open('rb') as stream:
        for row in map(json.loads,(folder/'B/UART4-ring-private.jsonl').read_text().splitlines()):
            data=row['data'];blob=stream.read(1088)
            g.require(data['offset']==count*1088 and len(blob)==1088 and g.sha(blob)==data['sha256'],'CHANNEL_UART_BLOCK')
            received=struct.unpack_from('<I',blob,1024)[0]
            # ISR先增加received再发布槽；排除最新16字节，至少两份一致才归入源证据。
            for ordinal in range(max(1,received-127),received-15):
                pos=((ordinal-1)%128)*8;versions.add(ordinal,blob[pos:pos+8],data['offset']+pos)
            count+=1
        g.require(not stream.read(1),'CHANNEL_UART_EXTRA_BYTES')
    stable,bad=versions.stable();frames=[];pending=[];previous=0
    for ordinal,blob in sorted(stable.items()):
        tick,byte=struct.unpack_from('<IB',blob)
        if ordinal!=previous+1:pending=[]
        previous=ordinal
        if len(pending)<4 and byte!=(0xa4,3,7,7)[len(pending)]:
            pending=[(byte,tick,ordinal)] if byte==0xa4 else [];continue
        pending.append((byte,tick,ordinal))
        if len(pending)<12:continue
        raw=bytes(x[0] for x in pending);pending=[]
        if sum(raw[:11])&255!=raw[11]:continue
        obj=int.from_bytes(raw[5:7],'big');emissivity=raw[4]
        if not 1<=emissivity<=100 or obj>10000:continue
        utcs=set()
        for epoch,anchor,received_ms,valid in clocks:
            if valid and -100<=g.signed(tick,received_ms)<=30000:
                utcs.add(epoch*1000+g.signed(tick,anchor))
        frames.append({'ordinal_end':ordinal,'received_tick':tick,'object_centi':obj,'UTC_candidates':sorted(utcs),
                       'raw_hex':raw.hex()})
    return frames,{'blocks':count,'stable_bytes':len(stable),'unqualified_bytes':len(bad),'valid_frames':len(frames)}

def match_temperature(message,frames):
    value=g.fixed(message['value'],100);timestamp=message['timestamp']
    return [f for f in frames if f['object_centi']==value and
            any(timestamp-2500<=utc<=timestamp+1000 for utc in f['UTC_candidates'])]

def match_temperature_entry(message,frames,entry):
    g.require(entry is not None and entry['lost']==0 and entry['valid']==1,'TEMP_ENTRY_REQUIRED_OR_LOST')
    g.require(entry['seq']==message['seq'] and entry['report_utc']==message['timestamp'] and
              message['session_id']=='can-'+str(entry['epoch'])+'-'+str(entry['boot']) and
              entry['centi']==g.fixed(message['value'],100),'TEMP_ENTRY_IDENTITY_OR_VALUE')
    # 报告UTC保留PDO秒锚；使用独立记录的C入口UTC约束物理原帧，不扩大2500ms新鲜度。
    arrival=entry['arrival_utc']
    return [f for f in frames if f['object_centi']==entry['centi'] and
            any(arrival-2500<=utc<=arrival+g.CRITERIA['nominal_grid_phase_max_ms'] for utc in f['UTC_candidates'])]

def assess_b(diagnostics,t0,profile):
    result=old.assess_b(diagnostics,t0)
    result['failures']=[x for x in result['failures'] if x not in ('B_HR_VALID60','B_RR_EXPECTED_INVALID')]
    chosen=[x for x in diagnostics if t0['monotonic']+45<=x['host_monotonic']<t0['monotonic']+345]
    if profile=='ECG60' and any(not x['bio']['hr_valid'] or x['bio']['hr_reason'] or not 58<=x['bio']['hr']<=62 for x in chosen):result['failures'].append('B_HR_VALID60')
    if profile=='RR15' and any(not x['bio']['rpm_valid'] or x['bio']['rpm_reason'] or not 14<=x['bio']['rpm']<=16 or x['bio']['hr_valid'] for x in chosen):result['failures'].append('B_RR_VALID15_HR_INVALID')
    if profile=='TEMP_OBJECT':
        for x in chosen:
            t=x['temperature'];age=g.signed(x['bio']['last_sample_ms'],t['last_ms'])
            if not t['present'] or not 0<=t['object_centi']<=10000 or not -10<=age<=2500:
                result['failures'].append('B_TEMP_FRESH_SOURCE');break
    if chosen:
        first,last=chosen[0]['temperature'],chosen[-1]['temperature']
        errors={k:last[k]-first[k] for k in ('overflow','uart_errors','checksum_errors')}
        if any(errors.values()):result['failures'].append('B_NEW_TEMPERATURE_ERRORS')
        result['temperature_errors']=errors;result['temperature_new_frames']=last['frames']-first['frames']
    result['profile']=profile
    if result.get('CAN_evaluation_increments',{}).get('expired',0):result['failures'].append('B_NEW_EXPIRED_SAMPLES')
    return result

def review(folder,profile):
    g.require(profile in profiles.PROFILES,'CHANNEL_PROFILE')
    joint=g.load(folder/'joint-receipt-private.json');supervisor=g.load(folder/'supervisor-private.json')
    raw_lines=[json.loads(x) for x in (folder/'C-lines-private.jsonl').read_text().splitlines()]
    temp_entries={}
    if joint.get('source_STOP_required'):
        for row in raw_lines:
            if row['data'].startswith('B5 TEMP_ENTRY '):
                e={k:int(v) for k,v in (x.split('=') for x in row['data'][14:].split())}
                temp_entries[(e['seq'],e['epoch'],e['boot'],e['report_utc'])]=e
    g.require(joint['exit_code']==0 and supervisor['supervisor_exit_code']==0 and joint['B5START_attempts']==1,'CHANNEL_CAPTURE_INCOMPLETE')
    g.require(g.load(folder/'B/receipt-private.json')['exit_code']==0 and g.load(folder/'cloud-receipt-private.json')['exit_code']==0,'CHANNEL_WORKERS_INCOMPLETE')
    t0=g.load(folder/'T0.json');arm=g.load(folder/'ARM_ATTEMPT.json');start,end=t0['evaluation_UTC_ms']
    g.require(end-start==300000 and t0['tail_end']<=arm['monotonic']+420,'CHANNEL_WINDOW')
    raw,can,clocks,reconstruction=old.reconstruct(folder);index=g.can_utc_points(can,clocks)
    uart,uart_summary=uart_frames(folder,clocks)
    events=[json.loads(x) for x in (folder/'cloud-events-private.jsonl').read_text().splitlines()]
    messages={};fail=[];max_bytes=0;points={'ECG':{},'RESP':{}};mapping=Counter();expected=set();duplicates=0
    for row in events:
        if row['kind']!='BROKER_RAW' or row['monotonic']<arm['monotonic'] or row['data']['retain']:continue
        x=row['data'];blob=bytes.fromhex(x['payload_hex']);max_bytes=max(max_bytes,len(blob))
        m=old.decode_mqtt(x['topic'],blob).model_dump();key=g.telemetry_key(m)
        if key in messages:
            g.require(messages[key]==m,'CHANNEL_DUPLICATE_CONFLICT');duplicates+=1;continue
        messages[key]=m
        if m['source']!='MOCK' or not m['synthetic']:fail.append('BROKER_NOT_MOCK')
        if x['qos']!=(0 if m['stream'] in ('ECG','RESP') and m['source']=='MOCK' else 1):fail.append('BROKER_QOS')
        if m['node_id']!='NODE-B' or m['stream'] not in points:continue
        rate,count=(250,100) if m['stream']=='ECG' else (50,50)
        g.require(m['sample_rate']==rate and len(m['samples'])==count,'CHANNEL_WAVE_SHAPE')
        if m['timestamp']<start or m['timestamp']-(count-1)*(1000//rate)>=end:continue
        try:
            matched=old.match_batch(m,index,can,raw)
            if m['stream']==('RESP' if profile=='RR15' else 'ECG'):expected.add(key)
            for seq,utc,value in matched:
                if start<=utc<end:
                    previous=points[m['stream']].get(seq);g.require(previous is None or previous==(utc,value),'CHANNEL_REUSED_POINT')
                    points[m['stream']][seq]=(utc,value)
        except ValueError as error:mapping[str(error)]+=1
    if mapping:fail.append('WAVE_SOURCE_MAPPING')
    if max_bytes>2047:fail.append('MQTT_2048')
    wave='ECG' if profile=='ECG60' else 'RESP' if profile=='RR15' else None
    if wave:
        seq=sorted(points[wave]);stride=1 if wave=='ECG' else 5;minimum=74250 if wave=='ECG' else 14850
        if len(seq)<minimum or any(b-a!=stride for a,b in zip(seq,seq[1:])):fail.append(wave+'_SOURCE_COVERAGE_OR_GAP')
    if profile=='ECG60':
        near=0
        for seq in points['ECG']:
            value=int.from_bytes(raw[seq][6:9],'big');value=value-(1<<24) if value&0x800000 else value
            near+=abs(value)>=8220835
        if near:fail.append('CH2_NEAR_RAIL')
    selected=[m for m in messages.values() if start<=m['timestamp']<end and m['node_id']=='NODE-B']
    if any(m['session_id']!=t0['B_session'] for m in selected):fail.append('BROKER_SESSION')
    scalar='HR' if profile=='ECG60' else 'RR' if profile=='RR15' else 'TEMP'
    scalar_rows=[m for m in selected if m['stream']==scalar]
    if len(scalar_rows)<295:fail.append(scalar+'_BROKER_COVERAGE')
    if any(m['validity']!='VALID' for m in scalar_rows):fail.append(scalar+'_INVALID')
    if profile!='TEMP_OBJECT':
        lo,hi=(58,62) if profile=='ECG60' else (14,16)
        if any(m['value'] is None or not lo<=m['value']<=hi for m in scalar_rows):fail.append(scalar+'_VALUE')
        if any(m['validity']!='VALID' for m in selected if m['stream']==wave):fail.append(wave+'_INVALID')
        invalid='RR' if profile=='ECG60' else 'HR'
        if any(m['validity']!='INVALID' or m['value'] is not None for m in selected if m['stream']==invalid):fail.append(invalid+'_EXPECTED_INVALID')
    temp_matches=[]
    if profile=='TEMP_OBJECT':
        for m in scalar_rows:
            if m['value'] is None:candidates=[]
            elif joint.get('source_STOP_required'):
                ep,boot=map(int,m['session_id'].split('-')[1:])
                candidates=match_temperature_entry(m,uart,temp_entries.get((m['seq'],ep,boot,m['timestamp'])))
            else:candidates=match_temperature(m,uart)
            if not candidates:fail.append('TEMPERATURE_UART_TO_BROKER_VALUE_OR_AGE')
            temp_matches.append(len(candidates))
    wss=[x for x in events if x['kind']=='WSS_RAW' and start<=x['data']['server_time']<end];seen=set()
    if len(wss)<2900:fail.append('WSS_COVERAGE')
    for row in wss:
        s=row['data'];profiles.assert_snapshot(s,profile)
        if s['gateway_state']!='ONLINE' or s['nodes']['NODE-B']!='ONLINE':fail.append('WSS_OFFLINE')
        streams={x['stream']:x for x in s['streams'] if x['node_id']=='NODE-B'}
        if not profiles.ready_streams(streams,profile):fail.append('WSS_TARGET_CHANNEL_INVALID')
        for m in streams.values():
            original=messages.get(g.telemetry_key(m))
            if original is None:fail.append('WSS_NOT_IN_BROKER');continue
            if m['validity']=='VALID' and (m['value']!=original['value'] or m['samples']!=original['samples']):fail.append('WSS_BROKER_VALUES')
    for row in events:
        if row['kind']!='WSS_RAW' or not start<=row['data']['server_time']<end+15000:continue
        for m in row['data'].get('streams',[]):
            key=g.telemetry_key(m);original=messages.get(key)
            if original and m['validity']=='VALID' and m['value']==original['value'] and m['samples']==original['samples']:seen.add(key)
    if wave and (not expected or not expected<=seen):fail.append(wave+'_WSS_BATCH_MISSING')
    if profile=='TEMP_OBJECT' and any(g.telemetry_key(m) not in seen for m in scalar_rows):fail.append('TEMP_WSS_MESSAGE_MISSING')
    before=g.load(folder/'ARM_BACKEND_BASELINE.json')['health'];after=next(x['data'] for x in reversed(events) if x['kind']=='BACKEND_HEALTH_AFTER')
    backend={k:after[k]-before[k] for k in ('accepted','rejected','dropped')}
    if backend['accepted']!=len(messages) or backend['rejected'] or backend['dropped']:fail.append('BACKEND_ACCEPTANCE')
    diag=[json.loads(x)['data'] for x in (folder/'B/diagnostics-private.jsonl').read_text().splitlines()]
    b=assess_b(diag,t0,profile);fail.extend(b['failures'])
    lines=[json.loads(x) for x in (folder/'C-lines-private.jsonl').read_text().splitlines()]
    cs=[(x,g.parse_diag(x['data'])) for x in lines if x['data'].startswith('B5 DIAG ') and t0['monotonic']+45<=x['monotonic']<t0['monotonic']+345]
    if len(cs)<58:fail.append('CHANNEL_C_DIAGNOSTICS')
    g.require(cs,'CHANNEL_C_DIAGNOSTICS_EMPTY');chosen=[x[1] for x in cs]
    if any(b[0]['monotonic']-a[0]['monotonic']>8 for a,b in zip(cs,cs[1:])):fail.append('C_DIAGNOSTIC_GAP')
    delta={k:chosen[-1][k]-chosen[0][k] for k in ('rx','txack','txfail','overflow','uart_err','dropped','mqtt_fail')}
    if any(delta[k] for k in ('txfail','overflow','uart_err','dropped','mqtt_fail')) or delta['rx']<=0 or delta['txack']<=0:fail.append('C_NEW_LOSS_OR_ERROR')
    sessions={x['session'] for x in chosen}
    if len(sessions)!=1 or not next(iter(sessions)):fail.append('C_GATEWAY_SESSION_CHANGED')
    elif any(not m['session_id'].startswith('can-'+str(next(iter(sessions)))+'-') for m in selected):fail.append('C_BROKER_SESSION')
    if any(x['esr']&7 or x['esr']>>16 for x in chosen):fail.append('C_TEC_REC_BOFF')
    stop=g.load(folder/'C_STOP_BANNER.json');offset=stop['monotonic']-arm['monotonic']
    if not 419<=offset<=422:fail.append('MCU_STOP_TIMING')
    if joint.get('source_STOP_required'):
        source=g.load(folder/'C_STOP_SOURCE_STATE.json')['source']
        if source['business_elapsed_ms']!=420000 or source['reason']!=1 or source['phase']!=7 or source['unsynced'] or source['pending']:
            fail.append('MCU_SOURCE_STOP_OR_NETWORK_END')
        queue=[]
        for row in lines:
            if t0['monotonic']+45<=row['monotonic']<t0['monotonic']+345 and row['data'].startswith('B5 QUEUE '):
                queue.append({k:int(v) for k,v in (x.split('=') for x in row['data'][9:].split())})
        if len(queue)<58 or any(x['unsynced'] for x in queue):fail.append('C_EGRESS_QUEUE_EVIDENCE')
        elif any(queue[-1][k]!=queue[0][k] for k in ('replaced','overflow','expired')):fail.append('C_NEW_REALTIME_LOSS_OR_EXPIRY')
    post=[x['data'] for x in events if x['kind']=='WSS_RAW' and x['monotonic']>=arm['monotonic']+435]
    if not post or not any(x['gateway_state'] in ('OFFLINE','STALE') for x in post):fail.append('NATURAL_OFFLINE_NOT_OBSERVED')
    fail=sorted(set(fail))
    return {'status':'B5_SEPARATE_'+profile+('_ENGINEERING_PASS' if not fail else '_NOT_PASS'),
        'exit_code':3 if fail else 0,'profile':profile,'criteria':profiles.criteria(profile),'failures':fail,
        'B':b,'source_reconstruction':reconstruction,'ECG_source_points':len(points['ECG']),'RESP_source_points':len(points['RESP']),
        'source_mapping_errors':dict(mapping),'UART_source':uart_summary,'temperature_message_candidate_counts':temp_matches,
        'temperature_source_proof':'raw UART checksum/value plus source report-second interval; not unique frame identity or absolute calibration',
        'Broker_messages':len(messages),'Broker_duplicates':duplicates,'Backend_delta':backend,'WSS_snapshots':len(wss),
        'wave_batches_observed_in_WSS':len(expected&seen),'C_error_delta':delta,'C_diagnostic_count':len(cs),
        'C_diagnostic_max_gap_s':max((b[0]['monotonic']-a[0]['monotonic'] for a,b in zip(cs,cs[1:])),default=0),
        'STOP_observed_offset_s':offset,
        'evaluation_UTC_ms':[start,end],'max_MQTT_JSON_bytes':max_bytes,'original_G3_verdict_rewritten':False,
        'CPU_ROM_ROOT_CAUSE':'UNRESOLVED','temperature_absolute_accuracy':'NOT_CALIBRATED'}

def main():
    p=argparse.ArgumentParser();p.add_argument('--folder',type=Path,required=True);p.add_argument('--profile',choices=profiles.PROFILES,required=True)
    p.add_argument('--out',type=Path,required=True);a=p.parse_args();r=review(a.folder,a.profile);g.save(a.out,r)
    print(json.dumps({'status':r['status'],'exit_code':r['exit_code'],'failures':r['failures']}));return r['exit_code']

if __name__=='__main__':raise SystemExit(main())
