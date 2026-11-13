"""P1-B新薄入口的定向Mock验证；不重复P1-A151项或R5回放。"""
from contextlib import redirect_stdout
import hashlib
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import b5_codex_p1b_readonly as p


class Gate(unittest.TestCase):
    def signed(self,changes=None,key_byte=1):
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
        from cryptography.hazmat.primitives.serialization import Encoding,PublicFormat
        key=Ed25519PrivateKey.from_private_bytes(bytes([key_byte])*32)
        public=key.public_key().public_bytes(Encoding.Raw,PublicFormat.Raw)
        expected={'board':'B','repo_commit':'9f5a6641fec2bcdb575f5f9ff549b8e9b0223820',
                  'repo_tree':'5'*40,
                  'tools_sha256':{'SYNTHETIC_TOOL':'1'*64},'DLL_sha256':'2'*64,
                  'identity_reference_sha256':'3'*64,'options_reference_sha256':'6'*64,
                  'full_flash_sha256':'7'*64,'reads':[[0x08000000,1048576,1]],
                  'budget':{'session_s':90,'full_read_s':45,'other_s':5},
                  'site_sha256':'4'*64,'manual_responsibility':'SYNTHETIC_OWNER',
                  'sdk_policy':'SYNTHETIC_RESIDUAL_RISK_ACK_CLOSE_ZERO'}
        a={**expected,'scope':p.SCOPE['B'],'not_before':90,'expires':110,
           'nonce':'SYNTHETIC_ONLY_NONCE_0001','sdk_risk_acknowledged':True}
        a.update(changes or {});raw=json.dumps(a,sort_keys=True).encode()
        return raw,key.sign(raw),public,p.SHA(public),expected,a

    def test_signed_mock_only_positive_and_atomic_nonce(self):
        raw,sig,key,pin,expected,a=self.signed()
        self.assertEqual(p.verify_mock_authorization(raw,sig,key,pin,expected,100),a)
        with tempfile.TemporaryDirectory() as folder:
            marker=p.consume_mock_nonce(Path(folder),raw,a,execution_context='OFFLINE_MOCK')
            p.validate_worker_marker(marker,raw,a)
            with self.assertRaises(FileExistsError):p.consume_mock_nonce(Path(folder),raw,a,execution_context='OFFLINE_MOCK')
            changed={**a,'board':'C','scope':p.SCOPE['C']}
            with self.assertRaisesRegex(ValueError,'MARKER'):p.validate_worker_marker(marker,raw,changed)

    def test_fake_signature_wrong_key_and_untrusted_root(self):
        from cryptography.exceptions import InvalidSignature
        raw,sig,key,pin,expected,a=self.signed()
        for signature,public,trusted in [(b'ok',key,pin),(sig,self.signed(key_byte=2)[2],pin),(sig,key,None)]:
            with self.subTest(signature_size=len(signature)),self.assertRaises((ValueError,InvalidSignature)):
                p.verify_mock_authorization(raw,signature,public,trusted,expected,100)

    def test_modified_payload_without_resigning_refused(self):
        from cryptography.exceptions import InvalidSignature
        raw,sig,key,pin,expected,a=self.signed()
        with self.assertRaises(InvalidSignature):p.verify_mock_authorization(raw+b' ',sig,key,pin,expected,100)

    def test_caller_cannot_omit_required_bindings(self):
        raw,sig,key,pin,expected,a=self.signed()
        for name in expected:
            with self.subTest(name=name),self.assertRaisesRegex(ValueError,'INCOMPLETE_TRUSTED_BINDING'):
                p.verify_mock_authorization(raw,sig,key,pin,{k:v for k,v in expected.items() if k!=name},100)

    def test_bound_fields_and_scope_tampering_refused(self):
        for changes in [{'board':'C'},{'scope':'B5_FINAL_RR15_R6'}, {'not_before':101}, {'expires':100},
                        {'tools_sha256':{}},{'reads':[[0,4,1]]},{'sdk_risk_acknowledged':False},
                        {'DLL_sha256':'9'*64},{'site_sha256':'9'*64}]:
            raw,sig,key,pin,expected,_=self.signed(changes)
            with self.subTest(changes=changes),self.assertRaises(ValueError):
                p.verify_mock_authorization(raw,sig,key,pin,expected,100)

    def test_parent_content_and_cross_board_replay_refused(self):
        raw,sig,key,pin,expected,a=self.signed()
        with tempfile.TemporaryDirectory() as folder:
            marker=p.consume_mock_nonce(Path(folder),raw,a,execution_context='OFFLINE_MOCK')
            for changed in (raw+b' ',b'OLD_G3_TOKEN'):
                with self.assertRaisesRegex(ValueError,'MARKER'):p.validate_worker_marker(marker,changed,a)
            with self.assertRaisesRegex(ValueError,'CONTEXT'):
                p.consume_mock_nonce(Path(folder),raw,a,execution_context='FIELD')

    def test_cli_field_cannot_be_enabled_by_any_document(self):
        for board in ('B','C'):
            with self.subTest(board=board),patch.object(sys,'argv',['FIXTURE','--execute','--board',board,'--authorization','SYNTHETIC_ONLY']),\
                    patch.object(Path,'read_bytes',side_effect=AssertionError('no authorization/SDK read')),redirect_stdout(io.StringIO()):
                self.assertEqual(p.main(),1)

    def test_plan_does_not_import_device_components(self):
        with patch.dict(sys.modules,{'b5_g3_devices':None}):
            self.assertFalse(p.plan('B')['enabled']);self.assertFalse(p.plan('C')['enabled'])


