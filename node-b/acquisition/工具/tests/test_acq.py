# 公开副本：全部设备身份为合成夹具，不能用于绑定真实板卡。
"""普通脱机回归：合成槽、模拟调试进程及失败路径；禁止访问真实 J-Link。"""
from contextlib import contextmanager
import csv
import hashlib
import json
import re
from pathlib import Path
import struct
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from acq import import_files, main
from acq_protocol import dump_strict_json, load_strict_json, sha256_file
from acq_storage import create_run, offline_precheck, seal_run, verify_package, within
from acq_processing import export_run, compare_dataset, validate_run
from acq_swd import capture_run, JLinkClient, HALTED
from stable_slot_export import StableSlots


def slot(seq, raw=-12345, ms=None, cycles=None, flags=0):
    # 构造与实际 ABI 相同的 24 B，包括 signed 24-bit 大端及 u32 小端。
    return (b'\xc0\x00\x00' + (raw & 0xffffff).to_bytes(3,'big')
            + (raw & 0xffffff).to_bytes(3,'big') + bytes([flags])+b'\x00\x00'
            + struct.pack('<III', seq, cycles if cycles is not None else seq*672000,
                          ms if ms is not None else seq*4))


def ring(count=32):
    blob = bytearray(3072)
    for i in range(count):
        blob[i*24:(i+1)*24] = slot(i+1)
    return bytes(blob)


def ram(count=32):
    blob = bytearray(131072)
    struct.pack_into('<I', blob, 0x1c4, count)
    blob[0x2038:0x2038+3072] = ring(count)
    struct.pack_into('<12I', blob, 0x20c, count,count,count,0,0,0,4,0,0,672000,672000,10000)
    struct.pack_into('<i', blob, 0xbc, -12345)
    return bytes(blob)


