"""B温度屏安装后的15秒组件只读检查；复用BLink和原诊断，不宣称CAN/云复验。"""
import argparse
import json
from pathlib import Path
import sys
import time

import abc_board_backup as backup
import b4_runtime as runtime
import b5_g3_contract as g
from b5_g3_devices import BLink


def capture(a):
    installed=g.load(a.install/'receipt-private.json');profile=g.load(a.profile)['profile_from_actual_symbols']
    g.require(installed['board']=='B' and installed['exit_code']==0 and installed['Close_completed'],'B_SCREEN_INSTALL_REQUIRED')
    a.out.mkdir();probe=a.out/'probe';probe.mkdir();g.private.protected(a.out,False)
    link=None;rows=[];result={'exit_code':1,'scope':'B_TEMP_SCREEN_COMPONENT_ONLY','explicit_target_writes':0,
        'CAN_and_cloud':'NOT_TESTED_B_ONLY_NO_CAN_PEER','SDK_native_side_effects':'UNRESOLVED'}
    try:
        link=BLink(probe,a.out,profile=profile);link.open()
        identity=runtime.raw.identity(link);g.save(probe/'identity-private.json',identity)
        g.require(identity==g.load(a.install/'probe/identity-after-private.json'),'B_SCREEN_IDENTITY')
        g.save(probe/'sticky-private.json',{'DHCSR':link.u32(runtime.ro.SYSTEM['DHCSR'])})
        state=runtime.ro.snapshot(link);g.save(probe/'entry-private.json',state);runtime.ro.check_running(link,state)
        full=link.read(0x08000000,1048576);options=link.read(0x1fffc000,16)
        g.write_private(probe/'full-private.bin',full);g.write_private(probe/'options-private.bin',options)
        g.require(g.sha(full)==installed['full_flash_sha256'] and g.sha(full[:profile['BIN_bytes']])==profile['BIN_sha256']
            and options==(a.install/'probe/after-options-private.bin').read_bytes(),'B_SCREEN_IMAGE_OR_OPTIONS')
        start=time.monotonic()
        print(json.dumps({'event':'B_TEMP_SCREEN_DIAGNOSTICS_READY','seconds':15}),flush=True)
        for n in range(31):
            time.sleep(max(0,start+n*.5-time.monotonic()))
            row=runtime.snapshot(link,probe,'d'+str(n),profile['RAM'],stable_temperature=True)
            rows.append(row)
        g.save(a.out/'diagnostics-private.json',rows)
        first,last=rows[0],rows[-1];duration=last['bio']['last_sample_ms']-first['bio']['last_sample_ms']
        rate=(last['bio']['samples']-first['bio']['samples'])*1000/duration if duration>0 else 0
        errors={k:last['bio']['adc'][k]-first['bio']['adc'][k] for k in ('bad_status','spi_errors','queue_overflow','init_errors','long_gap_count')}
        failures=[]
        if not 247.5<=rate<=252.5 or any(errors.values()):failures.append('ADC_RATE_OR_ERRORS')
        if any(not r['temperature_observation']['qualified'] or not r['temperature']['present'] or
            not -10<=g.signed(r['bio']['last_sample_ms'],r['temperature']['last_ms'])<=2500 for r in rows):failures.append('TEMP_FRESH_COHERENT')
        if any(not r['bio']['hr_valid'] or not 58<=r['bio']['hr']<=62 for r in rows):failures.append('HR60_NONREGRESSION')
        state=runtime.ro.snapshot(link);g.save(probe/'final-private.json',state);runtime.ro.check_running(link,state)
        link.final_close_verified=True;link.set_close_resume(True)
        result.update(exit_code=3 if failures else 0,failures=failures,samples=len(rows),ADC_SPS=rate,ADC_error_increments=errors,
            temperature_range_C=[min(r['temperature']['object_centi'] for r in rows)/100,max(r['temperature']['object_centi'] for r in rows)/100],
            display_round_values=sorted({str((r['temperature']['object_centi']+5)//10//10)+'.'+str((r['temperature']['object_centi']+5)//10%10) for r in rows}),
            HR_values=sorted({r['bio']['hr'] for r in rows}),screen_visual_result='REQUIRES_OWNER_CONFIRMATION')
    except Exception as error:
        if link:link.verified_running_flash=False
        g.save(a.out/'failure-private.json',{'type':type(error).__name__,'reason':str(error)})
        result.update(error_type=type(error).__name__,error_sha256=g.sha(str(error).encode()))
    finally:
        if link:
            try:link.close();result['Close_completed']=True
            except Exception as error:result.update(exit_code=1,Close_completed=False,close_error_type=type(error).__name__)
        g.save(a.out/'receipt-public.json',result)
    print(json.dumps(result),flush=True);return result['exit_code']


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for key in ('install','profile','out'):p.add_argument('--'+key,type=Path,required=True)
    p.add_argument('--execute',action='store_true');p.add_argument('--worker',action='store_true');a=p.parse_args()
    g.private.protected(a.out.parent,False);g.require(not a.out.exists(),'B_SCREEN_OUTPUT_EXISTS')
    if a.worker:raise SystemExit(capture(a))
    if not a.execute:print(json.dumps({'execute':False,'seconds':15,'scope':'B_ONLY_COMPONENT_NO_CAN_CLOUD'}))
    else:raise SystemExit(backup.supervise([sys.executable,'-X','utf8',str(Path(__file__)),'--worker','--install',str(a.install),
        '--profile',str(a.profile),'--out',str(a.out)],a.out))
