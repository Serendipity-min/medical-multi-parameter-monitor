"""运行事件白名单：持久化前去除原始文本，限制体积并支持线程并发写入。"""
from datetime import datetime, timezone
import json
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

EVENTS = {
    'broker_started', 'broker_ready', 'broker_stopped', 'broker_exit', 'broker_reload',
    'broker_error', 'broker_warning', 'broker_notice', 'broker_wrapper_failed',
    'tls_error', 'tls_certificate_error', 'authentication_denied', 'protocol_error',
    'listener_in_use', 'file_permission_denied', 'credentials_file_error', 'memory_error',
    'mqtt_connected', 'mqtt_disconnected', 'mqtt_subscribed', 'mqtt_connect_failed',
    'mqtt_metrics', 'backend_stopped',
}
FIELDS = {'code', 'accepted', 'rejected', 'dropped', 'queue_depth', 'attempts', 'signal', 'openssl_code'}


class EventLog:
    def __init__(self, component, directory=None, max_bytes=5*1024*1024, backups=7):
        if component not in {'broker', 'backend'}:
            raise ValueError('Unknown log component')
        self.component = component
        self.logger = logging.Logger('monitor.'+component, level=logging.INFO)
        # stdout 进入 journald；独立轮转文件不依赖系统 journal 是否持久化。
        self.logger.addHandler(logging.StreamHandler())
        if directory:
            folder = Path(directory)
            folder.mkdir(parents=True, exist_ok=True, mode=0o750)
            handler = RotatingFileHandler(folder/(component+'.jsonl'), maxBytes=max_bytes,
                                          backupCount=backups, encoding='utf-8')
            self.logger.addHandler(handler)

    def emit(self, event, severity='notice', **fields):
        if event not in EVENTS or severity not in {'notice', 'warning', 'error'}:
            raise ValueError('Unknown diagnostic event')
        # 值只接受数字和布尔值；地址、用户名、Token、Topic 和载荷不会进入日志。
        safe = {key: value for key, value in fields.items()
                if key in FIELDS and type(value) in (int, bool)}
        record = {'timestamp': datetime.now(timezone.utc).isoformat(),
                  'component': self.component, 'severity': severity, 'event': event, **safe}
        self.logger.info(json.dumps(record, separators=(',', ':')))

    def close(self):
        for handler in self.logger.handlers[:]:
            handler.close()
            self.logger.removeHandler(handler)
