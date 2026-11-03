"""M0薄编排：复用B原帧、C语音和真实Broker/Backend/WSS观察器。"""
import argparse
import asyncio
import datetime
import hashlib
import json
from pathlib import Path
import socket
import subprocess
import sys
import threading
import time

import abc_two_group as abc
import b5_g3_cloud as cloud
import b5_g3_contract as g

ROOT=g.ROOT


def b_session(s,fresh,profile):
    if not fresh or s['gateway_state']!='ONLINE' or s['nodes']['NODE-B']!='ONLINE':return None
    rows={x['stream']:x for x in s['streams'] if x['node_id']=='NODE-B'}
    rate,wave,target,tolerance=('HR','ECG',60,2) if profile=='ECG60' else ('RR','RESP',18,1)
    if not {rate,wave,'TEMP'}<=rows.keys():return None
    selected=[rows[n] for n in (rate,wave,'TEMP')]
    if any(x['validity']!='VALID' for x in selected):return None
    if rows[rate]['value'] is None or abs(rows[rate]['value']-target)>tolerance:return None
    sessions={x['session_id'] for x in selected}
    if len(sessions)!=1:return None
    session=next(iter(sessions))
    return session if session.startswith(fresh.rsplit('-',1)[0]+'-') else None


def prepare(topology,profile,port):
    pointer=json.loads((ROOT/'node-b/build/m0-current-pointer.json').read_text());base=Path(pointer['job'])
    stamp=datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    job=base/(topology+'-'+profile+'-'+stamp);job.mkdir();g.private.protected(job,False)
    (job/'executed-m0-field.py').write_bytes(Path(__file__).read_bytes())
    g.save(job/'tool-source-sha256.json',{name:g.sha((ROOT/name).read_bytes()) for name in ('node-b/tools/m0_field.py','node-b/tools/m0_review.py','node-b/tools/b5_g3_devices.py','node-b/tools/b5_g3_cloud.py','node-b/tools/abc_two_group.py','gateway/microphone/field.py','cloud/backend/app/hub.py','cloud/backend/app/main.py','cloud/backend/app/mqtt_adapter.py')})
    oldstate=json.loads((ROOT/'node-b/build/abc-two-group-resume-state.json').read_text())
    oldjob=Path(json.loads((ROOT/'node-b/build/abc-two-group-pointer.json').read_text())['job'])
    bundle=g.load(Path(oldstate['ECG60_pass_window'])/'bundle-private.json')
    installed=oldjob/oldstate['B_current_install'];proof=g.load(installed/'receipt-private.json')
    g.require(proof['exit_code']==0 and proof['Close_completed'],'M0_B_INSTALL_REFERENCE')
    profile_document=g.load(oldstate['B_current_profile']);profile_data=profile_document['profile_from_actual_symbols']
    for key,state_key,metadata in (('B_ELF','B_current_ELF','AXF'),('B_symbols','B_current_symbols','symbols')):
        path=Path(oldstate[state_key]);digest=g.sha(path.read_bytes())
        g.require(digest==profile_document[metadata]['sha256'],'M0_B41516_SYMBOL_IDENTITY')
        bundle[key]={'path':str(path),'sha256':digest}
    g.require(profile_data['BIN_bytes']==41516 and profile_data['BIN_sha256']==oldstate['B_current_image_sha256'],'M0_B41516_PROFILE')
    bundle['_B_profile']=profile_data;bundle['_ABC_stable_temperature_read']=True
    for key,name in (('B_full','after-full-private.bin'),('B_options','after-options-private.bin'),('B_identity','identity-after-private.json')):
        path=installed/'probe'/name;bundle[key]={'path':str(path),'sha256':g.sha(path.read_bytes())}
    bundle['cloud_package']={'path':str(base/'cloud-package-private.json')}
    bundle['cloud_credentials']={'path':str(base/'cloud-credentials-private.json')}
    g.save(job/'bundle-private.json',bundle)
    previous=Path(pointer['previous_job'])
    for name in ('voice-runtime-credentials-private.json','host-hotspot-runtime-private.json'):
        (job/name).write_bytes((previous/name).read_bytes())
    a={'COM':port,'topology':topology,'channel_profile':profile,'bundle':str(job/'bundle-private.json'),
       'output':str(job/'capture'),'observer_client_id':'m0-observer-'+stamp,'integration_window_s':1200,'debug_speed_khz':4000,
       'host_cancel_cleanup_s':15,'owner_approved':True,'scope':'M0_CURRENT_OWNER_BC_THEN_ABC_NONHUMAN',
       'B5START_allowed':False,'signatures_nonces_cards':False}
    g.save(job/'runtime-inputs-private.json',a)
    (ROOT/'node-b/build/m0-group-current-pointer.json').write_text(json.dumps({'job':str(job),'topology':topology,'profile':profile})+'\n')
    return job,a,bundle


