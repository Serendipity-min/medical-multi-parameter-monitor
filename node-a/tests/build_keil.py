"""只调用 UV4 rebuild；固定没有下载/调试参数，保留原始日志及进程退出码。"""
from pathlib import Path
import hashlib
import json
import subprocess
ROOT=Path(__file__).resolve().parents[1]
project=ROOT/'STM32F407_HOSPITAL/USER/STM32F407_Template.uvprojx'
out=ROOT/'evidence';out.mkdir(exist_ok=True)
log=out/'a1-final-keil.log'
r=subprocess.run(['D:/keil/UV4/UV4.exe','-r',str(project),'-o',str(log)],creationflags=subprocess.CREATE_NO_WINDOW,timeout=120)
result={'exit_code':r.returncode,'mode':'KEIL_ARMCC_REBUILD_ONLY','hardware':'NOT_ACCESSED','project_sha256':hashlib.sha256(project.read_bytes()).hexdigest()}
(out/'a1-final-keil-exit.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
print('Keil final exit',r.returncode);print(log.read_text(encoding='utf-8',errors='replace')[-700:])
raise SystemExit(r.returncode)
