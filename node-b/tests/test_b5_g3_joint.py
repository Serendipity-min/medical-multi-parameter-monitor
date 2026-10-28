"""G3定向离线验证：真实解析/匹配/状态机，设备与网络边界使用合成替身。"""
import ast
import ctypes as C
import io
import json
from pathlib import Path
import struct
import sys
import tempfile
import types
import unittest
from unittest.mock import patch, Mock
ROOT=Path(__file__).resolve().parents[2]
sys.path[:0]=[str(ROOT/'node-b/tools'),str(ROOT)]
import b5_g3_contract as g
import b5_g3_joint as j
import b5_g3_devices as d
import b5_g3_review as review


def raw_slot(seq,tick,ch2=0):
    return (0xc00000).to_bytes(3,'big')+bytes(3)+(ch2&0xffffff).to_bytes(3,'big')+bytes(3)+struct.pack('<III',seq,123,tick)


def fixture(stream='ECG'):
    count,stride,rate,scale=(100,1,250,1000) if stream=='ECG' else (50,5,50,1000000)
    raw={};can={};clock=(1700000000,0,0,1)
    for seq in range(1,count*stride+1):
        tick=1000+seq*4+[0,1,1,0][seq%4]
        ecg=seq*17-1000;resp=seq*1000-500000
        raw[seq]=raw_slot(seq,tick,seq)
        can[seq]=struct.pack('<iiIIBB2x',ecg,resp,tick,seq,int(seq%5==0),0)
    chosen=[can[s] for s in range(stride,count*stride+1,stride)]
    vals=[struct.unpack('<iiIIBB2x',b)[0 if stream=='ECG' else 1] for b in chosen]
    end=struct.unpack('<iiIIBB2x',chosen[-1])[2]+clock[0]*1000
    m={'stream':stream,'sample_rate':rate,'samples':[x/scale for x in vals],'timestamp':end}
    return m,g.can_utc_points(can,{clock}),can,raw


