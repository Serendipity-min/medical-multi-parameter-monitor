"""持久用量、跨进程准入及历史迁移回归，全部使用合成审计，不调用外部模型。"""
from concurrent.futures import ProcessPoolExecutor
import hashlib
import json
from types import SimpleNamespace
import pytest
from cloud.ai.usage import UsageLedger, UsageBlocked


def reserve_and_finish(directory):
    ledger = UsageLedger(directory)
    ident = ledger.reserve('synthetic-model')
    ledger.finish(ident, {'status': 'VALIDATED', 'usage': {'total_tokens': 3},
                          'question': 'NOT_STORED', 'facts': 'NOT_STORED'})
    return ident


def test_no_lifetime_cap_and_restart_preserves_usage(tmp_path, monkeypatch):
    clock = [1000.0]
    monkeypatch.setattr('cloud.ai.usage.time', SimpleNamespace(time=lambda: clock[0]))
    ledger = UsageLedger(tmp_path)
    for _ in range(40):
        ident = ledger.reserve('synthetic-model')
        ledger.finish(ident, {'status': 'VALIDATED', 'usage': {'total_tokens': 2}})
        clock[0] += 6
    summary = UsageLedger(tmp_path).summary()
    assert summary['requests'] == 40 and summary['usage']['total_tokens'] == 80
    assert summary['lifetime_cap'] is None


def test_old_slots_import_once_preserve_original_bytes(tmp_path):
    path = tmp_path / 'call-01.json'
    path.write_text(json.dumps({'status': 'VALIDATED', 'usage': {'total_tokens': 7}}))
    original = hashlib.sha256(path.read_bytes()).hexdigest()
    assert UsageLedger(tmp_path).summary()['requests'] == 1
    assert UsageLedger(tmp_path).summary()['usage']['total_tokens'] == 7
    assert hashlib.sha256(path.read_bytes()).hexdigest() == original


def test_cross_process_creation_and_recording(tmp_path):
    with ProcessPoolExecutor(max_workers=4) as pool:
        identifiers = list(pool.map(reserve_and_finish, [str(tmp_path)] * 8))
    assert len(set(identifiers)) == 8
    ledger = UsageLedger(tmp_path)
    assert ledger.summary()['requests'] == 8 and ledger.summary()['usage']['total_tokens'] == 24
    assert b'NOT_STORED' not in ledger.path.read_bytes()


def test_concurrency_lease_expiry_and_circuit_do_not_delete_history(tmp_path, monkeypatch):
    clock = [1000.0]
    monkeypatch.setattr('cloud.ai.usage.time', SimpleNamespace(time=lambda: clock[0]))
    ledger = UsageLedger(tmp_path)
    ids = [ledger.reserve('synthetic') for _ in range(4)]
    with pytest.raises(UsageBlocked, match='CONCURRENCY'):
        ledger.reserve('synthetic')
    clock[0] += 31
    ident = ledger.reserve('synthetic')
    assert ledger.summary()['states']['INTERRUPTED_UNKNOWN'] == 4
    ledger.finish(ident, {'status': 'API_ERROR'})
    for _ in range(2):
        ident = ledger.reserve('synthetic'); ledger.finish(ident, {'status': 'API_ERROR'})
    with pytest.raises(UsageBlocked, match='CIRCUIT'):
        ledger.reserve('synthetic')
    clock[0] += 61
    assert ledger.reserve('synthetic')
    assert ledger.summary()['requests'] == 8


def test_rate_limit_not_a_lifetime_limit(tmp_path, monkeypatch):
    clock = [1000.0]
    monkeypatch.setattr('cloud.ai.usage.time', SimpleNamespace(time=lambda: clock[0]))
    ledger = UsageLedger(tmp_path)
    for _ in range(12):
        ident = ledger.reserve('synthetic'); ledger.finish(ident, {'status': 'VALIDATED'})
    with pytest.raises(UsageBlocked, match='RATE'):
        ledger.reserve('synthetic')
    clock[0] += 61
    assert ledger.reserve('synthetic')
