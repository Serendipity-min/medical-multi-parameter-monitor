"""六页面交互回归：真实全屏 API、命中测试和点击；线上仅访问已授权项目页面。"""
import argparse
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import time
from urllib.parse import urlparse


def load_config(args):
    if args.config:
        config = json.loads(args.config.read_text(encoding='utf-8-sig'))
        if urlparse(config['origin']).hostname not in ('127.0.0.1', 'localhost', '::1'):
            raise ValueError('配置文件模式仅允许回环实例')
        return config
    # 线上原点和只读令牌由现有服务环境读入内存，禁止输出或落盘。
    script = """
import json,subprocess
pid=subprocess.check_output(['systemctl','show','medical-monitor','-p','MainPID','--value'],text=True).strip()
env=dict(x.decode().split('=',1) for x in open('/proc/'+pid+'/environ','rb').read().split(b'\\0') if b'=' in x)
origins=[s.strip() for s in env['MONITOR_ALLOWED_ORIGINS'].split(',') if s.strip().startswith('https://')]
if len(origins)!=1: raise SystemExit(1)
print(json.dumps({'origin':origins[0], 'view_token':env['MONITOR_VIEW_TOKEN']}))
"""
    result = subprocess.run(['ssh', args.ssh_alias, 'sudo python3 -'], input=script,
                            capture_output=True, text=True, encoding='utf-8', timeout=30)
    if result.returncode:
        raise RuntimeError('无法读取已授权服务的运行配置')
    return json.loads(result.stdout)


