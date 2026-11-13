"""仅测试新增豁免门禁和只读入口，不重跑冻结软件矩阵，不加载J-Link。"""
import io
import ctypes
import json
from pathlib import Path
import sys
import time
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/'node-b/tools'))
import b5_g2_site as site
sys.path.insert(0, str(ROOT/'node-b/tests'))
import test_b5_sector3_write as prior


class ObservedSDKReplay:
    """重放已观察到的Configure后读失败边界，不代表真实SDK内部实现。"""
    def __init__(self):
        self.image = b'\x5a'*1048576; self.options = b'\xaa'*16
        self.bus = prior.APBus(self.image[:64]); self.events = []
        self.configured = False; self.connected = True; self.fail_raw = False; self.fail_after_raw = False
        self.verified_running_flash = False; self.close_resume_enabled = False
        self.values = {0xe000ed00: 0x410fc241, 0xe0042000: 0x10000413, 0x40023c14: 0x0fffaaed,
                       0xe000edf0: 0x01010001, 0xe000ed08: 0x08000000, 0xe000101c: 0x08001000,
                       site.config.CR: 0x80000000, site.config.SR: 0}

    def open(self): pass
    def set_close_resume(self, enabled): self.close_resume_enabled = enabled
    def u32(self, address): return int.from_bytes(self.read(address, 4), 'little')

    def read(self, address, size):
        self.events.append(('SDK_READ', address))
        if self.configured or (self.fail_after_raw and any(e[0].endswith('APDPReg') for e in self.events)):
            raise ValueError('SITE_SDK_MEMORY_NATIVE_ERROR')
        if address == 0x08000000: return self.image[:size]
        if address == 0x1fffc000: return self.options
        if address == 0x1fff7a10: return b'\x5a'*12
        if address == 0x1fff7a22: return (1024).to_bytes(2, 'little')
        if address == site.RAM: return bytes(4)
        return self.values.get(address, 0).to_bytes(4, 'little')

    def call(self, name, *args, **kwargs):
        self.events.append((name, args[0] if args else None))
        if name == 'JLINKARM_CORESIGHT_Configure': self.configured = True; return 0
        if name == 'JLINKARM_IsConnected': return int(self.connected)
        if name == 'JLINKARM_CORESIGHT_ReadAPDPReg':
            if self.fail_raw: return -17
            reg, ap, pointer = args
            ctypes.cast(pointer, ctypes.POINTER(ctypes.c_uint32)).contents.value = self.bus.read(reg, bool(ap))
            return 0
        if name == 'JLINKARM_CORESIGHT_WriteAPDPReg':
            reg, ap, value = args; self.bus.write(reg, bool(ap), value); return 0
        raise AssertionError('UNEXPECTED_NATIVE_OPERATION')

    def payload(self):
        return {'identity-private.json': json.dumps(site.ro.raw.identity(self)).encode(),
                'expected-full-private.bin': self.image, 'options-private.bin': self.options}


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
                         'JLINKARM_WriteMem', 'JLINKARM_BeginDownload', 'JLINKARM_EndDownload',
                         'JLINKARM_CORESIGHT_Configure'):
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

    def replay(self, link):
        with tempfile.TemporaryDirectory() as folder, patch.object(site.recovery, 'protected', side_effect=lambda path, _: Path(path)):
            return site.bridge_readonly(link, Path(folder), link.payload())

    def test_connected_context_avoids_configure_and_checks_SDK_before_raw(self):
        link = ObservedSDKReplay(); result = self.replay(link)
        self.assertEqual(result['status'], 'G2B_MEMAP_READONLY_CROSSCHECK_PASS')
        self.assertFalse(any(e[0] == 'JLINKARM_CORESIGHT_Configure' for e in link.events))
        first_raw = next(i for i, e in enumerate(link.events) if e[0].endswith('APDPReg'))
        self.assertTrue(any(e == ('SDK_READ', 0xe000ed00) for e in link.events[:first_raw]))
        self.assertTrue(link.close_resume_enabled); self.assertTrue(link.verified_running_flash)
        self.assertEqual(link.bus.effects, [])

    def test_disconnected_sdk_stops_without_raw_AP_DP(self):
        link = ObservedSDKReplay(); link.connected = False
        with self.assertRaisesRegex(ValueError, 'SDK_NOT_CONNECTED'): self.replay(link)
        self.assertFalse(link.close_resume_enabled)
        self.assertFalse(any(e[0].endswith('APDPReg') for e in link.events))

    def test_raw_error_has_no_flash_write_or_close_resume(self):
        link = ObservedSDKReplay(); link.fail_raw = True
        with self.assertRaisesRegex(ValueError, 'DAP_READ_NATIVE_ERROR'): self.replay(link)
        self.assertFalse(link.close_resume_enabled); self.assertFalse(link.verified_running_flash)
        self.assertEqual(link.bus.effects, [])

    def test_post_raw_SDK_error_cannot_sign_pass_or_resume(self):
        link = ObservedSDKReplay(); link.fail_after_raw = True
        with self.assertRaisesRegex(ValueError, 'SDK_MEMORY_NATIVE_ERROR'): self.replay(link)
        self.assertFalse(link.close_resume_enabled); self.assertFalse(link.verified_running_flash)
        self.assertEqual(link.bus.effects, [])

    def test_negative_SDK_error_and_positive_short_count_are_distinct(self):
        link = object.__new__(site.BridgeLink); link.io = io.StringIO()
        for returned, reason in ((-1, 'MEMORY_NATIVE_ERROR'), (2, 'POSITIVE_SHORT_READ')):
            with patch.object(site.BridgeLink, 'call', return_value=returned):
                with self.assertRaisesRegex(ValueError, reason): link.read(0xe000ed00, 4)
        self.assertIn('"returned": -1', link.io.getvalue()); self.assertIn('"returned": 2', link.io.getvalue())

    def test_SDK_callback_has_API_and_time_without_message_plaintext(self):
        link = object.__new__(site.BridgeLink); link.log = io.BytesIO(); link.install_log_filters()
        def emit(*args, **kwargs):
            link.logger(b'CPU could not be halted'); raise ValueError('SYNTHETIC_NATIVE_FAILURE')
        with patch.object(site.config.NativeLink, 'call', side_effect=emit):
            with self.assertRaises(ValueError): link.call('JLINKARM_IsConnected')
        row = json.loads(link.log.getvalue())
        self.assertEqual(row['inflight_host_API'], 'JLINKARM_IsConnected')
        self.assertGreater(row['monotonic_s'], 0); self.assertIsNone(link.active_api)
        self.assertEqual(row['sdk_text_sha256'], site.sha(b'CPU could not be halted'))
        self.assertNotIn(b'CPU could not be halted', link.log.getvalue())

    def test_raw_native_error_latches_stop_even_for_finally_transport_cleanup(self):
        link = object.__new__(site.BridgeLink)
        with patch.object(site.config.NativeLink, 'call', return_value=-17) as native:
            self.assertEqual(link.call('JLINKARM_CORESIGHT_WriteAPDPReg', 2, 0, 0), -17)
            with self.assertRaisesRegex(ValueError, 'RAW_STOP_LATCHED'):
                link.call('JLINKARM_CORESIGHT_WriteAPDPReg', 2, 0, 0)
            self.assertEqual(native.call_count, 1)


if __name__ == '__main__': unittest.main(verbosity=2)
