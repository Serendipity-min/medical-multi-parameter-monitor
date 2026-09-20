"""用合成结果验证安全门本身，不扫描真实项目，也不模拟攻击。"""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from common import HERE, dump, execute, relative
from normalize import finding, parse
from policy import evaluate, valid_acceptance
from report import write

class PolicyTests(unittest.TestCase):
    def setUp(self):
        self.secret = finding('gitleaks', 'synthetic-rule', 'example.py', '.', 'CRITICAL', kind='secret')
        self.high = finding('semgrep', 'synthetic-rule', 'example.py', '.', 'HIGH')

    def test_secret_fails(self):
        self.assertEqual(evaluate('quick', [], [self.secret], [])['exit_code'], 1)

    def test_critical_cve_fails(self):
        f = finding('trivy', 'CVE-2099-0001', 'requirements.lock', '.', 'CRITICAL', fix=False, kind='dependency')
        self.assertEqual(evaluate('pr', [], [f], [])['exit_code'], 1)

    def test_accepted_and_expired_findings(self):
        accepted = dict(id=self.high['id'], tool='semgrep', path='example.py',
            reason='Documented controlled test code with explicit review evidence', owner='P',
            accepted_at='2020-01-01', expires_at='2099-01-01', review_issue='SEC-001')
        self.assertEqual(evaluate('pr', [], [self.high], [], [accepted])['exit_code'], 2)
        accepted['expires_at'] = '2020-01-02'
        self.assertEqual(evaluate('pr', [], [self.high], [], [accepted])['exit_code'], 1)

    def test_secret_cannot_be_risk_accepted_without_false_positive_evidence(self):
        accepted = dict(id=self.secret['id'], tool='gitleaks', path='example.py',
            reason='Documented accepted demonstration value with owner and expiry', owner='P',
            accepted_at='2020-01-01', expires_at='2099-01-01', review_issue='SEC-001')
        self.assertEqual(evaluate('quick', [], [self.secret], [], [accepted])['exit_code'], 1)

    def test_coverage_gap_and_missing_tool(self):
        self.assertEqual(evaluate('pr', [{'tool':'trivy','status':'MISSING'}], [], [])['exit_code'], 3)
        self.assertEqual(evaluate('pr', [], [], [{'id':'coverage', 'mandatory':True}])['exit_code'], 3)
        self.assertEqual(evaluate('pr', [], [], ['arm-coverage-gap'])['exit_code'], 2)

    def test_dirty_tree_blocks_release_and_dry_run_never_passes(self):
        self.assertEqual(evaluate('release', [], [], [], dirty=True)['exit_code'], 1)
        self.assertEqual(evaluate('quick', [], [], [], dry_run=True)['exit_code'], 2)

    def test_real_data_manual_gate(self):
        result = evaluate('release', [], [], [], real_data=True)
        self.assertEqual(result['real_data_result'], 'FAIL_FOR_REAL_DATA')
        self.assertEqual(result['exit_code'], 1)

    def test_build_failure_and_optional_tool(self):
        self.assertEqual(evaluate('pr', [{'tool':'build','status':'FAIL'}], [], [])['exit_code'], 1)
        self.assertEqual(evaluate('pr', [{'tool':'optional','status':'MISSING','mandatory':False}], [], [])['exit_code'], 2)

    def test_clean_quick_pass(self):
        self.assertEqual(evaluate('quick', [{'tool':'test','status':'OK'}], [], [])['exit_code'], 0)

