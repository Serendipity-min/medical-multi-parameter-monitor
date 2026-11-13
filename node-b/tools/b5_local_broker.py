"""进程自有loopback TLS Mosquitto；只使用合成账户和临时端口，不安装系统服务。"""
from pathlib import Path
from datetime import datetime,timedelta,timezone
import ipaddress
import socket
import subprocess
import sys
import time
from cryptography import x509
from cryptography.hazmat.primitives import hashes,serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID


def free_port():
    with socket.socket() as s:
        s.bind(('127.0.0.1',0));return s.getsockname()[1]


class Broker:
    def __init__(self,runtime:Path,out:Path):
        self.out=out.resolve();self.out.mkdir(parents=True)
        self.port=free_port();self.password='synthetic-b5-local-only-password'
        def linux(p):
            p=p.resolve();return '/mnt/'+p.drive[0].lower()+p.as_posix()[2:]
        self.prefix=['wsl','-d','HERA-C3','--','env','LD_LIBRARY_PATH='+linux(runtime/'usr/lib/x86_64-linux-gnu')+':'+linux(runtime/'lib/x86_64-linux-gnu')]
        key=rsa.generate_private_key(public_exponent=65537,key_size=2048)
        subject=x509.Name([x509.NameAttribute(NameOID.COMMON_NAME,'B5 loopback test only')])
        now=datetime.now(timezone.utc)
        cert=(x509.CertificateBuilder().subject_name(subject).issuer_name(subject).public_key(key.public_key())
              .serial_number(x509.random_serial_number()).not_valid_before(now-timedelta(minutes=1)).not_valid_after(now+timedelta(days=1))
              .add_extension(x509.BasicConstraints(ca=True,path_length=None),critical=True)
              .add_extension(x509.SubjectAlternativeName([x509.DNSName('localhost'),x509.IPAddress(ipaddress.ip_address('127.0.0.1'))]),critical=False)
              .sign(key,hashes.SHA256()))
        self.cert=self.out/'loopback.crt';self.key=self.out/'loopback.key'
        self.cert.write_bytes(cert.public_bytes(serialization.Encoding.PEM))
        self.key.write_bytes(key.private_bytes(serialization.Encoding.PEM,serialization.PrivateFormat.TraditionalOpenSSL,serialization.NoEncryption()))
        passwords=self.out/'synthetic.passwd'
        for i,user in enumerate(('b5-gateway','b5-reader','b5-audit')):
            subprocess.run([*self.prefix,linux(runtime/'usr/bin/mosquitto_passwd'),'-b',*(['-c'] if not i else []),linux(passwords),user,self.password],check=True,capture_output=True)
        acl=self.out/'synthetic.acl'
        acl.write_text('user b5-gateway\ntopic write mpm/v1/GW-B5-001/#\nuser b5-reader\ntopic read mpm/v1/GW-B5-001/#\nuser b5-audit\ntopic read #\n',encoding='utf-8')
        config=self.out/'mosquitto.conf'
        config.write_text(f'user root\nlistener {self.port} 127.0.0.1\nallow_anonymous false\npersistence false\npassword_file {linux(passwords)}\nacl_file {linux(acl)}\ncafile {linux(self.cert)}\ncertfile {linux(self.cert)}\nkeyfile {linux(self.key)}\ntls_version tlsv1.2\nlog_dest stdout\n',encoding='utf-8')
        self.log=(self.out/'broker.log').open('w',encoding='utf-8')
        # launcher持有专属进程；关闭stdin就终止并wait，禁止遗留后台Broker/监听端口。
        launcher='import subprocess,sys; p=subprocess.Popen(sys.argv[1:]); print("OWNED_BROKER_PID",p.pid,flush=True); sys.stdin.readline(); p.terminate(); p.wait(timeout=5)'
        self.process=subprocess.Popen([*self.prefix,'python3','-u','-c',launcher,linux(runtime/'usr/sbin/mosquitto'),'-c',linux(config)],stdin=subprocess.PIPE,stdout=self.log,stderr=subprocess.STDOUT,text=True)
        try:
            for _ in range(100):
                if self.process.poll() is not None:raise RuntimeError('LOCAL_BROKER_START_FAILED')
                try:
                    with socket.create_connection(('127.0.0.1',self.port),timeout=.1):break
                except OSError:time.sleep(.1)
            else:raise TimeoutError('LOCAL_BROKER_NOT_READY')
        except BaseException:
            self.close();raise

    def close(self):
        if self.process.poll() is None:self.process.communicate('\n',timeout=10)
        self.log.close()
