"""离线 P3，核对原件、运行 C Host 夹具并评估单所有者出口预算。"""
import argparse
from collections import Counter, defaultdict
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import re
import statistics
import subprocess

from five_node_p1_offline import decode, STREAMS

ROOT = Path(__file__).resolve().parents[2]
DOC = ROOT/'node-b/docs'
P1 = DOC/'FIVE-NODE-MIGRATION/P1-20261106/OFFLINE-RESULTS.json'
P2 = DOC/'FIVE-APPLIANCE-20261107/P2-EVIDENCE.json'
STAGES = ('AT_other_including_receive', 'CIPSEND_command_and_prompt', 'UART_binary',
          'SEND_OK_wait', 'serialize', 'MQTT_send_total', 'PUBACK_inclusive',
          'live_queue_residence', 'source_age_at_take')
WAVES = {'ecg', 'resp', 'ppg'}
BAUD_BYTES_MS = 11.52
HORIZON_MS = 110000


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def field_data(path, reference):
    source = Path(path)
    for name, evidence in reference['input_evidence'].items():
        file = source/name
        assert file.stat().st_size == evidence['bytes'] and sha(file) == evidence['sha256'], 'P1_SOURCE_CHANGED'
    start = json.loads((source/'T0.json').read_text())['UTC_ms']
    end = start+300000
    rows = [json.loads(line) for line in (source/'C-observation/lines-private.jsonl').read_text().splitlines()]
    lines = [row for row in rows if start <= row['UTC_ms'] < end]

    def select(prefix):
        return [(row['UTC_ms'], {k:int(v) for k,v in re.findall(r'(\w+)=(\d+)',row['text'])})
                for row in lines if row['text'].startswith(prefix)]

    io = select('B5 IO ')
    duration = (io[-1][0]-io[0][0])/1000
    keys = ('tx_calls','tx_ok','rx_queries','rx_empty','rx_reads')
    io_delta = {k:io[-1][1][k]-io[0][1][k] for k in keys}
    audio = select('UNI AUDIO ')
    sched = select('B5 SCHED ')
    phases = {}
    for i,name in enumerate(STAGES):
        samples = select(f'B5 LAT stage={i} ')
        first,last = samples[0][1],samples[-1][1]
        phases[name] = dict(first=first,last=last,sample_count_delta=last['n']-first['n'])
    lengths = defaultdict(list)
    wave_integrity = Counter()
    for line in (source/'receiver/MQTT-private.jsonl').read_text().splitlines():
        row = json.loads(line)
        if row['retain']:
            continue
        value = json.loads(bytes.fromhex(row['payload_hex']))
        if start <= value['timestamp'] < end:
            frame,_,packet = decode(row)
            key=STREAMS[frame.stream]
            lengths[key].append(packet)
            if key in WAVES:
                wave_integrity[key]+=frame.count
    for key, data in lengths.items():
        saved = reference['packet_sizes'][key]
        assert (len(data),min(data),max(data))==(saved['count'],saved['min'],saved['max'])
    stats = dict(field_no_audio=bool(audio) and all(x['turns']==0 and x['acked']==0 for _,x in audio),
                 sample_interval_s=duration, io_delta=io_delta,
                 empty_query_ratio=io_delta['rx_empty']/io_delta['rx_queries'],
                 per_sec={k:v/duration for k,v in io_delta.items()},
                 tx_ms_sample_range=[min(x['tx_ms'] for _,x in io),max(x['tx_ms'] for _,x in io)],
                 sched_max={k:max(x[k] for _,x in sched) for k in ('service_gap','console_ms','rx_high')},
                 phases=phases, observed_service=reference['observed_service'],
                 demand_lower_bound=reference['total_input_lower_bound_per_s'],
                 packet_size_counts={k:dict(Counter(data)) for k,data in lengths.items()},
                 wave_points=dict(wave_integrity), observed_uart_trace_records=len(select('B5 AT_EVENT ')),
                 unavailable=['field split command vs prompt','field query durations by empty/read',
                              'field admission deferral by cause','field network idle',
                              'field PUBACK event to Router reclaim','field matched audio delta'])
    return stats,lengths


