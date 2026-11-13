"""M0当前组合联评；复用冻结原码/温度匹配函数，不改旧结果。"""
import argparse
from collections import Counter
import json
from pathlib import Path

import abc_two_group_review as abc
import b5_channel_review as channel
import b5_g3_contract as g
import b5_g3_review as old
import m0_field


def state_snapshots(events,begin,utc_bounds):
    # 同时限定既有源UTC窗口与主机活动窗口，排除缓存晚到的窗口前/STOP后快照。
    start,end=utc_bounds
    return [x['data'] for x in events if x['kind']=='WSS_RAW'
        and start<=x['data']['server_time']<end and begin<=x['monotonic']<begin+300]


def console_rows(rows):
    result=[];repairs=[];i=0
    tags=('B5 DIAG ','B5 TEMP_ENTRY ','UNI CAN ','UNI IRQ ','ABC A_CAN ','ABC A_STATE ','B5 WAVE ','B5 SCHED ','B5 IO ','B5 LAT ')
    markers=('UNI RECORDING','UNI ID V1 DUAL_CAN_MIC_MQTT_TTS CONFIG_RAM')
    while i<len(rows):
        row=rows[i];text=row['data']
        marker=next((m for m in markers if text.endswith(m) and not text.startswith(m)),None)
        if marker and i+1<len(rows) and text.startswith(tags):
            # 仅移走实际回执并接回紧邻的原诊断尾段，不改原始文件或时间戳。
            result.append(dict(row,data=text[:-len(marker)]+rows[i+1]['data']))
            repairs.append({'raw_row_indices':[i,i+1],'marker':marker});i+=2
        else:result.append(row);i+=1
    return result,repairs


def nibp_lifecycle(message,successors,snapshots):
    key=g.telemetry_key(message);deadline=message['timestamp']+90000
    newer={g.telemetry_key(m) for m in successors if m['timestamp']>message['timestamp']}
    replacements=[s['server_time'] for s in snapshots for m in s['streams']
        if g.telemetry_key(m) in newer and m['validity']=='VALID']
    replaced_at=min(replacements) if replacements else None
    superseded=replaced_at is not None and replaced_at<=deadline
    expired=any(s['server_time']>deadline and g.telemetry_key(m)==key
        and m['validity']!='VALID' and m['value'] is None for s in snapshots for m in s['streams'])
    # 新完成结果替代旧值；旧值既不能在替代后复活，也不能被重收包延长90秒。
    resurrected=any(g.telemetry_key(m)==key and m['validity']=='VALID'
        and (s['server_time']>deadline or (superseded and s['server_time']>=replaced_at))
        for s in snapshots for m in s['streams'])
    return {'expiry_observed':expired,'superseded_before_expiry':superseded,
        'successor_first_seen_UTC_ms':replaced_at,'resurrected':resurrected}


