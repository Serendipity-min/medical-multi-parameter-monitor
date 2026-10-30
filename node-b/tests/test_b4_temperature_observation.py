"""温度更新恰落在分次读之间时，验证原始时基的观察顺序。"""
from pathlib import Path
import struct
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import b4_runtime as runtime
import b5_b_temp_readonly as temp
import b5_channel_review as review


class AdvancingTarget:
    close_resume_enabled=True
    def __init__(self):self.tick=1000;self.bio_ticks=[];self.temp_tick=None;self.reads=[]
    def read(self,address,size):
        self.reads.append((address,size));tick=self.tick;self.tick+=4
        if address==temp.RAM['bio'][0]:
            self.bio_ticks.append(tick)
            values=[0]*26+[0.0]*4
            values[0]=0x324f4942;values[1]=2;values[2]=tick//4;values[3]=tick//4;values[4]=tick
            return struct.pack('<8I4i14I4f',*values)
        if address==temp.RAM['temperature'][0]:
            self.temp_tick=tick
            blob=bytearray(64)
            struct.pack_into('<7I3H3B',blob,0,12,0,0,1,0,0,tick,2500,2400,2500,95,0,1)
            return bytes(blob)
        return bytes(size)
    def u32(self,address):self.tick+=4;return 0


class TemperatureObservation(unittest.TestCase):
    def observe(self,target):
        state={'DHCSR':0,'CFSR':0,'HFSR':0,'FLASH_CR':0x80000000,
               'pc_samples':[0x08001000],'VTOR':0x08000000}
        with patch.object(runtime.ro,'snapshot',return_value=state):
            return runtime.snapshot(target,addresses=temp.RAM)

    def review_freshness(self,result):
        result['host_monotonic']=50
        with patch.object(review.old,'assess_b',return_value={'failures':[]}):
            return review.assess_b([result],{'monotonic':0},'TEMP_OBJECT')['failures']

    def test_update_between_reads_is_bracketed_without_clamping_ticks(self):
        target=AdvancingTarget();result=self.observe(target)
        self.assertGreaterEqual(result['bio']['last_sample_ms']-result['temperature']['last_ms'],0)
        self.assertEqual(result['temperature']['last_ms'],target.temp_tick)
        self.assertEqual(result['bio']['last_sample_ms'],target.bio_ticks[-1])
        self.assertEqual(len(target.bio_ticks),2)
        observation=result['temperature_observation']
        self.assertEqual(observation['bio_before_ms'],target.bio_ticks[0])
        self.assertEqual(observation['bio_after_ms'],target.bio_ticks[-1])
        self.assertLessEqual(observation['bio_before_ms'],target.temp_tick)
        self.assertLessEqual(target.temp_tick,observation['bio_after_ms'])
        self.assertNotIn('B_TEMP_FRESH_SOURCE',self.review_freshness(result))

    def test_stale_temperature_is_preserved_for_the_frozen_reviewer(self):
        class Stale(AdvancingTarget):
            def read(self,address,size):
                blob=super().read(address,size)
                if address==temp.RAM['temperature'][0]:
                    blob=bytearray(blob);struct.pack_into('<I',blob,24,0);return bytes(blob)
                return blob
        target=Stale();target.tick=4000
        result=self.observe(target)
        self.assertEqual(result['temperature']['last_ms'],0)
        self.assertGreater(result['bio']['last_sample_ms']-result['temperature']['last_ms'],2500)
        self.assertIn('B_TEMP_FRESH_SOURCE',self.review_freshness(result))

    def test_genuine_future_timestamp_is_not_repaired_or_hidden(self):
        class Future(AdvancingTarget):
            def read(self,address,size):
                blob=super().read(address,size)
                if address==temp.RAM['temperature'][0]:
                    blob=bytearray(blob);struct.pack_into('<I',blob,24,self.temp_tick+100);return bytes(blob)
                return blob
        target=Future();result=self.observe(target)
        self.assertEqual(result['temperature']['last_ms'],target.temp_tick+100)
        self.assertLess(result['bio']['last_sample_ms']-result['temperature']['last_ms'],-10)
        self.assertIn('B_TEMP_FRESH_SOURCE',self.review_freshness(result))


if __name__=='__main__':unittest.main(verbosity=2)