class ExecutionTests(unittest.TestCase):
    def test_release_snapshot_uses_commit_not_modified_worktree(self):
        from adapters import copy_worktree
        with tempfile.TemporaryDirectory() as folder:
            repo = Path(folder)/'repo'
            work = Path(folder)/'work'
            repo.mkdir()
            work.mkdir()
            subprocess.run(['git','init','-q',str(repo)],check=True)
            (repo/'source.txt').write_text('committed\n')
            subprocess.run(['git','-C',str(repo),'add','.'],check=True)
            subprocess.run(['git','-C',str(repo),'-c','user.name=Test','-c','user.email=test@example.com','commit','-qm','fixture'],check=True)
            commit = subprocess.check_output(['git','-C',str(repo),'rev-parse','HEAD'],text=True).strip()
            (repo/'source.txt').write_text('uncommitted\n')
            copy_worktree(repo,work,commit)
            self.assertEqual((work/'source.txt').read_text(),'committed\n')

    def test_sbom_covers_custom_runtime_lock(self):
        from sbom import complete_runtime_locks
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root/'requirements.lock').write_text('example-package==1.2.3\n')
            dump(root/'sbom.json', {'bomFormat':'CycloneDX','components':[]})
            self.assertEqual(complete_runtime_locks(root/'sbom.json',root,['requirements.lock']), 1)
            self.assertEqual(complete_runtime_locks(root/'sbom.json',root,['requirements.lock']), 0)
            self.assertEqual(json.loads((root/'sbom.json').read_text())['components'][0]['purl'], 'pkg:pypi/example-package@1.2.3')

    def test_missing_timeout_and_nonzero(self):
        with tempfile.TemporaryDirectory() as folder:
            self.assertEqual(execute(['missing-security-test-executable'], folder, folder, 'missing')['status'], 'MISSING')
            self.assertEqual(execute([sys.executable, '-c', 'import time;time.sleep(3)'], folder, folder, 'timeout', 0.1)['status'], 'TIMEOUT')
            self.assertEqual(execute([sys.executable, '-c', 'raise SystemExit(9)'], folder, folder, 'exit')['status'], 'ERROR')

    def test_malformed_and_zero_scan_reports(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'data.json'
            path.write_text('not json')
            with self.assertRaises(ValueError):
                parse('trivy', path, folder)
            dump(path, {'results':[], 'paths':{'scanned':[]}, 'errors':[]})
            findings, gaps, coverage = parse('semgrep', path, folder)
            self.assertIn({'id':'semgrep:zero-files-scanned', 'mandatory':True}, gaps)

    def test_secrets_and_absolute_paths_never_enter_normalized_report(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'data.json'
            # 测试只使用不对应任何服务的无效标记，报告仍不得泄露其值。
            dump(path, [{'RuleID':'example','File':'example.txt','StartLine':1,'Secret':'INVALID_FIXTURE_VALUE','Match':'RAW_SOURCE_SNIPPET'}])
            findings, _, _ = parse('gitleaks', path, folder)
            result = evaluate('quick', [], findings, [])
            write(Path(folder), result, findings, [], {}, {})
            content = (Path(folder) / 'gate-report.md').read_text()
            self.assertNotIn('INVALID_FIXTURE_VALUE', content)
            self.assertNotIn('RAW_SOURCE_SNIPPET', content)
            self.assertEqual(relative('/home/example/private.txt', folder), '[external]')
            self.assertEqual(json.loads((Path(folder) / 'gate-result.json').read_text())['exit_code'], result['exit_code'])

class CliTests(unittest.TestCase):
    def invoke(self, args):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        base = Path(temp.name)
        repo = base / 'repo'
        repo.mkdir()
        subprocess.run(['git', 'init', '-q', str(repo)], check=True)
        (repo / 'example.py').write_text('print(1)\n')
        subprocess.run(['git', '-C', str(repo), 'add', '.'], check=True)
        subprocess.run(['git', '-C', str(repo), '-c', 'user.name=Gate Test', '-c', 'user.email=gate@example.com',
                        'commit', '-qm', 'fixture'], check=True)
        run = subprocess.run([sys.executable, str(HERE / 'gate.py'), *args, '--repo', str(repo),
                              '--output-root', str(base / 'out')], capture_output=True, text=True)
        outputs = list((base / 'out').glob('*/gate-result.json'))
        self.assertEqual(len(outputs), 1, run.stdout + run.stderr)
        result = json.loads(outputs[0].read_text())
        self.assertEqual(run.returncode, result['exit_code'])
        self.assertTrue(outputs[0].with_name('gate-report.md').exists())
        return result

    def test_authorization_required(self):
        self.assertEqual(self.invoke(['quick'])['exit_code'], 3)

    def test_zap_not_authorized(self):
        result = self.invoke(['release', '--authorize', '--target', 'https://staging.example.com'])
        self.assertEqual(result['exit_code'], 3)

    def test_release_dry_run_no_target(self):
        result = self.invoke(['release', '--dry-run'])
        self.assertEqual(result['exit_code'], 2)
        self.assertTrue(result['dry_run'])

if __name__ == '__main__':
    unittest.main()
