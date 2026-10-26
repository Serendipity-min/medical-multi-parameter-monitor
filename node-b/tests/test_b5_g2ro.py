"""G2-RO必要离线负例：SDK替身与真实子进程监督，不加载调试器。"""
import ctypes
import io
import json
from pathlib import Path
import struct
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch
import zlib

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/'node-b/tools'))
import b5_g2ro as read
import b5_g2ro_supervisor as supervisor


def fixture():
    blob = bytearray(b'\xa5'*1048576)
    struct.pack_into('<II', blob, 0, 0x20020000, 0x08000101)
    record = bytearray(336)
    struct.pack_into('<IHHIIII', record, 0, 0x32433348, 1, 24, 312, 7, 0, 0x54494D43)
    struct.pack_into('<II', record, 24, 0x31435747, 1700000000)
    for offset, value in [(171, b'SYNTHETIC_OLD_USR'), (269, b'SYNTHETIC_OLD_ID!')]:
        record[24+offset:24+offset+len(value)] = value
    assert len(record) == 336
    struct.pack_into('<I', record, 16, zlib.crc32(record[:16]+record[24:]))
    blob[49152:49152+336] = record
    assert len(blob) == 1048576
    ident = {'cpuid': 0x410fc241, 'device_id': 0x10000413, 'capacity_kib': 1024,
             'uid_hex': '5a'*12, 'optcr': 0x0fffaaed, 'flash_sr': 0}
    return ident, bytes(blob), b'\xaa\x55'*8


class FakeRead:
    def __init__(self, reference):
        self.ident, self.image, self.options = reference
        self.verified_running_flash = False; self.close_resume_enabled = False
        self.reads = []; self.flash_reads = 0; self.option_reads = 0
        self.rom = False; self.halted = False; self.corrupt_second = False; self.option_drift = False
    def open(self): pass
    def u32(self, address):
        values = {0xe000ed00: self.ident['cpuid'], 0xe0042000: self.ident['device_id'],
                  0x40023c14: self.ident['optcr'], 0x40023c0c: 0, 0x40023c10: 0x80000000,
                  read.SYSTEM['DHCSR']: read.raw.HALT if self.halted else 0,
                  read.SYSTEM['VTOR']: 0x1fff0000 if self.rom else 0x08000000,
                  read.SYSTEM['DWT_PCSR']: 0x1fff32f0 if self.rom else 0x08000201}
        return values.get(address, 0)
    def read(self, address, size):
        self.reads.append((address, size))
        if address == 0x1fff7a10: return bytes.fromhex(self.ident['uid_hex'])
        if address == 0x1fff7a22: return (1024).to_bytes(2, 'little')
        if address == 0x1fffc000:
            self.option_reads += 1
            return bytes(16) if self.option_drift else self.options
        if address == 0x08000000 and size == 1048576:
            self.flash_reads += 1
            return self.image[:-1]+b'\x00' if self.corrupt_second and self.flash_reads == 2 else self.image
        return self.u32(address).to_bytes(size, 'little')
    def set_close_resume(self, enabled): self.close_resume_enabled = enabled