def run_host(cc, out, *, cpu_scan=False, pass_scan=False, r8_slots=None, service_fit=False, r15_scan=False):
    g=ROOT/'gateway'
    vendor=g/'third_party/coreMQTT/source'
    mqtt=g/'mqtt/src'
    flags=['MP_FRAME_MAX_SAMPLES=100','MP_LIVE_CAPACITY=24','MP_CACHE_CAPACITY=56',
           'MP_B5_CLOUD_CANDIDATE','MP_B5_EGRESS_FINAL','MP_CAN_RX_IRQ','PLATFORM_HOST_TEST',
           'GATEWAY_MQTT_HOST_TEST','MP_MQTT_GATEWAY_ID="GW-B5-001"','MP_FINAL_UNIFIED',
           'MP_ABC_TRI_CANDIDATE','MP_FIVE_NODE','MP_FIVE_APPLIANCE','MP_CLOUD_VOICE']
    files=[g/'b5/test_five_p3_egress.c',mqtt/'mqtt_transport_adapter.c',g/'storage/router.c',
           g/'data_model/model.c',g/'b5/b5_policy.c',*[vendor/n for n in
           ('core_mqtt.c','core_mqtt_serializer.c','core_mqtt_state.c')],
           *[g/'microphone'/n for n in ('unified_audio.c','mic_format.c','mic_protocol.c')],
           g/'voice/tts_queue.c',g/'voice/tts_frame.c']
    if r8_slots is not None:
        pass_scan=True
        flags += [f'GATEWAY_TELEMETRY_SLOTS={r8_slots}']
    if service_fit:
        pass_scan=True
        flags += ['MP_P3_SERVICE_MODEL']
    if r15_scan:
        pass_scan=True
        flags += ['MP_P3_R15_SCAN']
    if pass_scan:
        flags += ['MP_AUDIO_DISABLED','MP_ESP_PASSTHROUGH']
        files=[p for p in files if p.name not in ('unified_audio.c','tts_queue.c','tts_frame.c')]
    exe=out/'p3-host.exe'
    cmd=[cc,'-std=c11','-O2','-Wall','-Wextra','-Werror','-Wno-unused-parameter','-D__USE_MINGW_ANSI_STDIO=1',
         *['-D'+x for x in flags],*['-I'+str(x) for x in (mqtt,g/'b5',vendor/'include',vendor/'interface',
                                                        g/'microphone',g/'voice')],
         *map(str,files),'-o',str(exe)]
    build=subprocess.run(cmd,capture_output=True,timeout=60)
    (out/'host-compile.log').write_bytes(build.stdout+build.stderr)
    if build.returncode:
        print((build.stdout+build.stderr).decode(errors='replace'))
        raise RuntimeError('P3_HOST_BUILD')
    baseline = ((0,22),(64,22),(125,22),(0,42),(125,42))
    runs = [(blocks, terminal, 115200, 0) for blocks, terminal in baseline]
    if cpu_scan:
        runs += [(blocks, terminal, 230400, 0) for blocks, terminal in baseline]
        runs += [(0, terminal, baud, cost) for terminal in (22,42)
                 for baud in (115200,230400) for cost in (30,60,120)]
    if pass_scan:
        check=subprocess.run([str(exe),'--pass-check'],capture_output=True,timeout=10)
        (out/'pass-peer.log').write_bytes(check.stdout+check.stderr)
        check.check_returncode()
        runs=[(0,42,115200,0,'normal',55)]+[
            (0,42,baud,cost,mode,ack) for baud in (115200,230400) for cost in (0,30,60,120)
            for mode in ('normal','pass') for ack in (250,370)]
    else:
        runs=[(*run,None,None) for run in runs]
    if r8_slots is not None:
        runs=[(0,42,230400,cost,'pass',ack,300000) for cost in (0,60) for ack in (250,370,500,700)]
        if r8_slots==3:
            runs += [(0,42,baud,cost,'pass',370,300000) for baud in (115200,230400) for cost in (0,30,60)
                     if (baud,cost) not in ((230400,0),(230400,60))]
    else:
        runs=[(*run,110000) for run in runs]
    cases={}
    fit={}
    def service_cases():
        target=8.07
        for cost in range(121):
            yield (0,22,115200,cost,'normal',55,110000)
        rows=[(abs(row['service_rate']-target),row['service']['cpu_us_per_poll'],row['service_rate'])
              for row in cases.values() if 'service_rate' in row]
        _,cost,rate=min(rows)
        fit.update(target_batches_s=target,service_us=cost,fit_rate=rate,
                   send_ok_ms=22,peer_ack_delay_ms=55)
        yield (0,42,115200,0,'normal',55,110000)
        for mode,baud in (('normal',230400),('pass',115200),('pass',230400),('dma',115200)):
            for ack in (55,370):
                yield (0,22,baud,cost,mode,ack,110000)
    if service_fit:
        runs=service_cases()
    if r15_scan:
        mandatory=(10500,12000,14000,16000)
        rates={115200:(12500,13000,13500,14250,14500,14750,15000),
               230400:(15000,15250,15500,15750,16250,16500,17000)}
        runs=[(0,42,baud,0,'pass',270,300000,rate,'calibrated')
              for baud in rates for rate in sorted(mandatory+rates[baud])]
        runs += [(0,42,baud,0,'pass',55 if mode=='fast-ack' else 270,300000,rate,mode)
                 for baud in rates for rate in (10500,12000,14000,16000)
                 for mode in ('fast-ack','line-only','can-proportional')]
    for blocks, terminal, baud, cost, mode, ack, window, *scan in runs:
        key=f'{blocks}blocks-{terminal}ms'
        if cpu_scan:
            key+=f'-{baud}baud-{cost}us'
        if pass_scan:
            key=f'{mode}-{baud}baud-{cost}us-{ack}ack'
        if service_fit:
            key+=f'-{terminal}sendok'
        if r15_scan:
            key=f'{baud}-{scan[0]}-{scan[1]}'
        argv=[str(exe),str(blocks),str(terminal),str(baud),str(0 if service_fit else cost)]
        if pass_scan:
            argv += [mode,str(ack),str(window)]
        if service_fit:
            argv.append(str(cost))
        if r15_scan:
            argv.extend(map(str,scan))
        result=subprocess.run(argv,
                              capture_output=True,timeout=35)
        log=result.stdout+result.stderr
        (out/(key+'.log')).write_bytes(log)
        text=log.decode(errors='replace')
        print(key,result.returncode,text.splitlines()[:3],flush=True)
        summary=dict(exit=result.returncode,log_sha256=hashlib.sha256(log).hexdigest(),streams=[],latency={},queue_samples=[])
        for line in text.splitlines():
            label=line.split(' ',1)[0]
            fields={k:int(v) for k,v in re.findall(r'(\w+)=(\d+)',line)}
            if label=='stream':
                summary['streams'].append(fields)
            elif label=='queue':
                summary['queue_samples'].append(fields)
            elif label=='lat':
                summary['latency'][line.split()[1]]=fields
            elif label in ('case','flow','owner','slots','peer','offered','service','calibration','FAILED'):
                summary[label]=fields
        if result.returncode==0:
            per_stream={f"{row['node']}/{row['stream']}":row['offered'] for row in summary['streams']}
            summary['offered_total']={'all':summary['offered']['total'],'streams':per_stream}
            assert sum(per_stream.values())==summary['offered_total']['all']
            f=summary['flow']
            summary['service_rate']=(f['q0']+f['q1']-f['replay'])*1000/summary['case']['elapsed_ms']
            summary['all_offered_waves_delivered_at_end']=summary['case']['offered_wave']==summary['case']['delivered_wave']
            if r15_scan:
                c=summary['calibration']
                elapsed_us=summary['case']['elapsed_ms']*1000
                summary['calibration'].update(tx_cpu_fraction=c['tx_us']/elapsed_us,
                    service_cpu_fraction=c['service_us']/elapsed_us,
                    slots_time_mean=c['slot_sum_us']/elapsed_us, slots_full_fraction=c['slot_full_us']/elapsed_us,
                    average_packet_bytes=c['tx_bytes']/(f['published']+f['replay']))
        cases[key]=summary
    for baud in (() if pass_scan else (115200,230400) if cpu_scan else (115200,)):
        suffix=f'-{baud}baud-0us' if cpu_scan else ''
        for terminal in (22,42):
            base=cases[f'0blocks-{terminal}ms{suffix}'].get('service_rate')
            for blocks in (64,125):
                sample=cases.get(f'{blocks}blocks-{terminal}ms{suffix}')
                if sample and base and 'service_rate' in sample:
                    sample['service_rate_delta_vs_no_audio']=sample['service_rate']-base
    return dict(scope='REAL_C_WITH_VIRTUAL_UART_PEER_NOT_FIELD', cases=cases,
                **({'fit':fit} if service_fit else {}),
                source_sha256={p.relative_to(ROOT).as_posix():sha(p) for p in
                              [*files,mqtt/'gateway_transport.c',mqtt/'platform.c',g/'b5/egress.h']})


