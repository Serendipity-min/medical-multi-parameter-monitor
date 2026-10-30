"""P1-A入口拒止测试；仅内存授权和驱动替身，不创建现场令牌。"""
import ast
from contextlib import ExitStack, redirect_stdout
import copy
import io
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT/'node-b/tools'), str(ROOT/'node-b/tests')]
import b5_g3_contract as g
import b5_channel_profiles as p
import b5_g3_joint as joint
import b5_g3_devices as devices
import build_b4_arm as build
import test_b5_channel_profiles as legacy


class EntryGate(unittest.TestCase):
    def test_actual_main_all_field_flags_reject_mock_before_driver_or_marker(self):
        for flag in ('--execute','--joint-worker','--c-worker','--ack-c-reset','--c-check'):
            a = dict(scope=p.FINAL_SCOPES_R6['ECG60'], execution_mode='OFFLINE_MOCK')
            with self.subTest(flag=flag), ExitStack() as stack:
                stack.enter_context(patch.object(sys,'argv',['G3_INPROCESS_FIXTURE',flag,'--authorization','SYNTHETIC_ONLY']))
                stack.enter_context(patch.object(g,'load',return_value=a))
                save = stack.enter_context(patch.object(g,'save',side_effect=AssertionError('marker/write forbidden')))
                worker = stack.enter_context(patch.object(joint,'joint_worker',side_effect=AssertionError('worker forbidden')))
                cworker = stack.enter_context(patch.object(devices,'c_preflight',side_effect=AssertionError('SDK forbidden')))
                stack.enter_context(redirect_stdout(io.StringIO()))
                self.assertEqual(joint.main(),1)
                save.assert_not_called();worker.assert_not_called();cworker.assert_not_called()

    def test_actual_main_fake_signed_r6_refused_before_children(self):
        for flag in ('--execute','--joint-worker','--c-worker','--ack-c-reset','--c-check'):
            a=dict(scope=p.FINAL_SCOPES_R6['ECG60'],enabled=True,owner_approved=True,
                   pi_signature='ok',field_execution_authorized=True,nonce='SYNTHETIC_REUSED_NONCE')
            with self.subTest(flag=flag),patch.object(sys,'argv',['G3_INPROCESS_FIXTURE',flag,'--authorization','SYNTHETIC_ONLY']), \
                 patch.object(g,'load',return_value=a),patch.object(g,'save') as save, \
                 patch.object(joint.subprocess,'Popen',side_effect=AssertionError('child forbidden')) as popen, \
                 redirect_stdout(io.StringIO()):
                self.assertEqual(joint.main(),1)
                save.assert_not_called();popen.assert_not_called()

    def test_fake_signatures_old_tokens_wrong_board_and_reused_nonce_always_denied(self):
        for fields in ({'pi_signature':'ok'}, {'field_execution_authorized':True},
                       {'nonce':'SYNTHETIC_REUSED_NONCE'}, {'scope':p.FINAL_SCOPES_R5['ECG60'],'execution_mode':'OFFLINE_MOCK'},
                       {'JLink_target':'C'}, {'B_ELF':'WRONG_ABI'}):
            a=dict(scope=p.FINAL_SCOPES_R6['ECG60'],enabled=True,owner_approved=True,**{})
            a.update(fields)
            for attempt in range(2):
                with self.subTest(fields=fields,attempt=attempt),self.assertRaisesRegex(ValueError,'FIELD'):
                    g.validate(a,g.G3)

    def test_r1_to_r5_dispatch_still_uses_original_profile(self):
        for scopes in (p.FINAL_SCOPES,p.FINAL_SCOPES_R2,p.FINAL_SCOPES_R3,p.FINAL_SCOPES_R4,p.FINAL_SCOPES_R5):
            for scope in scopes.values():
                a={'scope':scope}
                with self.subTest(scope=scope),patch.object(p,'validate',return_value=('bundle','site')) as call:
                    self.assertEqual(g.validate(a,g.G3),('bundle','site'))
                    call.assert_called_once_with(a,execution_context='FIELD')

    def test_invalid_execution_context_never_selects_field(self):
        with self.assertRaisesRegex(ValueError,'EXECUTION_CONTEXT'):
            g.validate({'scope':p.FINAL_SCOPES_R6['ECG60']},g.G3,execution_context='AUTOMATIC')


