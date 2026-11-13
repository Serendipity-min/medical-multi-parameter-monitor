"""M1独立工程评价：165秒原码、45秒预热和固定120个1Hz槽；无设备入口。"""
import argparse
import csv
import json
from pathlib import Path

from b5_m1_entry import need, plan, plan_hash, save, sha, PRIVATE, SCOPE


def evaluate(rows, diagnostics, anchor, condition, target):
    """rows来自既有稳定槽解码，保持seq/IRQ原码；不调用或修改HR算法。"""
    origin=anchor['ms']; integrity=[];failures=[]
    offsets=[((r[1]-origin)&0xffffffff) for r in rows]
    selected=[r for r,t in zip(rows,offsets) if t<165000]
    relative=[t for t in offsets if t<165000]
    if not selected or min(relative)>12 or max(relative)<164988:integrity.append('RAW_WINDOW_EDGE')
    for a,b in zip(selected,selected[1:]):
        if b[0]!=a[0]+1:integrity.append('RAW_SEQUENCE_GAP')
        if ((b[1]-a[1])&0xffffffff) not in (3,4,5):integrity.append('IRQ_MS_ORDER_OR_GAP')
        if not ((b[5]-a[5])&0xffffffff):integrity.append('IRQ_CYCLES_NOT_ADVANCING')
    if any(r[4] for r in selected):integrity.append('RAW_FLAGS')
    if any((r[6]&0xf01fff)!=0xc00000 for r in selected):integrity.append('ADC_STATUS')
    if len(selected)>1:
        sps=(len(selected)-1)*1000/(relative[-1]-relative[0]) if relative[-1]>relative[0] else 0
        if not 247.5<=sps<=252.5:integrity.append('RAW_NOT_250SPS')
    else:sps=0
    slots=[None]*120; native=[];last_offset=-1;all_bio=[]
    for d in diagnostics:
        bio=d['bio'];offset=(bio['last_sample_ms']-origin)&0xffffffff
        if offset>=165000:continue
        if offset<=last_offset:integrity.append('DIAGNOSTIC_ORDER')
        last_offset=offset;all_bio.append(bio)
        if bio['adc']['init_errors'] or d['CAN']['error']:integrity.append('INITIALIZATION_ERROR')
        if 45000<=offset<165000:
            i=(offset-45000)//1000
            if slots[i] is None:slots[i]=bio
            native.append({'offset_ms':offset,'bio':bio})
    for a,b in zip(all_bio,all_bio[1:]):
        for k in ['discontinuities']:
            if b[k]!=a[k]:integrity.append('NEW_'+k.upper())
        for k in ['bad_status','spi_errors','queue_overflow','long_gap_count','init_errors']:
            if b['adc'][k]!=a['adc'][k]:integrity.append('NEW_ADC_'+k.upper())
    for a,b in zip(diagnostics,diagnostics[1:]):
        for k in ['overflow','discontinuities','comm_reset']:
            if a['CAN'][k]!=b['CAN'][k]:integrity.append('NEW_CAN_'+k.upper())
    is_ecg=condition.startswith('E');value='hr' if is_ecg else 'rpm';valid='hr_valid' if is_ecg else 'rpm_valid'
    tolerance=2 if is_ecg else 1
    correct=sum(b is not None and b[valid]==1 and abs(b[value]-target)<=tolerance for b in slots)
    if correct<118:failures.append('CORRECT_VALID_COVERAGE_BELOW_118_OF_120')
    if any(r['bio'][valid]==1 and abs(r['bio'][value]-target)>tolerance for r in native):failures.append('VALID_VALUE_OUT_OF_TOLERANCE')
    # 这里只统计保存快照观察簇，不冒称真实逐拍时长或源端QRS标签。
    clusters=[];active=None
    for r in native:
        if r['bio']['hr_valid']:
            if active is None or r['offset_ms']-active['last_observed_ms']>1000:
                clusters.append({'first_observed_ms':r['offset_ms'],'last_observed_ms':r['offset_ms'],'observations':0})
                active=clusters[-1]
            active['last_observed_ms']=r['offset_ms'];active['observations']+=1
        else:active=None
    return {'status':'M1_ENGINEERING_RATE_SUBFUNCTION_PASS' if not (integrity or failures) else 'M1_ENGINEERING_NOT_PASS',
        'exit_code':2 if integrity else 3 if failures else 0,'integrity_failures':sorted(set(integrity)),
        'engineering_failures':failures,'condition':condition,'target':target,'correct_valid_slots':correct,'denominator':120,
        'missing_slots':sum(b is None for b in slots),'selection':'FIRST_NATIVE_OBSERVATION_PER_HALF_OPEN_SECOND_NO_VALIDITY_FILTER',
        'native_evaluation_observations':len(native),'observed_raw_sps':sps,'raw_window_frames':len(selected),
        'raw_evaluation_frames':sum(45000<=t<165000 for t in relative),
        'RESP50_evaluation_frames':sum(45000<=t<165000 and r[0]%5==0 for r,t in zip(selected,relative)),
        'HR_valid_native_observations':sum(bool(r['bio']['hr_valid']) for r in native),'HR_snapshot_clusters':clusters,
        'HR_truth':'NOMINAL_ECG_NO_PER_BEAT_CALIBRATION' if is_ecg else 'SOURCE_UNKNOWN_ROOT_CAUSE_UNRESOLVED',
        'whole_RR_window_PASS':False,'physical_accuracy':'NOT_CALIBRATED','snapshot_duration_resolution':'OBSERVATIONS_ONLY_NOT_CONTINUOUS_PROOF'}