class Tests(unittest.TestCase):
    def setUp(self):
        parent = ROOT/'node-b/build'; parent.mkdir(exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=parent, prefix='g2ro-fake-')
        self.addCleanup(self.temp.cleanup); self.out = Path(self.temp.name)
        self.reference = fixture()
    def capture(self, fake=None, reference=None):
        with patch.object(read.recovery, 'protected', side_effect=lambda p, _: Path(p)):
            return read.capture(fake or FakeRead(self.reference), self.out, reference or self.reference)
    def policy_link(self):
        link = object.__new__(read.ReadLink)
        link.counts = {}; link.sdk_calls = 0; link.io = io.StringIO()
        link.verified_running_flash = False
        return link

    def test_complete_double_reads_and_all_sectors(self):
        f = FakeRead(self.reference); result = self.capture(f)
        self.assertEqual(result['status'], 'C24104_FRESH_DOUBLE_READ_PASS')
        self.assertEqual(f.flash_reads, 2); self.assertEqual(f.option_reads, 2)
        self.assertEqual(len([x for x in f.reads if x == (0x08000000, 1048576)]), 2)
        self.assertEqual((self.out/'flash-1-private.bin').read_bytes(), (self.out/'flash-2-private.bin').read_bytes())
        for name, (a, b) in read.REGIONS.items():
            self.assertEqual((self.out/(name+'-1-private.bin')).read_bytes(), self.reference[1][a:b])
            self.assertEqual((self.out/(name+'-2-private.bin')).read_bytes(), self.reference[1][a:b])
        self.assertEqual(result['real_PC'], 'NOT_OBSERVED_RUNNING_NO_HALT')
        self.assertFalse(result['config']['B5_identity_matches'])

    def test_wrong_board_UID_stops_before_full_read(self):
        f = FakeRead(self.reference); f.ident = {**f.ident, 'uid_hex': '6b'*12}
        with self.assertRaisesRegex(ValueError, 'WRONG_C_IDENTITY'): self.capture(f)
        self.assertEqual(f.flash_reads, 0)

    def test_ROM_stops_without_recovery(self):
        f = FakeRead(self.reference); f.rom = True
        with self.assertRaisesRegex(ValueError, 'ROM_STOP'): self.capture(f)
        self.assertEqual(f.flash_reads, 0); self.assertFalse(f.close_resume_enabled)

    def test_HALTED_stops_without_Go(self):
        f = FakeRead(self.reference); f.halted = True
        with self.assertRaisesRegex(ValueError, 'HALTED_LOCKUP'): self.capture(f)
        self.assertEqual(f.flash_reads, 0)

    def test_second_read_drift_retains_both_negative_originals(self):
        f = FakeRead(self.reference); f.corrupt_second = True
        with self.assertRaisesRegex(ValueError, 'FLASH_DRIFT'): self.capture(f)
        self.assertNotEqual((self.out/'flash-1-private.bin').read_bytes(), (self.out/'flash-2-private.bin').read_bytes())
        self.assertEqual(f.flash_reads, 2)

    def test_first_flash_drift_stops_before_second_read(self):
        f = FakeRead(self.reference); f.image = f.image[:-1]+b'\x00'
        with self.assertRaisesRegex(ValueError, 'FLASH_DRIFT'): self.capture(f)
        self.assertEqual(f.flash_reads, 1)

    def test_options_drift_stops_before_full_read(self):
        f = FakeRead(self.reference); f.option_drift = True
        with self.assertRaisesRegex(ValueError, 'OPTIONS_DRIFT'): self.capture(f)
        self.assertEqual(f.flash_reads, 0)

    def test_short_native_read_rejected(self):
        link = self.policy_link()
        with patch.object(read.raw.Link, 'call', return_value=15):
            with self.assertRaisesRegex(ValueError, 'PARTIAL_READ'): link.read(0x1fffc000, 16)

    def test_Reset_Halt_Go_writes_and_PC_reads_denied_before_sdk(self):
        link = self.policy_link()
        names = ('JLINKARM_Reset', 'JLINKARM_Halt', 'JLINKARM_Go', 'JLINKARM_WriteReg',
                 'JLINKARM_WriteMem', 'JLINKARM_BeginDownload', 'JLINKARM_EndDownload', 'JLINKARM_ReadReg')
        with patch.object(read.raw.Link, 'call') as native:
            for name in names:
                with self.assertRaisesRegex(ValueError, 'FUNCTION_DENIED'): link.call(name)
            native.assert_not_called()

    def test_unknown_policy_and_unverified_close_denied(self):
        link = self.policy_link()
        with patch.object(read.raw.Link, 'call') as native:
            for value in (b'Unlock', b'SetPC = 0x08000001', b'SetRestartOnClose = 1'):
                with self.assertRaises(ValueError): link.call('JLINKARM_ExecCommand', value, None, 0)
            native.assert_not_called()

    def test_RestartOnClose_previous_value_confirmation_is_finite(self):
        link=self.policy_link()
        with patch.object(read.raw.Link,'call',side_effect=[1,0]) as native:
            link.policy('SetRestartOnClose 0');self.assertEqual(native.call_count,2)
        link=self.policy_link()
        with patch.object(read.raw.Link,'call',side_effect=[1,1]) as native:
            with self.assertRaisesRegex(ValueError,'POLICY_NOT_ACCEPTED'):link.policy('SetRestartOnClose 0')
            self.assertEqual(native.call_count,2)

    def test_close_policy_counts_cannot_exceed_frozen_budget(self):
        link=self.policy_link();link.verified_running_flash=True
        with patch.object(read.raw.Link,'call',return_value=0) as native:
            for _ in range(6):link.call('JLINKARM_ExecCommand',b'SetRestartOnClose 0',None,0)
            with self.assertRaisesRegex(ValueError,'POLICY_LIMIT'):link.call('JLINKARM_ExecCommand',b'SetRestartOnClose 0',None,0)
            link.call('JLINKARM_ExecCommand',b'SetRestartOnClose = 1',None,0)
            with self.assertRaisesRegex(ValueError,'POLICY_LIMIT'):link.call('JLINKARM_ExecCommand',b'SetRestartOnClose = 1',None,0)
            self.assertEqual(native.call_count,7)

    def test_address_flags_and_third_full_read_denied(self):
        link = self.policy_link()
        with patch.object(read.raw.Link, 'call', return_value=1048576) as native:
            for _ in range(2): link.call('JLINKARM_ReadMemEx', 0x08000000, 1048576, None, 0)
            with self.assertRaisesRegex(ValueError, 'DOUBLE_READ_LIMIT'):
                link.call('JLINKARM_ReadMemEx', 0x08000000, 1048576, None, 0)
            with self.assertRaisesRegex(ValueError, 'ADDRESS_DENIED'):
                link.call('JLINKARM_ReadMemEx', 0x20000000, 131072, None, 0)
            with self.assertRaisesRegex(ValueError, 'ADDRESS_DENIED'):
                link.call('JLINKARM_ReadMemEx', 0x1fffc000, 16, None, 1)
            self.assertEqual(native.call_count, 2)

    def test_SDK_text_logs_never_contain_UID_plaintext(self):
        link = self.policy_link(); link.log = io.BytesIO(); link.error = False
        link.install_log_filters()
        uid = b'SYNTHETIC_UID_5a5a5a5a5a5a5a5a5a5a5a5a'
        link.logger(uid); link.error_callback(uid)
        self.assertNotIn(uid, link.log.getvalue()); self.assertTrue(link.error)
        self.assertIn(read.digest(uid).encode(), link.log.getvalue())

    def test_invalid_CRC_or_commit_is_not_config_pass(self):
        sector = bytearray(self.reference[1][49152:65536])
        self.assertTrue(read.config_record(sector)['header_committed_CRC_valid'])
        sector[300] ^= 1; self.assertFalse(read.config_record(sector)['header_committed_CRC_valid'])
        sector = bytearray(self.reference[1][49152:65536]); sector[20:24] = b'\xff'*4
        self.assertFalse(read.config_record(sector)['header_committed_CRC_valid'])

    def test_B5_identity_test_does_not_expose_fields(self):
        sector = bytearray(self.reference[1][49152:65536])
        sector[24+171:24+204] = b'b5-gateway\0'+bytes(22)
        sector[24+269:24+310] = b'b5-c-isolated\0'+bytes(27)
        struct.pack_into('<I', sector, 16, zlib.crc32(sector[:16]+sector[24:336]))
        result = read.config_record(sector)
        self.assertTrue(result['B5_identity_matches']); self.assertEqual(set(result), {'header_committed_CRC_valid','CRC_matches','B5_identity_matches'})

    def test_disabled_authorization_never_launches_process(self):
        with patch.object(read, 'private_read', return_value=b'{}'), patch.object(supervisor.subprocess, 'Popen') as spawn:
            with self.assertRaisesRegex(ValueError, 'OWNER_AUTH_REQUIRED'): supervisor.supervise(self.out/'auth', self.out/'capture')
            spawn.assert_not_called()

    def test_EFS_failure_refused_before_SDK(self):
        path = self.out/'unencrypted-authorization.json'; path.write_text('{}')
        with patch.object(read.recovery, 'PRIVATE', self.out):
            with self.assertRaisesRegex(ValueError, 'EFS_REQUIRED'): read.private_read(path)
        with self.assertRaises((ValueError, OSError)):
            read.private_read(self.out/'unencrypted-authorization.json')

    def authorization(self):
        site = {'JLink_target':'C', 'HW0_completed':True, 'cold_transfer_completed':True,
                'no_hot_transfer':True, 'C_power_ready':True, 'C_USB_unchanged_for_session':True,
                'BOOT_and_RESET_untouched':True, 'readback_only_no_power_change':True,
                'cold_transfer_authorization_id':'SYNTHETIC_OFFLINE_TRANSFER'}
        blobs = {'site':json.dumps(site).encode(), 'identity':json.dumps(self.reference[0]).encode(),
                 'flash':self.reference[1], 'options':self.reference[2]}
        a = read.plan();a.update(enabled=True, owner_approved=True, expires_unix=time.time()+60,
            output=str(self.out/'capture'), site_record='site',site_record_sha256=read.digest(blobs['site']))
        for name in ('identity','flash','options'):
            a[name+'_reference']=name;a[name+'_reference_sha256']=read.digest(blobs[name])
        a['expected_full_sha256']=read.digest(blobs['flash']);a['expected_options_sha256']=read.digest(blobs['options'])
        return a,blobs

    def validate_fixture(self, auth, blobs):
        with patch.object(read, 'private_read', side_effect=lambda p: blobs[str(p)]), patch.object(read.recovery, 'protected', side_effect=lambda p,_:Path(p)), patch.object(read, 'CURRENT_SHA', read.digest(self.reference[1])), patch.object(read, 'OPTIONS_SHA', read.digest(self.reference[2])):
            return read.validate_authorization(auth,self.out/'capture')

    def test_full_authorization_bindings_without_DLL_load(self):
        a,b=self.authorization();self.assertEqual(self.validate_fixture(a,b),self.reference)
        self.assertEqual(read.plan()['explicit_reset_halt_go_and_target_writes'],0)

    def test_tool_expiry_site_and_reference_drift_are_rejected(self):
        for field,value in [('tools_sha256',{}),('expires_unix',0),('probe_sessions',2),('output',str(self.out/'different')),('identity_reference_sha256','0'*64)]:
            a,b=self.authorization();a[field]=value
            with self.subTest(field=field), self.assertRaises(ValueError):self.validate_fixture(a,b)
        a,b=self.authorization();s=json.loads(b['site']);s['JLink_target']='B';b['site']=json.dumps(s).encode();a['site_record_sha256']=read.digest(b['site'])
        with self.assertRaisesRegex(ValueError,'SITE_NOT_READY'):self.validate_fixture(a,b)

    def test_session_authorization_is_not_reusable(self):
        auth=self.out/'auth.json';out=self.out/'capture';blob=b'{"synthetic":true}'
        child=unittest.mock.Mock();child.poll.return_value=7;child.returncode=7
        with patch.object(read, 'private_read',return_value=blob), patch.object(read,'validate_authorization'), patch.object(read.recovery,'protected',side_effect=lambda p,_:Path(p)), patch.object(supervisor.subprocess,'Popen',return_value=child) as spawn:
            self.assertEqual(supervisor.supervise(auth,out),1)
            self.assertEqual(json.loads((out/'supervisor-private.json').read_text())['worker_exit_code'],7)
            self.assertEqual(spawn.call_count,1)
            with self.assertRaisesRegex(ValueError,'OUTPUT_EXISTS'):supervisor.supervise(auth,out)
            self.assertEqual(spawn.call_count,1)
            self.assertEqual(json.loads(auth.with_suffix('.used').read_text())['authorization_sha256'],read.digest(blob))

    def test_supervisor_exception_preserves_worker_exit_and_does_not_reconnect(self):
        child=unittest.mock.Mock();child.poll.side_effect=[None,None,9];child.returncode=9
        with patch.object(read,'private_read',return_value=b'{}'), patch.object(read,'validate_authorization'), patch.object(read.recovery,'protected',side_effect=lambda p,_:Path(p)), patch.object(supervisor.subprocess,'Popen',return_value=child), patch.object(supervisor,'watch',side_effect=TypeError):
            self.assertEqual(supervisor.supervise(self.out/'auth.json',self.out/'capture'),1)
        r=json.loads((self.out/'capture/supervisor-private.json').read_text());self.assertEqual(r['reason'],'SUPERVISOR_EXCEPTION');self.assertEqual(r['worker_exit_code'],9)

    def test_missing_supervisor_marker_refused_before_link(self):
        auth = {'enabled': True}
        with patch.object(read, 'validate_authorization', return_value=self.reference), patch.object(read, 'private_read', side_effect=FileNotFoundError), patch.object(read, 'ReadLink') as link:
            with self.assertRaises(FileNotFoundError): read.worker(auth, self.out/'auth.json', self.out/'capture')
            link.assert_not_called()

    def sleeping_child(self):
        child = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(10)'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        self.addCleanup(lambda: child.kill() if child.poll() is None else None)
        return child

    def test_total_timeout_kills_real_child_and_preserves_native_exit(self):
        child = self.sleeping_child(); result = supervisor.watch(child, self.out, timeout_s=.05, poll_s=.005)
        self.assertEqual(result['reason'], 'SESSION_TIMEOUT'); self.assertNotEqual(result['worker_exit_code'], 0)
        self.assertEqual(result['supervisor_exit_code'], 1); self.assertFalse(result['automatic_retry_or_hardware_recovery'])

    def test_SDK_deadline_kills_real_child(self):
        (self.out/'heartbeat-events.jsonl').write_text(json.dumps({'active':True,'deadline_monotonic':time.monotonic()-1})+'\n')
        child = self.sleeping_child(); result = supervisor.watch(child, self.out, timeout_s=1)
        self.assertEqual(result['reason'], 'SDK_TIMEOUT'); self.assertNotEqual(result['worker_exit_code'], 0)

    def test_owner_stop_kills_without_retry(self):
        (self.out/'STOP').touch(); child = self.sleeping_child()
        self.assertEqual(supervisor.watch(child, self.out, timeout_s=1)['reason'], 'OWNER_STOP')


if __name__ == '__main__': unittest.main(verbosity=2)
