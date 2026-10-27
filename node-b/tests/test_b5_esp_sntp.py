"""SNTP固定易失计划的定向验证，不连接设备或网络。"""
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
import b5_esp_sntp as s
import b5_sector3_plan as planner


def synthetic_image():
    payload=bytearray(312);struct.pack_into('<II',payload,0,0x31435747,1792977536)
    for key,offset,width in planner.FIELDS:
        value={'ssid':b'LAB-FIXTURE','wifi_password':b'INVALID-TEST-PASSWORD'}.get(key,b'synthetic.invalid')
        payload[offset:offset+len(value)]=value
    record=bytearray(24)+payload;struct.pack_into('<IHHIIII',record,0,0x32433348,1,24,312,4,0,0x54494d43)
    struct.pack_into('<I',record,16,planner.record_crc(record))
    full=bytearray(1048576);full[49152:49152+336]=record;return bytes(full)


def sample(offset,epoch):
    return {'elapsed_s':offset,'UTC_ms':1793080000000+offset*1000,
            'raw':('\r\n+SYSTIMESTAMP:'+str(epoch)+'\r\n\r\nOK\r\n').encode()}


class Tests(unittest.TestCase):
    def test_default_never_executes(self):
        with patch.object(sys,'argv',['sntp']),patch.object(s,'worker') as worker,contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(s.main(),0);worker.assert_not_called()
    def test_disabled_scope_stops_before_file_access(self):
        with self.assertRaisesRegex(ValueError,'OWNER_SCOPE'):s.validate({'enabled':False})
    def test_plan_uses_actual_record_credentials_only_in_private_command(self):
        full=synthetic_image()
        with patch.object(s.g,'C_FULL',s.g.sha(full)):commands,minimum=s.command_plan(full)
        self.assertEqual(commands[3],b'AT+CWJAP="LAB-FIXTURE","INVALID-TEST-PASSWORD"\r\n')
        self.assertEqual(minimum,1792977536);self.assertEqual(len(commands),13)
        self.assertEqual(commands[0],b'AT+SYSSTORE=0\r\n');self.assertEqual(commands[1],b'AT+SYSSTORE?\r\n')
        self.assertEqual(commands[5:7],(b'AT+CIPSNTPCFG=1,0\r\n',b'AT+CIPSNTPCFG?\r\n'))
        self.assertEqual(commands[7:11],(b'AT+SYSTIMESTAMP?\r\n',)*4)
        self.assertEqual(commands[11:],(b'AT+CIPSNTPCFG=0\r\n',b'AT+CIPSNTPCFG?\r\n'))
        self.assertFalse(any(b'SYSTIMESTAMP=' in x or x==b'AT+SYSSTORE=1\r\n' for x in commands))
    def test_wrong_reference_image_denied(self):
        with self.assertRaisesRegex(ValueError,'REFERENCE_IMAGE'):s.command_plan(b'bad')
    def test_dns_plan_only_exact_existing_hosts_and_no_setters(self):
        full=synthetic_image();hosts=['first.invalid','second.invalid','third.invalid']
        with patch.object(s.g,'C_FULL',s.g.sha(full)):
            commands,_=s.command_plan(full,hosts)
            for bad in ([],['bad"\r\nAT+RST'],['a.invalid']*4):
                with self.assertRaisesRegex(ValueError,'DNS_TARGET'):s.command_plan(full,bad)
        self.assertEqual(commands,tuple(('AT+CIPDOMAIN="'+x+'"\r\n').encode() for x in hosts))
        grant=s.q.ByteGrant(commands)
        with self.assertRaises(ValueError):grant.begin(b'AT+CIPDNS=1,"192.0.2.1"\r\n')
    def test_dns_replies_mask_addresses_and_do_not_claim_udp_success(self):
        r=s.dns_findings([b'\r\n+CIPDOMAIN:192.0.2.1\r\n\r\nOK\r\n',b'\r\nERROR\r\n'])
        self.assertTrue(r['DNS_queries'][0]['IP_parsed']);self.assertFalse(r['all_resolved'])
        self.assertNotIn('192.0.2.1',json.dumps(r));self.assertIn('NOT_PROVEN',r['UDP_123_reachability'])
        self.assertTrue(s.dns_findings([b'\r\n+CIPDOMAIN:"192.0.2.1"\r\n\r\nOK\r\n'])['all_resolved'])
    def test_selected_plan_is_one_existing_server_and_exact_G3_replay(self):
        full=synthetic_image()
        with patch.object(s.g,'C_FULL',s.g.sha(full)):commands,_=s.command_plan(full,selected_server='second.invalid')
        self.assertEqual(len(commands),12)
        self.assertEqual(commands[1],b'AT+CIPSNTPCFG=1,0,"second.invalid"\r\n')
        self.assertEqual(commands[7],b'AT+CIPSNTPCFG=1,0\r\n');self.assertEqual(commands[10],b'AT+CIPSNTPCFG=0\r\n')
        self.assertFalse(any(b'SYSTIMESTAMP=' in c or b'CWJAP=' in c for c in commands))
    def test_selected_time_success_and_G3_overwrite_are_separate_observations(self):
        full=synthetic_image()
        with patch.object(s.g,'C_FULL',s.g.sha(full)):commands,_=s.command_plan(full,selected_server='second.invalid')
        samples=[sample(o,1793080000+o) for o in s.OFFSETS]
        cfg=b'\r\n+CIPSNTPCFG:1,0,"second.invalid"\r\n\r\nOK\r\n'
        replaced=b'\r\n+CIPSNTPCFG:1,0,"first.invalid"\r\n\r\nOK\r\n'
        for after,expected in [(cfg,True),(replaced,False)]:
            r={};replies=[b'\r\n+SYSSTORE:0\r\n\r\nOK\r\n',b'\r\nOK\r\n',cfg,
                b'\r\nOK\r\n',after,samples[-1]['raw'],b'\r\nOK\r\n',b'\r\n+CIPSNTPCFG:0\r\n\r\nOK\r\n']
            with patch.object(s.q,'capture',side_effect=replies),patch.object(s,'observe_times',return_value=samples):
                observed=s.observe_selected(None,None,commands,None,1792977536,r,'second.invalid')
            self.assertTrue(observed['coarse_UTC_observation_pass']);self.assertEqual(observed['exact_G3_preserves_selected_primary'],expected)
            self.assertTrue(r['SNTP_stop_verified'])
    def test_exact_plan_rejects_extra_server_setting_and_fake_time(self):
        full=synthetic_image()
        with patch.object(s.g,'C_FULL',s.g.sha(full)):commands,_=s.command_plan(full)
        for forbidden in (b'AT+CIPSNTPCFG=1,0,"synthetic.invalid"\r\n',b'AT+SYSTIMESTAMP=1793080000\r\n',b'B5START\n'):
            grant=s.q.ByteGrant(commands)
            with self.assertRaises(ValueError):grant.begin(forbidden)
        grant=s.q.ByteGrant(commands)
        for command in commands:
            grant.begin(command)
            for b in command:grant.check(s.q.DR,b)
        self.assertEqual(bytes(grant.history),b''.join(commands))
        with self.assertRaises(ValueError):grant.begin(commands[0])
    def test_observed_time_progress_pass_does_not_claim_TLS_or_nonce(self):
        cfg=b'\r\n+CIPSNTPCFG:1,0,"synthetic.invalid"\r\n\r\nOK\r\n'
        r=s.findings(b'\r\nOK\r\n',cfg,[sample(o,1793080000+o) for o in s.OFFSETS],1792977536)
        self.assertTrue(r['coarse_UTC_observation_pass']);self.assertTrue(r['time_progresses'])
        self.assertIn('NOT_PROVEN',r['fresh_nonce_UDP_SNTP_TLS_validation'])
    def test_enable_error_or_disabled_readback_cannot_pass(self):
        rows=[sample(o,1793080000+o) for o in s.OFFSETS]
        for reply,cfg in [(b'\r\nERROR\r\n',b'\r\n+CIPSNTPCFG:1,0\r\n\r\nOK\r\n'),
                          (b'\r\nOK\r\n',b'\r\n+CIPSNTPCFG:0\r\n\r\nOK\r\n')]:
            self.assertFalse(s.findings(reply,cfg,rows,1792977536)['coarse_UTC_observation_pass'])
    def test_uptime_or_static_or_incorrect_clock_does_not_pass(self):
        cfg=b'\r\n+CIPSNTPCFG:1,0\r\n\r\nOK\r\n'
        for values in ([10,15,25,40],[1793080000]*4,[1793080100+o for o in s.OFFSETS]):
            rows=[sample(o,v) for o,v in zip(s.OFFSETS,values)]
            self.assertFalse(s.findings(b'\r\nOK\r\n',cfg,rows,1792977536)['coarse_UTC_observation_pass'])
    def test_no_valid_time_is_none_not_fabricated(self):
        rows=[{**sample(o,0),'raw':b'\r\nERROR\r\n'} for o in s.OFFSETS]
        r=s.findings(b'\r\nERROR\r\n',b'\r\nERROR\r\n',rows,1792977536)
        self.assertEqual(r['timestamp_epochs'],[None]*4);self.assertFalse(r['coarse_UTC_observation_pass'])
    def test_timeout_extension_is_bounded_before_any_UART_write(self):
        for timeout in (0,-1,31):
            with self.assertRaisesRegex(ValueError,'TIMEOUT_RANGE'):
                s.q.capture(None,None,b'AT\r\n',None,0,response_timeout_s=timeout)
    def test_store_readback_not_zero_stops_before_WIFI(self):
        full=synthetic_image();options=bytes(16);commands=None
        with patch.object(s.g,'C_FULL',s.g.sha(full)):commands,_=s.command_plan(full)
        uart={s.q.UART+8:69,s.q.UART+12:0x202c,s.q.UART+16:0,s.q.UART+20:0,0x40023808:4}
        def read(address,size):
            if address==0x08000000:return full if size==1048576 else full[:size]
            if address==0x1fffc000:return options
            return bytes(size)
        link=types.SimpleNamespace(open=lambda:None,u32=lambda a:uart.get(a,0),read=read,call=lambda *a:1,
            query_before_verified=False,byte_grant=s.q.ByteGrant(commands),native_UART_writes=0,sdk_calls=0,
            close_resume_enabled=False,close=Mock(),error=False,raw_failed=False,read_failed=False)
        bridge=types.SimpleNamespace(probe=lambda *a:None)
        with tempfile.TemporaryDirectory() as temp:
            out=Path(temp)/'out'
            with patch.object(s,'SyncLink',return_value=link),patch.object(s.g,'C_FULL',s.g.sha(full)), \
                 patch.object(s.q.site.ro.raw,'identity',return_value={}),patch.object(s.g,'load',return_value={}), \
                 patch.object(s.q.site.ro.old,'snapshot',return_value={}),patch.object(s.q.site.ro.old,'check_running'), \
                 patch.object(s.q,'DapBridge',return_value=bridge),patch.object(s.q.site.config,'NativeBus'), \
                 patch.object(s.q,'capture',side_effect=[b'\r\nOK\r\n',b'\r\n+SYSSTORE:1\r\n\r\nOK\r\n']) as capture, \
                 patch.object(s.t,'verify_exit'),patch.object(s.g.private,'protected'), \
                 patch.object(s.g,'save',side_effect=lambda p,v:Path(p).write_text(json.dumps(v))), \
                 patch.object(s.g,'write_private',side_effect=lambda p,b:Path(p).write_bytes(b)),contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(s.worker({}, {'C_identity':{'path':'SYNTHETIC'},'C_options':{'sha256':s.g.sha(options)}},commands,out),1)
            self.assertEqual(capture.call_count,2)
            self.assertEqual(json.loads((out/'receipt-private.json').read_text())['reason'],'SNTP_VOLATILE_NOT_VERIFIED')


if __name__=='__main__':unittest.main()
