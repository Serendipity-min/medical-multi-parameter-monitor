import unittest
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import b5_channel_review as r

class Entry(unittest.TestCase):
    def setUp(self):
        self.m=dict(seq=7,timestamp=100000,session_id='can-12-1',value=25.26)
        self.e=dict(seq=7,report_utc=100000,arrival_utc=101600,epoch=12,boot=1,centi=2526,valid=1,lost=0)
        self.frames=[dict(object_centi=2526,UTC_candidates=[101400])]
    def test_report_anchor_is_not_measurement_time(self):
        self.assertFalse(r.match_temperature(self.m,self.frames))
        self.assertTrue(r.match_temperature_entry(self.m,self.frames,self.e))
        self.assertEqual(self.m['timestamp'],100000)
    def test_2500ms_age_not_relaxed(self):
        self.frames[0]['UTC_candidates']=[99099]
        self.assertFalse(r.match_temperature_entry(self.m,self.frames,self.e))
    def test_future_frame_beyond_original_phase_bound_rejected(self):
        self.frames[0]['UTC_candidates']=[101603]
        self.assertFalse(r.match_temperature_entry(self.m,self.frames,self.e))
    def test_seq_session_value_loss_or_invalid_rejected(self):
        for changes in ({'seq':8},{'epoch':13},{'boot':2},{'centi':2527},{'lost':1},{'valid':0}):
            with self.assertRaises(ValueError):r.match_temperature_entry(self.m,self.frames,dict(self.e,**changes))
    def test_missing_entry_is_not_filled_from_broker(self):
        with self.assertRaises(ValueError):r.match_temperature_entry(self.m,self.frames,None)

if __name__=='__main__':unittest.main()
