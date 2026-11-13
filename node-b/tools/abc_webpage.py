"""独立无头浏览器观察真实WSS网页；只填写访问令牌，不注入测量数据。"""
import argparse
import json
from pathlib import Path
import time

from playwright.sync_api import sync_playwright
import b5_g3_contract as g


def observe(job):
    inputs=g.load(job/'runtime-inputs-private.json');bundle=g.load(inputs['bundle'])
    package=g.load(bundle['cloud_package']['path']);credentials=g.load(bundle['cloud_credentials']['path'])
    host=package['snapshot']['backend']['host'];out=job/'browser-observations-private.jsonl'
    ids=['value-HR','state-HR','value-RR','state-RR','value-TEMP','state-TEMP','pressure-sys',
         'pressure-dia','state-NIBP','bp-updated','value-SpO2','state-SpO2','value-PR','state-PR',
         'gateway','node-a','node-b','connection','received-at','source-banner','source-note',
         'quality-ECG','quality-RESP','quality-PPG']
    result={'exit_code':1,'sensor_data_injected':False,'TLS_errors_ignored':False,'browser_context':'TASK_ONLY'}
    stage='BROWSER_LAUNCH'
    try:
        with sync_playwright() as pw:
            browser=pw.chromium.launch(headless=True,args=['--no-proxy-server','--host-resolver-rules=MAP '+host+' 127.0.0.1'])
            try:
                # 上下文显式全绕过，避免系统代理覆盖启动参数；不修改系统代理或用户浏览器。
                stage='BROWSER_CONTEXT';context=browser.new_context(viewport={'width':1440,'height':1050},proxy={'server':'http://127.0.0.1:9','bypass':'*'})
                stage='PAGE_AND_AUTH'
                page=context.new_page();page.goto(package['origin']+'/medical-monitor/?gateway=GW-B5-001',wait_until='domcontentloaded',timeout=20000)
                page.locator('#open-access').click();page.locator('#view-token').fill(credentials['view_token'])
                page.locator('#access-form').evaluate('(form)=>form.requestSubmit()')
                page.get_by_text('监护通道已连接',exact=False).wait_for(timeout=15000)
                print(json.dumps({'event':'ACTUAL_BROWSER_WSS_CONNECTED'}),flush=True)
                started=time.monotonic();saved=0;last_shot=0;nibp_shot=False
                with out.open('a',encoding='utf8') as log:
                    while time.monotonic()-started<460 and not (job/'STOP_BROWSER').exists():
                        values=page.evaluate('(ids)=>Object.fromEntries(ids.map(id=>[id,document.getElementById(id)?.textContent ?? null]))',ids)
                        row={'monotonic':time.monotonic(),'UTC_ms':int(time.time()*1000),'visible':values,'DOM_read_only':True,'sensor_data_injected':False}
                        nibp=values['pressure-sys'] not in (None,'','--','—','–')
                        if saved==0 or nibp and not nibp_shot or time.monotonic()-last_shot>=60:
                            name='browser-live-'+str(saved)+'.png';page.screenshot(path=str(job/name),full_page=True)
                            row.update(screenshot_file=name,screenshot_sha256=g.sha((job/name).read_bytes()));last_shot=time.monotonic()
                            if nibp:nibp_shot=True
                        log.write(json.dumps(row,ensure_ascii=False)+'\n');log.flush();saved+=1
                        if (job/'capture/joint-receipt-private.json').exists():break
                        page.wait_for_timeout(1000)
                result.update(exit_code=0,observations=saved,NIBP_screenshot_taken=nibp_shot)
            finally:browser.close()
    except Exception as error:
        g.save(job/('browser-error-'+str(time.time_ns())+'-private.json'),{'stage':stage,'error':str(error)})
        result.update(error_type=type(error).__name__,stage=stage,error_sha256=g.sha(str(error).encode()))
    g.save(job/'browser-receipt-public.json',result);print(json.dumps(result),flush=True);return result['exit_code']


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--job',type=Path,required=True);a=p.parse_args()
    g.private.protected(a.job,False);raise SystemExit(observe(a.job))
