"""专用writer离线：真实实现状态机配NOR/MEMAP假身，不加载J-Link DLL。"""
import ctypes
import io
import json
from pathlib import Path
import struct
import subprocess
import sys
import tempfile
import time
import types
import unittest
from unittest.mock import patch, Mock
import zlib

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/'node-b/tools'))
import b5_sector3_plan as planner
import b5_sector3_package as package
import b5_sector3_write as writer
import b5_sector3_write_protocol as p
import b5_sector3_write_supervisor as supervisor


def fixture():
    record = bytearray(336); struct.pack_into('<IHHIIII', record, 0, 0x32433348,1,24,312,3,0,0x54494d43)
    struct.pack_into('<II', record,24,0x31435747,1700000000)
    fields = {'ssid':'SYNTHETIC_SSID', 'wifi_password':'SYNTHETIC_WIFI_KEY','host':'old.example.invalid',
              'username':'SYNTHETIC_OLD','password':'SYNTHETIC_OLD_KEY','client_id':'SYNTHETIC_OLD_ID'}
    for key, offset, width in planner.FIELDS:
        data=fields[key].encode();record[24+offset:24+offset+len(data)]=data
    struct.pack_into('<I',record,16,planner.record_crc(record))
    original=bytearray(b'\xff'*1048576);original[49152:49488]=record
    app=bytearray(b'\x5a'*42552);struct.pack_into('<II',app,0,0x20020000,0x08000101)
    installed=bytes(app)+bytes(original[42552:]);original=bytes(original)
    mqtt={'gateway_id':'GW-B5-001','username':'b5-gateway','client_id':'b5-c-isolated',
          'host':'broker.example.invalid','password':'SYNTHETIC_NEVER_REAL','port':8883}
    with patch.object(planner,'CURRENT_FULL_SHA',planner.sha(original)),patch.object(planner,'APP_SHA',planner.sha(app)):
        manifest,files=planner.build_plan(original,installed,mqtt)
    identity={'cpuid':0x410fc241,'device_id':0x10000413,'capacity_kib':1024,'uid_hex':'5a'*12,
              'optcr':0x0fffaaed,'flash_sr':0}
    return original,installed,manifest,files,identity,b'\xaa\x55'*8


class NorIO:
    def __init__(self,before,options):
        self.flash=bytearray(before);self.options=options;self.reg={p.CR:p.LOCK,p.SR:0,p.ACR:0x600}
        self.guard=None;self.writes=[];self.reads=[];self.erase_count=0;self.key=[]
        self.corrupt_erase=False;self.corrupt_stage=False;self.corrupt_final=False;self.option_drift=False
        self.busy_after_erase=False;self.program_fail=False
    def bind_guard(self,guard):self.guard=guard;self.engine=guard.__self__
    def read32(self,address):return self.reg.get(address,0)
    def write32(self,address,value):
        self.guard(address,value);self.writes.append((address,value,self.engine.phase))
        if address==p.KEYR:
            self.key.append(value)
            if self.key[-2:]==[0x45670123,0xcdef89ab]:self.reg[p.CR]&=~p.LOCK
        elif address==p.CR:
            self.reg[p.CR]=value
            if value==p.ERASE_START:
                assert not value&4 and value&2 and (value>>3)&15==3
                self.flash[49152:65536]=b'\xff'*16384;self.erase_count+=1;self.reg[p.CR]&=~0x10000
                if self.corrupt_erase:self.flash[50000]=0
                if self.busy_after_erase:self.reg[p.SR]=p.BUSY
        elif address==p.SR:self.reg[p.SR]&=~value
        elif address==p.ACR:self.reg[p.ACR]=value
        else:
            assert self.reg[p.CR]==p.PROGRAM and p.BASE<=address<p.END and address%4==0
            if self.program_fail:raise OSError('synthetic_native_failure')
            offset=address-0x08000000;old=int.from_bytes(self.flash[offset:offset+4],'little')
            assert old&value==value
            self.flash[offset:offset+4]=value.to_bytes(4,'little')
    def read(self,address,size):
        self.reads.append((address,size,self.engine.phase,self.reg[p.ACR]))
        if address==0x1fffc000:return bytes(16) if self.option_drift else self.options
        start=address-0x08000000;data=bytes(self.flash[start:start+size])
        if address==p.BASE and size==16384 and self.engine.phase=='STAGE_VERIFY' and self.corrupt_stage:
            return data[:-1]+bytes([data[-1]^1])
        if address==0x08000000 and size==1048576 and self.corrupt_final:return bytes([data[0]^1])+data[1:]
        return data


