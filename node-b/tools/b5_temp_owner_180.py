"""负责人直接授权的一次180秒非人体TEMP只读观察；复用M1Link与温度快照。"""
import argparse
import json
from pathlib import Path
import subprocess
import sys
import time

import b5_m1_entry as m
from b5_m1_owner_once import private_file

SCOPE = 'B5_OWNER_TEMP180_20261031'
PIN = 'b913287d47ab4426614b535453f9a997ace46888e00125a57c1bacfabf43cb93'
RUN = 'OWNER-TEMP180-20261031-ONE'


def tools():
    return {**m.tool_bindings(), 'node-b/tools/b5_temp_owner_180.py': m.sha(Path(__file__).read_bytes())}


def assess(rows):
    from b5_g3_contract import signed
    failures = []
    ages = [signed(x['bio']['last_sample_ms'], x['temperature']['last_ms']) for x in rows]
    if not rows or any(not x['temperature']['present'] or not 0 <= x['temperature']['object_centi'] <= 10000
                       or not -10 <= age <= 2500 for x, age in zip(rows, ages)):
        failures.append('TEMP_FRESH_PRESENT_RANGE')
    increments = {k: rows[-1]['temperature'][k]-rows[0]['temperature'][k]
                  for k in ('frames', 'overflow', 'uart_errors', 'checksum_errors', 'header_errors')}
    if increments['frames'] <= 0 or any(increments[k] for k in increments if k != 'frames'):
        failures.append('TEMP_UPDATE_OR_ERROR_INCREMENT')
    raw_bad = 0
    for x in rows:
        t = x['temperature']; raw = bytes.fromhex(t['last_frame_hex'])
        if len(raw) != 12 or raw[:4] != bytes((0xa4,3,7,7)) or sum(raw[:11]) & 255 != raw[11]:
            raw_bad += 1
    if raw_bad: failures.append('TEMP_LAST_FRAME_CHECKSUM_OR_HEADER')
    values = [x['temperature']['object_centi']/100 for x in rows]
    slots = {int(x['host_monotonic']-rows[0]['host_monotonic']) for x in rows}
    return {'status': 'OWNER_TEMP180_FUNCTIONAL_PASS' if not failures else 'NOT_PASS',
            'exit_code': 3 if failures else 0, 'failures': failures, 'observations': len(rows),
            'first_last_observation_span_s': rows[-1]['host_monotonic']-rows[0]['host_monotonic'],
            'observed_one_second_slots': len(slots), 'temperature_C_min': min(values),
            'temperature_C_max': max(values), 'age_ms_min': min(ages), 'age_ms_max': max(ages),
            'counter_increments': increments, 'bad_last_frame_observations': raw_bad,
            'quantity': 'NONHUMAN_OBJECT_SURFACE', 'absolute_accuracy': 'NOT_CALIBRATED',
            'cloud_end_to_end': 'NOT_RUN', 'formal_frozen_review': 'NOT_RUN_SHORT_OWNER_WINDOW'}


def verify(args):
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
    raw = private_file(args.card).read_bytes(); public = private_file(args.public).read_bytes()
    m.need(m.sha(public) == PIN, 'M1_TEMP_UNTRUSTED_KEY')
    Ed25519PublicKey.from_public_bytes(public).verify(private_file(args.signature).read_bytes(), raw)
    a = json.loads(raw)
    m.need(a['scope'] == SCOPE and a['run_id'] == RUN and a['seconds'] == 180 and a['sessions'] == 1
           and a['retries'] == 0 and a['PI_independent_signature'] is False and a['enabled'] is True,
           'M1_TEMP_SCOPE')
    m.need(a['expires'] > time.time() >= a['not_before'], 'M1_TEMP_EXPIRED')
    m.need(a['tools_sha256'] == tools(), 'M1_TEMP_TOOLS')
    def git(*cmd): return subprocess.check_output(['git', *cmd],cwd=m.ROOT).decode().strip()
    m.need(not git('status','--porcelain') and git('rev-parse','HEAD') == a['repo_commit'], 'M1_TEMP_GIT')
    m.need(a['owner_report'] and a['target_object'] and a['nonhuman'] is True and a['C_USB_disconnected'] is True
           and a['JLink_on_B'] is True and a['sdk_residual_risk_acknowledged'] is True, 'M1_TEMP_SITE')
    bundle_path = private_file(a['bundle']);m.need(m.sha(bundle_path.read_bytes()) == a['bundle_sha256'],'M1_TEMP_BUNDLE')
    bundle = json.loads(bundle_path.read_text());m.validate_bundle(bundle)
    ident = private_file(bundle['identity_reference'])
    m.need(m.sha(ident.read_bytes()) == bundle['identity_reference_sha256'],'M1_TEMP_IDENTITY_REFERENCE')
    out = Path(a['output']).resolve()
    m.need(out.parent.is_relative_to(m.PRIVATE.resolve()) and out.parent.stat().st_file_attributes & 0x4000,
           'M1_TEMP_OUTPUT_EFS')
    m.need(isinstance(a['nonce'],str) and len(a['nonce']) >= 16,'M1_TEMP_NONCE')
    return a, raw, json.loads(ident.read_text()), out


