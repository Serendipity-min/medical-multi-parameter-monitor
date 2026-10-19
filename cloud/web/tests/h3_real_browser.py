"""经SSH loopback转发验证真实豆包页面；服务端Key不离开服务器，截图隐去问答正文。"""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import urllib.request

os.environ['P6_BROWSER_SESSION']='h3-real-isolated'
os.environ['P6_BROWSER_EVIDENCE']='cloud/evidence/h3/real-browser'
from ui_browser import ROOT,OUT,URL,cli,js,wait,check,checks


def main():
    OUT.mkdir(parents=True,exist_ok=True)
    procs=[]
    results=[]
    script=r'''
import pathlib,shlex,json
data={}
for line in pathlib.Path('/var/lib/medical-monitor-p6/h3-20261019/ai.env').read_text().splitlines():
 k,v=line.split('=',1)
 if k in ('P6_AI_TOKEN','P6_MONITOR_VIEW_TOKEN'):data[k]=shlex.split(v)[0]
print(json.dumps(data))
'''
    r=subprocess.run(['ssh','tencent-codex','sudo -n python3 -'],input=script,text=True,capture_output=True,timeout=20)
    if r.returncode:raise RuntimeError('EPHEMERAL_TEST_AUTH_NOT_AVAILABLE')
    auth=json.loads(r.stdout)
    with tempfile.TemporaryFile() as tunnel_log,(OUT/'vite.log').open('wb') as vite_log:
        try:
            procs.append(subprocess.Popen(['ssh','-N','-o','ExitOnForwardFailure=yes','-o','ServerAliveInterval=15',
                '-L','127.0.0.1:18765:127.0.0.1:18775','-L','127.0.0.1:18766:127.0.0.1:18776','tencent-codex'],stdout=tunnel_log,stderr=tunnel_log))
            procs.append(subprocess.Popen(['node',str(ROOT/'cloud/web/node_modules/vite/bin/vite.js'),str(ROOT/'cloud/web'),
                '--host','127.0.0.1','--port','18767','--strictPort'],cwd=ROOT,stdout=vite_log,stderr=vite_log))
            end=time.monotonic()+20
            while time.monotonic()<end:
                try:
                    urllib.request.urlopen('http://127.0.0.1:18766/health',timeout=1).close()
                    urllib.request.urlopen(URL,timeout=1).close();break
                except Exception:time.sleep(.1)
            cli('set','viewport','1920','1080');cli('open',URL+'#/ai');cli('reload')
            wait("document.querySelector('#ai-token')!==null")
            cli('click','#open-access');cli('select','#gateway-select','GW-C-001')
            # 临时应用令牌只经stdin进入本任务浏览器内存，不作为CLI参数或截图/日志内容。
            js("document.querySelector('#view-token').value="+json.dumps(auth['P6_MONITOR_VIEW_TOKEN'])+";document.querySelector('#access-form').requestSubmit()")
            wait("document.querySelector('#connection').textContent==='监护通道已连接'")
            js("document.querySelector('.ai-access').open=true;document.querySelector('#ai-token').value="+json.dumps(auth['P6_AI_TOKEN']))
            js("""window.__h3=[];const original=window.fetch;window.fetch=async(...args)=>{const r=await original(...args);if(String(args[0]).includes('/ai/api/v1/text')){const d=await r.clone().json();window.__h3.push({http:r.status,real_model:d.real_model,answer_kind:d.answer_kind,model_evidence:d.model_evidence,fact_digest:d.fact_digest,facts:d.facts?.map(f=>({stream:f.stream,node_id:f.node_id,validity:f.validity,source:f.source,synthetic:f.synthetic})),answer_present:typeof d.answer==='string'&&d.answer.length>0});}return r;}""")
            for label,question,real in [('current','当前血氧多少',False),('general','久坐办公有哪些一般健康提示',True),('absent_b','当前心率多少',False)]:
                cli('fill','#ai-question',question);cli('click','#ai-send')
                wait("document.querySelector('#ai-status').textContent.includes('回答完成')")
                receipt=js('window.__h3.at(-1)');receipt['case']=label
                assert receipt['http']==200 and (receipt['real_model']=='REAL_REQUEST_USED')==real
                assert all(f['validity']=='OFFLINE' for f in receipt['facts'] if f['node_id']=='NODE-B')
                results.append(receipt)
            check('node_b_fact_offline',"document.querySelector('[data-channel=HR] strong').textContent.includes('--')")
            check('test_source_visible',"document.querySelector('#ai-source').textContent.includes('模拟')")
            check('voice_default_off',"!document.querySelector('#ai-voice').checked")
            js("document.querySelector('.ai-access').open=false;for(const el of document.querySelectorAll('.ai-turn>h3,.ai-answer'))el.textContent='问答正文按合同不存档';const tag=document.createElement('div');tag.textContent='H3隔离验证 · 真实豆包API / 非个人软件合成快照 · 非硬件E2E';tag.style.cssText='position:fixed;top:0;left:0;z-index:99999;background:#fff4cc;color:#302600;padding:6px 20px';document.body.append(tag)")
            for width,height,name in [(1920,1080,'desktop'),(390,844,'mobile')]:
                cli('set','viewport',str(width),str(height))
                check(name+'_no_horizontal_overflow','document.documentElement.scrollWidth<=innerWidth')
                cli('screenshot',str(OUT/(name+'.png')))
            report={'exit_code':0,'checks':checks,'cases':results,'source':'MOCK_NONPERSONAL_SOFTWARE_FIXTURE',
                    'hardware_e2e':'NOT_TESTED','real_calls':sum(r['real_model']=='REAL_REQUEST_USED' for r in results),
                    'route':'Vite full prefix → SSH loopback → actual FastAPI → Doubao'}
            (OUT/'result.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
            print('REAL_BROWSER_PASS',len(checks),'checks',report['real_calls'],'real model call',flush=True)
        finally:
            # 每个资源由本脚本创建；清理不触及正式服务或用户浏览器。
            cli('close')
            for p in reversed(procs):
                if p.poll() is None:p.terminate();p.wait(10)


if __name__=='__main__':main()
