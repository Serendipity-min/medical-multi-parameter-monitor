"""实际Python包装器+假DLL回归；不实例化DLL、不访问硬件或网络。"""
import contextlib
import ctypes as C
import io
import json
from pathlib import Path
import struct
import subprocess
import time
import sys
import tempfile
import types
import unittest
from unittest.mock import Mock, patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import b5_esp_gmr as q
import b5_esp_udp_ntp as u
import b5_g3r5_time_precheck as p
from b5_esp_budget import *


def link_fake():
    link=object.__new__(u.UdpLink)
    link.sdk_calls=0;link.sdk_limit=6000;link.verified_running_flash=True
    link.error=False;link.query_before_verified=True;link.opened=True
    link.close_resume_enabled=False;link.native_UART_writes=0
    link.byte_grant=q.ByteGrant((b'AT\r\n',));link.BYTE_COMMANDS=(b'AT\r\n',)
    link.memory_counts={};link.dap_select=0;link.dap_csw=2;link.dap_tar=q.DR
    link.raw_target_grant=None;link.gate=Mock()
    link.io=io.StringIO();link.events=io.StringIO();link.log=io.BytesIO();link.directory=Mock()
    values={0xe000edf0:0x10001,0xe000ed08:0x08000000,0xe000101c:0x08000101}
    def read(address,size,buffer,zone):
        C.memmove(buffer,values.get(address,0).to_bytes(size,'little'),size)
        return size
    link.dll=types.SimpleNamespace(JLINKARM_ReadMemEx=Mock(side_effect=read),
        JLINKARM_ExecCommand=Mock(return_value=0),JLINKARM_Close=Mock(),
        JLINKARM_CORESIGHT_WriteAPDPReg=Mock(return_value=0),
        JLINKARM_CORESIGHT_ReadAPDPReg=Mock(return_value=0))
    return link,values


