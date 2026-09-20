"""整改回归：优化模式门禁、归档路径检查和日志持久化/白名单。"""
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import zipfile

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/'backend'))
from app.diagnostics import EventLog


@pytest.mark.parametrize('code,severity', [(0, 'notice'), (128, 'warning')])
def test_disconnect_severity_distinguishes_normal_shutdown(code, severity):
    from app.mqtt_adapter import MqttAdapter
    from types import SimpleNamespace
    import queue
    events = []
    adapter = MqttAdapter.__new__(MqttAdapter)
    adapter.pending = queue.Queue()
    adapter.pending.put(('obsolete', b'old'))
    adapter.log = SimpleNamespace(emit=lambda *args, **fields: events.append((args, fields)))
    adapter.on_disconnect(None, None, None, SimpleNamespace(value=code), None)
    assert events == [(('mqtt_disconnected', severity), {'code': code})]
    assert not adapter.connected and adapter.pending.empty()


def module(name):
    spec = importlib.util.spec_from_file_location(name, ROOT/'deploy'/(name+'.py'))
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


@pytest.mark.parametrize('failure', ['uid', 'release', 'hash', 'exists', 'traversal', 'symlink'])
def test_preflight_remains_enforced_under_optimized_python(tmp_path, failure):
    bundle = tmp_path/'bundle.zip'
    with zipfile.ZipFile(bundle, 'w') as archive:
        name = '../outside' if failure == 'traversal' else 'backend/main.py'
        item = zipfile.ZipInfo(name)
        if failure == 'symlink':
            item.external_attr = 0o120777 << 16
        archive.writestr(item, 'test')
    root = tmp_path/'server'
    if failure == 'exists':
        (root/'broker').mkdir(parents=True)
    digest = '0'*64 if failure == 'hash' else hashlib.sha256(bundle.read_bytes()).hexdigest()
    release = '../bad' if failure == 'release' else 'test-1'
    # 真正启动 -O 子进程，而不是仅检查源码里是否出现 assert。
    code = ('import sys;from pathlib import Path;sys.path.insert(0,'+repr(str(ROOT/'deploy'))+');'
            'from upgrade_mqtt import validate_preflight;validate_preflight('
            f'Path({str(bundle)!r}),{digest!r},{release!r},root=Path({str(root)!r}),uid={1 if failure=="uid" else 0})')
    result = subprocess.run([sys.executable, '-O', '-c', code], capture_output=True, text=True)
    assert result.returncode != 0 and 'RuntimeError:' in result.stderr
    assert not (tmp_path/'outside').exists()


def test_safe_bundle_passes_without_creating_target(tmp_path):
    bundle = tmp_path/'safe.zip'
    with zipfile.ZipFile(bundle, 'w') as archive:
        archive.writestr('backend/app/main.py', '# fixture')
    module('upgrade_mqtt').validate_preflight(bundle, hashlib.sha256(bundle.read_bytes()).hexdigest(),
                                              'safe-1', root=tmp_path/'target', uid=0)
    assert not (tmp_path/'target').exists()


def test_broker_errors_preserve_category_and_code_without_raw_text():
    classify = module('broker_logging').classify
    assert classify('OpenSSL Error[0]: error:0A000086:SSL routines::certificate verify failed at example.invalid')[0:2] == ('tls_error', 'error')
    assert classify('OpenSSL Error: error:0A000086:secret')[2] == {'openssl_code': 0x0A000086}
    assert classify('Error: Address already in use 192.0.2.1')[0] == 'listener_in_use'
    assert classify('Warning: unrecognized text password=test-only')[0:2] == ('broker_warning','warning')


def test_event_log_persists_and_bounds_rotation_without_payload(tmp_path, capsys):
    log = EventLog('backend', tmp_path, max_bytes=400, backups=2)
    for count in range(30):
        log.emit('mqtt_metrics', accepted=count, rejected=0, payload='test-only-secret', code='example.invalid')
    log.close()
    files = list(tmp_path.glob('backend.jsonl*'))
    assert len(files) == 3 and all(p.stat().st_size <= 400 for p in files)
    text = ''.join(p.read_text() for p in files)
    assert 'test-only-secret' not in text and 'example.invalid' not in text
    assert '"accepted":29' in text
    assert all(json.loads(line)['event'] == 'mqtt_metrics' for line in text.splitlines())
    assert 'test-only-secret' not in capsys.readouterr().err
