"""M1-P0：真实入口/评测器的离线正负例，无设备、串口或网络。"""
import copy
import io
import json
import os
from pathlib import Path
import struct
import sys
import tempfile
import unittest
from contextlib import redirect_stdout, redirect_stderr
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'node-b/tools'))
import b5_m1_entry as entry
import b5_m1_review as review


class Clock:
    def __init__(self):self.t=0.
    def __call__(self):return self.t
    def sleep(self,n):self.t+=n


def bio(t):
    seq=int((10000+t*1000)//4);tick=seq*4
    d={k:0 for k in __import__('resp_exploratory').FIELDS}
    d.update(tag=0x324f4942,abi_version=2,samples=seq,last_sequence=seq,last_sample_ms=tick,segment=1,
             hr=60,rpm=15,hr_valid=1,rpm_valid=1)
    return d


class FakeLink:
    identity={'cpuid':0x410fc241,'device_id':0x413,'uid_hex':'0102030405060708090a0b0c','capacity_kib':1024,'optcr':0xaa00,'flash_sr':0}
    def __init__(self,clock,fault=None):
        self.clock=clock;self.fault=fault;self.opened=False;self.closes=0;self.reads=[]
        self.verified_running_flash=False;self.close_resume_enabled=False;self.final_close_verified=False
    def open(self):
        self.opened=True
        if self.fault in ('OpenEx','Device','Connect'):raise ValueError('M1_'+self.fault.upper()+'_FAILED')
    def set_close_resume(self,yes):
        if not yes or self.final_close_verified:self.close_resume_enabled=yes
    def u32(self,a):return int.from_bytes(self.read(a,4),'little')
    def read(self,a,n):
        self.reads.append((a,n));self.clock.sleep(.001)
        if self.fault=='negative':raise ValueError('G3_B_NATIVE_READ_ERROR')
        if self.fault=='timeout':raise TimeoutError('M1_NATIVE_TIMEOUT')
        regs={0xe000ed00:self.identity['cpuid'],0xe0042000:0x413,0x40023c14:0xaa00,0x40023c0c:0,
              0xe000ed08:0x1fff0000 if self.fault=='ROM' else 0x08000000,
              0xe000101c:0x08000100,0xe000edf0:1<<17 if self.fault=='HALT' else 0,0x40023c10:0x80000000}
        if n==4:return regs.get(a,0).to_bytes(4,'little')
        if a==0x1fff7a10:return bytes.fromhex(self.identity['uid_hex'])
        if a==0x1fff7a22:return (1024).to_bytes(2,'little')
        if a in (0x08000000,0,0x1fffc000):return bytes(n) if self.fault!='firmware' else b'x'*n
        if (a,n)==entry.RAM['bio']:
            d=bio(self.clock());return struct.pack('<8I4i14I4f',*(d[k] for k in __import__('resp_exploratory').FIELDS))
        if (a,n)==entry.RAM['adc']:
            seq=bio(self.clock())['samples'];return struct.pack('<12I',seq,seq,seq,0,0,0,1,0,0,672000,672000,1000)
        if a==entry.SLOTS:
            last=bio(self.clock())['last_sequence'];data=bytearray(n)
            for seq in range(last-127,last+1):
                f=bytearray(24);f[:3]=bytes.fromhex('c00000');f[3:6]=(100).to_bytes(3,'big');f[6:9]=(200).to_bytes(3,'big')
                struct.pack_into('<III',f,12,seq,(seq*672000)&0xffffffff,seq*4)
                at=(seq%128)*24;data[at:at+24]=f
            return bytes(data)
        return bytes(n)
    def close(self):
        self.closes+=1
        if self.fault=='Close':raise OSError('SYNTHETIC_CLOSE_ERROR')
        if self.fault=='Close_timeout':self.clock.sleep(6)
        self.opened=False


def reference():
    return {'identity':dict(FakeLink.identity),'full_sha256':entry.sha(bytes(1048576)),'BIN_sha256':entry.sha(bytes(41012)),
            'options_sha256':entry.sha(bytes(16)),'maximum_cold_start_uptime_ms':120000,'cold_start_sha256':'c'*64}


class Authorization(unittest.TestCase):
    def signed(self,output,changes=None):
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
        from cryptography.hazmat.primitives.serialization import Encoding,PublicFormat
        key=Ed25519PrivateKey.generate();public=key.public_key().public_bytes(Encoding.Raw,PublicFormat.Raw)
        expected={'scope':entry.SCOPE,'run_id':'M1-E60-R1','plan_sha256':entry.plan_hash('M1-E60-R1'),'repo_commit':'2'*40,'repo_tree':'3'*40,
                  'tools_sha256':{'FIXTURE':'4'*64},'DLL_sha256':'5'*64,'bundle_sha256':'6'*64,'site_sha256':'7'*64,
                  'cold_start_sha256':'c'*64,'output':str(output),'manual_stop_responsibility':'SYNTHETIC_ONLY'}
        a={**expected,'enabled':True,'sessions':1,'retries':0,'not_before':90,'expires':110,
           'nonce':'M1_SYNTHETIC_NONCE_0001','sdk_residual_risk_acknowledged':True}
        a.update(changes or {});raw=json.dumps(a,sort_keys=True).encode()
        return raw,key.sign(raw),public,entry.sha(public),expected,a
    def test_signed_binding_and_atomic_nonce(self):
        with tempfile.TemporaryDirectory() as f:
            raw,sig,key,pin,expected,a=self.signed(Path(f)/'out')
            self.assertEqual(entry.verify_signed_card(raw,sig,key,pin,expected,100),a)
            entry.consume_nonce(Path(f),raw,a)
            with self.assertRaises(FileExistsError):entry.consume_nonce(Path(f),raw+b' ',a)
    def test_invalid_signature_key_and_payload(self):
        from cryptography.exceptions import InvalidSignature
        raw,sig,key,pin,expected,a=self.signed(Path('SYNTHETIC'))
        for args in [(raw,b'nonempty',key,pin),(raw,sig,key,None),(raw+b' ',sig,key,pin),(raw,sig,key,'0'*64)]:
            with self.subTest(args=args[-1]),self.assertRaises((ValueError,InvalidSignature)):
                entry.verify_signed_card(*args,expected,100)
    def test_bound_fields_and_old_scope(self):
        for changes in [{'run_id':'M1-E90-R1'},{'scope':'B5_FINAL_RR15_R6'},{'enabled':False},{'expires':100},
                        {'not_before':101},{'sessions':2},{'retries':1},{'sdk_residual_risk_acknowledged':False},
                        {'cold_start_sha256':'0'*64},{'output':'OTHER'},{'nonce':'short'}]:
            raw,sig,key,pin,expected,_=self.signed(Path('SYNTHETIC'),changes)
            with self.subTest(changes=changes),self.assertRaises(ValueError):entry.verify_signed_card(raw,sig,key,pin,expected,100)
    def test_reject_before_factory_and_no_nonce_refund(self):
        with tempfile.TemporaryDirectory() as f:
            root=Path(f);raw,sig,key,pin,expected,a=self.signed(root/'out');calls=[]
            def factory(b,out):calls.append(1);raise OSError('SYNTHETIC_CONSTRUCTOR_FAILURE')
            with self.assertRaises(ValueError):entry.run_authorized_capture(raw,sig,key,None,expected,reference(),factory,root,now=lambda:100)
            self.assertEqual(calls,[])
            r=entry.run_authorized_capture(raw,sig,key,pin,expected,reference(),factory,root,now=lambda:100)
            self.assertEqual(r['exit_code'],1);self.assertFalse(r['Close_attempted']);self.assertEqual(len(calls),1)
            changed={**expected,'output':str(root/'other')};a.update(output=changed['output'])
            with self.assertRaises(FileExistsError):entry.consume_nonce(root,raw,a)
    def test_CLI_cannot_be_enabled_or_mock_bypassed(self):
        for args in [['--execute','--authorization','ANY'],['--worker'],['--execute','--plan']]:
            with patch.object(sys,'argv',['ENTRY',*args]),patch.object(entry,'native_link',side_effect=AssertionError('NO_SDK')),redirect_stdout(io.StringIO()):
                self.assertEqual(entry.main(),2)
        with patch.object(sys,'argv',['ENTRY','--execute','--mock']),redirect_stdout(io.StringIO()),redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit) as cm:entry.main()
            self.assertEqual(cm.exception.code,2)
    def test_all_M0_runs_reused_and_unknown_refused(self):
        matrix=json.loads(entry.MATRIX.read_text())
        for run in matrix['execution_order']:self.assertFalse(entry.plan(run['run_id'])['enabled'])
        with self.assertRaises(ValueError):entry.plan('G3_OLD')
    def test_artifact_drift_rejected_before_device(self):
        with tempfile.TemporaryDirectory() as f:
            p=Path(f)/'fake.bin';p.write_bytes(bytes(41012))
            with self.assertRaisesRegex(ValueError,'ARTIFACT'):entry.validate_bundle({'BIN':str(p)})


