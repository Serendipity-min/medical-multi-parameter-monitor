"""上传已冻结包的单独门禁；默认只输出计划，不重打包、不启动服务、不安装依赖。"""
import argparse
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import uuid


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def plan(archive,receipt):
    data=json.loads(receipt.read_text())
    if archive.stat().st_size>1024**3:raise ValueError('NETDISK_OWNER_TRANSFER_REQUIRED')
    if archive.stat().st_size!=data['archive_bytes'] or sha(archive)!=data['archive_sha256']:
        raise ValueError('FROZEN_ARCHIVE_MISMATCH')
    return {'archive_sha256':data['archive_sha256'],'archive_bytes':data['archive_bytes'],
        'source_commit':data['source_commit'],
        'target':'/opt/medical-monitor-h3/releases/runtime-'+data['runtime_payload_sha256'][:12],
        'action':'UPLOAD_EXTRACT_VERIFY_ONLY','services_modified':False,'dependencies_installed':False}


def remote_script(remote,identity):
    # 输入只有本次UUID临时名/散列/尺寸/版本目录，没有服务器地址或凭据。
    return '''import hashlib,json,pathlib,tarfile
p=pathlib.Path(REMOTE)
target=pathlib.Path(TARGET)
assert target.parent==pathlib.Path('/opt/medical-monitor-h3/releases') and not target.exists()
assert p.stat().st_size==SIZE and hashlib.sha256(p.read_bytes()).hexdigest()==SHA
p.chmod(0o600)
with tarfile.open(p) as archive:
    members=archive.getmembers()
    assert len({m.name for m in members})==len(members)
    assert all(m.isfile() and not pathlib.PurePosixPath(m.name).is_absolute() and '..' not in pathlib.PurePosixPath(m.name).parts for m in members)
    manifest=json.load(archive.extractfile('H3_RUNTIME_SOURCE.json'))
    assert manifest['schema']==2 and manifest['backend_session_fix_present'] and manifest['persistent_usage_ledger']
    assert set(manifest['critical_source_sha256'])|{'H3_RUNTIME_SOURCE.json'}=={m.name for m in members}
    for name,expected in manifest['critical_source_sha256'].items():
        assert hashlib.sha256(archive.extractfile(name).read()).hexdigest()==expected
    assert target.name=='runtime-'+manifest['payload_sha256'][:12]
    target.mkdir(mode=0o755)
    archive.extractall(target,filter='data')
for name,expected in manifest['critical_source_sha256'].items():
    assert hashlib.sha256((target/name).read_bytes()).hexdigest()==expected
p.unlink()
print(json.dumps({'exit_code':0,'archive_sha256':SHA,'target':str(target),'state':'STAGED_ONLY_NO_INSTALL_NO_SERVICE_CHANGE'}))
'''.replace('REMOTE',repr(remote)).replace('TARGET',repr(identity['target'])).replace('SIZE',str(identity['archive_bytes'])).replace('SHA',repr(identity['archive_sha256']))


def upload(archive,receipt,auth):
    identity=plan(archive,receipt)
    if auth.get('auth_id')!='AUTH-AC-CLOUD-STAGE' or auth.get('approved_by_owner') is not True:
        raise ValueError('EXPLICIT_CLOUD_STAGE_APPROVAL_REQUIRED')
    expiry=datetime.fromisoformat(auth['expires_utc'])
    if expiry.tzinfo is None or datetime.now(timezone.utc)>=expiry:
        raise ValueError('OWNER_WINDOW_EXPIRED')
    if any(auth.get(k)!=identity[k] for k in ('archive_sha256','target','action')) or auth.get('tool_sha256')!=sha(__file__):
        raise ValueError('OWNER_SCOPE_OR_TOOL_CHANGED')
    # 此包由本机源码生成，服务器没有可直接下载来源；严格经本机指定中转目录。
    staging=Path('E:/Server_file');staging.mkdir(exist_ok=True)
    temporary=staging/('h3-final-'+uuid.uuid4().hex+'.tar.gz')
    shutil.copyfile(archive,temporary)
    if sha(temporary)!=identity['archive_sha256']:raise RuntimeError('STAGING_COPY_MISMATCH')
    remote='/tmp/'+temporary.name
    r=subprocess.run(['scp',str(temporary),'tencent-codex:'+remote],capture_output=True,timeout=90)
    if r.returncode:raise RuntimeError('SCP_FAILED_LOCAL_STAGE_RETAINED')
    r=subprocess.run(['ssh','tencent-codex','sudo -n python3 -'],input=remote_script(remote,identity),
        text=True,capture_output=True,timeout=90)
    if r.returncode:raise RuntimeError('REMOTE_VERIFY_FAILED_LOCAL_STAGE_RETAINED')
    result=json.loads(r.stdout)
    if result.get('exit_code')!=0 or result.get('archive_sha256')!=identity['archive_sha256']:
        raise RuntimeError('REMOTE_RECEIPT_MISMATCH_LOCAL_STAGE_RETAINED')
    if temporary.resolve().parent!=staging.resolve() or sha(temporary)!=identity['archive_sha256']:
        raise RuntimeError('LOCAL_CLEANUP_SCOPE_CHANGED')
    temporary.unlink()
    return result


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('action',choices=('plan','upload'))
    p.add_argument('--archive',type=Path,required=True);p.add_argument('--receipt',type=Path,required=True)
    p.add_argument('--auth',type=Path);args=p.parse_args()
    try:
        result=plan(args.archive,args.receipt) if args.action=='plan' else upload(args.archive,args.receipt,json.loads(args.auth.read_text()))
        print(json.dumps(result,indent=2))
    except Exception as error:
        print(json.dumps({'exit_code':1,'failure_type':type(error).__name__,'details_suppressed':True}));raise SystemExit(1)
