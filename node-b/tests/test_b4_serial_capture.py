"""唯一START和串口开启顺序负例；使用内存替身，不访问COM或调试器。"""
import json
import itertools
import time
from types import SimpleNamespace
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch,Mock
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
    def test_running_attach_waits_for_progress_and_does_not_fabricate_BOOT(self):
        # 开口晚于复位：先检查完整的五类诊断、两秒推进，再允许唯一START。
        with tempfile.TemporaryDirectory() as t:
            p=Port();p.chunks=[packet(5,i,0,b'\0'*8,seq=i+1) for i in range(5)]
            p.chunks += [packet(5,0,2000,b'\0'*8,seq=6),packet(9,0,2001,b'\0'*8,seq=7),
                         # 对应真实排队负例：模型生成时间早于前面出队的TX确认，不是MCU时基重启。
                         packet(3,0,2004,b'\1\2',seq=8),packet(8,9,2000,b'\0'*8,seq=9),
                         packet(6,0,182001,(180000).to_bytes(4,'little')+b'\0'*4,seq=10)]
            with patch.object(c,'ready',return_value=True):
                r=c.capture(p,Path(t),Path(t)/'ready',clock=lambda:1,
                            install_check=lambda:True,flash_alias_verified=True,running_attach=True)
            self.assertEqual(p.writes,[b'B4START\n'])
            self.assertNotIn('BOOT_NOT_CAPTURED',r['failures'])
            self.assertFalse(json.loads((Path(t)/'C-RUNNING-OBSERVED.json').read_text())['BOOT_captured'])
    def test_running_attach_no_proof_or_sequence_restart_stops(self):
        # 缺独立安装证明、附着后新BOOT及序号/时基重启均不能作为可重试的正常数据。
        for chunks,proof,reason in (([packet(5,0,0,b'\0'*8)],False,'INSTALL_PROOF'),
              ([packet(7,4,0,b'B4C4'+b'\0'*4)],True,'REBOOT'),
              ([packet(5,0,0,b'\0'*8),packet(5,1,1,b'\0'*8,seq=3)],True,'SEQUENCE_GAP'),
              ([packet(5,0,3,b'\0'*8),packet(5,1,1,b'\0'*8,seq=2)],True,'TICK_RESTART')):
            with self.subTest(reason=reason),tempfile.TemporaryDirectory() as t:
                p=Port();p.chunks=chunks
                with self.assertRaisesRegex(ValueError,reason):
                    c.capture(p,Path(t),Path(t)/'ready',clock=lambda:1,
                              install_check=lambda:True,flash_alias_verified=proof,running_attach=True)
                self.assertFalse(p.writes)
    def test_incomplete_install_never_opens_serial(self):
        # 安装未完成时只能返回负例；不允许先打开串口再等待安装器的计划复位。
        serial=SimpleNamespace(Serial=Mock())
        ports=SimpleNamespace(comports=lambda:[])
        with tempfile.TemporaryDirectory() as t:
            out=Path(t)/'capture';args=SimpleNamespace(out=out)
            with patch.dict(sys.modules,{'serial':serial,'serial.tools':SimpleNamespace(list_ports=ports)}), \
                 patch.object(c,'port_matches',return_value=True), \
                 patch.object(c,'installed',return_value=False), \
                 patch.object(c.pkg,'protected',side_effect=lambda p,synthetic:p):
                code=c.worker(args,{'C_candidate_sha256':'ab'*32})
            self.assertEqual(code,1);serial.Serial.assert_not_called()
            self.assertEqual(json.loads((out/'receipt-private.json').read_text())['reason'],
                             'CAPTURE_INSTALL_NOT_COMPLETE_BEFORE_OPEN')
    def test_zero_vector_serial_gate_matches_flash_alias_policy(self):
        # 必须在两个裁定入口使用同一判据；ROM或Fault不能随合法零别名一起被放宽。
        for proof,vtor,fault,accepted in ((False,0,0,False),(True,0,0,True),
                                          (True,0x1fff0000,0,False),(True,0,1,False)):
            with self.subTest(proof=proof,vtor=vtor,fault=fault),tempfile.TemporaryDirectory() as t:
                p=Port();p.chunks=[packet(7,4,0,b'B4C4'+b'\0'*4),
                    packet(5,4,1,vtor.to_bytes(4,'little')+fault.to_bytes(4,'little'),seq=2),
                    packet(9,0,2,b'\0'*8,seq=3),
                    packet(6,0,180002,(180000).to_bytes(4,'little')+b'\0'*4,seq=4)]
                with patch.object(c,'ready',return_value=True):
                    if accepted:
                        r=c.capture(p,Path(t),Path(t)/'ready',clock=lambda:1,
                                    install_check=lambda:True,flash_alias_verified=proof)
                        self.assertNotIn('C_VECTOR_OR_FAULT',r['failures'])
                    else:
                        with self.assertRaisesRegex(ValueError,'VECTOR_FAULT'):
                            c.capture(p,Path(t),Path(t)/'ready',clock=lambda:1,
                                      install_check=lambda:True,flash_alias_verified=proof)
    def test_explicit_C_port_binding_and_driver_match(self):
        a={'enabled':True,'owner_approved':True,'scope':c.SCOPE,'tools_sha256':c.bindings(),
           'port':'COM17','baud':230400,'C_port_owner_confirmed':True,'USB_VID':0x1a86,
           'USB_PID':0x7523,'ESP_isolated':True,'A_disconnected':True,
           'expires_unix':time.time()+30,'C_candidate_sha256':'ab'*32}
        c.validate(a)
        self.assertTrue(c.port_matches([SimpleNamespace(device='COM17',vid=0x1a86,pid=0x7523)],a))
        self.assertFalse(c.port_matches([SimpleNamespace(device='COM15',vid=0x1a86,pid=0x7523)],a))
        a['C_port_owner_confirmed']=False
        with self.assertRaisesRegex(ValueError,'NOT_CONFIRMED'):c.validate(a)
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