class Tests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name)
    def save(self,path,obj):Path(path).write_text(json.dumps(obj),encoding='utf8')
    def save_once(self,path,obj):
        with Path(path).open('x',encoding='utf8') as f:json.dump(obj,f)
    def ready(self,now=None):
        for name in ('B_READY.json','NET_READY.json','C_BANNER_READY.json','ARM_BACKEND_BASELINE.json','C_RESET_OWNER_DONE.json','RESET_REQUESTED.json'):
            self.save(self.root/name,{})
        self.save(self.root/'C_BANNER_READY.json',{'monotonic':j.time.monotonic() if now is None else now})
    def test_exact_45_300_15_with_late_readiness_fits_420(self):
        x=j.phase_limits(100,160)
        self.assertEqual(x['evaluation'],[205,505]);self.assertEqual(x['tail_end'],520);self.assertEqual(x['hard'],520)
        with self.assertRaisesRegex(ValueError,'BUDGET'):j.phase_limits(100,160.001)
    def test_default_never_opens_device_serial_or_network(self):
        with patch.object(sys,'argv',['joint']),patch('sys.stdout',io.StringIO()), \
             patch.object(j,'supervise') as execute,patch.object(d,'BLink') as native:
            self.assertEqual(j.main(),0);execute.assert_not_called();native.assert_not_called()
    def test_disabled_or_wrong_stage_auth_fails_before_file_access(self):
        for a in ({},{'enabled':True,'owner_approved':True,'scope':g.HW}):
            with self.assertRaisesRegex(ValueError,'OWNER_SCOPE'):g.validate(a,g.G3)
    def test_start_denied_without_separate_approval(self):
        port=types.SimpleNamespace(write=lambda x:self.fail('real or fake write forbidden'))
        with self.assertRaisesRegex(ValueError,'NOT_ALLOWED'):j.start_once(port,self.root,{'owner_approved':True,'B5START_allowed':False})
    def test_missing_manual_reset_ack_or_observer_readiness_prevents_start(self):
        self.ready();(self.root/'C_RESET_OWNER_DONE.json').unlink()
        port=types.SimpleNamespace(write=lambda x:self.fail('write forbidden'))
        with self.assertRaisesRegex(ValueError,'PREREQUISITES'):j.start_once(port,self.root,{'owner_approved':True,'B5START_allowed':True})
    def test_single_complete_command_and_no_second_attempt(self):
        self.ready(now=100);calls=[];port=types.SimpleNamespace(write=lambda x:(calls.append(x) or len(x)))
        with patch.object(g,'save',side_effect=self.save_once):
            j.start_once(port,self.root,{'owner_approved':True,'B5START_allowed':True},now=100,utc_ms=1700000000000)
            with self.assertRaises(FileExistsError):j.start_once(port,self.root,{'owner_approved':True,'B5START_allowed':True},now=100.1)
        self.assertEqual(calls,[b'B5START\n'])
    def test_positive_short_serial_write_consumes_permission_and_never_retries(self):
        self.ready();calls=[];port=types.SimpleNamespace(write=lambda x:(calls.append(x) or 7))
        with patch.object(g,'save',side_effect=self.save_once):
            with self.assertRaisesRegex(ValueError,'NO_RETRY'):j.start_once(port,self.root,{'owner_approved':True,'B5START_allowed':True})
        self.assertEqual(len(calls),1);self.assertTrue((self.root/'ARM_ATTEMPT.json').exists())
    def test_late_manual_reset_confirmation_never_sends_start(self):
        self.ready(now=100)
        port=types.SimpleNamespace(write=lambda x:self.fail('expired reset must not start'))
        with self.assertRaisesRegex(ValueError,'RESET_ACK_TOO_LATE'):
            j.start_once(port,self.root,{'owner_approved':True,'B5START_allowed':True},now=130.001)
        self.assertFalse((self.root/'ARM_ATTEMPT.json').exists())
    def test_serial_duplicate_boot_or_postarm_reset_stops(self):
        for armed in (False,True):
            gate=j.SerialGate();gate.consume('B5 DISARMED MOCK B_ONLY NO_FLASH_WRITE')
            with self.assertRaises(ValueError):gate.consume('B5 DISARMED MOCK B_ONLY NO_FLASH_WRITE',armed)
    def test_exact_startup_gate_requires_fresh_SNTP_and_strict_TLS(self):
        gate=j.SerialGate()
        for line in ('GW AT_VERSION value=2.2.0.0','GW SNTP_SAMPLE rtt_ms=40 uncertainty_ms=20 epoch=1700000000 fraction=2 server_index=0',
                     'GW SNTP_VALID epoch=1700000000 uptime=100','GW OK CA_VERIFY','GW OK CERT_NAME','GW OK SNI','GW MQTT_CONNECTED'):
            gate.consume(line,True)
        gate.consume('GW OK TLS_extra',True);self.assertFalse(gate.startup_ready())
        gate.consume('GW OK TLS',True);self.assertTrue(gate.startup_ready())
    def test_SNTPrtt_or_clock_metadata_invalid_denied(self):
        with self.assertRaisesRegex(ValueError,'SNTP_METADATA'):
            j.SerialGate().consume('GW SNTP_SAMPLE rtt_ms=1001 uncertainty_ms=500 epoch=1700000000 fraction=0 server_index=0',True)
    def test_only_explicit_precommon_NTP_rejections_can_be_observed(self):
        with self.assertRaises(ValueError):j.SerialGate().consume('GW FAIL SNTP_FRESH_SAMPLE',True)
        gate=j.SerialGate()
        for _ in range(2):gate.consume('GW FAIL SNTP_FRESH_SAMPLE',True,2)
        self.assertEqual(len(gate.precommon_ntp_failures),2)
        self.assertFalse(gate.startup_ready())
        with self.assertRaises(ValueError):gate.consume('GW FAIL SNTP_FRESH_SAMPLE',True,2)
        with self.assertRaises(ValueError):j.SerialGate().consume('GW FAIL SNTP_FRESH_SAMPLE',False,2)
    def test_TLS_and_other_network_failures_still_stop_with_NTP_observation_permission(self):
        for line in ('GW FAIL CA_VERIFY','GW FAIL CERT_NAME','GW FAIL SNI','GW FAIL TLS','GW FAIL WIFI'):
            with self.subTest(line=line),self.assertRaises(ValueError):j.SerialGate().consume(line,True,2)
        gate=j.SerialGate();gate.steps={'AT_VERSION','SNTP_SAMPLE','SNTP_VALID','CA','CERT','SNI','TLS','MQTT'}
        with self.assertRaises(ValueError):gate.consume('GW FAIL SNTP_FRESH_SAMPLE',True,2)
    def test_C_error_counter_or_TEC_REC_stops(self):
        fields=dict(tick=1,session=1,rx=1,txack=1,txfail=0,overflow=0,esr=0,uart_err=0,live=0,cache=0,dropped=0,q0_transport=0,q1_puback=0,mqtt_fail=0,stop=0)
        for key,value in [('txfail',1),('overflow',1),('esr',1<<16),('esr',1<<24),('esr',4),('uart_err',1)]:
            x={**fields,key:value};line='B5 DIAG '+' '.join(k+'='+str(v) for k,v in x.items())
            with self.assertRaises(ValueError):j.SerialGate().consume(line,True)
    def test_C_old_STOP_cannot_be_rearmed(self):
        with self.assertRaisesRegex(ValueError,'ALREADY_STOPPED'):j.SerialGate().consume('B5 STOPPED NO_AUTOREARM')
    def test_repeated_slot_version_and_single_outlier_keep_provenance(self):
        v=g.Versions();v.add(1,b'A',1);v.add(1,b'A',2);v.add(1,b'B',3)
        good,bad=v.stable();self.assertEqual(good,{1:b'A'});self.assertEqual(bad,[]);self.assertEqual(v.positions[1,b'A'],[1,2])
    def test_two_repeated_conflicts_never_choose_majority(self):
        v=g.Versions()
        for b in (b'A',b'A',b'A',b'B',b'B'):v.add(1,b,0)
        good,bad=v.stable();self.assertEqual(good,{});self.assertEqual(bad,[1])
    def test_ELF_bound_contiguous_block_layout_and_actual_offsets(self):
        b=bytearray(g.BLOCK_BYTES);b[24:48]=raw_slot(5,100)
        b[3072+60:3072+80]=struct.pack('<iiIIBB2x',-1,2,100,5,1,0)
        struct.pack_into('<III B 3x',b,5632,1700000000,0,100,1)
        rr,cc,clock=g.decode_block(b)
        self.assertEqual(rr[0][2],24);self.assertEqual(cc[0][2],3132);self.assertEqual(clock,(1700000000,0,100,1))
        with self.assertRaisesRegex(ValueError,'BLOCK_LENGTH'):g.decode_block(b[:-1])
    def test_actual_ECG_queue_to_100_point_payload_handles_quantized_ticks(self):
        m,index,can,raw=fixture();points=review.match_batch(m,index,can,raw)
        self.assertEqual(len(points),100);self.assertEqual([s for s,_,_ in points],list(range(1,101)))
    def test_RESP50_selects_actual_every_fifth_source_frame(self):
        m,index,can,raw=fixture('RESP');points=review.match_batch(m,index,can,raw)
        self.assertEqual([s for s,_,_ in points],list(range(5,251,5)))
    def test_wave_scale_error_gain6_or_corrupted_value_is_rejected(self):
        for factor in (1.5,2/3,2):
            m,index,can,raw=fixture();m['samples'][10]*=factor
            with self.assertRaises(ValueError):review.match_batch(m,index,can,raw)
    def test_missing_ADC_source_or_can_slot_does_not_get_filled(self):
        for kind in ('raw','can'):
            m,index,can,raw=fixture();(raw if kind=='raw' else can).pop(50)
            with self.assertRaisesRegex(ValueError,'MISSING_OR_AMBIGUOUS'):review.match_batch(m,index,can,raw)
    def test_wrong_wave_batch_or_rate_cannot_pass(self):
        for key,value in [('sample_rate',50),('samples',[0.0]*99)]:
            m,index,can,raw=fixture();m[key]=value
            with self.assertRaisesRegex(ValueError,'BATCH_RATE'):review.match_batch(m,index,can,raw)
    def test_fixed_point_positive_negative_and_limits(self):
        for i in (-2147483648,-1,0,1,2147483647):
            self.assertEqual(g.fixed(str(i/1000),1000),i)
        with self.assertRaises(ValueError):g.fixed('0.0001',1000)
    def test_future_clock_is_not_unconditionally_used_for_old_samples(self):
        m,index,can,raw=fixture()
        self.assertEqual(g.can_utc_points(can,{(1700000000,0,100000,1)}),{})
    def test_invalid_WSS_values_masked_and_A_offline(self):
        good={'gateway_id':'GW-B5-001','nodes':{'NODE-A':'OFFLINE'},'streams':[{'source':'MOCK','synthetic':True,'stream':'RR','validity':'INVALID','value':None,'samples':[]}]}
        g.assert_snapshot(good)
        for key,value in [('value',15.0),('samples',[1.0]),('source','LIVE')]:
            bad=json.loads(json.dumps(good));bad['streams'][0][key]=value
            with self.assertRaises(ValueError):g.assert_snapshot(bad)
    def test_B_unsafe_control_APIs_never_reach_native(self):
        link=object.__new__(d.BLink)
        for api in ('JLINKARM_Reset','JLINKARM_Halt','JLINKARM_Go','JLINKARM_WriteMem','JLINKARM_WriteReg','JLINKARM_CORESIGHT_Configure','JLINKARM_CORESIGHT_WriteAPDPReg'):
            with self.assertRaisesRegex(ValueError,'API_DENIED'):link.call(api)
    def test_B_unwhitelisted_RAM_and_UART_DR_read_denied(self):
        link=object.__new__(d.BLink);link.sdk_calls=0
        for address,size in ((0x40011004,4),(0x20000000,65536),(g.SLOTS,3072)):
            with self.assertRaisesRegex(ValueError,'READ_SCOPE'):link.call('JLINKARM_ReadMemEx',address,size,None,0)
    def test_B_native_negative_return_is_retained_with_address(self):
        link=object.__new__(d.BLink);link.sdk_calls=0;link.io=io.StringIO();link.events=io.StringIO();link.gate=lambda:None
        link.dll=types.SimpleNamespace(JLINKARM_ReadMemEx=lambda *a:-1)
        with self.assertRaisesRegex(ValueError,'NATIVE_READ_ERROR'):link.read(g.SLOTS,g.BLOCK_BYTES)
        row=json.loads(link.io.getvalue());self.assertEqual(row['native_return_int'],-1);self.assertEqual(row['address'],hex(g.SLOTS))
        self.assertTrue(link.native_failed);self.assertFalse(link.verified_running_flash)
    def test_host_cancel_close_requires_fresh_running_state_and_never_Go(self):
        link=object.__new__(d.BLink);link.error=False;link.native_failed=False;link.host_cancel_close=False
        link.final_close_verified=False;link.set_close_resume=Mock()
        with patch.object(d.b.ro,'snapshot',return_value={'fixture':'SYNTHETIC'}),patch.object(d.raw,'write_json'),\
                patch.object(d.b.ro,'check_running') as check:
            link.prepare_host_cancel_close(self.root)
            check.assert_called_once();link.set_close_resume.assert_called_once_with(True)
        self.assertTrue(link.final_close_verified);self.assertFalse(link.host_cancel_close)
    def test_host_cancel_close_does_not_resume_HALT_ROM_or_native_failures(self):
        for native,error,fault in ((True,False,False),(False,True,False),(False,False,True)):
            link=object.__new__(d.BLink);link.error=error;link.native_failed=native;link.host_cancel_close=False
            link.final_close_verified=False;link.set_close_resume=Mock()
            with patch.object(d.b.ro,'snapshot',return_value={}),patch.object(d.raw,'write_json'),\
                    patch.object(d.b.ro,'check_running',side_effect=ValueError('SYNTHETIC_HALT_OR_ROM')):
                with self.assertRaises(ValueError):link.prepare_host_cancel_close(self.root)
            link.set_close_resume.assert_not_called();self.assertFalse(link.host_cancel_close)
    def test_no_MQTT_publisher_or_firmware_write_in_cloud_observer(self):
        tree=ast.parse((ROOT/'node-b/tools/b5_g3_cloud.py').read_text('utf8'))
        calls=[x.func.attr for x in ast.walk(tree) if isinstance(x,ast.Call) and isinstance(x.func,ast.Attribute)]
        self.assertNotIn('publish',calls);self.assertIn('subscribe',calls)
    def test_supervisor_tail_reader_preserves_active_deadline_without_full_scan(self):
        p=self.root/'event';p.write_text('{}\n'*3000+json.dumps({'active':True,'deadline_monotonic':10})+'\n')
        self.assertEqual(j.last_event(p)['deadline_monotonic'],10)
    def test_failed_or_incomplete_capture_never_gets_engineering_PASS(self):
        self.save(self.root/'joint-receipt-private.json',{'status':'STOP','exit_code':1})
        self.save(self.root/'supervisor-private.json',{'worker_exit_code':0,'supervisor_exit_code':0})
        with patch.object(g,'load',side_effect=lambda p:json.loads(Path(p).read_text())):
            with self.assertRaisesRegex(ValueError,'NOT_COMPLETE'):review.review(self.root)


