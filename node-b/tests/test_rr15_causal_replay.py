"""RR15回放工具的合成原件与假host库测试；不加载目标SDK、不访问网络。"""
import ctypes
import json
import math
from pathlib import Path
import struct
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import b5_rr15_causal_replay as replay


def frame(seq,ms=None,ecg=-5,resp=7,flags=0,cycles=None,status=0xc00000):
    raw=bytearray(replay.RAW_BYTES)
    raw[:3]=status.to_bytes(3,'big')
    raw[3:6]=resp.to_bytes(3,'big',signed=True)
    raw[6:9]=ecg.to_bytes(3,'big',signed=True)
    raw[9]=flags
    struct.pack_into('<III',raw,12,seq,cycles if cycles is not None else seq*672000,
                     ms if ms is not None else seq*4)
    return bytes(raw)


def block(*frames):
    raw=bytearray(replay.BLOCK_BYTES)
    for i,value in enumerate(frames):raw[i*replay.RAW_BYTES:(i+1)*replay.RAW_BYTES]=value
    return bytes(raw)


class SealedFrames(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.window=Path(self.temp.name)
        self.folder=self.window/'B';self.folder.mkdir()

    def write(self,blocks,*,tail=b'',change_index=None):
        rows=[{'data':{'offset':n*replay.BLOCK_BYTES,'sha256':replay.digest(raw)}}
              for n,raw in enumerate(blocks)]
        if change_index:change_index(rows)
        binary=b''.join(blocks)+tail
        index=(''.join(json.dumps(row)+'\n' for row in rows)).encode('utf-8')
        (self.folder/'blocks-private.bin').write_bytes(binary)
        (self.folder/'blocks-private.jsonl').write_bytes(index)
        return replay.digest(binary),replay.digest(index)

    def read(self,seals):return replay.sealed_raw_frames(self.window,*seals)

    def test_preserves_signed_channels_flags_status_and_wrapped_IRQ_statistics(self):
        start=0xffff0000
        first=frame(100,0xfffffffc,-8388608,8388607,1,start,0xc02000)
        second=frame(101,0,8388607,-123,0,(start+672000)&0xffffffff)
        third=frame(103,8,-77,2,0x80,(start+3*672000)&0xffffffff)
        invalid=frame(104,12,status=0xa00000)
        raw=block(first,second,third,invalid)
        rows,receipt=self.read(self.write([raw,raw]))
        self.assertEqual(rows[0],(100,0xfffffffc,-8388608,8388607,1,start,0xc02000))
        self.assertEqual(rows[1][2:5],(8388607,-123,0))
        self.assertEqual(receipt['invalid_status_sequences'],1)
        self.assertEqual(receipt['nonzero_flags_frames'],2)
        self.assertEqual(receipt['sequence_gaps'],[(101,103)])
        self.assertEqual(receipt['IRQ_ms_step_histogram'],{4:1})
        self.assertEqual(receipt['IRQ_cycles_step_min'],672000)
        self.assertEqual(receipt['IRQ_cycles_step_max'],672000)
        self.assertEqual(receipt['raw_status_values'],[0xc00000,0xc02000])

    def test_full_binary_hash_mismatch_is_refused(self):
        _,index_sha=self.write([block(frame(1))]*2)
        with self.assertRaisesRegex(ValueError,'PRIVATE_BLOCKS_FULL_SHA256_MISMATCH'):
            self.read(('0'*64,index_sha))

    def test_index_hash_mismatch_is_refused(self):
        binary_sha,_=self.write([block(frame(1))]*2)
        with self.assertRaisesRegex(ValueError,'PRIVATE_BLOCK_INDEX_SHA256_MISMATCH'):
            self.read((binary_sha,'0'*64))

    def test_per_block_hash_mismatch_is_refused(self):
        seals=self.write([block(frame(1))]*2,change_index=lambda rows:rows[0]['data'].update(sha256='0'*64))
        with self.assertRaisesRegex(ValueError,'G3_BLOCK_HASH_OR_OFFSET'):self.read(seals)

    def test_offset_mismatch_is_refused(self):
        seals=self.write([block(frame(1))]*2,change_index=lambda rows:rows[1]['data'].update(offset=1))
        with self.assertRaisesRegex(ValueError,'G3_BLOCK_HASH_OR_OFFSET'):self.read(seals)

    def test_positive_short_block_is_refused_even_when_its_hash_matches(self):
        seals=self.write([block(frame(1))[:-1]])
        with self.assertRaisesRegex(ValueError,'G3_BLOCK_HASH_OR_OFFSET'):self.read(seals)

    def test_unindexed_extra_byte_is_refused(self):
        seals=self.write([block(frame(1))]*2,tail=b'X')
        with self.assertRaisesRegex(ValueError,'G3_EXTRA_UNINDEXED_BYTES'):self.read(seals)

    def test_missing_original_is_refused(self):
        with self.assertRaises(FileNotFoundError):self.read(('0'*64,'0'*64))

    def test_single_copy_is_excluded_without_inventing_a_frame(self):
        rows,receipt=self.read(self.write([block(frame(1),frame(2),frame(3)),block(frame(1),frame(3))]))
        self.assertEqual([r[0] for r in rows],[1,3])
        self.assertEqual(receipt['unqualified_sequences'],1)

    def test_two_repeated_conflicting_versions_are_excluded(self):
        a=block(frame(1,ecg=10),frame(2))
        b=block(frame(1,ecg=11),frame(2))
        rows,receipt=self.read(self.write([a,a,b,b]))
        self.assertEqual([r[0] for r in rows],[2])
        self.assertEqual(receipt['unqualified_sequences'],1)

    def test_one_repeated_version_and_single_transient_matches_frozen_rule(self):
        a=block(frame(1,ecg=10));b=block(frame(1,ecg=11))
        rows,receipt=self.read(self.write([a,a,b]))
        self.assertEqual(rows[0][2],10)
        self.assertEqual(receipt['unqualified_sequences'],0)

    def test_sequence_restart_or_wrap_is_refused_before_sorting(self):
        for before,after in ((100,1),(0xfffffffe,1)):
            with self.subTest(before=before):
                seals=self.write([block(frame(before,0,cycles=0)),block(frame(after,4,cycles=672000))])
                with self.assertRaisesRegex(ValueError,'RAW_SEQUENCE_EPOCH_RESTART_OR_WRAP'):self.read(seals)


class LineProjection(unittest.TestCase):
    def rows(self):
        return [(seq,(0xffffff00+seq*4)&0xffffffff,
                 round(1000*math.sin(2*math.pi*50*(seq*4)/1000)),0,0,0,0xc00000)
                for seq in range(1,251)]

    def test_single_missing_sample_refuses_projection(self):
        rows=[r for r in self.rows() if r[0]!=125]
        self.assertEqual(replay.mains_projection(rows,251)['quality'],'INSUFFICIENT_CONTIGUOUS_SOURCE')

    def test_contiguous_50Hz_projection_uses_wrapped_original_ms(self):
        result=replay.mains_projection(self.rows(),251)
        self.assertEqual(result['quality'],'RAW_UNCALIBRATED')
        self.assertEqual(result['actual_samples'],250)
        self.assertGreater(result['line_50hz_projection_fraction'],.999)

    def test_DC_reports_zero_without_claiming_a_line_fraction(self):
        rows=[(seq,seq*4,17,0,0,0,0xc00000) for seq in range(1,251)]
        self.assertEqual(replay.mains_projection(rows,251),{'quality':'DC','raw_rms_codes':0})


class NativeFunction:
    def __init__(self,function):self.function=function
    def __call__(self,*args):return self.function(*args)


class FakeHostLibrary:
    def __init__(self,wrong_offset=False):
        self.diag=replay.Diag();self.calls=[];self.initialized=[]
        offsets=[ctypes.sizeof(replay.Diag)]+[getattr(replay.Diag,key).offset for key,_ in replay.FIELDS]
        if wrong_offset:offsets[2]+=1
        self.BioV2_ReplayAbi=NativeFunction(lambda index:offsets[index])
        self.BioV2_Init=NativeFunction(self.initialized.append)
        self.BioV2_Process=NativeFunction(self.process)
    def process(self,ecg,resp,ms,seq,flags):
        self.calls.append((ecg,resp,ms,seq,flags))
        self.diag.hr=60;self.diag.hr_valid=1;self.diag.rpm_valid=0
        self.diag.hr_last_cycle_ms=ms


class ReplayClock(unittest.TestCase):
    def run_replay(self,lib,rows):
        with patch.object(replay.C,'CDLL',return_value=lib),patch.object(replay.Diag,'in_dll',return_value=lib.diag):
            return replay.replay(Path('SYNTHETIC_HOST_ALGORITHM_ONLY.dll'),rows,'SYNTHETIC')

    def test_uint32_wrap_warmup_preserves_original_inputs_and_peak_timestamp(self):
        start=0xfffffff0
        rows=[(10+i,(start+elapsed)&0xffffffff,-10-i,20+i,i%2,0,0xc00000)
              for i,elapsed in enumerate((0,44996,45000,45004))]
        lib=FakeHostLibrary();result=self.run_replay(lib,rows)
        self.assertEqual(lib.initialized,[start])
        self.assertEqual(lib.calls,[(r[2],r[3],r[1],r[0],r[4]) for r in rows])
        self.assertEqual(result['analyzed_samples_after_replay_warmup'],2)
        self.assertEqual(result['hr_valid_samples'],2)
        episode=result['episodes_first_24'][0]
        self.assertEqual(episode['start_seq'],12)
        self.assertEqual(episode['last_accepted_peak_timestamp_ms'],rows[-1][1])
        self.assertNotIn('last_cycle_ms',episode)

    def test_C_offset_mismatch_is_refused_before_initialization(self):
        lib=FakeHostLibrary(wrong_offset=True)
        with self.assertRaisesRegex(AssertionError,'BIO_V2_C_SIZE_OR_OFFSETOF_DRIFT'):
            self.run_replay(lib,[(1,0,0,0,0,0,0xc00000)])
        self.assertEqual(lib.initialized,[])
        self.assertEqual(lib.calls,[])


if __name__=='__main__':unittest.main(verbosity=2)
