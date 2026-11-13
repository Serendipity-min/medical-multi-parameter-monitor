"""gen5及其回退的独立scope入口；默认禁用，不能借用旧G2-B许可。"""
import argparse
import json
from pathlib import Path
import sys
import time
import b5_sector3_write as old
import b5_sector3_write_supervisor as supervisor
import b5_sector3_write_protocol as protocol
import b5_gen5_plan as plan
recovery=old.recovery;ro=old.ro;sha=old.sha;require=old.require
SCOPES={'B5_GEN5_WIFI_WRITE':('provision','gen4-full-private.bin','gen5-full-private.bin','gen5-stage-sector-private.bin'),
    'B5_GEN5_REVERT_GEN4':('restore_config','gen5-full-private.bin','gen4-full-private.bin','gen4-stage-sector-private.bin'),
    'B5_GEN5_RCFG_ORIGINAL_GEN3':('restore_config','gen5-full-private.bin','B5-gen3-full-private.bin','gen3-stage-sector-private.bin')}
CARD='B5-GEN5-AND-G3-OBJECT-AUTHORIZATION-DRAFT.md'


def bindings():
    return {**old.bindings(),'b5_gen5_plan.py':sha(Path(plan.__file__).read_bytes()),'b5_gen5_writer.py':sha(Path(__file__).read_bytes())}


class WifiEngine(protocol.Engine):
    def validate_transition(self,phase,before,after):
        a,_,af=plan.p.parse_record(before);b,_,bf=plan.p.parse_record(after)
        require((a,b)==((4,5) if phase=='provision' else (5,4)),'G5_GENERATION_TRANSITION')
        require(all(f['username']==b'b5-gateway' and f['client_id']==b'b5-c-isolated' for f in (af,bf)),'G5_B5_IDENTITY')
        require(plan.non_wifi(before)==plan.non_wifi(after),'G5_NON_WIFI_CHANGE')


class OriginalConfigEngine(protocol.Engine):
    def validate_transition(self,phase,before,after):
        a,_,af=plan.p.parse_record(before);b,_,bf=plan.p.parse_record(after)
        require(phase=='restore_config' and (a,b)==(5,3) and af['username']==b'b5-gateway'
            and af['client_id']==b'b5-c-isolated' and bf['username']!=b'b5-gateway','G5_ORIGINAL_CONFIG_TRANSITION')


def load_package(folder,manifest_sha):
    folder=Path(folder);raw=recovery.read(folder/'manifest-private.json',False)
    require(sha(raw)==manifest_sha,'G5_PACKAGE_MANIFEST');manifest=json.loads(raw)
    require(manifest['schema']=='B5_GEN5_WIFI_ONLY_PACKAGE_V1' and manifest['hardware_execution_enabled'] is False,'G5_PACKAGE_SCHEMA')
    require({p.name for p in folder.iterdir()}==set(manifest['files'])|{'manifest-private.json'},'G5_PACKAGE_EXTRA_FILES')
    blobs={name:recovery.read(folder/name,False) for name in manifest['files']}
    require(all(len(blobs[n])==m['bytes'] and sha(blobs[n])==m['sha256'] for n,m in manifest['files'].items()),'G5_PAYLOAD_SHA')
    _,_,fields=plan.p.parse_record(blobs['gen5-record-private.bin'])
    rebuilt_manifest,rebuilt=plan.build(blobs['gen4-full-private.bin'],blobs['original-C24104-full-private.bin'],
        {'ssid':fields['ssid'],'password':fields['wifi_password']},blobs['options-private.bin'],blobs['identity-private.json'])
    require(blobs==rebuilt and manifest==rebuilt_manifest,'G5_REBUILT_PACKAGE_MISMATCH')
    return manifest,blobs


