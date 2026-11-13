"""扩展首轮 Browser Acceptance：六路由与共享会话回归，仅访问本地夹具。"""
import argparse
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import time
from urllib.parse import urlparse


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--config', type=Path, required=True)
    parser.add_argument('--control', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    config = json.loads(args.config.read_text(encoding='utf-8-sig'))
    if urlparse(config['origin']).hostname not in ('127.0.0.1', 'localhost', '::1'):
        parser.error('本验收仅允许本机回环目标')
    executable = shutil.which('agent-browser.cmd') or shutil.which('agent-browser')
    if not executable:
        raise RuntimeError('agent-browser required')
    args.output.mkdir(parents=True, exist_ok=True)
    checks = []

    def cli(*parts, script=None):
        # 防止 Windows 守护进程继承管道导致挂起；凭据只通过 stdin 送入页面。
        with tempfile.TemporaryFile(mode='w+', encoding='utf-8') as output:
            result = subprocess.run([executable, '--session', 'medical-stitch-local', *parts],
                                    input=script, stdout=output, stderr=output, text=True,
                                    encoding='utf-8', timeout=40)
            if result.returncode:
                raise RuntimeError('browser command failed: ' + parts[0])
            output.seek(0)
            return output.read().strip()

    def evaluate(expression):
        return json.loads(cli('eval', '--stdin', script=expression))

    def wait(expression, timeout=18):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if evaluate(expression):
                return
            time.sleep(.25)
        raise RuntimeError('state timeout: ' + expression)

    def control(**values):
        temporary = args.control.with_suffix('.tmp')
        # 功能回归使用固定值便于精确断言；日常预览默认为多样化场景。
        temporary.write_text(json.dumps({'scenario': 'fixed', **values}), encoding='utf-8')
        temporary.replace(args.control)

    def passed(name):
        checks.append(name)
        print('PASS', name, flush=True)

    def route(name):
        cli('click', f'[data-route="{name}"]')
        wait(f'location.hash === "#/{name}" && document.querySelector(".route-{name}") !== null')

    def screenshot(name):
        cli('screenshot', str((args.output / (name + '.png')).resolve()))

    def connect():
        cli('click', '#open-access')
        cli('eval', '--stdin', script='document.querySelector("#view-token").value=' + json.dumps(config['view_token']) + ';document.querySelector("#access-form").requestSubmit();true')
        wait('document.querySelector("#source-banner").textContent.includes("MOCK")')

    def state(selector, value):
        return f'document.querySelector({json.dumps(selector)})?.textContent === {json.dumps(value)}'

    try:
        control()
        cli('set', 'viewport', '1920', '1080')
        cli('open', config['origin'] + '/medical-monitor/')
        cli('snapshot', '-i')
        assert evaluate('location.hash === "#/overview"')
        passed('01 默认进入 overview')
        route('ecg')
        assert evaluate('document.querySelector("#history-rows").children.length === 0 && document.querySelector("#export-csv").disabled')
        passed('02 未接收数据时历史和趋势为空，导出禁用')
        route('overview')
        # 仅计数连接与帧，不记录帧内容、认证载荷或 URL 参数。
        evaluate('window.__wsCreated=0; window.__frames=0; window.WebSocket=class extends WebSocket {constructor(...args){super(...args);window.__wsCreated++;this.addEventListener("message",()=>window.__frames++);}};true')
        connect()
        wait(state('#value-HR', '72'))
        for channel in ('ECG', 'PPG', 'RESP'):
            wait('(() => {const c=document.querySelector("#wave-' + channel + '");return [...c.getContext("2d").getImageData(0,0,c.width,c.height).data].some((v,i,a)=>i%4===0 && (a[i+1]>160 || v>180));})()')
        passed('03 三路 Canvas 均绘制实际接收波形')
        assert evaluate(state('#pressure-sys', '118') + ' && ' + state('#pressure-dia', '76') + ' && ' + state('#value-TEMP', '36.6'))
        passed('04 总览显示六项实时标量与 SYS/DIA')
        screenshot('overview-1920x1080')
        screenshot('overview-mock')
        for key in ('ecg', 'spo2', 'resp', 'nibp', 'temp'):
            cli('click', f'.numeric-tile.{key}')
            wait(f'location.hash === "#/{key}"')
            passed('05 总览卡片进入 ' + key)
            assert evaluate('document.querySelector("#source-banner").textContent.includes("MOCK")')
            wait('document.querySelector("#history-rows").children.length > 0')
            screenshot(key + '-1920x1080')
            assert evaluate('document.querySelector("#route-view").scrollHeight <= document.querySelector("#route-view").clientHeight + 1')
            route('overview')
        for key in ('temp', 'ecg', 'spo2', 'resp', 'nibp', 'overview'):
            route(key)
            assert evaluate(f'document.querySelector("[data-route={key}]").getAttribute("aria-current") === "page"')
        passed('06 六页底部导航及活动标记')
        assert evaluate('window.__wsCreated === 1 && window.__frames > 5')
        passed('07 路由切换不重连、不重新认证，接收持续')
        for key in ('temp', 'ecg', 'spo2', 'resp', 'nibp'):
            route(key)
            assert evaluate('document.querySelector("#source-banner").textContent.includes("MOCK")')
            assert evaluate('(() => {const ids=[...document.querySelectorAll("[id]")].map(x=>x.id);return ids.length===new Set(ids).size;})()')
        passed('08 全部页面 MOCK 明显且 Canvas/DOM 无重复 ID')
        route('ecg')
        assert evaluate(r'!/Lead II|ECG II|\bST\b|\bQT\b|\bPVC\b|25mm|10mm/.test(document.body.innerText)')
        passed('09 ECG 无多导联、诊断或物理标定假文案')
        route('spo2')
        assert evaluate(r'!/\bPI\b|灌注指数|AC\/DC|探头正常/.test(document.body.innerText)')
        passed('10 SpO2 无 PI、灌注或探头自检结论')
        route('temp')
        assert evaluate(r'!/\bTa\b|\bTo\b|\bFOV\b|环境温度|内部校准/.test(document.body.innerText)')
        passed('11 TEMP 无虚构环境温、校准及 FOV')
        route('nibp')
        assert evaluate(r'!/\bMAP\b|开始测量|停止测量|放气|校准|0x2A|CRC/.test(document.body.innerText) && document.querySelectorAll("canvas").length === 1')
        passed('12 NIBP 仅 SYS/DIA 离散记录，无远程控制')
        route('resp')
        assert evaluate('!/Ω|64kHz|RA-LL|呼吸暂停|节律正常/.test(document.body.innerText)')
        passed('13 RESP 无电阻标定与诊断推断')
        control(validities={'RR': 'INVALID'})
        wait(state('#value-RR', '--'))
        assert evaluate('document.querySelector("#quality-RESP").textContent.includes("VALID")')
        screenshot('rr-invalid')
        passed('14 RR INVALID 显示 --，RESP 波形质量独立')
        control()
        wait(state('#value-RR', '15'))
        wait('document.querySelector("#history-rows").children.length === 12')
        passed('15 新记录推动有界最近记录表与会话趋势')
        count = evaluate('window.__frames')
        cli('click', '#freeze')
        wait('document.querySelector("#frozen-status").hidden === false')
        evaluate('window.__frozenWave=document.querySelector("#wave-RESP").toDataURL();true')
        control(values={'RR': 21})
        wait(f'window.__frames > {count + 3}')
        assert evaluate(state('#value-RR', '15'))
        assert evaluate('window.__frozenWave === document.querySelector("#wave-RESP").toDataURL()')
        passed('16 FREEZE 保持波形与数值，底层继续接收')
        cli('click', '#freeze')
        wait(state('#value-RR', '21'))
        passed('17 恢复显示立即呈现最新接收值')
        # 截取本次用户点击生成的本地 Blob，不落盘凭据或采集网络载荷。
        evaluate('window.__blobFactory=URL.createObjectURL;window.__csv=null;URL.createObjectURL=function(blob){blob.text().then(text=>window.__csv=text);return window.__blobFactory(blob);};true')
        cli('click', '#export-csv')
        wait('window.__csv !== null')
        assert evaluate('window.__csv.includes("MOCK") && window.__csv.includes("timestamp,channel") && window.__csv.split("\\r\\n").length > 2')
        evaluate('URL.createObjectURL=window.__blobFactory;delete window.__csv;true')
        passed('18 CSV 由本次会话生成且只在点击后导出')
        control()
        route('overview')
        control(node_a_online=False)
        wait(state('#value-SpO2', '--') + ' && ' + state('#value-HR', '72'))
        assert evaluate(state('#pressure-sys', '--'))
        screenshot('node-a-offline')
        passed('19 Node-A 离线只清空血氧、脉率、血压')
        control(node_b_online=False)
        wait(state('#value-HR', '--') + ' && ' + state('#value-SpO2', '98'))
        assert evaluate(state('#value-RR', '--') + ' && ' + state('#value-TEMP', '--'))
        screenshot('node-b-offline')
        passed('20 Node-B 离线只清空心电、呼吸、体温')
        control()
        wait(state('#value-HR', '72'))
        control(network_online=False)
        wait('document.querySelector("#gateway").textContent.includes("OFFLINE") && ' + state('#value-HR', '--'))
        passed('21 Gateway 离线清空旧值')
        control()
        wait(state('#value-HR', '72'))
        control(pause=True)
        wait(state('#value-HR', '--'))
        passed('22 静默数据过期后清空')
        control()
        wait(state('#value-HR', '72'))
        control(mode='REPLAY')
        wait('document.querySelector("#replay-status").textContent.includes("模拟补传")')
        wait(state('#value-HR', '--'))
        passed('23 REPLAY 独立显示，不续活 LIVE')
        control()
        wait(state('#value-HR', '72'))
        route('ecg')
        cli('click', '#open-settings')
        wait('document.querySelector("#access-dialog").open')
        cli('select', '#gateway-select', 'GW-C-001')
        wait('document.querySelector("#history-rows").children.length === 0 && ' + state('#value-HR', '--'))
        passed('24 切换网关清空历史及当前值')
        cli('select', '#gateway-select', 'GW-DEV-001')
        wait(state('#value-HR', '72'))
        cli('click', '[data-window="16"]')
        assert evaluate('document.querySelector(".window-start").textContent.includes("16")')
        cli('click', '[data-window="8"]')
        cli('click', '#fullscreen')
        wait('document.fullscreenElement !== null')
        assert evaluate('!document.querySelector("#access-dialog").open')
        # 进入全屏后设置层必须退出；重新打开设置才能操作退出按钮。
        cli('click', '#open-settings')
        cli('click', '#fullscreen')
        wait('document.fullscreenElement === null')
        assert evaluate('!document.querySelector("#access-dialog").open')
        passed('25 设置、显示窗口和全屏可操作')
        assert evaluate('!location.search && !location.hash.includes("token") && localStorage.length === 0 && sessionStorage.length === 0 && document.querySelector("#view-token").value === ""')
        passed('26 Token 不在 URL、存储或输入框中保留')
        for width, height in ((1920, 1080), (1600, 900), (1366, 768)):
            cli('set', 'viewport', str(width), str(height))
            route('overview')
            assert evaluate('document.documentElement.scrollHeight <= innerHeight && document.documentElement.scrollWidth <= innerWidth && document.querySelector("#route-view").scrollHeight <= document.querySelector("#route-view").clientHeight + 1')
            screenshot(f'overview-{width}x{height}')
            passed(f'27 总览 {width}×{height} 无滚动遮挡')
        cli('set', 'viewport', '390', '844')
        for key in ('overview', 'ecg', 'spo2', 'resp', 'nibp', 'temp'):
            route(key)
            assert evaluate('document.documentElement.scrollWidth <= innerWidth && document.querySelector("#route-view").scrollWidth <= document.querySelector("#route-view").clientWidth + 1')
        screenshot('temp-390x844')
        passed('28 六页移动端均无横向溢出，中央区域可滚动')
        cli('set', 'viewport', '1920', '1080')
        cli('open', config['origin'] + '/medical-monitor/#/ecg')
        # 只改变 hash 是同文档导航；必须真正重载才能验证内存会话清空。
        cli('reload')
        wait('document.querySelector("#history-rows") !== null')
        assert evaluate('document.querySelector("#history-rows").children.length === 0 && document.querySelector("#export-csv").disabled && ' + state('#value-HR', '--'))
        passed('29 刷新不保留令牌、不伪造历史或自动认证')
        resources = evaluate('[...performance.getEntriesByType("resource")].map(x=>new URL(x.name).origin).every(x=>x===location.origin)')
        assert resources
        passed('30 运行时仅加载本源资源，无 CDN 或外部字体')
        # 在独立回环验收实例观察默认动态场景，不能扰动用户正在查看的预览。
        control(scenario='varied')
        connect()
        route('overview')
        observed = {name: set() for name in ('HR', 'RR', 'SpO2', 'PR', 'TEMP')}
        deadline = time.monotonic() + 35
        while time.monotonic() < deadline:
            values = evaluate('Object.fromEntries(["HR","RR","SpO2","PR","TEMP"].map(k=>[k,document.getElementById("value-"+k).textContent]))')
            for name, value in values.items():
                observed[name].add(value)
            time.sleep(2)
        assert all(len(values - {'--'}) > 1 for values in observed.values())
        passed('31 默认预览各标量随时间变化，不预填假历史')
        screenshot('overview-varied')
        route('spo2')
        assert evaluate('getComputedStyle(document.querySelector("#value-SpO2")).color === "rgb(255, 82, 103)"')
        assert evaluate('getComputedStyle(document.querySelector("[data-route=spo2]")).color === "rgb(255, 82, 103)"')
        wait('(() => {const c=document.querySelector("#wave-PPG");return [...c.getContext("2d").getImageData(0,0,c.width,c.height).data].some((v,i,a)=>i%4===0 && v>200 && a[i+1]<120 && a[i+2]<160);})()')
        screenshot('spo2-varied')
        passed('32 血氧读数、PPG 波形与活动导航统一红色')
        route('nibp')
        count = evaluate('document.querySelector("#history-rows").children.length')
        assert 2 <= count <= 3
        evaluate('window.__blobFactory=URL.createObjectURL;window.__csv=null;URL.createObjectURL=function(blob){blob.text().then(text=>window.__csv=text);return window.__blobFactory(blob);};true')
        cli('click', '#export-csv')
        wait('window.__csv !== null')
        assert evaluate(r'(() => {const times=window.__csv.split("\r\n").slice(1).map(line=>Date.parse(line.split("\",\"")[0].slice(1)));return times.slice(1).every((t,i)=>t-times[i]===30000);})()')
        evaluate('URL.createObjectURL=window.__blobFactory;delete window.__csv;true')
        screenshot('nibp-varied')
        passed('33 NIBP 约每 30 秒一条，CSV 测量时间间隔 30000ms')
        for key in ('ecg', 'resp', 'temp'):
            route(key)
            screenshot(key + '-varied')
        report = {'passed': len(checks), 'checks': checks, 'simulation': True, 'target': 'loopback-only',
                  'timestamp': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())}
        (args.output / 'browser-acceptance.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    finally:
        control(scenario='varied')
        cli('close')


if __name__ == '__main__':
    main()