def review(session, out, run_id):
    from b5_rr15_causal_replay import sealed_raw_frames
    import b5_m1_entry as entry
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
    p=plan(run_id);b=session/'B'
    receipt=json.loads((b/'receipt-private.json').read_text())
    need(receipt['exit_code']==0 and receipt['Close_completed'], 'M1_CAPTURE_OR_CLOSE_NOT_COMPLETE')
    binding=json.loads((session/'authorization-binding-private.json').read_text())
    need(binding['run_id']==run_id and binding['nonce_ledger_consumed'] is True, 'M1_CAPTURE_RUN_BINDING')
    authorization=(session/'authorization-private.json').read_bytes()
    need(sha(authorization)==binding['authorization_sha256'], 'M1_CAPTURE_AUTH_SHA')
    signature=(session/'authorization-signature.bin').read_bytes();public=(session/'authorization-public-key.bin').read_bytes()
    need(sha(signature)==binding['signature_sha256'] and sha(public)==binding['public_key_sha256'],'M1_SIGNATURE_FILE_SHA')
    Ed25519PublicKey.from_public_bytes(public).verify(signature,authorization)
    trusted=entry.TRUSTED_PI_KEY_SHA256 is not None and sha(public)==entry.TRUSTED_PI_KEY_SHA256
    if entry.TRUSTED_PI_KEY_SHA256 is not None:need(trusted,'M1_REVIEW_UNTRUSTED_PI_KEY')
    a=json.loads(authorization)
    need(a['scope']==SCOPE and a['run_id']==run_id and a['plan_sha256']==plan_hash(run_id),'M1_REVIEW_PLAN_BINDING')
    inputs=(b/'input-hashes-private.json').read_bytes()
    need(sha(inputs)==binding['capture_input_manifest_sha256'],'M1_CAPTURE_MANIFEST_SHA')
    for name,expected in json.loads(inputs).items():need(sha((b/name).read_bytes())==expected,'M1_CAPTURE_FILE_SHA')
    meta=json.loads((b/'window-private.json').read_text())
    need((meta['duration_ms'],meta['warmup_ms'],meta['evaluation_ms'])==(165000,45000,120000),'M1_TIMING_DRIFT')
    frozen=json.loads(inputs)
    rows,integrity=sealed_raw_frames(session,frozen['blocks-private.bin'],frozen['blocks-private.jsonl'])
    diagnostics=[json.loads(line)['data'] for line in (b/'diagnostics-private.jsonl').read_text().splitlines()]
    result=evaluate(rows,diagnostics,meta['anchor'],p['condition'],p['target'])
    if integrity['invalid_status_sequences']:
        result['integrity_failures'].append('OBSERVED_INVALID_RAW_STATUS');result['exit_code']=2;result['status']='M1_ENGINEERING_NOT_PASS'
    out.mkdir(exist_ok=False)
    with (out/'raw250-private.csv').open('x',newline='',encoding='utf-8') as f:
        writer=csv.writer(f);writer.writerow(['seq','irq_ms','CH2_ecg_codes','CH1_resp_codes','flags','irq_cycles','status']);writer.writerows(rows)
    with (out/'resp50-private.csv').open('x',newline='',encoding='utf-8') as f:
        writer=csv.writer(f);writer.writerow(['seq','irq_ms','CH1_resp_codes','flags','irq_cycles'])
        writer.writerows((r[0],r[1],r[3],r[4],r[5]) for r in rows if r[0]%5==0)
    result['stable_slot_integrity']=integrity;result['capture_native_side_effects']=receipt['native_side_effects']
    result['authorization_signature_math_verified']=True;result['PI_trust_root_verified']=trusted
    result['field_scope_PASS']=trusted and result['exit_code']==0
    if not trusted and result['exit_code']==0:result['status']='M1_OFFLINE_RATE_METRICS_ONLY_UNVERIFIED_PI_ROOT'
    result['input_sha256']={name:sha((b/name).read_bytes()) for name in ['blocks-private.bin','blocks-private.jsonl','diagnostics-private.jsonl','window-private.json','receipt-private.json']}
    save(out/'review-private.json',result)
    return result


def main():
    from cryptography.exceptions import InvalidSignature
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--session',type=Path,required=True)
    p.add_argument('--out',type=Path,required=True);p.add_argument('--run-id',required=True);a=p.parse_args()
    try:
        for folder in (a.session,a.out.parent):
            need(folder.resolve().is_relative_to(PRIVATE.resolve()) and folder.stat().st_file_attributes&0x4000,'M1_REVIEW_REQUIRES_RESTRICTED_EFS')
        result=review(a.session,a.out,a.run_id)
        print(json.dumps({k:result[k] for k in ['status','exit_code','correct_valid_slots','denominator','HR_truth']}));return result['exit_code']
    except (OSError,KeyError,ValueError,RuntimeError,InvalidSignature) as error:
        print(json.dumps({'status':'M1_REVIEW_INPUT_REJECT','exit_code':2,'type':type(error).__name__}));return 2


if __name__=='__main__':raise SystemExit(main())