class AdditionalBoundaryTests(unittest.TestCase):
    def test_C_control_and_DAP_calls_denied_even_if_old_bridge_supported_them(self):
        link=object.__new__(d.CLink)
        for name in ('JLINKARM_Reset','JLINKARM_Halt','JLINKARM_Go','JLINKARM_WriteMem','JLINKARM_CORESIGHT_ReadAPDPReg','JLINKARM_CORESIGHT_WriteAPDPReg'):
            with self.assertRaisesRegex(ValueError,'READONLY_API'):link.call(name)
    def test_C_full_and_options_single_read_limit_is_enforced_before_parent(self):
        link=object.__new__(d.CLink);link.started=j.time.monotonic()
        with patch.object(d.c.BridgeLink,'call',return_value=16) as parent:
            self.assertEqual(link.call('JLINKARM_ReadMemEx',0x1fffc000,16,None,0),16)
            with self.assertRaisesRegex(ValueError,'ONE_READ_LIMIT'):link.call('JLINKARM_ReadMemEx',0x1fffc000,16,None,0)
            self.assertEqual(parent.call_count,1)
    def test_environment_drift_stops_before_private_reference_reads(self):
        a={'enabled':True,'owner_approved':True,'scope':g.G3,'tools_sha256':g.bindings(),'criteria':g.CRITERIA,'environment':{}}
        with patch.object(g.private,'read') as read:
            with self.assertRaisesRegex(ValueError,'ENVIRONMENT_DRIFT'):g.validate(a,g.G3)
            read.assert_not_called()
    def test_unsafe_error_text_is_fingerprinted_and_numeric_error_retained(self):
        e=OSError(123,'SYNTHETIC example.invalid credential-like detail')
        result=g.error_record(e)
        self.assertEqual(result['reason'],'PRIVATE_ERROR_SUPPRESSED');self.assertEqual(result['errno'],123)
        self.assertNotIn('example.invalid',json.dumps(result))
        self.assertEqual(g.error_record(ValueError('B4_RUNTIME_NEW_ADC_GAP'))['reason'],'B4_RUNTIME_NEW_ADC_GAP')
    def test_C_second_MQTT_session_stops_instead_of_masking_reconnect(self):
        gate=j.SerialGate()
        fields=dict(tick=1,session=777,rx=1,txack=1,txfail=0,overflow=0,esr=0,uart_err=0,live=0,cache=0,dropped=0,q0_transport=0,q1_puback=0,mqtt_fail=0,stop=0)
        gate.consume('B5 DIAG '+' '.join(k+'='+str(v) for k,v in fields.items()),True)
        fields.update(tick=2,session=888)
        with self.assertRaisesRegex(ValueError,'SESSION_CHANGED'):gate.consume('B5 DIAG '+' '.join(k+'='+str(v) for k,v in fields.items()),True)


