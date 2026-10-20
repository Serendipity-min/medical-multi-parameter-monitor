"""当前已批准C窗口的本地编排；秘密文件只通过外部路径传给受限工具。"""
from pathlib import Path
from datetime import datetime,timedelta,timezone
import hashlib,json,os,subprocess,sys

root=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(root))
private=Path('E:/medical-monitor-h3-private')
out=root/'gateway/physical_can/evidence/h3-r2/c-window'
statefile=private/'r2-current-window-reference.json'
action=sys.argv[1]
if action=='prepare':
    out.mkdir(exist_ok=False)
    plan=json.loads((root/'gateway/physical_can/evidence/h3-r2/persistence-tool/offline-plan.json').read_text())
    matches=[p for p in private.glob('r2-persistent-record-*/record.bin') if hashlib.sha256(p.read_bytes()).hexdigest()==plan['record_sha256']]
    if not matches:raise RuntimeError('FROZEN_RECORD_NOT_FOUND')
    stamp=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    work=private/('r2-c-window-'+stamp);work.mkdir()
    head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=root,text=True).strip()
    window={'role':'C','port':'COM15','source_commit':head,'actions':['backup','program','restore'],
      'expires_utc':(datetime.now(timezone.utc)+timedelta(hours=6)).isoformat(),
      'erase_sectors':[0,1,2,3],'mqtt_tls_port':8884,
      'image_sha256':plan['image_sha256'],'record_sha256':plan['record_sha256'],
      'identity_source_sha256':plan['identity_source_sha256'],
      'authority':'USER_APPROVED_SINGLE_C_WINDOW_THIS_TURN',
      'bounds':'No human input, A firmware unchanged, protected7/11/options unchanged, no cloud SG or production changes'}
    with (work/'owner-window.json').open('x') as f:json.dump(window,f,indent=2)
    reference={'private_dir':str(work),'record':str(matches[0]),'source_commit':head}
    if statefile.exists():raise RuntimeError('EXISTING_WINDOW_REFERENCE_REVIEW_REQUIRED')
    with statefile.open('x') as f:json.dump(reference,f)
    with (out/'owner-window.json').open('x') as f:json.dump(window,f,indent=2)
    print(json.dumps({'prepared':True,'physical_actions_run':False,'source_commit':head}));raise SystemExit(0)

reference=json.loads(statefile.read_text());work=Path(reference['private_dir'])
from gateway.esp_at_probe.build import LIBRARY
command=[sys.executable,'-m','gateway.physical_can.r2_flash_c','--action',action,
 '--manifest',str(root/'gateway/physical_can/evidence/h3-r2/persistent-isolated/isolated-arm-result.json'),
 '--image',str(root/'gateway/physical_can/build/h3-r2-persistent-isolated/gateway_physical_can.bin'),
 '--record',reference['record'],'--owner-window',str(work/'owner-window.json'),
 '--private-dir',str(work),'--identity-source','E:/stm32/ai_serial_console/tools/flash.py',
 '--commit',reference['source_commit'],'--sdk-root',str(LIBRARY)]
if action in ('program','restore'):command+=['--reset-c']
if action=='backup':command+=['--previous-receipt',str(root/'gateway/physical_can/evidence/h3/c-download-20261020T074926Z.json')]
elif action in ('program','restore'):
    command+=['--baseline',str(work/'baseline.json')]
    if action=='restore':command+=['--expected-current-sha256',sys.argv[2]]
r=subprocess.run(command,cwd=root,capture_output=True,text=True,timeout=300)
try:result=json.loads(r.stdout)
except ValueError:result={'exit_code':r.returncode or 1,'failure_code':'NON_JSON_RUNNER_OUTPUT','raw_suppressed':True}
stamp=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
with (out/(action+'-'+stamp+'.json')).open('x') as f:json.dump(result,f,indent=2)
print(json.dumps(result));raise SystemExit(r.returncode or result['exit_code'])
