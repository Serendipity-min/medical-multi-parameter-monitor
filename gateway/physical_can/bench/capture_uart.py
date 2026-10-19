"""H2现场串口观测：明确命令文件驱动，不重刷、不联网、不自动故障重试。"""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import time

import serial


def public_line(text):
    """公开证据保留协议时序和质量；未知来源的生理样值只留受限本地原始日志。"""
    text = re.sub(r'(RX id=(?:181|381)\b[^\n]*\bdata=)[0-9a-fA-F]+',
                  r'\1REDACTED_SAMPLE_PAYLOAD', text)
    text = re.sub(r'(\bvalues=)[^ \r\n]+', r'\1REDACTED_SAMPLES', text)
    return re.sub(r'(\bwave=)[^/ \r\n]+/', r'\1REDACTED_SAMPLE/', text)


def public_status(status):
    """复制后脱敏，不改变进程内解析状态，防止后续时序分析使用脱敏占位符。"""
    result = json.loads(json.dumps(status))
    for ident in ('181', '381'):
        if ident in result.get('rx', {}):
            result['rx'][ident]['data'] = 'REDACTED_SAMPLE_PAYLOAD'
    if 'mirror' in result:
        result['mirror']['values'] = 'REDACTED_SAMPLES'
        wave = result['mirror'].get('wave', '')
        if '/' in wave:
            result['mirror']['wave'] = 'REDACTED_SAMPLE/' + wave.split('/')[-1]
    result['sample_payloads'] = 'REDACTED; raw UART retained in ACL-restricted local directory'
    return result


class ReportTracker:
    """设备明确声明的报告行数与主机收到的行数比对；不把边界半份报告当作丢行。"""
    def __init__(self):
        self.current = None
        self.previous = None
        self.lines = set()
        self.stats = {'protocol_available': False, 'complete_reports': 0,
                      'missing_reports': 0, 'missing_lines': 0, 'incomplete_reports': 0,
                      'duplicate_lines': 0, 'invalid_tags': 0, 'device_boot_markers': 0}

    def feed(self, text):
        fields = dict(re.findall(r'(\w+)=([^ ]+)', text))
        if text.startswith('CAN_ONLY_BENCH '):
            self.stats['device_boot_markers'] += 1
            self.current = self.previous = None
            self.lines = set()
        elif text.startswith('DIAG_BEGIN '):
            self.stats['protocol_available'] = True
            seq, expected = int(fields['seq']), int(fields['expected'])
            if not 1 <= expected <= 64:
                self.stats['invalid_tags'] += 1
                return
            if self.current:
                self.stats['incomplete_reports'] += 1
                self.stats['missing_lines'] += len(set(range(1, self.current[1]+1))-self.lines)
            if self.previous is not None:
                if seq > self.previous+1:
                    self.stats['missing_reports'] += seq-self.previous-1
                elif seq <= self.previous:
                    self.stats['invalid_tags'] += 1
            self.current = (seq, expected)
            self.previous = seq
            self.lines = set()
        elif text.startswith('DIAG_END ') and self.current:
            seq, expected = self.current
            if int(fields['seq']) != seq or int(fields['lines']) != expected:
                self.stats['invalid_tags'] += 1
            missing = len(set(range(1, expected+1))-self.lines)
            self.stats['missing_lines'] += missing
            if missing:
                self.stats['incomplete_reports'] += 1
            else:
                self.stats['complete_reports'] += 1
            self.current = None
        elif self.current and 'rs' in fields and 'rl' in fields:
            index = int(fields['rl'])
            if int(fields['rs']) != self.current[0] or not 1 <= index <= self.current[1]:
                self.stats['invalid_tags'] += 1
            elif index in self.lines:
                self.stats['duplicate_lines'] += 1
            else:
                self.lines.add(index)

    def snapshot(self):
        return dict(self.stats, trailing_partial_report=self.current is not None,
                    interpretation='HOST_OBSERVED_DIAGNOSTIC_GAPS; UART and hardware counters are separate')


