"""三板两组工程联评；复用冻结原件重建函数，不改旧评测结果。"""
import argparse
from collections import Counter
import json
from pathlib import Path

import abc_two_group as abc
import b5_channel_review as channel
import b5_g3_contract as g
import b5_g3_review as old


def numeric_line(line,prefix):
    return {k:int(v) for k,v in (x.split('=') for x in line[len(prefix):].split())}


def nibp_source_match(message,state):
    value=message['value']
    return (message['node_id']=='NODE-A' and message['stream']=='NIBP' and message['validity']=='VALID'
        and isinstance(value,list) and len(value)==2 and state['completion']>0
        and state['completion']==state['emitted_tick'] and state['emitted']==1
        and state['flags']&(1<<3) and state['flags']&(1<<9)
        and state['packed']==(g.fixed(value[0],10)|(g.fixed(value[1],10)<<16))
        and state['nibp_seq']==message['seq']
        and int(message['session_id'].rsplit('-',1)[1])==state['boot'])


def review(job):
    folder=job/'capture';inputs=g.load(job/'runtime-inputs-private.json');profile=inputs['channel_profile']
    joint=g.load(folder/'joint-receipt-private.json');supervisor=g.load(job/'supervisor-private.json')
    g.require(joint['exit_code']==0 and supervisor['actual_supervisor_exit_code']==0,'ABC_CAPTURE_INCOMPLETE')
    child={n:g.load(folder/n)['exit_code'] for n in ('B/receipt-private.json','cloud-receipt-private.json')}
    g.require(not any(child.values()),'ABC_WORKER_INCOMPLETE')
    arm=g.load(folder/'ARM_ATTEMPT.json');t0=g.load(folder/'T0.json');start,end=t0['evaluation_UTC_ms']
    g.require(end-start==300000 and joint['B5START_attempts']==1 and arm['bytes']==8
        and arm['command_sha256']==g.sha(b'B5START\n'),'ABC_WINDOW_OR_START')
    raw,can,clocks,reconstruction=old.reconstruct(folder);index=g.can_utc_points(can,clocks)
    uart,uart_summary=channel.uart_frames(folder,clocks)
    lines=[json.loads(x) for x in (folder/'C-lines-private.jsonl').read_text().splitlines()]
    entries={};states=[]
    for row in lines:
        line=row['data']
        if line.startswith('B5 TEMP_ENTRY '):
            e=numeric_line(line,'B5 TEMP_ENTRY ');entries[(e['seq'],e['epoch'],e['boot'],e['report_utc'])]=e
        if line.startswith('ABC A_STATE '):states.append((row['monotonic'],numeric_line(line,'ABC A_STATE ')))
    events=[json.loads(x) for x in (folder/'cloud-events-private.jsonl').read_text().splitlines()]
    messages={};fail=[];duplicates=0;maximum=0;points={'ECG':{},'RESP':{}};mapping=Counter();expected=set()
    primary,scalar,target,tolerance=('ECG','HR',60,2) if profile=='ECG60' else ('RESP','RR',18,1)
    for row in events:
        if row['kind']!='BROKER_RAW' or row['monotonic']<arm['monotonic'] or row['data']['retain']:continue
        x=row['data'];blob=bytes.fromhex(x['payload_hex']);maximum=max(maximum,len(blob))
        m=old.decode_mqtt(x['topic'],blob).model_dump();key=g.telemetry_key(m)
        if key in messages:
            g.require(messages[key]==m,'ABC_DUPLICATE_CONFLICT');duplicates+=1;continue
        messages[key]=m
        if m['source'] not in ('MOCK','REPLAY') or not m['synthetic']:fail.append('SOURCE_NOT_MOCK_OR_HISTORY')
        if x['qos']!=(0 if m['stream'] in ('ECG','RESP','PPG') else 1):fail.append('BROKER_QOS')
        if m['node_id']!='NODE-B' or m['stream'] not in points:continue
        rate,count=(250,100) if m['stream']=='ECG' else (50,50)
        g.require(m['sample_rate']==rate and len(m['samples'])==count,'ABC_WAVE_SHAPE')
        if m['timestamp']<start or m['timestamp']-(count-1)*(1000//rate)>=end:continue
        try:
            matched=old.match_batch(m,index,can,raw)
            if m['stream']==primary:expected.add(key)
            for seq,utc,value in matched:
                if start<=utc<end:
                    previous=points[m['stream']].get(seq);g.require(previous is None or previous==(utc,value),'ABC_POINT_CONFLICT')
                    points[m['stream']][seq]=(utc,value)
        except ValueError as error:mapping[str(error)]+=1
    if mapping:fail.append('WAVE_SOURCE_MAPPING')
    if maximum>2047:fail.append('MQTT_BUFFER')
    sequences=sorted(points[primary]);stride=1 if primary=='ECG' else 5;minimum=74250 if primary=='ECG' else 14850
    if len(sequences)<minimum or any(b-a!=stride for a,b in zip(sequences,sequences[1:])):fail.append('PRIMARY_SOURCE_COVERAGE_OR_GAP')
    selected=[m for m in messages.values() if start<=m['timestamp']<end]
    b_selected=[m for m in selected if m['node_id']=='NODE-B']
    if any(m['session_id']!=t0['B_session'] for m in b_selected):fail.append('B_SESSION_CHANGED')
    for stream in (scalar,'TEMP'):
        rows=[m for m in b_selected if m['stream']==stream]
        if len(rows)<295:fail.append(stream+'_BROKER_COVERAGE')
        if any(m['validity']!='VALID' or m['value'] is None for m in rows):fail.append(stream+'_INVALID')
        if stream==scalar and any(m['value'] is None or abs(m['value']-target)>tolerance for m in rows):fail.append(stream+'_VALUE')
    temp_rows=[m for m in b_selected if m['stream']=='TEMP'];temp_matched=0
    for m in temp_rows:
        if m['value'] is None:continue
        epoch,boot=map(int,m['session_id'].split('-')[1:])
        e=entries.get((m['seq'],epoch,boot,m['timestamp']))
        try:matched=channel.match_temperature_entry(m,uart,e)
        except ValueError:matched=[]
        if matched:temp_matched+=1
    if temp_matched!=len(temp_rows):fail.append('TEMP_UART_TO_BROKER_MAPPING')
    wss=[x for x in events if x['kind']=='WSS_RAW' and start<=x['data']['server_time']<end]
    if len(wss)<2900:fail.append('WSS_COVERAGE')
    seen=set();sessions={};online=0;old_masked=0
    for row in events:
        if row['kind']!='WSS_RAW' or not start<=row['data']['server_time']<end+15000:continue
        s=row['data'];abc.validate_snapshot(s)
        in_evaluation=s['server_time']<end
        if in_evaluation:
            if s['gateway_state']=='ONLINE' and all(s['nodes'][n]=='ONLINE' for n in ('NODE-A','NODE-B')):online+=1
            else:fail.append('WSS_NODE_OFFLINE')
            if abc.current_sessions(s,t0['gateway_session'],profile)!=t0['B_session']:fail.append('WSS_PRIMARY_NOT_READY')
        for m in s['streams']:
            key=g.telemetry_key(m);original=messages.get(key)
            if in_evaluation and m['node_id'] in ('NODE-A','NODE-B'):
                if m['session_id'].startswith(t0['gateway_session'].rsplit('-',1)[0]+'-'):
                    sessions.setdefault(m['node_id'],set()).add(m['session_id'])
                    if original is None:fail.append('WSS_MESSAGE_NOT_IN_BROKER')
                elif m['validity'] in ('STALE','OFFLINE') and m['value'] is None and not m['samples']:old_masked+=1
                else:fail.append('PRIOR_SESSION_REVIVED')
            if original and m['validity']=='VALID':
                if m['value']!=original['value'] or m['samples']!=original['samples']:fail.append('WSS_VALUE_MISMATCH')
                else:seen.add(key)
    if not expected or not expected<=seen:fail.append('PRIMARY_WSS_BATCH_MISSING')
    if any(g.telemetry_key(m) not in seen for m in temp_rows):fail.append('TEMP_WSS_MESSAGE_MISSING')
    if any(len(x)!=1 for x in sessions.values()):fail.append('NODE_SESSION_CHANGED')
    nibp=[m for m in messages.values() if m['node_id']=='NODE-A' and m['stream']=='NIBP' and m['validity']=='VALID' and m['source']=='MOCK']
    nibp_proofs=[]
    for m in nibp:
        matched=[s for at,s in states if nibp_source_match(m,s)]
        expired=[]
        for row in events:
            if row['kind']!='WSS_RAW' or row['data']['server_time']<=m['timestamp']+90000:continue
            for current in row['data']['streams']:
                if g.telemetry_key(current)!=g.telemetry_key(m):continue
                if current['validity']=='VALID':fail.append('NIBP_VALID_AFTER_90S')
                elif current['value'] is None:expired.append(current['validity'])
        nibp_proofs.append({'session_id':m['session_id'],'seq':m['seq'],'timestamp':m['timestamp'],'value':m['value'],
            'source_states_matched':len(matched),'WSS_seen':g.telemetry_key(m) in seen,'expiry_states_observed':dict(Counter(expired))})
        if m['timestamp']<int(arm['UTC_ms']) or not matched or g.telemetry_key(m) not in seen:fail.append('NIBP_FRESH_SOURCE_WSS_PROOF')
    if not nibp:fail.append('NEW_NIBP_NOT_OBSERVED')
    diagnostics=[json.loads(x)['data'] for x in (folder/'B/diagnostics-private.jsonl').read_text().splitlines()]
    b=channel.assess_b(diagnostics,t0,'ECG60' if profile=='ECG60' else 'TEMP_OBJECT')
    chosen=[x for x in diagnostics if t0['monotonic']+45<=x['host_monotonic']<t0['monotonic']+345]
    if profile=='RR18' and any(not x['bio']['rpm_valid'] or abs(x['bio']['rpm']-18)>1 for x in chosen):b['failures'].append('B_RR18_INVALID')
    if any(not x.get('temperature_observation',{}).get('qualified') for x in chosen):b['failures'].append('B_TEMP_OBSERVATION_UNQUALIFIED')
    fail.extend(b['failures']);counters={}
    for prefix,label in (('B5 DIAG ','B_CAN'),('ABC A_CAN ','A_CAN')):
        rows=[numeric_line(x['data'],prefix) for x in lines if x['data'].startswith(prefix) and t0['monotonic']+45<=x['monotonic']<t0['monotonic']+345]
        if len(rows)<58:fail.append(label+'_DIAGNOSTIC_COVERAGE')
        if rows:
            counters[label]={k:rows[-1][k]-rows[0][k] for k in ('rx','txack','txfail','overflow')}
            if counters[label]['rx']<=0 or counters[label]['txack']<=0 or any(x['txfail'] or x['overflow'] or x['esr']&7 or x['esr']>>16 for x in rows):fail.append(label+'_LOSS_OR_ERROR')
    before=g.load(folder/'ARM_BACKEND_BASELINE.json')['health'];after=next(x['data'] for x in reversed(events) if x['kind']=='BACKEND_HEALTH_AFTER')
    backend={k:after[k]-before[k] for k in ('accepted','rejected','dropped')}
    if backend['accepted']!=len(messages) or backend['rejected'] or backend['dropped']:fail.append('BACKEND_ACCEPTANCE')
    source=g.load(folder/'C_STOP_SOURCE_STATE.json')['source']
    if source['business_elapsed_ms']!=420000 or source['reason']!=1 or source['phase']!=7 or source['unsynced'] or source['pending']:fail.append('SOURCE_STOP')
    post=[x['data'] for x in events if x['kind']=='WSS_RAW' and x['monotonic']>=arm['monotonic']+435]
    if not any(x['gateway_state'] in ('OFFLINE','STALE') for x in post):fail.append('NATURAL_OFFLINE_NOT_OBSERVED')
    observations=job/'browser-observations-private.jsonl'
    browser=[json.loads(x) for x in observations.read_text().splitlines()] if observations.exists() else []
    if not browser:fail.append('ACTUAL_WEBPAGE_NOT_OBSERVED')
    visible_nibp=[]
    for row in browser:
        v=row['visible']
        for m in nibp:
            if (v['pressure-sys']==str(round(m['value'][0])) and v['pressure-dia']==str(round(m['value'][1]))
                    and (v['state-NIBP'] or '').startswith('VALID') and (v['state-'+scalar] or '').startswith('VALID')
                    and (v['state-TEMP'] or '').startswith('VALID') and v['node-a']=='Node-A · ONLINE'
                    and v['node-b']=='Node-B · ONLINE'):
                visible_nibp.append({'NIBP_seq':m['seq'],'UTC_ms':row['UTC_ms'],'values':v})
                break
    if not visible_nibp:fail.append('WEBPAGE_SIMULTANEOUS_PRIMARY_TEMP_NIBP_NOT_OBSERVED')
    owner_path=job/'owner-screen-comparison-private.json'
    owner=g.load(owner_path) if owner_path.exists() else None
    if not owner or not any(m['value']==[float(owner['SYS_mmHg']),float(owner['DIA_mmHg'])] for m in nibp):fail.append('OWNER_NIBP_SCREEN_COMPARISON_MISSING')
    fail=sorted(set(fail))
    return {'status':'ABC_'+profile+('_ENGINEERING_PASS' if not fail else '_NOT_PASS'),'exit_code':3 if fail else 0,
        'profile':profile,'failures':fail,'evaluation_UTC_ms':[start,end],'B':b,'source_reconstruction':reconstruction,
        'ECG_source_points':len(points['ECG']),'RESP_source_points':len(points['RESP']),'mapping_errors':dict(mapping),
        'UART_source':uart_summary,'TEMP_Broker_count':len(temp_rows),'TEMP_source_matched':temp_matched,
        'NIBP':nibp_proofs,'Broker_messages':len(messages),'Broker_duplicates':duplicates,'Backend_delta':backend,
        'WSS_snapshots':len(wss),'WSS_both_nodes_online':online,'primary_batches_WSS_seen':len(expected&seen),
        'node_sessions':{n:sorted(s) for n,s in sessions.items()},'C_counter_increments':counters,
        'prior_session_masked_snapshots':old_masked,'history_messages':sum(m['source']=='REPLAY' for m in messages.values()),
        'max_MQTT_JSON_bytes':maximum,'actual_webpage_observations':len(browser),'actual_child_exit_codes':child,
        'webpage_simultaneous_readings':visible_nibp[:1],'owner_screen_comparison':owner,
        'source_STOP':source,'absolute_BP_TEMP_accuracy':'NOT_CALIBRATED_REQUIRES_OWNER_SCREEN_COMPARISON',
        'RR_HR_source_truth':'SOURCE_UNKNOWN_ROOT_CAUSE_UNRESOLVED','old_verdicts_rewritten':False}


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--job',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args()
    g.private.protected(a.job,False);result=review(a.job);g.save(a.out,result)
    print(json.dumps(result,ensure_ascii=False));raise SystemExit(result['exit_code'])
