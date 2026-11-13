"""P0取证协议的离线负例；测试不打开任何调试器或串口。"""
import argparse
import copy
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'tools'))
import precan_cpu_state_b as state
from readback_b import Link


def observations():
    return [{'system': {'DHCSR': 0x10001, 'VTOR': 0x08000000, 'CFSR': 0, 'HFSR': 0},
             'pc_regions': ['BIO_V2_FLASH'], 'bio': {'samples': n*250, 'adc': {'captured': n*250}}}
            for n in (1, 2, 3)]


class CpuStateTests(unittest.TestCase):
    def test_all_running_observations_never_close_root_cause(self):
        result = state.runtime_assessment(observations())
        self.assertTrue(result['application_observed_running'])
        self.assertEqual(result['root_cause'], 'CPU_ROOT_CAUSE_UNRESOLVED')
        self.assertFalse(result['P0_closeout_pass'])

    def test_ROM_fault_ABI_or_missing_PC_remains_abnormal(self):
        for field, value in [('VTOR', 0x1fff0000), ('DHCSR', 0x30003), ('CFSR', 1)]:
            data = observations(); data[0]['system'][field] = value
            self.assertFalse(state.runtime_assessment(data)['application_observed_running'])
        data = observations(); data[0]['pc_regions'] = ['UNAVAILABLE']
        self.assertFalse(state.runtime_assessment(data)['application_observed_running'])
        data = observations(); data[0]['bio'] = None
        self.assertIn('BIO_ABI_NOT_READY', state.runtime_assessment(data)['reasons'])

    def test_frozen_BIO_or_ADC_counters_do_not_show_runtime_success(self):
        data = observations(); data[1]['bio']['samples'] = data[0]['bio']['samples']
        self.assertIn('BIO_NOT_ADVANCING', state.runtime_assessment(data)['reasons'])
        data = observations(); data[2]['bio']['adc']['captured'] = 0
        self.assertIn('ADC_NOT_ADVANCING', state.runtime_assessment(data)['reasons'])

    def fake_link(self):
        link = state.StateLink.__new__(state.StateLink)
        link.sdk_calls = 0; link.read_counts = {}; link.function_counts = {}
        link.register_reads_allowed = False; link.journal = io.StringIO()
        return link

    def test_reset_halt_go_and_data_writes_never_reach_SDK(self):
        link = self.fake_link()
        with patch.object(Link, 'call') as sdk:
            for name in ('JLINKARM_Reset', 'JLINKARM_Halt', 'JLINKARM_Go', 'JLINKARM_WriteMem', 'JLINKARM_WriteReg'):
                with self.assertRaisesRegex(RuntimeError, 'FUNCTION_DENIED'): link.call(name)
            for command in (b'SetResetType = 0', b'SupplyPower = 1', b'SetWorkRAM 0x20000000-0x20001000'):
                with self.assertRaisesRegex(RuntimeError, 'POLICY_DENIED'): link.call('JLINKARM_ExecCommand', command)
            sdk.assert_not_called()

    def test_already_halted_core_guard_and_function_limits(self):
        link = self.fake_link()
        with patch.object(Link, 'call', return_value=0):
            with self.assertRaisesRegex(RuntimeError, 'ALREADY_HALTED'): link.call('JLINKARM_ReadReg', 15)
            link.register_reads_allowed = True; link.call('JLINKARM_ReadReg', 15)
            self.assertEqual(link.sdk_calls, 1)
            link.call('JLINKARM_OpenEx', None, None)
            with self.assertRaisesRegex(RuntimeError, 'FUNCTION_BUDGET'): link.call('JLINKARM_OpenEx', None, None)

    def test_read_lengths_and_per_address_budget(self):
        link = self.fake_link()
        with patch.object(Link, 'call', return_value=1048576):
            link.call('JLINKARM_ReadMemEx', 0x08000000, 1048576, None, 0)
            with self.assertRaisesRegex(RuntimeError, 'READ_BUDGET'): link.call('JLINKARM_ReadMemEx', 0x08000000, 1048576, None, 0)
            with self.assertRaisesRegex(RuntimeError, 'READ_SCOPE'): link.call('JLINKARM_ReadMemEx', 0x08000000, 64, None, 0)
            with self.assertRaisesRegex(RuntimeError, 'READ_SCOPE'): link.call('JLINKARM_ReadMemEx', 0x40023800, 4, None, 0)

    def test_disabled_manifest_stops_before_Link_or_owner_records(self):
        with tempfile.TemporaryDirectory() as folder:
            manifest = Path(folder)/'disabled.json'; manifest.write_text(json.dumps({'enabled': False}), encoding='utf-8')
            args = argparse.Namespace(manifest=manifest)
            with patch.object(state, 'StateLink') as sdk:
                with self.assertRaisesRegex(RuntimeError, 'NOT_AUTHORIZED'): state.authorize(args)
                sdk.assert_not_called()

    def test_call_journal_keeps_ordered_before_and_after(self):
        link = self.fake_link()
        with patch.object(Link, 'call', return_value=0):
            link.call('JLINKARM_ExecCommand', b'ForceAttachTarget = 1')
        events = [json.loads(line) for line in link.journal.getvalue().splitlines()]
        self.assertEqual([e['phase'] for e in events], ['BEFORE_CALL', 'AFTER_CALL'])
        self.assertEqual([e['index'] for e in events], [1, 1])
        self.assertEqual(events[0]['command'], 'ForceAttachTarget = 1')


if __name__ == '__main__':
    unittest.main()
