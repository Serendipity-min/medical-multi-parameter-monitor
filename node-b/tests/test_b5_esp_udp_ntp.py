"""单包权限、二进制帧和NTP校验的定向测试，不访问设备或网络。"""
import contextlib
import io
import json
import struct
import sys
import tempfile
import types
from pathlib import Path
import unittest
from unittest.mock import Mock,patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import b5_esp_udp_ntp as u


def request():
    p=bytearray(48);p[0]=0x23;p[40:48]=b'12345678';return bytes(p)


def response():
    p=bytearray(48);p[0]=0x24;p[1]=1;p[24:32]=request()[40:48]
    struct.pack_into('!II',p,32,1793080000+2208988800,0)
    struct.pack_into('!II',p,40,1793080000+2208988800,0);return bytes(p)


class Tests(unittest.TestCase):
    def test_default_never_executes(self):
        with patch.object(sys,'argv',['udp']),patch.object(u,'worker') as worker,contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(u.main(),0);worker.assert_not_called()
    def test_disabled_authorization_stops_before_file_access(self):
        with self.assertRaisesRegex(ValueError,'OWNER_SCOPE'):u.validate({'enabled':False})
    def test_plan_has_exactly_one_payload_and_no_identity_or_time_setting(self):
        commands=u.plan('192.0.2.1',request())
        self.assertEqual(len(commands),11);self.assertEqual(commands.count(b'AT+CIPSEND=48\r\n'),1)
        self.assertEqual(commands.count(request()),1);self.assertEqual(commands[-2],b'AT+CIPCLOSE\r\n')
        self.assertFalse(any(b'SYSTIMESTAMP=' in c or b'CWJAP=' in c or b'B5START' in c for c in commands))
        grant=u.q.ByteGrant(commands)
        for command in commands:
            grant.begin(command)
            for value in command:grant.check(u.q.DR,value)
        with self.assertRaises(ValueError):grant.begin(request())
    def test_non_IP_or_non_48B_packet_denied(self):
        with self.assertRaises(ValueError):u.plan('bad"\r\nAT+RST',request())
        with self.assertRaises(ValueError):u.plan('192.0.2.1',bytes(47))
    def test_native_and_high_level_uid_flash_options_reads_are_denied(self):
        link=object.__new__(u.UdpLink)
        for address,size in [(0x1fff7a10,12),(0x1fff7a22,2),(0x08000000,64),(0x08000000,1048576),(0x1fffc000,16),(0xe000ed00,4)]:
            with self.assertRaisesRegex(ValueError,'MINIMAL_READ_SCOPE'):link.read(address,size)
            with self.assertRaisesRegex(ValueError,'MINIMAL_READ_SCOPE'):link._call_native('JLINKARM_ReadMemEx',address,size,None,0)
    def test_raw_DAP_cannot_read_identity_or_vectors(self):
        link=object.__new__(u.UdpLink);link.dap_select=0
        for address in (0xe000ed00,0x08000000):
            link.dap_tar=address
            with self.assertRaisesRegex(ValueError,'IDENTITY_DAP_READ'):link._call_native('JLINKARM_CORESIGHT_ReadAPDPReg',3,1,None)
    def test_target_writes_other_than_exact_UART_bytes_are_denied(self):
        grant=u.q.ByteGrant(u.plan('192.0.2.1',request()));grant.begin(b'AT+CIPSNTPCFG?\r\n')
        for address in (u.q.CR,0x0800c000,u.q.UART+8,0x2001170c):
            with self.assertRaises(ValueError):grant.check(address,65)
    def test_prompt_and_send_ok_are_distinct(self):
        self.assertEqual(u.terminal(b'\r\nOK\r\n> ','PROMPT'),'PROMPT')
        self.assertIsNone(u.terminal(b'\r\nOK\r\n','PROMPT'))
        self.assertEqual(u.terminal(b'\r\nSEND OK\r\n','SEND'),'SEND_OK')
        self.assertEqual(u.terminal(b'\r\nERROR\r\n','OK'),'ERROR')
    def test_active_and_both_passive_binary_formats_preserve_NUL(self):
        body=response()
        for prefix,fmt in [(b'+IPD,48:','IPD_ACTIVE'),(b'+CIPRECVDATA:48,','CIPRECVDATA'),(b'+CIPRECVDATA,48:','CIPRECVDATA')]:
            packets,spans,partial=u.framed(b'\r\n'+prefix+body+b'\r\nOK\r\n')
            self.assertEqual(packets[0][0],body);self.assertEqual(packets[0][3],fmt);self.assertFalse(partial)
    def test_binary_OK_ERROR_and_nested_header_do_not_finish_AT(self):
        body=bytearray(48);body[0:9]=b'\r\nERROR\r\n';body[10:16]=b'\r\nOK\r\n';body[20:28]=b'+IPD,1:x'
        data=b'+CIPRECVDATA:48,'+body
        self.assertIsNone(u.terminal(data,'OK'));self.assertEqual(len(u.framed(data)[0]),1)
        self.assertEqual(u.terminal(data+b'\r\nOK\r\n','OK'),'OK')
    def test_partial_and_oversize_frames_not_accepted(self):
        self.assertTrue(u.framed(b'+IPD,48:'+bytes(47))[2]);self.assertIsNone(u.terminal(b'+IPD,48:'+bytes(47),'OK'))
        with self.assertRaisesRegex(ValueError,'FRAME_LENGTH_BOUND'):u.framed(b'+IPD,9999:')
    def test_no_socket_requires_IP_ready_and_no_connection_rows(self):
        self.assertTrue(u.no_socket(b'STATUS:2\r\nOK\r\n'))
        for bad in (b'STATUS:5\r\n',b'STATUS:3\r\n',b'STATUS:2\r\n+CIPSTATUS:0,"UDP"\r\n'):
            self.assertFalse(u.no_socket(bad))
    def test_dinfo_false_is_zero_without_a_setting_command(self):
        for value in (b'0',b'false',b'False'):
            self.assertTrue(u.dinfo_disabled(b'\r\n+CIPDINFO:'+value+b'\r\n\r\nOK\r\n'))
        for value in (b'1',b'true'):
            self.assertFalse(u.dinfo_disabled(b'\r\n+CIPDINFO:'+value+b'\r\n\r\nOK\r\n'))
    def test_packet_marker_is_exclusive_even_across_execution_records(self):
        with tempfile.TemporaryDirectory() as temp:
            marker=Path(temp)/'payload.used'
            def exclusive_save(path,data):
                with Path(path).open('x') as stream:json.dump(data,stream)
            with patch.object(u.g,'save',side_effect=exclusive_save):
                u.claim_payload({'payload_once_marker':str(marker)})
                with self.assertRaises(FileExistsError):u.claim_payload({'payload_once_marker':str(marker)})
    def test_valid_nonce_reply_and_g3_rtt_not_claimed(self):
        r=u.inspect_packet(response(),request(),1793080000050)
        self.assertTrue(r['packet_fields_valid']);self.assertTrue(r['nonce_matches']);self.assertIn('NOT_VALIDATED',r['G3_RTT_1S_and_clock_installation'])
    def test_nonce_LI_version_mode_KOD_and_receive_timestamp_checks(self):
        self.assertFalse(u.inspect_packet(bytes(47),request(),1793080000000)['packet_fields_valid'])
        for offset,value in [(24,0),(0,0xe4),(0,0x14),(0,0x23),(1,0)]:
            body=bytearray(response());body[offset]=value
            self.assertFalse(u.inspect_packet(bytes(body),request(),1793080000000)['packet_fields_valid'])
        body=bytearray(response());body[32:40]=bytes(8)
        self.assertFalse(u.inspect_packet(bytes(body),request(),1793080000000)['packet_fields_valid'])
    def test_ROM_stops_runtime_before_UART_packet(self):
        values={a:0 for a in u.CORE.values()};values.update({u.CORE['VTOR']:0x1fff0000,u.CORE['DWT_PCSR']:0x1fff32f2})
        link=types.SimpleNamespace(u32=lambda a:values.get(a,1),read=lambda a,n:bytes(n),verified_running_flash=True)
        with patch.object(u.g,'save'):
            with self.assertRaisesRegex(ValueError,'ROM_STOP'):u.runtime(link,Path('SYNTHETIC'),'entry')
        self.assertFalse(link.verified_running_flash)
    def test_controller_sends_once_and_closes_with_or_without_reply(self):
        for has_reply in (False,True):
            with self.subTest(reply=has_reply),tempfile.TemporaryDirectory() as temp:
                out=Path(temp)/'attempt';clock=[0.0];commands=u.plan('192.0.2.1',request())
                active=b'\r\nSEND OK\r\n'+(b'+IPD,48:'+response() if has_reply else b'')
                link=types.SimpleNamespace(open=lambda:None,u32=lambda a:{u.q.UART+8:69,u.q.UART+12:0x202c,0x40023808:4}.get(a,0),
                    call=lambda *a:1,native_UART_writes=0,sdk_calls=0,close_resume_enabled=False,
                    close=lambda:None,verified_running_flash=True,query_before_verified=False,
                    byte_grant=u.q.ByteGrant(commands),error=False)
                link.set_close_resume=lambda enabled:setattr(link,'close_resume_enabled',enabled)
                replies=[b'\r\n+CIPSNTPCFG:0\r\n\r\nOK\r\n',b'\r\n+CIPMUX:0\r\n\r\nOK\r\n',
                    b'\r\n+CIPRECVMODE:0\r\n\r\nOK\r\n',b'\r\n+CIPDINFO:'+(b'false' if has_reply else b'0')+b'\r\n\r\nOK\r\n',
                    b'STATUS:2\r\nOK\r\n',b'CONNECT\r\nOK\r\n',b'OK\r\n>',active,
                    b'\r\nERROR\r\n',b'CLOSED\r\nOK\r\n',b'STATUS:2\r\nOK\r\n']
                def exchange(*args,**kw):return replies[args[4]],(0,0,0,0,0),clock[0]
                with patch.object(u,'UdpLink',return_value=link),patch.object(u,'runtime'),patch.object(u.q,'rx_route_snapshot',return_value={}), \
                     patch.object(u.q.site.config,'NativeBus'),patch.object(u,'UartBridge'), \
                     patch.object(u,'exchange',side_effect=exchange) as calls,patch.object(u,'ring_since',return_value=active), \
                     patch.object(u.time,'monotonic',side_effect=lambda:clock[0]),patch.object(u.time,'sleep',side_effect=lambda n:clock.__setitem__(0,clock[0]+n)), \
                     patch.object(u.time,'time',return_value=1793080000.05),patch.object(u.g.private,'protected'), \
                     patch.object(u.g,'save',side_effect=lambda p,v:Path(p).write_text(json.dumps(v))), \
                     patch.object(u.g,'write_private',side_effect=lambda p,b:Path(p).write_bytes(b)),contextlib.redirect_stdout(io.StringIO()):
                    self.assertEqual(u.worker({'payload_once_marker':str(Path(temp)/'payload.used')},commands,request(),out),0)
                receipt=json.loads((out/'receipt-private.json').read_text())
                self.assertEqual(receipt['UDP_payload_attempts'],1);self.assertTrue(receipt['socket_close_confirmed'])
                self.assertEqual(receipt['matching_valid_reply'],has_reply)
                self.assertEqual([x.args[4] for x in calls.call_args_list],list(range(11)))
                self.assertEqual(sum(x.args[2]==request() for x in calls.call_args_list),1)


if __name__=='__main__':unittest.main()