class FakeLink:
    def __init__(self,fault=None):self.fault=fault;self.opened=False;self.closes=0;self.reads=[]
    def open(self):
        if self.fault in ('Device_environment','Connect_error'):self.opened=True
        if self.fault in ('OpenEx_negative','policy_failure','Device_environment','Connect_error'):raise ValueError('P1B_'+self.fault)
        self.opened=True
    def u32(self,address):
        if address==p.STATE['DHCSR'] and self.fault=='HALT':return 1<<17
        if address==p.STATE['VTOR']:return 0x1fff0000 if self.fault=='ROM' else 0x08000000
        return 0x08000020 if address==p.STATE['PCSR'] else 0
    def read(self,address,size):
        self.reads.append((address,size))
        if self.fault in ('negative_read','positive_short_read','timeout','disconnect'):raise ValueError('P1B_'+self.fault)
        if self.fault=='SIGTERM':raise SystemExit('SYNTHETIC_SIGTERM')
        return bytes(size)
    def close(self):
        self.closes+=1
        if self.fault in ('Close_error','Close_timeout'):raise TimeoutError('SYNTHETIC_CLOSE')
        self.opened=False


class Capture(unittest.TestCase):
    def run_capture(self,fault=None):
        link=FakeLink(fault);saved={};full=bytes(1048576);options=bytes(16)
        reference={'identity':{'SYNTHETIC_ID':True},'options_sha256':p.SHA(options)}
        with patch.dict(p.IMAGES,{'B':(40928,p.SHA(full[:40928]),p.SHA(full))}),\
                patch('readback_b.identity',return_value=reference['identity']):
            result=p.capture(link,'B',reference,lambda n,b:saved.update({n:b}))
        return result,link,saved

    def test_readonly_positive_mock_and_close_once(self):
        result,link,saved=self.run_capture()
        self.assertEqual(result['exit_code'],0);self.assertEqual(link.closes,1)
        self.assertEqual(link.reads,[(0x08000000,1048576),(0x1fffc000,16)])
        self.assertEqual(result['SDK_residual_risk'],'UNRESOLVED')
        self.assertEqual(result['target_state_after_Close'],'UNKNOWN_NOT_OBSERVED')

    def test_open_policy_device_and_connect_failures(self):
        for fault in ('OpenEx_negative','policy_failure','Device_environment','Connect_error'):
            with self.subTest(fault=fault):
                result,link,saved=self.run_capture(fault)
                self.assertEqual(result['exit_code'],1);self.assertTrue(result['Close_attempted'])
                self.assertEqual(link.closes,1);self.assertEqual(link.reads,[])
                self.assertEqual(result['native_Close_expected'],fault in ('Device_environment','Connect_error'))

    def test_existing_blink_rejects_numeric_negative_and_short_reads(self):
        from b5_g3_devices import BLink
        for returned,reason in ((-1,'NATIVE_READ_ERROR'),(3,'POSITIVE_SHORT_READ')):
            calls=[];link=BLink.__new__(BLink)
            link.allowed_reads={0x08000000:{4}};link.native_failed=False;link.verified_running_flash=True
            def native(name,*args,**kwargs):
                calls.append((name,args[0],args[1],returned));return returned
            link.call=native
            with self.subTest(returned=returned),self.assertRaisesRegex(ValueError,reason):link.read(0x08000000,4)
            self.assertEqual(calls,[('JLINKARM_ReadMemEx',0x08000000,4,returned)])
            self.assertTrue(link.native_failed);self.assertFalse(link.verified_running_flash)

    def test_read_faults_sigterm_and_no_retry(self):
        for fault in ('negative_read','positive_short_read','timeout','disconnect','SIGTERM'):
            with self.subTest(fault=fault):
                result,link,_=self.run_capture(fault)
                self.assertEqual(result['exit_code'],1);self.assertEqual(link.closes,1)
                self.assertEqual(len(link.reads),1)

    def test_rom_halt_stop_before_full_read(self):
        for fault in ('HALT','ROM'):
            with self.subTest(fault=fault):
                result,link,_=self.run_capture(fault)
                self.assertEqual(result['exit_code'],1);self.assertEqual(link.reads,[])

    def test_close_error_or_timeout_is_not_pass(self):
        for fault in ('Close_error','Close_timeout'):
            with self.subTest(fault=fault):
                result,link,_=self.run_capture(fault)
                self.assertEqual(result['exit_code'],1);self.assertFalse(result['Close_completed'])
                self.assertEqual(link.closes,1)

    def test_kill_cannot_claim_close_or_recovery(self):
        result=p.killed_receipt('LAST_OBSERVED_FLASH')
        self.assertFalse(result['Close_completed']);self.assertEqual(result['retries'],0)
        self.assertEqual(result['Close_attempted'],'UNKNOWN_PROCESS_KILLED')

    def test_c_disarmed_flags_use_bound_address_only(self):
        full=bytes(1048576);reference={'identity':{'SYNTHETIC_C':True},'options_sha256':p.SHA(bytes(16)),
                                     'flags_address':0x20001234}
        link=FakeLink();saved={}
        with patch.dict(p.IMAGES,{'C':(49132,p.SHA(full[:49132]),p.SHA(full))}),\
                patch('readback_b.identity',return_value=reference['identity']):
            r=p.capture(link,'C',reference,lambda name,value:saved.update({name:value}))
        self.assertEqual(r['exit_code'],0)
        self.assertEqual(link.reads,[(0x08000000,1048576),(0x1fffc000,16),(0x20001234,4)])
        self.assertEqual(saved['flags-private.bin'],bytes(4))


if __name__=='__main__':unittest.main()
