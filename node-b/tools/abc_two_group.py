"""A/B/C非人体两组采集薄适配：复用原B记录器、云观察器和420秒联合流程。"""
import argparse
import asyncio
import datetime
import json
from pathlib import Path
import subprocess
import sys
import time

import b5_g3_cloud as cloud
import b5_g3_contract as g
import b5_g3_devices as devices
import b5_g3_joint as joint

BANNER='B5 DISARMED MOCK ABC_DUAL_CAN NO_FLASH_WRITE'


def validate_snapshot(s,profile=None):
    g.require(s.get('gateway_id')=='GW-B5-001' and {'NODE-A','NODE-B'}<=s.get('nodes',{}).keys(),'G3_ABC_SNAPSHOT_IDENTITY')
    for x in s.get('streams',[]):
        g.require(x.get('source')=='MOCK' and x.get('synthetic') is True,'G3_ABC_SOURCE')
        if x['validity']!='VALID':g.require(x.get('value') is None and not x.get('samples'),'G3_ABC_INVALID_MASK')


def current_sessions(s,fresh_gateway,profile):
    if s.get('gateway_state')!='ONLINE' or any(s['nodes'].get(n)!='ONLINE' for n in ('NODE-A','NODE-B')):return None
    by_node={node:[x for x in s['streams'] if x['node_id']==node] for node in ('NODE-A','NODE-B')}
    by_node['NODE-A']=[x for x in by_node['NODE-A'] if not (x['stream']=='NIBP' and x['validity'] in ('STALE','OFFLINE'))]
    prefix=fresh_gateway.rsplit('-',1)[0]+'-'
    for rows in by_node.values():
        sessions={x['session_id'] for x in rows}
        if len(sessions)!=1 or not next(iter(sessions)).startswith(prefix):return None
    b={x['stream']:x for x in by_node['NODE-B']}
    rate,wave,target,tolerance=('HR','ECG',60,2) if profile=='ECG60' else ('RR','RESP',18,1)
    if not {rate,wave,'TEMP'}<=b.keys():return None
    if any(b[n]['validity']!='VALID' for n in (rate,wave,'TEMP')):return None
    if b[rate]['value'] is None or abs(b[rate]['value']-target)>tolerance:return None
    return next(iter({x['session_id'] for x in by_node['NODE-B']}))


class SerialGate(joint.SerialGate):
    def consume(self,line,*args,**kwargs):
        if line=='B5 DISARMED MOCK B_ONLY NO_FLASH_WRITE':raise ValueError('G3_ABC_WRONG_C_IMAGE')
        if line.startswith('ABC A_CAN '):
            v={k:int(n) for k,n in (part.split('=') for part in line[10:].split())}
            g.require(not(v['txfail'] or v['overflow'] or v['esr']&7 or v['esr']>>16),'G3_ABC_A_CAN_ERROR')
        return super().consume('B5 DISARMED MOCK B_ONLY NO_FLASH_WRITE' if line==BANNER else line,*args,**kwargs)


def observe(a,root,bundle,stop,shared):
    return asyncio.run(cloud.observe(a,root,bundle,stop,shared,snapshot_validator=validate_snapshot,session_selector=current_sessions))


def make_inputs(profile):
    from serial.tools import list_ports
    parent=Path(json.loads((g.ROOT/'node-b/build/abc-two-group-pointer.json').read_text())['job'])
    stamp=datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    job=parent/(profile+'-'+stamp);job.mkdir();g.private.protected(job,False)
    old=json.loads((g.ROOT/'node-b/build/codex-ECG-TEMP-current-pointer.json').read_text());bundle=g.load(old['bundle'])
    state=json.loads((g.ROOT/'node-b/build/abc-two-group-resume-state.json').read_text())
    c=parent/state['C_install'];c_proof=g.load(c/'receipt-private.json')
    g.require(c_proof['exit_code']==0 and c_proof['Close_completed'] and c_proof['outside_affected_sectors_unchanged'],'G3_ABC_C_NOT_INSTALLED')
    a_proof=g.load(parent/'A-restored-candidate/receipt-private.json')
    g.require(a_proof['exit_code']==0 and a_proof['Close_completed'],'G3_ABC_A_NOT_INSTALLED')
    for name,file in (('C_full','after-full-private.bin'),('C_options','after-options-private.bin'),('C_identity','identity-after-private.json')):
        p=c/'probe'/file;bundle[name]={'path':str(p),'sha256':g.sha(p.read_bytes())}
    bundle['_expected_C_full_sha256']=c_proof['full_flash_sha256'];bundle['_require_source_STOP_state']=True
    bundle['_ABC_stable_temperature_read']=True
    g.save(job/'bundle-private.json',bundle)
    ports=[p.device for p in list_ports.comports() if p.vid==0x1a86 and p.pid==0x7523]
    g.require(len(ports)==1,'G3_ABC_C_SERIAL_NOT_UNIQUE')
    a={'scope':'ABC_OWNER_TWO_GROUP_'+profile,'authority':'CURRENT_USER_ENGINEERING_REQUEST_NO_PI_SIGNATURE_NONCE_CARD',
       'owner_approved':True,'B5START_allowed':True,'COM':ports[0],'output':str(job/'capture'),
       'bundle':str(job/'bundle-private.json'),'channel_profile':profile,'observer_client_id':'b5-g3-observer-abc-'+stamp,
       'precommon_ntp_retries_max':2,'owner_manual_reset_preapproved':True,'reset_confirmation':'SERIAL_DISARMED_AFTER_INTENT',
       'operator_wait_extra_s':600,'host_cancel_cleanup_s':15,'source_truth_RR_HR':'SOURCE_UNKNOWN_ROOT_CAUSE_UNRESOLVED',
       'NIBP_source':'HKB08B_PLUS_NONHUMAN_SAFE_GAS_PATH_OWNER_SUPERVISED','NIBP_new_result_required_per_group':True,
       'formal_PI_acceptance':False,'Git_source':subprocess.check_output(['git','rev-parse','HEAD'],cwd=g.ROOT).decode().strip()}
    g.save(job/'runtime-inputs-private.json',a)
    (g.ROOT/'node-b/build/abc-current-group-pointer.json').write_text(json.dumps({'job':str(job),'profile':profile})+'\n')
    return job,a