def review(job):
    root=job/'capture';a=g.load(job/'runtime-inputs-private.json');t0=g.load(root/'T0.json')
    start,end=t0['evaluation_UTC_ms'];begin=t0['monotonic'];fail=[]
    g.require(end-start==300000,'M0_EXACT_300_SECOND_WINDOW')
    run=g.load(job/'receipt-private.json');recovery=None
    if run['exit_code']!=0 and (job/'stop-completion-recovery/receipt.json').exists():
        import m0_stop_completion
        m0_stop_completion.boundary(job);recovery=g.load(job/'stop-completion-recovery/receipt.json')
        g.require(recovery['exit_code']==0 and recovery['STOP_ACK_query_IDLE'] and not recovery['new_recording'],'M0_RECOVERY_NOT_COMPLETE')
    g.require(run['exit_code']==0 or recovery is not None,'M0_CAPTURE_INCOMPLETE')
    cap=next(job.glob('field-capture-*'));audio=g.load(cap/'receipt-public.json') if (cap/'receipt-public.json').exists() else g.load(cap/'receipt.json')
    if recovery:audio=recovery
    raw,can,clocks,recon=old.reconstruct(root);index=g.can_utc_points(can,clocks)
    uart,uart_summary=channel.uart_frames(root,clocks)
    events=[json.loads(x) for x in (root/'cloud-events-private.jsonl').read_text().splitlines()]
    lines=sorted([json.loads(x) for x in (root/'C-lines-private.jsonl').read_text().splitlines()],key=lambda x:x['monotonic'])
    lines,control_interleavings=console_rows(lines)
    entries={};states=[]
    for row in lines:
        line=row['data']
        if line.startswith('B5 TEMP_ENTRY '):
            e=abc.numeric_line(line,'B5 TEMP_ENTRY ');entries[(e['seq'],e['epoch'],e['boot'],e['report_utc'])]=e
        if line.startswith('ABC A_STATE '):states.append(abc.numeric_line(line,'ABC A_STATE '))
    messages={};duplicate=0
    for event in events:
        if event['kind']!='BROKER_RAW' or event['data']['retain']:continue
        d=event['data'];m=old.decode_mqtt(d['topic'],bytes.fromhex(d['payload_hex'])).model_dump();key=g.telemetry_key(m)
        if key in messages:
            if messages[key]!=m:fail.append('BROKER_DUPLICATE_CONFLICT')
            duplicate+=1
        messages[key]=m
    primary,scalar,target,tolerance=('ECG','HR',60,2) if a['channel_profile']=='ECG60' else ('RESP','RR',18,1)
    points={'ECG':{},'RESP':{}};expected=set();mapping=Counter()
    for key,m in messages.items():
        if m['source'] not in ('MOCK','REPLAY') or not m['synthetic']:fail.append('SOURCE_CHANGED')
        if m['source']!='MOCK' or m['node_id']!='NODE-B' or m['stream'] not in points:continue
        count,rate=(100,250) if m['stream']=='ECG' else (50,50)
        if m['sample_rate']!=rate or len(m['samples'])!=count:fail.append('WAVE_ABI');continue
        if m['timestamp']<start or m['timestamp']-(count-1)*(1000//rate)>=end:continue
        try:
            matched=old.match_batch(m,index,can,raw)
            if m['stream']==primary:expected.add(key)
            for seq,utc,value in matched:
                if start<=utc<end:
                    previous=points[m['stream']].get(seq)
                    if previous is not None and previous!=(utc,value):fail.append('SOURCE_POINT_CONFLICT')
                    points[m['stream']][seq]=(utc,value)
        except ValueError as error:mapping[str(error)]+=1
    if mapping:fail.append('WAVE_SOURCE_MAPPING')
    seq=sorted(points[primary]);stride=1 if primary=='ECG' else 5;minimum=74250 if primary=='ECG' else 14850
    if len(seq)<minimum or any(y-x!=stride for x,y in zip(seq,seq[1:])):fail.append('PRIMARY_COVERAGE_OR_GAP')
    selected=[m for m in messages.values() if m['source']=='MOCK' and m['node_id']=='NODE-B' and start<=m['timestamp']<end]
    for name in (scalar,'TEMP'):
        rows=[m for m in selected if m['stream']==name]
        if len(rows)<295 or any(m['validity']!='VALID' or m['value'] is None for m in rows):fail.append(name+'_COVERAGE_OR_VALIDITY')
        if name==scalar and any(m['value'] is None or abs(m['value']-target)>tolerance for m in rows):fail.append(name+'_VALUE')
    temp=[m for m in selected if m['stream']=='TEMP'];temp_matched=0
    for m in temp:
        epoch,boot=map(int,m['session_id'].split('-')[1:]);entry=entries.get((m['seq'],epoch,boot,m['timestamp']))
        try:matched=channel.match_temperature_entry(m,uart,entry)
        except ValueError:matched=[]
        temp_matched+=bool(matched)
    if temp_matched!=len(temp):fail.append('TEMP_RAW_TO_BROKER_MAPPING')
    snapshots=state_snapshots(events,begin,(start,end))
    if len(snapshots)<2900:fail.append('WSS_COVERAGE')
    seen=set();max_temp_age=0
    for s in snapshots:
        if s['gateway_state']!='ONLINE' or s['nodes']['NODE-B']!='ONLINE':fail.append('WSS_B_OR_GATEWAY_OFFLINE')
        if a['topology']=='ABC' and s['nodes']['NODE-A']!='ONLINE':fail.append('WSS_A_OFFLINE')
        if a['topology']=='BC' and s['nodes']['NODE-A']!='OFFLINE':fail.append('BC_UNEXPECTED_A_ONLINE')
        if m0_field.b_session(s,t0['gateway_session'],a['channel_profile'])!=t0['B_session']:fail.append('WSS_PRIMARY_OR_TEMP_NOT_READY')
        for m in s['streams']:
            original=messages.get(g.telemetry_key(m))
            if original and m['validity']=='VALID':
                if m['value']!=original['value'] or m['samples']!=original['samples']:fail.append('WSS_VALUE_MISMATCH')
                else:seen.add(g.telemetry_key(m))
            if m['node_id']=='NODE-B' and m['stream']=='TEMP' and m['validity']=='VALID':max_temp_age=max(max_temp_age,s['server_time']-m['timestamp'])
    # 沿用旧ABC评测的15秒送达尾段；源数据评价范围仍严格为300秒。
    for event in events:
        if event['kind']!='WSS_RAW':continue
        if not (end<=event['data']['server_time']<end+15000 or begin+300<=event['monotonic']<begin+315):continue
        for m in event['data']['streams']:
            original=messages.get(g.telemetry_key(m))
            if original and m['validity']=='VALID' and m['value']==original['value'] and m['samples']==original['samples']:
                seen.add(g.telemetry_key(m))
    if not expected or not expected<=seen:fail.append('PRIMARY_WSS_BATCH_MISSING')
    if any(g.telemetry_key(m) not in seen for m in temp):fail.append('TEMP_WSS_MISSING')
    if max_temp_age>5000:fail.append('TEMP_FIVE_SECOND_FRESHNESS')
    diagnostics=[json.loads(x)['data'] for x in (root/'B/diagnostics-private.jsonl').read_text().splitlines()]
    old_t0=dict(t0,monotonic=begin-45)
    b=channel.assess_b(diagnostics,old_t0,'ECG60' if a['channel_profile']=='ECG60' else 'TEMP_OBJECT');fail.extend(b['failures'])
    chosen=[d for d in diagnostics if begin<=d['host_monotonic']<begin+300]
    if any(not d.get('temperature_observation',{}).get('qualified') for d in chosen):fail.append('B_TEMP_SOURCE_UNQUALIFIED')
    if primary=='RESP' and any(not d['bio']['rpm_valid'] or d['bio']['rpm_reason'] or abs(d['bio']['rpm']-18)>1 for d in chosen):fail.append('B_RR18')
    counters={}
    for prefix,label in (('B5 DIAG ','B_CAN'),('ABC A_CAN ','A_CAN')):
        rows=[abc.numeric_line(r['data'],prefix) for r in lines if r['data'].startswith(prefix) and begin<=r['monotonic']<begin+300]
        required=label=='B_CAN' or a['topology']=='ABC'
        if len(rows)<58:fail.append(label+'_DIAGNOSTIC_COVERAGE')
        if rows:
            counters[label]={k:rows[-1][k]-rows[0][k] for k in ('rx','txack','txfail','overflow')}
            if required and (counters[label]['rx']<=0 or counters[label]['txack']<=0):fail.append(label+'_NO_PHYSICAL_TRAFFIC')
            if any(x['txfail'] or x['overflow'] or x['esr']&7 or x['esr']>>16 for x in rows):fail.append(label+'_ERROR')
    irq=[abc.numeric_line(r['data'],'UNI IRQ ') for r in lines if r['data'].startswith('UNI IRQ ') and begin<=r['monotonic']<begin+300]
    if len(irq)<58 or any(x['group']!=3 or x['can_b']!=3 or x['dma']!=8 or (a['topology']=='ABC' and x['can_a']!=3) for x in irq):fail.append('ACTUAL_IRQ_PRIORITY')
    if irq and (irq[-1]['calls_b']<=irq[0]['calls_b'] or (a['topology']=='ABC' and irq[-1]['calls_a']<=irq[0]['calls_a'])):fail.append('ACTUAL_CAN_IRQ_NO_PROGRESS')
    uni=[abc.numeric_line(r['data'],'UNI CAN ') for r in lines if r['data'].startswith('UNI CAN ') and begin<=r['monotonic']<begin+300]
    if not uni or any(x['mask']!=(2 if a['topology']=='BC' else 3) or x['replay_a'] or x['replay_b'] or x['network_fault'] for x in uni):fail.append('PHYSICAL_TOPOLOGY_OR_REPLAY')
    before=g.load(root/'ARM_BACKEND_BASELINE.json')['health'];after=next(x['data'] for x in reversed(events) if x['kind']=='BACKEND_HEALTH_AFTER')
    backend={k:after[k]-before[k] for k in ('accepted','rejected','dropped')}
    if backend['accepted']!=len(messages) or backend['rejected'] or backend['dropped']:fail.append('BACKEND_ACCEPTANCE')
    nibp=[]
    if a['topology']=='ABC':
        owner_path=job/'owner-confirmation-private.json';owner=g.load(owner_path) if owner_path.exists() else {}
        completed=[m for m in messages.values() if m['source']=='MOCK' and m['node_id']=='NODE-A' and m['stream']=='NIBP' and m['validity']=='VALID']
        for m in completed:
            matched=sum(abc.nibp_source_match(m,s) for s in states)
            lifecycle=nibp_lifecycle(m,completed,snapshots)
            nibp.append({'value':m['value'],'timestamp':m['timestamp'],'source_matches':matched,**lifecycle,'WSS_seen':g.telemetry_key(m) in seen})
            if (not matched or not (lifecycle['expiry_observed'] or lifecycle['superseded_before_expiry'])
                    or lifecycle['resurrected'] or g.telemetry_key(m) not in seen or m['timestamp']<start):fail.append('NIBP_NEW_SOURCE_OR_EXPIRY')
        if not nibp or owner.get('NIBP') not in [m['value'] for m in nibp]:fail.append('NIBP_OWNER_SCREEN_MATCH')
    if audio['exit_code'] or audio.get('broker_chunks')!=125 or not audio.get('STOP_ACK_query_IDLE'):fail.append('VOICE_AND_LOCAL_STOP')
    owner_path=job/'owner-confirmation-private.json';owner=g.load(owner_path) if owner_path.exists() else {}
    if not owner.get('speaker_heard_and_matches') or not owner.get('ASR_matches_source'):fail.append('VOICE_OWNER_CONFIRMATION')
    browser=g.load(job/'browser-receipt-public.json') if (job/'browser-receipt-public.json').exists() else {}
    if browser.get('exit_code')!=0 or browser.get('observations',0)<290:fail.append('ACTUAL_WEBPAGE')
    visible_nibp=[]
    if a['topology']=='ABC':
        for line in (job/'browser-observations-private.jsonl').read_text().splitlines():
            row=json.loads(line);v=row['visible']
            if not start<=row['UTC_ms']<end:continue
            for m in nibp:
                if (v['pressure-sys']==str(round(m['value'][0])) and v['pressure-dia']==str(round(m['value'][1]))
                        and all((v['state-'+s] or '').startswith('VALID') for s in ('NIBP',scalar,'TEMP'))
                        and v['node-a']=='Node-A · ONLINE' and v['node-b']=='Node-B · ONLINE'):
                    visible_nibp.append({'UTC_ms':row['UTC_ms'],'NIBP':m['value']});break
            if visible_nibp:break
        if not visible_nibp:fail.append('WEBPAGE_SIMULTANEOUS_PRIMARY_TEMP_NIBP_NOT_OBSERVED')
    return {'status':'M0_'+a['topology']+'_'+a['channel_profile']+('_ENGINEERING_PASS_WITH_STOP_COMPLETION_RECOVERY' if not fail and recovery else '_ENGINEERING_PASS' if not fail else '_NOT_PASS'),
        'original_capture_native_exit':run['exit_code'],'post_STOP_completion_recovery':bool(recovery),
        'serial_control_interleavings_reconstructed':control_interleavings,
        'exit_code':3 if fail else 0,'failures':sorted(set(fail)),'evaluation_UTC_ms':[start,end],'B':b,'source_reconstruction':recon,
        'source_points':{k:len(v) for k,v in points.items()},'mapping_errors':dict(mapping),'UART_source':uart_summary,
        'TEMP_messages':len(temp),'TEMP_source_matches':temp_matched,'TEMP_max_WSS_age_ms':max_temp_age,'NIBP':nibp,'webpage_simultaneous_readings':visible_nibp,
        'Broker_messages':len(messages),'Broker_duplicates':duplicate,'Backend_delta':backend,'WSS_snapshots':len(snapshots),
        'C_CAN_delta':counters,'actual_IRQ_first_last':irq[::max(1,len(irq)-1)],'voice':audio,'browser':browser,'old_results_modified':False}


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--job',type=Path,required=True);p.add_argument('--out',type=Path);a=p.parse_args();r=review(a.job)
    g.save(a.out or a.job/'M0-review.json',r);print(json.dumps({k:v for k,v in r.items() if k not in ('voice','browser')},ensure_ascii=False));raise SystemExit(r['exit_code'])
