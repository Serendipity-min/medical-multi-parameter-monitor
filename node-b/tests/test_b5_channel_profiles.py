import copy
import base64
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch
from contextlib import ExitStack
import time
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import b5_channel_profiles as p
import b5_g3_cloud as c
import b5_g3_contract as g

def snapshot(profile):
    rows=[]
    for name in ('ECG','HR','RESP','RR','TEMP'):
        valid=name in p.criteria(profile)['expected_valid']
        value=60.0 if name=='HR' else 15.0 if name=='RR' else 27.05
        rows.append(dict(node_id='NODE-B',stream=name,session_id='can-1234-1',source='MOCK',synthetic=True,
            validity='VALID' if valid else 'INVALID',value=None if name in ('ECG','RESP') or not valid else value,
            samples=[1.0]*100 if name=='ECG' and valid else [1.0]*50 if name=='RESP' and valid else []))
    return dict(gateway_id='GW-B5-001',nodes={'NODE-A':'OFFLINE','NODE-B':'ONLINE'},streams=rows)

class Profiles(unittest.TestCase):
    def test_time_init_scope_is_new_and_ECG_only(self):
        self.assertEqual(set(p.FINAL_SCOPES_R4TI),{'ECG60'})
        self.assertFalse(set(p.FINAL_SCOPES_R4TI.values())&set(p.FINAL_SCOPES_R4TB.values()))
        for profile in ('RR15','TEMP_OBJECT'):
            a=dict(enabled=True,owner_approved=True,scope=p.FINAL_SCOPES_R4TI['ECG60'],channel_profile=profile,require_source_STOP_state=True)
            with self.assertRaisesRegex(ValueError,'FINAL_OBJECT'):g.validate(a,g.G3)
    def test_diagnostic_successor_is_not_a_consumed_time_close_window(self):
        self.assertFalse(set(p.FINAL_SCOPES_R4D.values())&set(p.FINAL_SCOPES_R4TC.values()))
        a=dict(enabled=True,owner_approved=True,scope=p.FINAL_SCOPES_R4D['ECG60'],channel_profile='RR15',require_source_STOP_state=True)
        with self.assertRaisesRegex(ValueError,'FINAL_OBJECT'):p.validate(a)
        a.update(channel_profile='ECG60',require_source_STOP_state=False)
        with self.assertRaisesRegex(ValueError,'FINAL_OBJECT'):p.validate(a)
    def test_final_objects_cannot_be_shared_or_mapped_to_another_profile(self):
        self.assertEqual(len(set(p.FINAL_SCOPES.values())),3)
        self.assertEqual(len(set((*p.FINAL_SCOPES.values(),*p.FINAL_SCOPES_R2.values()))),6)
        self.assertEqual(len(set((*p.FINAL_SCOPES.values(),*p.FINAL_SCOPES_R2.values(),*p.FINAL_SCOPES_R3.values()))),9)
        a=dict(enabled=True,owner_approved=True,scope=p.FINAL_SCOPES['ECG60'],channel_profile='TEMP_OBJECT',require_source_STOP_state=True)
        with self.assertRaisesRegex(ValueError,'FINAL_OBJECT'):p.validate(a)
    def test_time_bootstrap_new_objects_do_not_reuse_D_scopes(self):
        self.assertFalse(set(p.FINAL_SCOPES_R4D.values()) & set(p.FINAL_SCOPES_R4TB.values()))
        for profile in p.PROFILES:
            a=dict(enabled=True,owner_approved=True,scope=p.FINAL_SCOPES_R4TB[profile],channel_profile=profile)
            with self.assertRaisesRegex(ValueError,'FINAL_OBJECT'):g.validate(a,g.G3)
        a=dict(enabled=True,owner_approved=True,scope=p.FINAL_SCOPES_R4TB['ECG60'],channel_profile='RR15',require_source_STOP_state=True)
        with self.assertRaisesRegex(ValueError,'FINAL_OBJECT'):p.validate(a)
    def test_final_object_requires_source_stop_proof(self):
        a=dict(enabled=True,owner_approved=True,scope=p.FINAL_SCOPES['ECG60'],channel_profile='ECG60')
        with self.assertRaisesRegex(ValueError,'FINAL_OBJECT'):p.validate(a)
    def test_old_criteria_remain_invalid(self):
        old=copy.deepcopy(g.CRITERIA)
        for name in p.PROFILES:p.criteria(name)
        self.assertEqual(g.CRITERIA,old);self.assertEqual(old['TEMP'],'INVALID');self.assertEqual(old['RR'],'INVALID')
    def test_three_profiles_are_independent(self):
        self.assertEqual(p.criteria('ECG60')['expected_valid'],['ECG','HR'])
        self.assertEqual(p.criteria('RR15')['expected_valid'],['RESP','RR'])
        self.assertEqual(p.criteria('TEMP_OBJECT')['expected_valid'],['TEMP'])
    def test_durations_and_source_minimum_not_relaxed(self):
        for name in p.PROFILES:
            x=p.criteria(name)
            for key in ('warmup_s','evaluation_s','arm_hard_s','ECG_min_points','RESP_min_points','WSS_min_saved'):
                self.assertEqual(x[key],g.CRITERIA[key])
    def test_reference_not_invented(self):
        x=p.criteria('TEMP_OBJECT');self.assertIsNone(x['temperature_reference']);self.assertEqual(x['temperature_accuracy'],'NOT_CALIBRATED')
    def test_current_session_each_profile(self):
        for name in p.PROFILES:self.assertEqual(c.current_b_session(snapshot(name),'can-1234-2',name),'can-1234-1')
    def test_cross_profile_not_ready(self):
        self.assertIsNone(c.current_b_session(snapshot('RR15'),'can-1234-2','ECG60'))
        self.assertIsNone(c.current_b_session(snapshot('ECG60'),'can-1234-2','RR15'))
    def test_stale_RESP_session_not_accepted(self):
        s=snapshot('RR15');next(x for x in s['streams'] if x['stream']=='RESP')['session_id']='can-old-1'
        self.assertIsNone(c.current_b_session(s,'can-1234-2','RR15'))
    def test_old_gateway_not_current(self):self.assertIsNone(c.current_b_session(snapshot('TEMP_OBJECT'),'can-999-1','TEMP_OBJECT'))
    def test_replay_never_current(self):
        s=snapshot('TEMP_OBJECT');s['streams'][0]['source']='REPLAY'
        self.assertIsNone(c.current_b_session(s,'can-1234-2','TEMP_OBJECT'))
    def test_temperature_stale_not_ready(self):
        s=snapshot('TEMP_OBJECT');s['streams'][-1].update(validity='STALE',value=None)
        self.assertIsNone(c.current_b_session(s,'can-1234-2','TEMP_OBJECT'))
    def test_temperature_domain(self):
        s=snapshot('TEMP_OBJECT');s['streams'][-1]['value']=100.01
        self.assertIsNone(c.current_b_session(s,'can-1234-2','TEMP_OBJECT'))
    def test_invalid_mask_remains_enforced(self):
        s=snapshot('TEMP_OBJECT');s['streams'][1]['value']=60.0
        with self.assertRaisesRegex(ValueError,'INVALID_MASK'):p.assert_snapshot(s,'TEMP_OBJECT')
    def test_formal_or_live_source_rejected(self):
        s=snapshot('TEMP_OBJECT');s['streams'][-1].update(source='LIVE',synthetic=False)
        with self.assertRaisesRegex(ValueError,'SOURCE'):p.assert_snapshot(s,'TEMP_OBJECT')
    def test_no_active_A(self):
        s=snapshot('TEMP_OBJECT');s['nodes']['NODE-A']='ONLINE'
        with self.assertRaisesRegex(ValueError,'NAMESPACE'):p.assert_snapshot(s,'TEMP_OBJECT')
    def test_old_G3_does_not_accept_valid_temperature(self):
        with self.assertRaisesRegex(ValueError,'RR_TEMP'):g.assert_snapshot(snapshot('TEMP_OBJECT'))
    def test_new_scope_not_old_authorization(self):
        with self.assertRaisesRegex(ValueError,'OWNER'):p.validate({'enabled':True,'owner_approved':True,'scope':g.G3})
    def test_profile_unknown_rejected(self):
        with self.assertRaisesRegex(ValueError,'PROFILE'):p.criteria('ECG_RR_SIMULTANEOUS')

