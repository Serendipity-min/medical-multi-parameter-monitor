"""把真实CAN数值/末点UTC与C输出分包逐点核对；不对ADC原码作伪电压/欧姆标定。"""
from pathlib import Path
import json
import struct
from collections import Counter
from b4_capture_decode import signed_delta
import b4_recovery as pkg

ROOT=Path(__file__).resolve().parents[2]


def main():
    private=pkg.protected(Path(json.loads((ROOT/'node-b/build/b5-private-pointer.json').read_text())['base']),False)
    results={}
    for label in ('ECG','RR'):
        anchor=None;waves={'ecg':[],'resp':[]}
        for line in (private/(label+'-CAN-private.txt')).read_text().splitlines():
            _,ident,length,hexdata=line.split();ident=int(ident,16);data=bytes.fromhex(hexdata)
            if ident==0x482:anchor=struct.unpack('<II',data)
            if ident in (0x182,0x282) and anchor:
                value,tick=struct.unpack('<iI',data);utc=anchor[0]*1000+signed_delta(tick,anchor[1])
                waves['ecg' if ident==0x182 else 'resp'].append((utc,value))
        positions={name:{p[0]:i for i,p in enumerate(points)} for name,points in waves.items()}
        counts=Counter();sizes=[];last_seq={}
        for line in (private/(label+'-MpFrame-MQTT-private.jsonl')).read_text().splitlines():
            item=json.loads(line);body=item['payload'];topic=item['topic'];name=topic.split('/')[-1]
            assert topic.startswith('mpm/v1/GW-B5-001/') and body['source']=='MOCK' and body['synthetic']
            key=(topic,body['session_id']);assert body['seq']>last_seq.get(key,-1);last_seq[key]=body['seq']
            sizes.append(len(json.dumps(body,separators=(',',':')).encode()))
            if name in waves:
                rate,count,scale,unit=(250,100,1000,'mV') if name=='ecg' else (50,50,1000000,'relative')
                assert body['sample_rate']==rate and len(body['samples'])==count and body['unit']==unit
                end=positions[name][body['timestamp']];actual=waves[name][end-count+1:end+1]
                assert len(actual)==count and [v for _,v in actual]==[round(v*scale) for v in body['samples']]
                counts[name+'_matched_samples']+=count;counts[name+'_batches']+=1
            elif name in ('hr','rr','temp'):
                if body['validity']!='VALID':assert body['value'] is None
                assert body['unit']=={'hr':'bpm','rr':'breaths/min','temp':'degC'}[name]
                if name=='temp':assert body['validity']=='INVALID'
                counts[name+'_messages']+=1
            if item['qos']==0:assert name in waves
        assert counts['ecg_batches']>400 and counts['resp_batches']>170 and max(sizes)<2048
        results[label]={'status':'PASS','counts':dict(counts),'max_reencoded_JSON_bytes':max(sizes),
                        'source_UTC_preserved':True,'unit_conversion_matches_CAN_fixed_point':True,
                        'ADC_codes_not_compared_as_filtered_mV':True,'partial_tail_not_padded':True}
    target=ROOT/'node-b/evidence/B5-1/actual-CAN-frame-value-time.json'
    target.write_text(json.dumps({'status':'PASS','cases':results},indent=2)+'\n',encoding='utf-8')
    print('ACTUAL_CAN_VALUE_TIME_AND_100_50_BATCHING_PASS');return 0


if __name__=='__main__':raise SystemExit(main())