def main():
    parser = argparse.ArgumentParser()
    target = parser.add_mutually_exclusive_group(required=True)
    target.add_argument('--config', type=Path)
    target.add_argument('--ssh-alias', help='现有 SSH 别名，线上只做正常浏览器操作')
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--auth-only', action='store_true', help='只复测失败弹窗、重试和冻结接收说明')
    args = parser.parse_args()
    config = load_config(args)
    executable = shutil.which('agent-browser.cmd') or shutil.which('agent-browser')
    if not executable:
        parser.error('agent-browser required')
    args.output.mkdir(parents=True, exist_ok=True)
    checks = []
    report = {'target': 'authorized-server' if args.ssh_alias else 'loopback-only',
              'simulation': True, 'checks': checks, 'status': 'running',
              'suite': 'connection-feedback' if args.auth_only else 'full-interaction'}

    def cli(*parts, script=None):
        # 临时文件避免浏览器守护进程继承 stdout 管道；所有原始输出即读即销毁。
        with tempfile.TemporaryFile(mode='w+', encoding='utf-8') as output:
            result = subprocess.run([executable, '--session', 'medical-ui-interaction', *parts],
                                    input=script, stdout=output, stderr=output, text=True,
                                    encoding='utf-8', timeout=40)
            if result.returncode:
                raise RuntimeError('浏览器操作失败：' + parts[0])
            output.seek(0)
            return output.read().strip()

    def evaluate(expression):
        return json.loads(cli('eval', '--stdin', script=expression))

    def wait(expression, timeout=18):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if evaluate(expression):
                return
            time.sleep(.2)
        raise AssertionError('等待页面状态超时')

    def check(name, expression):
        if not evaluate(expression):
            raise AssertionError(name)
        checks.append(name)
        print('PASS', name, flush=True)

    def click(selector, scroll=False):
        encoded = json.dumps(selector)
        if scroll:
            evaluate(f'document.querySelector({encoded}).scrollIntoView({{block:"center"}});true')
        # 不用 JS click 绕过遮挡。先断言点击中心真正命中目标，再发送浏览器点击。
        if not evaluate(f'''(() => {{const e=document.querySelector({encoded});
          if(!e)return false;const r=e.getBoundingClientRect();
          const x=r.x+r.width/2,y=r.y+r.height/2;
          return r.width>0&&r.height>0&&x>=0&&x<innerWidth&&y>=0&&y<innerHeight
            &&e.contains(document.elementFromPoint(x,y));}})()'''):
            raise AssertionError('交互被遮挡或超出视区：' + selector)
        cli('click', selector)

    def route(name):
        click(f'[data-route="{name}"]')
        wait(f'location.hash==="#/{name}" && !!document.querySelector(".route-{name}")')

    def picture(name):
        cli('screenshot', str((args.output / (name + '.png')).resolve()))

    def connect():
        click('#open-access')
        # 令牌只经 stdin 输入，返回值始终为 true；报告、截图不包含输入框内容。
        evaluate('document.querySelector("#view-token").value=' + json.dumps(config['view_token']) + ';true')
        click('#access-form button[type="submit"]')
        wait('document.querySelector("#source-banner").textContent.includes("MOCK")')
        wait('document.querySelector("#value-HR")?.textContent !== "--"')

    def fullscreen():
        click('#open-settings')
        click('#fullscreen')
        wait('document.fullscreenElement === document.documentElement')

    def clear_layer():
        # 全屏根元素本身也匹配 :modal；这里只检测会拦截操作的 dialog 模态层。
        return '!document.querySelector("#access-dialog").open && !document.querySelector("dialog:modal")'

    def layout():
        # 小屏允许中央区域滚动，页面外框与导航仍必须留在视区。
        return '''(() => {const nav=document.querySelector('.bottom-nav').getBoundingClientRect();
          const view=document.querySelector('#route-view');
          return document.documentElement.scrollWidth<=innerWidth
            &&document.documentElement.scrollHeight<=innerHeight
            &&nav.bottom<=innerHeight+1&&nav.top>=0
            &&view.scrollWidth<=view.clientWidth+1
            &&[...document.querySelectorAll('.bottom-nav a,.bottom-nav button')].every(e=>{
              const r=e.getBoundingClientRect();return r.width>0&&r.height>0
                &&e.contains(document.elementFromPoint(r.x+r.width/2,r.y+r.height/2));});})()'''

    try:
        cli('set', 'viewport', '1920', '1080')
        cli('open', config['origin'].rstrip('/') + '/medical-monitor/#/overview')
        cli('snapshot', '-i')
        evaluate('''window.__errors=0;window.__frames=0;window.__sockets=0;
          addEventListener('error',()=>window.__errors++);
          addEventListener('unhandledrejection',()=>window.__errors++);
          window.WebSocket=class extends WebSocket {constructor(...args){super(...args);window.__activeSocket=this;
            window.__sockets++;this.addEventListener('message',()=>window.__frames++);}};true''')
        if args.auth_only:
            # 只用固定的无效合成字符串做两次正常登录失败回归，不枚举或猜测凭据。
            for mode in ('normal', 'fullscreen'):
                if mode == 'fullscreen':
                    fullscreen()
                click('#open-settings')
                evaluate('document.querySelector("#view-token").value="invalid-synthetic-test-token";true')
                click('#access-form button[type="submit"]')
                wait('document.querySelector("#connection-error-dialog").open')
                check(mode + ' 错误令牌出现独立失败弹窗',
                      'document.querySelector("#connection-error-title").textContent==="访问验证失败" && document.querySelector("#connection-error-message").textContent.includes("令牌无效")')
                check(mode + ' 仅有一个模态弹窗且不回显令牌',
                      'document.querySelectorAll("dialog:modal").length===1 && !document.querySelector("#access-dialog").open && document.querySelector("#view-token").value==="" && !document.body.innerText.includes("invalid-synthetic-test-token")')
                count = evaluate('window.__sockets')
                time.sleep(2)
                check(mode + ' 校验失败不自动重试', f'window.__sockets==={count}')
                picture('invalid-token-' + mode)
                if mode == 'normal':
                    click('#close-connection-error')
                    route('ecg')
                    route('overview')
                    check('关闭失败提示后导航恢复', clear_layer())
            click('#retry-access')
            check('重新输入按钮打开设置并聚焦令牌框',
                  'document.querySelector("#access-dialog").open && !document.querySelector("#connection-error-dialog").open && document.activeElement.id==="view-token"')
            evaluate('document.querySelector("#view-token").value=' + json.dumps(config['view_token']) + ';true')
            click('#access-form button[type="submit"]')
            wait('document.querySelector("#source-banner").textContent.includes("MOCK") && document.querySelector("#value-HR").textContent!=="--"')
            check('正确令牌重试后连接成功并保留全屏',
                  clear_layer() + ' && !!document.fullscreenElement && !document.querySelector("#view-token").hasAttribute("aria-invalid")')
            click('#open-settings')
            check('成功后设置不残留旧认证错误', '!document.querySelector("#access-message").textContent.includes("无效")')
            click('#close-access')
            click('#freeze')
            evaluate('window.__frameBefore=window.__frames;window.__frozenValue=document.querySelector("#value-HR").textContent;true')
            wait('window.__frames>window.__frameBefore+4')
            check('冻结继续接收但不改变冻结读数，提示说明内存缓冲',
                  'document.querySelector("#value-HR").textContent===window.__frozenValue && document.querySelector("#received-at").title.includes("内存缓冲") && document.querySelector("#frozen-status").textContent.includes("仍在接收")')
            picture('connected-frozen')
            click('#freeze')
            if args.config:
                # 仅本地客户端接收固定的不兼容格式，验证提示分类，不向服务器发送测试数据。
                evaluate('window.__activeSocket.dispatchEvent(new MessageEvent("message",{data:JSON.stringify({type:"unsupported-version"})}));true')
                wait('document.querySelector("#connection-error-dialog").open')
                check('本地不兼容快照单独提示，不归咎令牌过期',
                      'document.querySelector("#connection-error-title").textContent==="数据格式不兼容" && !document.querySelector("#view-token").hasAttribute("aria-invalid")')
                click('#close-connection-error')
            check('反馈流程无未捕获异常或 Promise 拒绝', 'window.__errors===0')
            report['status'] = 'passed'
            return
        fullscreen()
        check('未连接时进入全屏，设置弹窗退出且不残留模态层', clear_layer())
        picture('fullscreen-disconnected')
        click('.numeric-tile.ecg')
        wait('location.hash==="#/ecg"')
        check('未连接时全屏卡片仍可进入子页', '!!document.fullscreenElement')
        route('overview')
        connect()
        check('全屏内正常连接模拟数据', clear_layer() + ' && window.__sockets===1')
        for key in ('ecg', 'spo2', 'resp', 'nibp', 'temp'):
            click('.numeric-tile.' + key)
            wait(f'location.hash==="#/{key}"')
            check('全屏总览卡片进入 ' + key, '!!document.fullscreenElement && ' + layout())
            click('.detail-heading > a')
            wait('location.hash==="#/overview"')
            check('全屏详情返回总览 ' + key, clear_layer() + ' && !!document.fullscreenElement')
        for key in ('ecg', 'spo2', 'resp'):
            click('.wave-panel.' + key + ' .canvas-container')
            wait(f'location.hash==="#/{key}"')
            check('全屏波形点击进入 ' + key, '!!document.fullscreenElement')
            route('overview')
        for key in ('temp', 'ecg', 'spo2', 'resp', 'nibp', 'overview'):
            route(key)
            check('全屏底部导航 ' + key,
                  f'document.querySelector("[data-route={key}]").getAttribute("aria-current")==="page" && !!document.fullscreenElement')
        route('spo2')
        evaluate('history.back();true')
        wait('location.hash==="#/overview"')
        evaluate('history.forward();true')
        wait('location.hash==="#/spo2"')
        check('全屏浏览器前进后退保持页面和连接', '!!document.fullscreenElement && window.__sockets===1')
        click('#open-settings')
        check('全屏内重新打开设置位于画面上层', 'document.querySelector("#access-dialog").matches(":modal")')
        click('[data-window="16"]')
        click('#close-access')
        route('ecg')
        check('16 秒显示窗口在页面切换后保留', 'document.querySelector(".window-start").textContent.includes("16")')
        click('#open-access')
        click('[data-window="8"]')
        click('#close-access')
        check('顶部设置入口与关闭恢复点击', clear_layer())
        click('#open-settings')
        cli('press', 'Escape')
        # Chromium 优先用第一次 Escape 退出全屏，第二次才关闭仍打开的设置。
        wait('!document.fullscreenElement')
        check('Escape 退出全屏后按钮文案同步', 'document.querySelector("#fullscreen span").textContent==="全屏显示"')
        cli('press', 'Escape')
        wait('!document.querySelector("#access-dialog").open')
        check('继续按 Escape 关闭设置并恢复主界面点击', clear_layer())
        fullscreen()
        click('#freeze')
        wait('!document.querySelector("#frozen-status").hidden')
        evaluate('window.__frozenValue=document.querySelector("#value-HR").textContent;window.__frameBefore=window.__frames;true')
        wait('window.__frames>window.__frameBefore+4')
        check('全屏冻结仍接收数据，读数保持', 'document.querySelector("#value-HR").textContent===window.__frozenValue')
        route('overview')
        check('冻结状态跨页面保持', 'document.querySelector("#freeze").getAttribute("aria-pressed")==="true"')
        click('#freeze')
        check('全屏恢复显示', 'document.querySelector("#frozen-status").hidden')
        route('ecg')
        wait('!document.querySelector("#export-csv").disabled')
        evaluate('window.__blobFactory=URL.createObjectURL;window.__csv=null;URL.createObjectURL=b=>{b.text().then(t=>window.__csv=t);return window.__blobFactory(b);};true')
        click('#export-csv')
        wait('window.__csv!==null')
        check('全屏 CSV 导出包含本会话 MOCK 数据', 'window.__csv.includes("timestamp,channel")&&window.__csv.includes("MOCK")')
        evaluate('URL.createObjectURL=window.__blobFactory;delete window.__csv;true')
        route('overview')
        picture('fullscreen-connected')
        click('#open-settings')
        click('#fullscreen')
        wait('!document.fullscreenElement')
        check('退出全屏清除模态层并继续导航', clear_layer() + ' && ' + layout())
        # 常见大屏、笔记本及手机横竖屏：每个页面逐一检查导航命中与横向溢出。
        for width, height in ((2560, 1440), (1920, 1080), (1600, 900), (1366, 768), (1280, 720), (390, 844), (844, 390)):
            cli('set', 'viewport', str(width), str(height))
            for key in ('overview', 'ecg', 'spo2', 'resp', 'nibp', 'temp'):
                route(key)
                check(f'{width}×{height} {key} 布局及导航命中', layout())
            picture(f'temp-{width}x{height}')
            if width > 900:
                fullscreen()
                for key in ('overview', 'ecg', 'spo2', 'resp', 'nibp', 'temp'):
                    route(key)
                    check(f'{width}×{height} 全屏 {key} 布局及导航命中',
                          '!!document.fullscreenElement && ' + clear_layer() + ' && ' + layout())
                click('#open-settings')
                click('#fullscreen')
                wait('!document.fullscreenElement')
        cli('set', 'viewport', '1920', '1080')
        route('overview')
        for index in range(3):
            fullscreen()
            check(f'重复全屏第 {index+1} 次无弹窗残留', clear_layer())
            route('nibp')
            click('#open-settings')
            click('#fullscreen')
            wait('!document.fullscreenElement')
            route('overview')
        check('整轮导航和全屏切换未创建重复 WebSocket', 'window.__sockets===1 && window.__frames>30')
        click('#open-settings')
        click('#disconnect')
        wait('document.querySelector("#value-HR").textContent==="--"')
        check('断开连接清空实时读数且主界面可操作', clear_layer())
        connect()
        check('断开后可重新连接', 'window.__sockets===2')
        # 权限拒绝仅在独立本地页面模拟；不修改线上服务或浏览器全局设置。
        if args.config:
            evaluate('window.__requestFullscreen=document.documentElement.requestFullscreen;document.documentElement.requestFullscreen=()=>Promise.reject(new Error("test denied"));true')
            click('#open-settings')
            click('#fullscreen')
            wait('document.querySelector("#access-dialog").open')
            wait('document.querySelector("#access-message").textContent.includes("浏览器未允许")')
            check('全屏权限拒绝提供持续提示并可关闭', '!document.fullscreenElement && !document.querySelector("#fullscreen").disabled')
            click('#close-access')
            evaluate('document.documentElement.requestFullscreen=window.__requestFullscreen;true')
        check('浏览器无未捕获异常或 Promise 拒绝', 'window.__errors===0')
        report['status'] = 'passed'
    except Exception as error:
        # 失败只记录断言名称，不持久化 CLI 原始输出、地址或凭据。
        report['status'] = 'failed'
        report['failure'] = str(error) if isinstance(error, AssertionError) else type(error).__name__
        picture('failure')
        raise
    finally:
        report['passed'] = len(checks)
        report['timestamp'] = time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
        (args.output / 'interaction-acceptance.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
        cli('close')


if __name__ == '__main__':
    main()
