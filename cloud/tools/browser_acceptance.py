"""通过 agent-browser 检查页面真实状态；Token 经 stdin 传递，不进入命令参数。"""

import argparse
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import time


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--config', type=Path, required=True)
    parser.add_argument('--control', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--restart-ssh-alias', help='显式指定时，测试本项目 Backend 重启与 Nginx reload')
    parser.add_argument('--control-ssh-alias', help='显式指定时控制服务器上的合成发布器')
    args = parser.parse_args()
    config = json.loads(args.config.read_text(encoding='utf-8-sig'))
    executable = shutil.which('agent-browser.cmd') or shutil.which('agent-browser')
    if not executable:
        raise RuntimeError('agent-browser is required')
    checks = []
    args.output.mkdir(parents=True, exist_ok=True)

    def cli(*parts, script=None):
        # Windows 首次启动的浏览器守护进程可能继承 stdout 句柄；用临时文件
        # 避免 capture_output 等待所有后代关闭管道，从而造成验收进程挂起。
        with tempfile.TemporaryFile(mode='w+', encoding='utf-8') as output:
            result = subprocess.run([executable, '--session', 'medical-monitor-mqtt-v07', *parts],
                                    input=script, stdout=output, stderr=output, text=True, encoding='utf-8', timeout=30)
            if result.returncode:
                # CLI 错误可能包含当前 URL，不写进报告。
                raise RuntimeError('browser command failed: ' + parts[0])
            output.seek(0)
            return output.read().strip()

    def evaluate(expression):
        return json.loads(cli('eval', '--stdin', script=expression))

    def wait(expression, timeout=15):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if evaluate(expression):
                return
            time.sleep(.3)
        raise RuntimeError('browser state timeout')

    def control(**values):
        # 原子替换控制文件，避免 Mock 看到半写入 JSON。
        temporary = args.control.with_suffix('.tmp')
        temporary.write_text(json.dumps(values), encoding='utf-8')
        temporary.replace(args.control)
        if args.control_ssh_alias:
            # 仅同步无凭据的故障开关，原子替换文件避免服务读到半写 JSON。
            code = "from pathlib import Path\np=Path('/opt/medical-monitor/mqtt-config/mock-control.json')\nt=p.with_suffix('.next')\nt.write_text(" + repr(json.dumps(values)) + ")\nt.chmod(0o644)\nt.replace(p)"
            result = subprocess.run(['ssh', args.control_ssh_alias, 'sudo python3 -'], input=code, text=True, capture_output=True, timeout=20)
            assert result.returncode == 0

    def passed(name):
        checks.append(name)
        print('PASS', name, flush=True)

    def login():
        cli('open', config['origin'] + '/medical-monitor/')
        cli('click', '#open-access')
        wait('document.querySelector("#access-dialog").open')
        cli('eval', '--stdin', script='document.querySelector("#view-token").value=' + json.dumps(config['view_token']) + '; document.querySelector("#access-form").requestSubmit(); true')
        wait('document.querySelector("#value-HR").textContent === "72"')

    try:
        control()
        login()
        cli('set', 'viewport', '1920', '1080')
        assert evaluate('document.querySelectorAll("[data-module]").length === 4 && document.querySelector("#value-TEMP").textContent === "36.6" && document.querySelector("#source-banner").textContent.includes("MOCK")')
        assert evaluate('!document.querySelector("#access-dialog").open')
        passed('Four modules plus TEMP and explicit MOCK source')
        wait('Array.from(document.querySelector("#wave-ECG").getContext("2d").getImageData(0,0,300,100).data).some((v,i,a) => i%4===1 && v>150 && v>a[i-1]*1.2)')
        # 核验 RR 图确实绘制了接收到的 RR，而不是仅创建空 Canvas。
        wait('(() => { const c=document.querySelector("#trend-RR"); return Array.from(c.getContext("2d").getImageData(0,0,c.width,c.height).data).some((v,i,a)=>i%4===0 && v>160 && a[i+1]>130 && a[i+2]<150); })()')
        assert evaluate('document.querySelector("#value-RR").textContent === "15"')
        passed('RR numeric and received current RR trend render separately from RESP')
        assert evaluate('document.querySelector("#pressure-sys").textContent === "118" && document.querySelector("#pressure-dia").textContent === "76"')
        passed('NIBP SYS/DIA pair renders without an invented pressure waveform')
        cli('click', '[data-window="16"]')
        assert evaluate('document.querySelector("[data-window=\\"16\\"]").getAttribute("aria-pressed") === "true" && document.querySelector(".window-start").textContent.includes("16")')
        cli('click', '[data-window="8"]')
        passed('Waveform window control changes the display scale')
        cli('click', '#fullscreen')
        wait('document.fullscreenElement !== null')
        cli('click', '#fullscreen')
        wait('document.fullscreenElement === null')
        passed('Fullscreen control enters and exits browser fullscreen')
        assert evaluate('document.documentElement.scrollHeight <= innerHeight && document.documentElement.scrollWidth <= innerWidth')
        passed('All four modules fit within a 1920x1080 screen')
        cli('screenshot', str((args.output / 'public-live.png').resolve()))
        passed('Public browser MOCK values and Canvas signal rendered')
        control(validity='INVALID')
        wait('document.querySelector("#state-HR").textContent.includes("INVALID") && document.querySelector("#value-HR").textContent === "—"')
        assert evaluate('document.querySelector("#value-RR").textContent === "—" && document.querySelector("#rr-trend-status").textContent.includes("无有效")')
        passed('Invalid UI hides numeric values')
        control(node_a_online=False)
        wait('document.querySelector("#value-SpO2").textContent === "—" && document.querySelector("#value-HR").textContent === "72"')
        passed('Node-A offline UI isolation')
        control(node_b_online=False)
        wait('document.querySelector("#value-HR").textContent === "—" && document.querySelector("#value-SpO2").textContent === "98"')
        passed('Node-B offline UI isolation')
        control(); wait('document.querySelector("#value-HR").textContent === "72"')
        control(mode='REPLAY')
        wait('document.querySelector("#replay-status").textContent.includes("模拟补传")')
        wait('document.querySelector("#value-HR").textContent === "—" && document.querySelector("#gateway").textContent.includes("ONLINE")')
        cli('screenshot', str((args.output / 'public-replay.png').resolve()))
        passed('REPLAY reaches separate panel and LIVE expires')
        control(); wait('document.querySelector("#value-HR").textContent === "72"')
        control(network_online=False)
        wait('document.querySelector("#gateway").textContent.includes("OFFLINE") && document.querySelector("#value-HR").textContent === "—"')
        control(); wait('document.querySelector("#value-HR").textContent === "72"')
        passed('Network disconnect and automatic reconnection')
        control(pause=True)
        wait('document.querySelector("#value-HR").textContent === "—"')
        control(); wait('document.querySelector("#value-HR").textContent === "72"')
        passed('Silent stream expires and recovers')
        login()
        passed('Page refresh and authenticated resubscription')
        if args.restart_ssh_alias:
            result = subprocess.run(['ssh', '-o', 'BatchMode=yes', args.restart_ssh_alias,
                                     'sudo -n systemctl restart medical-monitor'], capture_output=True, timeout=30)
            assert result.returncode == 0
            wait('document.querySelector("#value-HR").textContent === "72" && document.querySelector("#connection").textContent.includes("已连接")', timeout=20)
            passed('Backend restart and browser/Mock reconnection')
            result = subprocess.run(['ssh', '-o', 'BatchMode=yes', args.restart_ssh_alias,
                                     'sudo -n nginx -t >/dev/null 2>&1 && sudo -n systemctl reload nginx'], capture_output=True, timeout=30)
            assert result.returncode == 0
            wait('document.querySelector("#value-HR").textContent === "72"')
            passed('Nginx validated reload while streaming')
        # 切换到尚无数据的真机网关必须清空模拟值，不能串源。
        cli('select', '#gateway-select', 'GW-C-001')
        wait('document.querySelector("#gateway-id").textContent === "GW-C-001" && document.querySelector("#value-HR").textContent === "—"')
        cli('select', '#gateway-select', 'GW-DEV-001')
        wait('document.querySelector("#value-HR").textContent === "72"')
        passed('Gateway selection isolates data sources')
        if args.restart_ssh_alias:
            result = subprocess.run(['ssh', args.restart_ssh_alias, 'sudo systemctl stop medical-monitor-mqtt'], capture_output=True, timeout=30)
            assert result.returncode == 0
            wait('document.querySelector("#gateway").textContent.includes("OFFLINE") && document.querySelector("#value-HR").textContent === "—"', timeout=15)
            result = subprocess.run(['ssh', args.restart_ssh_alias, 'sudo systemctl start medical-monitor-mqtt'], capture_output=True, timeout=30)
            assert result.returncode == 0
            wait('document.querySelector("#gateway").textContent.includes("ONLINE") && document.querySelector("#value-HR").textContent === "72"', timeout=25)
            passed('Broker restart restores MQTT publisher and backend subscription')
        cli('set', 'viewport', '390', '844')
        assert evaluate('document.documentElement.scrollWidth <= innerWidth')
        cli('screenshot', str((args.output / 'public-mobile.png').resolve()))
        passed('Mobile layout has no horizontal overflow')
        cli('set', 'viewport', '1920', '1080')
        report = {'passed': len(checks), 'checks': checks, 'simulation': True,
                  'timestamp': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())}
        (args.output / 'browser-acceptance.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    finally:
        control()
        cli('close')


if __name__ == '__main__':
    main()
