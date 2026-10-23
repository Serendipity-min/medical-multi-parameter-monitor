"""唯一START和串口开启顺序负例；使用内存替身，不访问COM或调试器。"""
import json
import itertools
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'node-b/tools'))
import b4_serial_capture as c
from test_b4_capture_decode import packet

class Port:
    def __init__(self,**kwargs):self.events=[('construct',kwargs)];self.writes=[]
    def __setattr__(self,key,value):
        if key in ('dtr','rts','port'):self.events.append((key,value))
        object.__setattr__(self,key,value)
    def open(self):self.events.append(('open',))
    def flush(self):pass
    def read(self,n):return self.chunks.pop(0) if self.chunks else b''
    def write(self,data):self.writes.append(data);return len(data)

class Tests(unittest.TestCase):
    def test_default_disabled(self):
        with self.assertRaisesRegex(ValueError,'OWNER_AUTH'):c.validate({})
    def test_DTR_RTS_before_open(self):
        p=c.open_port(Port,'COM15')
        self.assertEqual([x[0] for x in p.events],['construct','dtr','rts','port','open'])
        self.assertIsNone(p.events[0][1]['port']);self.assertFalse(p.dtr);self.assertFalse(p.rts)
    def test_only_fresh_matching_ready(self):
        with tempfile.TemporaryDirectory() as t:
            path=Path(t)/'READY.json'
            self.assertFalse(c.ready(path,10))
            path.write_text(json.dumps({'B4_image_sha256':c.monitor.IMAGE_SHA,'host_monotonic':9}))
            self.assertTrue(c.ready(path,10));self.assertFalse(c.ready(path,13))
            self.assertFalse(c.ready(path,8))
    def test_one_exact_START_no_retry(self):
        with tempfile.TemporaryDirectory() as t:
            out=Path(t);p=Port();p.chunks=[packet(7,4,0,b'B4C4'+b'\0'*4),
                packet(9,0,1,b'\0'*8,seq=2),packet(6,0,180001,(180000).to_bytes(4,'little')+b'\0'*4,seq=3)]
            with patch.object(c,'ready',return_value=True):
                r=c.capture(p,out,out/'ready',clock=lambda:1,install_check=lambda:True)
            self.assertEqual(p.writes,[b'B4START\n']);self.assertEqual(r['start_commands_attempted'],1)
            self.assertEqual(r['status'],'NOT_PASS') # 没有CAN数据，不能把串口流程成功冒充收发通过。
    def test_short_START_write_stops_without_retry(self):
        with tempfile.TemporaryDirectory() as t:
            p=Port();p.chunks=[packet(7,4,0,b'B4C4'+b'\0'*4)]
            def short(data):p.writes.append(data);return 3
            p.write=short
            with patch.object(c,'ready',return_value=True), self.assertRaisesRegex(ValueError,'PARTIAL_WRITE'):
                c.capture(p,Path(t),Path(t)/'ready',clock=lambda:1,install_check=lambda:True)
            self.assertEqual(len(p.writes),1)
    def test_reboot_stops(self):
        with tempfile.TemporaryDirectory() as t:
            p=Port();p.chunks=[packet(7,4,0,b'B4C4'+b'\0'*4)+packet(7,4,0,b'B4C4'+b'\0'*4,seq=2)]
            with self.assertRaisesRegex(ValueError,'REBOOT'):c.capture(p,Path(t),Path(t)/'ready',clock=lambda:1)
    def test_boot_timeout_no_command(self):
        with tempfile.TemporaryDirectory() as t:
            p=Port();p.chunks=[];times=iter([0,181])
            with self.assertRaisesRegex(ValueError,'BOOT_TIMEOUT'):
                c.capture(p,Path(t),Path(t)/'ready',clock=lambda:next(times))
            self.assertFalse(p.writes)
    def test_corrupt_packet_after_BOOT_in_same_read_is_counted(self):
        with tempfile.TemporaryDirectory() as t:
            p=Port();bad=bytearray(packet(5,1,0,b'\0'*8,seq=2));bad[20]^=1
            p.chunks=[packet(7,4,0,b'B4C4'+b'\0'*4)+bytes(bad),
                packet(9,0,1,b'\0'*8,seq=3),packet(6,0,180001,(180000).to_bytes(4,'little')+b'\0'*4,seq=4)]
            with patch.object(c,'ready',return_value=True):
                r=c.capture(p,Path(t),Path(t)/'ready',clock=lambda:1,install_check=lambda:True)
            self.assertEqual(r['CRC_errors'],1);self.assertIn('SERIAL_CRC_ERROR',r['failures'])
    def test_missing_install_receipt_never_start(self):
        self.assertFalse(c.installed({}))
        with tempfile.TemporaryDirectory() as t:
            p=Port();p.chunks=[packet(7,4,0,b'B4C4'+b'\0'*4)]
            # 单调推进的替身时钟不依赖实现内部查询时钟的次数。
            times=itertools.count(0,60)
            with patch.object(c,'ready',return_value=True),self.assertRaisesRegex(ValueError,'TIMEOUT'):
                c.capture(p,Path(t),Path(t)/'ready',clock=lambda:next(times))
            self.assertFalse(p.writes)
if __name__=='__main__':unittest.main(verbosity=2)
