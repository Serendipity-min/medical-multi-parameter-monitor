"""只允许恢复本轮拥有的隔离角色；外部更改发生后必须保留原件并拒绝覆盖。"""
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace
import pytest
from cloud.deploy.h3 import network_probe


@pytest.mark.parametrize('foreign_change',[False,True])
def test_probe_cleanup_preserves_original_files_and_rejects_foreign_change(tmp_path,monkeypatch,foreign_change):
    state=tmp_path/'state';state.mkdir()
    directory=tmp_path/'broker';directory.mkdir()
    backup=state/'network-probe-backup-1';backup.mkdir()
    before={};after={}
    for name in ('passwords','acl'):
        original=('synthetic-before-'+name).encode();added=original+b'\nsynthetic-probe-role'
        (backup/name).write_bytes(original);(directory/name).write_bytes(added)
        before[name]=hashlib.sha256(original).hexdigest();after[name]=hashlib.sha256(added).hexdigest()
    (state/'network-probe-ownership.json').write_text(json.dumps({'backup':str(backup),'before':before,'after':after}))
    (state/'network-probe.json').write_text('{}')
    monkeypatch.setattr(network_probe,'STATE',state)
    monkeypatch.setattr(network_probe,'Path',lambda p:directory if str(p)=='/opt/medical-monitor-h3/broker' else Path(p))
    commands=[]
    def run(args,**kwargs):commands.append(args);return SimpleNamespace(returncode=0)
    monkeypatch.setattr(network_probe.subprocess,'run',run)
    if foreign_change:
        (directory/'acl').write_bytes(b'foreign-change')
        prior=(directory/'passwords').read_bytes()
        with pytest.raises(ValueError,match='OWNERSHIP_CHANGED'):network_probe.cleanup()
        assert (directory/'passwords').read_bytes()==prior and (state/'network-probe.json').exists()
        assert not commands
    else:
        assert network_probe.cleanup()['exit_code']==0
        for name in before:
            assert hashlib.sha256((directory/name).read_bytes()).hexdigest()==before[name]
        assert not (state/'network-probe.json').exists()
        assert commands==[['systemctl','kill','--signal=HUP','medical-monitor-h3-broker-diagnostic']]
