"""用受限原码/主机读时序回放采集器；不打开设备。"""
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import b5_m1_entry as entry
from test_b5_m1 import Clock, FakeLink, reference


@unittest.skipUnless(os.environ.get('M1_TIMING_REPLAY_JOB'), 'requires restricted timing evidence')
class CaptureIOTiming(unittest.TestCase):
    def replay(self, io_seconds=None, truncate_tail=False):
        source = Path(os.environ['M1_TIMING_REPLAY_JOB'])/'capture/B'
        rows = [json.loads(s)['data'] for s in (source/'blocks-private.jsonl').read_text().splitlines()]
        data = (source/'blocks-private.bin').read_bytes()
        if truncate_tail:
            rows = rows[:-3]
        clock = Clock()
        class ReplayLink(FakeLink):
            def __init__(self):
                super().__init__(clock); self.index = 0; self.origin = None
            def read(self, address, size):
                if address != entry.SLOTS:
                    return super().read(address, size)
                if self.origin is None:
                    self.origin = clock(); self.capture_deadline = self.deadline
                i = self.index; self.index += 1
                if i < len(rows):
                    end = rows[i]['read_end']-rows[0]['read_start']
                    offset = rows[i]['offset']
                else:
                    end = rows[-1]['read_end']-rows[0]['read_start']+(i-len(rows)+1)*.141
                    offset = rows[-1]['offset']
                clock.t = max(clock(), self.origin+end)
                entry.need(clock() <= self.deadline, 'M1_PHASE_TIMEOUT')
                return data[offset:offset+entry.BLOCK_BYTES]
        link = ReplayLink(); ref = reference()
        if io_seconds is not None:
            ref.update(capture_io_s=io_seconds, maximum_cold_start_uptime_ms=None)
        with tempfile.TemporaryDirectory(dir=os.environ.get('M1_TEST_ROOT')) as folder:
            result = entry.capture_window(lambda *_: link, Path(folder)/'session', ref,
                                          clock=clock, sleep=clock.sleep)
        self.assertEqual(link.closes, 1)
        self.assertEqual(result['post_Close_state'], 'UNKNOWN_NOT_OBSERVED')
        self.assertLessEqual(link.capture_deadline, entry.BUDGET['session_s']-entry.BUDGET['cleanup_s'])
        return result, link

    def test_original_165_host_budget_reproduces_timeout(self):
        result, _ = self.replay()
        self.assertEqual((result['exit_code'], result['reason']), (4, 'M1_PHASE_TIMEOUT'))

    def test_owner_IO_margin_completes_same_raw_boundary_within_total_budget(self):
        result, link = self.replay(180)
        self.assertEqual(result['exit_code'], 0, result)
        self.assertGreater(result['capture_host_s'], 165)
        self.assertLess(result['capture_host_s'], 166)
        self.assertEqual(result['anchor'], {'seq': 13383, 'ms': 54914})
        self.assertEqual(link.index, 1057)

    def test_margin_cannot_pass_when_raw_endpoint_is_missing(self):
        result, _ = self.replay(180, truncate_tail=True)
        self.assertEqual(result['exit_code'], 4, result)

    def test_owner_cold_confirmation_needs_no_exact_clock(self):
        import b5_m1_owner_once as owner
        job = Path(os.environ['M1_TIMING_REPLAY_JOB'])
        bundle = json.loads((job/'reference-bundle-path.json').read_text())['bundle_file']
        with tempfile.TemporaryDirectory(dir=os.environ['M1_TEST_ROOT']) as folder:
            root = Path(folder); site_path = root/'site.json'; cold_path = root/'cold.json'
            site = dict.fromkeys(('owner_approved_topology', 'JLink_on_B', 'nonhuman_source', 'no_human',
                                 'B_USB_disconnected', 'SKX_battery_no_charge_USB', 'manual_emergency_cutoff_ready',
                                 'sdk_residual_risk_acknowledged', 'C_J5_powered', 'CAN_B_C_connected',
                                 'C_USB_disconnected'), True)
            site.update(topology=owner.TOPOLOGY, B_C_electrically_isolated=False, source_mode='NORMAL_ECG',
                        target_rate=60, ECG_amplitude_mV=1, waveform_type_confirmed=True,
                        R_lead='RA', L_lead='LA', F_lead='RL', manual_stop_responsibility='SYNTHETIC_PERSON')
            cold = {'run_id': 'M1-E60-R1', 'cold_start_completed': True,
                    'independent_boot_epoch': 'SYNTHETIC_PHYSICAL_CONFIRMATION_NO_EXACT_TIME'}
            site_path.write_text(json.dumps(site)); cold_path.write_text(json.dumps(cold))
            a = {'bundle_file': bundle, 'site_file': str(site_path), 'cold_start_file': str(cold_path),
                 'output': str(root/'session')}
            def git(command, **kwargs):
                return b'' if command[1] == 'status' else b'SYNTHETIC_FROZEN_GIT_ID'
            with patch.object(owner.subprocess, 'check_output', side_effect=git):
                _, ref = owner.bindings(a)
                self.assertIsNone(ref['maximum_cold_start_uptime_ms'])
                self.assertEqual(ref['capture_io_s'], 180)
                cold['cold_start_completed'] = False; cold_path.write_text(json.dumps(cold))
                with self.assertRaisesRegex(ValueError, 'M1_INDEPENDENT_COLD_START'):
                    owner.bindings(a)


if __name__ == '__main__':
    unittest.main()
