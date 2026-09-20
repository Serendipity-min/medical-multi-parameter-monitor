"""从既有证书的本机路径更新 Broker 副本；不下载、不输出证书或私钥。"""

import json
from pathlib import Path
import shutil
import ssl
import subprocess


# 只同步本机既有证书并通知 Broker 重载；不负责申请证书，也不从远端下载文件。
def main():
    root = Path('/opt/medical-monitor/broker')
    config = json.loads((root / 'certificate-source.json').read_text())
    source = Path(config['certificate'])
    target = root / 'tls/server-chain.pem'
    if source.read_bytes() == target.read_bytes():
        return
    # SSLContext 仅用于检查证书与密钥配对；私钥内容不进入日志或返回值。
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.load_cert_chain(str(source), config['private_key'])
    expiry = subprocess.run(
        ['openssl', 'x509', '-checkend', '86400', '-noout', '-in', str(source)], capture_output=True
    )
    if expiry.returncode:
        raise RuntimeError('Source certificate expires too soon')
    for original, name in [
        (source, 'server-chain.pem'),
        (Path(config['private_key']), 'server-key.pem'),
    ]:
        temporary = root / 'tls' / (name + '.next')
        shutil.copyfile(original, temporary)
        temporary.chmod(0o640)
        shutil.chown(temporary, group='mosquitto')
        temporary.replace(root / 'tls' / name)
    subprocess.run(
        ['systemctl', 'kill', '--kill-who=main', '-s', 'HUP', 'medical-monitor-mqtt'],
        check=True,
        capture_output=True,
    )
    print('Broker certificate refreshed')


if __name__ == '__main__':
    main()
