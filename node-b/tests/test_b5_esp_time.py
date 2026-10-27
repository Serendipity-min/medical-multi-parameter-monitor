"""仅验证固定时间查询、原码保留和拒绝路径；不访问设备。"""
import contextlib
import io
import json
from pathlib import Path
import struct
import sys
import tempfile
import types
import unittest
from unittest.mock import Mock,patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import b5_esp_time as t


class Tests(unittest.TestCase):
    def test_default_disabled_without_device(self):
        with patch.object(sys,'argv',['time']),patch.object(t,'worker') as worker,contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(t.main(),0);worker.assert_not_called()
    def test_disabled_or_wrong_scope_denied(self):
        with self.assertRaisesRegex(ValueError,'OWNER_SCOPE'):t.validate({'enabled':False})
    def test_exact_query_order_and_34_bytes(self):
        x=t.q.ByteGrant(t.COMMANDS)
        self.assertEqual(t.MAX_BYTES,34)
        with self.assertRaises(ValueError):x.begin(t.COMMANDS[1])
        for command in t.COMMANDS:
            x.begin(command)
            for b in command:x.check(t.q.DR,b)
        self.assertEqual(bytes(x.history),b'AT+CIPSNTPCFG?\r\nAT+SYSTIMESTAMP?\r\n')
        with self.assertRaises(ValueError):x.begin(t.COMMANDS[0])
    def test_setters_start_reset_and_wifi_denied(self):
        for command in (b'AT+CIPSNTPCFG=1,0\r\n',b'AT+SYSTIMESTAMP=1793080000\r\n',b'AT+RST\r\n',b'B5START\n',b'AT+CWJAP?\r\n'):
            with self.assertRaises(ValueError):t.q.ByteGrant(t.COMMANDS).begin(command)
    def test_native_all_34_bytes_and_35th_denied(self):
        x=object.__new__(t.TimeLink);x.byte_grant=t.q.ByteGrant(t.COMMANDS)
        x.sdk_calls=0;x.sdk_limit=6000;x.query_before_verified=True;x.native_UART_writes=0
        x.dap_select=0;x.dap_csw=2;x.dap_tar=t.q.DR;x.io=io.StringIO();x.events=io.StringIO();x.gate=lambda:None
        native=Mock(return_value=0);x.dll=types.SimpleNamespace(JLINKARM_CORESIGHT_WriteAPDPReg=native)
        for command in t.COMMANDS:
            x.byte_grant.begin(command)
            for value in command:
                x.byte_grant.check(t.q.DR,value);x.raw_target_grant=(t.q.DR,value)
                x.call('JLINKARM_CORESIGHT_WriteAPDPReg',3,1,value)
        self.assertEqual(native.call_count,34);self.assertEqual(x.native_UART_writes,34)
        with self.assertRaises(ValueError):x.call('JLINKARM_CORESIGHT_WriteAPDPReg',3,1,10)
        self.assertEqual(native.call_count,34)
    def test_epoch_at_minimum_valid_but_no_historical_claim(self):
        r=t.interpret(b'\r\n+CIPSNTPCFG:1,0,"synthetic.invalid"\r\n\r\nOK\r\n',
                      b'\r\n+SYSTIMESTAMP:1792977536\r\n\r\nOK\r\n',1792977536)
        self.assertTrue(r['SNTP_enabled_observed']);self.assertTrue(r['timestamp_meets_C_gate_now'])
        self.assertNotIn('synthetic.invalid',json.dumps(r));self.assertIn('NOT_PROVEN',r['prior_G3_TIME_root_cause'])
    def test_disabled_sntp_zero_and_old_epoch_fail_gate(self):
        for value in (0,1792977535):
            r=t.interpret(b'\r\n+CIPSNTPCFG:0,0\r\n\r\nOK\r\n',
                          ('\r\n+SYSTIMESTAMP:'+str(value)+'\r\n\r\nOK\r\n').encode(),1792977536)
            self.assertFalse(r['SNTP_enabled_observed']);self.assertFalse(r['timestamp_meets_C_gate_now'])
    def test_ERROR_is_evidence_not_an_invented_zero(self):
        r=t.interpret(b'\r\nERROR\r\n',b'\r\nERROR\r\n',1792977536)
        self.assertIsNone(r['SYSTIMESTAMP_epoch_observed']);self.assertIsNone(r['SNTP_enabled_observed'])
        self.assertTrue(r['timestamp_query_ERROR']);self.assertFalse(r['timestamp_meets_C_gate_now'])
    def test_disabled_config_without_timezone_is_parsed_from_raw_reply(self):
        r=t.interpret(b'AT+CIPSNTPCFG?\r\r\n+CIPSNTPCFG:0\r\n\r\nOK\r\n',
                      b'AT+SYSTIMESTAMP?\r\r\n+SYSTIMESTAMP:404\r\n\r\nOK\r\n',1792977536)
        self.assertIs(r['SNTP_enabled_observed'],False);self.assertIsNone(r['SNTP_timezone_observed'])
        self.assertEqual(r['SYSTIMESTAMP_epoch_observed'],404);self.assertFalse(r['timestamp_meets_C_gate_now'])
    def test_capture_preserves_ERROR_and_next_fixed_query_is_possible(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);clock=[0.0];reply=b'\r\nERROR\r\n'
            class Link:
                def __init__(self):self.byte_grant=t.q.ByteGrant(t.COMMANDS);self.sent=0;self.base=0
                def read(self,address,size):
                    if address==t.q.STATS:return struct.pack('<5I',0,0,0,0,self.base+(len(reply) if self.sent==len(self.byte_grant.command) and self.sent else 0))
                    return reply*2+b'\0'*(t.q.CAPACITY-len(reply)*2)
                def u32(self,address):return 1<<7
            link=Link()
            def write(address,value):link.byte_grant.check(address,value);link.sent+=1
            def save(path,value):Path(path).write_text(json.dumps(value))
            with patch.object(t.q.g,'save',side_effect=save),patch.object(t.q.g,'write_private',side_effect=lambda p,b:Path(p).write_bytes(b)), \
                 patch.object(t.q.time,'monotonic',side_effect=lambda:clock[0]),patch.object(t.q.time,'sleep',side_effect=lambda n:clock.__setitem__(0,clock[0]+n)):
                for i,command in enumerate(t.COMMANDS):
                    link.sent=0;link.base=i*len(reply)
                    actual=t.q.capture(link,types.SimpleNamespace(write32=write),command,root,i,accept_error=True)
                    self.assertEqual(actual,reply);self.assertEqual((root/f'query-{i}-response-private.bin').read_bytes(),reply)
            self.assertEqual(len(link.byte_grant.history),34)
    def test_ROM_entry_has_one_snapshot_zero_UART_writes_and_no_recovery(self):
        with tempfile.TemporaryDirectory() as temp:
            link=types.SimpleNamespace(open=lambda:None,u32=lambda _:0,query_before_verified=False,
                byte_grant=types.SimpleNamespace(history=[]),native_UART_writes=0,sdk_calls=0,close_resume_enabled=False,close=Mock())
            with patch.object(t,'TimeLink',return_value=link),patch.object(t.q.site.ro.raw,'identity',return_value={}), \
                 patch.object(t.g,'load',return_value={}),patch.object(t.g,'save',side_effect=lambda p,v:Path(p).write_text(json.dumps(v))), \
                 patch.object(t.g.private,'protected'),patch.object(t.q.site.ro.old,'snapshot',return_value={}) as snapshot, \
                 patch.object(t.q.site.ro.old,'check_running',side_effect=ValueError('C_RO_ROM_STOP')),contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(t.worker({}, {'C_identity':{'path':'SYNTHETIC'}},Path(temp)/'out'),1)
            self.assertEqual(snapshot.call_count,1);link.close.assert_called_once()
    def test_query_time_limit_and_address_guards_are_inherited(self):
        x=object.__new__(t.TimeLink)
        for name in ('JLINKARM_Halt','JLINKARM_Reset','JLINKARM_Go','JLINKARM_WriteMem'):
            with self.assertRaisesRegex(ValueError,'API_DENIED'):x._call_native(name)
        grant=t.q.ByteGrant(t.COMMANDS);grant.begin(t.COMMANDS[0])
        for address in (t.q.CR,0x0800c000,t.q.UART+8,0x2001170c):
            with self.assertRaises(ValueError):grant.check(address,65)


if __name__=='__main__':unittest.main()
