"""正式窗口判据负例：短窗/缺口/无效HR不能被正常末值掩盖。"""
import copy
from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from analyze_capture_b import formal_evaluate


class Cases(unittest.TestCase):
    def fixture(self):
        rows=[{'source_seq':i+1,'device_ms':i*4,'flags_raw':0,'ch2_raw':1000} for i in range(23000)]
        replay=[dict(device_ms=r['device_ms'],hr=60,hr_valid=1) for r in rows]
        live=[{'last_sample_ms':i*800,'hr':60,'hr_valid':1,'host_start_s':i*.8,'host_end_s':i*.8,
               'adc':{'captured':i*200,'init_errors':0,'spi_errors':0,'bad_status':0,'queue_overflow':0}} for i in range(115)]
        return rows,live,replay

    def test_success_and_failures(self):
        rows,live,replay=self.fixture()
        self.assertEqual(formal_evaluate(rows,live,replay,60)['status'],'ENGINEERING_RATE_WINDOW_PASS')
        shortened=rows[:20000]
        self.assertIn('LESS_THAN_COMPLETE_60S_RAW',formal_evaluate(shortened,live,replay,60)['failures'])
        bad=rows[:10000]+rows[10001:]
        self.assertIn('STEADY_SEQUENCE_GAP',formal_evaluate(bad,live,replay,60)['failures'])
        changed=copy.deepcopy(live);changed[50]['hr_valid']=0
        self.assertIn('LIVE_HR_NOT_WITHIN_2_BPM',formal_evaluate(rows,changed,replay,60)['failures'])
        changed=copy.deepcopy(rows);changed[10000]['ch2_raw']=8388607
        self.assertIn('ECG_NEAR_RAIL',formal_evaluate(changed,live,replay,60)['failures'])


if __name__=='__main__':unittest.main(verbosity=2)
