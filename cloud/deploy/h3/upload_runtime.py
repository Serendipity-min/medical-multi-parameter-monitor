"""通过本机专用中转目录上传最小候选，远端尺寸/哈希核验后仅删除本次暂存包。"""
import hashlib
import json
from pathlib import Path
import subprocess
import tarfile
import uuid

ROOT=Path(__file__).resolve().parents[3]


def main():
    stage=Path('E:/Server_file')/('h3-runtime-'+uuid.uuid4().hex+'.tar.gz')
    files=[]
    for folder in ('cloud/ai','cloud/backend','cloud/deploy/h3'):
        files+=list((ROOT/folder).rglob('*.py'))
    files += [p for p in (ROOT/'cloud/web/dist').rglob('*') if p.is_file()]
    with tarfile.open(stage,'w:gz') as archive:
        for p in sorted(files):archive.add(p,arcname=p.relative_to(ROOT).as_posix())
    size=stage.stat().st_size;sha=hashlib.sha256(stage.read_bytes()).hexdigest()
    if size>1024**3:raise RuntimeError('TRANSFER_SIZE_GATE')
    remote='/tmp/'+stage.name
    result=subprocess.run(['scp',str(stage),'tencent-codex:'+remote],capture_output=True)
    if result.returncode:raise RuntimeError('SCP_FAILED_RETAINED_STAGING')
    script=f'''
import pathlib,hashlib,tarfile,json
p=pathlib.Path({remote!r})
assert p.stat().st_size=={size} and hashlib.sha256(p.read_bytes()).hexdigest()=={sha!r}
root=pathlib.Path('/opt/medical-monitor-h3/releases/runtime-{sha[:12]}')
root.mkdir(parents=True,exist_ok=False)
with tarfile.open(p) as archive:archive.extractall(root,filter='data')
p.unlink()
print(json.dumps({{'sha256':{sha!r},'bytes':{size},'release':str(root),'verified':True}}))
'''
    result=subprocess.run(['ssh','tencent-codex','sudo -n python3 -'],input=script,text=True,capture_output=True)
    if result.returncode:raise RuntimeError('REMOTE_VERIFY_FAILED_RETAINED_STAGING')
    receipt=json.loads(result.stdout)
    (ROOT/'cloud/evidence/h3'/('runtime-upload-'+sha[:12]+'.json')).write_text(json.dumps(receipt,indent=2),encoding='utf-8')
    Path('E:/medical-monitor-h3-private/runtime-upload.json').write_text(json.dumps(receipt),encoding='utf-8')
    assert stage.resolve().parent==Path('E:/Server_file').resolve();stage.unlink()
    print(json.dumps(receipt,indent=2))


if __name__=='__main__':
    try:main()
    except Exception as exc:
        print(json.dumps({'failure_type':type(exc).__name__,'details_suppressed':True}));raise SystemExit(1)
