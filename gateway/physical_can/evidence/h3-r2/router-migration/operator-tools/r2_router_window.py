"""已获批准的路由器换网窗口；只调用sector3专用事务，不输出外部凭据。"""
from pathlib import Path
from datetime import datetime,timedelta,timezone
import hashlib,json,subprocess,sys

root=Path(__file__).resolve().parents[3];sys.path.insert(0,str(root))
private=Path('E:/medical-monitor-h3-private')
out=root/'gateway/physical_can/evidence/h3-r2/router-migration'
reference=json.loads((private/'r2-router-reference.json').read_text())
work=Path(reference['private_dir']);action=sys.argv[1]
if action=='prepare':
    plan=json.loads((out/'prepared-plan.json').read_text())
    head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=root,text=True).strip()
    window={k:plan[k] for k in ('role','port','image_sha256','record_sha256','previous_record_sha256','erase_sectors')}
    window.update(source_commit=head,actions=['wifi-backup','wifi-update','wifi-restore'],
      expires_utc=(datetime.now(timezone.utc)+timedelta(hours=4)).isoformat(),mqtt_tls_port=8884,
      identity_source_sha256=hashlib.sha256(Path('E:/stm32/ai_serial_console/tools/flash.py').read_bytes()).hexdigest(),
      controlled_c_rom_reset=True,authority='USER_APPROVED_ROUTER_SECTOR3_WINDOW',
      bounds='C sector3 only; A and C application unchanged; protect7/11/options; no human input or production changes')
    with (work/'owner-window.json').open('x') as f:json.dump(window,f,indent=2)
    with (out/'owner-window.json').open('x') as f:json.dump(window,f,indent=2)
    reference.update(source_commit=head,isolation_tag=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ-router'))
    # 独立路由器引用不覆盖已完成热点窗口的原件；后续服务编排显式读取该新引用。
    with (work/'window-reference.json').open('x') as f:json.dump(reference,f,indent=2)
    print(json.dumps({'exit_code':0,'source_commit':head,'scope':[3],'hardware_accessed':False}));raise SystemExit(0)

reference=json.loads((work/'window-reference.json').read_text())
from gateway.esp_at_probe.build import LIBRARY
command=[sys.executable,'-m','gateway.physical_can.r2_flash_c','--action',action,
 '--manifest',str(root/'gateway/physical_can/evidence/h3-r2/persistent-isolated/isolated-arm-result.json'),
 '--image',str(root/'gateway/physical_can/build/h3-r2-persistent-isolated/gateway_physical_can.bin'),
 '--record',reference['record'],'--previous-record',reference['previous_record'],
 '--owner-window',str(work/'owner-window.json'),'--private-dir',str(work),
 '--identity-source','E:/stm32/ai_serial_console/tools/flash.py','--commit',reference['source_commit'],
 '--sdk-root',str(LIBRARY),'--reset-c']
if action=='wifi-backup':command+=['--previous-baseline',reference['previous_baseline']]
else:command+=['--baseline',str(work/'baseline.json')]
if action=='wifi-restore':command+=['--expected-current-sha256',sys.argv[2]]
r=subprocess.run(command,cwd=root,capture_output=True,text=True,timeout=300)
try:value=json.loads(r.stdout)
except ValueError:value={'exit_code':r.returncode or 1,'failure_code':'OUTPUT_SUPPRESSED'}
stamp=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
with (out/(action+'-'+stamp+'.json')).open('x') as f:json.dump(value,f,indent=2)
print(json.dumps(value));raise SystemExit(r.returncode or value['exit_code'])