class NativeTests(unittest.TestCase):
    def test_5998_read_5999_refusal_reserves_call_6000_for_close(self):
        link,_=link_fake();link.sdk_calls=5998
        self.assertEqual(link.u32(q.UART),0);self.assertEqual(link.sdk_calls,5999)
        for count in (5999,6000):
            link.sdk_calls=count
            with self.assertRaises(HostBudgetExhausted):link.u32(q.UART)
            self.assertFalse(getattr(link,'read_failed',False));self.assertTrue(link.verified_running_flash)
        self.assertEqual(link.dll.JLINKARM_ReadMemEx.call_count,1)

    def test_raw_budget_refusal_does_not_poison_native_bus(self):
        link,_=link_fake();link.sdk_calls=5999
        with self.assertRaises(HostBudgetExhausted):link.call('JLINKARM_CORESIGHT_WriteAPDPReg',2,0,0)
        self.assertFalse(getattr(link,'raw_failed',False));link.dll.JLINKARM_CORESIGHT_WriteAPDPReg.assert_not_called()

    def test_scope_refusal_and_preflight_do_not_poison(self):
        link,_=link_fake()
        with self.assertRaises(ValueError):link.read(0x08000000,1048576)
        self.assertTrue(link.verified_running_flash);self.assertFalse(getattr(link,'read_failed',False))
        link.dll.JLINKARM_ReadMemEx.assert_not_called()

    def test_negative_and_positive_short_read_latch_actual_native_failure(self):
        for returned in (-1,2):
            link,_=link_fake();link.dll.JLINKARM_ReadMemEx=Mock(return_value=returned)
            with self.assertRaises(NativeReadFailed):link.u32(q.UART)
            self.assertTrue(link.read_failed);self.assertFalse(link.verified_running_flash)
            with self.assertRaises(ValueError):link.u32(q.UART)
            self.assertEqual(link.dll.JLINKARM_ReadMemEx.call_count,1)

    def test_native_exception_and_deadline_are_uncertain_not_short_read(self):
        link,_=link_fake();link.dll.JLINKARM_ReadMemEx=Mock(side_effect=OSError())
        with self.assertRaises(NativeCallUncertain):link.u32(q.UART)
        self.assertTrue(link.native_uncertain);self.assertFalse(getattr(link,'read_failed',False))
        link,_=link_fake()
        with patch.object(q.time,'monotonic',side_effect=[0,0,6,6]):
            with self.assertRaises(NativeCallUncertain):link.u32(q.UART)
        self.assertTrue(link.native_uncertain)

    def test_native_callback_stops_cleanup(self):
        link,_=link_fake()
        def read(*args):link.error=True;return 4
        link.dll.JLINKARM_ReadMemEx=Mock(side_effect=read)
        with self.assertRaises(NativeCallUncertain):link.u32(q.UART)
        self.assertFalse(p.healthy(link))

    def test_successful_close_is_freshly_verified_and_counted_but_post_state_unknown(self):
        link,_=link_fake();link.set_close_resume(True)
        self.assertFalse(link.close_resume_enabled)
        r={};p.close_receipt(link,r)
        self.assertEqual(link.sdk_calls,9);self.assertTrue(r['Close_completed'])
        self.assertTrue(r['close_resume']);self.assertIn('UNKNOWN',r['post_close_target_state'])
        self.assertEqual(link.dll.JLINKARM_ExecCommand.call_count,1);link.dll.JLINKARM_Close.assert_called_once()

    def test_implicit_halt_between_worker_check_and_close_cannot_enable_resume(self):
        link,values=link_fake();values[0xe000edf0]=0x30003
        link.set_close_resume(True)
        with self.assertRaisesRegex(ValueError,'TARGET_STATE_STOP'):link.close()
        link.dll.JLINKARM_ExecCommand.assert_not_called();link.dll.JLINKARM_Close.assert_called_once()

    def test_close_error_timeout_and_callback_never_claim_success(self):
        for mode in ('exception','timeout','callback'):
            link,_=link_fake()
            if mode=='exception':link.dll.JLINKARM_Close.side_effect=OSError()
            if mode=='callback':link.dll.JLINKARM_Close.side_effect=lambda:setattr(link,'error',True)
            if mode=='timeout':
                with patch.object(q.time,'monotonic',side_effect=[0,6,6]):
                    with self.assertRaises(NativeCallUncertain):link.close()
            else:
                with self.assertRaises(NativeCallUncertain):link.close()
            self.assertFalse(link.close_completed)
            self.assertTrue(link.native_uncertain);link.dll.JLINKARM_Close.assert_called_once()

    def test_real_halt_rom_fault_and_vector_gate_stop_before_UART(self):
        for kind in ('HALT','ROM','FAULT','VECTOR'):
            link,values=link_fake()
            if kind=='HALT':values[0xe000edf0]=0x30003
            elif kind=='ROM':values.update({0xe000ed08:0x1fff0000,0xe000101c:0x1fff32f0})
            elif kind=='FAULT':values[0xe000ed28]=1
            else:values[0xe000ed08]=0x08010000
            with tempfile.TemporaryDirectory() as tmp,patch.object(u.g,'save'):
                with self.assertRaises(ValueError):u.runtime(link,Path(tmp),'entry')
            self.assertFalse(link.verified_running_flash);self.assertEqual(link.native_UART_writes,0)
            self.assertFalse(link.close_resume_enabled)

    def test_flash_identity_mismatch_at_existing_full_gate_prevents_commands(self):
        fake=types.SimpleNamespace(open=lambda:None,u32=lambda a:0,read=Mock(return_value=b'wrong image'),
            query_before_verified=False,error=False,native_UART_writes=0,sdk_calls=0,
            byte_grant=types.SimpleNamespace(history=[]),close=Mock())
        with tempfile.TemporaryDirectory() as tmp,patch.object(q,'QueryLink',return_value=fake), \
            patch.object(q.site.ro.raw,'identity',return_value={}),patch.object(q.g,'load',return_value={}), \
            patch.object(q.site.ro.old,'snapshot',return_value={}),patch.object(q.site.ro.old,'check_running'), \
            patch.object(q.g.private,'protected'),patch.object(q.g,'save',side_effect=lambda path,obj:Path(path).write_text(json.dumps(obj))), \
            patch.object(q.g,'write_private'),patch.object(q,'capture') as capture,contextlib.redirect_stdout(io.StringIO()):
            out=Path(tmp)/'run';code=q.worker({}, {'C_identity':{'path':'SYNTHETIC'},'C_options':{'sha256':'WRONG'}},out)
            self.assertEqual(code,1);capture.assert_not_called()
            self.assertEqual(fake.native_UART_writes,0);self.assertFalse(fake.query_before_verified)


