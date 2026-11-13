"""使用 agent-browser 验证既有 UI；LIVE 夹具仅在本机内存注入，不发布到云端。"""

import argparse
import copy
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import threading
import time

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / 'cloud/backend'))
from app.adapters import decode_mqtt


# 默认仅本机内存夹具；显式给出生产配置才读取公开页面，两种证据必须分开保存。
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--production-config', type=Path)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    executable = shutil.which('agent-browser.cmd') or shutil.which('agent-browser')
    if not executable:
        raise RuntimeError('agent-browser unavailable')

    def cli(*parts, script=None):
        # 浏览器守护进程不能继承可阻塞父进程的 stdout 管道；敏感输入只走 stdin。
        with tempfile.TemporaryFile(mode='w+', encoding='utf-8') as output:
            r = subprocess.run(
                [executable, '--session', 'medical-canopen-phase2', *parts],
                input=script,
                stdout=output,
                stderr=output,
                text=True,
                encoding='utf-8',
                timeout=30,
            )
            if r.returncode:
                raise RuntimeError('Browser operation failed: ' + parts[0])
            output.seek(0)
            return output.read().strip()

    def evaluate(script):
        return json.loads(cli('eval', '--stdin', script=script))

    def wait(script, seconds=20):
        end = time.monotonic() + seconds
        while time.monotonic() < end:
            if evaluate(script):
                return
            time.sleep(0.2)
        raise RuntimeError('Browser condition timed out')

    server = None
    checks = []
    try:
        if args.production_config:
            config = json.loads(args.production_config.read_text(encoding='utf-8-sig'))
            cli('open', config['origin'] + '/medical-monitor/')
            cli('snapshot', '-i')
            cli('click', '#open-access')
            evaluate(
                'document.querySelector("#view-token").value='
                + json.dumps(config['view_token'])
                + ';document.querySelector("#access-form").requestSubmit();true'
            )
            cli('select', '#gateway-select', 'GW-C-001')
            wait(
                'document.querySelector("#value-HR").textContent==="73" && document.querySelector("#value-SpO2").textContent==="97"'
            )
            if not evaluate(
                'document.querySelector("#source-banner").textContent.includes("MOCK") && document.querySelector("#value-RR").textContent==="—"'
            ):
                raise RuntimeError('Production synthetic/RR semantics failed')
            checks.append('Public Gateway-C CANopen data renders as MOCK; RR remains unavailable')
        else:

            class Handler(SimpleHTTPRequestHandler):
                def log_message(self, *unused):
                    pass

                def translate_path(self, path):
                    self.path = path.removeprefix('/medical-monitor')
                    return super().translate_path(self.path)

            server = ThreadingHTTPServer(
                ('127.0.0.1', 0), partial(Handler, directory=str(ROOT / 'cloud/web/dist'))
            )
            threading.Thread(target=server.serve_forever, daemon=True).start()
            cli('open', f'http://127.0.0.1:{server.server_port}/medical-monitor/')
            cli('snapshot', '-i')
            evaluate(
                'window.WebSocket=class { static OPEN=1;readyState=1;constructor(){window.fixtureSocket=this;setTimeout(()=>this.onopen?.(),0)}send(){}close(){this.readyState=3}};true'
            )
            cli('select', '#gateway-select', 'GW-C-001')
            cli('click', '#open-access')
            evaluate(
                'document.querySelector("#view-token").value="local-fixture-token-not-production-12345";document.querySelector("#access-form").requestSubmit();true'
            )
            values = {}
            for line in (ROOT / 'gateway/canopen/build/canonical.jsonl').read_text().splitlines():
                topic, body = line.split('\t', 1)
                value = decode_mqtt(topic, body.encode()).model_dump()
                if value['stream'] not in ('NODE_STATUS', 'GATEWAY_STATUS', 'FAULT'):
                    values[value['stream']] = value
            snapshot = {
                'type': 'snapshot',
                'schema_version': 1,
                'gateway_id': 'GW-C-001',
                'gateway_state': 'ONLINE',
                'nodes': {'NODE-A': 'ONLINE', 'NODE-B': 'ONLINE'},
                'streams': list(values.values()),
                'replay': None,
                'event': None,
            }
            # 同一份 C 模型输出先验证 MOCK，再仅在离线浏览器测试来源切换。
            evaluate(
                'window.fixture='
                + json.dumps(snapshot)
                + ';window.fixtureTimer=setInterval(()=>{for(const s of fixture.streams){s.timestamp=Date.now();s.seq++}fixtureSocket.onmessage({data:JSON.stringify(fixture)})},200);true'
            )
            wait(
                'document.querySelector("#source-banner").textContent.includes("MOCK") && document.querySelector("#value-HR").textContent==="73"'
            )
            checks.append('C canonical MOCK frames render in unchanged UI')
            evaluate('fixture.streams.forEach(s=>{s.source="LIVE";s.synthetic=false});true')
            wait(
                'document.querySelector("#source-banner").textContent==="LIVE" && document.querySelector("#value-SpO2").textContent==="97"'
            )
            checks.append('Same browser schema renders LIVE fixture without source-specific layout')
            replay = copy.deepcopy(values['HR'])
            replay.update(source='REPLAY', synthetic=False, value=49.0, seq=900)
            evaluate('fixture.replay=' + json.dumps(replay) + ';true')
            wait('document.querySelector("#replay-status").textContent.includes("#900")')
            if not evaluate(
                'document.querySelector("#value-HR").textContent==="73" && document.querySelector("#value-RR").textContent==="—" && document.querySelector("#event-status").textContent==="无事件"'
            ):
                raise RuntimeError('Replay isolation failed')
            checks.append('REPLAY is separate; current HR and alarms unchanged; RR INVALID hidden')
            evaluate(
                'const b=document.createElement("div");b.textContent="本机接口夹具 · 非传感器实测 · 未上传云端";b.style="position:fixed;bottom:0;right:0;background:#fff;color:#000;padding:8px;z-index:9999";document.body.append(b);true'
            )
        cli('set', 'viewport', '1920', '1080')
        wait(
            '(() => {const c=document.querySelector("#wave-ECG");return Array.from(c.getContext("2d").getImageData(0,0,c.width,c.height).data).some((v,i,a)=>i%4===1&&v>150&&v>a[i-1]*1.2)})()'
        )
        checks.append('ECG canvas contains rendered signal')
        cli('screenshot', str((args.output / 'screen.png').resolve()))
        (args.output / 'report.json').write_text(
            json.dumps(
                {
                    'checks': checks,
                    'fixture_only': not bool(args.production_config),
                    'web_source_modified': False,
                },
                indent=2,
            )
            + '\n'
        )
        print(json.dumps({'passed': len(checks), 'fixture_only': not bool(args.production_config)}))
    finally:
        cli('close')
        if server:
            server.shutdown()
            server.server_close()


if __name__ == '__main__':
    main()