def supervise(job,a):
    inputs=job/'runtime-inputs-private.json';out=Path(a['output']);reason=None;notices=set();started=time.monotonic()
    with (job/'collector-worker-private.log').open('xb') as log:
        child=subprocess.Popen([sys.executable,'-X','utf8',str(Path(__file__)),'--joint-worker',str(inputs)],stdout=log,stderr=subprocess.STDOUT)
        try:
            while child.poll() is None:
                now=time.monotonic();arm=g.maybe(out/'ARM_ATTEMPT.json')
                if (out/'RESET_REQUESTED.json').exists() and 'reset' not in notices:
                    print(json.dumps({'event':'READY_PRESS_C_RESET','group':a['channel_profile']}),flush=True);notices.add('reset')
                if (out/'T0.json').exists() and 'common' not in notices:
                    print(json.dumps({'event':'ABC_COMMON_T0','group':a['channel_profile'],'warmup_s':45,'evaluation_s':300}),flush=True);notices.add('common')
                if arm and 'arm' not in notices:print(json.dumps({'event':'ABC_START_SENT','business_stop_s':420}),flush=True);notices.add('arm')
                if now>(arm['monotonic']+445 if arm else started+g.prearm_seconds(a)+30):reason='COLLECTOR_SESSION_DEADLINE'
                if (out/'STOP-SUPERVISOR').exists():reason='OWNER_STOP'
                for filename,label in (('B/heartbeat-events.jsonl','B_NATIVE_TIMEOUT'),('serial-API-events.jsonl','SERIAL_TIMEOUT')):
                    e=joint.last_event(out/filename)
                    if e.get('active') and now>e['deadline_monotonic']:reason=label
                if arm and now>arm['monotonic']+422 and not (out/'C_STOP_BANNER.json').exists():reason='MCU_STOP_NOT_CONFIRMED'
                if reason:subprocess.run(['taskkill','/PID',str(child.pid),'/T','/F'],capture_output=True,timeout=8);break
                time.sleep(.05)
            child.wait(timeout=5)
        finally:
            if child.poll() is None:
                subprocess.run(['taskkill','/PID',str(child.pid),'/T','/F'],capture_output=True,timeout=8);child.wait(timeout=5)
    result={'actual_joint_worker_exit_code':child.returncode,'supervisor_reason':reason,
        'actual_supervisor_exit_code':0 if child.returncode==0 and reason is None else 1,'profile':a['channel_profile'],
        'hardware_or_end_to_end_pass':'REQUIRES_OFFLINE_REVIEW_AND_OPERATOR_DISPLAY_COMPARISON',
        'signatures_nonces_execution_cards_used':False}
    g.save(job/'supervisor-private.json',result);print(json.dumps(result),flush=True);return result['actual_supervisor_exit_code']


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--group',choices=('ECG60','RR18'));p.add_argument('--execute',action='store_true')
    p.add_argument('--B-worker',type=Path);p.add_argument('--joint-worker',type=Path);a=p.parse_args()
    worker=a.B_worker or a.joint_worker
    if worker:
        inputs=g.load(worker);bundle=g.load(inputs['bundle']);root=Path(inputs['output'])
        if a.B_worker:return devices.b_worker(inputs,root,bundle,start_record_name='B-worker-started.json')
        return joint.joint_worker(worker,inputs,bundle,b_worker_command=[sys.executable,'-X','utf8',str(Path(__file__)),'--B-worker',str(worker)],
            serial_gate_factory=SerialGate,cloud_runner=observe,banner_line=BANNER)
    if not a.execute:print(json.dumps({'execute':False,'groups':['ECG60','RR18'],'no_signature_nonce_or_execution_card':True}));return 0
    g.require(a.group is not None,'G3_ABC_GROUP_REQUIRED');job,inputs=make_inputs(a.group);return supervise(job,inputs)


if __name__=='__main__':raise SystemExit(main())
