"""新构建器的普通冻结/白名单检查，不编译或运行任何设备及网络代码。"""
import importlib.util
from pathlib import Path
import unittest
import sys

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
from build_diagnostic import ALLOWED_PATCH, PINS, ROOT, patch_paths, safe_target
from prepare_overlays import modified, once

class BuildContractTests(unittest.TestCase):
    def test_exact_fixed_commit_pair(self):
        self.assertEqual(PINS, {'P4': '8dee339491cfd4edc468bb9451511d421f26db5e',
                               'P5': 'e598fc63719acdf49a99c6da46c656dc8c607782'})

    def test_patch_file_whitelist_and_no_third_party_or_build_changes(self):
        for variant in PINS:
            text = (HERE / 'overlays' / (variant + '.patch')).read_text(encoding='utf-8')
            self.assertEqual(set(patch_paths(text)), ALLOWED_PATCH)
            self.assertNotIn('+++ b/gateway/mqtt/build.py', text)
            self.assertNotIn('+++ b/gateway/third_party', text)

    def test_overlays_start_from_exact_git_sources(self):
        for variant in PINS:
            before, after = modified(variant)
            self.assertEqual(set(before), ALLOWED_PATCH)
            self.assertTrue(all(before[path] != after[path] for path in before))
            self.assertIn('static int original_gateway_mqtt_open', after['gateway/mqtt/src/gateway_transport.c'])
            self.assertIn('return result;', after['gateway/mqtt/src/gateway_transport.c'])

    def test_reject_missing_duplicate_or_escaped_patch_section(self):
        text = (HERE / 'overlays/P4.patch').read_text(encoding='utf-8')
        for mutated in [text.replace('+++ b/gateway/mqtt/src/main.c', '+++ b/../outside.c'),
                        text.replace('diff --git a/gateway/mqtt/src/main.c b/gateway/mqtt/src/main.c', 'diff --git a/outside.c b/gateway/mqtt/src/main.c'),
                        text + '\nGIT binary patch\n', text + '\ndiff --git a/x b/x\n']:
            with self.assertRaises(ValueError): patch_paths(mutated)

    def test_missing_exact_context_is_not_fuzzed(self):
        with self.assertRaises(ValueError): once('changed source', 'original source', 'new source')
        with self.assertRaises(ValueError): once('twice twice', 'twice', 'once')

    def test_isolated_path_escape_is_rejected(self):
        base = ROOT / 'gateway/mqtt/build/h16-diagnostic'
        with self.assertRaises(ValueError): safe_target(base, '../outside.json')

    def test_all_original_frontend_returns_remain_in_inner_implementations(self):
        for variant in PINS:
            before, after = modified(variant)
            transport = after['gateway/mqtt/src/gateway_transport.c']
            for name in ('open', 'publish', 'yield'):
                self.assertIn(f'original_gateway_mqtt_{name}', transport)
            # 不把语义原函数的return改成日志返回；外层统一处理，迟到/丢失ACK仍走原实现。
            self.assertGreaterEqual(transport.count('return 0;'), before['gateway/mqtt/src/gateway_transport.c'].count('return 0;'))

    def test_original_delays_and_dispatch_budget_remain(self):
        for variant in PINS:
            _, after = modified(variant)
            main = after['gateway/mqtt/src/main.c']
            for original in ('unsigned budget = 8;', 'delay_ms(30000);', 'delay_ms(2000);', 'mp_router_ack(&router, &f, ok);'):
                self.assertIn(original, main)

    def test_no_automatic_stack_sentinel_or_probe_business_io(self):
        text = (HERE / 'probe_events.c').read_text(encoding='utf-8')
        for call in ('malloc(', 'calloc(', 'printf(', 'at_command(', 'gateway_mqtt_', 'console(', '__assert_func('):
            self.assertNotIn(call, text)
        self.assertIn('PROBE_STACK_BLOCKED', text)
        self.assertNotIn('_estack', text)

if __name__ == '__main__':
    unittest.main()
