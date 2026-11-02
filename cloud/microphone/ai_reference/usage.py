"""持久用量流水：保留历史审计，跨线程/进程限并发与速率，不设置累计调用上限。"""
from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import time
import uuid


class UsageBlocked(ValueError):
    pass


class UsageLedger:
    def __init__(self, directory):
        self.directory = Path(directory)
        self.path = self.directory / 'usage.sqlite3'
        try:
            fd = os.open(self.path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
            os.close(fd)
        except FileExistsError:
            pass
        with self.transaction() as db:
            # 避免executescript隐式提交；建表和历史导入共享同一个进程间写事务。
            db.execute('CREATE TABLE IF NOT EXISTS requests(id TEXT PRIMARY KEY, started REAL NOT NULL, lease_until REAL NOT NULL, status TEXT NOT NULL, metadata TEXT NOT NULL)')
            db.execute('CREATE TABLE IF NOT EXISTS legacy(name TEXT PRIMARY KEY, sha256 TEXT NOT NULL)')
            db.execute('CREATE INDEX IF NOT EXISTS requests_started ON requests(started)')
            # 旧五槽文件只读取/逐份导入，原件不删除、不改写；重启不会重复入账。
            for item in sorted(self.directory.glob('call-*.json')):
                if db.execute('SELECT 1 FROM legacy WHERE name=?', (item.name,)).fetchone():
                    continue
                data = item.read_bytes()
                old = json.loads(data)
                safe = {k: old[k] for k in ('model', 'requested_model', 'reported_model',
                         'status', 'http_status', 'latency_ms', 'usage', 'request_id') if k in old}
                db.execute('INSERT INTO requests VALUES(?,?,?,?,?)',
                           ('legacy:' + item.name, item.stat().st_mtime, 0,
                            'LEGACY_IMPORTED', json.dumps(safe)))
                db.execute('INSERT INTO legacy VALUES(?,?)', (item.name, hashlib.sha256(data).hexdigest()))

    @contextmanager
    def transaction(self):
        db = sqlite3.connect(self.path, timeout=5, isolation_level=None)
        try:
            db.execute('PRAGMA busy_timeout=5000')
            db.execute('BEGIN IMMEDIATE')
            yield db
            db.commit()
        except BaseException:
            db.rollback()
            raise
        finally:
            db.close()

    def reserve(self, model):
        now, ident = time.time(), uuid.uuid4().hex
        with self.transaction() as db:
            # 异常终止只释放过期租约并保留UNKNOWN记录，不能靠重启抹掉失败/用量。
            db.execute("UPDATE requests SET status='INTERRUPTED_UNKNOWN' WHERE status='RESERVED' AND lease_until<?", (now,))
            if db.execute("SELECT count(*) FROM requests WHERE status='RESERVED'").fetchone()[0] >= 4:
                raise UsageBlocked('MODEL_CONCURRENCY_LIMIT')
            if db.execute('SELECT count(*) FROM requests WHERE started>?', (now-60,)).fetchone()[0] >= 12:
                raise UsageBlocked('MODEL_RATE_LIMIT')
            recent = db.execute("SELECT status FROM requests WHERE status!='RESERVED' AND started>? ORDER BY started DESC LIMIT 3", (now-60,)).fetchall()
            if len(recent) == 3 and all(row[0] in ('API_ERROR', 'TIMEOUT', 'AUTH_ERROR', 'QUOTA_ERROR') for row in recent):
                raise UsageBlocked('MODEL_CIRCUIT_OPEN')
            db.execute('INSERT INTO requests VALUES(?,?,?,?,?)',
                       (ident, now, now+30, 'RESERVED', json.dumps({'requested_model': model})))
        return ident

    def finish(self, ident, evidence):
        # 调用者只传固定审计字段；不接受问题正文、模型回复、事实或凭据。
        allowed = ('requested_model', 'reported_model', 'status', 'http_status', 'error_code',
                   'latency_ms', 'usage', 'request_id', 'finish_reason', 'billing_state')
        safe = {k: evidence[k] for k in allowed if k in evidence}
        with self.transaction() as db:
            db.execute('UPDATE requests SET status=?, lease_until=0, metadata=? WHERE id=?',
                       (safe.get('status', 'API_ERROR'), json.dumps(safe), ident))

    def summary(self):
        usage = {k: 0 for k in ('prompt_tokens', 'completion_tokens', 'total_tokens')}
        errors = {}
        count = 0
        # 只读逐行汇总，历史增长不产生全表内存副本，也不占用预留调用的写锁。
        with sqlite3.connect(self.path, timeout=5) as db:
            for state, metadata in db.execute('SELECT status, metadata FROM requests'):
                count += 1
                data = json.loads(metadata)
                for key in usage:
                    value = data.get('usage', {}).get(key)
                    if type(value) is int and value >= 0:
                        usage[key] += value
                if state not in ('VALIDATED', 'LEGACY_IMPORTED'):
                    errors[state] = errors.get(state, 0) + 1
        return {'requests': count, 'usage': usage, 'states': errors,
                'billing_state': 'TOKEN_USAGE_RECORDED_COST_NOT_INFERRED', 'lifetime_cap': None}