class JointControlTests(unittest.TestCase):
    """虚拟时钟驱动真实联合控制器；Serial/Popen/Thread全替身，无实板/服务。"""
    def run_joint(self,mode='normal'):
        temporary=tempfile.TemporaryDirectory();self.addCleanup(temporary.cleanup)
        root=Path(temporary.name)/'window';clock=[10000.0];writes=[];shared_holder={}
        a={'output':str(root),'COM':'SYNTHETIC','owner_approved':True,'B5START_allowed':True}
        if mode in ('ntp_retry','ntp_late'):a['precommon_ntp_retries_max']=2
        def save(path,value):
            with Path(path).open('x',encoding='utf8') as f:json.dump(value,f)
        def cloud(a,r,bundle,stop,shared):
            shared_holder['shared']=shared
            save(r/'NET_READY.json',{})
            save(r/'cloud-receipt-private.json',{'exit_code':0})
        class Thread:
            def __init__(self,target,args,**kw):self.target,self.args=target,args
            def start(self):self.target(*self.args)
            def join(self,**kw):pass
            def is_alive(self):return False
        class Child:
            def __init__(self,*args,**kwargs):
                self.returncode=None;save(root/'B_READY.json',{})
            def poll(self):
                if (root/'END_B').exists():self.returncode=0
                return self.returncode
            def wait(self,**kwargs):self.returncode=0;return 0
            def kill(self):self.returncode=-9
        class Serial:
            def __init__(self,**kw):self.sent=False;self.banner=False;self.arm=None;self.stop=False;self.ntp_failed=False
            def open(self):pass
            def close(self):pass
            def write(self,data):writes.append(data);self.arm=clock[0];return len(data)
            def read(self,size):
                clock[0]+=.5
                shared_holder['shared']['cloud_last_monotonic']=clock[0]
                if (root/'ARM_PREPARE.json').exists() and not (root/'ARM_BACKEND_BASELINE.json').exists():save(root/'ARM_BACKEND_BASELINE.json',{})
                if not self.banner:
                    self.banner=True
                    if mode=='no_banner':return b''
                    save(root/'C_RESET_OWNER_DONE.json',{})
                    return b'B5 DISARMED MOCK B_ONLY NO_FLASH_WRITE\r\n'
                if self.arm is None:return b''
                if not self.sent:
                    if mode in ('ntp_retry','ntp_late') and not self.ntp_failed:
                        self.ntp_failed=True;return b'GW FAIL SNTP_FRESH_SAMPLE\r\n'
                    if mode=='ntp_late' and clock[0]-self.arm<=61:return b''
                    self.sent=True
                    if mode=='network_failure':return b'GW FAIL CA_VERIFY\r\n'
                    save(root/'CLOUD_COMMON.json',{'monotonic':clock[0],'server_time':int((1700000000+clock[0]-10000)*1000),
                         'gateway_session':'can-1-1','B_session':'can-1-1'})
                    return ('GW AT_VERSION value=2.2.0.0\nGW SNTP_SAMPLE rtt_ms=20 uncertainty_ms=10 epoch=1700000000 fraction=0 server_index=0\n'
                            'GW SNTP_VALID epoch=1700000000 uptime=100\nGW OK CA_VERIFY\nGW OK CERT_NAME\nGW OK SNI\nGW OK TLS\nGW MQTT_CONNECTED\n').encode()
                if clock[0]-self.arm>=420 and not self.stop:
                    self.stop=True;return b'B5 STOPPED NO_AUTOREARM\n'
                return b''
        import b5_g3_cloud
        with patch.dict(sys.modules,{'serial':types.SimpleNamespace(Serial=Serial)}), \
             patch.object(g,'save',side_effect=save),patch.object(g.private,'protected',side_effect=lambda p,_:Path(p)), \
             patch.object(j.subprocess,'Popen',Child),patch.object(j.threading,'Thread',Thread), \
             patch.object(b5_g3_cloud,'run',side_effect=cloud), \
             patch.object(j.time,'monotonic',side_effect=lambda:clock[0]), \
             patch.object(j.time,'time',side_effect=lambda:1700000000+clock[0]-10000),patch('sys.stdout',io.StringIO()):
            code=j.joint_worker(Path('SYNTHETIC_ONLY'),a,{})
        return code,json.loads((root/'joint-receipt-private.json').read_text()),writes,clock[0],root
    def test_real_control_flow_captures_virtual_420_and_passive20_without_publishing(self):
        code,r,writes,ended,root=self.run_joint()
        self.assertEqual(code,0);self.assertEqual(writes,[b'B5START\n'])
        arm=json.loads((root/'ARM_ATTEMPT.json').read_text())
        self.assertGreaterEqual(ended-arm['monotonic'],440)
        self.assertLessEqual(r['C_STOP_banner_monotonic']-arm['monotonic'],422)
        self.assertEqual(r['physiological_and_transport_PASS'],'NOT_GRANTED_UNTIL_OFFLINE_JOINT_REVIEW')
    def test_missing_boot_evidence_times_out_with_zero_start(self):
        code,r,writes,ended,root=self.run_joint('no_banner')
        self.assertEqual(code,1);self.assertEqual(writes,[]);self.assertEqual(r['reason'],'G3_PREARM_TIMEOUT_NO_START')
    def test_first_network_failure_stops_and_requests_physical_isolation_without_restart(self):
        code,r,writes,ended,root=self.run_joint('network_failure')
        self.assertEqual(code,1);self.assertEqual(len(writes),1)
        self.assertIn('MANUAL_ALL_BOARD_POWER_REMOVAL',r['physical_stop'])
        self.assertEqual(len(r['manual_isolation_required']),4)
    def test_NTP_rotation_before_common_keeps_same_single_start_and_full_window(self):
        code,r,writes,ended,root=self.run_joint('ntp_retry')
        self.assertEqual(code,0);self.assertEqual(writes,[b'B5START\n'])
        self.assertEqual(r['precommon_ntp_failures'],['GW FAIL SNTP_FRESH_SAMPLE'])
        self.assertGreaterEqual(ended-json.loads((root/'ARM_ATTEMPT.json').read_text())['monotonic'],440)
    def test_NTP_rotation_cannot_extend_frozen_60_second_ready_gate(self):
        code,r,writes,ended,root=self.run_joint('ntp_late')
        self.assertEqual(code,1);self.assertEqual(writes,[b'B5START\n'])
        self.assertEqual(r['reason'],'G3_COMMON_NOT_READY_IN_60S')


