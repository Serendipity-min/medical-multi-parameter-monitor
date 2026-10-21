"""正式进程/二进制/静态树的收尾只读指纹；不读取cmdline、environ或凭据正文。"""
import inspect,json,subprocess
from pathlib import Path


def snapshot():
    import hashlib,json,os,subprocess
    from datetime import datetime,timezone
    from pathlib import Path
    def query(args):return subprocess.check_output(args,text=True).strip()
    def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
    def process(pid):
        p=Path('/proc')/str(pid);exe=os.readlink(p/'exe')
        return {'pid':int(pid),'cwd':os.readlink(p/'cwd'),'executable':exe,'executable_sha256':sha(p/'exe')}
    units={}
    for unit in ('medical-monitor.service','medical-monitor-mqtt.service','p6-ai.service','nginx.service'):
        pid=query(['systemctl','show',unit,'-p','MainPID','--value'])
        fragment=Path(query(['systemctl','show',unit,'-p','FragmentPath','--value']))
        units[unit]={**process(pid),'state':query(['systemctl','show',unit,'-p','ActiveState','--value']),
          'unit_sha256':sha(fragment),'unit_mode':oct(fragment.stat().st_mode&0o777)}
    # Broker业务单元是Python包装器；额外冻结其实际子进程，避免误把默认mosquitto.service当业务身份。
    parent=units['medical-monitor-mqtt.service']['pid'];children=[]
    for line in query(['ps','-eo','pid=,ppid=,comm=']).splitlines():
        columns=line.split()
        if len(columns)==3 and int(columns[1])==parent:children.append({**process(columns[0]),'name':columns[2]})
    trees={}
    for label,base,suffix in (
      ('backend_app',Path(units['medical-monitor.service']['cwd'])/'app','.py'),
      ('ai_app',Path(units['p6-ai.service']['cwd'])/'cloud/ai','.py'),
      ('web_dist',Path('/opt/medical-monitor/current/web/dist'),None)):
        # 只读取应用源码/静态发布树，不遍历venv、日志、用户数据或秘密配置目录。
        entries={p.relative_to(base).as_posix():sha(p) for p in base.rglob('*')
          if p.is_file() and (suffix is None or p.suffix==suffix) and '__pycache__' not in p.parts}
        trees[label]={'files':entries,'file_count':len(entries),
          'tree_sha256':hashlib.sha256(json.dumps(entries,sort_keys=True).encode()).hexdigest()}
    ports={}
    for port in (8883,8884,18775):
        text=query(['ss','-H','-ltn','sport','=',':'+str(port)]);ports[str(port)]=bool(text)
    return {'exit_code':0,'recorded_utc':datetime.now(timezone.utc).isoformat(),'units':units,
      'actual_broker_children':children,'deployed_trees':trees,'listeners':ports,
      'server_mutations':False,'real_AI_calls':0,'physical_board_access':False}


def main():
    root=Path(__file__).resolve().parents[3]
    code=inspect.getsource(snapshot)+'\nimport json\nprint(json.dumps(snapshot()))\n'
    r=subprocess.run(['ssh','tencent-codex','sudo -n python3 -'],input=code,text=True,capture_output=True,timeout=40)
    try:data=json.loads(r.stdout)
    except ValueError:data={'exit_code':r.returncode or 1,'failure_code':'READONLY_RUNTIME_OUTPUT_SUPPRESSED'}
    data['ssh_exit_code']=r.returncode
    with (root/'gateway/physical_can/evidence/h3-ac/AC0-runtime-readonly.json').open('x') as f:json.dump(data,f,indent=2)
    print(json.dumps({'exit_code':data['exit_code'],'ssh_exit_code':r.returncode,'server_mutations':False,
      'tree_file_counts':{k:v['file_count'] for k,v in data.get('deployed_trees',{}).items()}}))
    return data['exit_code']


if __name__=='__main__':raise SystemExit(main())
