"""S板USB变体逐条命令会话：保持端口开启供仪表观测，退出时明确OFF。

不提供ROM擦写，不接受其它固件，不周期发送模式命令。导入模块不打开串口。
"""
from pathlib import Path
import argparse
import datetime
import json
import time
import serial

COMMANDS = frozenset(['info', 'status', 'off', 'bias', 'sine', 'ecg60', 'ecg90'])
FW = 'ecg-source-usb-1'


def decode_reply(raw):
    if len(raw) > 512 or not raw.endswith(b'\n'):
        raise ValueError('缺少有界完整响应')
    result = json.loads(raw.decode('ascii'))
    if not isinstance(result, dict) or not isinstance(result.get('ok'), bool):
        raise ValueError('不是源板协议响应')
    if result.get('ok') and result.get('fw') != FW:
        raise ValueError('源板固件身份不符')
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port', required=True)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[2]
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    out = root / 'local-evidence/G2S-20261015' / ('app-' + stamp)
    out.mkdir(parents=True)
    verified = False
    # 与已实测的自动下载电路极性保持一致：DTR=True释放复位、RTS=False为Flash。
    # 在open之前设置，避免默认线状态引发不必要的RESET/BOOT0切换。
    port = serial.Serial(port=None, baudrate=115200, bytesize=8, parity='N', stopbits=1,
                         timeout=2, write_timeout=2, rtscts=False, dsrdtr=False)
    port.port = args.port;port.dtr=True;port.rts=False
    with (out / 'responses.jsonl').open('x', encoding='utf-8') as log:
        def request(command):
            if command not in COMMANDS:
                raise ValueError('非白名单源板命令')
            port.write((command+'\n').encode('ascii'));port.flush()
            result=decode_reply(port.readline(513))
            record={'time_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),
                    'command':command,'reply':result}
            log.write(json.dumps(record,ensure_ascii=True)+'\n');log.flush()
            print(json.dumps(record,ensure_ascii=True),flush=True)
            if not result['ok']:
                raise RuntimeError('源板命令返回失败；不自动重试或清除证据')
            return result
        try:
            port.open();time.sleep(0.6);port.reset_input_buffer()
            first=request('info')
            verified=True
            if first.get('mode')!=0 or first.get('state')!=0 or first.get('faults') or first.get('console_errors'):
                raise RuntimeError('启动非OFF或存在故障；停止')
            print('SESSION_READY: info/status/off/bias/sine/ecg60/ecg90/quit',flush=True)
            while True:
                line=input().strip()
                if line=='quit':
                    break
                if line not in COMMANDS:
                    print('LOCAL_REJECTED_UNKNOWN_COMMAND',flush=True);continue
                request(line)
        finally:
            # 已确认固件后才发送OFF；不向未知端口固件发送控制指令。
            # 保留原异常及退出证据；若OFF确认失败，不声称源输出已停止。
            if verified and port.is_open:
                try:
                    r=request('off')
                    print('EXIT_OFF_CONFIRMED' if r.get('mode')==0 and r.get('state')==0 else 'EXIT_OFF_NOT_CONFIRMED',flush=True)
                except Exception as error:
                    print('EXIT_OFF_FAILED:'+type(error).__name__,flush=True)
            if port.is_open:
                port.close()


if __name__=='__main__':
    main()
