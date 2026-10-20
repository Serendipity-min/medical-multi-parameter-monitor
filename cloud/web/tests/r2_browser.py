"""七页、独立鉴权、真实90秒时效及桌面/手机截图；真实模型调用固定0。"""
import json,time,urllib.request
from ui_browser import cli,js,wait,check,checks,OUT
BASE='https://127.0.0.1:18767/medical-monitor/'
VIEW='r2-local-view-'+'x'*32
AI='r2-local-ai-'+'x'*32


def control(**values):
    request=urllib.request.Request('http://127.0.0.1:18765/fixture/control',data=json.dumps(values).encode(),headers={'Content-Type':'application/json'})
    with urllib.request.urlopen(request) as response:return json.load(response)


def route(name):
    cli('click',f'[data-route={name}]');wait(f"location.hash === '#/{name}'")


def ask(question):
    js("document.querySelector('.ai-access').open=true")
    cli('fill','#ai-token',AI);cli('fill','#ai-question',question);cli('click','#ai-send')
    wait("document.querySelector('#ai-status').textContent.includes('回答完成')")
    js("document.querySelector('.ai-access').open=false")


def shot(name):
    js("document.title='H3-R2 本地HTTPS · MOCK · 非正式发布';if(!document.querySelector('#r2-test-label')){const d=document.createElement('div');d.id='r2-test-label';d.textContent='本地 HTTPS/WSS 合成协议验证 · Node-B OFFLINE · 真实模型调用 0 · 非正式发布';d.style='position:fixed;bottom:0;left:0;right:0;z-index:99999;background:#142d42;color:#fff;padding:5px;font-size:12px;pointer-events:none';document.body.appendChild(d)}")
    cli('screenshot',str(OUT/name))


def main():
    OUT.mkdir(parents=True,exist_ok=True)
    # 仅本任务的短期自签名证书允许忽略信任错误，不影响正式浏览器或生产TLS配置。
    cli('--ignore-https-errors','open',BASE+'#/ai');cli('set','viewport','1920','1080');cli('snapshot','-i')
    wait("document.querySelector('#ai-token') !== null")
    cli('select','#gateway-select','GW-C-001');cli('click','#open-access');cli('fill','#view-token',VIEW);cli('click','#access-form button[type=submit]')
    wait("document.querySelector('#connection').textContent === '监护通道已连接'")
    check('https_secure_context',"location.protocol==='https:' && window.isSecureContext")
    check('node_b_offline',"document.querySelector('#node-b').textContent.includes('OFFLINE')")
    for name in ('overview','temp','ecg','spo2','resp','nibp','ai'):
        route(name);check('route_'+name,"document.querySelector('[aria-current=page]').dataset.route===location.hash.slice(2)")
    check('synthetic_source_visible',"document.querySelector('#ai-source').textContent.includes('MOCK') || document.querySelector('#ai-source').textContent.includes('模拟')")
    check('unmeasured_nibp_hidden',"document.querySelector('[data-channel=NIBP] strong').textContent.includes('--')")
    completed=control(phase='measured')['completion_timestamp'];started=time.monotonic()
    wait("document.querySelector('[data-channel=NIBP] strong').textContent.includes('123')")
    ask('现在血压多少')
    # MOCK服务应显式显示MOCK；不能要求它冒充DOUBAO模式的NOT_CALLED展示文案。
    check('deterministic_nibp_mock_no_real_model',"document.querySelector('#ai-mode').textContent.includes('MOCK') && document.querySelector('.ai-turn:last-child .ai-answer').textContent.includes('123')")
    shot('ai-desktop-valid.png')
    # 切换七页不创建额外订阅；AI单次SnapshotReader请求退出后订阅应回到1。
    route('nibp');wait("document.querySelector('#pressure-sys').textContent==='123'");shot('nibp-valid.png');route('ai')
    cli('set','viewport','390','844')
    check('mobile_no_horizontal_overflow',"document.documentElement.scrollWidth<=innerWidth")
    shot('ai-mobile-valid.png');cli('set','viewport','1920','1080')
    js("document.querySelector('.ai-access').open=true")
    cli('fill','#ai-token','invalid-local-token');cli('fill','#ai-question','鉴权检查');cli('click','#ai-send')
    wait("document.querySelector('#ai-status').textContent.includes('验证失败')")
    check('monitor_survives_ai_auth_failure',"document.querySelector('#connection').textContent==='监护通道已连接'")
    cli('fill','#ai-token',AI);js("document.querySelector('.ai-access').open=false")
    ask('久坐后有哪些一般健康提示')
    check('general_explanation_is_mock',"document.querySelector('#ai-mode').textContent.includes('MOCK')")
    control(probe=False);wait("document.querySelector('[data-channel=SpO2] strong').textContent.includes('--')")
    check('invalid_spo2_hidden',"document.querySelector('[data-channel=PR] strong').textContent.includes('--')")
    control(probe=True)
    # 等待的是同一测量真实经过90秒；新seq持续到达，不能用重收时间续期。
    wait("document.querySelector('[data-channel=NIBP] strong').textContent.includes('--')",timeout=max(5,105-(time.monotonic()-started)))
    elapsed=time.monotonic()-started
    assert elapsed>=89,'NIBP expired before the 90-second boundary'
    ask('现在血压多少')
    check('expired_ai_has_no_current_value',"document.querySelector('.ai-turn:last-child .ai-answer').textContent.includes('没有可用当前读数') && !document.querySelector('.ai-turn:last-child .ai-answer').textContent.includes('123')")
    shot('ai-desktop-expired.png')
    control(phase='measured');wait("document.querySelector('[data-channel=NIBP] strong').textContent.includes('123')")
    control(phase='aborted');wait("document.querySelector('[data-channel=NIBP] strong').textContent.includes('--')")
    check('aborted_measurement_does_not_revive_old_value',"document.querySelector('[data-channel=NIBP] strong').textContent.includes('--')")
    check('node_b_still_offline',"document.querySelector('#node-b').textContent.includes('OFFLINE')")
    cli('reload');wait("document.querySelector('#ai-token') !== null")
    check('refresh_clears_credentials',"document.querySelector('#ai-token').value==='' && document.querySelector('#connection').textContent==='未连接'")
    result={'exit_code':0,'checks':checks,'nibp_actual_elapsed_s':round(elapsed,3),'completion_timestamp':completed,
        'source':'LOCAL_SOFTWARE_MOCK_OVER_REAL_BACKEND_WSS_AND_AI_APP','real_model_calls':0,'physical_nibp_source':'NOT_USED',
        'https':'LOCAL_SELF_SIGNED_CERTIFICATE_ONLY','production_published':False}
    (OUT/'result.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    print(json.dumps({'exit_code':0,'checks':len(checks),'nibp_actual_elapsed_s':round(elapsed,3),'real_model_calls':0}))


if __name__=='__main__':main()