class BoundMock(unittest.TestCase):
    def run_existing_r6_fixture(self, changes=None, expected_override=None, receipt_age=None):
        actual=p.validate
        observed=[]
        def validate(a,*,execution_context='FIELD'):
            a=copy.deepcopy(a)
            a.update(changes or {})
            observed.append(execution_context)
            with ExitStack() as stack:
                if receipt_age is not None:
                    read=g.private.read
                    receipt=json.loads(read(Path('cpre'),False))
                    receipt['observed_unix']=p.time.time()-receipt_age
                    blob=json.dumps(receipt).encode()
                    a['C_preflight_receipt_sha256']=g.sha(blob)
                    stack.enter_context(patch.object(g.private,'read',side_effect=lambda path,flag:
                        blob if str(path)=='cpre' else read(path,flag)))
                if expected_override:
                    name,value=expected_override
                    stack.enter_context(patch.object(p,name,value))
                return actual(a,execution_context=execution_context)
        with patch.object(p,'validate',side_effect=validate):
            legacy.SyntheticAdmission().test_r6_positive_mock_validates_cleanly_with_b41012b()
        self.assertEqual(observed,['OFFLINE_MOCK'])

    def test_g3_to_profile_full_mock_admission(self):
        self.run_existing_r6_fixture()

    def test_old_card_in_r6_mock_rejected(self):
        with self.assertRaisesRegex(ValueError,'FINAL_CARD'):
            self.run_existing_r6_fixture({'execution_card':p.FINAL_CARD_R5.name})

    def test_cross_profile_rejected(self):
        with self.assertRaisesRegex(ValueError,'FINAL_OBJECT'):
            self.run_existing_r6_fixture({'channel_profile':'RR15'})

    def test_mock_declaration_without_mock_context_cannot_enable_profile(self):
        with self.assertRaisesRegex(ValueError,'FIELD_EXECUTION_BLOCKED'):
            actual=p.validate
            def validate(a,**kwargs):return actual(a)
            with patch.object(p,'validate',side_effect=validate):
                legacy.SyntheticAdmission().test_r6_positive_mock_validates_cleanly_with_b41012b()

    def test_wrong_elf_and_symbols_rejected(self):
        for name in ('B_ELF_R6','B_SYMBOLS_R6'):
            with self.subTest(name=name),self.assertRaisesRegex(ValueError,'B_ABI'):
                self.run_existing_r6_fixture(expected_override=(name,'0'*64))

    def test_old_b40928_image_cannot_impersonate_b41012(self):
        profile={**p.B_PROFILE_R6,'BIN_bytes':40928,'BIN_sha256':'0'*64}
        with self.assertRaisesRegex(ValueError,'B_IMAGE'):
            self.run_existing_r6_fixture(expected_override=('B_PROFILE_R6',profile))

    def test_3601_second_receipt_and_86400_waiver_rejected(self):
        for age in (3601,86400):
            with self.subTest(age=age),self.assertRaisesRegex(ValueError,'C_PREFLIGHT'):
                self.run_existing_r6_fixture(receipt_age=age)


class BuilderAssertions(unittest.TestCase):
    def anchors(self):
        tree=ast.parse(Path(build.__file__).read_text(encoding='utf-8'))
        fn=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='inject_r6')
        return [ast.literal_eval(n.args[1]) for n in ast.walk(fn)
                if isinstance(n,ast.Call) and isinstance(n.func,ast.Name) and n.func.id=='replace_once']

    def test_eight_unique_anchors_and_preserved_sampling_source(self):
        source=(ROOT/'node-b/firmware/biov2/实验固件/HARDWARE/hr_page.c').read_text(encoding='utf-8')
        anchors=self.anchors();self.assertEqual(len(anchors),8)
        self.assertTrue(all(source.count(a)==1 for a in anchors))
        candidate=build.inject_r6(source)
        self.assertEqual(candidate.count('FrameFeed(TimeBase_GetMs());')-source.count('FrameFeed(TimeBase_GetMs());'),8)

    def test_missing_or_duplicate_each_anchor_refused(self):
        source=(ROOT/'node-b/firmware/biov2/实验固件/HARDWARE/hr_page.c').read_text(encoding='utf-8')
        for anchor in self.anchors():
            for broken in (source.replace(anchor,''),source+'\n'+anchor):
                with self.subTest(anchor=anchor),self.assertRaisesRegex(RuntimeError,'ANCHOR_NOT_UNIQUE'):
                    build.inject_r6(broken)


if __name__=='__main__':
    unittest.main()
