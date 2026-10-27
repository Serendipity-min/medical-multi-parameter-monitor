"""连接流程变更的定向离线验证；不加载DLL、不接实板。"""
import ctypes as C
import io
import json
from pathlib import Path
import sys
import tempfile
import time
import types
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT/'node-b/tools'), str(ROOT/'node-b/tests')]
import b5_sector3_write as w
import b5_sector3_write_protocol as p
import test_b5_sector3_write as prior


class Connected(prior.FakeLink):
    def __init__(self, out, before, options, identity):
        super().__init__(out, before, options, identity)
        self.mem = prior.NorIO(before, options)
        self.bus = prior.APBus(before[:64])
        self.trace = []; self.connected = True; self.bad_cpuid = False
        self.fail_raw = False; self.raw_failed = False; self.error = False
        read_bus, write_bus = self.bus.read, self.bus.write
        def read(reg, ap):
            if ap and reg == 3 and self.bus.select == 0 and self.bus.tar in self.mem.reg:
                return self.mem.read32(self.bus.tar)
            return read_bus(reg, ap)
        def write(reg, ap, value):
            if ap and reg == 3:
                assert self.raw_target_grant == (self.bus.tar, value)
                self.mem.write32(self.bus.tar, value)
            else: write_bus(reg, ap, value)
        self.bus.read, self.bus.write = read, write
    def read(self, address, size):
        self.trace.append(('SDK_READ', address))
        if hasattr(self, 'active_engine') and (0x08000000 <= address < 0x08100000 or address == 0x1fffc000):
            if size == 1048576: self.full_reads += 1
            elif address == 0x1fffc000: self.option_reads += 1
            return self.mem.read(address, size)
        return super().read(address, size)
    def u32(self, address):
        self.trace.append(('SDK_U32', address))
        if address in self.mem.reg: return self.mem.reg[address]
        return super().u32(address)
    def call(self, name, *args, **kwargs):
        self.trace.append((name, args[:2]))
        if name == 'JLINKARM_IsConnected': return int(self.connected)
        if name == 'JLINKARM_Reset': self.actions[name] = 1; self.halted = True; return 0
        if name == 'JLINKARM_Go': self.actions[name] = 1; self.halted = False; self.runtime_entry = bytes(4); return 0
        if name.endswith('APDPReg'):
            if self.fail_raw: self.raw_failed = True; raise ValueError('S3_DAP_NATIVE_ERROR_SYNTHETIC')
            reg, ap, value = args
            if name.endswith('ReadAPDPReg'):
                result = self.bus.read(reg, bool(ap))
                if self.bad_cpuid and self.bus.tar == 0xe000ed00: result ^= 1
                C.cast(value, C.POINTER(C.c_uint32)).contents.value = result
            else: self.bus.write(reg, bool(ap), value)
            return 0
        assert name != 'JLINKARM_CORESIGHT_Configure'
        return super().call(name, *args, **kwargs)