class SupervisorTests(unittest.TestCase):
    def scenario(self,stop_confirmed):
        tmp=tempfile.TemporaryDirectory();self.addCleanup(tmp.cleanup)
        base=Path(tmp.name);root=base/'window';auth=base/'auth.json';auth.write_text('{}')
        clock=[10000.0];instances=[];kills=[]
        def save(path,value):
            with Path(path).open('x') as f:json.dump(value,f)
        class Child:
            def __init__(self,*args,**kwargs):
                self.pid=987654;self.returncode=None;instances.append(self);root.mkdir()
                save(root/'ARM_ATTEMPT.json',{'monotonic':10000.0});save(root/'T0.json',{})
            def poll(self):
                if stop_confirmed and clock[0]>=10420 and not (root/'C_STOP_BANNER.json').exists():save(root/'C_STOP_BANNER.json',{'monotonic':clock[0]})
                if clock[0]>=10440 and self.returncode is None:self.returncode=0
                return self.returncode
            def wait(self,**kwargs):return self.returncode
        def kill(command,**kwargs):kills.append(command);instances[0].returncode=99;return types.SimpleNamespace(returncode=0)
        with patch.object(g,'load',return_value={'output':str(root),'scope':g.G3}),patch.object(g,'validate',return_value=({},{})), \
             patch.object(g,'save',side_effect=save),patch.object(g,'write_private',side_effect=lambda p,b:Path(p).write_bytes(b)), \
             patch.object(j.subprocess,'Popen',Child),patch.object(j.subprocess,'run',side_effect=kill), \
             patch.object(j.time,'monotonic',side_effect=lambda:clock[0]),patch.object(j.time,'sleep',side_effect=lambda n:clock.__setitem__(0,clock[0]+1)), \
             patch('sys.stdout',io.StringIO()):code=j.supervise(auth)
        return code,json.loads((root/'supervisor-private.json').read_text()),kills,clock[0]
    def test_independent_supervisor_requires_MCU_stop_not_process_liveness(self):
        code,r,kills,at=self.scenario(False)
        self.assertEqual(code,1);self.assertEqual(r['supervisor_reason'],'MCU_STOP_NOT_CONFIRMED_MANUAL_ISOLATE')
        self.assertEqual(kills,[['taskkill','/PID','987654','/T','/F']]);self.assertTrue(r['process_tree_killed_is_not_MCU_stop'])
        self.assertLessEqual(at,10423)
    def test_independent_supervisor_allows_only_passive_20s_after_confirmed_stop(self):
        code,r,kills,at=self.scenario(True)
        self.assertEqual(code,0);self.assertEqual(kills,[]);self.assertEqual(at,10440)