class SyntheticAdmission(unittest.TestCase):
    def admission(self,changes=None,broken=None):
        # 仅内存夹具；不生成可执行私有授权、不访问目标或真实云。
        encode=lambda x:json.dumps(x).encode()
        blobs={n:('SYNTHETIC_'+n).encode() for n in ('B_identity','B_full','B_options','C_identity','C_full','C_options','B_ELF','B_symbols','cloud_credentials')}
        blobs['B_full']=b'SYNTHETIC_B'+bytes(40928)
        env={'Backend_sources':{'models.py':g.sha(b'SYNTHETIC_BACKEND')}}
        blobs['cloud_package']=encode({'sources':{'backend/app/models.py':base64.b64encode(b'SYNTHETIC_BACKEND').decode()}})
        bundle={n:{'path':n,'sha256':g.sha(b)} for n,b in blobs.items()}
        full=g.sha(blobs['B_full']);cf=g.sha(blobs['C_full'])
        blobs['install']=encode(dict(status='B_TEMP_INSTALL_FULL_VERIFY_AND_FLASH_BOOT_PASS',exit_code=0,Close_completed=True,full_flash_sha256=full))
        blobs['temperature']=encode(dict(status='B_TEMP_READONLY_CAPTURED',exit_code=0,new_valid_frames=3,Close_completed=True,full_flash_sha256=full))
        blobs['cpre']=encode(dict(status='C_CURRENT_B5_CONFIG_DISARMED_READONLY_PASS',exit_code=0,full_sha256=cf,observed_unix=time.time()))
        source=dict(p.SOURCE_ECG)
        site=dict(source=source,temperature_source='GY641V3_NONHUMAN_OBJECT_NO_REFERENCE',JLink_target='B',C_USB_connector='USB_UART/USB232',C_USB_port='COM6')
        site.update(dict.fromkeys(('COM_confirmed','C_J5','B_J5','CAN_GND_unchanged','A_disconnected','INMP441_TTS_disconnected','ESP_present_powered_exception','operator_ready_manual_cutoff','one_C_reset_preplanned_only','B_USB_disconnected','exclusive_test_namespace'),True))
        blobs['site']=encode(site);blobs['bundle']=encode(bundle)
        a=dict(enabled=True,owner_approved=True,scope=p.SCOPE,channel_profile='ECG60',tools_sha256={'SYNTHETIC_TOOL':'0'},criteria=p.criteria('ECG60'),environment=env,
            card_sha256=g.sha(p.CARD.read_bytes()),expires_unix=time.time()+2000,retries=0,B5START_allowed=True,start_max=1,
            precommon_ntp_retries_max=2,operator_wait_extra_s=180,host_cancel_cleanup_s=10,test_service_expiry_unix=time.time()+2000,
            DLL_sha256=p.temp.raw.DLL_SHA,bundle='bundle',bundle_sha256=g.sha(blobs['bundle']),B_install_receipt='install',B_install_receipt_sha256=g.sha(blobs['install']),
            B_temperature_receipt='temperature',B_temperature_receipt_sha256=g.sha(blobs['temperature']),C_preflight_receipt='cpre',C_preflight_receipt_sha256=g.sha(blobs['cpre']),
            site_record='site',site_record_sha256=g.sha(blobs['site']),COM='COM6',observer_username='b5-observer',observer_client_id='b5-g3-observer-synthetic',output='SYNTHETIC_NO_TARGET')
        if changes:a.update(changes)
        if broken:
            key,value=broken;blobs[key]=encode(value)
            field={'temperature':'B_temperature_receipt_sha256','install':'B_install_receipt_sha256','site':'site_record_sha256'}[key]
            a[field]=g.sha(blobs[key])
        with ExitStack() as stack:
            stack.enter_context(patch.object(g.private,'read',side_effect=lambda path,_:blobs[str(path)]))
            stack.enter_context(patch.object(g.private,'protected'))
            stack.enter_context(patch.object(g,'bindings',return_value={'SYNTHETIC_TOOL':'0'}))
            stack.enter_context(patch.object(g,'environment',return_value=env))
            stack.enter_context(patch.object(g,'expected_c_full',return_value=cf))
            stack.enter_context(patch.object(p,'B_ELF',g.sha(blobs['B_ELF'])))
            stack.enter_context(patch.object(p,'B_SYMBOLS',g.sha(blobs['B_symbols'])))
            stack.enter_context(patch.object(p,'CLOUD_PACKAGE_SHA',g.sha(blobs['cloud_package'])))
            stack.enter_context(patch.object(p.update,'CANDIDATE_BIN',g.sha(blobs['B_full'][:40928])))
            return p.validate(a)
    def test_bound_synthetic_scope_admitted_without_IO(self):
        b,s=self.admission();self.assertEqual(b['_B_profile']['slots'],0x2000216c);self.assertEqual(s['C_USB_port'],'COM6')
    def test_changed_criteria_not_admitted(self):
        with self.assertRaisesRegex(ValueError,'FROZEN_BINDING'):self.admission({'criteria':dict(p.criteria('ECG60'),evaluation_s=30)})
    def test_residency_not_silently_shortened(self):
        with self.assertRaisesRegex(ValueError,'RESIDENCY'):self.admission({'test_service_expiry_unix':time.time()+600})
    def test_observer_is_not_publisher(self):
        with self.assertRaisesRegex(ValueError,'OBSERVER_IDENTITY'):self.admission({'observer_username':'b5-gateway'})
    def test_no_offline_only_temperature(self):
        with self.assertRaisesRegex(ValueError,'TEMP_INPUT'):self.admission(broken=('temperature',dict(exit_code=0,status='SOFTWARE_PASS',new_valid_frames=0)))
    def test_R3_serial_confirmation_requires_new_card_and_intent(self):
        changed={'execution_card':p.CONTINUE_CARD.name,'card_sha256':g.sha(p.CONTINUE_CARD.read_bytes()),
                 'reset_confirmation':'SERIAL_DISARMED_AFTER_INTENT','owner_manual_reset_preapproved':True}
        b,_=self.admission(changed);self.assertEqual(b['_B_profile']['BIN_bytes'],40928)
        with self.assertRaisesRegex(ValueError,'RESET_CONFIRMATION'):self.admission(dict(changed,owner_manual_reset_preapproved=False))
    def test_R2_cannot_silently_enable_new_confirmation(self):
        with self.assertRaisesRegex(ValueError,'RESET_CONFIRMATION'):
            self.admission({'reset_confirmation':'SERIAL_DISARMED_AFTER_INTENT','owner_manual_reset_preapproved':True})

if __name__=='__main__':unittest.main()
