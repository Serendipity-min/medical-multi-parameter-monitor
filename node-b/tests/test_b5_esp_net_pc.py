import json
from pathlib import Path
import sys
import tempfile
import types
import unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import b5_esp_net_pc as n

REQ=bytes([0x23])+bytes(39)+b'NEWnonce'
PEER=('192.0.2.2',42024)


class Tests(unittest.TestCase):
    def test_default_disabled(self):
        with self.assertRaises(ValueError):n.validate({})

    def test_each_exception_must_be_explicit(self):
        a={'enabled':True,'owner_approved':True,'scope':n.SCOPE,'tools_sha256':n.bindings(),'expires_unix':n.time.time()+100}
        with self.assertRaisesRegex(ValueError,'LAN_EXCEPTIONS_REQUIRED'):n.validate(a)
        a['firewall_disabled_owner_exception']=True
        with self.assertRaisesRegex(ValueError,'LAN_EXCEPTIONS_REQUIRED'):n.validate(a)

    def test_fixed_single_plan_without_time_settings(self):
        p=n.commands('192.0.2.1',REQ)
        self.assertEqual(p[7],b'AT+CIPSTART="UDP","192.0.2.1",42023,42024,0\r\n')
        self.assertEqual(sum(v==REQ for v in p),1)
        self.assertNotIn(b'CIPRECVDATA',b''.join(p));self.assertNotIn(b'SYSTIMESTAMP=',b''.join(p))
        self.assertEqual(p[8],b'AT+CIPSTATUS\r\n')
        with self.assertRaises(ValueError):n.commands('192.0.2.1',REQ[:-1])

    def test_station_route_must_be_local_other_host(self):
        self.assertEqual(n.station_ip(b'+CIPSTA:ip:"192.0.2.2"\r\n','192.0.2.1',24),PEER[0])
        for ip in ('192.0.2.1','198.51.100.1','0.0.0.0'):
            with self.assertRaises(ValueError):n.station_ip(b'+CIPSTA:ip:"'+ip.encode()+b'"','192.0.2.1',24)

    def test_remote_and_local_socket_ports_are_both_checked(self):
        self.assertTrue(n.socket_tuple(b'+CIPSTATUS:0,"UDP","192.0.2.1",42023,42024,0','192.0.2.1'))
        for line in (b'+CIPSTATUS:0,"UDP","192.0.2.1",42024,42023,0',b'+CIPSTATUS:0,"UDP","192.0.2.9",42023,42024,0'):
            self.assertFalse(n.socket_tuple(line,'192.0.2.1'))

    def test_reply_matches_nonce_but_is_not_time_authority(self):
        reply=n.response48(REQ,REQ,PEER,PEER,1793090000000000000,1793090000001000000)
        self.assertEqual(len(reply),48);self.assertEqual(reply[24:32],REQ[40:48]);self.assertEqual(reply[:2],b'\xe4\x10')
        self.assertFalse(n.u.inspect_packet(reply,REQ,1793090000000)['packet_fields_valid'])

    def test_wrong_peer_length_or_replay_never_gets_reply(self):
        for data,peer in ((REQ[:-1],PEER),(REQ+b'x',PEER),(REQ[:-1]+b'x',PEER),(REQ,('192.0.2.3',42024)),(REQ,(PEER[0],123))):
            with self.assertRaises(ValueError):n.response48(data,REQ,peer,PEER,100,101)
        with self.assertRaises(ValueError):n.response48(REQ,REQ,PEER,PEER,101,100)

    def test_wait_never_ignores_stop(self):
        with tempfile.TemporaryDirectory() as folder:
            out=Path(folder);(out/'STOP').write_text('stop')
            with self.assertRaises(ValueError):n.wait_file(out/'absent',n.time.monotonic()+10,out)

    def pc_case(self,data,bind_failure=False):
        class FakeSocket:
            def __init__(self):self.calls=[]
            def setsockopt(self,*a):self.calls.append(('exclusive',a))
            def bind(self,a):
                self.calls.append(('bind',a))
                if bind_failure:raise OSError('synthetic bind failure')
            def connect(self,a):self.calls.append(('connect',a))
            def settimeout(self,a):pass
            def getsockname(self):return ('192.0.2.1',42023)
            def getpeername(self):return PEER
            def recv(self,size):self.calls.append(('recv',size));return data
            def send(self,reply):self.calls.append(('send',reply));return len(reply)
            def close(self):self.calls.append(('close',))
        fake=FakeSocket()
        with tempfile.TemporaryDirectory() as folder:
            out=Path(folder)
            save=lambda p,v:Path(p).write_text(json.dumps(v))
            with patch.object(n,'wait_file',return_value={'IP':PEER[0]}),patch.object(n.socket,'socket',return_value=fake),patch.object(n.select,'select',return_value=([fake],[],[])),patch.object(n.g,'save',side_effect=save),patch.object(n.g,'write_private',side_effect=lambda p,b:Path(p).write_bytes(b)):
                result=n.pc_worker({'PC_IPv4':'192.0.2.1'},REQ,out)
            receipt=json.loads((out/'PC-receipt-private.json').read_text())
            return result,receipt,fake.calls,(out/'PC_READY.json').exists()

    def test_pc_socket_is_exclusive_connected_and_sends_once(self):
        result,receipt,calls,ready=self.pc_case(REQ)
        self.assertEqual(result,0);self.assertTrue(ready);self.assertEqual(receipt['reply_attempts'],1)
        self.assertEqual([c[0] for c in calls],['exclusive','bind','connect','recv','send','close'])
        self.assertEqual(calls[3],('recv',49));self.assertTrue(receipt['socket_closed'])

    def test_wrong_request_closes_without_sending(self):
        result,receipt,calls,_=self.pc_case(REQ+b'x')
        self.assertEqual(result,1);self.assertEqual(receipt['reply_attempts'],0)
        self.assertNotIn('send',[c[0] for c in calls]);self.assertEqual(calls[-1],('close',))

    def test_bind_failure_never_becomes_ready(self):
        result,receipt,calls,ready=self.pc_case(REQ,True)
        self.assertEqual(result,1);self.assertFalse(ready);self.assertNotIn('recv',[c[0] for c in calls])

    def test_ROM_stops_before_UART_and_network_peer(self):
        with tempfile.TemporaryDirectory() as folder:
            out=Path(folder);fake=types.SimpleNamespace(open=lambda:None,u32=lambda a:0,query_before_verified=False,
                native_UART_writes=0,sdk_calls=0,close_resume_enabled=False,close=lambda:None)
            with patch.object(n.u,'UdpLink',return_value=fake),patch.object(n.u,'runtime',side_effect=ValueError('UDP_ROM_STOP')),patch.object(n.g,'save',side_effect=lambda p,v:Path(p).write_text(json.dumps(v))):
                result=n.esp_worker({},n.commands('192.0.2.1',REQ),REQ,out)
            self.assertEqual(result,1);self.assertFalse((out/'ESP-peer-private.json').exists())
            self.assertEqual(json.loads((out/'ESP-receipt-private.json').read_text())['payload_attempts'],0)


    def test_supervisor_hard_limit_kills_workers_without_retry(self):
        class Child:
            returncode=None
            def poll(self):return self.returncode
            def kill(self):self.returncode=-9
            def wait(self,timeout):return self.returncode
        with tempfile.TemporaryDirectory() as folder:
            out=Path(folder)/'run';auth=Path(folder)/'authorization.json';children=[Child(),Child()]
            a={'output':str(out)};auth.write_text('{}');ticks=iter([0,181,181,181,181,181])
            with patch.object(n.sys,'argv',['tool','--execute','--authorization',str(auth)]),patch.object(n,'validate',return_value=([],REQ)),patch.object(n.g,'load',return_value=a),patch.object(n.g.private,'protected'),patch.object(n.g,'save',side_effect=lambda p,v:Path(p).write_text(json.dumps(v))),patch.object(n.g,'write_private',side_effect=lambda p,b:Path(p).write_bytes(b)),patch.object(n.subprocess,'Popen',side_effect=children) as popen,patch.object(n.time,'monotonic',side_effect=lambda:next(ticks,181)),patch.object(n.time,'sleep'),patch('builtins.print'):
                result=n.main()
            self.assertEqual(result,1);self.assertEqual(popen.call_count,2)
            receipt=json.loads((out/'supervisor-private.json').read_text())
            self.assertEqual(receipt['reason'],'LAN_HARD_180S');self.assertEqual(receipt['ESP_payload_attempts'],0)
            self.assertTrue((out/'STOP').exists());self.assertTrue(all(c.returncode==-9 for c in children))

    def test_partial_frame_never_masquerades_as_complete_reply(self):
        packet,spans,partial=n.u.framed(b'+IPD,48:'+bytes(20))
        self.assertTrue(partial);self.assertFalse(packet)


    def test_WiFi_join_is_optional_volatile_and_before_LAN(self):
        wifi={'ssid':'Test,SSID','password':'synthetic"password'}
        plan=n.commands('192.0.2.1',REQ,wifi)
        self.assertEqual(plan[2],b'AT+SYSSTORE=0\r\n');self.assertEqual(plan[3],b'AT+SYSSTORE?\r\n')
        self.assertEqual(plan[4],b'AT+CWJAP="Test\\,SSID","synthetic\\"password"\r\n')
        self.assertEqual(plan[5],b'AT+CIPSTA?\r\n');self.assertEqual(sum(c==REQ for c in plan),1)
        self.assertNotIn(b'SYSSTORE=1',b''.join(plan))
        for invalid in ('a\rb','a\nb','a\0b'):
            with self.assertRaises(ValueError):n.at_string(invalid)

    def test_join_payload_cannot_change_fixed_peer_ports(self):
        plan=n.commands('192.0.2.1',REQ,{'ssid':'TestSSID','password':'synthetic-password'})
        self.assertEqual(plan[12],b'AT+CIPSTART="UDP","192.0.2.1",42023,42024,0\r\n')
        self.assertEqual(plan[-2:],(b'AT+CIPCLOSE\r\n',b'AT+CIPSTATUS\r\n'))


    def test_prejoin_disconnected_is_not_an_existing_socket(self):
        self.assertTrue(n.prejoin_no_socket(b'STATUS:5\r\nOK\r\n'))
        self.assertFalse(n.u.no_socket(b'STATUS:5\r\nOK\r\n'))
        self.assertFalse(n.prejoin_no_socket(b'STATUS:3\r\n+CIPSTATUS:0,"UDP","192.0.2.1",42023,42024,0\r\n'))
        self.assertFalse(n.prejoin_no_socket(b'STATUS:4\r\n+CIPSTATUS:0,"UDP","192.0.2.1",42023,42024,0\r\n'))


if __name__=='__main__':unittest.main()
