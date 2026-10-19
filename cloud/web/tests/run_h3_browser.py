"""拥有独立进程/浏览器会话的本地回归，结束仅回收本轮资源。"""
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import urllib.request

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT/'cloud/evidence/h3/browser'


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    env = dict(os.environ, PYTHONUTF8='1', P6_BROWSER_SESSION='h3-integration-local',
               P6_BROWSER_EVIDENCE='cloud/evidence/h3/browser')
    processes, files, results = [], [], {}

    def start(label, command, extra=None):
        log = (OUT/(label+'.log')).open('wb'); files.append(log)
        p = subprocess.Popen(command, cwd=ROOT, env={**env, **(extra or {})}, stdout=log, stderr=log,
                             creationflags=subprocess.CREATE_NO_WINDOW if sys.platform=='win32' else 0)
        processes.append(p)
        return p

    def wait(port, path):
        end = time.monotonic()+30
        while time.monotonic()<end:
            try:
                with urllib.request.urlopen(f'http://127.0.0.1:{port}{path}',timeout=1): return
            except Exception: time.sleep(.1)
        raise RuntimeError('LOCAL_SERVICE_NOT_READY')

    try:
        start('monitor-fixture',[sys.executable,'-m','uvicorn','cloud.web.tests.ui_fixture:app','--host','127.0.0.1','--port','18765','--no-access-log'])
        fixture = start('ai-fixture',[sys.executable,'-m','uvicorn','cloud.web.tests.ui_fixture:app','--host','127.0.0.1','--port','18766','--no-access-log'])
        start('vite',['node',str(ROOT/'cloud/web/node_modules/vite/bin/vite.js'),str(ROOT/'cloud/web'),'--host','127.0.0.1','--port','18767','--strictPort'])
        wait(18765,'/fixture/state'); wait(18766,'/fixture/state'); wait(18767,'/medical-monitor/')
        for label, script in [('browser','ui_browser.py'),('service','ui_service.py')]:
            if label=='service':
                fixture.terminate(); fixture.wait(10)
                start('ai-service',[sys.executable,'-m','uvicorn','cloud.ai.app:create_app','--factory','--host','127.0.0.1','--port','18766','--no-access-log'],
                      {'P6_AI_TOKEN':'local-ai-service-'+'x'*32,'P6_MODEL_MODE':'MOCK','P6_SNAPSHOT_MODE':'MONITOR',
                       'P6_MONITOR_VIEW_TOKEN':'local-monitor-fixture-'+'x'*32,'P6_MONITOR_ORIGIN':'http://127.0.0.1:18767','P6_MQTT_MODE':'DISABLED'})
                wait(18766,'/health')
            with (OUT/(label+'-run.log')).open('wb') as log:
                r=subprocess.run([sys.executable,str(Path(__file__).parent/script)],cwd=ROOT,env=env,stdout=log,stderr=log)
            results[label]=r.returncode;print(label,'exit',r.returncode,flush=True)
            if r.returncode:break
    finally:
        # 不关闭其他会话；原始失败日志原样保留，最终只输出退出码。
        subprocess.run(['D:/Node/node_global/node_modules/agent-browser/bin/agent-browser-win32-x64.exe','--session',env['P6_BROWSER_SESSION'],'close'],capture_output=True)
        for p in reversed(processes):
            if p.poll() is None:p.terminate();p.wait(10)
        for f in files:f.close()
        (OUT/'run-result.json').write_text(json.dumps(results,indent=2),encoding='utf-8')
    return int(any(results.values()))


if __name__=='__main__':raise SystemExit(main())
