"""S板单连接BIAS观测：只发一次BIAS，定时读取状态，退出请求OFF。

只记录数字状态采样，不能证明两次查询之间没有复位，也不代替物理电压。
不下载、不重连、不自动重新启用输出。导入本模块不访问串口。
"""
import argparse
import datetime
import json
from pathlib import Path
import time

import serial
from app_session import FW, decode_reply


def require_state(reply, mode):
    # 缺失字段也视为失败，不能把未返回的故障字段当作零。
    expected = {'ok': True, 'fw': FW, 'mode': mode, 'state': mode,
                'faults': 0, 'console_errors': 0}
    if any(type(reply.get(key)) is not type(value) or reply[key] != value
           for key, value in expected.items()):
        raise ValueError('模式、身份或故障字段不符合本窗口要求')


def observe(request, emit, seconds, monotonic=time.monotonic, sleep=time.sleep):
    if type(seconds) is not int or not 1 <= seconds <= 300:
        raise ValueError('窗口必须为1至300秒')
    verified = False
    result = {'observation': 'FAIL', 'off': 'NOT_CONFIRMED', 'samples': 0}
    try:
        first = request('info')
        # 只有成功确认固件身份后，finally才允许向该端口请求OFF。
        verified = first.get('ok') is True and first.get('fw') == FW
        require_state(first, 0)
        require_state(request('bias'), 1)
        started = monotonic()
        emit({'event': 'BIAS_WINDOW_STARTED', 'duration_s': seconds})
        while monotonic() - started < seconds:
            sleep(max(0, min(2, seconds - (monotonic() - started))))
            require_state(request('status'), 1)
            result['samples'] += 1
        result['observation'] = 'DIGITAL_SAMPLED_WINDOW_COMPLETE'
    except Exception as error:
        result['error_type'] = type(error).__name__
    finally:
        # 无论正常结束还是观测失败都撤销输出；通信已断则只记失败，不重连。
        if verified:
            try:
                reply = request('off')
                if reply.get('ok') is True and reply.get('fw') == FW and \
                        type(reply.get('mode')) is int and type(reply.get('state')) is int and \
                        reply.get('mode') == 0 and reply.get('state') == 0:
                    result['off'] = 'CONFIRMED'
            except Exception as error:
                result['off_error_type'] = type(error).__name__
        emit({'event': 'WINDOW_END', **result})
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port', required=True)
    parser.add_argument('--seconds', type=int, default=300, choices=range(1, 301),
                        metavar='1..300')
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[2]
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    out = root / 'local-evidence/G2S-20261015' / ('bias-window-' + stamp)
    out.mkdir(parents=True)
    # 沿用已核对的S板控制线极性，在open前设置，不做自动BOOT/RESET切换。
    port = serial.Serial(port=None, baudrate=115200, timeout=2, write_timeout=2,
                         rtscts=False, dsrdtr=False)
    port.port = args.port
    port.dtr = True
    port.rts = False
    with (out / 'responses.jsonl').open('x', encoding='utf-8') as log:
        def emit(record):
            record = {'time_utc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
                      'monotonic_s': time.monotonic(), **record}
            line = json.dumps(record, ensure_ascii=True)
            log.write(line + '\n')
            log.flush()
            print(line, flush=True)

        def request(command):
            if command not in ('info', 'bias', 'status', 'off'):
                raise ValueError('非本窗口命令')
            emit({'event': 'REQUEST', 'command': command})
            port.write((command + '\n').encode('ascii'))
            port.flush()
            reply = decode_reply(port.readline(513))
            emit({'event': 'REPLY', 'command': command, 'reply': reply})
            return reply

        try:
            port.open()
            time.sleep(0.6)
            port.reset_input_buffer()
            result = observe(request, emit, args.seconds)
        finally:
            # close不能声称板上已OFF，是否确认只能以窗口结果为准。
            port.close()
        (out / 'result.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
    return 0 if result['observation'] == 'DIGITAL_SAMPLED_WINDOW_COMPLETE' and \
        result['off'] == 'CONFIRMED' else 1


if __name__ == '__main__':
    raise SystemExit(main())
