"""普通负向回归：仅用内存ROM模型检查身份/备份/先验顺序，不打开串口。"""
from pathlib import Path
import datetime
import json
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import patch
import usb_rom as rom


class FakeBoot:
    def __init__(self):
        # 明确的合成身份与Flash图样，不复用真实设备唯一信息。
        self.uid = b'HOST-S-00001'
        self.chip = 0x413
        self.capacity = 1024
        self.data = bytearray((bytes(range(256)) * (rom.SIZE // 256)))
        self.erases = []
        self.reads = 0
        self.short = False
        self.drift_second_copy = False
        self.protected = False
        self.fail_write = False
        self.short_signature = False
        self.signature_calls = []

    def get_id(self):
        return self.chip

    def get_uid(self):
        return self.uid

    def read_memory(self, address, length):
        if address == 0x1FFF7A00:
            self.signature_calls.append((address,length))
            if length != 256:
                raise RuntimeError('synthetic F4 short signature read NACK')
            block=bytearray(256)
            block[0x10:0x1C]=self.uid
            block[0x22:0x24]=self.capacity.to_bytes(2,'little')
            return block[:-1] if self.short_signature else block
        if self.protected:
            raise PermissionError('synthetic read protected')
        self.reads += 1
        result = bytes(self.data[address-rom.BASE:address-rom.BASE+length])
        if self.short:
            return result[:-1]
        if self.drift_second_copy and self.reads == rom.SIZE // 256 + 1:
            return bytes([result[0] ^ 1]) + result[1:]
        return result

    def erase_memory(self, pages=None):
        self.erases.append(pages)
        self.data[:rom.SECTOR0 if pages else rom.SIZE] = b'\xff' * (rom.SECTOR0 if pages else rom.SIZE)

    def write_memory_data(self, address, data):
        if self.fail_write:
            raise OSError('synthetic programming failure')
        self.write_memory(address, data)

    def write_memory(self, address, data):
        offset = address-rom.BASE
        self.data[offset:offset+len(data)] = data


class RomTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.folder = Path(self.tmp.name)
        self.boot = FakeBoot()

    def tearDown(self):
        self.tmp.cleanup()

    def backed(self):
        p = self.folder/'backup';p.mkdir()
        rom.backup(self.boot, p)
        return p

    def test_chip_rejected_without_erase(self):
        self.boot.chip = 0x414
        with self.assertRaises(RuntimeError): rom.identity(self.boot)
        self.assertFalse(self.boot.erases)

    def test_capacity_rejected_without_erase(self):
        self.boot.capacity = 512
        with self.assertRaises(RuntimeError): rom.identity(self.boot)
        self.assertFalse(self.boot.erases)

    def test_invalid_identity_rejected(self):
        self.boot.uid = b'\xff'*12
        with self.assertRaises(RuntimeError): rom.identity(self.boot)

    def test_F4_signature_aligned_block(self):
        result=rom.identity(self.boot)
        self.assertEqual(self.boot.signature_calls,[(0x1FFF7A00,256)])
        self.assertEqual(result['flash_bytes'],rom.SIZE)

    def test_short_signature_block_rejected(self):
        self.boot.short_signature=True
        with self.assertRaises(RuntimeError): rom.identity(self.boot)
        self.assertFalse(self.boot.erases)

    def test_short_read_is_not_backup(self):
        self.boot.short = True
        with self.assertRaises(RuntimeError): rom.backup(self.boot,self.folder)
        self.assertFalse((self.folder/'backup.json').exists())

    def test_read_protection_no_erase_or_unlock(self):
        self.boot.protected = True
        with self.assertRaises(PermissionError): rom.backup(self.boot,self.folder)
        self.assertFalse(self.boot.erases)

    def test_double_read_mismatch_no_erase(self):
        self.boot.drift_second_copy = True
        with self.assertRaises(RuntimeError): rom.backup(self.boot,self.folder)
        self.assertFalse((self.folder/'backup.json').exists())
        self.assertFalse(self.boot.erases)

    def test_backup_preserves_full_bytes(self):
        original = bytes(self.boot.data);p = self.backed()
        self.assertEqual((p/'original-a.bin').read_bytes(),original)
        self.assertEqual((p/'original-b.bin').read_bytes(),original)
        self.assertFalse(self.boot.erases)

    def test_identity_change_before_erase(self):
        p = self.backed();self.boot.uid = b'HOST-S-00002'
        with self.assertRaises(RuntimeError): rom.bound_original(self.boot,p)
        self.assertFalse(self.boot.erases)

    def test_backup_tamper_before_erase(self):
        p = self.backed();(p/'original-b.bin').write_bytes(b'bad')
        with self.assertRaises(RuntimeError): rom.bound_original(self.boot,p)
        self.assertFalse(self.boot.erases)

    def test_flash_drift_before_erase(self):
        p = self.backed();self.boot.data[-1] ^= 1
        out=self.folder/'flash';out.mkdir()
        with self.assertRaises(RuntimeError): rom.flash(self.boot,p,b'candidate',out)
        self.assertFalse(self.boot.erases)

    def test_sector0_only_full_verify(self):
        p = self.backed();original = bytes(self.boot.data)
        out=self.folder/'flash';out.mkdir()
        result=rom.flash(self.boot,p,b'candidate',out)
        self.assertEqual(result['status'],'PASS')
        self.assertEqual(self.boot.erases,[[0]])
        self.assertEqual(self.boot.data[rom.SECTOR0:],original[rom.SECTOR0:])
        self.assertEqual(len((out/'post-flash.bin').read_bytes()),rom.SIZE)

    def test_write_failure_is_not_PASS(self):
        p=self.backed();self.boot.fail_write=True
        out=self.folder/'flash';out.mkdir()
        with self.assertRaises(OSError): rom.flash(self.boot,p,b'candidate',out)
        self.assertTrue((out/'erase-started.marker').exists())

    def test_restore_full_original(self):
        p=self.backed();original=bytes(self.boot.data)
        self.boot.data[:100]=b'\x01'*100
        out=self.folder/'restore';out.mkdir()
        result=rom.restore(self.boot,p,out)
        self.assertEqual(result['status'],'PASS')
        self.assertEqual(bytes(self.boot.data),original)
        self.assertEqual((out/'restored-readback.bin').read_bytes(),original)

    def test_real_ROM_capability_query(self):
        ops=[0,2,0x11,0x31,0x44]
        queue=[bytes([len(ops)]),bytes([0x31]+ops)]
        stub=SimpleNamespace(connection=SimpleNamespace(read=lambda n: queue.pop(0)),
                             command=lambda *a: None,_wait_for_ack=lambda *a: None)
        result=rom.restore_capabilities(stub)
        self.assertTrue(result['ROM_restore_commands_verified'])
        self.assertTrue(stub.extended_erase)

    def test_missing_write_capability_stops(self):
        queue=[b'\x04',bytes([0x31,0,2,0x11,0x44])]
        stub=SimpleNamespace(connection=SimpleNamespace(read=lambda n: queue.pop(0)),
                             command=lambda *a: None,_wait_for_ack=lambda *a: None)
        with self.assertRaises(RuntimeError): rom.restore_capabilities(stub)

    def test_short_GET_stops(self):
        stub=SimpleNamespace(connection=SimpleNamespace(read=lambda n: b''),command=lambda *a: None)
        with self.assertRaises(RuntimeError): rom.restore_capabilities(stub)

    def test_manual_mode_sets_safe_lines_before_open(self):
        opened=[]
        class FakeSerial:
            def __init__(self,**kwargs):
                self.kwargs=kwargs;self.port=None;self.dtr=None;self.rts=None
            def open(self):
                opened.append((self.port,self.dtr,self.rts,self.kwargs['parity']))
        with patch('serial.Serial',FakeSerial):
            connection=rom.manual_connection('HOST_S_SYNTHETIC')
            connection.connect()
            self.assertEqual(opened,[('HOST_S_SYNTHETIC',True,False,'E')])
            before=(connection.serial_connection.dtr,connection.serial_connection.rts)
            connection.enable_reset(True);connection.enable_reset(False)
            connection.enable_boot0(True);connection.enable_boot0(False)
            self.assertEqual((connection.serial_connection.dtr,connection.serial_connection.rts),before)


if __name__ == '__main__':
    # 测试摘要和各次结果独立归档；没有创建串口对象或触发MCP。
    suite=unittest.defaultTestLoader.loadTestsFromTestCase(RomTests)
    result=unittest.TextTestRunner(verbosity=2).run(suite)
    stamp=datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    art=rom.ROOT/'artifacts/ecg-source/g2s'
    record={'scope':'ORDINARY_HOST_ROM_MODEL_NO_HARDWARE','tests':result.testsRun,
            'failures':len(result.failures),'errors':len(result.errors),'status':'PASS' if result.wasSuccessful() else 'FAIL'}
    (art/('usb-rom-host-'+stamp+'.json')).write_text(json.dumps(record,indent=2)+'\n',encoding='utf-8')
    raise SystemExit(0 if result.wasSuccessful() else 1)
