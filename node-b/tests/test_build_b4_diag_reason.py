import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

NODE_B = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(NODE_B / 'tools'))
from build_b4_arm import (DIAG_REASON_ANCHOR, HOME_CAPTURE_WRITE, HOME_QUALITY_WRITE, VALUE_TICK,
                          inject_diag_reason, inject_home_diag_reason, inject_r6)


class TestDiagReason(unittest.TestCase):
    def run_formatter(self, source):
        with tempfile.TemporaryDirectory() as folder:
            code = Path(folder) / 'format.c'
            program = Path(folder) / 'format.exe'
            code.write_text(source, encoding='ascii')
            header = NODE_B / 'firmware/biov2/实验固件/HARDWARE/bio_v2.h'
            (Path(folder) / header.name).write_bytes(header.read_bytes())
            subprocess.run(['gcc', '-std=c99', '-Wall', '-Wextra', '-Werror',
                            str(code), '-o', str(program)], check=True)
            subprocess.run([str(program)], check=True)

    def test_single_anchor_in_r6_copy(self):
        page = NODE_B / 'firmware/biov2/实验固件/HARDWARE/hr_page.c'
        baseline = inject_r6(page.read_text(encoding='utf-8'))
        before, after = baseline.split(DIAG_REASON_ANCHOR)
        updated = inject_diag_reason(baseline)
        self.assertTrue(updated.startswith(before))
        self.assertTrue(updated.endswith(after))
        self.assertNotIn(DIAG_REASON_ANCHOR, updated)
        with self.assertRaises(RuntimeError):
            inject_diag_reason(baseline + DIAG_REASON_ANCHOR)
        with self.assertRaises(RuntimeError):
            inject_diag_reason(before + after)

    def test_format_injected_c(self):
        fragment = inject_diag_reason(DIAG_REASON_ANCHOR)
        source = '''
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include "bio_v2.h"
#define HP_SCR_PROBE 5
#define HP_TXT5_ADVICE 12
BioV2Diag g_bio_v2;
static char actual[40];
static void TxtGB(int screen, int control, const uint8_t *text) {
    if (screen == 5 && control == 12) strcpy(actual, (const char *)text);
}
static void render(void) {
    char buf[40];
    const uint8_t *adv = NULL;
''' + fragment + '''
}
int main(void) {
    g_bio_v2.hr_reason = 66;
    g_bio_v2.rpm_reason = 6;
    g_bio_v2.ecg_mains_fraction = 0.968f;
    g_bio_v2.resp_mains_fraction = 0.123f;
    g_bio_v2.ecg_rms_codes = 1234.9f;
    render();
    if (strcmp(actual, "H66 R6 M97/12 E1234")) return 1;
    g_bio_v2.hr_reason = 255;
    g_bio_v2.rpm_reason = 255;
    g_bio_v2.ecg_mains_fraction = 1.2f;
    g_bio_v2.resp_mains_fraction = 0.999f;
    g_bio_v2.ecg_rms_codes = 1000000.0f;
    render();
    return strlen(actual) > 26 || strcmp(actual, "H255 R255 M100/100 E999999");
}
'''
        self.run_formatter(source)

    def test_home_injection_keeps_probe_outputs(self):
        page = NODE_B / 'firmware/biov2/实验固件/HARDWARE/hr_page.c'
        baseline = inject_diag_reason(inject_r6(page.read_text(encoding='utf-8')))
        updated = inject_home_diag_reason(baseline)
        self.assertNotIn(HOME_QUALITY_WRITE, updated)
        self.assertIn('SetTextValue(HP_SCR_PROBE, HP_TXT5_QUAL, (uchar *)buf);', updated)
        self.assertIn('"H%lu R%lu M%u/%u E%lu"', updated)
        self.assertEqual(updated.count('"H%lu M%u"'), 1)
        self.assertEqual(updated.count('"H%lu R%lu M%u"'), 1)
        self.assertEqual(updated.count('TxtGB(HP_SCR_HOME, HP_TXT_CAP, STR_CAP);'), 2)
        with self.assertRaises(RuntimeError):
            inject_home_diag_reason(baseline + VALUE_TICK)
        with self.assertRaises(RuntimeError):
            inject_home_diag_reason(baseline + HOME_CAPTURE_WRITE)

    def test_home_format_and_page_gate(self):
        fixture = HOME_CAPTURE_WRITE + HOME_QUALITY_WRITE + VALUE_TICK
        fragment = inject_home_diag_reason(fixture).split(VALUE_TICK)[1]
        self.run_formatter('''
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include "bio_v2.h"
#define HP_SCR_HOME 0
#define HP_TXT_QUAL 17
typedef uint8_t uchar;
BioV2Diag g_bio_v2;
static uint8_t s_cur;
static unsigned writes;
static char actual[10];
static void SetTextValue(int screen, int control, uchar *text) {
    if (screen == HP_SCR_HOME && control == HP_TXT_QUAL) {
        ++writes;
        snprintf(actual, sizeof(actual), "%s", (const char *)text);
    }
}
static void render(void) {''' + fragment + '''
}
int main(void) {
    s_cur = 5;
    render();
    if (writes) return 1;
    s_cur = HP_SCR_HOME;
    g_bio_v2.hr_reason = 66;
    g_bio_v2.ecg_mains_fraction = 0.968f;
    render();
    if (writes != 1 || strcmp(actual, "H66 M97")) return 2;
    g_bio_v2.hr_reason = 255;
    g_bio_v2.ecg_mains_fraction = 1.2f;
    render();
    if (writes != 2 || strcmp(actual, "H255 M100")) return 3;
    g_bio_v2.hr_reason = 0;
    g_bio_v2.ecg_mains_fraction = -0.1f;
    render();
    return writes != 3 || strcmp(actual, "H0 M0");
}
''')

    def test_capture_format_and_active_home_gate(self):
        page = NODE_B / 'firmware/biov2/实验固件/HARDWARE/hr_page.c'
        refresh = page.read_text(encoding='utf-8').split('static void ValueRefresh', 1)[1]
        gate_at = refresh.index('    if ((s_cur == HP_SCR_HOME) && (s_run != 0))')
        gate = refresh[gate_at:refresh.index('    {\n', gate_at) + len('    {\n')]
        self.assertIn(HOME_CAPTURE_WRITE, refresh[gate_at:].split('    }\n    TxtGB', 1)[0] + '    }\n')
        fixture = HOME_QUALITY_WRITE + gate + HOME_CAPTURE_WRITE + VALUE_TICK
        fragment = inject_home_diag_reason(fixture).split(VALUE_TICK)[0]
        self.run_formatter('''
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include "bio_v2.h"
#define HP_SCR_HOME 0
#define HP_TXT_CAP 20
BioV2Diag g_bio_v2;
static uint8_t s_cur, s_run;
static unsigned writes;
static char actual[15];
static void TxtGB(int screen, int control, const uint8_t *text) {
    if (screen == HP_SCR_HOME && control == HP_TXT_CAP) {
        ++writes;
        snprintf(actual, sizeof(actual), "%s", (const char *)text);
    }
}
static void render(void) {
''' + fragment + '''
}
int main(void) {
    s_cur = 5;
    s_run = 1;
    render();
    s_cur = HP_SCR_HOME;
    s_run = 0;
    render();
    if (writes) return 1;
    s_run = 1;
    g_bio_v2.hr_reason = 66;
    g_bio_v2.rpm_reason = 6;
    g_bio_v2.ecg_mains_fraction = 0.968f;
    render();
    if (writes != 1 || strcmp(actual, "H66 R6 M97")) return 2;
    g_bio_v2.hr_reason = 255;
    g_bio_v2.rpm_reason = 255;
    g_bio_v2.ecg_mains_fraction = 1.2f;
    render();
    return writes != 2 || strlen(actual) != 14 || strcmp(actual, "H255 R255 M100");
}
''')


if __name__ == '__main__':
    unittest.main()
