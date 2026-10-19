"""仅离线验证下载边界/保护策略，绝不导入串口或连接真实设备。"""
import importlib.util
from pathlib import Path
import unittest

spec=importlib.util.spec_from_file_location('flash_c',Path(__file__).resolve().parents[1]/'bench/flash_c.py')
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)

def image(size=24000):
    result=bytearray(size);result[:4]=(0x20020000).to_bytes(4,'little');result[4:8]=(0x08000101).to_bytes(4,'little')
    result[256:256+len(b'CAN_ONLY_BENCH OFFLINE_NO_CONFIG')]=b'CAN_ONLY_BENCH OFFLINE_NO_CONFIG'
    return bytes(result)

class Device:
    def __init__(self):self.extended_erase=True;self.erased=None;self.written=None;self.corrupt=False;self.rdp=0xAA
    def read_memory_data(self,address,length):
        if address==0x1FFFC000:
            assert length==16
            return bytes([0xed,self.rdp])+b'\xff'*14
        if address==0x40023C14:raise AssertionError('UART ROM must not depend on peripheral read')
        if address==m.START:return self.written if self.written is not None else bytes(length)
        return bytes([1 if self.corrupt and self.written else 0xff])*length
    def extended_erase_memory(self,pages):
        assert pages and all(0<=p<=3 for p in pages);self.erased=pages
    def write_memory_data(self,address,data):
        assert address==m.START and address+len(data)<=m.LIMIT;self.written=bytes(data)

class Tests(unittest.TestCase):
    def test_f4_uses_block_reader_not_otp_short_reads(self):
        class F4:
            def get_id(self):return 0x413
            def get_flash_size_and_uid(self):return 1024,b'HOST_SYNTHETIC'
            def format_uid(self,uid):return 'HOST_FAKE_ID'
            def get_flash_size(self):raise AssertionError('OTP short read forbidden')
            def get_uid(self):raise AssertionError('OTP short read forbidden')
        m.verify_f4_identity(F4(),{'EXPECTED_CHIP_ID':'0x413','EXPECTED_UID':'HOST_FAKE_ID'})
    def test_f4_block_reader_still_rejects_wrong_size(self):
        class F4:
            def get_id(self):return 0x413
            def get_flash_size_and_uid(self):return 512,b'HOST_SYNTHETIC'
        with self.assertRaisesRegex(m.GateError,'C_CHIP_SIZE_MISMATCH'):
            m.verify_f4_identity(F4(),{'EXPECTED_CHIP_ID':'0x413','EXPECTED_UID':'HOST_FAKE_ID'})
    def test_f4_block_reader_still_rejects_wrong_identity(self):
        class F4:
            def get_id(self):return 0x413
            def get_flash_size_and_uid(self):return 1024,b'HOST_SYNTHETIC'
            def format_uid(self,uid):return 'HOST_OTHER_ID'
        with self.assertRaisesRegex(m.GateError,'C_UID_MISMATCH'):
            m.verify_f4_identity(F4(),{'EXPECTED_CHIP_ID':'0x413','EXPECTED_UID':'HOST_FAKE_ID'})
    def test_size_and_vectors(self):
        for data in (b'',bytes(65537),bytes(100)):
            with self.assertRaises(m.GateError):m.image_plan(data,m.digest(data))
        data=image(65536);self.assertEqual(m.image_plan(data,m.digest(data))['sectors'],[0,1,2,3])
    def test_affected_sectors_only_and_hashes(self):
        data=image();plan=m.image_plan(data,m.digest(data));device=Device()
        result=m.program_verified(device,data,plan)
        self.assertEqual(device.erased,[0,1]);self.assertEqual(device.written,data)
        self.assertTrue(result['protected_unchanged'])
    def test_read_protection_blocks_before_erase(self):
        data=image();device=Device();device.rdp=0x55
        with self.assertRaises(m.GateError):m.program_verified(device,data,m.image_plan(data,m.digest(data)))
        self.assertIsNone(device.erased)
    def test_protected_change_fails(self):
        data=image();device=Device();device.corrupt=True
        with self.assertRaisesRegex(m.GateError,'PROTECTED_DATA_CHANGED_STOP'):
            m.program_verified(device,data,m.image_plan(data,m.digest(data)))
    def test_wrong_sha_blocks(self):
        with self.assertRaises(m.GateError):m.image_plan(image(),'0'*64)
    def test_empty_plan_cannot_mass_erase(self):
        data=image();plan=m.image_plan(data,m.digest(data));plan['sectors']=[];device=Device()
        with self.assertRaises(m.GateError):m.program_verified(device,data,plan)
        self.assertIsNone(device.erased)

if __name__=='__main__':unittest.main()
