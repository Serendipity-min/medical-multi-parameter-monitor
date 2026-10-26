"""复核B4冻结文件和受限原件；不导入调试器或串口驱动。"""
from pathlib import Path
import argparse
import json
import hashlib
import b4_recovery as pkg


def load(p):
    return json.loads(p.read_text(encoding='utf-8'))


def digest(p):
    pkg.protected(p, False)
    return hashlib.sha256(p.read_bytes()).hexdigest()


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--b4-worktree',type=Path,required=True)
    ap.add_argument('--out',type=Path,required=True);args=ap.parse_args()
    pointers=args.b4_worktree/'node-b/build/c-com15-can2-review'
    closeout=load(pointers/'closeout-24104-pointer.json');base=pkg.protected(Path(closeout['base']),False)
    backup=base/'C-current-backup'
    assert digest(backup/'flash-1-private.bin')==digest(backup/'flash-2-private.bin')=='1f56dd2ec1eb8002b52b77eb3faf5986bb0336694ac993923c9a7575ba264a10'
    assert digest(backup/'options-1-private.bin')==digest(backup/'options-2-private.bin')
    assert digest(Path(closeout['B_package'])/'expected-full-private.bin')=='a1abed50a4c4dbab142a2319d61c047bc43b6816dd62754a080e3f7e12415091'
    phases=[]
    for name in ('01-old-restore-H3','02-new-install','03-new-restore-H3','04-new-reinstall'):
        folder=base/name;r=load(folder/'receipt-private.json')
        assert r['exit_code']==0 and r['options_unchanged'] and r['outside_affected_sectors_unchanged']
        assert digest(folder/'after-full-private.bin')==r['full_flash_sha256']
        assert digest(folder/'after-options-private.bin')==digest(backup/'options-1-private.bin')
        assert (folder/'before-full-private.bin').read_bytes()[32768:]==(folder/'after-full-private.bin').read_bytes()[32768:]
        phases.append({'name':name,'full_flash_sha256':r['full_flash_sha256'],'exit_code':0,
                       'options_unchanged':True,'outside_application_unchanged':True})
    windows={}
    for label,filename in (('ECG','current-ecg-can-pointer.json'),('RR','current-resp-can-pointer.json')):
        pointer=load(pointers/filename);root=pkg.protected(Path(pointer['base']),False)
        common=load(root/'common-review-private.json');b=Path(pointer['B']);c=Path(pointer['C'])
        original_paths={'C-serial':c/'serial-raw-private.bin','C-packets':c/'packets-private.jsonl',
                        'C-receipt':c/'receipt-private.json','B-slots':b/'slots-private.bin',
                        'B-diagnostics':b/'diagnostics-private.jsonl','B-analysis':root/'analysis/analysis-private.json'}
        for key,p in original_paths.items():assert digest(p)==common['originals_sha256'][key]
        ds=[json.loads(s) for s in (b/'diagnostics-private.jsonl').read_text(encoding='utf-8').splitlines()]
        start,end=common['B_sample_tick_first_last']
        selected=[d for d in ds if start<=d['bio']['last_sample_ms']<=end]
        # 全窗expired包括首次TIME前丢弃；独立报告共同稳态增量，不改写全窗累计值。
        whole=ds[-1]['CAN']['expired']-ds[0]['CAN']['expired']
        steady=selected[-1]['CAN']['expired']-selected[0]['CAN']['expired']
        receipt=load(c/'receipt-private.json');assert receipt['exit_code']==common['analysis_exit_code']==0
        packets=[json.loads(s) for s in (c/'packets-private.jsonl').read_text(encoding='utf-8').splitlines()]
        nmt=sum(r['kind']==3 and r['id']==0 and r['bus']==1 for r in packets)
        times=sum(r['kind']==3 and r['id']==0x100 and r['bus']==1 for r in packets)
        assert nmt>0 and times>0 and not receipt['model_value_time_checks_failed']
        windows[label]={'status':common['status'],'expired_whole_capture':whole,'expired_common_saved_span':steady,
                        'expired_snapshot_span_tick':[selected[0]['bio']['last_sample_ms'],selected[-1]['bio']['last_sample_ms']],
                        'CAN_failures':receipt['failures'],'TEC':receipt['C_CAN2_peak_TEC'],'REC':receipt['C_CAN2_peak_REC'],
                        'NMT_ACK':nmt,'TIME_ACK':times,'model_checks':receipt['model_value_time_checks_passed'],
                        'quality_flags':common['C_quality_flags'],
                        'source_ticks_matched':common['matched_B_raw_points'],'original_sha256':common['originals_sha256']}
        # CAN数据副本仍仅在EFS保存；本机后续离线模型测试直接消费该副本。
        target=pkg.protected(args.out,False)/(label+'-CAN-private.txt')
        with target.open('x',encoding='ascii',newline='\n') as f:
            for line in (c/'packets-private.jsonl').read_text(encoding='utf-8').splitlines():
                r=json.loads(line)
                if r['kind']==1 and r['bus']==1:
                    f.write(f"{r['tick']} {r['id']:x} {r['dlc']} {r['data'][:r['dlc']*2]}\n")
        pkg.protected(target,False)
    result={'status':'FROZEN_B4_EVIDENCE_REVERIFIED','hardware_operations':0,'C_four_actual_phases':phases,
            'windows':windows,'B_image_sha256':'676eb7a46ad9cd15c7bf93db51a1931d7711d37c6f2fd636197dc4a85b339b82',
            'C_image_sha256':'127ba765b8144e8f8ae98ef826ac2a98f45f8facb4021ce1888c004e5ca46547',
            'old_failures_retained':True,'CPU_ROM':'UNRESOLVED','coldboot':'NOT_VALIDATED',
            'same_window_HR_RR':'NOT_VALIDATED','impedance_amplitude':'INSTRUMENT_REQUIRED','fault_injection_recovery':'NOT_TESTED'}
    args.out.joinpath('audit-private.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    pkg.protected(args.out/'audit-private.json',False)
    print(json.dumps({'status':result['status'],'expired':{k:[v['expired_whole_capture'],v['expired_common_saved_span']] for k,v in windows.items()}}))
    return 0


if __name__=='__main__':raise SystemExit(main())