class APBus:
    def __init__(self,header):
        self.select=0xa0;self.csw=0x23000052;self.tar=0x20001000;self.idr=0x24770011
        self.memory={0xe000ed00:0x410fc241,p.CR:p.LOCK,p.SR:0}
        self.memory.update({0x08000000+i:int.from_bytes(header[i:i+4],'little') for i in range(0,64,4)})
        self.read_dp2=0;self.grant=None;self.effects=[];self.fail_write=False
    def read(self,reg,ap):
        if not ap:
            self.read_dp2+=1;return 0xdeadbeef  # RESEND不是SELECT。
        if reg==0:return self.csw
        if reg==1:return self.tar
        if reg==3:return self.idr if self.select==0xf0 else self.memory.get(self.tar,0)
        raise AssertionError('wrong AP index')
    def write(self,reg,ap,value):
        if not ap:self.select=value;return
        if reg==0:self.csw=value;return
        if reg==1:self.tar=value;return
        assert reg==3 and self.select==0 and self.csw&0x37==2 and self.grant==(self.tar,value)
        if self.fail_write:raise OSError('synthetic DAP failure')
        self.effects.append((self.tar,value));self.memory[self.tar]=value
    def grant_target_write(self,address,value):self.grant=None if address is None else(address,value)


class FakeLink:
    def __init__(self,out,before,options,identity):
        self.out=out;self.before=before;self.options=options;self.identity=identity;self.halted=False
        self.verified_running_flash=False;self.close_resume_enabled=False;self.before_verified=False
        self.actions={};self.started=time.monotonic();self.full_reads=0;self.option_reads=0
        self.before_second_bad=False;self.after_second_bad=False;self.armed_after_halt=False
        self.runtime_entry=bytes(4)
        self.after=None;self.writes=[]
    def open(self):writer.ro.raw.write_json(self.out/'probe-status-private.json',{'voltage_mv':3300})
    def set_close_resume(self,v):self.close_resume_enabled=v
    def u32(self,address):
        d={0xe000ed00:self.identity['cpuid'],0xe0042000:self.identity['device_id'],0x40023c14:self.identity['optcr'],
           p.CR:p.LOCK,p.SR:0,writer.ro.SYSTEM['DHCSR']:writer.ro.raw.HALT if self.halted else 0,
           writer.ro.SYSTEM['DWT_PCSR']:0x08000101,writer.ro.SYSTEM['VTOR']:0x08000000,
           writer.RCC_CR:1<<17,writer.RCC_CFGR:5}
        return d.get(address,0)
    def read(self,address,size):
        if address==0x1fff7a10:return bytes.fromhex(self.identity['uid_hex'])
        if address==0x1fff7a22:return (1024).to_bytes(2,'little')
        if address==writer.RAM_STATE:return b'\x01\0\0\0' if self.halted and self.armed_after_halt else self.runtime_entry
        if address==0x1fffc000:self.option_reads+=1;return self.options
        if address==0x08000000 and size==1048576:
            self.full_reads+=1;data=self.after if self.after is not None else self.before
            bad=(self.before_second_bad and self.full_reads==2) or (self.after_second_bad and self.full_reads==4)
            return data[:-1]+bytes([data[-1]^1]) if bad else data
        if address in (0,0x08000000) and size==64:return self.before[:64]
        return self.u32(address).to_bytes(size,'little')
    def call(self,name,*args,**kwargs):
        self.actions[name]=self.actions.get(name,0)+1
        if name=='JLINKARM_Halt':self.halted=True;return 0
        if name=='JLINKARM_IsConnected':return 1
        if name=='JLINKARM_CORESIGHT_Configure':return 0
        raise AssertionError(name)
    def stable_halt(self):assert self.halted
    def policy(self,command):pass


