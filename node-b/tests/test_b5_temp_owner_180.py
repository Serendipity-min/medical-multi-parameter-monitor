"""TEMP短窗的工程评估负例；不接触SDK。"""
import copy
import unittest

import b5_temp_owner_180 as temp


class Temp180(unittest.TestCase):
    def setUp(self):
        frame=bytearray((0xa4,3,7,7,95,9,196,9,196,0,0,0));frame[-1]=sum(frame[:11])&255
        t={'present':1,'object_centi':2500,'last_ms':900,'frames':100,
           'overflow':0,'uart_errors':0,'checksum_errors':0,'header_errors':0,'last_frame_hex':frame.hex()}
        self.rows=[{'host_monotonic':1.,'bio':{'last_sample_ms':1000},'temperature':t},
                   {'host_monotonic':180.5,'bio':{'last_sample_ms':180500},'temperature':dict(t,last_ms=180400,frames=900)}]

    def test_valid_updating_nonhuman_window(self):
        r=temp.assess(self.rows)
        self.assertEqual(r['exit_code'],0);self.assertEqual(r['counter_increments']['frames'],800)
        self.assertEqual(r['age_ms_max'],100);self.assertEqual(r['absolute_accuracy'],'NOT_CALIBRATED')
        self.assertEqual(r['cloud_end_to_end'],'NOT_RUN')

    def test_stale_future_missing_and_out_of_range(self):
        for change in ({'last_ms':170000},{'last_ms':180600},{'present':0},{'object_centi':10001}):
            with self.subTest(change=change):
                rows=copy.deepcopy(self.rows);rows[-1]['temperature'].update(change)
                self.assertIn('TEMP_FRESH_PRESENT_RANGE',temp.assess(rows)['failures'])

    def test_counter_stall_and_new_uart_errors(self):
        for change in ({'frames':100},{'checksum_errors':1},{'header_errors':1},{'overflow':1},{'uart_errors':1}):
            with self.subTest(change=change):
                rows=copy.deepcopy(self.rows);rows[-1]['temperature'].update(change)
                self.assertIn('TEMP_UPDATE_OR_ERROR_INCREMENT',temp.assess(rows)['failures'])

    def test_raw_frame_corruption_is_not_hidden(self):
        rows=copy.deepcopy(self.rows);rows[-1]['temperature']['last_frame_hex']='00'*12
        self.assertEqual(temp.assess(rows)['bad_last_frame_observations'],1)
        self.assertEqual(temp.assess(rows)['exit_code'],3)


if __name__=='__main__':unittest.main()
