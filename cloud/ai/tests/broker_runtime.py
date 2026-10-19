"""进程自有 Mosquitto 夹具：loopback、独立账户/ACL、临时端口与有界清理。"""
from pathlib import Path
import socket
import subprocess
import sys
import time


class BrokerRuntime:
    def __init__(self, runtime: Path, directory: Path):
        self.directory = directory.resolve(); self.directory.mkdir(parents=True, exist_ok=True)
        self.runtime = runtime.resolve()
        self.windows = sys.platform == 'win32'
        with socket.socket() as probe:
            probe.bind(('127.0.0.1', 0)); self.port = probe.getsockname()[1]
        def linux(path):
            return '/mnt/' + path.drive[0].lower() + path.as_posix()[2:] if self.windows else str(path)
        self.path = linux
        prefix = ['wsl', '-d', 'HERA-C3', '--'] if self.windows else []
        env = ['env', 'LD_LIBRARY_PATH=' + linux(self.runtime / 'usr/lib/x86_64-linux-gnu')]
        passwords = self.directory / 'synthetic.passwd'
        self.password = 'synthetic-p6-offline-password'
        for index, user in enumerate(['synthetic-ai', 'synthetic-gateway', 'synthetic-user']):
            subprocess.run(prefix + env + [linux(self.runtime / 'usr/bin/mosquitto_passwd'), '-b'] + (['-c'] if not index else []) + [linux(passwords), user, self.password], check=True, capture_output=True)
        acl = self.directory / 'synthetic.acl'
        acl.write_text('user synthetic-ai\ntopic write mpm/v1/GW-C-001/voice/reply\n'
                       'user synthetic-gateway\ntopic read mpm/v1/GW-C-001/voice/reply\n'
                       'user synthetic-user\ntopic readwrite mpm/v1/GW-C-001/#\n', encoding='utf-8')
        config = self.directory / 'mosquitto.conf'
        config.write_text(f'listener {self.port} 127.0.0.1\nallow_anonymous false\npersistence false\npassword_file {linux(passwords)}\nacl_file {linux(acl)}\nlog_dest stdout\n', encoding='utf-8')
        self.log = (self.directory / 'broker.log').open('w', encoding='utf-8')
        # Linux 子进程由专属 launcher 持有；父端关闭 stdin 即 terminate/wait，不残留 WSL 服务。
        launcher = 'import subprocess,sys; p=subprocess.Popen(sys.argv[1:]); print("BROKER_PID",p.pid,flush=True); sys.stdin.readline(); p.terminate(); p.wait(timeout=5)'
        self.process = subprocess.Popen(prefix + env + ['python3', '-u', '-c', launcher, linux(self.runtime / 'usr/sbin/mosquitto'), '-c', linux(config)],
                                        stdin=subprocess.PIPE, stdout=self.log, stderr=subprocess.STDOUT, text=True)
        try:
            for _ in range(100):
                if self.process.poll() is not None: raise RuntimeError('ISOLATED_BROKER_START')
                try:
                    with socket.create_connection(('127.0.0.1', self.port), timeout=.1): break
                except OSError: time.sleep(.1)
            else: raise TimeoutError('ISOLATED_BROKER_READY')
        except BaseException:
            self.close(); raise

    def close(self):
        if self.process.poll() is None:
            self.process.communicate('\n', timeout=10)
        self.log.close()