def command_allowed(command, latest, age):
    """只在新鲜的无故障实板诊断后发命令；测试授时还需真实NMT TXOK及A在线。"""
    if age > 3 or not latest or latest.get('fault') != '0' or latest.get('BOFF') != '0':
        return False
    if command == 'S':
        return latest.get('armed') == '0'
    if command == 'T':
        return (latest.get('armed') == '1' and latest.get('A') == '1'
                and latest.get('paused', '0') == '0' and int(latest.get('NMT_TXOK', '0')) > 0)
    if command == 'P':
        return latest.get('armed') == '1' and latest.get('paused', '0') == '0'
    if command == 'G':
        return latest.get('armed') == '1' and latest.get('paused') == '1'
    if command == 'D':
        return latest.get('armed') == '1' and latest.get('paused', '0') == '0'
    return False


def publish_status(path, status):
    """Windows读者可能短暂禁止替换文件；跳过本次快照，不能因此中断原始串口记录。"""
    temp = path.with_suffix('.tmp')
    temp.write_text(json.dumps(public_status(status), indent=2) + '\n', encoding='utf-8')
    try:
        temp.replace(path)
    except PermissionError:
        status['status_publish_busy'] = status.get('status_publish_busy', 0) + 1
        return False
    return True


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--await-boot', action='store_true')
    parser.add_argument('--h2r', action='store_true')
    parser.add_argument('--seconds', type=int, default=600)
    args = parser.parse_args()
    if not 1 <= args.seconds <= 900:
        parser.error('seconds must be in 1..900')
    root = Path(__file__).resolve().parents[3]
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    evidence = root / ('gateway/physical_can/evidence/h2r' if args.h2r else 'gateway/physical_can/evidence/h2')
    build = root / ('gateway/physical_can/build/h2r' if args.h2r else 'gateway/physical_can/build/bench')
    control = build / 'uart-control.txt'
    status_path = build / 'uart-status.json'
    # 任何不能识别的UART输出只进受限本地目录，避免其他固件意外输出进入版本库。
    private = Path('E:/medical-monitor-node-a-handoff/h2-private')
    if not private.is_dir():
        raise RuntimeError('PRIVATE_DIRECTORY_REQUIRED')
    control.write_text('', encoding='ascii')
    status = {'mode': 'REAL_HARDWARE_UART_CAPTURE', 'stamp': stamp, 'state': 'OPENING',
              'exit_code': None, 'await_manual_boot': args.await_boot, 'commands': [],
              'latest': {}, 'rx': {}, 'elapsed_s': 0, 'recognized_lines': 0,
              'log': f'c-continuous-{stamp}.log'}
    started = time.monotonic()
    last_bench = float('-inf')
    last_status = 0
    reset_seen = not args.await_boot
    consumed = 0
    pending = bytearray()
    tracker = ReportTracker()
    allowed = ('CAN_ONLY_BENCH ', 'BENCH ', 'RX id=', 'MIRROR ', 'MODEL ',
               'CAN_INIT ', 'BENCH_TEST_TIME_UNTRUSTED ', 'H2R_IRQ_', 'RXQ ', 'TIMING ',
               'DIAG_BEGIN ', 'DIAG_END ', 'DIAG_RATE_', 'RX_ONLY_PAUSED ', 'CAN_EVENT ')
    uart = serial.Serial(port=None, baudrate=115200, timeout=0.1, write_timeout=1)
    # 沿用现场可读取日志的端口电平；它不证明DTR/RTS能控制板卡复位。
    # 本工具不提供自动复位，重新启动应由现场明确操作并以新启动标记核实。
    uart.dtr = True
    uart.rts = False
    uart.port = 'COM15'
    try:
        with (private / f'c-continuous-{stamp}.raw.log').open('wb') as raw, \
                (evidence / status['log']).open('w', encoding='utf-8', newline='\n') as log:
            uart.open()
            status['state'] = 'CAPTURING'
            while time.monotonic() - started < args.seconds:
                now = time.monotonic()
                chunk = uart.read(4096)
                raw.write(chunk)
                raw.flush()
                pending.extend(chunk)
                # 串口行缓冲有界；损坏/非预期输出不拖垮本地观测进程。
                if len(pending) > 16384:
                    pending.clear()
                    status['state'] = 'UART_LINE_OVERFLOW_STOP'
                    break
                while b'\n' in pending:
                    line, _, pending = pending.partition(b'\n')
                    text = line.decode('ascii', errors='replace').rstrip('\r')
                    if not text.startswith(allowed):
                        continue
                    tracker.feed(text)
                    log.write(public_line(text) + '\n')
                    log.flush()
                    status['recognized_lines'] += 1
                    fields = dict(re.findall(r'(\w+)=([^ ]+)', text))
                    # USB/驱动可能保留复位前尾部行；要求见到新启动标记后才应用故障/命令门禁。
                    if text.startswith('CAN_ONLY_BENCH '):
                        reset_seen = True
                    if not reset_seen:
                        status['pre_reset_tail_lines'] = status.get('pre_reset_tail_lines', 0) + 1
                        continue
                    if text.startswith('BENCH '):
                        status['latest'] = fields
                        last_bench = now
                        if fields.get('fault') != '0' or fields.get('BOFF') != '0' or fields.get('B') != '0':
                            status['state'] = 'HARDWARE_FAULT_STOP'
                    elif text.startswith('RX id='):
                        status['rx'][fields['id']] = fields
                    elif text.startswith('MODEL '):
                        status['model'] = fields
                    elif text.startswith('MIRROR '):
                        status['mirror'] = fields
                    elif text.startswith('RXQ '):
                        status['rx_queue'] = fields
                    elif text.startswith('TIMING '):
                        status['timing'] = fields
                    elif text.startswith('CAN_EVENT '):
                        status.setdefault('can_events', []).append(fields)
                if status['state'] != 'CAPTURING':
                    break
                if not reset_seen and now - started > (180 if args.await_boot else 5):
                    status['state'] = 'RESET_NOT_OBSERVED_STOP'
                    break
                requests = control.read_text(encoding='ascii').splitlines()
                for command in requests[consumed:]:
                    consumed += 1
                    if command == 'STOP':
                        status['state'] = 'OPERATOR_STOP'
                        break
                    if not command_allowed(command, status['latest'], now - last_bench):
                        status['state'] = 'COMMAND_GATE_STOP'
                        status['rejected_command'] = command
                        break
                    if uart.write(command.encode('ascii')) != 1:
                        raise RuntimeError('SHORT_COMMAND_WRITE')
                    uart.flush()
                    status['commands'].append({'command': command, 'elapsed_s': round(now - started, 3),
                                               'device_ms_before': status['latest'].get('ms')})
                if status['state'] != 'CAPTURING':
                    break
                if now - last_status >= 1:
                    status['elapsed_s'] = round(now - started, 3)
                    status['host_log'] = tracker.snapshot()
                    publish_status(status_path, status)
                    last_status = now
            else:
                status['state'] = 'DURATION_COMPLETED'
            status['exit_code'] = 0 if status['state'] in ('OPERATOR_STOP', 'DURATION_COMPLETED') else 1
    except Exception as exc:
        status['state'] = 'HOST_EXCEPTION_STOP'
        status['exception_type'] = type(exc).__name__
        status['exit_code'] = 1
    finally:
        uart.close()
        status['elapsed_s'] = round(time.monotonic() - started, 3)
        status['host_log'] = tracker.snapshot()
        safe = public_status(status)
        publish_status(status_path, status)
        (evidence / f'c-continuous-{stamp}.json').write_text(json.dumps(safe, indent=2) + '\n', encoding='utf-8')
        print(json.dumps(safe))
    return status['exit_code']


if __name__ == '__main__':
    raise SystemExit(main())
