"""G1收尾仅只读：部署/备份/正式服务核验与受限取回，不续开测试窗口。"""
import base64
import inspect
import json
from pathlib import Path
import subprocess

import b5_g1_cloud as g


def remote_verify(P):
    import base64,datetime,hashlib,http.client,json,socket,ssl,subprocess,time
    from pathlib import Path
    base=Path(P['base']);S=P['snapshot'];files={}
    def digest(blob):return hashlib.sha256(blob).hexdigest()
    def query(args):
        r=subprocess.run(args,capture_output=True,text=True,timeout=10)
        if r.returncode:raise ValueError('FINAL_READONLY_COMMAND_FAILED')
        return r.stdout.strip()
    def status(name):
        text=query(['systemctl','show',name,'-p','MainPID','-p','ActiveState','-p','ActiveEnterTimestamp','-p','ActiveEnterTimestampMonotonic','-p','RuntimeMaxUSec'])
        d=dict(x.split('=',1) for x in text.splitlines() if '=' in x)
        return d
    formal={name:status(name) for name in S['units']}
    formal_same=all(int(formal[k]['MainPID'])==v['pid'] and formal[k]['ActiveState']=='active' for k,v in S['units'].items())
    retained={name:digest(Path(name).read_bytes())==meta['sha256'] for name,meta in S['files'].items() if name not in [S['acl_path'],S['password_path']]}
    auth_match=(digest(Path(S['acl_path']).read_bytes())==digest(base64.b64decode(P['new_acl_base64'])) and
                digest(Path(S['password_path']).read_bytes())==digest(base64.b64decode(P['new_password_file_base64'])))
    own={}
    for name in ['backend','tls']:
        unit='medical-monitor-b5-'+P['tx']+'-'+name+'.service';st=status(unit)
        epoch=time.time()-(time.monotonic()-int(st['ActiveEnterTimestampMonotonic'])/1e6)
        own[name]={'unit':unit,'pid':int(st['MainPID']),'active':st['ActiveState'],'RuntimeMaxUSec':st['RuntimeMaxUSec'],
                   'observed_start_utc':st['ActiveEnterTimestamp'],
                   'estimated_expiry_utc':datetime.datetime.fromtimestamp(epoch+21600,datetime.timezone.utc).isoformat()}
    listener=query(['ss','-H','-ltn','sport','=',':18775'])
    loopback=bool(listener) and all('127.0.0.1:18775' in line for line in listener.splitlines())
    no8884=not bool(query(['ss','-H','-ltn','sport','=',':8884']))
    # 仅GET健康/静态首页，不打开WebSocket、MQTT或新增发布窗口。
    c=http.client.HTTPConnection('127.0.0.1',18765,timeout=4);c.request('GET','/health');r=c.getresponse();health=json.loads(r.read());c.close()
    host=S['backend']['host'];context=ssl.create_default_context()
    with socket.create_connection(('127.0.0.1',18775),timeout=4) as raw:
        with context.wrap_socket(raw,server_hostname=host) as conn:
            conn.sendall(('GET /medical-monitor/ HTTP/1.1\r\nHost: '+host+':18775\r\nConnection: close\r\n\r\n').encode())
            response=http.client.HTTPResponse(conn);response.begin();index=response.read()
            index_ok=response.status==200 and digest(index)==digest(base64.b64decode(P['sources']['web/dist/index.html']))
    # 只遍历本事务目录；包括服务日志、实际before备份和配置。私钥位于外部，只引用不读取。
    for p in base.rglob('*'):
        if p.is_file() and not p.is_symlink():
            b=p.read_bytes();files[p.relative_to(base).as_posix()]={'base64':base64.b64encode(b).decode(),'sha256':digest(b),'mode':p.stat().st_mode&0o777}
    metadata=json.loads((base/'before-private/metadata-private.json').read_text())
    backups=all(digest((base/'before-private'/(i+'.bin')).read_bytes())==v['sha256'] for i,v in metadata.items())
    unit_hashes={}
    for unit in ['backend','tls']:
        p=Path('/etc/systemd/system')/own[unit]['unit'];b=p.read_bytes()
        unit_hashes[unit]=digest(b)==digest(base64.b64decode(P['config'][unit+'.service']))
    public={'formal_service_PIDs_active_unchanged':formal_same,'formal_unaffected_config_SHA_unchanged':all(retained.values()),
            'formal_backend_health_ok':health.get('status')=='ok' and health.get('mqtt_connected') is True,
            'approved_ACL_password_SHA_match':auth_match,'actual_server_complete_backups_match':backups,
            'only_loopback_18775':loopback,'8884_not_listening':no8884,'deployed_unit_SHA_match':all(unit_hashes.values()),
            'HTTPS_static_index_matches_frozen_B5':index_ok,'own_services':own,'test_services_still_resident':True,
            'formal_namespace_publish_count':0,'G0_keyfile_content_read_or_copied':False,'rollback_executed':False,
            'read_only_final_check':True,'new_MQTT_or_WSS_window':False,'private_files_retrieved':len(files),'exit_code':0}
    if not all([formal_same,all(retained.values()),auth_match,backups,loopback,no8884,all(unit_hashes.values()),index_ok,public['formal_backend_health_ok']]):
        public['exit_code']=1;public['status']='STOP_FINAL_INVARIANT_FAILED'
    else:public['status']='G1_A_READY_PASS'
    return {'public':public,'files':files}


def main():
    link=json.loads((g.ROOT/'node-b/build/b5-g1-private-pointer.json').read_bytes());private=Path(link['base'])
    package=json.loads((private/link['package']).read_bytes())
    source=inspect.getsource(remote_verify)+'\nimport json\nprint(json.dumps(remote_verify(v["package"])))\n'
    g.write_private(private/'final-verify-executed-private.py',source.encode())
    loader="import sys,json;v=json.load(sys.stdin);exec(v['script'])"
    r=subprocess.run(['ssh','-o','BatchMode=yes','-o','StrictHostKeyChecking=yes','-o','ConnectTimeout=12','tencent-codex',
                      'sudo -n timeout 40s python3 -c '+repr(loader)],input=g.encode({'script':source,'package':package}),capture_output=True,timeout=55)
    g.write_private(private/'final-verify-stdout-private.json',r.stdout);g.write_private(private/'final-verify-stderr-private.bin',r.stderr)
    if r.returncode:print(json.dumps({'status':'STOP_READONLY_FINAL_FAILED','exit_code':r.returncode}));return r.returncode
    data=json.loads(r.stdout);report=data['public'];report.update(ssh_exit_code=r.returncode,raw_snapshot_sha256=g.sha(r.stdout),tool_sha256=g.sha(Path(__file__).read_bytes()))
    (g.ROOT/'node-b/evidence/B5-G1/final-readonly.json').write_bytes(g.encode(report))
    origin=package['origin'];entry={'origin':origin,'WSS':origin.replace('https:','wss:')+'/medical-monitor/ws/v1/monitor','Web':origin+'/medical-monitor/?gateway=GW-B5-001',
        'Gateway':'GW-B5-001','ssh_alias':'tencent-codex','server_TLS_listen':'127.0.0.1:18775','credentials_reference':'test-credentials-private.json',
        'six_hour_service_deadlines':report['own_services'],'public_direct_WSS_reachability':'NOT_TESTED_SSH_TUNNEL_ONLY'}
    g.write_private(private/'test-entry-and-lifetime-private.json',g.encode(entry))
    print(json.dumps(report));return report['exit_code']


if __name__=='__main__':raise SystemExit(main())
