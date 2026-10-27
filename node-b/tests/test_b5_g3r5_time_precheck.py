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
import b5_g3r5_time_precheck as p

NAMES=['ntp1.example.invalid','ntp2.example.invalid','ntp3.example.invalid']
MINIMUM=1792977536


class Tests(unittest.TestCase):
    def test_default_refuses_execution(self):
        with self.assertRaises(ValueError):p.validate({})

    def test_plan_has_one_enable_no_manual_NTP_or_time_setter(self):
        plan=p.plan(NAMES);self.assertEqual(len(plan),31)
        self.assertEqual(plan.count(b'AT+CIPSNTPCFG=1,0\r\n'),1)
        self.assertEqual(plan.count(b'AT+SYSTIMESTAMP?\r\n'),16)
        self.assertEqual(plan[-2:],(b'AT+CIPSNTPCFG=0\r\n',b'AT+CIPSNTPCFG?\r\n'))
        for forbidden in (b'CIPSTART',b'CIPSEND',b'SYSTIMESTAMP=',b'CWJAP=',b'SYSSTORE='):
            self.assertNotIn(forbidden,b''.join(plan))

    def test_DNS_command_injection_and_unbounded_list_rejected(self):
        for values in ([],NAMES*2,['bad\r\nAT'],['bad"name'],['x'*65]):
            with self.assertRaises(ValueError):p.plan(values)

    def test_cleanup_can_only_jump_to_off_not_enable(self):
        plan=p.plan(NAMES);grant=p.Grant(plan)
        for c in plan[:10]:grant.begin(c);grant.index=len(c)
        grant.cleanup();self.assertEqual(grant.commands,29)
        grant.begin(plan[-2]);grant.index=len(plan[-2]);grant.begin(plan[-1])
        with self.assertRaises(ValueError):grant.cleanup()

    def test_partial_UART_command_cannot_skip_to_cleanup(self):
        grant=p.Grant(p.plan(NAMES));grant.begin(b'AT+SYSSTORE?\r\n')
        with self.assertRaises(ValueError):grant.cleanup()

    def test_network_name_and_2_4_channel_are_checked(self):
        raw=b'+CWJAP:"TestSSID","00:00:00:00:00:00",7,-45\r\n'
        self.assertTrue(p.same_network(raw,'TestSSID'));self.assertFalse(p.same_network(raw,'OtherSSID'))
        self.assertFalse(p.same_network(raw.replace(b',7,',b',44,'),'TestSSID'))
        self.assertFalse(p.same_network(b'OK','TestSSID'))

    def test_time_parse_and_first_gate_do_not_use_host_time(self):
        self.assertEqual(p.epoch(b'+SYSTIMESTAMP:1792977536\r\nOK\r\n'),MINIMUM)
        self.assertIsNone(p.epoch(b'ERROR\r\n'))
        self.assertTrue(p.time_gate([MINIMUM,MINIMUM+1],MINIMUM,True,True))
        for values,on,cfg in (([1,2],True,True),([MINIMUM]*2,True,True),([MINIMUM,MINIMUM+1],False,True),([MINIMUM,MINIMUM+1],True,False)):
            self.assertFalse(p.time_gate(values,MINIMUM,on,cfg))

    def run_worker(self,enable_ok=True,valid_time=True):
        plan=p.plan(NAMES);calls=[]
        fake=types.SimpleNamespace(open=lambda:None,u32=lambda a:{p.q.UART+8:1,p.q.UART+12:0x202c}.get(a,0),
            call=lambda *a:1,query_before_verified=False,error=False,native_UART_writes=0,sdk_calls=0,
            close_resume_enabled=False,close=lambda:None)
        fake.set_close_resume=lambda v:setattr(fake,'close_resume_enabled',v)
        network=b'+CWJAP:"TestSSID","00:00:00:00:00:00",7,-45\r\nOK\r\n'
        pre=[b'+SYSSTORE:0\r\nOK\r\n',network,b'+CIPSTA:ip:"192.0.2.2"\r\nOK\r\n',b'+CIPMODE:0\r\nOK\r\n',b'+CIPMUX:0\r\nOK\r\n',b'+CIPRECVMODE:0\r\nOK\r\n',b'STATUS:2\r\nOK\r\n',b'+CIPSNTPCFG:0\r\nOK\r\n',b'+SYSTIMESTAMP:1\r\nOK\r\n']
        def exchange(link,bridge,command,out,index,**kwargs):
            calls.append(index);link.byte_grant.begin(command);link.byte_grant.index=len(command)
            if index<9:raw=pre[index]
            elif index==9:raw=b'\r\nOK\r\n' if enable_ok else b'\r\nERROR\r\n'
            elif index==10:raw=b'+CIPSNTPCFG:1,0,"'+b'","'.join(n.encode() for n in NAMES)+b'"\r\nOK\r\n'
            elif 11<=index<26:raw=b'+SYSTIMESTAMP:'+str((MINIMUM if valid_time else 100)+index).encode()+b'\r\nOK\r\n'
            elif index<29:raw=b'+CIPDOMAIN:"192.0.2.10"\r\nOK\r\n'
            elif index==29:raw=b'\r\nOK\r\n'
            else:raw=b'+CIPSNTPCFG:0\r\nOK\r\n'
            return raw,(),0
        route={k:True for k in ('PB10_PB11_AF7','GPIOB_clock_enabled','USART3_clock_enabled','USART3_IRQ_enabled','uptime_advances')}
        with tempfile.TemporaryDirectory() as folder:
            out=Path(folder)/'run'
            with patch.object(p.u,'UdpLink',return_value=fake),patch.object(p.u,'runtime'),patch.object(p.q,'rx_route_snapshot',return_value=route),patch.object(p.q,'baud_from_registers',return_value=115200),patch.object(p.q.site.config,'NativeBus'),patch.object(p.u,'UartBridge'),patch.object(p.u,'exchange',side_effect=exchange),patch.object(p.time,'sleep'),patch.object(p.g.private,'protected'),patch.object(p.g,'save',side_effect=lambda f,v:Path(f).write_text(json.dumps(v))),contextlib.redirect_stdout(io.StringIO()):
                code=p.worker({'dns_names':NAMES,'minimum_epoch':MINIMUM},plan,'TestSSID',out)
            result=json.loads((out/'receipt-private.json').read_text())
        return code,result,calls

    def test_enabled_observation_cleans_up_once_and_passes_only_first_gate(self):
        code,result,calls=self.run_worker();self.assertEqual(code,0);self.assertEqual(calls,list(range(31)))
        self.assertEqual(result['SNTP_enable_attempts'],1);self.assertEqual(result['SNTP_disable_attempts'],1)
        self.assertTrue(result['SNTP_stop_verified']);self.assertEqual(result['manual_UDP_payloads'],0)
        self.assertIn('NOT_RUN',result['public_fresh_UDP_sample'])

    def test_enable_ERROR_skips_time_and_DNS_but_disables_once(self):
        code,result,calls=self.run_worker(enable_ok=False);self.assertEqual(code,1)
        self.assertEqual(calls,list(range(10))+[29,30]);self.assertTrue(result['SNTP_stop_verified'])

    def test_low_time_is_BLOCKED_even_with_OK_and_DNS(self):
        code,result,calls=self.run_worker(valid_time=False)
        self.assertEqual(code,2);self.assertEqual(result['status'],'TIME_PRECHECK_BLOCKED');self.assertTrue(result['SNTP_stop_verified'])

    def test_ROM_prevents_any_UART_or_enable(self):
        with tempfile.TemporaryDirectory() as folder:
            fake=types.SimpleNamespace(open=lambda:None,u32=lambda a:0,query_before_verified=False,native_UART_writes=0,sdk_calls=0,close_resume_enabled=False,close=lambda:None)
            out=Path(folder)/'run'
            with patch.object(p.u,'UdpLink',return_value=fake),patch.object(p.u,'runtime',side_effect=ValueError('UDP_ROM_STOP')),patch.object(p.g.private,'protected'),patch.object(p.g,'save',side_effect=lambda f,v:Path(f).write_text(json.dumps(v))),contextlib.redirect_stdout(io.StringIO()):
                code=p.worker({},p.plan(NAMES),'TestSSID',out)
            receipt=json.loads((out/'receipt-private.json').read_text())
            self.assertEqual(code,1);self.assertEqual(receipt['SNTP_enable_attempts'],0);self.assertEqual(receipt['UART_native_attempts'],0)


    def test_API_reserve_stops_before_native_read_latch(self):
        link=types.SimpleNamespace(sdk_limit=12000,sdk_calls=9000,byte_grant=types.SimpleNamespace(cleanup_started=False),read_failed=False)
        with patch.object(p.u,'exchange') as native:
            with self.assertRaisesRegex(ValueError,'P0A_API_CLEANUP_RESERVE'):p.exchange(link,None,b'',Path('.'),0)
        native.assert_not_called();self.assertFalse(link.read_failed)

    def test_cleanup_may_use_reserved_budget_but_not_change_commands(self):
        link=types.SimpleNamespace(sdk_limit=12000,sdk_calls=9000,byte_grant=types.SimpleNamespace(cleanup_started=True))
        with patch.object(p.u,'exchange',return_value=('ok',(),0)) as native:
            self.assertEqual(p.exchange(link,None,b'AT+CIPSNTPCFG=0\r\n',Path('.'),29)[0],'ok')
        native.assert_called_once()

    def test_finalize_has_zero_enable_and_only_remaining_work(self):
        commands=p.finalize_plan(NAMES)
        self.assertEqual(len(commands),11);self.assertNotIn(b'CIPSNTPCFG=1',b''.join(commands))
        self.assertEqual(commands.count(b'AT+CIPSNTPCFG=0\r\n'),1)
        self.assertEqual(commands.count(b'AT+SYSTIMESTAMP?\r\n'),2)
        self.assertNotIn(b'CIPSTART',b''.join(commands));self.assertNotIn(b'CIPSEND',b''.join(commands))
        grant=p.Grant(commands);grant.cleanup_index=len(commands)-3
        for command in commands[:5]:grant.begin(command);grant.index=len(command)
        grant.cleanup();self.assertEqual(grant.commands,8);grant.begin(commands[8])


if __name__=='__main__':unittest.main()