class SyntheticReviewIntegrationTests(unittest.TestCase):
    """固定300秒的软件合成夹具，真实Hub/适配器/原件解析器；不是SKX或实板验收。"""
    def build(self,root):
        from cloud.backend.app.hub import Hub
        from cloud.backend.app.adapters import decode_mqtt
        base=1700000000000;mono=1000.0
        def save(path,value):Path(path).write_text(json.dumps(value),encoding='utf8')
        (root/'B').mkdir()
        save(root/'joint-receipt-private.json',{'status':'G3_FILES_CAPTURED_REVIEW_PENDING','exit_code':0,'B5START_attempts':1})
        save(root/'supervisor-private.json',{'worker_exit_code':0,'supervisor_exit_code':0})
        save(root/'B/receipt-private.json',{'exit_code':0});save(root/'cloud-receipt-private.json',{'exit_code':0})
        save(root/'T0.json',{'monotonic':mono,'UTC_ms':base,'B_session':'can-777-1','gateway_session':'can-777-1',
                           'evaluation_UTC_ms':[base+45000,base+345000],'evaluation':[1045,1345],'tail_end':1360})
        save(root/'ARM_ATTEMPT.json',{'monotonic':990.0,'UTC_ms':base-10000,'bytes':8,'command_sha256':g.sha(b'B5START\n')})
        save(root/'C_STOP_BANNER.json',{'monotonic':1410.5})
        save(root/'ARM_BACKEND_BASELINE.json',{'health':{'accepted':0,'rejected':0,'dropped':0}})
        def ecg(seq):return seq%1000-500
        def resp(seq):return (seq%2500-1250)*1000
        with (root/'B/blocks-private.bin').open('wb') as binary,(root/'B/blocks-private.jsonl').open('w') as meta:
            for index,high in enumerate(range(128,90001,32)):
                blob=bytearray(g.BLOCK_BYTES)
                for seq in range(high-127,high+1):
                    slot=(seq-1)%128
                    blob[slot*24:slot*24+24]=raw_slot(seq,seq*4,ecg(seq)*10)
                    blob[3072+slot*20:3072+(slot+1)*20]=struct.pack('<iiIIBB2x',ecg(seq),resp(seq),seq*4,seq,int(seq%5==0),0)
                at=high*4//10000*10000
                struct.pack_into('<III B 3x',blob,5632,1700000000+at//1000,at,at,1)
                binary.write(blob);meta.write(json.dumps({'data':{'index':index,'offset':index*g.BLOCK_BYTES,'sha256':g.sha(blob)}})+'\n')
        can_fields='offered enqueued sent_ecg sent_resp overflow expired comm_reset app_reset_rejected high_water error discontinuities'.split()
        with (root/'B/diagnostics-private.jsonl').open('w') as f:
            for ms in range(0,360001,500):
                can={k:0 for k in can_fields};can.update(offered=ms//4,enqueued=ms//4,sent_ecg=ms//4,sent_resp=ms//20,high_water=2)
                bio={'hr_valid':1,'hr_reason':0,'hr':60,'rpm_valid':0,'rpm_reason':2,'last_sample_ms':ms,'samples':ms//4,
                     'clipped_samples':0,'adc':{k:0 for k in ('bad_status','spi_errors','queue_overflow','init_errors','long_gap_count')}}
                f.write(json.dumps({'data':{'host_monotonic':mono+ms/1000,'bio':bio,'CAN':can,'CAN1_ESR':0}})+'\n')
        pending=[]
        def body(timestamp,seq,unit,value,validity='VALID',**kw):
            return dict(timestamp=base+timestamp,seq=seq,session_id='can-777-1',validity=validity,source='MOCK',synthetic=True,unit=unit,value=value,**kw)
        def emit(at,suffix,b):pending.append((at,suffix,json.dumps(b,separators=(',',':')).encode()))
        for ms in range(0,360001,5000):
            emit(ms,'status',body(ms,ms//5000+1,'state','ONLINE'))
            emit(ms,'NODE-B/status',body(ms,ms//5000+1,'state','ONLINE'))
        for seq in range(100,90001,100):
            emit(seq*4,'NODE-B/telemetry/ecg',body(seq*4,seq//100,'mV',None,samples=[ecg(x)/1000 for x in range(seq-99,seq+1)],sample_rate=250))
        for seq in range(250,90001,250):
            emit(seq*4,'NODE-B/telemetry/resp',body(seq*4,seq//250,'relative',None,'INVALID',samples=[resp(x)/1000000 for x in range(seq-245,seq+1,5)],sample_rate=50))
        for ms in range(1000,360001,1000):
            for stream,unit,value,valid in [('hr','bpm',60.0,'VALID'),('rr','breaths/min',None,'INVALID'),('temp','degC',None,'INVALID')]:
                emit(ms,'NODE-B/telemetry/'+stream,body(ms,ms//1000,unit,value,valid))
        pending.sort(key=lambda x:x[0]);at=[0];hub=Hub(['GW-B5-001'],clock=lambda:(base+at[0])/1000,monotonic=lambda:at[0]/1000)
        hub.broker_connected=True;index=0;events=[]
        for ms in range(0,360001,100):
            at[0]=ms
            while index<len(pending) and pending[index][0]<=ms:
                arrival,suffix,blob=pending[index];topic='mpm/v1/GW-B5-001/'+suffix
                message=decode_mqtt(topic,blob);hub.ingest(message)
                events.append({'monotonic':mono+arrival/1000,'kind':'BROKER_RAW','data':{'topic':topic,'payload_hex':blob.hex(),'qos':0 if suffix.endswith(('ecg','resp')) else 1,'retain':False}})
                index+=1
            events.append({'monotonic':mono+ms/1000,'kind':'WSS_RAW','data':hub.snapshot('GW-B5-001')})
        at[0]=426000
        events.append({'monotonic':1426.0,'kind':'WSS_RAW','data':hub.snapshot('GW-B5-001')})
        events.append({'monotonic':1430.0,'kind':'BACKEND_HEALTH_AFTER','data':{'accepted':hub.accepted,'rejected':0,'dropped':0}})
        with (root/'cloud-events-private.jsonl').open('w') as f:
            for event in events:f.write(json.dumps(event)+'\n')
        with (root/'C-lines-private.jsonl').open('w') as f:
            for seconds in range(0,411,5):
                fields=dict(tick=seconds*1000,session=777,rx=seconds*300,txack=seconds,txfail=0,overflow=0,esr=0,uart_err=0,live=0,cache=0,dropped=0,q0_transport=seconds*3,q1_puback=seconds*4,mqtt_fail=0,stop=0)
                line='B5 DIAG '+' '.join(k+'='+str(v) for k,v in fields.items())
                f.write(json.dumps({'monotonic':mono+seconds,'data':line})+'\n')
    def test_full_frozen_300s_synthetic_pipeline_and_one_corruption_negative(self):
        temp=tempfile.TemporaryDirectory();self.addCleanup(temp.cleanup);root=Path(temp.name);self.build(root)
        with patch.object(g,'load',side_effect=lambda p:json.loads(Path(p).read_text('utf8'))):
            result=review.review(root)
            self.assertEqual(result['exit_code'],0,result['failures']);self.assertEqual(result['ECG_source_points'],75000)
            self.assertEqual(result['RESP_source_points'],15000)
            path=root/'cloud-events-private.jsonl';rows=path.read_text().splitlines()
            for i,line in enumerate(rows):
                x=json.loads(line)
                if x['kind']=='BROKER_RAW' and x['data']['topic'].endswith('/ecg'):
                    original=rows[i];x['data']['qos']=1;rows[i]=json.dumps(x);break
            path.write_text('\n'.join(rows)+'\n')
            qos_bad=review.review(root)
            self.assertIn('BROKER_QOS_POLICY_MISMATCH',qos_bad['failures']);rows[i]=original
            for i,line in enumerate(rows):
                x=json.loads(line)
                if x['kind']=='BROKER_RAW' and x['data']['topic'].endswith('/ecg'):
                    body=json.loads(bytes.fromhex(x['data']['payload_hex']))
                    if body['timestamp']>=1700000045000:
                        body['samples'][10]+=0.001
                        x['data']['payload_hex']=json.dumps(body,separators=(',',':')).encode().hex();rows[i]=json.dumps(x);break
            path.write_text('\n'.join(rows)+'\n')
            bad=review.review(root)
            self.assertEqual(bad['exit_code'],3);self.assertIn('B_QUEUE_TO_BROKER_WAVE_MAPPING',bad['failures'])

if __name__=='__main__':unittest.main()