def authorize(a,out):
    require(a.get('enabled') is True and a.get('owner_approved') is True and a.get('scope') in SCOPES,'G5_OWNER_SCOPE_REQUIRED')
    require(a['tools_sha256']==bindings() and a['DLL_sha256']==ro.raw.DLL_SHA and time.time()<a['expires_unix'],'G5_SOURCE_OR_EXPIRY')
    require(a['card_sha256']==sha((old.ROOT/'node-b/docs'/CARD).read_bytes()),'G5_CARD_BINDING')
    phase,before,after,stage=SCOPES[a['scope']]
    require(a['phase']==phase and a['board']=='C' and a['session_timeout_s']==180 and a['retries']==0 and a['probe_sessions']==1,'G5_LIMITS')
    require(a['Halt_max']==a['reset_max']==a['Go_max']==a['erase_max']==a['commit_max']==1,'G5_ACTION_LIMITS')
    require(a['nonhuman_mock'] is True and a['failure_cleanup_scope']=='PG_CLEAR_CR_LOCK_AND_ORIGINAL_ACR_IF_IDLE_ONLY'
        and Path(a['output']).resolve()==Path(out).resolve(),'G5_OUTPUT_OR_CLEANUP_SCOPE')
    site_raw=recovery.read(Path(a['site_record']),False);require(sha(site_raw)==a['site_record_sha256'],'G5_SITE_SHA')
    site=json.loads(site_raw)
    require(site.get('JLink_target')=='C' and all(site.get(k) is True for k in ('latest_power_state_checked',
        'A_bus_disconnected','no_human','C_power_ready','USB_and_CAN_state_frozen','BOOT_and_RESET_untouched')),'G5_SITE_NOT_READY')
    require(site.get('ESP_present_powered') is True and site.get('ESP_isolated') is False and site.get('ESP_autonomous_network')=='UNKNOWN'
        and a['ESP_isolated'] is False and a['ESP_autonomous_network']=='UNKNOWN'
        and a['ESP_present_powered_exception_approved'] is True and a['ESP_exception_scope']==a['scope'],'G5_ESP_EXCEPTION')
    old.entry_runtime_state(a)
    if phase=='provision':
        for key,status in [('SNTP','TIME_CLEAN_PASS'),('NTP','FRESH_PUBLIC_NTP_PASS')]:
            raw=recovery.read(Path(a['gate_receipts'][key]['path']),False);gate=json.loads(raw)
            require(sha(raw)==a['gate_receipts'][key]['sha256'] and gate['status']==status and gate['exit_code']==0
                and gate['cleanup_verified'] and gate['Close_completed'],'G5_TIME_GATE_BINDING')
    manifest,blobs=load_package(a['package'],a['package_manifest_sha256'])
    require(a['before_full_sha256']==sha(blobs[before]) and a['after_full_sha256']==sha(blobs[after]),'G5_TRANSACTION_IMAGES')
    recovery.protected(Path(out).parent,False)
    return manifest,blobs,json.loads(blobs['identity-private.json']),blobs[before],blobs[after],blobs[stage]


def worker(authorization,out):
    raw=recovery.read(authorization,False);a=json.loads(raw);loaded=authorize(a,out)
    mark=json.loads(recovery.read(authorization.with_suffix('.used'),False));require(mark['authorization_sha256']==sha(raw),'G5_USED_BINDING')
    out.mkdir();recovery.protected(out,False);link=None;result={'status':'STOP','exit_code':1,'retry_or_auto_rollback':False}
    try:
        count=sum(loaded[-1][i:i+4]!=b'\xff'*4 for i in range(0,16384,4) if i!=20)
        link=old.NativeLink(out,count);link.started=min(link.started,mark['started_monotonic'])
        engine=OriginalConfigEngine if a['scope']=='B5_GEN5_RCFG_ORIGINAL_GEN3' else WifiEngine
        result=old.execute(link,out,a,loaded,engine_type=engine)
        result.update(scope=a['scope'],package_manifest_sha256=a['package_manifest_sha256'],
            after_full_sha256=sha(loaded[4]),
            configuration_generation=plan.p.parse_record(loaded[4][49152:49488])[0],observed_unix=time.time())
    except Exception as error:
        if link:link.verified_running_flash=False
        result.update(status='STOP',exit_code=1,error_type=type(error).__name__,error_sha256=sha(str(error).encode()))
        if link and getattr(link,'active_engine',None) and not link.post_verified and not getattr(link,'raw_failed',False) and not link.error:
            try:
                engine=link.active_engine
                if (engine.keys or engine.acr_history) and engine.phase!='DONE' and link.u32(ro.SYSTEM['DHCSR'])&ro.raw.HALT:engine.failure_lock()
            except Exception as cleanup:result['cleanup_error_type']=type(cleanup).__name__
    finally:
        if link:
            try:
                if not link.verified_running_flash and link.close_resume_enabled:link.set_close_resume(False)
            except Exception as error:result.update(exit_code=1,close_policy_error_type=type(error).__name__)
            finally:
                try:link.close();result['Close_completed']=True
                except Exception as error:result.update(exit_code=1,close_error_type=type(error).__name__)
            result.update(sdk_calls=link.sdk_calls,actions=link.actions,close_resume=link.close_resume_enabled)
        ro.raw.write_json(out/'receipt-private.json',result)
    print(json.dumps({'status':result['status'],'exit_code':result['exit_code']}));return result['exit_code']


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--execute',action='store_true');parser.add_argument('--worker',action='store_true')
    parser.add_argument('--authorization',type=Path);parser.add_argument('--out',type=Path);args=parser.parse_args()
    if not args.execute and not args.worker:print(json.dumps({'enabled':False,'owner_approved':False,'scopes':list(SCOPES),'target_writes':0}));return 0
    if args.worker:return worker(args.authorization,args.out)
    return supervisor.supervise(args.authorization,args.out,backend=sys.modules[__name__])


if __name__=='__main__':raise SystemExit(main())
