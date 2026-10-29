"""新C候选的包/ABI、只读门禁和停止回退边界；不加载DLL、不连接设备。"""
import ctypes as C
import io
import json
from pathlib import Path
import struct
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[2]
sys.path[:0]=[str(ROOT/'node-b/tools'),str(ROOT/'node-b/tests')]
import b5_c_app_update as u
import b5_g3_contract as g
import b5_g3_devices as d
from test_b4_swd_install import Fake


class Tests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(dir=ROOT/'node-b/build',prefix='c-update-synthetic-')
        self.addCleanup(self.tmp.cleanup);self.out=Path(self.tmp.name)
        old=bytearray(b'\xa5'*1048576);struct.pack_into('<II',old,0,0x20020000,0x08000101)
        old[256:256+len(u.recovery.MARKER)]=u.recovery.MARKER
        image=bytearray(b'\x3c'*42764);struct.pack_into('<II',image,0,0x20020000,0x08000201)
        image[256:256+len(u.recovery.MARKER)]=u.recovery.MARKER
        identity={'device_id':0x10000413,'cpuid':0x410fc241,'capacity_kib':1024,
                  'uid_hex':u.recovery.SYNTHETIC_UID,'optcr':0x0fffaaed,'flash_sr':0}
        self.m,self.files=u.recovery.make_plan('C',bytes(old),bytes(old),b'\xaa'*16,b'\xaa'*16,
            identity,identity,bytes(image),u.sha(image),True)
        package=self.out/'package';package.mkdir()
        for name,data in self.files.items():(package/name).write_bytes(data)
        manifest=u.recovery.encoded(self.m);(package/'manifest-private.json').write_bytes(manifest)
        symbols=b'2000191a b mqtt_connected\n2000191b b network_open\n2000191c b stopped\n2000191d b armed\n'
        (self.out/'symbols.txt').write_bytes(symbols);(self.out/'app.elf').write_bytes(b'SYNTHETIC_ELF')
        self.binding={'package':str(package),'manifest_sha256':u.sha(manifest),
            'before_full_sha256':u.sha(old),'after_full_sha256':u.sha(self.files['expected-full-private.bin']),
            'symbols':str(self.out/'symbols.txt'),'symbols_sha256':u.sha(symbols),
            'ELF':str(self.out/'app.elf'),'ELF_sha256':u.sha(b'SYNTHETIC_ELF'),'flags_address':0x2000191a}
    def load(self,**changes):
        b=dict(self.binding,**changes);raw=u.recovery.encoded(b);path=self.out/'binding.json';path.write_bytes(raw)
        return u.load_binding(path,u.sha(raw),True)
    def test_offline_package_layout_and_exact_restore(self):
        b,m,f=self.load();self.assertEqual(m['sectors'],[0,1,2]);self.assertEqual(b['flags_address'],0x2000191a)
        self.assertEqual(f['expected-full-private.bin'][49152:],f['before-full-private.bin'][49152:])
        restored=f['restore-sectors-private.bin']+f['expected-full-private.bin'][49152:]
        self.assertEqual(restored,f['before-full-private.bin'])
    def test_wrong_old_ABI_cannot_claim_disarmed(self):
        with self.assertRaisesRegex(ValueError,'FLAG_LAYOUT'):self.load(flags_address=u.OLD_FLAGS)
    def test_changed_candidate_package_rejected(self):
        path=Path(self.binding['package'])/'candidate-private.bin';path.write_bytes(path.read_bytes()[:-1]+b'\0')
        with self.assertRaisesRegex(ValueError,'PAYLOAD_CHANGED'):self.load()
    def test_changed_symbols_rejected(self):
        (self.out/'symbols.txt').write_bytes(b'20001918 b mqtt_connected\n')
        with self.assertRaisesRegex(ValueError,'ABI_ARTIFACTS'):self.load()
    def test_changed_before_hash_rejected(self):
        with self.assertRaisesRegex(ValueError,'IMAGES'):self.load(before_full_sha256='0'*64)
    def predecessor(self,before=None,flags=0x2000191a,**changes):
        before=before or u.BEFORE_R1
        proof=dict(status='C_EGRESS_INSTALL_FULL_VERIFY_DISARMED_PASS',exit_code=0,Close_completed=True,
                   DISARMED=True,full_flash_sha256=before);proof.update(changes)
        blob=json.dumps(proof).encode();b=dict(self.binding,before_full_sha256=before,before_flags_address=flags,
               prior_install_receipt='SYNTHETIC_PREDECESSOR',prior_install_receipt_sha256=u.sha(blob))
        raw=u.recovery.encoded(b);path=self.out/'binding.json';path.write_bytes(raw)
        m=json.loads(json.dumps(self.m));m['files']['before-full-private.bin']['sha256']=before
        def read(p,synthetic):return blob if str(p)=='SYNTHETIC_PREDECESSOR' else Path(p).read_bytes()
        with patch.object(u.recovery,'read',side_effect=read),patch.object(u.recovery,'load_package',return_value=(m,self.files)):
            return u.load_binding(path,u.sha(raw),False)
    def test_R2_accepts_only_actual_closed_R1_predecessor(self):
        b,_,_=self.predecessor();self.assertEqual(b['before_full_sha256'],u.BEFORE_R1)
    def test_final_R2_requires_deployed46456_specific_flags_and_receipt(self):
        b,_,_=self.predecessor(before=u.BEFORE_FINAL_R1,flags=0x20001dc2)
        self.assertEqual(b['before_full_sha256'],u.BEFORE_FINAL_R1)
        with self.assertRaisesRegex(ValueError,'GEN5_BASELINE'):self.predecessor(before=u.BEFORE_FINAL_R1)
        with self.assertRaisesRegex(ValueError,'PREDECESSOR_NOT_PASS'):
            self.predecessor(before=u.BEFORE_FINAL_R1,flags=0x20001dc2,Close_completed=False)
    def test_diagnostic_requires_actual46584_closed_predecessor(self):
        b,_,_=self.predecessor(before=u.BEFORE_FINAL_R2,flags=0x20001dc2)
        self.assertEqual(b['before_full_sha256'],u.BEFORE_FINAL_R2)
        with self.assertRaisesRegex(ValueError,'GEN5_BASELINE'):self.predecessor(before=u.BEFORE_FINAL_R2)
    def test_diagnostic_schedule_requires_verified_C48988_and_exact_flags(self):
        b,_,_=self.predecessor(before=u.BEFORE_REPAIR_R4TC,flags=0x20001e6a)
        self.assertEqual(b['before_full_sha256'],u.BEFORE_REPAIR_R4TC)
        with self.assertRaisesRegex(ValueError,'GEN5_BASELINE'):self.predecessor(before=u.BEFORE_REPAIR_R4TC)
        with self.assertRaisesRegex(ValueError,'PREDECESSOR_NOT_PASS'):
            self.predecessor(before=u.BEFORE_REPAIR_R4TC,flags=0x20001e6a,DISARMED=False)
    def test_final_accepts_verified_C43036_and_rejects_failed_receipt(self):
        b,_,_=self.predecessor(before=u.BEFORE_TEMP);self.assertEqual(b['before_full_sha256'],u.BEFORE_TEMP)
        with self.assertRaisesRegex(ValueError,'PREDECESSOR_NOT_PASS'):self.predecessor(before=u.BEFORE_TEMP,exit_code=1)
    def test_R2_refuses_failed_or_unclosed_predecessor(self):
        for changes in ({'exit_code':1},{'Close_completed':False},{'DISARMED':False},{'full_flash_sha256':'0'*64}):
            with self.assertRaisesRegex(ValueError,'PREDECESSOR_NOT_PASS'):self.predecessor(**changes)
    def test_default_does_not_load_target(self):
        with patch.object(sys,'argv',['update']),patch('sys.stdout',io.StringIO()),patch.object(u,'InstallLink') as native:
            self.assertEqual(u.main(),0);native.assert_not_called()
    def test_consumed_old_scope_is_not_new_permission(self):
        with self.assertRaisesRegex(ValueError,'OWNER_SCOPE'):
            u.authorize({'enabled':True,'owner_approved':True,'scope':'B5_G2A_C012_OWNER_ESP_PRESENT_POWERED_EXCEPTION'},self.out)
    def test_unknown_ESP_exception_fails_before_package(self):
        a={'enabled':True,'owner_approved':True,'scope':u.SCOPE,'phase':'install','tools_sha256':u.bindings(),
           'DLL_sha256':u.ro.raw.DLL_SHA,'card_sha256':u.sha(u.CARD.read_bytes()),'expires_unix':u.time.time()+100,
           'session_timeout_s':180,'probe_sessions':1,'retries':0,'output':str(self.out),'site_record':'synthetic',
           'site_record_sha256':u.sha(b'{}')}
        with patch.object(u.recovery,'read',return_value=b'{}'),patch.object(u,'load_binding') as load:
            with self.assertRaisesRegex(ValueError,'SITE_INCOMPLETE'):u.authorize(a,self.out)
            load.assert_not_called()
    def test_halt_refused_before_native_unless_DISARMED(self):
        link=object.__new__(u.InstallLink);link.before_flags=u.OLD_FLAGS;link.flags=lambda a:b'\0\0\1\1'
        with patch.object(u.app.InstallLink,'call') as native:
            with self.assertRaisesRegex(ValueError,'BEFORE_NOT_DISARMED'):link.call('JLINKARM_Halt')
            native.assert_not_called()
    def test_arbitrary_flags_address_denied(self):
        link=object.__new__(u.InstallLink);link.flags_addresses={u.OLD_FLAGS,0x2000191a}
        with self.assertRaisesRegex(ValueError,'FLAGS_RANGE'):link.flags(0x40013804)
    def test_double_read_drift_is_not_success(self):
        link=object.__new__(u.InstallLink);link.out=self.out
        with patch.object(u.app.InstallLink,'read',side_effect=[b'\xaa'*16,b'\xaa'*15+b'\0']):
            with self.assertRaisesRegex(ValueError,'DOUBLE_READ_DRIFT'):link.read(0x1fffc000,16)
    def test_new_C_flag_read_uses_bound_address(self):
        link=object.__new__(d.CLink);link.flags_address=0x2000191a;calls=[]
        def call(name,address,size,buf,flags):calls.append(address);C.memset(buf,0,4);return 4
        link.call=call
        self.assertEqual(link.read(0x2000191a,4),bytes(4));self.assertEqual(calls,[0x2000191a])
    def test_native_short_flags_read_rejected(self):
        link=object.__new__(d.CLink);link.flags_address=0x2000191a;link.call=lambda *a:3
        with self.assertRaisesRegex(ValueError,'SHORT_READ'):link.read(0x2000191a,4)
    def test_new_flags_read_does_not_reenter_old_ABI_bridge(self):
        link=object.__new__(d.CLink);link.flags_address=0x2000191a;link.started=u.time.monotonic()
        link.sdk_calls=0;link.sdk_limit=2048;link.io=io.StringIO()
        with patch.object(d.raw.Link,'call',return_value=4) as native,patch.object(d.c.BridgeLink,'call') as old:
            self.assertEqual(link.call('JLINKARM_ReadMemEx',0x2000191a,4,None,0),4)
            self.assertEqual(native.call_count,1);old.assert_not_called()
    def test_install_then_restore_48K_leaves_config_and_protection(self):
        for phase in ('install','restore'):
            out=self.out/phase;out.mkdir()
            first,last=('before-full-private.bin','expected-full-private.bin') if phase=='install' else ('expected-full-private.bin','before-full-private.bin')
            fake=Fake(self.files[first],self.files['options-private.bin']);image=self.files[last]
            core={'registers':{'R15':int.from_bytes(image[4:8],'little'),'MSP':int.from_bytes(image[:4],'little')}}
            with patch.object(u.app.time,'sleep'),patch.object(u.app.runtime,'core_if_halted',return_value=core):
                result=u.app.execute(fake,out,{'phase':phase,'board':'C'},self.m,self.files)
            self.assertEqual(result['exit_code'],0);self.assertEqual(fake.image,image)
            self.assertEqual(len(fake.payload),49152)
    def test_ROM_entry_does_not_unlock_or_go(self):
        fake=Fake(self.files['before-full-private.bin'],self.files['options-private.bin']);fake.rom=True
        with self.assertRaisesRegex(ValueError,'ROM_STOP'):
            u.app.execute(fake,self.out,{'phase':'install','board':'C'},self.m,self.files)
        self.assertEqual(fake.counts,{})
    def test_wrong_identity_is_saved_before_rejecting_without_target_actions(self):
        fake=Fake(self.files['before-full-private.bin'],self.files['options-private.bin']);fake.wrong_uid=True
        with self.assertRaisesRegex(ValueError,'WRONG_BOARD_OR_PROTECTION'):
            u.app.execute(fake,self.out,{'phase':'install','board':'C'},self.m,self.files)
        self.assertEqual(fake.counts,{})
        observed=json.loads((self.out/'identity-before-private.json').read_text())
        expected=json.loads(self.files['identity-private.json'])
        self.assertNotEqual(observed['uid_hex'],expected['uid_hex'])
        self.assertEqual(json.loads((self.out/'identity-comparison-private.json').read_text())['different_fields'],['uid_hex'])
    def update_proof(self,**changes):
        gen5={'exit_code':0,'status':'SECTOR3_FULL_VERIFY_AND_DISARMED_BOOT_PASS','scope':'B5_GEN5_WIFI_WRITE',
              'configuration_generation':5,'Close_completed':True,'after_full_sha256':u.sha(b'old'),
              'package_manifest_sha256':'old-manifest'}
        proof=dict(status='C_EGRESS_INSTALL_FULL_VERIFY_DISARMED_PASS',exit_code=0,Close_completed=True,
                   DISARMED=True,binding_sha256='binding-sha',full_flash_sha256='new-full')
        proof.update(changes)
        oldraw=json.dumps(gen5).encode();newraw=json.dumps(proof).encode()
        a={'gen5_package':'old-package','configuration_generation':5,'gen5_package_manifest_sha256':'old-manifest',
           'gen5_install_receipt':'old-receipt','gen5_install_receipt_sha256':u.sha(oldraw),
           'C_application_binding':'binding','C_application_binding_sha256':'binding-sha',
           'C_application_install_receipt':'new-receipt','C_application_install_receipt_sha256':u.sha(newraw)}
        import b5_gen5_writer as gen5tool
        bundle={'C_full':{'sha256':'new-full'}}
        with patch.object(gen5tool,'load_package',return_value=({},{'gen5-full-private.bin':b'old'})), \
             patch.object(u,'load_binding',return_value=({'after_full_sha256':'new-full','flags_address':0x2000191a},{},{'before-full-private.bin':b'old'})), \
             patch.object(g.private,'read',side_effect=lambda path,s:oldraw if str(path)=='old-receipt' else newraw):
            return g.expected_c_full(a,bundle),bundle
    def test_G3_new_image_needs_real_install_and_uses_new_ABI(self):
        expected,bundle=self.update_proof();self.assertEqual(expected,'new-full');self.assertEqual(bundle['_C_flags_address'],0x2000191a)
    def test_G3_refuses_offline_only_or_unclosed_install(self):
        for changes in ({'exit_code':1},{'Close_completed':False},{'DISARMED':False}):
            with self.assertRaisesRegex(ValueError,'INSTALL_NOT_PASS'):self.update_proof(**changes)


if __name__=='__main__':unittest.main(verbosity=2)
