"""本轮拥有的loopback进程/短期TLS证书/浏览器；不使用真实模型和服务器配置。"""
from datetime import datetime,timedelta,timezone
import hashlib,ipaddress,json,os,socket,ssl,subprocess,sys,time,urllib.request,uuid
from pathlib import Path
from cryptography import x509
from cryptography.hazmat.primitives import hashes,serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID

ROOT=Path(__file__).resolve().parents[3]
# 复测写入新合同目录；P6浏览器子进程使用同一个路径，不覆盖R2截图/日志。
OUT=ROOT/os.environ.get('P6_BROWSER_EVIDENCE','cloud/evidence/h3-r2/browser')


def main():
    OUT.mkdir(parents=True,exist_ok=True)
    for port in (18765,18766,18767):
        with socket.socket() as test:
            try:test.bind(('127.0.0.1',port))
            except OSError:raise RuntimeError('OWNED_TEST_PORT_OCCUPIED_'+str(port))
    private=Path('E:/medical-monitor-h3-private')/('r2-local-tls-'+uuid.uuid4().hex);private.mkdir()
    key_path,cert_path=private/'key.pem',private/'cert.pem'
    key=rsa.generate_private_key(public_exponent=65537,key_size=2048)
    now=datetime.now(timezone.utc);name=x509.Name([x509.NameAttribute(NameOID.COMMON_NAME,'localhost')])
    cert=x509.CertificateBuilder().subject_name(name).issuer_name(name).public_key(key.public_key()).serial_number(x509.random_serial_number()).not_valid_before(now-timedelta(minutes=1)).not_valid_after(now+timedelta(days=1)).add_extension(x509.SubjectAlternativeName([x509.DNSName('localhost'),x509.IPAddress(ipaddress.ip_address('127.0.0.1'))]),critical=False).sign(key,hashes.SHA256())
    key_path.write_bytes(key.private_bytes(serialization.Encoding.PEM,serialization.PrivateFormat.PKCS8,serialization.NoEncryption()))
    cert_path.write_bytes(cert.public_bytes(serialization.Encoding.PEM))
    env={k:v for k,v in os.environ.items() if not k.startswith('ARK_')}
    env.update(PYTHONUTF8='1',P6_BROWSER_SESSION='h3-r2-local-'+uuid.uuid4().hex[:8],P6_BROWSER_EVIDENCE=str(OUT.relative_to(ROOT)),
        MONITOR_TESTING='1',MONITOR_VIEW_TOKEN='r2-local-view-'+'x'*32,MONITOR_GATEWAY_IDS='GW-C-001',
        MONITOR_ALLOWED_ORIGINS='https://127.0.0.1:18767',P6_AI_TOKEN='r2-local-ai-'+'x'*32,
        P6_MODEL_MODE='MOCK',P6_SNAPSHOT_MODE='MONITOR',P6_MONITOR_VIEW_TOKEN='r2-local-view-'+'x'*32,
        P6_MONITOR_WS_URL='ws://127.0.0.1:18765/ws/v1/monitor',P6_MONITOR_ORIGIN='https://127.0.0.1:18767',
        P6_ALLOWED_ORIGINS='https://127.0.0.1:18767',P6_MQTT_MODE='DISABLED',P6_REAL_ACCOUNT_APPROVED='0',P6_REAL_BUDGET_APPROVED='0')
    env.pop('MONITOR_MQTT_CONFIG',None)
    owned=[];logs=[];result={'exit_code':1,'real_model_calls':0,'production_mutations':False,'local_certificate_sha256':hashlib.sha256(cert.public_bytes(serialization.Encoding.DER)).hexdigest()}
    def start(label,module,port,tls=False):
        log=(OUT/(label+'.log')).open('wb');logs.append(log)
        command=[sys.executable,'-m','uvicorn',module,'--host','127.0.0.1','--port',str(port),'--no-access-log']
        if tls:command+=['--ssl-keyfile',str(key_path),'--ssl-certfile',str(cert_path)]
        if module.endswith('create_app'):command+=['--factory']
        p=subprocess.Popen(command,cwd=ROOT,env=env,stdout=log,stderr=log,creationflags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0);owned.append(p)
    try:
        start('backend','cloud.web.tests.r2_fixture:app',18765)
        start('ai','cloud.ai.app:create_app',18766)
        start('https','cloud.web.tests.r2_https_proxy:app',18767,True)
        for url in ('http://127.0.0.1:18765/fixture/state','http://127.0.0.1:18766/health','https://127.0.0.1:18767/medical-monitor/'):
            end=time.monotonic()+20
            while True:
                try:
                    with urllib.request.urlopen(url,context=ssl._create_unverified_context(),timeout=1) as response:
                        if response.status==200:break
                except Exception:
                    if time.monotonic()>end:raise RuntimeError('LOCAL_TEST_SERVICE_NOT_READY')
                    time.sleep(.1)
        with (OUT/'browser.log').open('wb') as log:
            r=subprocess.run([sys.executable,str(ROOT/'cloud/web/tests/r2_browser.py')],cwd=ROOT,env=env,stdout=log,stderr=log,timeout=210)
        result['exit_code']=r.returncode
    finally:
        subprocess.run(['D:/Node/node_global/node_modules/agent-browser/bin/agent-browser-win32-x64.exe','--session',env['P6_BROWSER_SESSION'],'close'],capture_output=True)
        for p in reversed(owned):
            if p.poll() is None:p.terminate();p.wait(10)
        for log in logs:log.close()
        result['owned_processes_stopped']=all(p.poll() is not None for p in owned)
        # 只删除本轮创建的两个TLS文件，不递归处理其他私有文件。
        key_path.unlink();cert_path.unlink();private.rmdir();result['owned_certificate_deleted']=True
        (OUT/'run-result.json').write_text(json.dumps(result,indent=2))
    print(json.dumps(result));return result['exit_code']


if __name__=='__main__':raise SystemExit(main())
