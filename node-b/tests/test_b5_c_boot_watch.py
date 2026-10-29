"""启动监控的危险动作拒绝、实际状态分支、预算和人工事件窗口。"""
import io
import json
from pathlib import Path
import sys
import tempfile
import time
from types import SimpleNamespace
import unittest
from unittest.mock import patch,MagicMock

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import b5_c_boot_watch as m


class Clock:
    now=0
    def __init__(self):self.now=0;self.on_sleep=lambda:None
    def read(self):return self.now
    def sleep(self,seconds):self.now+=seconds;self.on_sleep()


class Tests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(dir=m.g.ROOT/'node-b/build');self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name);self.folder=self.root/'attach';self.folder.mkdir()
        self.clock=Clock();self.link=self.make_link();self.clock.on_sleep=self.owner_intent
        self.invite=True
    def make_link(self):
        link=object.__new__(m.WatchLink);link.sdk_calls=0;link.started=0;link.io=io.StringIO()
        link.error=False;link.native_read_failed=False;link.register_reads_allowed=False;link.verified_running_flash=False
        link.expected_vectors=b'V'*64;link.native_calls=0
        return link
    def owner_intent(self):
        p=self.root/'RESET_INTENT.json'
        if self.invite and (self.root/'RESET_READY.json').exists() and not p.exists():
            p.write_text(json.dumps(dict(action='OWNER_C_RESET_ONCE',monotonic=self.clock.now)))
    def frame(self,at,reset=False):
        uptime=int(at*1000)+10000
        if reset and at>=7:uptime=int((at-7)*1000)
        return dict(DHCSR=0,VTOR=0x08000000,DWT_PCSR=0x08000200,uptime=uptime,flags=0,
                    CFSR=0,HFSR=0,DFSR=0,DEMCR=0,RCC_CSR=0,RCC_APB2ENR=0,SYSCFG_MEMRMP=0,GPIOB_IDR=0)
    def run_watch(self,frames,stage=1,alias=True):
        def sample(link,slow):link.sdk_calls+=13 if slow else 5;return frames(self.clock.now)
        def save(path,value):path.write_text(json.dumps(value))
        with patch.object(m,'sample',side_effect=sample),patch.object(m.g,'save',side_effect=save):
            return m.watch(self.link,self.folder,self.root,stage,alias,self.clock.read,self.clock.sleep)

    def test_default_never_opens_device(self):
        with patch.object(sys,'argv',['watch']),patch('sys.stdout',io.StringIO()),patch.object(m,'WatchLink') as native:
            self.assertEqual(m.main(),0);native.assert_not_called()

    def test_action_and_core_reads_denied(self):
        for name in ('JLINKARM_Halt','JLINKARM_Reset','JLINKARM_Go','JLINKARM_WriteMem','JLINKARM_WriteReg',
                     'JLINKARM_BeginDownload','JLINKARM_ReadReg'):
            with self.subTest(name=name),patch.object(m.raw.Link,'call') as native:
                with self.assertRaises(ValueError):self.link.call(name)
                native.assert_not_called()

    def test_ranges_exclude_UART_data_full_image_and_RAM_dump(self):
        for address,size in ((0x40004804,4),(0x08000000,1048576),(0x20000000,131072),(0x20012010,4)):
            with self.subTest(address=address),patch.object(m.raw.Link,'call') as native:
                with self.assertRaisesRegex(ValueError,'READ_DENIED'):self.link.read(address,size)
                native.assert_not_called()

    def test_unsupported_optional_log_policies_are_not_reintroduced(self):
        self.link.started=time.monotonic()
        for cmd in ('EnableRemarks','EnableMOEHandling'):
            with patch.object(m.raw.Link,'call') as native:
                with self.assertRaisesRegex(ValueError,'POLICY_DENIED'):
                    self.link.call('JLINKARM_ExecCommand',cmd.encode(),None,0)
                native.assert_not_called()

    def test_host_budget_is_not_native_read_failed(self):
        self.link.sdk_calls=m.SDK_LIMIT
        with patch.object(m.raw.Link,'call') as native:
            with self.assertRaisesRegex(ValueError,'HOST_SDK_BUDGET'):self.link.read(0xe000ed08,4)
            native.assert_not_called()
        self.assertFalse(self.link.native_read_failed);self.assertFalse(self.link.error)

    def test_native_negative_and_short_remain_distinct(self):
        for count,label in ((-1,'NEGATIVE'),(3,'SHORT')):
            link=self.make_link()
            with patch.object(link,'call',return_value=count):
                with self.assertRaisesRegex(ValueError,'NATIVE_'+label):link.read(0xe000ed08,4)
            self.assertTrue(link.native_read_failed)

    def test_callback_error_does_not_hide_native_short_return(self):
        self.link.started=time.monotonic();self.link.out=self.folder;self.link.events=io.StringIO()
        def native(*args):self.link.error=True;return 3
        self.link.dll=SimpleNamespace(JLINKARM_ReadMemEx=native)
        with self.assertRaisesRegex(RuntimeError,'SDK_ERROR'):self.link.read(0xe000ed08,4)
        rows=[json.loads(x) for x in self.link.io.getvalue().splitlines()]
        self.assertEqual(rows[-1]['data']['native_return'],3)
        self.assertTrue(rows[-1]['data']['SDK_error_latched']);self.assertTrue(self.link.native_read_failed)
        self.assertEqual(self.link.native_calls,1)

    def test_native_timeout_keeps_return_and_is_not_budget_refusal(self):
        tick=[1000.0];self.link.started=tick[0];self.link.out=self.folder;self.link.events=io.StringIO()
        def native(*args):tick[0]+=.01;return 4
        self.link.dll=SimpleNamespace(JLINKARM_ReadMemEx=native)
        with patch.object(m.time,'monotonic',side_effect=lambda:tick[0]):
            with self.assertRaisesRegex(ValueError,'NATIVE_CALL_TIMEOUT'):
                self.link.call('JLINKARM_ReadMemEx',0xe000ed08,4,None,0,timeout=.001)
        self.assertFalse(self.link.native_read_failed);self.assertEqual(self.link.native_calls,1)
        self.assertIn('"native_return": 4',self.link.io.getvalue())

    def test_authorization_limits_are_not_expandable(self):
        a=dict(enabled=True,owner_approved=True,scope=m.SCOPE,tools_sha256=m.bindings(),DLL_sha256=m.raw.DLL_SHA,
               session_timeout_s=170,connections_max=2,connection_s=75,manual_RESET_max=1,
               explicit_halt_reset_go_UART_NVM_writes=0,healthy_flash_close_resume_allowed=True,
               retries=0,expires_unix=time.time()+100,output=str(self.root/'out'))
        for changes in ({'connections_max':3},{'manual_RESET_max':2},{'explicit_halt_reset_go_UART_NVM_writes':1},
                        {'owner_approved':False},{'healthy_flash_close_resume_allowed':False},{'connection_slots_remaining':3}):
            with self.subTest(changes=changes),patch.object(m.recovery,'read') as read:
                with self.assertRaises(ValueError):m.authorize(dict(a,**changes),self.root/'out')
                read.assert_not_called()

    def test_budget_covers_sampling_core_and_close(self):
        self.assertLessEqual(5*m.MAX_SAMPLES+8*61+64+320+64,m.SDK_LIMIT)
        self.link.sdk_calls=m.SDK_LIMIT-m.CLOSE_RESERVE
        with patch.object(m,'sample') as sample:
            result=self.run_watch(lambda t:self.frame(t));self.assertEqual(result['status'],'HOST_BUDGET_REFUSAL')
            self.assertEqual(result['samples'],0)

    def test_healthy_reset_captured_without_chat_ack(self):
        result=self.run_watch(lambda t:self.frame(t,reset=True))
        self.assertEqual(result['status'],'NORMAL_FLASH_RESET_OBSERVED_MONITOR_COMPLETE')
        self.assertEqual(result['reset_event'],'APPLICATION_UPTIME_DECREASE_NOT_WRAP')
        self.assertGreaterEqual(self.clock.now,22);self.assertLess(self.clock.now,30)
        self.assertTrue((self.root/'RESET_OBSERVED.json').exists())

    def test_native_popup_only_after_health_and_once(self):
        self.invite=False;self.link.native_popup_allowed=True
        def launch(root,now):
            (root/'RESET_INTENT.json').write_text(json.dumps(dict(action='OWNER_C_RESET_ONCE',monotonic=now,lease_s=15)))
        with patch.object(m,'launch_popup',side_effect=launch) as launched:
            result=self.run_watch(lambda t:self.frame(t,reset=True))
        launched.assert_called_once();self.assertEqual(result['status'],'NORMAL_FLASH_RESET_OBSERVED_MONITOR_COMPLETE')

    def test_native_popup_short_lease_is_not_chat_budget(self):
        self.invite=False;self.link.native_popup_allowed=True
        def launch(root,now):
            (root/'RESET_INTENT.json').write_text(json.dumps(dict(action='OWNER_C_RESET_ONCE',monotonic=now,lease_s=15)))
        with patch.object(m,'launch_popup',side_effect=launch):result=self.run_watch(lambda t:self.frame(t))
        self.assertEqual(result['status'],'RESET_INVITATION_EXPIRED_NO_CONFIRMED_EVENT');self.assertLess(self.clock.now,21)

    def test_popup_cancellation_is_host_stop(self):
        (self.root/'RESET_CANCELLED.json').write_text('{}')
        result=self.run_watch(lambda t:self.frame(t));self.assertEqual(result['status'],'OWNER_CANCELLED_RESET')
        self.assertEqual(result['samples'],0)

    def test_native_popup_not_invited_in_ROM(self):
        self.link.native_popup_allowed=True
        with patch.object(m,'launch_popup') as launched:
            result=self.run_watch(lambda t:dict(self.frame(t),VTOR=0x1fff0000))
        launched.assert_not_called();self.assertEqual(result['status'],'ROM_OBSERVED')

    def test_expected_reset_zero_vector_transient_then_flash(self):
        def frame(t):
            f=self.frame(t,reset=True)
            if 7<=t<7.3:f.update(DHCSR=m.raw.RESET,VTOR=0,DWT_PCSR=0,uptime=0)
            return f
        self.link.read=MagicMock(return_value=b'V'*64)
        result=self.run_watch(frame)
        self.assertEqual(result['status'],'NORMAL_FLASH_RESET_OBSERVED_MONITOR_COMPLETE')
        self.assertTrue((self.folder/'reset-transitions-private.jsonl').exists())

    def test_reset_transition_still_stops_on_rom(self):
        def frame(t):
            f=self.frame(t,reset=True)
            if 7<=t<7.3:f.update(DHCSR=m.raw.RESET,VTOR=0,DWT_PCSR=0,uptime=0)
            elif t>=7.3:f.update(VTOR=0x1fff0000,DWT_PCSR=0x1fff369e)
            return f
        self.link.read=MagicMock(return_value=b'V'*64)
        result=self.run_watch(frame);self.assertEqual(result['status'],'ROM_OBSERVED')
        self.assertLess(self.clock.now,8)

    def test_reset_zero_vector_observation_never_exceeds_two_seconds(self):
        def frame(t):
            f=self.frame(t,reset=True)
            if t>=7:f.update(DHCSR=m.raw.RESET,VTOR=0,DWT_PCSR=0,uptime=0)
            return f
        self.link.read=MagicMock(return_value=b'V'*64)
        result=self.run_watch(frame);self.assertEqual(result['status'],'UNKNOWN_OBSERVED')
        self.assertLess(self.clock.now,9.2)

    def test_late_manual_action_not_accepted(self):
        result=self.run_watch(lambda t:self.frame(t))
        self.assertEqual(result['status'],'RESET_INVITATION_EXPIRED_NO_CONFIRMED_EVENT')
        self.assertFalse((self.root/'RESET_OBSERVED.json').exists())

    def test_ROM_on_attach_stops_before_invitation(self):
        result=self.run_watch(lambda t:dict(self.frame(t),VTOR=0x1fff0000,DWT_PCSR=0x1fff369e))
        self.assertEqual(result['status'],'ROM_OBSERVED');self.assertEqual(result['last_kind'],'ROM')
        self.assertEqual(result['samples'],1);self.assertFalse((self.root/'RESET_READY.json').exists())

    def test_HALT_reads_real_core_once_does_not_treat_PCSR_as_PC(self):
        with patch.object(m.runtime,'core_if_halted',return_value={'registers':{'R15':0x1fff369e}}) as core:
            result=self.run_watch(lambda t:dict(self.frame(t),DHCSR=m.raw.HALT,DWT_PCSR=0xffffffff))
            core.assert_called_once();self.assertEqual(result['status'],'HALT_OBSERVED')
            self.assertTrue((self.folder/'already-halted-core-private.json').exists())

    def test_reset_before_invitation_not_claimed_owner_action(self):
        result=self.run_watch(lambda t:dict(self.frame(t),uptime=0 if t>=1 else int(t*1000)+10000))
        self.assertEqual(result['status'],'RESET_OBSERVED_OUTSIDE_OWNER_INVITATION')
        self.assertFalse((self.root/'RESET_OBSERVED.json').exists())

    def test_zero_clock_never_invites_reset(self):
        result=self.run_watch(lambda t:dict(self.frame(t),uptime=0))
        self.assertEqual(result['status'],'FLASH_CLOCK_NOT_ADVANCING')
        self.assertFalse((self.root/'RESET_READY.json').exists())

    def test_wrap_is_not_reset_and_reconnect_has_no_manual_invitation(self):
        result=self.run_watch(lambda t:dict(self.frame(t),uptime=(0xfffffff0+int(t*1000))&0xffffffff),stage=2)
        self.assertEqual(result['status'],'NORMAL_FLASH_REATTACH_MONITOR_COMPLETE')
        self.assertFalse((self.root/'RESET_READY.json').exists())

    def test_alias_is_required_to_accept_VTOR_zero(self):
        s=dict(self.frame(0),VTOR=0)
        self.assertEqual(m.kind(s,True),'FLASH');self.assertEqual(m.kind(s,False),'UNKNOWN')

    def test_explicit_flash_VTOR_does_not_require_reset_alias_zero(self):
        self.assertEqual(m.kind(self.frame(0),False),'FLASH')

    def test_reset_alias_temporarily_zero_then_explicit_flash(self):
        def frame(t):
            f=self.frame(t,reset=True)
            if 7<=t<7.2:f.update(DHCSR=m.raw.RESET,VTOR=0,DWT_PCSR=0,uptime=0)
            elif 7.2<=t<7.4:f.update(DHCSR=m.raw.RESET)
            return f
        self.link.read=MagicMock(return_value=b'\0'*64)
        result=self.run_watch(frame)
        self.assertEqual(result['status'],'NORMAL_FLASH_RESET_OBSERVED_MONITOR_COMPLETE')

    def test_alias_after_reset_must_not_reuse_before_reset_proof(self):
        self.link.read=MagicMock(return_value=b'R'*64)
        result=self.run_watch(lambda t:dict(self.frame(t),VTOR=0),stage=2,alias=True)
        self.assertEqual(result['status'],'UNKNOWN_OBSERVED');self.link.read.assert_called_once_with(0,64)

    def test_stable_VTOR_zero_alias_read_is_not_repeated_every_sample(self):
        self.link.read=MagicMock(return_value=b'V'*64)
        result=self.run_watch(lambda t:dict(self.frame(t),VTOR=0),stage=2,alias=True)
        self.assertEqual(result['status'],'NORMAL_FLASH_REATTACH_MONITOR_COMPLETE')
        self.link.read.assert_called_once_with(0,64)

    def test_second_connection_only_after_healthy_first(self):
        for index,(first,count) in enumerate(((dict(status='ROM_OBSERVED',Close_completed=True,close_resume=False),1),
                            (dict(status='NORMAL_FLASH_RESET_OBSERVED_MONITOR_COMPLETE',Close_completed=True,close_resume=False),1),
                            (dict(status='NORMAL_FLASH_RESET_OBSERVED_MONITOR_COMPLETE',Close_completed=True,close_resume=True),2))):
            out=self.root/('worker-'+str(index))
            with patch.object(m.recovery,'protected'),patch.object(m,'capture',return_value=first) as capture, \
                 patch.object(m.time,'sleep'),patch.object(m.g,'save'):
                self.assertEqual(m.worker({},out),0);self.assertEqual(capture.call_count,count)

    def test_one_remaining_slot_does_not_start_reconnect(self):
        first=dict(status='NORMAL_FLASH_RESET_OBSERVED_MONITOR_COMPLETE',Close_completed=True,close_resume=True)
        with patch.object(m.recovery,'protected'),patch.object(m,'capture',return_value=first) as capture, \
             patch.object(m.time,'sleep'),patch.object(m.g,'save'):
            self.assertEqual(m.worker({'connection_slots_remaining':1},self.root/'remaining-one'),0)
            self.assertEqual(capture.call_count,1)

    def test_observation_pair_has_no_second_reset_invitation(self):
        first=dict(status='NORMAL_FLASH_REATTACH_MONITOR_COMPLETE',Close_completed=True,close_resume=True)
        with patch.object(m.recovery,'protected'),patch.object(m,'capture',return_value=first) as capture, \
             patch.object(m.time,'sleep'),patch.object(m.g,'save'):
            self.assertEqual(m.worker({'observation_only':True},self.root/'observe-pair'),0)
            self.assertEqual(capture.call_count,2)

    def capture_fixture(self,status,final):
        fake=MagicMock();fake.error=False;fake.native_read_failed=False;fake.sdk_calls=40;fake.close_resume_enabled=False
        fake.u32.return_value=0;fake.read.side_effect=lambda address,size:b'V'*64 if size==64 else b'O'*16
        a={'identity':'synthetic-id','full':'synthetic-full','options_sha256':m.sha(b'O'*16)}
        with patch.object(m,'WatchLink',return_value=fake),patch.object(m.raw,'identity',return_value={'synthetic':True}), \
             patch.object(m.recovery,'identity_check'),patch.object(m.g,'load',return_value={'synthetic':True}), \
             patch.object(m.recovery,'read',return_value=b'V'*64),patch.object(m.recovery,'protected'), \
             patch.object(m.g,'save'),patch.object(m.g,'write_private'), \
             patch.object(m,'watch',return_value=dict(status=status,last_kind='FLASH')), \
             patch.object(m,'sample',return_value=final) as sampling:
            result=m.capture(a,self.root,1)
        return result,fake,sampling

    def test_hardware_stop_does_not_sample_again_or_resume(self):
        result,fake,sampling=self.capture_fixture('HALT_OBSERVED',self.frame(1))
        fake.set_close_resume.assert_not_called();sampling.assert_not_called();fake.close.assert_called_once()
        self.assertEqual(result['status'],'HALT_OBSERVED')

    def test_changed_state_before_close_is_not_reported_healthy(self):
        result,fake,_=self.capture_fixture('NORMAL_FLASH_RESET_OBSERVED_MONITOR_COMPLETE',dict(self.frame(1),DHCSR=m.raw.HALT))
        fake.set_close_resume.assert_not_called();self.assertEqual(result['status'],'STATE_CHANGED_BEFORE_CLOSE')

    def test_actual_healthy_close_policy_uses_verified_flash(self):
        result,fake,_=self.capture_fixture('NORMAL_FLASH_RESET_OBSERVED_MONITOR_COMPLETE',self.frame(1))
        fake.set_close_resume.assert_called_once_with(True);self.assertTrue(fake.verified_running_flash)

    def test_existing_popup_end_from_prior_attach_does_not_skip_close(self):
        (self.root/'POPUP_END').touch()
        result,fake,_=self.capture_fixture('NORMAL_FLASH_REATTACH_MONITOR_COMPLETE',self.frame(1))
        fake.close.assert_called_once();self.assertTrue(result['Close_completed'])


if __name__=='__main__':unittest.main(verbosity=2)
