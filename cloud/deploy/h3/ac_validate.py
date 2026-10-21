"""AC-1固定软件回归清单：只编译/本机测试，永不调用串口、下载器或云端写操作。"""
from datetime import datetime,timezone
import hashlib,json,os,shutil,subprocess,sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[3]
OUT=ROOT/'gateway/physical_can/evidence/h3-ac/regression'


def main():
    OUT.mkdir(parents=True,exist_ok=False)
    head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
    environment={k:v for k,v in os.environ.items() if not k.startswith('ARK_')}
    environment.update(PYTHONUTF8='1',NODE_A_TEST_EVIDENCE=str(OUT/'node-a'),
      H3_WIRE_EVIDENCE=str(OUT/'wire'),P6_MODEL_MODE='MOCK',P6_MQTT_MODE='DISABLED',
      P6_REAL_ACCOUNT_APPROVED='0',P6_REAL_BUDGET_APPROVED='0',
      P6_BROWSER_EVIDENCE='gateway/physical_can/evidence/h3-ac/browser')
    environment.pop('MONITOR_MQTT_CONFIG',None)
    plan=[
      ('node-a-host',[sys.executable,'node-a/tests/run_host.py','--phase','ac1-frozen']),
      ('gateway-host',[sys.executable,'gateway/physical_can/build.py','--host','--irq','--evidence-dir',str(OUT/'gateway-host')]),
      ('gateway-rx-order',[sys.executable,'gateway/physical_can/build.py','--host','--irq','--rx-order','--evidence-dir',str(OUT/'gateway-rx-order')]),
      ('gateway-peer-cycle',[sys.executable,'gateway/physical_can/build.py','--host','--irq','--peer-cycle','--evidence-dir',str(OUT/'gateway-peer-cycle')]),
      ('p5-42',[sys.executable,'gateway/mqtt/tests/run_p5_host_tests.py']),
      ('p5-46',[sys.executable,'gateway/mqtt/tests/run_p5_host_tests.py','--network-irq','--fresh-sntp']),
      ('paired-python',[sys.executable,'-m','pytest','cloud/backend/tests','cloud/ai/tests','gateway/physical_can/tests','-q']),
      ('C-isolated-ARM',[sys.executable,'gateway/physical_can/build.py','--irq','--isolated','--fresh-sntp','--persistent-config','--evidence-dir',str(OUT/'C-isolated')]),
      ('C-formal-ARM',[sys.executable,'gateway/physical_can/build.py','--irq','--fresh-sntp','--persistent-config','--evidence-dir',str(OUT/'C-formal')]),
      ('node-a-keil',['D:/keil/UV4/UV4.exe','-r',str(ROOT/'node-a/STM32F407_HOSPITAL/USER/STM32F407_Template.uvprojx'),'-o',str(OUT/'node-a-keil-build.log')]),
      ('node-a-fromelf',['D:/keil/ARM/ARMCC/bin/fromelf.exe','--bin','--output',str(ROOT/'node-a/build/h3-ac-node-a.bin'),str(ROOT/'node-a/STM32F407_HOSPITAL/OBJ/STM32F407_Template.axf')]),
      ('web-tests',['D:/Node/npm.cmd','--prefix','cloud/web','test']),
      ('web-build',['D:/Node/npm.cmd','--prefix','cloud/web','run','build']),
      ('browser',[sys.executable,'cloud/web/tests/run_r2_browser.py']),
    ]
    results=[]
    for label,command in plan:
        started=datetime.now(timezone.utc).isoformat();record={'label':label,'command':command,'source_commit':head,
          'started_utc':started,'hardware_accessed':False,'real_AI_calls':0}
        kwargs={}
        if os.name=='nt':
            # Keil是GUI程序，也以隐藏窗口执行纯Rebuild；没有下载参数，工程用户钩子已核对禁用。
            startup=subprocess.STARTUPINFO();startup.dwFlags|=subprocess.STARTF_USESHOWWINDOW;startup.wShowWindow=0
            kwargs={'startupinfo':startup,'creationflags':subprocess.CREATE_NO_WINDOW}
        try:
            with (OUT/(label+'.log')).open('xb') as log:
                r=subprocess.run(command,cwd=ROOT,env=environment,stdout=log,stderr=log,timeout=360,**kwargs)
            record['exit_code']=r.returncode
        except subprocess.TimeoutExpired:record.update(exit_code=124,failure='TIMEOUT')
        except OSError as exc:record.update(exit_code=125,failure=type(exc).__name__)
        record['finished_utc']=datetime.now(timezone.utc).isoformat();results.append(record)
        with (OUT/(label+'-exit.json')).open('x') as f:json.dump(record,f,indent=2)
        if label.startswith('p5-') and record['exit_code']==0:
            # 普通P5入口写入忽略的build目录；复制本次完整原始日志和结果，不带二进制入库。
            parent=ROOT/'gateway/mqtt/build/p5-tests';last=sorted(p for p in parent.iterdir() if p.is_dir())[-1]
            target=OUT/label;target.mkdir()
            for p in last.iterdir():
                if p.suffix in ('.log','.json'):shutil.copyfile(p,target/p.name)
        print(json.dumps({'label':label,'exit_code':record['exit_code']}),flush=True)
        if record['exit_code']:break
    summary={'source_commit':head,'jobs':results,'expected_jobs':len(plan),
      'exit_code':next((r['exit_code'] for r in results if r['exit_code']),0) if len(results)==len(plan) or any(r['exit_code'] for r in results) else 1,
      'hardware_accessed':False,'server_mutations':False,'real_AI_calls':0}
    with (OUT/'validation-result.json').open('x') as f:json.dump(summary,f,indent=2)
    return summary['exit_code']


if __name__=='__main__':raise SystemExit(main())