class BudgetTests(unittest.TestCase):
    def setup_link(self,calls=0):
        link,_=link_fake();link.sdk_calls=calls;link.sdk_limit=6000
        commands=p.plan(['ntp.example.invalid']);link.BYTE_COMMANDS=commands;link.byte_grant=p.Grant(commands)
        return link,commands

    def test_whole_command_denied_before_baseline_or_grant(self):
        link,commands=self.setup_link(5900)
        with self.assertRaises(HostBudgetExhausted):p.exchange(link,None,commands[0],Path('.'),0)
        self.assertEqual(link.byte_grant.commands,0);link.dll.JLINKARM_ReadMemEx.assert_not_called()
        self.assertTrue(link.verified_running_flash)

    def test_enable_budget_refusal_keeps_cleanup_available(self):
        link,commands=self.setup_link();budget=CommandBudget(link,commands[-2:])
        link.sdk_calls=6000-budget.cleanup_reserve
        with self.assertRaises(HostBudgetExhausted):budget.admit(commands[9],3)
        link.sdk_calls+=FAILURE_SNAPSHOT_CALLS
        budget.admit(commands[-2],3,True)
        self.assertFalse(getattr(link,'read_failed',False))

    def test_already_active_SNTP_without_cleanup_capacity_is_not_blindly_written(self):
        link,commands=self.setup_link(5950);link.byte_grant.cleanup()
        with self.assertRaises(HostBudgetExhausted):p.exchange(link,None,commands[-2],Path('.'),len(commands)-2)
        link.dll.JLINKARM_ReadMemEx.assert_not_called();self.assertEqual(link.native_UART_writes,0)
        result=p.supervisor_summary(None,1,{'SNTP_stop_verified':False})
        self.assertTrue(result['physical_power_off_required'])

    def test_per_byte_admission_protects_entire_remaining_command(self):
        link,commands=self.setup_link();budget=CommandBudget(link,commands[-2:])
        budget.admit(commands[0],3);link.sdk_calls=5999
        with self.assertRaises(HostBudgetExhausted):budget.byte(len(commands[0]),response_polls(3))
        self.assertEqual(link.native_UART_writes,0)

    def test_actual_memap_byte_uses_twelve_calls_including_restore(self):
        link,_=self.setup_link();link.byte_grant=q.ByteGrant((b'A',));link.BYTE_COMMANDS=(b'A',)
        link.byte_grant.begin(b'A')
        bridge=q.DapBridge(q.site.config.NativeBus(link));bridge.proven=True;bridge.guard=link.byte_grant.check
        bridge.write32(q.DR,65)
        self.assertEqual(link.sdk_calls,DAP_BYTE_CALLS);self.assertTrue(bridge.state_restored)
        self.assertEqual(link.native_UART_writes,1)

    def test_full_AT_CRLF_and_maximum_polls_stay_within_model(self):
        link,commands=self.setup_link();command=commands[0];seen=[]
        class Bridge:
            def write32(self,address,value):
                link.byte_grant.check(address,value);link.sdk_calls+=DAP_BYTE_CALLS;seen.append(value)
        polls=0
        def read(address,size):link.sdk_calls+=1;return bytes(size)
        def tx(address):
            nonlocal polls
            polls+=1;link.sdk_calls+=1;return (1<<7) if polls%TX_POLLS==0 else 0
        def receive(*args):link.sdk_calls+=3;return b''
        link.read=read;link.u32=tx
        with tempfile.TemporaryDirectory() as tmp,patch.object(u,'ring_since',side_effect=receive),patch.object(u.time,'sleep'),patch.object(u.g,'save'),patch.object(u.g,'write_private'):
            with self.assertRaisesRegex(ValueError,'NO_EXPECTED_TERMINAL'):
                p.exchange(link,Bridge(),command,Path(tmp),0,timeout=.04)
        self.assertEqual(bytes(seen),command);self.assertTrue(bytes(seen).endswith(b'\r\n'))
        self.assertEqual(link.sdk_calls,command_calls(command,.04))

    def test_half_command_not_followed_by_random_cleanup(self):
        link,commands=self.setup_link();link.byte_grant.begin(commands[0]);link.byte_grant.index=2
        with self.assertRaises(ValueError):link.byte_grant.cleanup()
        self.assertEqual(link.native_UART_writes,0)

    def test_supervisor_kill_overrides_stale_success_receipt(self):
        result=p.supervisor_summary('P0A_NATIVE_DEADLINE',-9,{'SNTP_stop_verified':True})
        self.assertEqual(result['exit_code'],1);self.assertFalse(result['SNTP_stop_verified'])
        self.assertTrue(result['physical_power_off_required']);self.assertEqual(result['target_state'],'UNKNOWN')

    def test_close_failure_with_verified_SNTP_off_still_requires_target_stop(self):
        result=p.supervisor_summary(None,1,{'SNTP_stop_verified':True,'SDK_close_error':True})
        self.assertTrue(result['SNTP_stop_verified']);self.assertTrue(result['physical_power_off_required'])
        self.assertEqual(result['target_state'],'UNKNOWN')

    def test_real_offline_child_is_killed_on_active_native_deadline(self):
        with tempfile.TemporaryDirectory() as tmp:
            out=Path(tmp)
            (out/'heartbeat-events.jsonl').write_text(json.dumps({'operation':'FAKE_BLOCKED_DLL','active':True,'deadline_monotonic':time.monotonic()-1})+'\n')
            child=subprocess.Popen([sys.executable,'-c','import time;time.sleep(30)'])
            reason=p.supervise(child,out,2,time.monotonic())
            self.assertEqual(reason,'P0A_NATIVE_DEADLINE');self.assertIsNotNone(child.returncode)
            self.assertNotEqual(child.returncode,0)
            self.assertTrue(p.supervisor_summary(reason,child.returncode,{})['physical_power_off_required'])


if __name__=='__main__':unittest.main()