class Capture(unittest.TestCase):
    def test_full_virtual165_capture_and_real_stable_reader_review(self):
        parent=Path(os.environ.get('M1_TEST_ROOT',tempfile.gettempdir()))
        with tempfile.TemporaryDirectory(dir=parent) as f:
            root=Path(f);clock=Clock();link=FakeLink(clock);helper=Authorization()
            raw,sig,key,pin,expected,_=helper.signed(root/'session')
            r=entry.run_authorized_capture(raw,sig,key,pin,expected,reference(),lambda *_:link,root,
                clock=clock,sleep=clock.sleep,now=lambda:100)
            self.assertEqual(r['exit_code'],0,r);self.assertLessEqual(r['capture_host_s'],185)
            self.assertEqual(link.closes,1);self.assertEqual(r['post_Close_state'],'UNKNOWN_NOT_OBSERVED')
            result=review.review(root/'session',root/'review','M1-E60-R1')
            self.assertEqual(result['exit_code'],0,result);self.assertEqual(result['correct_valid_slots'],120)
            self.assertGreater(result['raw_evaluation_frames'],29980);self.assertGreater(result['RESP50_evaluation_frames'],5990)
            block=root/'session/B/blocks-private.bin'
            data=bytearray(block.read_bytes());data[0]^=1;block.write_bytes(data)
            with self.assertRaisesRegex(ValueError,'CAPTURE_FILE_SHA'):review.review(root/'session',root/'changed-review','M1-E60-R1')
    def test_open_native_and_Close_paths(self):
        for fault in ['OpenEx','Device','Connect','negative','timeout','firmware','ROM','HALT','Close','Close_timeout']:
            with self.subTest(fault=fault),tempfile.TemporaryDirectory() as f:
                clock=Clock();link=FakeLink(clock,fault)
                if fault in ('Close','Close_timeout'):
                    # 在预检失败后走同一finally，避免为Close负例重复165秒文件生成。
                    ref=reference();ref['identity']={}
                else:ref=reference()
                r=entry.capture_window(lambda *_:link,Path(f)/'s',ref,clock=clock,sleep=clock.sleep)
                self.assertEqual(r['exit_code'],1,r);self.assertEqual(link.closes,1)
                if fault=='Close':self.assertFalse(r['Close_completed'])
                if fault=='Close_timeout':self.assertTrue(r['Close_completed']);self.assertEqual(r['close_error_type'],'ValueError')
    def test_operator_stop_and_stale_cold_boot(self):
        for kind in ['STOP','stale']:
            with tempfile.TemporaryDirectory() as f:
                root=Path(f);clock=Clock();link=FakeLink(clock);ref=reference()
                if kind=='stale':ref['maximum_cold_start_uptime_ms']=1
                def factory(b,out):
                    if kind=='STOP':(out/'STOP').touch()
                    return link
                r=entry.capture_window(factory,root/'s',ref,clock=clock,sleep=clock.sleep)
                self.assertEqual(r['exit_code'],4 if kind=='STOP' else 1,r)
                self.assertFalse(link.close_resume_enabled)

    def _closing_stop_timing(self,moment):
        parent=Path(os.environ.get('M1_TEST_ROOT',tempfile.gettempdir()))
        gate=entry.link_class().gate
        with tempfile.TemporaryDirectory(dir=parent) as f:
            root=Path(f);clock=Clock();events=[]
            class StopLink(FakeLink):
                def __init__(self):
                    super().__init__(clock);self.root=root/'s';self.phase='preflight'
                    self.started=clock();self.deadline=75;self.error=False;self.injected=False
                def inject(self):
                    (self.root/'STOP').touch();self.injected=True;events.append('STOP')
                def read(self,address,size):
                    if self.phase=='closing' and moment=='final-state' and not self.injected:self.inject()
                    gate(self)
                    if self.injected:events.append('ordinary-read-after-STOP')
                    data=super().read(address,size);gate(self);return data
                def set_close_resume(self,yes):
                    if yes and self.final_close_verified:
                        if moment=='resume-policy' and not self.injected:self.inject()
                        gate(self)
                        if self.injected:events.append('resume-policy-after-STOP')
                    return super().set_close_resume(yes)
                def close(self):events.append('Close');return super().close()
            link=StopLink()
            with patch.object(entry.time,'monotonic',clock):
                result=entry.capture_window(lambda *_:link,root/'s',reference(),clock=clock,sleep=clock.sleep)
            detail={'moment':moment,'result':result,'events':events,'Close_calls':link.closes,
                    'close_resume_enabled':link.close_resume_enabled,'real_SDK_calls':0}
            if 'M1_TEST_ROOT' in os.environ:
                (parent/('closing-STOP-'+moment+'.json')).write_text(json.dumps(detail,indent=2)+'\n')
            self.assertTrue(link.injected)
            self.assertEqual(result['exit_code'],4,detail)
            self.assertEqual(result['reason'],'M1_OPERATOR_STOP')
            self.assertNotIn('ordinary-read-after-STOP',events)
            self.assertNotIn('resume-policy-after-STOP',events)
            self.assertFalse(link.close_resume_enabled)
            self.assertEqual(link.closes,1)
            self.assertTrue(result['Close_attempted'])
            self.assertEqual(result['post_Close_state'],'UNKNOWN_NOT_OBSERVED')
            self.assertEqual(result['native_side_effects'],'UNRESOLVED')

    def test_closing_STOP_before_final_state_read(self):self._closing_stop_timing('final-state')

    def test_closing_STOP_before_restart_on_Close_policy(self):self._closing_stop_timing('resume-policy')


