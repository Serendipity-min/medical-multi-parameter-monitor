"""捕获 Mosquitto error/warning/notice，仅把固定错误类别和数字码落盘。"""
import os
from pathlib import Path
import re
import signal
import subprocess
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'backend'))
from app.diagnostics import EventLog


def classify(line):
    # 原始文本只存在于有界管道读取缓冲，不输出、不先落原始日志再脱敏。
    text = line.lower()
    codes = re.findall(r'error:([0-9a-f]{8}):', text)
    if codes:
        return 'tls_error', 'error', {'openssl_code': int(codes[0], 16)}
    for fragment, event in [('address already in use','listener_in_use'),
                            ('permission denied','file_permission_denied'),
                            ('certificate','tls_certificate_error'), ('pwfile','credentials_file_error'),
                            ('not authoris','authentication_denied'), ('not authoriz','authentication_denied'),
                            ('protocol error','protocol_error'), ('out of memory','memory_error')]:
        if fragment in text:
            return event, 'error', {}
    if 'terminating' in text:
        return 'broker_stopped', 'notice', {}
    if 'running' in text and 'mosquitto version' in text:
        return 'broker_ready', 'notice', {}
    if 'reloading config' in text:
        return 'broker_reload', 'notice', {}
    if 'error' in text:
        return 'broker_error', 'error', {}
    if 'warning' in text:
        return 'broker_warning', 'warning', {}
    return 'broker_notice', 'notice', {}


def main():
    log = EventLog('broker', os.environ.get('MONITOR_LOG_DIR'))
    child = None
    try:
        child = subprocess.Popen(['/usr/sbin/mosquitto', '-c', '/opt/medical-monitor/broker/mosquitto.conf'],
                                 stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        def forward(number, frame):
            # 证书刷新仍通过主进程 HUP，代理须转发到 Broker；停止也正常保存持久状态。
            if child.poll() is None:
                child.send_signal(number)
        for number in (signal.SIGTERM, signal.SIGINT, signal.SIGHUP):
            signal.signal(number, forward)
        log.emit('broker_started')
        while True:
            data = child.stdout.readline(8192)
            if not data:
                break
            event, severity, fields = classify(data.decode('utf-8', errors='replace'))
            log.emit(event, severity, **fields)
        code = child.wait()
        log.emit('broker_exit', 'error' if code else 'notice', code=code)
        return code if code >= 0 else 1
    except Exception:
        log.emit('broker_wrapper_failed', 'error')
        return 1
    finally:
        if child and child.poll() is None:
            child.terminate()
            try:
                child.wait(timeout=10)
            except subprocess.TimeoutExpired:
                child.kill()
                child.wait()
        log.close()


if __name__ == '__main__':
    sys.exit(main())