def run(job,a,bundle):
    root=Path(a['output']);root.mkdir();stop=threading.Event();shared={};workers=[];logs=[];tunnel=None
    result={'exit_code':1,'topology':a['topology'],'profile':a['channel_profile'],'B5START':0,'A_B_Flash_writes':0}
    def child(cmd,label):
        log=(job/(label+'-private.log')).open('xb');logs.append(log)
        p=subprocess.Popen(cmd,stdout=log,stderr=subprocess.STDOUT);workers.append(p);return p
    def wait_for(check,seconds,label):
        deadline=time.monotonic()+seconds
        while time.monotonic()<deadline:
            if any((root/n).exists() for n in ('B_FAULT.json','CLOUD_FAULT.json')):raise RuntimeError('M0_WORKER_FAILED')
            if check():return
            time.sleep(.1)
        raise TimeoutError('M0_'+label)
    def field(action,extra=()):
        return child([sys.executable,'-X','utf8',str(ROOT/'gateway/microphone/field.py'),'--unified','--job',str(job),
                      '--port',a['COM'],'--topology',a['topology'],'--action',action,*extra],'field-'+action)
    observer=None;b=None;capture=None
    try:
        with socket.socket() as sock:sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
        tunnel=child(['ssh','-o','BatchMode=yes','-o','StrictHostKeyChecking=yes','-o','ExitOnForwardFailure=yes','-N',
                      '-L',f'127.0.0.1:{port}:127.0.0.1:18885','-L','127.0.0.1:18775:127.0.0.1:18775','tencent-codex'],'broker-tunnel')
        def broker_tunnel_ready():
            g.require(tunnel.poll() is None,'M0_BROKER_TUNNEL')
            try:
                with socket.create_connection(('127.0.0.1',port),timeout=.1):return True
            except OSError:return False
        wait_for(broker_tunnel_ready,15,'BROKER_TUNNEL_NOT_READY')
        settings=g.load(job/'voice-runtime-credentials-private.json')
        a['isolated_broker']={'port':port,'username':'mic-observer','password':settings['roles']['mic-observer']}
        observer=threading.Thread(target=lambda:asyncio.run(cloud.observe(a,root,bundle,stop,shared,
            snapshot_validator=abc.validate_snapshot,session_selector=abc.current_sessions if a['topology']=='ABC' else b_session,
            health_interval_s=None)),daemon=True)
        observer.start()
        wait_for(lambda:(root/'NET_READY.json').exists(),20,'CLOUD_READY_TIMEOUT')
        b=child([sys.executable,'-X','utf8',str(ROOT/'node-b/tools/abc_two_group.py'),'--B-worker',str(job/'runtime-inputs-private.json')],'B-worker')
        wait_for(lambda:(root/'B_READY.json').exists() and (root/'NET_READY.json').exists(),100,'B_AND_CLOUD_READY_TIMEOUT')
        (root/'ARM_PREPARE.json').write_text('{}')
        wait_for(lambda:(root/'ARM_BACKEND_BASELINE.json').exists(),8,'BACKEND_BASELINE_TIMEOUT')
        command=('UNISTART '+a['topology']+'\n').encode()
        g.save(root/'ARM_ATTEMPT.json',{'monotonic':time.monotonic(),'UTC_ms':int(time.time()*1000),
            'bytes':len(command),'command_sha256':g.sha(command),'command':'UNISTART '+a['topology']})
        connect=field('connect');g.require(connect.wait(timeout=190)==0,'M0_C_CONNECT_FAILED')
        print(json.dumps({'event':'M0_C_CONNECTED','topology':a['topology']}),flush=True)
        wait_for(lambda:(root/'CLOUD_COMMON.json').exists(),65,'REAL_TELEMETRY_NOT_READY')
        browser=child([sys.executable,'-X','utf8',str(ROOT/'node-b/tools/abc_webpage.py'),'--job',str(job)],'browser')
        common=g.load(root/'CLOUD_COMMON.json');wait_for(lambda:time.monotonic()>=common['monotonic']+45,50,'WARMUP')
        g.save(job/'VOICE_READY.json',{'monotonic':time.monotonic(),'warmup_s':45,'B_session':common['B_session']})
        print(json.dumps({'event':'M0_READY_PLAY_AUDIO','evaluation_s':300}),flush=True)
        wait_for(lambda:(job/'VOICE_GO').exists(),600,'OWNER_AUDIO_NOT_STARTED')
        capture=field('capture',('--window-seconds','300'))
        wait_for(lambda:any(job.glob('field-capture-*/evaluation.json')),8,'EVALUATION_START')
        evaluation=next(job.glob('field-capture-*/evaluation.json'));e=g.load(evaluation)
        g.save(root/'T0.json',dict(e,B_session=common['B_session'],gateway_session=common['gateway_session'],common_monotonic=common['monotonic'],warmup_completed=True))
        print(json.dumps({'event':'M0_EVALUATION_STARTED','evaluation_s':300,'manual_NIBP':a['topology']=='ABC'}),flush=True)
        wait_for(lambda:capture.poll() is not None,345,'CAPTURE_END_TIMEOUT')
        result['capture_native_exit']=capture.returncode;g.require(capture.returncode==0,'M0_CAPTURE_FAILED')
        (root/'END_B').write_text('');g.require(b.wait(timeout=15)==0,'M0_B_EXIT_FAILED')
        time.sleep(10);(job/'STOP_BROWSER').write_text('');browser.wait(timeout=15);stop.set();observer.join(8);g.require(not observer.is_alive(),'M0_CLOUD_CLOSE_TIMEOUT')
        g.require(g.load(root/'cloud-receipt-private.json')['exit_code']==0,'M0_CLOUD_EXIT_FAILED')
        with (root/'C-lines-private.jsonl').open('xb') as merged:
            for path in sorted(job.glob('field-*/C-lines-private.jsonl')):merged.write(path.read_bytes())
        result.update(exit_code=0,status='M0_CAPTURED_OFFLINE_REVIEW_AND_OWNER_HEARING_PENDING',B_native_exit=b.returncode)
    except Exception as error:
        g.save(job/'failure-private.json',{'type':type(error).__name__,'reason':str(error)})
        result.update(error_type=type(error).__name__,error_sha256=g.sha(str(error).encode()))
        if capture and capture.poll() is None:capture.terminate();capture.wait(timeout=5)
        if (root/'ARM_ATTEMPT.json').exists():
            finish=field('finish');result['cleanup_STOP_native_exit']=finish.wait(timeout=30)
    finally:
        (root/'END_B').write_text('');(job/'STOP_BROWSER').write_text('');stop.set()
        if b and b.poll() is None:
            try:b.wait(timeout=65)
            except subprocess.TimeoutExpired:b.terminate();b.wait(timeout=5)
        if observer:observer.join(8)
        if tunnel and tunnel.poll() is None:tunnel.terminate();tunnel.wait(timeout=5)
        for log in logs:log.close()
        result['worker_native_exit_codes']=[p.returncode for p in workers];g.save(job/'receipt-private.json',result)
    print(json.dumps(result),flush=True);return result['exit_code']


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--topology',choices=('BC','ABC'),required=True)
    p.add_argument('--profile',choices=('ECG60','RR18'),required=True);p.add_argument('--port',required=True);p.add_argument('--execute',action='store_true');a=p.parse_args()
    if not a.execute:print(json.dumps({'execute':False,'evaluation_s':300,'warmup_s':45,'software_CAN_replay':False}));return 0
    job,inputs,bundle=prepare(a.topology,a.profile,a.port);print(json.dumps({'job':str(job)}),flush=True)
    return run(job,inputs,bundle)


if __name__=='__main__':raise SystemExit(main())
