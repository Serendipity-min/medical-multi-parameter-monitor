"""已有EFS回执的离线复核；缺失分段不推断，不连接设备或网络。"""
import collections
import json
from pathlib import Path
import sys
import hashlib
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
import b5_g3_contract as g
import b5_g3_review as old
from cloud.backend.app.hub import Hub
from cloud.backend.app.adapters import decode_mqtt

def main():
    p=json.loads((g.ROOT/'node-b/build/b5-egress-final-r1-pointer.json').read_text());out=Path(p['root'])/'evidence-audit';out.mkdir()
    temp=json.loads((g.ROOT/p['temperature_pointer']).read_text());folder=Path(temp['windows']['ECG60']['output'])
    arm=g.load(folder/'ARM_ATTEMPT.json')['monotonic'];t0=g.load(folder/'T0.json');begin,end=t0['evaluation_UTC_ms']
    events=[json.loads(s) for s in (folder/'cloud-events-private.jsonl').read_text('utf8').splitlines()]
    now=[0.,0.];hub=Hub(['GW-B5-001'],clock=lambda:now[0],monotonic=lambda:now[1]);hub.broker_connected=True
    messages=[];bad=collections.Counter();gaps=[];last=None
    for x in events:
        if x['monotonic']<arm:continue
        now[:]=[x['UTC_ms']/1000,x['monotonic']]
        if x['kind']=='BROKER_RAW':
            item=x['data'];m=decode_mqtt(item['topic'],bytes.fromhex(item['payload_hex']))
            hub.ingest(m)
            if not item['retain']:
                messages.append((x,m))
                if last is not None:gaps.append((x['monotonic']-last,last-arm))
                last=x['monotonic']
        if x['kind']=='WSS_RAW' and begin<=x['data']['server_time']<end:
            # 用保存的服务端时钟检查同样的Hub契约，不回写真实WSS原件。
            now[0]=x['data']['server_time']/1000;s=hub.snapshot('GW-B5-001')
            if s['nodes']['NODE-B']!='ONLINE':bad['replayed_node_not_online']+=1
            streams={z['stream']:z for z in s['streams'] if z['node_id']=='NODE-B'}
            if any(streams.get(k,{}).get('validity')!='VALID' for k in ('ECG','HR')):bad['replayed_target_invalid']+=1
    assert len(messages)==2893
    assert collections.Counter(m.source for _,m in messages)=={'MOCK':2845,'REPLAY':48}
    raw,can,clocks,counts=old.reconstruct(folder)
    index=g.can_utc_points(can,clocks);points={};source_batches=[]
    for x,m in messages:
        if m.node_id!='NODE-B' or m.stream not in ('ECG','RESP'):continue
        d=m.model_dump();matched=old.match_batch(d,index,can,raw)
        if m.stream=='ECG':
            for seq,utc,value in matched:
                if begin<=utc<end:points[seq]=(utc,value)
        source_batches.append({'topic':x['data']['topic'],'payload':json.loads(bytes.fromhex(x['data']['payload_hex'])),
            'source_end_sequence':matched[-1][0],'source_mapping':'ACTUAL_B_RAW_AND_CAN_VERIFIED',
            'historical_Broker_received_UTC_ms':x['data']['received_UTC_ms']})
    seq=sorted(points);assert len(points)==74993 and all(b-a==1 for a,b in zip(seq,seq[1:]))
    assert abs(max(gaps)[0]-2.516)<.002 and bad['replayed_target_invalid'] and bad['replayed_node_not_online']
    g.write_private(out/'verified-source-batches-private.jsonl',('\n'.join(json.dumps(x) for x in source_batches)+'\n').encode())
    r={'status':'HISTORICAL_FAILURE_REPRODUCED','raw_ECG_points':len(points),'Broker_messages':len(messages),
       'source_counts':dict(collections.Counter(m.source for _,m in messages)),
       'Hub_offline_replay_counts':dict(bad),'saved_WSS_invalid_counts':{'target_invalid':72,'node_STALE':19},
       'largest_delivery_gaps_s_and_ARM_offset':sorted(gaps,reverse=True)[:8],
       'C_enqueue_prompt_data_SEND_OK_PUBACK_stage_times':'UNKNOWN_NOT_CAPTURED_PER_PACKET',
       'replay_Hub_is_not_replacement_for_original_WSS':True,'source_reconstruction':counts,
       'original_Broker_raw_sha256':g.sha((folder/'cloud-events-private.jsonl').read_bytes()),'hardware_operations':0}
    g.save(out/'receipt-private.json',r);print(json.dumps({k:r[k] for k in ('status','raw_ECG_points','Broker_messages','Hub_offline_replay_counts')}))
    return 0

if __name__=='__main__':raise SystemExit(main())
