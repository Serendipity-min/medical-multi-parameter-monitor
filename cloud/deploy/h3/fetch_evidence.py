"""仅取回已结束的脱敏MQTT/WSS观测，经本机中转、大小及SHA核验，不接触凭据文件。"""
import hashlib
import json
from pathlib import Path
import subprocess
import tarfile
import uuid

ROOT=Path(__file__).resolve().parents[3]


def main():
    name='h3-observation-'+uuid.uuid4().hex+'.tar.gz'
    remote='/tmp/'+name
    script='''import pathlib,tarfile,hashlib,json,re,os
state=pathlib.Path('/var/lib/medical-monitor-p6/h3-20261019')
archive=pathlib.Path(REMOTE)
files=[]
for directory in sorted(state.glob('e2e-*')):
 if not directory.is_dir() or not re.fullmatch(r'e2e-\\d{8}T\\d{6}Z',directory.name):continue
 if not (directory/'result.json').is_file():continue
 for name in ('mqtt-metadata.jsonl','wss-metadata.jsonl','result.json','status.json'):
  file=directory/name
  if file.is_file():files.append(file)
with tarfile.open(archive,'w:gz') as output:
 for file in files:output.add(file,arcname=file.relative_to(state).as_posix())
assert files,'NO_COMPLETED_OBSERVATION_FILES'
archive.chmod(0o600)
# 只把本次脱敏包交给SSH操作者，原受限目录与凭据权限不改变。
os.chown(archive,int(os.environ['SUDO_UID']),-1)
print(json.dumps({'sha256':hashlib.sha256(archive.read_bytes()).hexdigest(),'bytes':archive.stat().st_size,'files':len(files)}))
'''.replace('REMOTE',repr(remote))
    result=subprocess.run(['ssh','tencent-codex','sudo -n python3 -'],input=script,text=True,capture_output=True)
    if result.returncode:raise RuntimeError('REMOTE_EVIDENCE_PACKAGE_FAILED')
    receipt=json.loads(result.stdout)
    if receipt['bytes']>1024**3:raise RuntimeError('TRANSFER_SIZE_GATE')
    stage=Path('E:/Server_file')/name
    result=subprocess.run(['scp','tencent-codex:'+remote,str(stage)],capture_output=True)
    if result.returncode:raise RuntimeError('EVIDENCE_DOWNLOAD_FAILED')
    if stage.stat().st_size!=receipt['bytes'] or hashlib.sha256(stage.read_bytes()).hexdigest()!=receipt['sha256']:
        raise RuntimeError('LOCAL_EVIDENCE_HASH_MISMATCH')
    out=ROOT/'cloud/evidence/h3/observations';out.mkdir(exist_ok=True)
    # 远端与本地双侧限定元数据白名单；包里不得出现env/密钥/原始生理值文件。
    with tarfile.open(stage) as archive:
        for item in archive.getmembers():
            relative=Path(item.name)
            if len(relative.parts)!=2 or relative.name not in ('mqtt-metadata.jsonl','wss-metadata.jsonl','result.json','status.json'):
                raise RuntimeError('EVIDENCE_MEMBER_NOT_ALLOWED')
            destination=out/relative
            if not destination.resolve().is_relative_to(out.resolve()):raise RuntimeError('EVIDENCE_PATH')
            data=archive.extractfile(item).read()
            if destination.exists() and destination.read_bytes()!=data:raise RuntimeError('EXISTING_EVIDENCE_CHANGED')
            destination.parent.mkdir(exist_ok=True);destination.write_bytes(data)
    cleanup="from pathlib import Path;Path("+repr(remote)+").unlink()"
    result=subprocess.run(['ssh','tencent-codex','python3 -'],input=cleanup,text=True,capture_output=True)
    if result.returncode:raise RuntimeError('REMOTE_TEMP_CLEANUP_FAILED')
    if stage.resolve().parent!=Path('E:/Server_file').resolve():raise RuntimeError('LOCAL_STAGE_PATH')
    stage.unlink()
    receipt.update(exit_code=0,staging_removed=True,remote_temporary_removed=True,raw_measurements_included=False)
    (ROOT/'cloud/evidence/h3/observation-download.json').write_text(json.dumps(receipt,indent=2))
    print(json.dumps(receipt))


if __name__=='__main__':
    try:main()
    except Exception as exc:
        print(json.dumps({'exit_code':1,'failure_type':type(exc).__name__,'details_suppressed':True}))
        raise SystemExit(1)
