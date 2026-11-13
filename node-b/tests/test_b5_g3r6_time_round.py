"""授时事务编排与冻结C函数负例；不访问设备或网络。"""
import contextlib
import ctypes as C
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
import b5_g3r6_time_round as t

WIFI={'ssid':'Synthetic24','password':'temporary-only'}
SERVER='ntp.example.invalid'


class Tests(unittest.TestCase):
    def test_default_disabled_and_missing_permission(self):
        with patch.object(sys,'argv',['round']),patch.object(t,'worker') as worker,contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(t.main(),0);worker.assert_not_called()
        with self.assertRaises(ValueError):t.validate({},'sntp')
    def test_SnTP_plan_is_volatile_single_enable_two_off_twelve_samples(self):
        commands=t.sntp_plan(WIFI,SERVER)
        self.assertEqual(len(commands),31);self.assertEqual(commands.count(b'AT+CIPSNTPCFG=1,0\r\n'),1)
        self.assertEqual(commands.count(b'AT+CIPSNTPCFG=0\r\n'),2)
        self.assertEqual(commands.count(b'AT+SYSTIMESTAMP?\r\n'),12)
        wire=b''.join(commands)
        for bad in (b'SYSSTORE=1',b'SYSTIMESTAMP=',b'B5START',b'AT+RST',b'CIPSEND'):self.assertNotIn(bad,wire)
    def test_UDP_exact_packet_fixed_port_passive_then_restore(self):
        packet=bytes([0x23])+bytes(47)
        for mode in (0,1):
            with patch.object(t.ipaddress.IPv4Address,'is_global',new=property(lambda self:True)):
                commands=t.udp_plan('192.0.2.123',packet,mode)
            self.assertEqual(commands.count(packet),1);self.assertIn(b'123,42024,0',commands[7])
            self.assertEqual(commands[-2],b'AT+CIPRECVMODE='+str(mode).encode()+b'\r\n')
            self.assertNotIn(b'CIPSNTPCFG=1',b''.join(commands))
        for address in ('127.0.0.1','192.0.2.1','bad\r\nAT'):
            with self.assertRaises(ValueError):t.udp_plan(address,packet,0)
    def test_command_injection_and_half_cleanup_rejected(self):
        for field in ('ssid','password'):
            wifi=dict(WIFI);wifi[field]='bad\r\nAT'
            with self.assertRaises(ValueError):t.sntp_plan(wifi,SERVER)
        with self.assertRaises(ValueError):t.sntp_plan(WIFI,'x"\r\n')
        grant=t.p.Grant(t.sntp_plan(WIFI,SERVER));grant.cleanup_index=28;grant.begin(grant.allowed_commands[0])
        with self.assertRaises(ValueError):grant.cleanup()
    def test_sdk_bound_covers_whole_plan_entry_exit_and_failure_cleanup(self):
        commands=t.sntp_plan(WIFI,SERVER);limit=t.sdk_bound(commands,'sntp')
        self.assertLessEqual(limit,30000)
        self.assertGreater(limit,sum(t.command_calls(c,t.timeout_for('sntp',i)) for i,c in enumerate(commands)))
    def test_real_C_parser_rejects_old_nonce_KoD_LI_late_old_time_bad_order(self):
        dll=C.CDLL(str((t.g.ROOT/'node-b/build/g3r6-time/host_sntp_reference.dll').resolve()))
        request=bytearray(48);request[0]=0x23;request[40:48]=b'12345678'
        reply=bytearray(48);reply[0]=0x24;reply[1]=2;reply[24:32]=request[40:48]
        struct.pack_into('!I',reply,32,t.MINIMUM+2208988800);struct.pack_into('!I',reply,40,t.MINIMUM+2208988800)
        self.assertTrue(t.reference_check(dll,bytes(reply),bytes(request),1000)['C_sntp_sample_pass'])
        for offset,value in [(0,0xe4),(0,0x23),(1,0),(24,0)]:
            packet=bytearray(reply);packet[offset]=value
            self.assertFalse(t.reference_check(dll,bytes(packet),bytes(request),100)['C_sntp_sample_pass'])
        self.assertFalse(t.reference_check(dll,bytes(reply),bytes(request),1001)['C_sntp_sample_pass'])
        self.assertFalse(t.reference_check(dll,bytes(reply[:-1]),bytes(request),100)['C_sntp_sample_pass'])
        packet=bytearray(reply);struct.pack_into('!I',packet,32,t.MINIMUM+2208988801)
        self.assertFalse(t.reference_check(dll,bytes(packet),bytes(request),100)['C_sntp_sample_pass'])
        packet=bytearray(reply);struct.pack_into('!I',packet,40,t.MINIMUM+2208988799)
        self.assertFalse(t.reference_check(dll,bytes(packet),bytes(request),100)['C_sntp_sample_pass'])
    def run_sntp(self,valid=True,entry_error=None,close_error=False,store_one=False,set_error=False):
        commands=t.sntp_plan(WIFI,SERVER);calls=[]
        link=types.SimpleNamespace(open=Mock(),query_before_verified=False,error=False,read_failed=False,raw_failed=False,
            sdk_calls=0,sdk_limit=30000,native_UART_writes=0,close_resume_enabled=False,verified_running_flash=False)
        link.u32=lambda address:{t.q.UART+8:1,t.q.UART+12:0x202c}.get(address,0)
        link.set_close_resume=lambda v:setattr(link,'close_resume_enabled',v)
        def close():
            if close_error:raise RuntimeError('synthetic close')
            link.close_completed=True
        link.close=close
        def exchange(link,bridge,command,out,index,**kwargs):
            calls.append(index);link.byte_grant.begin(command)
            for value in command:link.byte_grant.check(t.q.DR,value)
            link.native_UART_writes+=len(command)
            if index==1 and set_error:raise ValueError('UDP_NO_EXPECTED_TERMINAL')
            values={0:b'+SYSSTORE:'+str(int(store_one)).encode()+b'\r\n',2:b'+SYSSTORE:0\r\n',4:b'+CIPSNTPCFG:0\r\n',5:b'STATUS:5\r\n',
                8:b'+CWJAP:"Synthetic24","00:00:00:00:00:00",7,-40\r\n',10:b'+CIPMODE:0\r\n',11:b'+CIPMUX:0\r\n',12:b'+CIPRECVMODE:0\r\n',
                14:b'+CIPSNTPCFG:1,0,"ntp.example.invalid"\r\n',27:b'+CIPDOMAIN:192.0.2.123\r\n',29:b'+CIPSNTPCFG:0\r\n',30:b'STATUS:2\r\n'}
            raw=b'+SYSTIMESTAMP:'+str((t.MINIMUM if valid else 10)+index).encode()+b'\r\n' if 15<=index<27 else values.get(index,b'')
            return raw+b'\r\nOK\r\n',(),0
        route={k:True for k in ('PB10_PB11_AF7','GPIOB_clock_enabled','USART3_clock_enabled','USART3_IRQ_enabled','uptime_advances')}
        with tempfile.TemporaryDirectory() as folder:
            out=Path(folder)/'sntp'
            with patch.object(t.u,'UdpLink',return_value=link),patch.object(t.u,'runtime',side_effect=entry_error),patch.object(t.q,'rx_route_snapshot',return_value=route), \
                patch.object(t.q,'baud_from_registers',return_value=115200),patch.object(t.u,'UartBridge'),patch.object(t.q.site.config,'NativeBus'), \
                patch.object(t.u,'exchange',side_effect=exchange),patch.object(t.time,'sleep'),patch.object(t.g.private,'protected'), \
                patch.object(t.g,'save',side_effect=lambda f,r:Path(f).write_text(json.dumps(r))),patch.object(t.g,'write_private'), \
                patch.object(t.ipaddress.IPv4Address,'is_global',new=property(lambda self:True)),contextlib.redirect_stdout(io.StringIO()):
                code=t.worker({'commands_hex':[c.hex() for c in commands],'SDK_limit':t.sdk_bound(commands,'sntp'),'ssid':WIFI['ssid'],'dns_names':[SERVER]},'sntp',out)
            result=json.loads((out/'receipt-private.json').read_text())
        return code,result,calls
    def test_normal_enable_time_progress_and_off_readback_are_all_required(self):
        code,r,calls=self.run_sntp();self.assertEqual(code,0);self.assertEqual(calls,[i for i in range(31) if i!=1])
        self.assertEqual(r['status'],'TIME_CLEAN_PASS');self.assertTrue(r['cleanup_verified']);self.assertEqual(r['manual_packets_attempted'],0)
        self.assertTrue(r['store_set_skipped_already_zero'])
    def test_store_one_must_write_zero_and_set_ERROR_cannot_join(self):
        code,r,calls=self.run_sntp(store_one=True);self.assertEqual(code,0);self.assertIn(1,calls)
        code,r,calls=self.run_sntp(store_one=True,set_error=True);self.assertEqual(code,1)
        self.assertEqual(calls,[0,1,28,29,30]);self.assertNotIn(7,calls);self.assertTrue(r['cleanup_verified'])
    def test_low_time_cleans_up_and_never_claims_PASS(self):
        code,r,calls=self.run_sntp(False);self.assertEqual(code,1);self.assertTrue(r['cleanup_verified']);self.assertEqual(r['status'],'STOP')
    def test_ROM_stops_before_AT_and_does_not_request_power_for_unstarted_network(self):
        code,r,calls=self.run_sntp(entry_error=ValueError('UDP_ROM_STOP'))
        self.assertEqual(code,1);self.assertFalse(calls);self.assertFalse(r['physical_stop_required'])
    def test_close_failure_cannot_keep_TIME_PASS(self):
        code,r,calls=self.run_sntp(close_error=True);self.assertEqual(code,1);self.assertEqual(r['status'],'STOP');self.assertTrue(r['physical_stop_required'])
    def run_udp(self,reply_present=True,slow=False):
        request=bytearray(48);request[0]=0x23;request[40:48]=b'abcdefgh'
        response=bytearray(48);response[0]=0x24;response[1]=2;response[24:32]=request[40:48]
        struct.pack_into('!I',response,32,t.MINIMUM+2208988800);struct.pack_into('!I',response,40,t.MINIMUM+2208988800)
        with patch.object(t.ipaddress.IPv4Address,'is_global',new=property(lambda self:True)):
            commands=t.udp_plan('192.0.2.123',bytes(request),0)
        calls=[];clock=[0.0]
        link=types.SimpleNamespace(open=Mock(),query_before_verified=False,error=False,sdk_calls=0,sdk_limit=30000,
            native_UART_writes=0,close_resume_enabled=False,close=lambda:None,set_close_resume=Mock(),verified_running_flash=False)
        link.u32=lambda address:{t.q.UART+8:1,t.q.UART+12:0x202c}.get(address,0)
        def exchange(link,bridge,command,out,index,**kwargs):
            calls.append(index);link.byte_grant.begin(command)
            for value in command:link.byte_grant.check(t.q.DR,value)
            link.native_UART_writes+=len(command);clock[0]+=2 if index==10 and slow else .05
            values={0:b'+SYSSTORE:0',1:b'+CIPSNTPCFG:0',2:b'+CIPMODE:0',3:b'+CIPMUX:0',4:b'+CIPRECVMODE:0',
                5:b'STATUS:2\r\n',10:b'+CIPRECVDATA:48,'+bytes(response) if reply_present else b'ERROR',12:b'STATUS:2\r\n',14:b'+CIPRECVMODE:0'}
            return values.get(index,b'OK')+b'\r\nOK\r\n',(),0
        route={k:True for k in ('PB10_PB11_AF7','GPIOB_clock_enabled','USART3_clock_enabled','USART3_IRQ_enabled','uptime_advances')}
        with tempfile.TemporaryDirectory() as folder:
            a={'root':folder,'commands_hex':[c.hex() for c in commands],'SDK_limit':t.sdk_bound(commands,'udp'),
                'receive_mode':0,'host_reference_DLL':str(t.g.ROOT/'node-b/build/g3r6-time/host_sntp_reference.dll')}
            out=Path(folder)/'udp'
            with patch.object(t.u,'UdpLink',return_value=link),patch.object(t.u,'runtime'),patch.object(t.q,'rx_route_snapshot',return_value=route), \
                patch.object(t.q,'baud_from_registers',return_value=115200),patch.object(t.u,'UartBridge'),patch.object(t.q.site.config,'NativeBus'), \
                patch.object(t.u,'exchange',side_effect=exchange),patch.object(t.time,'monotonic',side_effect=lambda:clock[0]),patch.object(t.g.private,'protected'), \
                patch.object(t.g,'save',side_effect=lambda f,r:Path(f).write_text(json.dumps(r))),patch.object(t.g,'write_private'),contextlib.redirect_stdout(io.StringIO()):
                code=t.worker(a,'udp',out)
            result=json.loads((out/'receipt-private.json').read_text())
            self.assertTrue((Path(folder)/'payload.used').exists())
        return code,result,calls
    def test_fresh_reply_requires_C_PASS_and_always_closes_restores(self):
        code,r,calls=self.run_udp();self.assertEqual(code,0);self.assertEqual(calls,list(range(15)))
        self.assertEqual(r['manual_packets_attempted'],1);self.assertTrue(r['cleanup_verified'])
        self.assertEqual(r['status'],'FRESH_PUBLIC_NTP_PASS')
    def test_SEND_OK_without_reply_is_failure_but_socket_closed(self):
        code,r,calls=self.run_udp(False);self.assertEqual(code,1);self.assertTrue(r['cleanup_verified'])
        self.assertEqual(r['status'],'STOP');self.assertEqual(calls.count(9),1)
    def test_slow_reply_not_allowed_to_pass_after_valid_nonce(self):
        code,r,calls=self.run_udp(slow=True);self.assertEqual(code,1);self.assertTrue(r['cleanup_verified'])
        self.assertFalse(r['NTP_checks'][0]['C_sntp_sample_pass'])


if __name__=='__main__':unittest.main()
