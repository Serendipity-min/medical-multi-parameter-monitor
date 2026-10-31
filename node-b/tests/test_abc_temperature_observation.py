"""有界TEMP重复观察：保留坏原件，不修改源时戳或伪造有效性。"""
import struct
import tempfile
from pathlib import Path
import unittest
from unittest.mock import patch

import b4_runtime as runtime
import b5_b_temp_readonly as temp
from test_b4_temperature_observation import AdvancingTarget, TemperatureObservation


def blob(last_ms=900):
    data=bytearray(64)
    struct.pack_into('<7I3H3B',data,0,120,0,0,10,0,0,last_ms,2500,2400,2500,95,0,1)
    frame=bytearray((0xa4,3,7,7,95,9,196,9,96,9,196,0));frame[-1]=sum(frame[:11])&255
    data[49:61]=frame;return bytes(data)


class ScriptedTemperature(AdvancingTarget):
    def __init__(self,blobs):super().__init__();self.blobs=iter(blobs);self.temperature_reads=0
    def read(self,address,size):
        if address==temp.RAM['temperature'][0]:
            self.tick+=4;self.temperature_reads+=1;return next(self.blobs)
        return super().read(address,size)


class ABCObservation(unittest.TestCase):
    def observe(self,target,out=None):
        state={'DHCSR':0,'CFSR':0,'HFSR':0,'FLASH_CR':0x80000000,'pc_samples':[0x08001000],'VTOR':0x08000000}
        with patch.object(runtime.ro,'snapshot',return_value=state):
            return runtime.snapshot(target,out=out,label='test',addresses=temp.RAM,stable_temperature=True)

    def test_bad_first_read_is_preserved_then_two_original_good_reads_qualify(self):
        good=blob();bad=bytearray(good);bad[60]^=1;bad=bytes(bad)
        target=ScriptedTemperature([bad,good,good])
        with tempfile.TemporaryDirectory() as d:
            out=Path(d);r=self.observe(target,out)
            self.assertEqual((out/'test-temperature-observation-0-private.bin').read_bytes(),bad)
            self.assertEqual((out/'test-temperature-observation-1-private.bin').read_bytes(),good)
            self.assertEqual((out/'test-temperature-raw-private.bin').read_bytes(),good)
        self.assertTrue(r['temperature_observation']['qualified']);self.assertEqual(target.temperature_reads,3)
        self.assertEqual(r['temperature']['last_ms'],900)

    def test_work_in_progress_input_frame_and_used_do_not_replace_published_identity(self):
        first=bytearray(blob());second=bytearray(first);first[35]=10;second[35]=11;second[37:49]=b'\x11'*12
        target=ScriptedTemperature([bytes(first),bytes(second)]);r=self.observe(target)
        self.assertTrue(r['temperature_observation']['qualified']);self.assertEqual(r['temperature']['used'],11)
        self.assertFalse(r['temperature_observation']['atomic_snapshot'])

    def test_three_bad_reads_stay_unqualified_without_clearing_present_or_clamping(self):
        bad=bytearray(blob());bad[60]^=1;target=ScriptedTemperature([bytes(bad)]*3);r=self.observe(target)
        self.assertFalse(r['temperature_observation']['qualified']);self.assertEqual(target.temperature_reads,3)
        self.assertEqual(r['temperature']['present'],1);self.assertEqual(r['temperature']['last_ms'],900)

    def test_real_stale_and_future_ticks_remain_rejected_by_original_reviewer(self):
        helper=TemperatureObservation()
        for tick in (0,1200):
            target=ScriptedTemperature([blob(tick)]*2);target.tick=4000 if tick==0 else 1000;r=self.observe(target)
            self.assertTrue(r['temperature_observation']['qualified']);self.assertEqual(r['temperature']['last_ms'],tick)
            self.assertIn('B_TEMP_FRESH_SOURCE',helper.review_freshness(r))


if __name__=='__main__':unittest.main()