@dataclass(frozen=True)
class Offer:
    at: float
    stream: str
    size: int

    @property
    def qos1(self):
        return self.stream not in WAVES


def offers(rates, sizes):
    rows=[]
    for stream,rate in rates.items():
        sizes_for_stream=sizes[stream]
        # 只补足已知源率的负载规模。真实窗口中缺失包的时序与内容未知。
        count=1 if stream=='nibp' else int(rate*HORIZON_MS/1000)
        for i in range(count):
            at=2000 if stream=='nibp' else (i+1)*1000/rate
            rows.append(Offer(at,stream,sizes_for_stream[i%len(sizes_for_stream)]))
    return sorted(rows,key=lambda row:row.at)


def capacity_model(rows, overhead, *, blocks, poll_save, pair_save, overlap_save):
    pending, tickets = [], []
    sent, lost, expired, late = Counter(), Counter(), Counter(), Counter()
    cursor=high=attempted=acknowledged=transactions=pairs=0
    now=0.0
    peak_age=0.0
    audio_ready=10000+(1010 if blocks==64 else 2000)
    audio_first=audio_last=audio_done=None
    audio_yield=False
    useful_owner_ms=0.0
    completed_in_window=0
    while cursor<len(rows) or pending or tickets or now<HORIZON_MS:
        while tickets and tickets[0][0]<=now:
            finished, frame=tickets.pop(0)
            sent[frame.stream]+=1
            completed_in_window+=finished<=HORIZON_MS
            age=finished-frame.at
            peak_age=max(peak_age,age)
            if age>=(90000 if frame.stream=='nibp' else 5000):late[frame.stream]+=1
        while cursor<len(rows) and rows[cursor].at<=now:
            frame=rows[cursor]
            cursor+=1
            if len(pending)==24:lost[frame.stream]+=1
            else:pending.append(frame)
        high=max(high,len(pending))
        keep=[]
        for frame in pending:
            # 现有 B5 出站资格在5秒后转历史。90秒血压读数寿命单独核对。
            if now-frame.at>5000:expired[frame.stream]+=1
            else:keep.append(frame)
        pending=keep
        if audio_done is not None and audio_done<=now:
            acknowledged+=1
            audio_done=None
        duration=0.0
        if (attempted<blocks and audio_done is None and now<HORIZON_MS and now>=audio_ready
                and len(pending)<22 and (not pending or now-pending[0].at<2500)
                and (not audio_yield or not pending)):
            if audio_first is None:audio_first=now
            duration=564/BAUD_BYTES_MS+overhead-poll_save-overlap_save
            audio_last=now+duration
            audio_done=audio_last+120
            audio_ready=now+250
            attempted+=1
            audio_yield=True
        else:
            slots=3-len(tickets)
            eligible=[i for i,frame in enumerate(pending) if slots or not frame.qos1]
            if eligible:
                first=pending.pop(eligible[0])
                group=[first]
                if pair_save and pending:
                    # 机会式合发相邻待发包，不因凑批等待。各 MQTT 包与票据独立。
                    other=pending[0]
                    projected=(first.size+other.size)/BAUD_BYTES_MS+2*(overhead-poll_save-overlap_save)-pair_save
                    if (first.size+other.size<=2048 and slots>=int(first.qos1)+int(other.qos1)
                            and now+projected-min(first.at,other.at)<2500):
                        group.append(pending.pop(0))
                        pairs+=1
                duration=sum(f.size/BAUD_BYTES_MS+overhead-poll_save-overlap_save for f in group)
                if len(group)==2:duration-=pair_save
                for frame in group:
                    finished=now+duration
                    if frame.qos1:
                        tickets.append((finished+120,frame))
                    else:
                        sent[frame.stream]+=1
                        completed_in_window+=finished<=HORIZON_MS
                        age=finished-frame.at
                        peak_age=max(peak_age,age)
                        if age>=5000:late[frame.stream]+=1
                audio_yield=False
        if duration:
            assert duration>0
            now+=duration
            transactions+=1
            useful_owner_ms+=duration
            continue
        upcoming=[x for x in (rows[cursor].at if cursor<len(rows) else None,
                  tickets[0][0] if tickets else None, audio_done,
                  audio_ready if attempted<blocks and audio_ready>now and audio_ready<HORIZON_MS else None,
                  HORIZON_MS if now<HORIZON_MS else None) if x is not None]
        if not upcoming:break
        now=min(upcoming)
    assert len(rows)==sum(sent.values())+sum(lost.values())+sum(expired.values())
    span=None if audio_first is None else audio_last-audio_first
    all_audio=acknowledged==blocks and (span is None or span<90000)
    return dict(offered=len(rows),completed=dict(sent),overflow=dict(lost),expired=dict(expired),late=dict(late),
                waves_missing=sum(lost[k]+expired[k]+late[k] for k in WAVES),peak_queue=high,
                max_completion_age_ms=peak_age,transactions=transactions,pairs=pairs,
                completion_rate_during_input=completed_in_window/(HORIZON_MS/1000),
                audio_blocks_requested=blocks,audio_blocks_acked=acknowledged,audio_assembly_span_ms=span,
                audio_finishes_during_input=not blocks or (all_audio and audio_last<=HORIZON_MS),
                owner_occupancy_per_input_time=useful_owner_ms/HORIZON_MS,
                simulated_deadline_pass=not (lost or expired or late) and all_audio)


