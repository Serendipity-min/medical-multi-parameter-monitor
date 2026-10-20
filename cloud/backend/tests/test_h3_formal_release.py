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
    (stage/'mqtt.json').write_text('{"client_id":"synthetic-formal","port":8883,"purpose":"FORMAL_BACKEND_READONLY"}')
    plan={'plan_schema_version':2,'formal_mqtt_policy':{'port':8883,'purpose':'FORMAL_BACKEND_READONLY'},'stage':str(stage),'release':str(payload),'original_services':identity,
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


def test_old_isolated_plan_cannot_activate(prepared):
    target,stage,snippet,commands=prepared
    d=json.loads(target.read_text());d.pop('plan_schema_version');target.write_text(json.dumps(d))
    with pytest.raises(RuntimeError,match='R2_REPREPARE'):release.switch(target)
    assert snippet.read_text()=='original route' and commands==[]


def test_signed_hash_of_isolated_config_is_still_rejected(prepared):
    target,stage,snippet,commands=prepared
    (stage/'mqtt.json').write_text('{"port":8884,"purpose":"FORMAL_BACKEND_READONLY"}')
    d=json.loads(target.read_text());d['owned_mqtt_config']['sha256']=release.digest(stage/'mqtt.json');target.write_text(json.dumps(d))
    with pytest.raises(RuntimeError,match='CANDIDATE_MQTT_POLICY_CHANGED'):release.switch(target)
    assert snippet.read_text()=='original route' and commands==[]


@pytest.mark.parametrize('value',[{}, {'port':8884}, {'port':8883,'purpose':'ISOLATED'}])
def test_formal_config_requires_explicit_private_role(tmp_path,value):
    p=tmp_path/'config.json';p.write_text(json.dumps(value));p.chmod(0o600)
    # Windows权限模型不能证明POSIX 0600，因此用Linux式权限边界替身做同一策略判断。
    from unittest.mock import patch
    from types import SimpleNamespace
    with patch.object(Path,'stat',return_value=SimpleNamespace(st_mode=0o100600)):
        with pytest.raises(ValueError,match='FORMAL_MQTT_POLICY_REQUIRED'):release.formal_mqtt_config(p,tmp_path/'runtime')


def test_missing_formal_config_does_not_fall_back_to_isolation(tmp_path):
    with pytest.raises(ValueError,match='FORMAL_MQTT_CONFIG_REQUIRED'):
        release.formal_mqtt_config(None,tmp_path/'runtime')


def test_degraded_backend_is_not_ready(prepared,monkeypatch):
    from io import StringIO
    class Response(StringIO):status=200
    monkeypatch.setattr(release.urllib.request,'urlopen',lambda *args,**kwargs:Response('{"status":"degraded","mqtt_connected":false}'))
    target,stage,snippet,commands=prepared
    with pytest.raises(RuntimeError,match='NEW_SERVICE_NOT_READY'):release.switch(target)
    assert snippet.read_text()=='original route'


def test_second_unit_mismatch_is_checked_before_first_install(prepared):
    target,stage,snippet,commands=prepared
    (stage/release.UNITS[1]).write_text('changed unit')
    with pytest.raises(RuntimeError,match='OWNED_UNIT_MISMATCH'):release.switch(target)
    assert not (stage.parents[1]/'system'/release.UNITS[0]).exists()
    assert snippet.read_text()=='original route' and commands==[]


def test_partial_unit_copy_failure_enters_cleanup(prepared,monkeypatch):
    target,stage,snippet,commands=prepared
    original=release.atomic_copy
    def failing(source,destination):
        if source.name==release.UNITS[1]:raise OSError('synthetic copy failure')
        return original(source,destination)
    monkeypatch.setattr(release,'atomic_copy',failing)
    with pytest.raises(OSError,match='synthetic copy failure'):release.switch(target)
    assert ['systemctl','disable','--now',*release.UNITS] in commands
    assert snippet.read_text()=='original route'
