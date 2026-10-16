"""普通Host回归：实际G1驱动/MMIO模型与新增串口解析器；不访问串口。"""
from pathlib import Path
import ctypes as C
import datetime
import hashlib
import json
import subprocess

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent


def main():
    # 每次运行独立留证，公开摘要另加于g2s目录，不覆盖G1原测试回执。
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    out = ROOT / 'build' / ('usb-host-' + stamp)
    out.mkdir(parents=True)
    inputs = [ROOT / name for name in [
        'src/source_driver.c', 'src/source_waveform.c', 'src/waveform_tables.c',
        'tests/mmio_mock.c', 'g2s-usb/console.c']]
    receipt = {'scope': 'ORDINARY_HOST_NO_HARDWARE', 'checks': [],
               'input_sha256': {p.relative_to(ROOT).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest() for p in inputs}}
    try:
        cmd = ['C:/mingw64/bin/gcc.exe', '-std=c99', '-O2', '-Wall', '-Wextra', '-Werror',
               '-shared', '-DSRC_HOST_TEST', '-I' + str(ROOT / 'src'),
               '-I' + str(ROOT / 'tests'), '-I' + str(HERE)]
        cp = subprocess.run(cmd + [str(p) for p in inputs] + ['-o', str(out / 'console.dll')],
                            capture_output=True, timeout=60)
        (out / 'compile.stdout.log').write_bytes(cp.stdout)
        (out / 'compile.stderr.log').write_bytes(cp.stderr)
        receipt['compile_exit'] = cp.returncode
        if cp.returncode:
            raise RuntimeError('Host编译失败，见本地原日志')
        lib = C.CDLL(str(out / 'console.dll'))
        lib.Console_Feed.argtypes = [C.c_uint8]
        lib.Console_Feed.restype = C.c_char_p
        lib.Console_Status.restype = C.c_char_p
        lib.Src_Fault.argtypes = [C.c_uint32]
        lib.SrcMock_Trigger.restype = C.c_uint32

        def check(name, good):
            receipt['checks'].append({'name': name, 'pass': bool(good)})
            if not good:
                raise AssertionError(name)

        def reset():
            lib.SrcMock_Reset(); lib.Src_Init(); lib.Console_Init()

        def feed(raw):
            replies = []
            for byte in raw:
                value = lib.Console_Feed(byte)
                if value is not None:
                    replies.append(json.loads(value))
            return replies

        def status():
            return json.loads(lib.Console_Status())

        reset()
        check('boot_OFF_no_unsolicited_output', status()['mode'] == status()['state'] == 0)
        for command, mode in [('bias', 1), ('sine', 2), ('ecg60', 3), ('ecg90', 4), ('off', 0)]:
            r = feed(command.encode() + b'\r\n')
            check('exact_mode_' + command, len(r) == 1 and r[0]['ok'] and r[0]['mode'] == mode)
        check('status_read_only', feed(b'status\n')[0]['mode'] == 0)
        check('info_identifies_USB_variant', feed(b'info\n')[0]['fw'] == 'ecg-source-usb-1')
        check('partial_command_no_action', not feed(b'ecg') and status()['mode'] == 0)
        check('fragmented_command_complete', feed(b'60\n')[0]['mode'] == 3)
        lib.SrcMock_Trigger()
        check('same_mode_does_not_restart', feed(b'ecg60\n')[0]['mode'] == 3)
        for bad in [b'ECG60\n', b'ecg60 extra\n', b'\n', b' mode=4\n', b'0x20000000\n']:
            check('unknown_rejected_' + bad.hex(), not feed(bad)[0]['ok'] and status()['mode'] == 3)
        check('multiple_explicit_lines', [v['mode'] for v in feed(b'bias\noff\n')] == [1, 0])
        feed(b'ecg90\n')
        check('overflow_discards_until_LF', not feed(b'x' * 100 + b'ecg60') and status()['mode'] == 0)
        check('overflow_reports_once', not feed(b'\n')[0]['ok'] and status()['console_errors'] == 1)
        check('after_resync_explicit_restart', feed(b'ecg60\n')[0]['mode'] == 3)
        for invalid in [0, 1, 127, 255]:
            feed(b'ecg90\n')
            check('binary_rejected_OFF_' + str(invalid), not feed(b'ecg' + bytes([invalid])) and status()['mode'] == 0)
            check('binary_suffix_not_command_' + str(invalid), not feed(b'60\n')[0]['ok'] and status()['mode'] == 0)
        feed(b'ecg60\n'); lib.Console_TransportError()
        check('transport_error_OFF', status()['mode'] == 0 and status()['console_errors'] == 6)
        check('transport_discards_partial', not feed(b'ecg90\n')[0]['ok'] and status()['mode'] == 0)
        feed(b'ecg90\n')
        for _ in range(4000):
            lib.SrcMock_Trigger()
        s = status()
        check('real_shared_DMA_statistics', s['completed_tables'] == 2 and s['completed_dma_samples'] == 4000)
        lib.Src_Fault(8)
        check('G1_fault_cannot_be_restarted_by_console', not feed(b'ecg60\n')[0]['ok'] and status()['faults'] & 8)
        # 原G1故障锁存后OFF确实关输出，但返回失败；不能强迫新增入口把它改成成功。
        off_reply = feed(b'off\n')[0]
        check('OFF_keeps_G1_fault_and_history', not off_reply['ok'] and status()['mode'] == 0
              and status()['faults'] & 8 and status()['completed_tables'] == 2)
        reset()
        # 用Host寄存器模型中的最大无符号值检查格式化容量，不把这些合成值当真机证据。
        diag_words = (C.c_uint32 * 18).in_dll(lib, 'g_source_diag')
        for i in range(18):
            diag_words[i] = 0xFFFFFFFF
        g_console_errors = C.c_uint32.in_dll(lib, 'g_console_errors')
        g_console_errors.value = 0xFFFFFFFF
        check('max_counters_fit_reply', len(lib.Console_Status()) < 512
              and status()['completed_dma_samples'] == 0xFFFFFFFF)
        receipt['status'] = 'PASS'
    except BaseException as error:
        receipt.update(status='FAIL', error=type(error).__name__ + ': ' + str(error))
        raise
    finally:
        receipt['passed'] = sum(v['pass'] for v in receipt['checks'])
        receipt['total'] = len(receipt['checks'])
        raw = json.dumps(receipt, ensure_ascii=False, indent=2) + '\n'
        (out / 'receipt.json').write_text(raw, encoding='utf-8')
        art = ROOT.parent / 'artifacts/ecg-source/g2s'
        art.mkdir(exist_ok=True)
        # 以时间戳保留历次结果，失败不覆盖，后续报告引用准确文件名。
        (art / ('usb-console-host-' + stamp + '.json')).write_text(raw, encoding='utf-8')
    print(json.dumps({'status': receipt['status'], 'passed': receipt['passed'], 'total': receipt['total']}))


if __name__ == '__main__':
    main()
