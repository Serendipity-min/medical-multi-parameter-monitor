"""VOICE-002专用有界用量窗口；保留原H3账本，跨进程预留且不靠重启重置。"""
from contextlib import contextmanager
from pathlib import Path
import sqlite3
import time
import uuid


class VoiceBudget:
    def __init__(self, path: str, until: int):
        self.path, self.until = Path(path), until
        if not self.path.is_absolute() or not self.path.parent.is_dir():
            raise ValueError('VOICE_BUDGET_PATH')
        with self.db() as db:
            db.execute('CREATE TABLE IF NOT EXISTS voice_calls(id TEXT PRIMARY KEY, tokens INTEGER NOT NULL, status TEXT NOT NULL)')
        self.path.chmod(0o600)

    @contextmanager
    def db(self):
        db = sqlite3.connect(self.path, timeout=2, isolation_level=None)
        try:
            db.execute('BEGIN IMMEDIATE')
            yield db
            db.commit()
        except BaseException:
            db.rollback()
            raise
        finally:
            db.close()

    def reserve(self, input_bytes: int):
        # 最多1700 UTF-8字节的输入+128输出+封装余量，保守预留2000Token；超额不发请求。
        now = int(time.time()*1000)
        if not now < self.until <= now+7200000 or input_bytes > 1700:
            raise ValueError('VOICE_BUDGET_WINDOW_OR_INPUT')
        ident = uuid.uuid4().hex
        with self.db() as db:
            calls, tokens = db.execute('SELECT count(*),coalesce(sum(tokens),0) FROM voice_calls').fetchone()
            if calls >= 3 or tokens+2000 > 5000:
                raise ValueError('VOICE_BUDGET_EXHAUSTED')
            db.execute('INSERT INTO voice_calls VALUES(?,?,?)', (ident,2000,'RESERVED'))
        return ident

    def finish(self, ident, evidence):
        value = evidence.get('usage', {}).get('total_tokens')
        # 网络失败/缺失用量保留整份预算；未知不能按零费用处理，也不自动重试。
        value = value if type(value) is int and value >= 0 else 2000
        with self.db() as db:
            db.execute('UPDATE voice_calls SET tokens=?,status=? WHERE id=?',
                       (value,evidence.get('status','UNKNOWN'),ident))
