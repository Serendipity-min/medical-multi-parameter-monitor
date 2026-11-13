"""B4运行监测的纯字典判据和SDK拒绝测试，不接设备。"""
from pathlib import Path
import sys
import unittest
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'node-b/tools'))
import b4_runtime as w

def snap(samples,ms):
    return {'bio':{'samples':samples,'last_sequence':samples,'last_sample_ms':ms,
            'discontinuities':0,'clipped_samples':0,'adc':{'long_gap_count':0,
            'bad_status':0,'spi_errors':0,'queue_overflow':0,'init_errors':0}},
            'CAN':{'overflow':0,'discontinuities':0,'comm_reset':0}}

class Tests(unittest.TestCase):
    def test_250(self):self.assertEqual(w.assess(snap(10,100),snap(760,3100)),250)
    def test_stopped(self):
        with self.assertRaisesRegex(ValueError,'NO_SAMPLES'):w.assess(snap(10,100),snap(10,3100))
    def test_bad_sps(self):
        with self.assertRaisesRegex(ValueError,'NOT_250'):w.assess(snap(10,100),snap(510,3100))
    def test_short_nonatomic_no_false_rate_verdict(self):
        self.assertGreater(w.assess(snap(10,100),snap(137,600)),250)
    def test_reset(self):
        with self.assertRaises(ValueError):w.assess(snap(1000,4000),snap(100,400))
    def test_new_gap(self):
        b=snap(760,3100);b['bio']['adc']['long_gap_count']=1
        with self.assertRaisesRegex(ValueError,'NEW_ADC_GAP'):w.assess(snap(10,100),b)
    def test_clipping_is_separate_from_sampling_continuity(self):
        b=snap(760,3100);b['bio']['clipped_samples']=50
        self.assertEqual(w.assess(snap(10,100),b),250)
    def test_denied_control(self):
        obj=object.__new__(w.Link);obj.sdk_calls=0
        for name in ('JLINKARM_Halt','JLINKARM_Go','JLINKARM_Reset','JLINKARM_WriteMem'):
            with self.assertRaisesRegex(ValueError,'FUNCTION_DENIED'):obj.call(name)
    def test_no_unknown_RAM(self):
        obj=object.__new__(w.Link);obj.sdk_calls=0
        with self.assertRaisesRegex(ValueError,'READ_SCOPE'):obj.call('JLINKARM_ReadMemEx',0x20000000,131072,None,0)
    def test_disabled(self):
        with self.assertRaisesRegex(ValueError,'OWNER_AUTH'):w.validate({})
    def test_RAM_failure_after_healthy_CPU_keeps_close_resume(self):
        class Fake:
            verified_running_flash=False
            close_resume_enabled=False
            def set_close_resume(self,value):self.close_resume_enabled=value
            def read(self,*args):raise ValueError('SYNTHETIC_RAM_ERROR')
        f=Fake();s={'DHCSR':0,'CFSR':0,'HFSR':0,'FLASH_CR':0x80000000,
                   'pc_samples':[0x08001000],'VTOR':0x08000000}
        with patch.object(w.ro,'snapshot',return_value=s):
            with self.assertRaisesRegex(ValueError,'SYNTHETIC_RAM_ERROR'):w.snapshot(f)
        self.assertTrue(f.close_resume_enabled)
    def test_preserved_historical_counts_not_zeroed(self):
        a=snap(10,100);b=snap(760,3100)
        a['CAN']['discontinuities']=b['CAN']['discontinuities']=3
        self.assertEqual(w.assess(a,b),250)
    def test_historical_adc_error_preserved_but_no_new_error(self):
        # 历史错误必须原样保留；本窗不增长才可通过连续性判据。
        a=snap(10,100);b=snap(760,3100)
        a['bio']['adc']['bad_status']=b['bio']['adc']['bad_status']=1
        self.assertEqual(w.assess(a,b),250)
    def test_each_new_adc_error_stops(self):
        for key in ('bad_status','spi_errors','queue_overflow','init_errors'):
            a=snap(10,100);b=snap(760,3100);b['bio']['adc'][key]=1
            with self.subTest(key=key), self.assertRaisesRegex(ValueError,'NEW_ADC_'):
                w.assess(a,b)
if __name__=='__main__':unittest.main(verbosity=2)
