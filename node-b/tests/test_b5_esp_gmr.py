"""新增UART固定查询的定向离线验证，不加载DLL或访问设备。"""
import contextlib
import io
import json
from pathlib import Path
import sys
import tempfile
import types
import unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import b5_esp_gmr as q


class Tests(unittest.TestCase):
    def test_default_plan_never_loads_native_or_executes(self):
        with patch.object(sys,'argv',['query']),patch.object(q,'worker') as worker,contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(q.main(),0);worker.assert_not_called()
    def test_disabled_or_wrong_scope_stops_first(self):
        with self.assertRaisesRegex(ValueError,'OWNER_SCOPE'):q.validate({'enabled':False})
    def test_old_and_new_version_strings_parse_without_inferring_module_age(self):
        for v in ('1.1.0.0','2.3.0.0-dev'):
            r=q.extract_version(('AT version:'+v+'(SYNTHETIC)\r\nSDK version:v3.4-test\r\n\r\nOK\r\n').encode())
            self.assertEqual(r['AT_version'],v);self.assertIn('NOT_ESTABLISHED',r['physical_module_age_or_flash_capacity'])
    def test_missing_GMR_or_OK_never_reports_version_PASS(self):
        for b in (b'\r\nOK\r\n',b'AT version:2.3.0.0\r\nERROR\r\n',b''):
            with self.assertRaisesRegex(ValueError,'VERSION_OR_OK'):q.extract_version(b)
    def test_only_exact_AT_then_GMR_bytes_are_granted(self):
        x=q.ByteGrant()
        with self.assertRaises(ValueError):x.begin(b'AT+RST\r\n')
        for command in q.COMMANDS:
            x.begin(command)
            for value in command:x.check(q.DR,value)
        self.assertEqual(bytes(x.history),b'AT\r\nAT+GMR\r\n');self.assertEqual(len(x.history),12)
        with self.assertRaises(ValueError):x.begin(q.COMMANDS[0])
    def test_RAM_Flash_control_GPIO_and_wrong_UART_byte_denied(self):
        x=q.ByteGrant();x.begin(q.COMMANDS[0])
        for a,v in ((0x08000000,65),(q.CR,65),(q.UART+8,65),(0x40020400,65),(q.DR,66)):
            with self.assertRaisesRegex(ValueError,'BYTE_WRITE_DENIED'):x.check(a,v)
        self.assertEqual(x.history,[])
    def test_HALT_reset_go_WriteMem_and_reconfigure_API_denied_before_DLL(self):
        x=object.__new__(q.QueryLink)
        for name in ('JLINKARM_Halt','JLINKARM_Go','JLINKARM_Reset','JLINKARM_WriteMem','JLINKARM_WriteReg','JLINKARM_CORESIGHT_Configure'):
            with self.assertRaisesRegex(ValueError,'API_DENIED'):x._call_native(name)
    def test_115200_register_baud_uses_actual_APB_divider(self):
        self.assertAlmostEqual(q.baud_from_registers(4,69),115942.02898550725)
        self.assertAlmostEqual(q.baud_from_registers(4|(4<<10),35),114285.71428571429)
        with self.assertRaises(ValueError):q.baud_from_registers(0,69)
    def native_link_stub(self,address):
        link=object.__new__(q.QueryLink);link.sdk_calls=0;link.sdk_limit=6000;link.query_before_verified=True
        link.byte_grant=q.ByteGrant();link.byte_grant.begin(q.COMMANDS[0]);link.byte_grant.check(q.DR,65)
        link.native_UART_writes=0;link.dap_select=0;link.dap_csw=2;link.dap_tar=address
        link.raw_target_grant=(address,65);link.raw_failed=False;link.active_api=None
        link.io=io.StringIO();link.events=io.StringIO();link.gate=lambda:None
        return link
    def test_native_DAP_guard_denies_Flash_even_with_forged_parent_grant(self):
        link=self.native_link_stub(q.CR)
        with self.assertRaisesRegex(ValueError,'TARGET_WRITE_DENIED'):
            link.call('JLINKARM_CORESIGHT_WriteAPDPReg',3,1,65)
        self.assertEqual(link.sdk_calls,0)
    def test_native_negative_write_is_preserved_and_latches_no_retry(self):
        link=self.native_link_stub(q.DR);calls=[]
        link.dll=types.SimpleNamespace(JLINKARM_CORESIGHT_WriteAPDPReg=lambda *a:(calls.append(a) or -1))
        bus=q.site.config.NativeBus(link)
        with self.assertRaisesRegex(ValueError,'WRITE_NATIVE_ERROR'):bus.write(3,True,65)
        with self.assertRaisesRegex(ValueError,'RAW_STOP_LATCHED'):bus.write(3,True,65)
        self.assertEqual(calls,[(3,1,65)])
        self.assertEqual(json.loads(link.io.getvalue())['native_return_int'],-1)
    def test_native_read_error_preserved_and_prevents_any_second_call(self):
        link=self.native_link_stub(q.DR);calls=[];link.memory_counts={}
        link.dll=types.SimpleNamespace(JLINKARM_ReadMemEx=lambda *a:(calls.append(a) or -1))
        with self.assertRaisesRegex(ValueError,'NATIVE_READ_ERROR'):link.read(q.UART,4)
        with self.assertRaisesRegex(ValueError,'READ_STOP_LATCHED'):link.read(q.UART,4)
        self.assertEqual(len(calls),1);self.assertFalse(link.verified_running_flash)
        self.assertEqual(json.loads(link.io.getvalue())['native_return_int'],-1)
    def test_ring_wrap_preserves_exact_reply_bytes(self):
        b=bytearray(q.CAPACITY);b[-3:]=b'ABC';b[:2]=b'DE'
        self.assertEqual(q.circular_delta(q.CAPACITY-3,2,b),b'ABCDE')
        self.assertEqual(q.circular_delta(3,3,b),b'')
    def test_capture_uses_running_RX_ring_and_fails_on_ERROR(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);clock=[0.0]
            class Link:
                def __init__(self,response):self.byte_grant=q.ByteGrant();self.reply=response;self.sent=0
                def read(self,address,size):
                    if address==q.STATS:return q.struct.pack('<5I',0,0,0,0,len(self.reply) if self.sent==4 else 0)
                    return self.reply+b'\x00'*(q.CAPACITY-len(self.reply))
                def u32(self,address):return 1<<7
            def save(p,v):Path(p).write_text(json.dumps(v))
            for i,response in enumerate((b'\r\nOK\r\n',b'\r\nERROR\r\n')):
                target=root/str(i);target.mkdir();link=Link(response)
                def write(a,v):link.byte_grant.check(a,v);link.sent+=1
                with patch.object(q.g,'save',side_effect=save),patch.object(q.g,'write_private',side_effect=lambda p,b:Path(p).write_bytes(b)), \
                     patch.object(q.time,'monotonic',side_effect=lambda:clock[0]),patch.object(q.time,'sleep',side_effect=lambda n:clock.__setitem__(0,clock[0]+n)):
                    if i:
                        with self.assertRaisesRegex(ValueError,'RESPONSE_NOT_OK'):q.capture(link,types.SimpleNamespace(write32=write),q.COMMANDS[0],target,0)
                    else:self.assertEqual(q.capture(link,types.SimpleNamespace(write32=write),q.COMMANDS[0],target,0),response)
                self.assertEqual((target/'query-0-response-private.bin').read_bytes(),response)
    def test_ROM_entry_closes_without_extra_snapshot_query_or_recovery(self):
        with tempfile.TemporaryDirectory() as temp:
            out=Path(temp)/'attempt'
            link=types.SimpleNamespace(open=lambda:None,u32=lambda a:0,error=False,raw_failed=False,read_failed=False,
                  byte_grant=types.SimpleNamespace(history=[]),native_UART_writes=0,sdk_calls=0,verified_running_flash=False)
            from unittest.mock import Mock
            link.close=Mock()
            def save(p,v):Path(p).write_text(json.dumps(v))
            with patch.object(q,'QueryLink',return_value=link),patch.object(q.site.ro.raw,'identity',return_value={}), \
                 patch.object(q.g,'load',return_value={}),patch.object(q.g,'save',side_effect=save), \
                 patch.object(q.g.private,'protected',side_effect=lambda p,_:p), \
                 patch.object(q.site.ro.old,'snapshot',return_value={'VTOR':0x1fff0000}) as snapshot, \
                 patch.object(q.site.ro.old,'check_running',side_effect=ValueError('C_RO_ROM_STOP')), \
                 contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(q.worker({}, {'C_identity':{'path':'SYNTHETIC'}},out),1)
            self.assertEqual(snapshot.call_count,1);link.close.assert_called_once()
            r=json.loads((out/'receipt-private.json').read_text());self.assertEqual(r['UART_native_write_attempts'],0)

if __name__=='__main__':unittest.main()