class Tests(unittest.TestCase):
    def setUp(self):
        (ROOT/'node-b/build').mkdir(exist_ok=True)
        self.temp=tempfile.TemporaryDirectory(dir=ROOT/'node-b/build',prefix='s3-writer-test-');self.addCleanup(self.temp.cleanup)
        self.out=Path(self.temp.name);self.original,self.before,self.manifest,self.files,self.identity,self.options=fixture()
    def engine(self,phase='provision',**kwargs):
        before,after,stage=self.before,self.files['expected-full-B5-new-config-private.bin'],self.files['sector3-uncommitted-private.bin']
        if phase=='restore_config':
            before,after=after,self.before;old=self.files['sector3-original-private.bin'];stage=old[:20]+b'\xff'*4+old[24:]
        mem=NorIO(before,self.options);engine=p.Engine(mem,before,after,stage,self.options,phase,**kwargs)
        return engine,mem
    def loaded(self):return({}, {'options-private.bin':self.options},self.identity,self.before,self.files['expected-full-B5-new-config-private.bin'],self.files['sector3-uncommitted-private.bin'])
    def run_execute(self,link,**patches):
        with patch.object(writer.recovery,'protected',side_effect=lambda path,_:Path(path)),patch.object(planner,'APP_SHA',planner.sha(self.before[:42552])):
            return writer.execute(link,self.out,{'phase':'provision','entry_runtime_state_hex':'00000000'},self.loaded())

    def formal_fixture(self):
        before = self.files['expected-full-B5-new-config-private.bin']
        mqtt = {'gateway_id': 'GW-C-001', 'username': 'gateway-c', 'client_id': 'gw-c-001', 'port': 8883,
                'host': 'formal.example.invalid', 'password': 'SYNTHETIC_FORMAL_ONLY'}
        manifest, blobs = package.formal_plan(before, mqtt)
        after = blobs['expected-full-committed-private.bin']
        stage = blobs['sector3-uncommitted-private.bin']
        return manifest, blobs, before, after, stage

    def test_formal_manifest_and_fresh_backup_bind_authorization(self):
        manifest, blobs, before, after, _ = self.formal_fixture()
        pkg = self.out/'formal-package'; pkg.mkdir()
        raw = writer.recovery.encoded(manifest)
        for name, blob in {**blobs, 'manifest-private.json': raw}.items():
            (pkg/name).write_bytes(blob)
        backup = self.out/'backup'; probe = backup/'probe'; probe.mkdir(parents=True)
        proof = {'board': 'C', 'exit_code': 0, 'Close_completed': True, 'independent_reads_match': True,
                 'full_sha256': writer.sha(before), 'options_sha256': writer.sha(self.options)}
        (backup/'receipt-private.json').write_bytes(writer.recovery.encoded(proof))
        for i in (1, 2):
            (probe/f'flash-{i}-private.bin').write_bytes(before)
            (probe/f'options-{i}-private.bin').write_bytes(self.options)
        for f in ('identity-private.json', 'identity-after-private.json'):
            (probe/f).write_bytes(writer.recovery.encoded(self.identity))
        card = self.out/'card'; card.write_bytes(b'SYNTHETIC_CARD')
        site = self.out/'site'
        site.write_bytes(writer.recovery.encoded({'JLink_target': 'C', **dict.fromkeys(
            ('latest_power_state_checked', 'other_boards_off', 'no_human', 'C_power_ready',
             'hotspot_off', 'USB_and_CAN_state_frozen', 'BOOT_and_RESET_untouched'), True)}))
        out = self.out/'capture'
        auth = {'enabled': True, 'owner_approved': True, 'scope': writer.FORMAL, 'board': 'C', 'phase': 'provision',
                'tools_sha256': writer.bindings(True), 'DLL_sha256': writer.ro.raw.DLL_SHA,
                'expires_unix': time.time()+60, 'card': str(card), 'card_sha256': writer.sha(card.read_bytes()),
                'session_timeout_s': 180, 'probe_sessions': 1, 'retries': 0, 'output': str(out),
                'site_record': str(site), 'site_record_sha256': writer.sha(site.read_bytes()),
                'package': str(pkg), 'package_manifest_sha256': writer.sha(raw), 'backup': str(backup),
                'before_full_sha256': writer.sha(before), 'after_full_sha256': writer.sha(after)}
        with patch.object(writer.recovery, 'protected', side_effect=lambda path, _: Path(path)):
            self.assertEqual(writer.authorize(auth, out, True)[3:5], (before, after))
            with self.assertRaisesRegex(ValueError, 'OWNER_AUTH_REQUIRED'):
                writer.authorize(auth, out)
            (probe/'flash-2-private.bin').write_bytes(before[:-1]+b'\x00')
            with self.assertRaisesRegex(ValueError, 'FORMAL_BACKUP_SOURCE_SHA'):
                writer.authorize(auth, out, True)
            tampered = pkg/'sector3-uncommitted-private.bin'
            tampered.write_bytes(tampered.read_bytes()[:-1]+b'\x00')
            with self.assertRaisesRegex(ValueError, 'FORMAL_REBUILT_PACKAGE_DRIFT'):
                writer.load_formal_package(pkg, writer.sha(raw))

    def test_formal_live_sha_drift_before_and_after_halt_never_reaches_flash_engine(self):
        manifest, blobs, before, after, stage = self.formal_fixture()
        loaded = (manifest, {**blobs, 'options-private.bin': self.options}, self.identity, before, after, stage)
        for phase in ('before', 'halted'):
            out = self.out/phase; out.mkdir()
            link = FakeLink(out, before, self.options, self.identity)
            original = link.read
            def read(address, size):
                result = original(address, size)
                if size == 1048576 and (phase == 'before' or link.halted):
                    return result[:-1]+b'\x00'
                return result
            link.read = read
            with patch.object(writer.recovery, 'protected', side_effect=lambda path, _: Path(path)):
                with patch.object(writer, 'NativeIO') as native, self.assertRaisesRegex(
                    ValueError, 'CURRENT_FULL_OR_OPTIONS_DRIFT' if phase == 'before' else 'FORMAL_SOURCE_CHANGED_AFTER_HALT'):
                    writer.execute(link, out, {'scope': writer.FORMAL, 'phase': 'provision'}, loaded)
                native.assert_not_called()
            self.assertNotIn('JLINKARM_Reset', link.actions)

    def test_formal_executes_only_sector3_and_requires_exact_committed_full_readback(self):
        manifest, blobs, before, after, stage = self.formal_fixture()
        loaded = (manifest, {**blobs, 'options-private.bin': self.options}, self.identity, before, after, stage)
        for corrupt in (False, True):
            out = self.out/str(corrupt); out.mkdir()
            link = FakeLink(out, before, self.options, self.identity)
            mem = NorIO(before, self.options); mem.corrupt_final = corrupt
            original = link.read
            def read(address, size):
                if mem.guard is not None and mem.engine.phase == 'DONE':
                    link.after = bytes(mem.flash)
                return original(address, size)
            link.read = read
            bridge = Mock(); bridge.read32.side_effect = link.u32; bridge.probe.return_value = {'synthetic': True}
            with patch.object(writer.recovery, 'protected', side_effect=lambda path, _: Path(path)), \
                    patch.object(writer, 'DapBridge', return_value=bridge), patch.object(writer, 'NativeIO', return_value=mem):
                if corrupt:
                    with self.assertRaisesRegex(ValueError, 'FINAL_FULL_OR_OPTIONS_DRIFT'):
                        writer.execute(link, out, {'scope': writer.FORMAL, 'phase': 'provision'}, loaded)
                else:
                    result = writer.execute(link, out, {'scope': writer.FORMAL, 'phase': 'provision'}, loaded)
                    self.assertEqual(result['status'], 'FORMAL_SECTOR3_FULL_VERIFY_PASS')
                    self.assertEqual((out/'after-full-2-private.bin').read_bytes(), after)
            self.assertEqual(bytes(mem.flash), after)
            self.assertEqual(mem.erase_count, 1)
            self.assertEqual([a for a, _, _ in mem.writes if 0x08000000 <= a < p.BASE or p.END <= a < 0x08100000], [])
            self.assertNotIn('JLINKARM_Reset', link.actions)
            self.assertNotIn('JLINKARM_Go', link.actions)

    def test_one_erase_stage1_verified_before_single_commit_and_caches_off(self):
        engine,mem=self.engine();result=engine.run(engine.before,self.options)
        self.assertEqual((mem.erase_count,engine.erases,engine.commits),(1,1,1));self.assertEqual(bytes(mem.flash),engine.after)
        data=[row for row in mem.writes if p.BASE<=row[0]<p.END]
        self.assertEqual(data[-1],(p.COMMIT,0x54494d43,'COMMIT'))
        self.assertTrue(all(a!=p.COMMIT for a,_,phase in data if phase=='PROGRAM'))
        self.assertTrue(all(not acr&0x400 for addr,size,phase,acr in mem.reads if addr in (p.BASE,0x08000000)))
        self.assertEqual(mem.reg[p.ACR],0x600);self.assertEqual(mem.reg[p.CR],p.LOCK)
        self.assertEqual(result['all_Download_APIs'],0)

    def test_RCFG_is_separate_reverse_phase_and_still_only_sector3(self):
        engine,mem=self.engine('restore_config');engine.run(engine.before,self.options)
        self.assertEqual(bytes(mem.flash),self.before);self.assertEqual(mem.erase_count,1)
        with self.assertRaises(ValueError):p.Engine(mem,engine.before,engine.after,engine.stage,self.options,'provision')

    def test_baseline_and_initial_SR_faults_never_unlock(self):
        engine,mem=self.engine()
        with self.assertRaisesRegex(ValueError,'BEFORE_DRIFT'):engine.run(bytes(1048576),self.options)
        self.assertEqual(mem.writes,[])
        engine,mem=self.engine();mem.reg[p.SR]=0x10
        with self.assertRaisesRegex(ValueError,'INITIAL_ERROR'):engine.run(engine.before,self.options)
        self.assertEqual(mem.writes,[])

    def test_wrong_erase_stage1_or_tail_never_commits(self):
        for name in ('corrupt_erase','corrupt_stage'):
            engine,mem=self.engine();setattr(mem,name,True)
            with self.subTest(name=name),self.assertRaises(ValueError):engine.run(engine.before,self.options)
            self.assertEqual(engine.commits,0)
            engine.failure_lock();self.assertEqual(mem.reg[p.CR],p.LOCK);self.assertEqual(mem.reg[p.ACR],0x600)

    def test_no_commit_without_final_read_time_reserve(self):
        engine,mem=self.engine(timeout_s=109)
        with self.assertRaisesRegex(ValueError,'SESSION_TIMEOUT'):engine.run(engine.before,self.options)
        self.assertEqual(engine.commits,0)

    def test_second_erase_early_repeat_or_wrong_commit_and_outside_writes_denied(self):
        engine,mem=self.engine();engine.run(engine.before,self.options)
        for address,value in [(p.BASE-4,0),(p.END,0),(0x40023c08,0),(0x40023c14,0),(0xe000ed08,0),(p.BASE+1,0)]:
            with self.assertRaises(ValueError):engine.authorize_write(address,value)
        engine.phase='ERASE_START'
        with self.assertRaises(ValueError):engine.authorize_write(p.CR,p.ERASE_START)
        engine.phase='COMMIT'
        with self.assertRaises(ValueError):engine.authorize_write(p.COMMIT,0x54494d43)
        other,_=self.engine();other.erase_completed=True;other.phase='COMMIT'
        with self.assertRaisesRegex(ValueError,'COMMIT_DENIED'):other.authorize_write(p.COMMIT,0x54494d43)

    def test_native_data_failure_does_not_retry_or_reerase_and_cleanup_has_no_NVM_writes(self):
        engine,mem=self.engine();mem.program_fail=True
        with self.assertRaises(OSError):engine.run(engine.before,self.options)
        count=len([x for x in mem.writes if p.BASE<=x[0]<p.END]);engine.failure_lock()
        self.assertEqual(len([x for x in mem.writes if p.BASE<=x[0]<p.END]),count)
        self.assertEqual(engine.erases,1);self.assertEqual(engine.commits,0)
        self.assertEqual(mem.reg[p.CR],p.LOCK);self.assertEqual(mem.reg[p.ACR],0x600)

    def test_busy_cleanup_refuses_any_further_control_write(self):
        engine,mem=self.engine();mem.reg[p.SR]=p.BUSY;before=list(mem.writes)
        with self.assertRaisesRegex(ValueError,'BUSY_NO_CLEANUP'):engine.failure_lock()
        self.assertEqual(mem.writes,before)

    def test_final_full_or_options_drift_is_failure_even_after_commit(self):
        for key in ('corrupt_final','option_drift'):
            engine,mem=self.engine();setattr(mem,key,True)
            with self.assertRaisesRegex(ValueError,'FINAL_FULL_OR_OPTIONS'):engine.run(engine.before,self.options)
            self.assertEqual(engine.commits,1)

    def test_raw_bridge_never_reads_DP_SELECT_and_restores_readable_state(self):
        bus=APBus(self.before[:64]);bridge=p.DapBridge(bus)
        result=bridge.probe(0x410fc241,self.before[:64],p.LOCK,0)
        self.assertEqual(bus.read_dp2,0);self.assertEqual((bus.select,bus.csw,bus.tar),(0,0x23000052,0x20001000))
        self.assertEqual(bus.effects,[]);self.assertTrue(result['AP_CSW_TAR_restored_SELECT_canonical0'])
        bridge.guard=lambda address,value:p.require(address==p.KEYR and value==0x45670123,'SYNTHETIC_SCOPE')
        bridge.write32(p.KEYR,0x45670123);self.assertEqual(bus.effects,[(p.KEYR,0x45670123)])
        self.assertEqual((bus.select,bus.csw,bus.tar),(0,0x23000052,0x20001000))

    def test_raw_bridge_wrong_AP_CPUID_or_flash_head_fails_before_target_write(self):
        for field in ('AP','CPUID','Flash'):
            bus=APBus(self.before[:64])
            if field=='AP':bus.idr=0x24770012
            if field=='CPUID':bus.memory[0xe000ed00]^=1
            if field=='Flash':bus.memory[0x08000000]^=1
            bridge=p.DapBridge(bus)
            with self.subTest(field=field),self.assertRaises(ValueError):bridge.probe(0x410fc241,self.before[:64],p.LOCK,0)
            self.assertFalse(bridge.proven);self.assertEqual(bus.effects,[])

    def test_raw_bridge_exception_preserves_no_grant_and_canonical_state(self):
        bus=APBus(self.before[:64]);bridge=p.DapBridge(bus);bridge.probe(0x410fc241,self.before[:64],p.LOCK,0)
        bridge.guard=lambda a,v:None;bus.fail_write=True
        with self.assertRaises(OSError):bridge.write32(p.KEYR,0x45670123)
        self.assertIsNone(bus.grant);self.assertEqual(bus.select,0);self.assertTrue(bridge.state_restored)

    def native_stub(self):
        link=object.__new__(writer.NativeLink);link.sdk_calls=0;link.sdk_limit=100
        link.actions={};link.native_policy_counts={};link.before_verified=link.post_verified=link.boot_vector_verified=False
        link.verified_running_flash=False;link.register_reads_allowed=False;link.raw_target_grant=None
        link.dap_select=0;link.dap_csw=2;link.dap_tar=p.KEYR;link.gate=lambda:None
        link.events=io.StringIO();link.io=io.StringIO();link.dll=types.SimpleNamespace()
        return link

    def test_all_high_level_flash_writes_PC_and_DP2_reads_denied_before_native(self):
        link=self.native_stub()
        for name in ('JLINKARM_BeginDownload','JLINKARM_EndDownload','JLINKARM_WriteMem','JLINKARM_WriteMemEx','JLINKARM_WriteU32','JLINKARM_WriteReg'):
            with self.assertRaisesRegex(ValueError,'FUNCTION_DENIED'):link.call(name)
        with self.assertRaises(ValueError):link.call('JLINKARM_ReadReg',0)
        with self.assertRaisesRegex(ValueError,'SELECT_IS_NOT_READABLE'):link.call('JLINKARM_CORESIGHT_ReadAPDPReg',2,0,ctypes.byref(ctypes.c_uint32()))
        self.assertTrue(link.raw_failed)
        with self.assertRaisesRegex(ValueError,'RAW_STOP_LATCHED'):link.call('JLINKARM_CORESIGHT_WriteAPDPReg',3,1,0x45670123)
        self.assertEqual(link.sdk_calls,0)
        link=self.native_stub()
        with self.assertRaisesRegex(ValueError,'DRW_NOT_GRANTED'):link.call('JLINKARM_CORESIGHT_WriteAPDPReg',3,1,0x45670123)
        self.assertEqual(link.sdk_calls,0)

    def test_native_API_negative_result_retained_and_no_host_retry(self):
        link=self.native_stub();calls=[]
        link.dll.JLINKARM_CORESIGHT_WriteAPDPReg=lambda *a:(calls.append(a) or -17)
        with self.assertRaisesRegex(ValueError,'NATIVE_ERROR'):writer.NativeBus(link).write(2,False,0)
        self.assertEqual(len(calls),1);self.assertIn('-17',link.io.getvalue())

    def test_before_second_read_drift_or_posthalt_armed_change_zero_flash_unlock(self):
        for field in ('before_second_bad','armed_after_halt'):
            folder=self.out/field;folder.mkdir();link=FakeLink(folder,self.before,self.options,self.identity);setattr(link,field,True)
            with patch.object(writer.recovery,'protected',side_effect=lambda path,_:Path(path)),patch.object(planner,'APP_SHA',planner.sha(self.before[:42552])):
                with self.subTest(field=field),self.assertRaises(ValueError):writer.execute(link,folder,{'phase':'provision','entry_runtime_state_hex':'00000000'},self.loaded())
            self.assertFalse(hasattr(link,'active_engine'));self.assertEqual(link.writes,[])
            self.assertNotIn('JLINKARM_CORESIGHT_Configure',link.actions)

    def test_after_second_read_drift_retains_both_and_never_resets_or_goes(self):
        link=FakeLink(self.out,self.before,self.options,self.identity);link.after_second_bad=True
        fake_bridge=Mock();fake_bridge.read32.side_effect=link.u32;fake_bridge.probe.return_value={'synthetic':True}
        fake_engine=Mock();fake_engine.phase='DONE'
        def finish(before,options):
            link.after=self.files['expected-full-B5-new-config-private.bin']
            fake_engine.verified_full=link.read(0x08000000,1048576)
            fake_engine.verified_options=link.read(0x1fffc000,16)
            return {'synthetic_engine':True}
        fake_engine.run.side_effect=finish
        with patch.object(writer,'DapBridge',return_value=fake_bridge),patch.object(writer,'Engine',return_value=fake_engine):
            with self.assertRaisesRegex(ValueError,'AFTER_DOUBLE_READ_MISMATCH'):self.run_execute(link)
        self.assertEqual(link.full_reads,4);self.assertEqual(link.option_reads,4)
        self.assertNotEqual((self.out/'after-full-1-private.bin').read_bytes(),(self.out/'after-full-2-private.bin').read_bytes())
        self.assertNotIn('JLINKARM_Reset',link.actions);self.assertNotIn('JLINKARM_Go',link.actions)

    def test_wrong_private_UID_never_reads_whole_flash_or_halts(self):
        link=FakeLink(self.out,self.before,self.options,{**self.identity,'uid_hex':'6b'*12})
        with self.assertRaisesRegex(ValueError,'WRONG_UID_OR_PROTECTION'):self.run_execute(link)
        self.assertEqual(link.full_reads,0);self.assertNotIn('JLINKARM_Halt',link.actions)

    def test_provision_and_RCFG_authorizations_cannot_be_borrowed(self):
        for scope,phase in [(writer.PROVISION,'restore_config'),(writer.RESTORE,'provision')]:
            a={'enabled':True,'owner_approved':True,'scope':scope,'phase':phase,'board':'C',
               'tools_sha256':{},'DLL_sha256':writer.ro.raw.DLL_SHA,'expires_unix':time.time()+60}
            with patch.object(writer,'bindings',return_value={}),self.assertRaisesRegex(ValueError,'SCOPE_PHASE'):
                writer.authorize(a,self.out/'unused')

    def test_RCFG_can_readgate_declared_stopped_closed_state_without_reset(self):
        new=self.files['expected-full-B5-new-config-private.bin'];old=self.files['sector3-original-private.bin']
        link=FakeLink(self.out,new,self.options,self.identity);link.runtime_entry=bytes.fromhex('00000101')
        loaded=({}, {'options-private.bin':self.options},self.identity,new,self.before,old[:20]+b'\xff'*4+old[24:])
        with patch.object(writer.recovery,'protected',side_effect=lambda path,_:Path(path)),patch.object(planner,'APP_SHA',planner.sha(self.before[:42552])),patch.object(writer,'DapBridge',side_effect=ValueError('SYNTHETIC_AFTER_READ_GATE')) as bridge:
            with self.assertRaisesRegex(ValueError,'SYNTHETIC_AFTER_READ_GATE'):
                writer.execute(link,self.out,{'phase':'restore_config','entry_runtime_state_hex':'00000101'},loaded)
            self.assertEqual(bridge.call_count,1)
        self.assertEqual(link.actions.get('JLINKARM_Halt'),1)
        self.assertNotIn('JLINKARM_Reset',link.actions);self.assertNotIn('JLINKARM_Go',link.actions)
        self.assertFalse(hasattr(link,'active_engine'))

    def test_active_armed_network_or_mqtt_states_not_valid_entry_authorizations(self):
        for value in ('00000001','00010001','01000001','01010101'):
            with self.subTest(value=value),self.assertRaisesRegex(ValueError,'RUNTIME_STATE_NOT_ALLOWED'):
                writer.entry_runtime_state({'phase':'restore_config','entry_runtime_state_hex':value})
        with self.assertRaises(ValueError):writer.entry_runtime_state({'phase':'provision','entry_runtime_state_hex':'00000101'})

    def test_actual_active_state_does_not_match_declared_safe_state_and_never_halts(self):
        for index,value in enumerate(('00000001','00010001','01000001')):
            out=self.out/str(index);out.mkdir();link=FakeLink(out,self.before,self.options,self.identity)
            link.runtime_entry=bytes.fromhex(value)
            with patch.object(writer.recovery,'protected',side_effect=lambda path,_:Path(path)),patch.object(planner,'APP_SHA',planner.sha(self.before[:42552])):
                with self.assertRaisesRegex(ValueError,'RUNTIME_STATE_MISMATCH'):
                    writer.execute(link,out,{'phase':'provision','entry_runtime_state_hex':'00000000'},self.loaded())
            self.assertNotIn('JLINKARM_Halt',link.actions)

    def test_RCFG_stopped_state_still_requires_explicit_ESP_exception(self):
        site={'JLink_target':'C','latest_power_state_checked':True,'ESP_electrically_isolated':False,
              'A_bus_disconnected':True,'no_human':True,'C_power_ready':True,'USB_and_CAN_state_frozen':True,'BOOT_and_RESET_untouched':True}
        raw=json.dumps(site).encode()
        a={'enabled':True,'owner_approved':True,'scope':writer.RESTORE,'phase':'restore_config','board':'C',
           'entry_runtime_state_hex':'00000101','tools_sha256':{},'DLL_sha256':writer.ro.raw.DLL_SHA,
           'expires_unix':time.time()+60,'session_timeout_s':180,'probe_sessions':1,'retries':0,
           'failure_cleanup_scope':'PG_CLEAR_CR_LOCK_AND_ORIGINAL_ACR_IF_IDLE_ONLY','nonhuman_mock':True,
           'card_sha256':writer.sha((ROOT/'node-b/docs'/writer.CARDS['restore_config']).read_bytes()),
           'output':str(self.out/'unused'),'site_record':'SYNTHETIC_SITE','site_record_sha256':writer.sha(raw)}
        with patch.object(writer,'bindings',return_value={}),patch.object(writer.recovery,'read',return_value=raw),patch.object(writer,'load_package') as load:
            with self.assertRaisesRegex(ValueError,'TRANSACTION_ESP_EXCEPTION_REQUIRED'):writer.authorize(a,self.out/'unused')
            load.assert_not_called()

    def package_fixture(self):
        folder=self.out/'package';folder.mkdir()
        blobs=dict(self.files)
        blobs.update({'original-full-private.bin':self.original,'app-before-private.bin':self.before,
                      'options-private.bin':self.options,'identity-private.json':writer.recovery.encoded(self.identity),
                      'manifest-private.json':writer.recovery.encoded(self.manifest)})
        binding={'schema':'B5_SECTOR3_BOUND_PACKAGE_V1','files':{n:{'bytes':len(b),'sha256':writer.sha(b)} for n,b in blobs.items()},
            'hardware_execution_enabled':False,'latest_power_state_recheck_required':True,
            'source_fresh_read_binding_sha256':writer.FRESH_SHA,'restore_order_for_execution':'R_CFG_FIRST_THEN_SEPARATELY_AUTHORIZED_R_APP',
            'runtime_state':{'address':writer.RAM_STATE,'bytes':4,'disarmed_expected_hex':'00000000','ELF_sha256':writer.ELF_SHA,'symbols_sha256':writer.SYMBOL_SHA},
            'planner_sha256':writer.sha(Path(planner.__file__).read_bytes()),'plan_manifest_sha256':writer.sha(blobs['manifest-private.json']),
            'generation_from':3,'generation_to':4,'minimum_epoch':1700000000,'gateway_id':'GW-B5-001','username':'b5-gateway',
            'client_id':'b5-c-isolated','port':8883,'source_original_full_sha256':writer.sha(self.original),'source_app_full_sha256':writer.sha(self.before)}
        for name,blob in blobs.items():(folder/name).write_bytes(blob)
        return folder,binding

    def load_fixture(self,folder,binding):
        blob=writer.recovery.encoded(binding);(folder/'binding-private.json').write_bytes(blob)
        with patch.object(writer.recovery,'protected',side_effect=lambda path,_:Path(path)),patch.object(writer.recovery,'read',side_effect=lambda path,_:Path(path).read_bytes()),patch.object(planner,'CURRENT_FULL_SHA',writer.sha(self.original)),patch.object(planner,'APP_SHA',writer.sha(self.before[:42552])),patch.object(writer.ro,'OPTIONS_SHA',writer.sha(self.options)):
            return writer.load_package(folder,writer.sha(blob))

    def test_package_rebuilt_bytes_and_forged_manifest_not_trusted(self):
        folder,binding=self.package_fixture();self.assertEqual(self.load_fixture(folder,binding)[2],self.identity)
        name='sector3-uncommitted-private.bin';data=(folder/name).read_bytes();data=data[:-1]+b'\x00';(folder/name).write_bytes(data)
        binding['files'][name]={'bytes':len(data),'sha256':writer.sha(data)}
        manifest=json.loads((folder/'manifest-private.json').read_bytes());manifest['files'][name]['sha256']=writer.sha(data)
        raw=writer.recovery.encoded(manifest);(folder/'manifest-private.json').write_bytes(raw)
        binding['files']['manifest-private.json']={'bytes':len(raw),'sha256':writer.sha(raw)};binding['plan_manifest_sha256']=writer.sha(raw)
        with self.assertRaisesRegex(ValueError,'REBUILT_PLAN_DRIFT'):self.load_fixture(folder,binding)

    def test_package_extra_file_or_payload_hash_drift_rejected(self):
        folder,binding=self.package_fixture();(folder/'extra').write_text('SYNTHETIC_ONLY')
        with self.assertRaisesRegex(ValueError,'EXTRA_FILES'):self.load_fixture(folder,binding)
        (folder/'extra').unlink();(folder/'options-private.bin').write_bytes(bytes(16))
        with self.assertRaisesRegex(ValueError,'PAYLOAD_SHA'):self.load_fixture(folder,binding)

    def test_disabled_authorization_and_default_plan_never_construct_native(self):
        with patch.object(writer,'NativeLink') as native:
            with self.assertRaisesRegex(ValueError,'OWNER_AUTH_REQUIRED'):writer.authorize({},self.out/'capture')
            with patch.object(sys,'argv',['writer']),patch('sys.stdout',io.StringIO()):self.assertEqual(writer.main(),0)
            with patch.object(sys,'argv',['supervisor']),patch('sys.stdout',io.StringIO()):self.assertEqual(supervisor.main(),0)
            native.assert_not_called()

    def sleeping_child(self):
        child=subprocess.Popen([sys.executable,'-c','import time; time.sleep(10)'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
        self.addCleanup(lambda:child.kill() if child.poll() is None else None);return child

    def test_supervisor_total_deadline_kills_child_without_reconnect(self):
        child=self.sleeping_child();result=supervisor.watch(child,self.out,timeout_s=.03)
        self.assertEqual(result['reason'],'SESSION_TIMEOUT');self.assertNotEqual(result['worker_exit_code'],0)
        self.assertEqual(result['target_state'],'UNKNOWN_NO_RECONNECT_CLEANUP')

    def test_supervisor_native_deadline_and_owner_stop(self):
        heartbeat=self.out/'heartbeat-events.jsonl';heartbeat.write_text(json.dumps({'active':True,'deadline_monotonic':time.monotonic()-1})+'\n')
        self.assertEqual(supervisor.watch(self.sleeping_child(),self.out)['reason'],'NATIVE_CALL_TIMEOUT')
        heartbeat.unlink();(self.out/'STOP').touch()
        self.assertEqual(supervisor.watch(self.sleeping_child(),self.out)['reason'],'OWNER_STOP')


if __name__=='__main__':unittest.main(verbosity=2)
