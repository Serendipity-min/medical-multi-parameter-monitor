"""P1-A定向回归运行器；不允许真实SDK、串口、网络或子进程。"""
import argparse
from contextlib import ExitStack
import ctypes
import json
from pathlib import Path
import platform
import re
import sys
import unittest
from unittest.mock import patch

import serial

ROOT = Path(__file__).resolve().parents[2]
TESTS = ROOT / 'node-b/tests'
MODULES = (
    'test_b5_channel_profiles', 'test_b5_channel_review', 'test_b5_g3_joint',
    'test_readback_b', 'test_c_b4_readonly', 'test_c_b4_closeout_readonly',
    'test_b5_c_rom_readonly', 'test_codex_r6_takeover',
)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--receipt', type=Path, required=True)
    args = parser.parse_args()
    blocked = []

    def deny(kind):
        blocked.append(kind)
        raise RuntimeError('P1A_OFFLINE_FORBIDDEN_' + kind)

    def audit(event, values):
        if event in ('ctypes.dlopen', 'subprocess.Popen', 'os.system',
                     'socket.connect', 'socket.connect_ex', 'socket.bind',
                     'socket.sendto', 'socket.getaddrinfo'):
            deny(event)
        if event == 'open' and isinstance(values[0], (str, bytes)):
            name = str(values[0]).replace('\\', '/').upper()
            if re.search(r'(^|/)(COM[1-9][0-9]*)(:|$)', name) or name.startswith('//./'):
                deny('DEVICE_OPEN')
            mode, flags = values[1:3]
            writing = mode and any(c in mode for c in 'wax+') or flags & 3
            if writing and 'MEDICAL-MONITOR-NODE-B-PRECAN-PRIVATE' in name:
                deny('PRIVATE_EVIDENCE_WRITE')

    # 预导入pyserial仅取得类型；此后任何串口构造和ctypes加载均被阻断。
    sys.addaudithook(audit)
    self_checks = []
    for event in ('ctypes.dlopen', 'subprocess.Popen', 'socket.connect'):
        try:
            sys.audit(event, 'SYNTHETIC_DENY_CHECK')
        except RuntimeError:
            self_checks.append(event)
    sys.path[:0] = [str(TESTS), str(ROOT / 'node-b/tools'), str(ROOT)]
    with ExitStack() as stack:
        stack.enter_context(patch.object(platform, 'system', return_value='Windows' if sys.platform=='win32' else sys.platform))
        stack.enter_context(patch.object(serial, 'Serial', side_effect=lambda *a, **k: deny('SERIAL_CONSTRUCTOR')))
        stack.enter_context(patch.object(ctypes, 'CDLL', side_effect=lambda *a, **k: deny('DLL_CONSTRUCTOR')))
        suite = unittest.TestSuite(unittest.defaultTestLoader.loadTestsFromName(name) for name in MODULES)
        result = unittest.TextTestRunner(verbosity=2).run(suite)
    receipt = {
        'status': 'PASS_MOCK' if result.wasSuccessful() else 'FAIL',
        'exit_code': 0 if result.wasSuccessful() else 1,
        'tests_run': result.testsRun, 'failures': len(result.failures),
        'errors': len(result.errors), 'skipped': len(result.skipped),
        'modules': list(MODULES), 'guard_self_checks': self_checks,
        'blocked_events': blocked, 'real_hardware_sessions': 0,
        'field_authorization': 'NOT_GRANTED',
        'guard_limit': 'Python audit hook and constructor guards; not an adversarial OS sandbox',
    }
    with args.receipt.open('x', encoding='utf-8', newline='\n') as stream:
        json.dump(receipt, stream, indent=2, ensure_ascii=False)
        stream.write('\n')
    print(json.dumps(receipt, ensure_ascii=False))
    return receipt['exit_code']


if __name__ == '__main__':
    raise SystemExit(main())
