"""sector3编制的合成输入测试；不读取G1凭据、真实配置或设备。"""
import io
import json
from pathlib import Path
import struct
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/'node-b/tools'))
import b5_sector3_plan as plan


def old_record(generation=9):
    record = bytearray(336); payload = memoryview(record)[24:]
    struct.pack_into('<II', payload, 0, 0x31435747, 1700000000)
    fields = {'ssid':'SYNTHETIC_WIFI', 'wifi_password':'SYNTHETIC_WIFI_KEY', 'host':'old.example.invalid',
              'username':'SYNTHETIC_OLD', 'password':'SYNTHETIC_OLD_SECRET', 'client_id':'SYNTHETIC_OLD_ID'}
    for name, offset, width in plan.FIELDS:
        data=fields[name].encode();payload[offset:offset+len(data)]=data
    struct.pack_into('<IHHIIII', record, 0, 0x32433348,1,24,312,generation,0,0x54494D43)
    struct.pack_into('<I',record,16,plan.record_crc(record));return bytes(record)


class Tests(unittest.TestCase):
    def setUp(self):
        self.mqtt={'gateway_id':'GW-B5-001','username':'b5-gateway','client_id':'b5-c-isolated',
                   'host':'b5.example.invalid','password':'SYNTHETIC_ONLY_NOT_A_PASSWORD','port':8883}
        self.original=bytearray(b'\xa5'*1048576)
        self.original[plan.START:plan.START+336]=old_record()
        self.original=bytes(self.original)
        self.installed=b'\x5a'*plan.APP_BYTES+self.original[plan.APP_BYTES:]
    def make(self, **changes):
        with patch.object(plan,'CURRENT_FULL_SHA',plan.sha(self.original)),patch.object(plan,'APP_SHA',plan.sha(self.installed[:plan.APP_BYTES])):
            return plan.build_plan(changes.get('original',self.original),changes.get('installed',self.installed),changes.get('mqtt',self.mqtt),changes.get('minimum_epoch'))

    def test_new_record_full_rebuild_reuses_wifi_only_in_memory(self):
        record,pre,old,new=plan.make_record(old_record(),self.mqtt)
        generation,epoch,fields=plan.parse_record(record)
        self.assertEqual((old,new,generation),(9,10,10));self.assertEqual(epoch,1700000000)
        self.assertEqual(fields['ssid'],b'SYNTHETIC_WIFI');self.assertEqual(fields['wifi_password'],b'SYNTHETIC_WIFI_KEY')
        self.assertEqual(fields['host'],b'b5.example.invalid');self.assertEqual(fields['username'],b'b5-gateway')
        self.assertEqual(pre[:20]+pre[24:],record[:20]+record[24:]);self.assertEqual(pre[20:24],b'\xff'*4)
        self.assertEqual(len(record),336)
        self.assertEqual(plan.parse_record(bytearray(record)),plan.parse_record(record))

    def test_uncommitted_partial_and_bad_CRC_rejected(self):
        record,pre,_,_=plan.make_record(old_record(),self.mqtt)
        for broken in [pre,record[:200],record[:300]+bytes(36)]:
            with self.assertRaises(ValueError):plan.parse_record(broken)
        broken=bytearray(record);broken[100]^=1
        with self.assertRaisesRegex(ValueError,'CRC'):plan.parse_record(broken)

    def test_invalid_old_record_not_used_as_credential_source(self):
        broken=bytearray(old_record());broken[16]^=1
        with self.assertRaisesRegex(ValueError,'CRC'):plan.make_record(bytes(broken),self.mqtt)

    def test_wrong_identity_and_TLS_refused(self):
        for key,value in [('gateway_id','GW-C-001'),('username','SYNTHETIC_OTHER'),('client_id','SYNTHETIC_OTHER'),('port',8884),('tls_insecure',True),('validate_certificate',False)]:
            with self.subTest(key=key),self.assertRaises(ValueError):plan.make_record(old_record(),{**self.mqtt,key:value})

    def test_generation_zero_and_overflow_refused(self):
        for generation in (0,0xffffffff):
            with self.assertRaises(ValueError):plan.make_record(old_record(generation),self.mqtt)

    def test_epoch_never_rolls_back_or_overflows(self):
        for epoch in (1699999999,0x100000000,True):
            with self.assertRaisesRegex(ValueError,'MINIMUM_EPOCH'):plan.make_record(old_record(),self.mqtt,epoch)
        self.assertEqual(plan.parse_record(plan.make_record(old_record(),self.mqtt,1700000001)[0])[1],1700000001)

    def test_field_lengths_are_bytes_and_AT_characters_rejected(self):
        for value in ('x'*65,'bad\nvalue','bad"value','bad\\value','bad\0value','汉'*22,''):
            with self.subTest(value=repr(value)),self.assertRaises(ValueError):plan.make_record(old_record(),{**self.mqtt,'password':value})
        self.assertEqual(len(plan.make_record(old_record(),{**self.mqtt,'password':'x'*64})[0]),336)

    def test_empty_wifi_password_allowed_but_no_other_empty_required_field(self):
        old=bytearray(old_record());old[24+41:24+106]=bytes(65);struct.pack_into('<I',old,16,plan.record_crc(old))
        record=plan.make_record(bytes(old),self.mqtt)[0];self.assertEqual(plan.parse_record(record)[2]['wifi_password'],b'')
        with self.assertRaises(ValueError):plan.make_record(bytes(old),{**self.mqtt,'host':''})

    def test_original_field_must_have_bounded_terminator(self):
        old=bytearray(old_record());old[24+8:24+41]=b'x'*33;struct.pack_into('<I',old,16,plan.record_crc(old))
        with self.assertRaisesRegex(ValueError,'TERMINATED'):plan.make_record(bytes(old),self.mqtt)

    def test_sector_tail_and_all_protected_bytes_preserved(self):
        manifest,files=self.make();final=files['expected-full-B5-new-config-private.bin']
        self.assertEqual(final[:plan.START],self.installed[:plan.START]);self.assertEqual(final[plan.END:],self.original[plan.END:])
        self.assertEqual(files['sector3-committed-private.bin'][336:],self.original[plan.START+336:plan.END])
        self.assertEqual(manifest['preserved_tail_bytes'],16048);self.assertFalse(manifest['hardware_execution_enabled'])
        self.assertEqual(manifest['physical_writer'],'NOT_IMPLEMENTED_NOT_AUTHORIZED')

    def test_restore_orders_have_distinct_intermediates_and_same_complete_original(self):
        manifest,files=self.make();app=files['expected-full-R-APP-only-private.bin'];cfg=files['expected-full-R-CFG-only-private.bin']
        self.assertEqual(app[:plan.START],self.original[:plan.START]);self.assertNotEqual(app,self.original)
        self.assertEqual(cfg,self.installed);self.assertNotEqual(cfg,self.original)
        self.assertEqual(app[:plan.START]+self.original[plan.START:plan.END]+app[plan.END:],self.original)
        self.assertEqual(self.original[:plan.START]+cfg[plan.START:],self.original)
        self.assertTrue(manifest['both_restore_orders_equal_original'])

    def test_original_app_tail_and_full_size_drift_refused(self):
        for key,blob in [('original',self.original[:-1]),('original',bytes(1048576)),('installed',self.installed[:-1]+b'\x00'),('installed',bytes(1048576))]:
            with self.subTest(key=key),self.assertRaises(ValueError):self.make(**{key:blob})

    def test_public_manifest_contains_no_private_field_values(self):
        manifest,_=self.make();text=json.dumps(manifest)
        for value in ['b5.example.invalid','SYNTHETIC_ONLY_NOT_A_PASSWORD','SYNTHETIC_WIFI_KEY']:
            self.assertNotIn(value,text)

    def test_CLI_rejects_non_EFS_paths_without_echoing_config_or_loading_DLL(self):
        with tempfile.TemporaryDirectory(dir=ROOT/'node-b/build') as folder:
            base=Path(folder);(base/'original').write_bytes(self.original)
            args=['b5_sector3_plan.py','--original-full',str(base/'original'),'--app-installed-full',str(base/'installed'),
                  '--mqtt-private-json',str(base/'mqtt'),'--out',str(base/'out')]
            output=io.StringIO()
            with patch.object(sys,'argv',args),patch('sys.stdout',output):self.assertEqual(plan.main(),1)
            self.assertNotIn(str(base),output.getvalue());self.assertFalse((base/'out').exists())


if __name__=='__main__':unittest.main(verbosity=2)