def worker(a, identity, out):
    import b4_runtime as live
    import readback_b as raw
    out.mkdir(); b = out/'B'; b.mkdir(); link = None; rows = []; started = time.monotonic()
    result = {'status':'STOP','exit_code':1,'Close_completed':False,'native_side_effects':'UNRESOLVED',
              'post_Close_state':'UNKNOWN_NOT_OBSERVED','explicit_RESET_HALT_GO_Flash_START':0,'retries':0}
    try:
        link = m.native_link(b,out);link.open()
        seen = raw.identity(link);raw.check_identity(seen);m.save(b/'identity-private.json',seen)
        m.need(seen == identity,'M1_WRONG_BOARD')
        m.save(b/'entry-sticky-private.json',{'DHCSR':link.u32(live.ro.SYSTEM['DHCSR'])})
        full = link.read(0x08000000,1048576);options = link.read(0x1fffc000,16)
        (b/'full-private.bin').write_bytes(full);(b/'options-private.bin').write_bytes(options)
        m.need(m.sha(full)==m.FULL_SHA and m.sha(full[:41012])==m.BIN_SHA and m.sha(options)==m.OPTIONS_SHA,'M1_FIRMWARE_DRIFT')
        first = live.snapshot(link,b,'entry',m.RAM);time.sleep(2)
        previous = live.snapshot(link,b,'ready',m.RAM);live.assess(first,previous)
        begin = time.monotonic();link.phase='capture'
        link.deadline=min(begin+190,started+m.BUDGET['session_s']-m.BUDGET['cleanup_s'])
        with (b/'temperature-observations-private.jsonl').open('x',encoding='utf-8') as log:
            while time.monotonic()-begin < 180:
                cycle = time.monotonic();current=live.snapshot(link,b,'temp-'+str(len(rows)),m.RAM)
                live.assess(previous,current);previous=current;rows.append(current)
                log.write(json.dumps(current)+'\n');log.flush()
                time.sleep(max(0,min(.5-(time.monotonic()-cycle),begin+180-time.monotonic())))
        result['measurement_host_s']=time.monotonic()-begin
        link.phase='closing';link.deadline=time.monotonic()+m.BUDGET['cleanup_s']
        final=live.snapshot(link,b,'final',m.RAM);live.assess(previous,final)
        m.need(m.sha(link.read(0x08000000,41012))==m.BIN_SHA and raw.identity(link)==identity,'M1_POST_IMAGE_OR_IDENTITY_DRIFT')
        link.final_close_verified=True;link.set_close_resume(True)
        result.update(assess(rows));result['temperature_target']=a['target_object']
    except (Exception,KeyboardInterrupt,SystemExit) as error:
        if link: link.verified_running_flash=False;link.final_close_verified=False
        m.save(b/'failure-private.json',{'type':type(error).__name__,'reason':str(error)})
        result.update(exit_code=1,error_type=type(error).__name__,error_sha256=m.sha(str(error).encode()))
    finally:
        if link:
            try: link.close();result['Close_completed']=True
            except Exception as error: result.update(exit_code=1,status='STOP',Close_error_type=type(error).__name__)
        result['session_elapsed_s']=time.monotonic()-started
        if result['session_elapsed_s']>m.BUDGET['session_s']:result.update(exit_code=4,status='SESSION_TIMEOUT')
        m.save(b/'receipt-private.json',result)
    m.save(out/'input-sha256-private.json',{str(p.relative_to(out)):m.sha(p.read_bytes()) for p in b.iterdir() if p.is_file()})
    print(json.dumps(result));return result['exit_code']


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--execute',action='store_true');p.add_argument('--worker',action='store_true')
    for name in ('card','signature','public'):p.add_argument('--'+name,type=Path)
    args=p.parse_args()
    if not(args.execute or args.worker):print(json.dumps({'enabled':False,'scope':SCOPE}));return 0
    a,raw,identity,out=verify(args);ledger=m.PRIVATE/'m1-used-nonces'
    name=m.sha((SCOPE+'\0'+a['nonce']).encode());mark={'scope':SCOPE,'run_id':RUN,'authorization_sha256':m.sha(raw)}
    if args.worker:
        m.need(json.loads((ledger/(name+'.used')).read_text())==mark,'M1_TEMP_PARENT_MARKER')
        m.save(ledger/(name+'.worker-used'),mark);return worker(a,identity,out)
    m.need(not out.exists(),'M1_OUTPUT_EXISTS');m.save(ledger/(name+'.used'),mark)
    cmd=[sys.executable,'-X','utf8',str(Path(__file__)),'--worker','--card',str(args.card),'--signature',str(args.signature),'--public',str(args.public)]
    with out.with_name(out.name+'-worker.log').open('xb') as log:
        child=subprocess.Popen(cmd,stdout=log,stderr=subprocess.STDOUT);result=m.watch_worker(child,out)
    out.mkdir(exist_ok=True);m.save(out/'supervisor-private.json',result)
    print(json.dumps(result));return result['supervisor_exit_code']


if __name__=='__main__':raise SystemExit(main())