def rows_and_diagnostics():
    rows=[(s,s*4,200,100,0,(s*672000)&0xffffffff,0xc00000) for s in range(1,41251)]
    diagnostics=[]
    for offset in range(0,165000,500):
        d=bio(0);d['last_sample_ms']=4+offset;d['discontinuities']=0
        d['adc']={k:0 for k in ['init_errors','bad_status','spi_errors','queue_overflow','long_gap_count']}
        diagnostics.append({'bio':d,'CAN':{k:0 for k in ['error','overflow','discontinuities','comm_reset']}})
    return rows,diagnostics,{'seq':1,'ms':4}


class Evaluation(unittest.TestCase):
    def test_review_CLI_bad_signature_returns_input_exit2(self):
        parent=Path(os.environ.get('M1_TEST_ROOT',tempfile.gettempdir()))
        with tempfile.TemporaryDirectory(dir=parent) as f:
            root=Path(f);session=root/'session';(session/'B').mkdir(parents=True)
            raw,sig,key,pin,expected,a=Authorization().signed(session);sig=b'bad-signature'
            (session/'authorization-private.json').write_bytes(raw)
            (session/'authorization-signature.bin').write_bytes(sig);(session/'authorization-public-key.bin').write_bytes(key)
            (session/'B/receipt-private.json').write_text(json.dumps({'exit_code':0,'Close_completed':True}))
            (session/'authorization-binding-private.json').write_text(json.dumps({'run_id':'M1-E60-R1','nonce_ledger_consumed':True,
                'authorization_sha256':entry.sha(raw),'signature_sha256':entry.sha(sig),'public_key_sha256':entry.sha(key)}))
            with patch.object(sys,'argv',['REVIEW','--session',str(session),'--out',str(root/'out'),'--run-id','M1-E60-R1']),redirect_stdout(io.StringIO()):
                self.assertEqual(review.main(),2)
    def test_baseline_and_RR_HR_truth_unknown(self):
        rows,diags,anchor=rows_and_diagnostics()
        for cond,target in [('E60',60),('R15',15)]:
            r=review.evaluate(rows,diags,anchor,cond,target)
            self.assertEqual(r['exit_code'],0);self.assertEqual(r['raw_evaluation_frames'],30000)
            self.assertEqual(r['RESP50_evaluation_frames'],6000);self.assertFalse(r['whole_RR_window_PASS'])
            if cond=='R15':self.assertIn('UNRESOLVED',r['HR_truth']);self.assertEqual(r['HR_valid_native_observations'],240)
    def test_earliest_slot_never_selects_later_valid(self):
        rows,diags,anchor=rows_and_diagnostics()
        for d in diags:
            if (d['bio']['last_sample_ms']-4)>=45000 and (d['bio']['last_sample_ms']-4)%1000==0:d['bio']['hr_valid']=0
        r=review.evaluate(rows,diags,anchor,'E60',60)
        self.assertEqual(r['correct_valid_slots'],0);self.assertEqual(r['exit_code'],3)
    def test_missing_slots_118_boundary_and_extra_outlier(self):
        rows,diags,anchor=rows_and_diagnostics()
        subset=[d for d in diags if not 45000<=d['bio']['last_sample_ms']-4<47000]
        self.assertEqual(review.evaluate(rows,subset,anchor,'E60',60)['correct_valid_slots'],118)
        subset=[d for d in subset if not 47000<=d['bio']['last_sample_ms']-4<48000]
        self.assertEqual(review.evaluate(rows,subset,anchor,'E60',60)['exit_code'],3)
        diags[91]['bio']['hr']=80
        self.assertIn('VALID_VALUE_OUT_OF_TOLERANCE',review.evaluate(rows,diags,anchor,'E60',60)['engineering_failures'])
    def test_raw_sequence_tick_flags_irq_and_diag_errors(self):
        rows,diags,anchor=rows_and_diagnostics()
        variants=[rows[:100]+rows[101:],rows[:100]+[(*rows[100][:1],rows[100][1]-10,*rows[100][2:])]+rows[101:],
                  rows[:100]+[(*rows[100][:4],1,*rows[100][5:])]+rows[101:],
                  rows[:100]+[(*rows[100][:5],rows[99][5],rows[100][6])]+rows[101:]]
        for variant in variants:self.assertEqual(review.evaluate(variant,diags,anchor,'E60',60)['exit_code'],2)
        d=copy.deepcopy(diags);d[100]['bio']['adc']['spi_errors']=1
        self.assertEqual(review.evaluate(rows,d,anchor,'E60',60)['exit_code'],2)
        d=copy.deepcopy(diags);d[100]['bio']['last_sample_ms']=d[99]['bio']['last_sample_ms']
        self.assertEqual(review.evaluate(rows,d,anchor,'E60',60)['exit_code'],2)
    def test_supervisor_kill_preserves_native_exit(self):
        for mode in ['STOP','native','hard']:
            with tempfile.TemporaryDirectory() as f:
                root=Path(f);(root/'B').mkdir();clock=Clock()
                if mode=='STOP':(root/'STOP').touch()
                if mode=='native':(root/'B/heartbeat-events.jsonl').write_text(json.dumps({'active':True,'deadline_monotonic':-.1})+'\n')
                class Child:
                    def poll(self):return None
                    def kill(self):pass
                    def wait(self,timeout):return -9
                r=entry.watch_worker(Child(),root,clock=clock,sleep=clock.sleep)
                self.assertEqual(r['worker_native_exit_code'],-9);self.assertEqual(r['supervisor_exit_code'],4)
                self.assertEqual(r['Close_completed'],'UNKNOWN_PROCESS_KILLED')
    def test_monitor_failure_terminates_child_and_preserves_error(self):
        with tempfile.TemporaryDirectory() as f:
            root=Path(f);(root/'B').mkdir();(root/'B/heartbeat-events.jsonl').write_text('{}\n')
            calls=[]
            class Child:
                def poll(self):return None
                def kill(self):calls.append('kill')
                def wait(self,timeout):return -9
            with patch.object(Path,'read_text',side_effect=PermissionError('SYNTHETIC_MONITOR_ERROR')):
                r=entry.watch_worker(Child(),root)
            self.assertEqual(calls,['kill']);self.assertEqual(r['worker_native_exit_code'],-9)
            self.assertEqual(r['supervisor_exit_code'],2);self.assertEqual(r['monitor_error_type'],'PermissionError')


class Adapter(unittest.TestCase):
    def test_inherited_native_negative_and_short_reads(self):
        from b5_g3_devices import BLink
        for native,code in [(-3,'NATIVE_READ_ERROR'),(3,'POSITIVE_SHORT_READ')]:
            obj=type('Reader',(),{'allowed_reads':{1:{4}},'call':lambda self,*args,**kwargs:native})()
            with self.subTest(native=native),self.assertRaisesRegex(ValueError,code):BLink.read(obj,1,4)
    def test_m1_budget_and_forbidden_API_before_DLL(self):
        cls=entry.link_class();obj=object.__new__(cls);obj.phase='capture';obj.sdk_calls=20000
        with self.assertRaisesRegex(ValueError,'SDK_BUDGET'):obj.call('JLINKARM_OpenEx')
        obj.sdk_calls=0
        for name in ['JLINKARM_Reset','JLINKARM_Halt','JLINKARM_Go','JLINKARM_WriteMem']:
            with self.assertRaisesRegex(ValueError,'API_DENIED'):obj.call(name)


if __name__=='__main__':unittest.main(verbosity=2)
