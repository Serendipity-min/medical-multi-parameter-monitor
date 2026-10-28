"""gen5最小差异、NOR提交/回退、授权与G3绑定；全部离线。"""
import contextlib
import io
import json
from pathlib import Path
import struct
import sys
import tempfile
import unittest
from unittest.mock import Mock,patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import b5_gen5_plan as plan
import b5_gen5_writer as writer
import b5_g3_contract as g
import b5_sector3_write_protocol as protocol
from test_b5_sector3_write import fixture,NorIO


class Tests(unittest.TestCase):
    def setUp(self):
        original,app,_,files,identity,options=fixture();self.original=original;self.current=files['expected-full-B5-new-config-private.bin'];self.options=options
        self.identity=json.dumps(identity).encode();self.wifi={'ssid':'NEW_SYNTHETIC24','password':'NEW_SYNTHETIC_KEY'}
        self.patches=[patch.object(plan.p,'APP_SHA',plan.sha(app[:42552])),patch.object(plan.p,'CURRENT_FULL_SHA',plan.sha(original))]
        for p in self.patches:p.start();self.addCleanup(p.stop)
        self.manifest,self.files=plan.build(self.current,original,self.wifi,options,self.identity)
    def test_only_wifi_generation_crc_changes_and_full_restore_equal(self):
        after=self.files['gen5-full-private.bin'];before=self.current
        self.assertEqual(before[:49152],after[:49152]);self.assertEqual(before[65536:],after[65536:])
        self.assertEqual(before[49488:65536],after[49488:65536]);self.assertEqual(plan.non_wifi(before[49152:49488]),plan.non_wifi(after[49152:49488]))
        self.assertEqual(plan.p.parse_record(after[49152:49488])[0],5)
        self.assertEqual(self.original[:49152]+self.files['B5-gen3-full-private.bin'][49152:],self.original)
    def test_wifi_no_change_invalid_string_and_gen_drift_refused(self):
        _,_,old=plan.p.parse_record(self.current[49152:49488])
        with self.assertRaises(ValueError):plan.wifi_record(self.current[49152:49488],{'ssid':old['ssid'],'password':old['wifi_password']})
        for wifi in ({'ssid':'bad\nAT','password':'ok'},{'ssid':'x'*33,'password':'ok'}):
            with self.assertRaises(ValueError):plan.wifi_record(self.current[49152:49488],wifi)
        with self.assertRaises(ValueError):plan.wifi_record(self.files['gen5-record-private.bin'],self.wifi)
    def engine(self,reverse=False,original=False,**kw):
        before=self.files['gen5-full-private.bin'] if reverse else self.current
        after=(self.files['B5-gen3-full-private.bin'] if original else self.current) if reverse else self.files['gen5-full-private.bin']
        stage=plan.stage(after[49152:65536]);mem=NorIO(before,self.options)
        klass=writer.OriginalConfigEngine if original else writer.WifiEngine
        return klass(mem,before,after,stage,self.options,'restore_config' if reverse else 'provision',**kw),mem
    def test_one_erase_single_commit_last_forward_and_two_reverse_objects(self):
        for reverse,original in ((False,False),(True,False),(True,True)):
            engine,mem=self.engine(reverse,original);result=engine.run(engine.before,self.options)
            self.assertEqual(bytes(mem.flash),engine.after);self.assertEqual((engine.erases,engine.commits),(1,1))
            writes=[x for x in mem.writes if protocol.BASE<=x[0]<protocol.END]
            self.assertEqual(writes[-1],(protocol.COMMIT,0x54494d43,'COMMIT'));self.assertEqual(result['all_Download_APIs'],0)
    def test_original_engine_does_not_gain_gen5_permission(self):
        after=self.files['gen5-full-private.bin'];mem=NorIO(self.current,self.options)
        with self.assertRaises(ValueError):protocol.Engine(mem,self.current,after,plan.stage(after[49152:65536]),self.options,'provision')
        self.assertFalse(mem.writes)
    def test_MQTT_or_epoch_change_rejected_even_with_valid_CRC(self):
        for offset in (28,130,195,228,293):
            after=bytearray(self.files['gen5-full-private.bin']);after[49152+offset]^=1
            record=bytearray(after[49152:49488]);struct.pack_into('<I',record,16,plan.p.record_crc(record));after[49152:49488]=record
            mem=NorIO(self.current,self.options)
            with self.assertRaises(ValueError):writer.WifiEngine(mem,self.current,bytes(after),plan.stage(after[49152:65536]),self.options,'provision')
            self.assertFalse(mem.writes)
    def test_drift_corruption_and_insufficient_commit_budget_never_fake_success(self):
        engine,mem=self.engine()
        with self.assertRaises(ValueError):engine.run(bytes(1048576),self.options)
        self.assertFalse(mem.writes)
        for attr in ('corrupt_erase','corrupt_stage'):
            engine,mem=self.engine();setattr(mem,attr,True)
            with self.assertRaises(ValueError):engine.run(engine.before,self.options)
            self.assertEqual(engine.commits,0)
        engine,mem=self.engine(timeout_s=100)
        with self.assertRaises(ValueError):engine.run(engine.before,self.options)
        self.assertEqual(engine.commits,0)
    def test_disabled_or_old_scope_never_constructs_SDK(self):
        with patch.object(sys,'argv',['gen5']),patch.object(writer.old,'NativeLink') as native,contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(writer.main(),0);native.assert_not_called()
        for a in ({},{'enabled':True,'owner_approved':True,'scope':writer.old.PROVISION}):
            with self.assertRaises(ValueError):writer.authorize(a,Path('.'))

    def test_authorization_separates_current_site_scope_exception_time_gates_and_images(self):
        import time
        import copy
        site={'JLink_target':'C','latest_power_state_checked':True,'A_bus_disconnected':True,'no_human':True,
            'C_power_ready':True,'USB_and_CAN_state_frozen':True,'BOOT_and_RESET_untouched':True,
            'ESP_present_powered':True,'ESP_isolated':False,'ESP_autonomous_network':'UNKNOWN'}
        raw=json.dumps(site).encode();gates={}
        for key,status in [('SNTP','TIME_CLEAN_PASS'),('NTP','FRESH_PUBLIC_NTP_PASS')]:
            payload=json.dumps({'status':status,'exit_code':0,'cleanup_verified':True,'Close_completed':True}).encode()
            gates[key]={'path':key,'sha256':plan.sha(payload),'data':payload}
        a={'enabled':True,'owner_approved':True,'scope':'B5_GEN5_WIFI_WRITE','phase':'provision','board':'C',
            'tools_sha256':{},'DLL_sha256':writer.ro.raw.DLL_SHA,'expires_unix':time.time()+60,
            'card_sha256':plan.sha((g.ROOT/'node-b/docs'/writer.CARD).read_bytes()),'session_timeout_s':180,
            'probe_sessions':1,'retries':0,'Halt_max':1,'reset_max':1,'Go_max':1,'erase_max':1,'commit_max':1,
            'nonhuman_mock':True,'failure_cleanup_scope':'PG_CLEAR_CR_LOCK_AND_ORIGINAL_ACR_IF_IDLE_ONLY',
            'output':'unused','site_record':'SITE','site_record_sha256':plan.sha(raw),'ESP_isolated':False,
            'ESP_autonomous_network':'UNKNOWN','ESP_present_powered_exception_approved':True,
            'ESP_exception_scope':'B5_GEN5_WIFI_WRITE','entry_runtime_state_hex':'00000000',
            'gate_receipts':gates,'package':'SYNTHETIC','package_manifest_sha256':'SYNTHETIC',
            'before_full_sha256':plan.sha(self.current),'after_full_sha256':plan.sha(self.files['gen5-full-private.bin'])}
        reads={'SITE':raw,**{k:v['data'] for k,v in gates.items()}}
        with patch.object(writer,'bindings',return_value={}),patch.object(writer.recovery,'read',side_effect=lambda p,_:reads[str(p)]),\
                patch.object(writer.recovery,'protected',side_effect=lambda p,_:p),\
                patch.object(writer,'load_package',return_value=(self.manifest,self.files)),patch.object(writer.old,'NativeLink') as native:
            self.assertEqual(writer.authorize(a,Path('unused'))[4],self.files['gen5-full-private.bin'])
            for key,value in [('expires_unix',0),('probe_sessions',2),('ESP_present_powered_exception_approved',False),
                    ('ESP_exception_scope','OLD'),('ESP_isolated',True),('before_full_sha256','BAD'),('entry_runtime_state_hex','01010101')]:
                bad=copy.deepcopy(a);bad[key]=value
                with self.subTest(key=key),self.assertRaises(ValueError):writer.authorize(bad,Path('unused'))
            for key in ('SNTP','NTP'):
                bad=copy.deepcopy(a);bad['gate_receipts'][key]['sha256']='BAD'
                with self.subTest(gate=key),self.assertRaises(ValueError):writer.authorize(bad,Path('unused'))
            site['latest_power_state_checked']=False;reads['SITE']=json.dumps(site).encode();a['site_record_sha256']=plan.sha(reads['SITE'])
            with self.assertRaises(ValueError):writer.authorize(a,Path('unused'))
            native.assert_not_called()

    def test_gen5_supervisor_uses_gen5_backend_without_consuming_old_scope(self):
        import b5_sector3_write_supervisor as supervisor
        from types import SimpleNamespace
        with tempfile.TemporaryDirectory() as temp:
            base=Path(temp);out=base/'output';auth=base/'auth.json';auth.write_text('{"scope":"B5_GEN5_WIFI_WRITE"}')
            fake=SimpleNamespace(returncode=0,poll=lambda:0,wait=lambda **_:0)
            with patch.object(writer,'authorize',return_value=None),patch.object(writer.recovery,'protected',side_effect=lambda p,_:Path(p)),\
                    patch.object(supervisor.subprocess,'Popen',return_value=fake) as popen,contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(supervisor.supervise(auth,out,backend=writer),0)
            self.assertEqual(popen.call_args.args[0][3],str(Path(writer.__file__).resolve()))
            self.assertEqual(json.loads(auth.with_suffix('.used').read_text())['scope'],'B5_GEN5_WIFI_WRITE')
    def write_package(self,folder):
        for name,blob in self.files.items():(folder/name).write_bytes(blob)
        raw=(json.dumps(self.manifest,indent=2)+'\n').encode();(folder/'manifest-private.json').write_bytes(raw)
        return plan.sha(raw)
    def test_package_full_rebuild_and_unlisted_file_rejected(self):
        with tempfile.TemporaryDirectory() as temp,patch.object(writer.recovery,'protected',side_effect=lambda p,_:Path(p)):
            folder=Path(temp);checksum=self.write_package(folder)
            manifest,files=writer.load_package(folder,checksum);self.assertEqual(files,self.files)
            (folder/'extra.bin').write_bytes(b'x')
            with self.assertRaises(ValueError):writer.load_package(folder,checksum)
    def test_G3_legacy_guard_stays_and_gen5_needs_real_install_receipt(self):
        self.assertEqual(g.expected_c_full({},{}),g.C_FULL)
        with self.assertRaises(Exception):g.expected_c_full({'configuration_generation':5},{})
        expected=plan.sha(self.files['gen5-full-private.bin']);a={'configuration_generation':5,'gen5_package':'SYNTHETIC',
            'gen5_package_manifest_sha256':'MANIFEST','gen5_install_receipt':'SYNTHETIC','gen5_install_receipt_sha256':''}
        receipt={'status':'SECTOR3_FULL_VERIFY_AND_DISARMED_BOOT_PASS','exit_code':0,'scope':'B5_GEN5_WIFI_WRITE',
            'Close_completed':True,
            'configuration_generation':5,'after_full_sha256':expected,'package_manifest_sha256':'MANIFEST'}
        with patch.object(writer,'load_package',return_value=(self.manifest,self.files)):
            for ok in (True,False):
                receipt['exit_code']=0 if ok else 1;raw=json.dumps(receipt).encode();a['gen5_install_receipt_sha256']=plan.sha(raw)
                with patch.object(g.private,'read',return_value=raw):
                    if ok:self.assertEqual(g.expected_c_full(a,{'C_full':{'sha256':expected}}),expected)
                    else:
                        with self.assertRaises(Exception):g.expected_c_full(a,{'C_full':{'sha256':expected}})


if __name__=='__main__':unittest.main()
