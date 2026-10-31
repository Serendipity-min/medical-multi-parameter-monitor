"""只验证负责人单次薄入口的签名和范围，不访问设备。"""
import argparse
import contextlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
import b5_m1_owner_once as owner


class OwnerOnce(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.key = Ed25519PrivateKey.generate()
        self.public = self.key.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)
        self.expected = dict(zip(('scope', 'run_id', 'plan_sha256', 'repo_commit', 'repo_tree', 'tools_sha256',
                                  'DLL_sha256', 'bundle_sha256', 'site_sha256', 'cold_start_sha256',
                                  'output', 'manual_stop_responsibility'),
                                 (owner.m.SCOPE, 'M1-E60-R1', 'plan', 'commit', 'tree', {'mock': 'sha'},
                                  'dll', 'bundle', 'site', 'cold', str(self.root/'capture'), 'MOCK_PERSON')))
        self.card = dict(self.expected, authority=owner.AUTHORITY, PI_independent_signature=False,
                         nonce='MOCK_OWNER_NONCE_123456', enabled=True, sessions=1, retries=0,
                         sdk_residual_risk_acknowledged=True, not_before=100, expires=160)
        self.args = argparse.Namespace(authorization=self.root/'card.json', signature=self.root/'sig.bin',
                                       public_key=self.root/'public.raw', worker=False)
        self.args.public_key.write_bytes(self.public)
        for obj, name, value in ((owner, 'PUBLIC_SHA256', owner.m.sha(self.public)),
                                 (owner, 'NONCE_SHA256', owner.m.sha(self.card['nonce'].encode()))):
            p = patch.object(obj, name, value); p.start(); self.addCleanup(p.stop)
        # EFS路径是外部存储边界；其本身另有实际磁盘检查，不在临时夹具中伪称EFS。
        p = patch.object(owner, 'private_file', side_effect=Path); p.start(); self.addCleanup(p.stop)
        p = patch.object(owner.time, 'time', return_value=110); p.start(); self.addCleanup(p.stop)
        self.real_bindings = owner.bindings
        p = patch.object(owner, 'bindings', return_value=(self.expected, {}))
        self.bindings = p.start(); self.addCleanup(p.stop)

    def signed(self, **changes):
        self.card.update(changes)
        raw = json.dumps(self.card).encode()
        self.args.authorization.write_bytes(raw); self.args.signature.write_bytes(self.key.sign(raw))

    def test_owner_signature_accepts_without_changing_PI_root(self):
        self.signed(); self.assertEqual(owner.verify(self.args)[3], self.card)
        self.assertIsNone(owner.m.TRUSTED_PI_KEY_SHA256)

    def test_wrong_public_key_before_bindings(self):
        self.signed(); self.args.public_key.write_bytes(b'x'*32)
        with self.assertRaisesRegex(ValueError, 'M1_OWNER_UNTRUSTED_KEY'): owner.verify(self.args)
        self.bindings.assert_not_called()

    def test_tampered_bytes_before_bindings(self):
        self.signed(); self.args.authorization.write_bytes(self.args.authorization.read_bytes()+b' ')
        with self.assertRaises(InvalidSignature): owner.verify(self.args)
        self.bindings.assert_not_called()

    def test_other_run_before_bindings(self):
        self.signed(run_id='M1-E90-R1')
        with self.assertRaisesRegex(ValueError, 'M1_OWNER_ONCE_SCOPE'): owner.verify(self.args)
        self.bindings.assert_not_called()

    def test_another_nonce_before_bindings(self):
        self.signed(nonce='ANOTHER_NONCE_NOT_AUTHORIZED')
        with self.assertRaisesRegex(ValueError, 'M1_OWNER_ONCE_SCOPE'): owner.verify(self.args)
        self.bindings.assert_not_called()

    def test_cannot_claim_PI_authority(self):
        self.signed(PI_independent_signature=True)
        with self.assertRaisesRegex(ValueError, 'M1_OWNER_ONCE_SCOPE'): owner.verify(self.args)

    def test_expired_or_disabled(self):
        for changes in ({'expires': 110}, {'enabled': False}, {'sessions': 2}, {'retries': 1},
                        {'sdk_residual_risk_acknowledged': False}):
            with self.subTest(changes=changes):
                original = self.card.copy(); self.signed(**changes)
                with self.assertRaises(ValueError): owner.verify(self.args)
                self.card = original

    def test_parent_nonce_no_refund_or_second_use(self):
        self.signed(); raw, _, _, card, _, _ = owner.verify(self.args)
        owner.m.consume_nonce(self.root, raw, card)
        with self.assertRaises(FileExistsError): owner.m.consume_nonce(self.root, raw, card)

    def test_missing_signed_files_exit2(self):
        with patch('sys.argv', ['owner', '--execute']), contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(owner.main(), 2)

    def test_site_rejects_C_USB_or_wrong_ECG_lead(self):
        reference = self.root/'reference.json'; reference.write_text('{}')
        bundle = {k+'_reference': str(reference) for k in ('identity', 'full', 'options')}
        bundle.update({k+'_reference_sha256': owner.m.sha(b'{}') for k in ('identity', 'full', 'options')})
        bundle_file = self.root/'bundle.json'; bundle_file.write_text(json.dumps(bundle))
        site_file = self.root/'site.json'; cold_file = self.root/'cold.json'; cold_file.write_text('{}')
        a = {'bundle_file': str(bundle_file), 'site_file': str(site_file), 'cold_start_file': str(cold_file)}
        site = dict.fromkeys(('owner_approved_topology', 'JLink_on_B', 'nonhuman_source', 'no_human',
                             'B_USB_disconnected', 'SKX_battery_no_charge_USB', 'manual_emergency_cutoff_ready',
                             'sdk_residual_risk_acknowledged', 'C_J5_powered', 'CAN_B_C_connected',
                             'C_USB_disconnected'), True)
        site.update(topology=owner.TOPOLOGY, B_C_electrically_isolated=False, source_mode='NORMAL_ECG',
                    target_rate=60, ECG_amplitude_mV=1, waveform_type_confirmed=True,
                    R_lead='RA', L_lead='LA', F_lead='RL')
        for change in ({'C_USB_disconnected': False}, {'L_lead': 'LL'}, {'target_rate': 90},
                       {'owner_approved_topology': False}):
            with self.subTest(change=change), patch.object(owner.m, 'validate_bundle'):
                site_file.write_text(json.dumps(dict(site, **change)))
                with self.assertRaisesRegex(ValueError, 'M1_OWNER_(SITE_NOT_READY|ECG60_MENU)'):
                    self.real_bindings(a)


if __name__ == '__main__':
    unittest.main()
