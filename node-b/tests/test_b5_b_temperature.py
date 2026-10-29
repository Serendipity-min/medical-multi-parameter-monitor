import contextlib
import io
import json
from pathlib import Path
import struct
import sys
import tempfile
import time
import unittest
from types import SimpleNamespace
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import b5_b_temp_update as u
import b5_b_temp_readonly as r

class TemperatureScopes(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name)
        self.card=self.root/'card.md';self.card.write_bytes(b'SYNTHETIC_CARD')
        self.site=self.root/'site.json'
        self.facts=dict.fromkeys(('JLink_on_B','B_J5','C_unchanged_STOPPED','ESP_present_powered_exception',
            'CAN_GND_BOOT_unchanged','module_3V3_GND_RC_PC10_TD_PC11','no_other_program','no_human'),True)
        self.site.write_text(json.dumps(self.facts))
        self.auth=dict(enabled=True,owner_approved=True,scope=u.SCOPE,phase='install',tools_sha256=u.bindings(),
            DLL_sha256=u.app.raw.DLL_SHA,card_sha256=u.sha(self.card.read_bytes()),session_timeout_s=180,
            probe_sessions=1,retries=0,expires_unix=time.time()+120,output=str(self.root/'out'),
            site_record=str(self.site),site_record_sha256=u.sha(self.site.read_bytes()),B5START=0,
            sector3_options_writes=0,binding='SYNTHETIC_BINDING',binding_sha256='0'*64)
    def authorize(self,a):
        with patch.object(u,'CARD',self.card),patch.object(u.recovery,'read',side_effect=lambda p,s:Path(p).read_bytes()),\
             patch.object(u.recovery,'protected'),patch.object(u,'load_binding',return_value=('bound','m','f')):
            return u.authorize(a,self.root/'out')
    def test_exact_install_scope(self):self.assertEqual(self.authorize(self.auth),('bound','m','f'))
    def test_owner_required(self):
        for k in ('enabled','owner_approved'):
            with self.assertRaisesRegex(ValueError,'OWNER'):self.authorize(dict(self.auth,**{k:False}))
    def test_old_scope_not_permission(self):
        with self.assertRaisesRegex(ValueError,'OWNER'):self.authorize(dict(self.auth,scope='B5_C_EGRESS_APP012_UPDATE'))
    def test_restore_not_implicit(self):
        with self.assertRaisesRegex(ValueError,'INSTALL_ONLY'):self.authorize(dict(self.auth,phase='restore'))
    def test_tools_drift(self):
        with self.assertRaisesRegex(ValueError,'TOOL_SHA'):self.authorize(dict(self.auth,tools_sha256={}))
    def test_card_drift(self):
        with self.assertRaisesRegex(ValueError,'CARD_SHA'):self.authorize(dict(self.auth,card_sha256='f'*64))
    def test_expiry_and_bounds(self):
        for change in ({'expires_unix':0},{'session_timeout_s':181},{'retries':1},{'probe_sessions':2}):
            with self.assertRaisesRegex(ValueError,'BUDGET'):self.authorize(dict(self.auth,**change))
    def test_no_unknown_or_false_site(self):
        for key in self.facts:
            self.site.write_text(json.dumps(dict(self.facts,**{key:None})))
            a=dict(self.auth,site_record_sha256=u.sha(self.site.read_bytes()))
            with self.assertRaisesRegex(ValueError,'SITE_INCOMPLETE'):self.authorize(a)
    def test_no_start_or_config_permission(self):
        for key in ('B5START','sector3_options_writes'):
            with self.assertRaisesRegex(ValueError,'SCOPE'):self.authorize(dict(self.auth,**{key:1}))
    def test_default_never_constructs_native(self):
        for module in (u,r):
            with patch.object(sys,'argv',['test']),contextlib.redirect_stdout(io.StringIO()),patch.object(u,'InstallLink') as native:
                self.assertEqual(module.main(),0);native.assert_not_called()
    def test_temperature_binary_ABI(self):
        blob=bytearray(64);struct.pack_into('<7I3H3B',blob,0,120,0,0,10,1,2,1000,3307,3135,3616,98,0,1)
        blob[49:61]=bytes.fromhex('a4030707620ceb0c3f0e2087')
        row=r.decode_temp(blob);self.assertEqual(row['object_centi'],3307);self.assertEqual(row['last_ms'],1000)
        self.assertEqual(row['last_frame_hex'],'a4030707620ceb0c3f0e2087')
    def test_bad_temperature_ABI(self):
        with self.assertRaisesRegex(ValueError,'DIAG_SIZE'):r.decode_temp(bytes(63))
    def test_readonly_scope_denies_writes(self):
        link=object.__new__(r.Link);link.sdk_calls=0
        for name in ('JLINKARM_Go','JLINKARM_Reset','JLINKARM_Halt','JLINKARM_WriteMem'):
            with self.assertRaisesRegex(ValueError,'RO_API'):link.call(name)
    def test_readonly_rejects_unbound_addresses(self):
        link=object.__new__(r.Link);link.sdk_calls=0
        with self.assertRaisesRegex(ValueError,'RO_ADDRESS'):link.call('JLINKARM_ReadMemEx',0x40004c04,4,None,0)
    def test_readonly_90s_profile_not_180(self):
        state={'killed':False}
        def kill():state['killed']=True;child.returncode=-9
        child=SimpleNamespace(poll=lambda:None if not state['killed'] else -9,kill=kill,wait=lambda timeout:None,returncode=None)
        with patch.object(r.supervisor.time,'monotonic',return_value=90):
            result=r.supervisor.watch(child,self.root,timeout_s=90,started_monotonic=0)
        self.assertTrue(state['killed']);self.assertEqual(result['reason'],'SESSION_TIMEOUT')

if __name__=='__main__':unittest.main()