class Tests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.out = Path(self.temp.name)
        self.original, self.before, self.manifest, self.files, self.identity, self.options = prior.fixture()
    def run_writer(self, link, phase='provision'):
        before, after, stage = self.before, self.files['expected-full-B5-new-config-private.bin'], self.files['sector3-uncommitted-private.bin']
        if phase == 'restore_config':
            before, after = after, before
            old = self.files['sector3-original-private.bin']; stage = old[:20]+b'\xff'*4+old[24:]
        loaded = ({}, {'options-private.bin': self.options}, self.identity, before, after, stage)
        real_engine = w.Engine
        def engine(io, *args, **kw):
            result = real_engine(io, *args, **kw)
            link.mem.engine = result
            link.mem.guard = lambda address, value: None  # 真实DapBridge已调用一次状态机授权。
            return result
        with patch.object(w.recovery, 'protected', side_effect=lambda path, _: Path(path)), \
             patch.object(w.planner, 'APP_SHA', w.sha(before[:42552])), \
             patch.object(w, 'Engine', side_effect=engine), \
             patch.object(w.ro.old.runtime, 'core_if_halted', return_value={'registers': {'R15': 0x08000101, 'MSP': 0x20020000}}):
            return w.execute(link, self.out, {'phase': phase, 'entry_runtime_state_hex': '00000000'}, loaded)
    def link(self): return Connected(self.out, self.before, self.options, self.identity)
    def test_connected_real_engine_commits_last_preserves_other_bytes_and_dual_reads(self):
        link = self.link(); result = self.run_writer(link)
        self.assertEqual(result['exit_code'], 0)
        self.assertEqual(bytes(link.mem.flash), self.files['expected-full-B5-new-config-private.bin'])
        self.assertEqual((link.full_reads, link.option_reads), (4, 4))
        self.assertEqual(link.actions, {'JLINKARM_Halt': 1, 'JLINKARM_Reset': 1, 'JLINKARM_Go': 1})
        data = [x for x in link.mem.writes if p.BASE <= x[0] < p.END]
        self.assertEqual(data[-1], (p.COMMIT, 0x54494d43, 'COMMIT'))
        self.assertEqual(link.mem.erase_count, 1); self.assertTrue(link.close_resume_enabled)
        self.assertEqual(link.bus.read_dp2, 0)
        first = next(i for i,e in enumerate(link.trace) if e[0].endswith('APDPReg'))
        self.assertTrue(all(any(e[1] == a for e in link.trace[:first] if e[0].startswith('SDK_'))
                            for a in (0xe000ed00, 0x08000000, p.CR, p.SR)))
        self.assertFalse(any(e[0] == 'JLINKARM_CORESIGHT_Configure' for e in link.trace))
    def test_separate_RCFG_restores_original_config_only(self):
        link = Connected(self.out, self.files['expected-full-B5-new-config-private.bin'], self.options, self.identity)
        self.run_writer(link, 'restore_config')
        self.assertEqual(bytes(link.mem.flash), self.before)
        self.assertEqual(link.active_engine.commits, 1)
    def test_disconnected_context_stops_before_any_raw_or_unlock(self):
        link = self.link(); link.connected = False
        with self.assertRaisesRegex(ValueError, 'NOT_CONNECTED'): self.run_writer(link)
        self.assertEqual(link.mem.writes, []); self.assertFalse(link.close_resume_enabled)
    def test_raw_identity_mismatch_stops_before_KEYR(self):
        link = self.link(); link.bad_cpuid = True
        with self.assertRaises(ValueError): self.run_writer(link)
        self.assertEqual(link.mem.writes, []); self.assertFalse(link.close_resume_enabled)
    def test_sdk_second_backup_drift_stops_before_halt(self):
        link = self.link(); link.before_second_bad = True
        with self.assertRaisesRegex(ValueError, 'DRIFT'): self.run_writer(link)
        self.assertEqual(link.actions, {}); self.assertFalse(link.close_resume_enabled)
    def test_posthalt_armed_change_stops_without_unlock(self):
        link = self.link(); link.armed_after_halt = True
        with self.assertRaisesRegex(ValueError, 'ARMED_CHANGED'): self.run_writer(link)
        self.assertEqual(link.mem.writes, [])
    def test_raw_error_latches_and_prevents_finally_AP_cleanup(self):
        link = object.__new__(w.NativeLink); calls = []
        def native(name, *a, **kw): calls.append(name); return -17
        link._call_native = native
        self.assertEqual(link.call('JLINKARM_CORESIGHT_ReadAPDPReg', 0, 1, None), -17)
        with self.assertRaisesRegex(ValueError, 'STOP_LATCHED'):
            link.call('JLINKARM_CORESIGHT_WriteAPDPReg', 2, 0, 0)
        self.assertEqual(len(calls), 1)
    def test_configure_never_reaches_DLL(self):
        link = object.__new__(w.NativeLink)
        with patch.object(link, '_call_native') as native:
            with self.assertRaisesRegex(ValueError, 'RECONFIGURE'): link.call('JLINKARM_CORESIGHT_Configure', b'')
            native.assert_not_called()
    def test_negative_and_positive_short_reads_are_distinguished_and_logged(self):
        for returned, reason in ((-1, 'MEMORY_NATIVE_ERROR'), (3, 'POSITIVE_SHORT_READ')):
            link = object.__new__(w.NativeLink); link.io = io.StringIO()
            link.call = lambda *a, **kw: returned
            with self.assertRaisesRegex(ValueError, reason): link.read(0xe000ed00, 4)
            self.assertEqual(json.loads(link.io.getvalue())['returned'], returned)
    def test_callback_fingerprint_has_API_time_no_plaintext(self):
        link = object.__new__(w.NativeLink); link.log = io.BytesIO(); link.active_api = 'JLINKARM_ReadMemEx'
        link.install_log_filters(); link.error_callback(b'SYNTHETIC_PRIVATE_MESSAGE')
        row = json.loads(link.log.getvalue())
        self.assertEqual(row['inflight_host_API'], link.active_api); self.assertGreater(row['monotonic_s'], 0)
        self.assertNotIn(b'SYNTHETIC_PRIVATE_MESSAGE', link.log.getvalue()); self.assertTrue(link.error)
    def test_default_and_old_scope_cannot_enable_native(self):
        self.assertFalse(w.plan()['enabled']); self.assertEqual(w.plan()['CORESIGHT_Configure_calls'], 0)
        with self.assertRaisesRegex(ValueError, 'OWNER_AUTH'):
            w.authorize({'enabled': True, 'owner_approved': True, 'scope': 'B5_G2B_SECTOR3_PROVISION_COMMIT_LAST_RAW_MEMAP'}, self.out)
    def auth(self, phase='provision'):
        scope = w.PROVISION if phase == 'provision' else w.RESTORE
        facts = dict(JLink_target='C', latest_power_state_checked=True, A_bus_disconnected=True,
                     no_human=True, C_power_ready=True, USB_and_CAN_state_frozen=True,
                     BOOT_and_RESET_untouched=True, ESP_isolated=False, ESP_present_powered=True,
                     ESP_autonomous_network='UNKNOWN')
        raw = json.dumps(facts).encode()
        a = dict(enabled=True, owner_approved=True, scope=scope, phase=phase, board='C',
                 tools_sha256=w.bindings(), DLL_sha256=w.ro.raw.DLL_SHA,
                 card_sha256=w.sha((ROOT/'node-b/docs'/w.CARDS[phase]).read_bytes()),
                 entry_runtime_state_hex='00000000', expires_unix=time.time()+60,
                 session_timeout_s=180, probe_sessions=1, retries=0,
                 failure_cleanup_scope='PG_CLEAR_CR_LOCK_AND_ORIGINAL_ACR_IF_IDLE_ONLY', nonhuman_mock=True,
                 output=str(self.out), site_record='SYNTHETIC_ONLY', site_record_sha256=w.sha(raw),
                 ESP_isolated=False, ESP_present_powered_exception_approved=True, ESP_exception_scope=scope,
                 package='SYNTHETIC_ONLY', package_binding_sha256='SYNTHETIC_ONLY')
        return a, raw
    def test_config_ESP_permission_is_transaction_specific_not_install_waiver(self):
        for key, value in [('ESP_present_powered_exception_approved', False),
                           ('ESP_exception_scope', 'B5_G2A_C012_OWNER_ESP_PRESENT_POWERED_EXCEPTION'),
                           ('ESP_isolated', True)]:
            a, raw = self.auth(); a[key] = value
            with patch.object(w.recovery, 'read', return_value=raw), patch.object(w, 'load_package') as load:
                with self.assertRaisesRegex(ValueError, 'TRANSACTION_ESP'): w.authorize(a, self.out)
                load.assert_not_called()
    def test_isolation_unknown_cannot_be_promoted_to_true(self):
        a, raw = self.auth(); facts = json.loads(raw); facts['ESP_isolated'] = 'UNKNOWN'
        raw = json.dumps(facts).encode(); a['site_record_sha256'] = w.sha(raw)
        with patch.object(w.recovery, 'read', return_value=raw), patch.object(w, 'load_package') as load:
            with self.assertRaisesRegex(ValueError, 'TRANSACTION_ESP'): w.authorize(a, self.out)
            load.assert_not_called()
    def test_provision_and_restore_reach_package_only_under_their_own_card(self):
        for phase in ('provision', 'restore_config'):
            a, raw = self.auth(phase)
            with patch.object(w.recovery, 'read', return_value=raw), \
                 patch.object(w, 'load_package', side_effect=ValueError('SYNTHETIC_PACKAGE_BOUNDARY')):
                with self.assertRaisesRegex(ValueError, 'PACKAGE_BOUNDARY'): w.authorize(a, self.out)
    def test_card_or_tool_drift_stops_before_private_read(self):
        for key, value in [('card_sha256', '0'*64), ('tools_sha256', {})]:
            a, raw = self.auth(); a[key] = value
            with patch.object(w.recovery, 'read') as read:
                with self.assertRaisesRegex(ValueError, 'DRIFT'): w.authorize(a, self.out)
                read.assert_not_called()

    def test_native_negative_return_saved_before_error_callback_gate(self):
        link = object.__new__(w.NativeLink); link.sdk_calls = 0; link.sdk_limit = 5
        link.io = io.StringIO(); link.events = io.StringIO(); link.error = False
        def native(*args): link.error = True; return -1
        link.dll = types.SimpleNamespace(JLINKARM_ReadMemEx=native)
        link.gate = lambda: w.require(not link.error, 'S3_SYNTHETIC_SDK_CALLBACK_ERROR')
        with self.assertRaisesRegex(ValueError, 'CALLBACK_ERROR'):
            link.call('JLINKARM_ReadMemEx', 0xe000ed00, 4, None, 0)
        row = json.loads(link.io.getvalue())
        self.assertEqual(row['native_return_int'], -1)
        self.assertEqual((row['address'], row['requested']), ('0xe000ed00', 4))

if __name__ == '__main__': unittest.main()
