"""仅测试新增豁免门禁和只读入口，不重跑冻结软件矩阵，不加载J-Link。"""
import io
import json
from pathlib import Path
import sys
import time
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/'node-b/tools'))
import b5_g2_site as site


class SiteGateTests(unittest.TestCase):
    def auth(self):
        facts = {'JLink_target': 'C', 'C_power': 'J5_ON_OWNER_REPORTED',
                 'C_USB': 'DISCONNECTED_OWNER_REPORTED', 'ESP_isolated': False,
                 'owner_isolation_waiver': '批准豁免'}
        raw = json.dumps(facts).encode()
        out = ROOT/'node-b/build/SYNTHETIC_G2_SITE_UNUSED'
        a = {'enabled': True, 'owner_approved': True, 'scope': site.INSTALL, 'phase': 'install',
             'tools_sha256': site.bindings(), 'DLL_sha256': site.ro.raw.DLL_SHA,
             'expires_unix': time.time()+60, 'session_timeout_s': 180, 'probe_sessions': 1, 'retries': 0,
             'output': str(out), 'card_sha256': site.sha((ROOT/site.CARD).read_bytes()),
             'site_record': 'SYNTHETIC_ONLY', 'site_record_sha256': site.sha(raw),
             'ESP_present_powered_exception_approved': True, 'ESP_isolated': False,
             'board': 'C', 'nonhuman_mock': True, 'manifest_sha256': site.PACKAGE,
             'package': 'SYNTHETIC_ONLY'}
        return a, raw, out

    def test_default_disabled_no_native_constructors(self):
        with patch.object(sys, 'argv', ['site']), patch('sys.stdout', io.StringIO()), \
             patch.object(site, 'InstallLink') as installer, patch.object(site, 'BridgeLink') as bridge:
            self.assertEqual(site.main(), 0); installer.assert_not_called(); bridge.assert_not_called()

    def test_missing_or_wrong_owner_scope_denied(self):
        for a in ({}, {'enabled': True, 'owner_approved': True, 'scope': site.config.PROVISION}):
            with self.assertRaisesRegex(ValueError, 'OWNER_SCOPE'): site.authorize(a, Path('unused'))

    def test_missing_waiver_or_false_isolation_claim_rejected_before_package(self):
        for key, value in [('ESP_present_powered_exception_approved', False), ('ESP_isolated', True)]:
            a, raw, out = self.auth(); a[key] = value
            with patch.object(site.recovery, 'read', return_value=raw), patch.object(site.recovery, 'load_package') as load:
                with self.assertRaisesRegex(ValueError, 'ESP_EXCEPTION'): site.authorize(a, out)
                load.assert_not_called()

    def test_explicit_waiver_reaches_frozen_package_gate_without_native(self):
        a, raw, out = self.auth()
        with patch.object(site.recovery, 'read', return_value=raw), \
             patch.object(site.recovery, 'load_package', side_effect=ValueError('SYNTHETIC_PACKAGE_BOUNDARY')) as load:
            with self.assertRaisesRegex(ValueError, 'SYNTHETIC_PACKAGE_BOUNDARY'): site.authorize(a, out)
            load.assert_called_once()

    def test_tool_drift_rejected(self):
        a, raw, out = self.auth(); a['tools_sha256'] = {}
        with self.assertRaisesRegex(ValueError, 'TOOL_DRIFT'): site.authorize(a, out)

    def test_bridge_never_allows_halt_reset_go_or_target_write(self):
        link = object.__new__(site.BridgeLink)
        with patch.object(site.config.NativeLink, 'call') as native:
            for name in ('JLINKARM_Halt', 'JLINKARM_Reset', 'JLINKARM_Go', 'JLINKARM_WriteReg',
                         'JLINKARM_WriteMem', 'JLINKARM_BeginDownload', 'JLINKARM_EndDownload'):
                with self.assertRaisesRegex(ValueError, 'RO_ACTION'): link.call(name)
            with self.assertRaisesRegex(ValueError, 'TARGET_WRITE'):
                link.call('JLINKARM_CORESIGHT_WriteAPDPReg', 3, 1, 0x45670123)
            with self.assertRaisesRegex(ValueError, 'TARGET_WRITE'):
                link.call('JLINKARM_CORESIGHT_WriteAPDPReg', 2, 0, 0x01000000)
            native.assert_not_called()

    def test_bridge_allows_only_AP_transport_setup_writes(self):
        link = object.__new__(site.BridgeLink)
        with patch.object(site.config.NativeLink, 'call', return_value=0) as native:
            for reg, ap, value in ((2, 0, 0), (2, 0, 0xf0), (0, 1, 2), (1, 1, 0xe000ed00)):
                self.assertEqual(link.call('JLINKARM_CORESIGHT_WriteAPDPReg', reg, ap, value), 0)
            self.assertEqual(native.call_count, 4)

    def test_extra_RAM_read_cannot_occur_before_full_verify(self):
        link = object.__new__(site.InstallLink); link.fully_verified = False; link.sdk_calls = 0
        with patch.object(site.ro.raw.Link, 'call') as native:
            with self.assertRaisesRegex(ValueError, 'RAM_BEFORE_VERIFY'):
                link.call('JLINKARM_ReadMemEx', site.RAM, 4, None, 0)
            native.assert_not_called(); self.assertEqual(link.sdk_calls, 0)


if __name__ == '__main__': unittest.main(verbosity=2)