def model_cases(reference, distributions):
    p2=json.loads(P2.read_text())['joint']
    p2_rates={k:n/p2['duration_s'] for k,n in p2['counts'].items()}
    workloads={name:(r['input_rates_per_s'],distributions[name],r['observed_service']['frames_per_s'])
               for name,r in reference.items()}
    # P2 回执只保存每流尺寸范围，取实测上界做保守负载。
    workloads['P2']=(p2_rates,{k:[v['max']] for k,v in p2['mqtt_size_by_stream'].items()},8.08)
    results={}
    for name,(rates,sizes,service) in workloads.items():
        workload=offers(rates,sizes)
        mean=statistics.mean(row.size for row in workload)
        overhead=1000/service-mean/BAUD_BYTES_MS
        scenarios={
            'baseline':(0,0,0),
            'fewer_empty_queries':(5,0,0),
            'fewer_empty_queries_optimistic':(12,0,0),
            'batch_two':(0,30,0),
            'nonblocking_same_wire':(0,0,0),
            'nonblocking_optimistic':(0,0,20),
            'poll_and_batch':(5,30,0),
            'upper_sensitivity':(12,45,20),
        }
        results[name]=dict(scope='COUNTERFACTUAL_NOT_DEVICE',baseline_field_service_calibration=service,
                           residual_per_transaction_ms=overhead,average_packet_bytes=mean,
                           offered_per_s=len(workload)/(HORIZON_MS/1000),window_ms=HORIZON_MS,
                           scenarios={key:dict(saved_poll_ms=p,saved_pair_ms=b,overlap_ms=o,
                                               cases={str(blocks):capacity_model(workload,overhead,blocks=blocks,
                                                   poll_save=p,pair_save=b,overlap_save=o) for blocks in (0,64,125)})
                                      for key,(p,b,o) in scenarios.items()})
    return results


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    source=parser.add_mutually_exclusive_group(required=True)
    source.add_argument('--paths',type=Path)
    source.add_argument('--cpu-scan',action='store_true',help='仅运行同输入 Host 波特率与每字节 CPU 扫描')
    source.add_argument('--service-fit',action='store_true',help='R9 按服务回调开销拟合 P1 实测完成率')
    source.add_argument('--r8-scan',action='store_true',help='R8 300秒对照与QoS1槽位扫描')
    source.add_argument('--r15-scan',action='store_true',help='R15 五板透传离线入队速率扫描')
    source.add_argument('--pass-scan',action='store_true',help='音频关闭的 R7 普通/透传 Host 对照')
    parser.add_argument('--out',type=Path,required=True)
    parser.add_argument('--cc',default='C:/mingw64/bin/gcc.exe')
    parser.add_argument('--host-results',type=Path,help='复用已完成的同源码 Host 回执')
    args=parser.parse_args()
    if (args.cpu_scan or args.pass_scan or args.r8_scan or args.service_fit or args.r15_scan) and args.host_results:
        parser.error('scan modes require a fresh Host run')
    args.out.mkdir(parents=True,exist_ok=False)
    if args.r15_scan:
        host=run_host(args.cc,args.out,r15_scan=True)
        result=dict(scope='HOST_MODEL_NOT_HARDWARE',script_sha256=sha(Path(__file__)),host=host)
        (args.out/'results.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
        return int(any(case['exit'] for case in host['cases'].values()))
    if args.service_fit:
        host=run_host(args.cc,args.out,service_fit=True)
        result=dict(scope='HOST_MODEL_NOT_HARDWARE',script_sha256=sha(Path(__file__)),host=host)
        (args.out/'results.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
        return int(any(case['exit'] for case in host['cases'].values()))
    if args.r8_scan:
        hosts={}
        for slots in (3,4,6):
            directory=args.out/f'slots-{slots}'
            directory.mkdir()
            hosts[str(slots)]=run_host(args.cc,directory,r8_slots=slots)
        result=dict(scope='HOST_ONLY_NOT_HARDWARE',script_sha256=sha(Path(__file__)),slots=hosts)
        (args.out/'results.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
        return int(any(case['exit'] for host in hosts.values() for case in host['cases'].values()))
    if args.cpu_scan or args.pass_scan:
        host=run_host(args.cc,args.out,cpu_scan=args.cpu_scan,pass_scan=args.pass_scan)
        result=dict(scope='HOST_ONLY_NOT_HARDWARE', cpu_model='serial line time plus CPU surcharge per TX/RX byte',
                    script_sha256=sha(Path(__file__)),host=host)
        (args.out/'results.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
        return int(any(case['exit'] for case in host['cases'].values()))
    if args.host_results:
        host=json.loads(args.host_results.read_text())['host']
        for name,checksum in host['source_sha256'].items():
            assert sha(ROOT/name)==checksum, name
    else:
        host=run_host(args.cc,args.out)
    reference=json.loads(P1.read_text())['windows']
    paths=json.loads(args.paths.read_text())
    field,distributions={},{}
    for name in ('ECG60','RR18'):
        field[name],distributions[name]=field_data(paths[name+'_completed_job'],reference[name])
    result=dict(field=field,host=host,model=model_cases(reference,distributions),
                capacity='CAPACITY_NOT_PASS',script_sha256=sha(Path(__file__)),
                p1_summary_sha256=sha(P1),p2_receipt_sha256=sha(P2))
    (args.out/'results.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')


if __name__=='__main__':
    raise SystemExit(main())
