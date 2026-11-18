import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

NODE_B = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(NODE_B / 'tools'))
from build_b4_arm import DIAG_REASON_ANCHOR, inject_diag_reason, inject_r6


class TestDiagReason(unittest.TestCase):
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
        with tempfile.TemporaryDirectory() as folder:
            code = Path(folder) / 'format.c'
            program = Path(folder) / 'format.exe'
            code.write_text(source, encoding='ascii')
            header = NODE_B / 'firmware/biov2/实验固件/HARDWARE/bio_v2.h'
            (Path(folder) / header.name).write_bytes(header.read_bytes())
            subprocess.run(['gcc', '-std=c99', '-Wall', '-Wextra', '-Werror',
                            str(code), '-o', str(program)], check=True)
            subprocess.run([str(program)], check=True)


if __name__ == '__main__':
    unittest.main()
