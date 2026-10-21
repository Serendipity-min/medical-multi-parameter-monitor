"""冻结包中转与远端解包的本机tmp仿真，不调用SSH或修改/opt。"""
import hashlib
import io
import json
from pathlib import Path
import tarfile
import pytest
from tools import h3_stage_runtime as stage


def fixture_package(tmp_path,unsafe=False):
    archive=tmp_path/'runtime.tar.gz';payload=b'synthetic source'
    manifest={'schema':2,'backend_session_fix_present':True,'persistent_usage_ledger':True,
        'payload_sha256':'a'*64,'critical_source_sha256':{'source.py':hashlib.sha256(payload).hexdigest()}}
    with tarfile.open(archive,'w:gz') as f:
        for name,value in [('source.py',payload),('H3_RUNTIME_SOURCE.json',json.dumps(manifest).encode())]:
            info=tarfile.TarInfo(name);info.size=len(value);f.addfile(info,io.BytesIO(value))
        if unsafe:
            info=tarfile.TarInfo('../outside');info.size=1;f.addfile(info,io.BytesIO(b'!'))
    receipt=tmp_path/'receipt.json';receipt.write_text(json.dumps({'archive_sha256':stage.sha(archive),
        'archive_bytes':archive.stat().st_size,'source_commit':'synthetic','runtime_payload_sha256':'a'*64}))
    return archive,receipt


def test_stage_plan_and_explicit_cloud_gate_never_call_network(tmp_path,monkeypatch):
    archive,receipt=fixture_package(tmp_path)
    def forbidden(*a,**k):raise AssertionError('NETWORK_WAS_CALLED')
    monkeypatch.setattr(stage.subprocess,'run',forbidden)
    assert stage.plan(archive,receipt)['action']=='UPLOAD_EXTRACT_VERIFY_ONLY'
    with pytest.raises(ValueError,match='EXPLICIT_CLOUD_STAGE'):
        stage.upload(archive,receipt,{})
    archive.write_bytes(b'changed')
    with pytest.raises(ValueError,match='ARCHIVE_MISMATCH'):stage.plan(archive,receipt)


@pytest.mark.parametrize('unsafe',[False,True])
def test_remote_extraction_scope_and_content_before_target_creation(tmp_path,unsafe,capsys):
    archive,receipt=fixture_package(tmp_path,unsafe)
    parent=tmp_path/'releases';parent.mkdir();target=parent/('runtime-'+'a'*12)
    identity=stage.plan(archive,receipt);identity['target']=str(target)
    # 仅将服务器固定父目录映射到tmp；其他检查和真实tar解包路径保持不变。
    code=stage.remote_script(str(archive),identity).replace(
        "pathlib.Path('/opt/medical-monitor-h3/releases')",'pathlib.Path('+repr(str(parent))+')')
    if unsafe:
        with pytest.raises(AssertionError):exec(compile(code,'synthetic-stage','exec'),{})
        assert not target.exists() and archive.exists()
    else:
        exec(compile(code,'synthetic-stage','exec'),{})
        assert (target/'source.py').read_bytes()==b'synthetic source' and not archive.exists()
    assert not (tmp_path/'outside').exists()
