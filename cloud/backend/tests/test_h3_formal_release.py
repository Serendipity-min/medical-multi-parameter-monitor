"""只用临时目录模拟发布失败，禁止接触systemd/Nginx或真实服务器。"""
import json
from pathlib import Path
import pytest
from cloud.deploy.h3 import formal_release as release


@pytest.fixture
def prepared(tmp_path,monkeypatch):
    stage=tmp_path/'formal'/'test';(stage/'backup').mkdir(parents=True)
    snippet=tmp_path/'snippet';snippet.write_text('original route')
    (stage/'backup/0').write_bytes(snippet.read_bytes())
    (stage/'candidate.nginx.conf').write_text('candidate route')
    payload=tmp_path/'runtime';payload.mkdir();(payload/'source.py').write_text('# synthetic source')
    system=tmp_path/'system';system.mkdir()
    # 映射仅本模块使用的绝对路径，其他文件访问仍由真实tmp_path约束。
    def mapped(value):
        if str(value)=='/opt/medical-monitor-h3/formal':return tmp_path/'formal'
        if str(value)=='/etc/systemd/system':return system
        return Path(value)
    monkeypatch.setattr(release,'Path',mapped);monkeypatch.setattr(release,'SNIPPET',snippet)
    identity={'original':{'pid':'123','state':'active'}}
    monkeypatch.setattr(release,'service_identity',lambda:identity)
    for unit in release.UNITS:(stage/unit).write_text('synthetic unit')
    for name in ('backend.env','ai.env'):(stage/name).write_text('SYNTHETIC=true')
    (stage/'mqtt.json').write_text('{"client_id":"synthetic-formal"}')
    plan={'stage':str(stage),'release':str(payload),'original_services':identity,
          'original_hashes':{str(snippet):release.digest(snippet)},
          'candidate_nginx_sha256':release.digest(stage/'candidate.nginx.conf'),
          'owned_unit_sha256':{u:release.digest(stage/u) for u in release.UNITS},
          'owned_env_sha256':{n:release.digest(stage/n) for n in ('backend.env','ai.env')},
          'owned_mqtt_config':{'path':str(stage/'mqtt.json'),'sha256':release.digest(stage/'mqtt.json')},
          'source':{'critical_source_sha256':{'source.py':release.digest(payload/'source.py')}}}
    target=stage/'plan.json';target.write_text(json.dumps(plan))
    commands=[];monkeypatch.setattr(release,'run',lambda args:commands.append(args) or '')
    monkeypatch.setattr(release.time,'sleep',lambda _:None)
    return target,stage,snippet,commands


def test_damaged_rollback_backup_blocks_every_mutation(prepared):
    target,stage,snippet,commands=prepared
    (stage/'backup/0').write_text('corrupted backup')
    with pytest.raises(RuntimeError,match='ROLLBACK_BACKUP_CHANGED'):release.switch(target)
    assert snippet.read_text()=='original route' and commands==[]


def test_start_health_failure_stops_owned_units_and_preserves_route(prepared,monkeypatch):
    target,stage,snippet,commands=prepared
    def unavailable(*args,**kwargs):raise OSError('synthetic health failure')
    monkeypatch.setattr(release.urllib.request,'urlopen',unavailable)
    with pytest.raises(RuntimeError,match='NEW_SERVICE_NOT_READY'):release.switch(target)
    assert snippet.read_text()=='original route'
    assert ['systemctl','disable','--now',*release.UNITS] in commands
    assert not any('reload' in command for command in commands)