class Cases(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='acq-脱机-')
        self.root = Path(self.temp.name)

    def tearDown(self):
        self.temp.cleanup()

    def new(self, kind='INTERNAL_TEST_SIGNAL'):
        return create_run(self.root/'dataset', 'sample-a', 'condition-a', kind, '合成夹具', duration=1, warmup=0, uid='00000000-00000000-00000001')

    def imported(self):
        run = self.new('SOFTWARE_FIXTURE')
        source = self.root/'source'
        source.mkdir()
        (source/'slot_0000.bin').write_bytes(ring())
        (source/'slot_0001.bin').write_bytes(ring())
        (source/'state_0000.bin').write_bytes(ram()[:2048])
        (source/'paused.bin').write_bytes(ram())
        analysis, quality = import_files(run, source, source/'paused.bin', True)
        return run, analysis, quality

    def test_offline_precheck_synthetic_bound_artifacts(self):
        # 公开包不含现场BIN/ELF。使用明确的合成文件验证SHA和符号绑定，
        # 不把这些测试字节称作真实ARM产物，不修改实际profile的验收规则。
        run = self.new()
        profile = load_strict_json(run/'adapter_profile.json')
        symbol_entries = {}
        for field in profile['symbol_table']:
            name, address, size = field['c_symbol'], int(field['address'], 0), field['byte_length']
            if name.startswith('s_stats.'):
                name, address, size = 's_stats', 0x2000020c, 0x30
            else:
                array = re.fullmatch(r'(\w+)\[(\d+)\]', name)
                if array:
                    name, index = array.group(1), int(array.group(2))
                    address -= index * size
                    size *= index + 1
            key = name, address
            symbol_entries[key] = max(symbol_entries.get(key, 0), size)
        symbols = '\n'.join(f'{name} 0x{address:08x} SYNTHETIC 0x{size:x}'
                            for (name, address), size in symbol_entries.items())
        files = {'bin': self.root/'synthetic.bin', 'elf': self.root/'synthetic.elf',
                 'symbol_file': self.root/'synthetic-symbols.txt'}
        files['bin'].write_bytes(b'SYNTHETIC_NOT_FIRMWARE')
        files['elf'].write_bytes(b'SYNTHETIC_NOT_ELF')
        files['symbol_file'].write_text(symbols, encoding='utf-8')
        for key, path in files.items():
            profile['firmware_binding'][key+'_sha256'] = sha256_file(path)
        dump_strict_json(profile, run/'adapter_profile.json')
        session = load_strict_json(run/'session.json')
        session['tool']['adapter_profile_sha256'] = sha256_file(run/'adapter_profile.json')
        session['tool']['symbol_file_sha256'] = profile['firmware_binding']['symbol_file_sha256']
        session['firmware'].update(bin_sha256=profile['firmware_binding']['bin_sha256'],
                                   elf_sha256=profile['firmware_binding']['elf_sha256'])
        dump_strict_json(session, run/'session.json')
        args = run, files['bin'], files['elf'], files['symbol_file']
        self.assertEqual(offline_precheck(*args)['status'], 'PASS_OFFLINE_ONLY')
        files['bin'].write_bytes(b'CHANGED_SYNTHETIC_BYTES')
        with self.assertRaises(ValueError):
            offline_precheck(*args)

    def test_init_no_overwrite_and_no_hardware(self):
        run = self.new()
        with self.assertRaises(FileExistsError):
            create_run(run.parent.parent, 'x', 'x','UNKNOWN','unknown',run_id=run.name)
        self.assertFalse((run/'raw_manifest.json').exists())

    def test_strict_repeated_conflict_even_unequal_votes(self):
        c = StableSlots(False)
        c.versions[1] = __import__('collections').Counter({slot(1,1): 3, slot(1,2): 2})
        selected = c.select()
        self.assertNotIn(1, selected.frames)
        self.assertIn(1, selected.multi_repeat_conflicts)

    def test_single_conflict_with_repeated_version_is_retained(self):
        c = StableSlots(False)
        c.versions[1] = __import__('collections').Counter({slot(1,1): 3, slot(1,2): 1})
        selected = c.select()
        self.assertEqual(selected.frames[1], slot(1,1))
        self.assertIn(1, selected.conflicts)

    def test_empty_and_nonzero_invalid_separated(self):
        c = StableSlots(False)
        blob = bytearray(3072)
        blob[24] = 1
        c.add_running_chunk(blob)
        self.assertEqual((c.empty_zero_slots,c.invalid_nonzero_slots), (127,1))

    def test_partial_block_rejected(self):
        with self.assertRaises(ValueError):
            StableSlots().add_running_chunk(bytes(3071))

    def test_tail_excludes_active_write_slot(self):
        c = StableSlots(False)
        blob = bytearray(3072)
        for i in range(128):
            blob[i*24:(i+1)*24] = slot(i+1)
        blob[0:24] = slot(129)
        c.add_paused_snapshot(blob,128)
        self.assertNotIn(129,c.select().frames)
        self.assertEqual(len(c.select().frames),127)

    def test_paused_does_not_override_repeated_conflict(self):
        c = StableSlots(False)
        c.versions[1] = __import__('collections').Counter({slot(1,1): 3, slot(1,2): 2})
        c.atomic[1] = slot(1,1)
        self.assertNotIn(1,c.select().frames)

    def test_import_signed_samples_states_and_hashes(self):
        run, analysis, quality = self.imported()
        self.assertEqual(quality['integrity']['status'],'PASS')
        self.assertEqual(quality['identity']['status'],'UNKNOWN')
        self.assertEqual(quality['accuracy']['status'],'NOT_EVALUATED_WITHOUT_REFERENCE')
        with (analysis/'samples.csv').open(encoding='utf-8',newline='') as f:
            rows=list(csv.DictReader(f))
        self.assertEqual(len(rows),64)
        self.assertEqual(int(rows[0]['raw_code']),-12345)
        with (analysis/'firmware_state.csv').open(encoding='utf-8',newline='') as f:
            states=list(csv.DictReader(f))
        resp=[r for r in states if r['module']=='resp_algorithm' and r['field']=='s_filtered']
        self.assertEqual(int(resp[0]['value']),-12345)
        self.assertEqual(validate_run(run)['analyses'][0]['sample_events'],32)
        self.assertIn(b'\r\n',(analysis/'samples.csv').read_bytes())

    def test_raw_drift_refuses_reanalysis(self):
        run, _, _=self.imported()
        (run/'raw/slot_0000.bin').write_bytes(b'bad')
        with self.assertRaises(ValueError):
            export_run(run)

    def test_reanalysis_preserves_all_previous_artifacts(self):
        run, first, _=self.imported()
        original=sha256_file(first/'samples.csv')
        second,_=export_run(run)
        self.assertNotEqual(first.name,second.name)
        self.assertEqual(original,sha256_file(first/'samples.csv'))
        self.assertEqual(original,sha256_file(second/'samples.csv'))

    def test_bad_identity_not_used_in_waveform_comparison(self):
        run, _, _=self.imported()
        output=compare_dataset(run.parent.parent,self.root/'comparison','waveform')
        with (output/'comparison.csv').open(encoding='utf-8',newline='') as f:
            rows=list(csv.DictReader(f))
        self.assertEqual(rows[0]['status'],'EXCLUDED')

    def test_missing_final_keeps_pending(self):
        run=self.new('SOFTWARE_FIXTURE')
        (run/'raw/slot_0000.bin').write_bytes(ring())
        dump_strict_json({'status':'IMPORT_COMPLETED','identity_status':'UNKNOWN'},run/'acquisition_receipt.json')
        seal_run(run)
        _,q=export_run(run)
        self.assertEqual(q['integrity']['pending'],32)
        self.assertEqual(q['integrity']['status'],'INCOMPLETE')

    def test_sequence_gap_preserved(self):
        run=self.new('SOFTWARE_FIXTURE')
        blob=bytearray(3072)
        blob[:24]=slot(1)
        blob[24:48]=slot(3)
        for i in range(2):
            (run/f'raw/slot_{i}.bin').write_bytes(blob)
        dump_strict_json({'status':'IMPORT_COMPLETED'},run/'acquisition_receipt.json')
        seal_run(run)
        _,q=export_run(run)
        self.assertEqual(q['integrity']['missing_in_selected_span'],1)
        self.assertEqual(q['integrity']['status'],'INCOMPLETE')

    def test_wrap_is_not_false_time_reversal(self):
        run=self.new('SOFTWARE_FIXTURE')
        blob=bytearray(3072)
        blob[:24]=slot(1,ms=0xfffffffe,cycles=0xfffffff0)
        blob[24:48]=slot(2,ms=2,cycles=(0xfffffff0+672000)&0xffffffff)
        for i in range(2):
            (run/f'raw/slot_{i}.bin').write_bytes(blob)
        dump_strict_json({'status':'IMPORT_COMPLETED'},run/'acquisition_receipt.json')
        seal_run(run)
        _,q=export_run(run)
        seg=q['timebase']['segments'][0]
        self.assertEqual((seg['span_us'],seg['dwt_wraps']), (4000,1))

    def test_reset_ambiguity_not_merged(self):
        run=self.new('SOFTWARE_FIXTURE')
        for i,seq in enumerate([1000,1000,1,1]):
            blob=bytearray(3072)
            blob[:24]=slot(seq)
            (run/f'raw/slot_{i}.bin').write_bytes(blob)
        dump_strict_json({'status':'IMPORT_COMPLETED'},run/'acquisition_receipt.json')
        seal_run(run)
        _,q=export_run(run)
        self.assertEqual(q['integrity']['distinct_sample_events'],0)
        self.assertTrue(q['integrity']['boot_ambiguity'])

    def test_time_ambiguity_creates_new_segment_without_filling_gap(self):
        run=self.new('SOFTWARE_FIXTURE')
        blob=bytearray(3072)
        blob[:24]=slot(1,ms=10,cycles=100)
        blob[24:48]=slot(2,ms=30010,cycles=200)
        for i in range(2):
            (run/f'raw/slot_{i}.bin').write_bytes(blob)
        dump_strict_json({'status':'IMPORT_COMPLETED'},run/'acquisition_receipt.json')
        seal_run(run)
        _,q=export_run(run)
        self.assertEqual(len(q['timebase']['segments']),2)
        self.assertEqual(q['integrity']['status'],'LIMITED')

    def test_source_flags_kept_without_zeroing(self):
        run=self.new('SOFTWARE_FIXTURE')
        blob=bytearray(3072)
        blob[:24]=slot(1,flags=3)
        for i in range(2):
            (run/f'raw/slot_{i}.bin').write_bytes(blob)
        dump_strict_json({'status':'IMPORT_COMPLETED'},run/'acquisition_receipt.json')
        seal_run(run)
        analysis,q=export_run(run)
        self.assertEqual(q['integrity']['flags_nonzero_samples'],1)
        self.assertEqual(q['integrity']['status'],'LIMITED')
        with (analysis/'samples.csv').open(encoding='utf-8',newline='') as stream:
            self.assertEqual(next(csv.DictReader(stream))['source_flags_raw'],'3')

    def test_old_tool_identity_not_accepted(self):
        run=self.new()
        obj=load_strict_json(run/'session.json')
        obj['tool']['files_sha256']['acq.py']='0'*64
        dump_strict_json(obj,run/'session.json')
        with self.assertRaises(ValueError):
            offline_precheck(run)

    def test_setpoint_preserved_without_fake_accuracy_or_sync(self):
        run=create_run(self.root/'dataset','a','a','ACTIVE_HARDWARE_SIMULATOR','declared generator',
                       duration=1,warmup=0,hr_setpoint=60,resp_setpoint=15)
        for i in range(2):
            (run/f'raw/slot_{i}.bin').write_bytes(ring())
        dump_strict_json({'status':'IMPORT_COMPLETED'},run/'acquisition_receipt.json')
        seal_run(run)
        analysis,q=export_run(run)
        self.assertEqual(q['accuracy']['status'],'NOT_EVALUATED_REFERENCE_ANALYSIS_NOT_IMPLEMENTED')
        with (analysis/'reference.csv').open(encoding='utf-8',newline='') as stream:
            rows=list(csv.DictReader(stream))
        self.assertEqual([r['value'] for r in rows],['60','15'])
        self.assertTrue(all(r['device_time_us']=='' for r in rows))

    def test_manifest_traversal_and_self_reference_rejected(self):
        run=self.new()
        with self.assertRaises(ValueError):
            within(run,'../other')
        dump_strict_json({'files':[{'path':'raw_manifest.json','size_bytes':0,'sha256':'x'}]},run/'raw_manifest.json')
        with self.assertRaises(ValueError):
            verify_package(run)

    def test_capture_requires_nonhuman_and_explicit_confirmation(self):
        with self.assertRaises(ValueError):
            capture_run(self.new('HUMAN_DECLARED'),Path(__file__),True)
        with self.assertRaises(ValueError):
            capture_run(self.new(),Path(__file__),False)

    def fake_capture(self, mismatch=False, bad_resume=False, timeout=False):
        run=self.new()
        profile=load_strict_json(run/'adapter_profile.json')
        profile['firmware_binding']['flash_1mib_sha256']=hashlib.sha256(b'X'*1048576).hexdigest()
        dump_strict_json(profile,run/'adapter_profile.json')
        session=load_strict_json(run/'session.json')
        session['tool']['adapter_profile_sha256']=sha256_file(run/'adapter_profile.json')
        dump_strict_json(session,run/'session.json')
        now=[0.0]
        self.commands=[]
        owner=self
        class FakeClient:
            def __init__(self,executable,raw,prefix):
                self.raw=raw
                self.last_status=0
                self.command_count=0
            def command(self,command='',timeout=8,file=None):
                owner.commands.append(command)
                self.command_count+=1
                if command=='h':
                    self.last_status=HALTED
                if command=='g':
                    self.last_status=HALTED if bad_resume and 'h' in owner.commands else 0
                text=''
                if '1FFF7A10' in command:
                    text='1FFF7A10 = '+('00000000 00000000 00000000' if mismatch else '00000000 00000000 00000001')
                if 'E0042000' in command:
                    text='E0042000 = 10016413'
                return self.last_status,text
            def read(self,name,address,size,timeout=8):
                if timeout_flag and name.startswith('slot_'):
                    raise TimeoutError('合成 IO 超时')
                now[0]+=.04
                content=b'X'*size if name.startswith('identity-') else (ram() if size==131072 else (ring() if size==3072 else ram()[:size]))
                file=self.raw/name
                file.write_bytes(content)
                return file
            def close(self):
                return 0
        timeout_flag=timeout
        @contextmanager
        def mapping(folder):
            yield 'NO_DEVICE:/'
        with patch('acq_swd.offline_precheck',return_value={'status':'SYNTHETIC_TEST_ONLY'}):
            try:
                capture_run(run,Path(__file__),True,FakeClient,mapping,lambda:now[0],lambda seconds:now.__setitem__(0,now[0]+seconds))
            except (ValueError,TimeoutError):
                pass
        return run,load_strict_json(run/'acquisition_receipt.json')

    def test_full_capture_mock_no_flash_writes(self):
        run,receipt=self.fake_capture()
        self.assertEqual(receipt['status'],'CAPTURE_COMPLETED')
        self.assertEqual(receipt['target_end_state'],'RUNNING_CONFIRMED_BEFORE_DISCONNECT')
        self.assertEqual(self.commands.count('r'),1)
        self.assertEqual(self.commands.count('h'),1)
        self.assertFalse(any('loadbin' in c or 'w4' in c for c in self.commands))
        self.assertEqual(export_run(run)[1]['integrity']['status'],'PASS')

    def test_identity_mismatch_stops_before_reset(self):
        run,receipt=self.fake_capture(mismatch=True)
        self.assertEqual(receipt['identity_status'],'MISMATCH')
        self.assertNotIn('r',self.commands)
        self.assertNotIn('h',self.commands)
        self.assertEqual(verify_package(run,raw=True)['status'],'PASS')

    def test_failed_resume_not_reported_as_running(self):
        _,receipt=self.fake_capture(bad_resume=True)
        self.assertEqual(receipt['status'],'STOP_OR_INCOMPLETE')
        self.assertEqual(receipt['target_end_state'],'UNKNOWN_AFTER_STOP')

    def test_timeout_preserves_receipt_and_no_automatic_recovery(self):
        run,receipt=self.fake_capture(timeout=True)
        self.assertEqual(receipt['status'],'STOP_OR_INCOMPLETE')
        self.assertNotIn('h',self.commands)
        self.assertTrue((run/'.capture.started').exists())

    def test_persistent_client_ack_error_and_timeout(self):
        raw=self.root/'raw'
        raw.mkdir()
        script=self.root/'fake_jlink.py'
        # 此进程仅模拟 Commander 文本接口，启动的是 Python，不是任何硬件程序。
        script.write_text('''import sys
for line in sys.stdin:
    line=line.strip()
    if line=='exit': break
    if line=='silence':
        sys.stdin.readline()
        continue
    if line=='bad': print('Error: synthetic failure', flush=True)
    elif line.startswith('mem32'): print('E000EDF0 = 00010000', flush=True)
''',encoding='utf-8')
        real_popen=subprocess.Popen
        def fake_process(*args,**kwargs):
            return real_popen([sys.executable,'-u',str(script)],**kwargs)
        with patch('acq_swd.subprocess.Popen',side_effect=fake_process):
            client=JLinkClient(Path('NOT_A_HARDWARE_PROGRAM'),raw,'X:/')
            try:
                self.assertEqual(client.command()[0],0x10000)
                with self.assertRaises(RuntimeError):
                    client.command('bad')
                with self.assertRaises(ValueError):
                    client.command()  # 迟到确认不能被当作新命令成功，失败客户端不得继续。
            finally:
                self.assertEqual(client.close(),0)
            second_raw=self.root/'raw-timeout'
            second_raw.mkdir()
            client=JLinkClient(Path('NOT_A_HARDWARE_PROGRAM'),second_raw,'X:/')
            try:
                self.assertEqual(client.command()[0],0x10000)
                with self.assertRaises(TimeoutError):
                    client.command('silence',timeout=.2)
            finally:
                self.assertEqual(client.close(),0)


if __name__=='__main__':
    unittest.main(verbosity=2)
