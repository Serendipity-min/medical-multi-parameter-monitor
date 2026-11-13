"""B5 G0定向只读云核验；原始配置只写受限EFS，不建立MQTT业务会话。"""
import base64
import ctypes
import hashlib
import inspect
import json
import os
from pathlib import Path
import subprocess
import uuid
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[2]
PRIVATE = Path('E:/medical-monitor-node-b-precan-private/20261023')


def remote_snapshot():
    import base64, hashlib, json, os, re, shlex, socket, ssl, subprocess
    from datetime import datetime, timezone
    from pathlib import Path
    raw, files, errors = {}, {}, []
    def run(args):
        p = subprocess.run(args, capture_output=True, text=True, timeout=12)
        return p.returncode, p.stdout, p.stderr
    def capture(path):
        p = Path(path)
        if p.is_file():
            b = p.read_bytes()
            files[str(p)] = {'sha256': hashlib.sha256(b).hexdigest(), 'bytes': len(b),
                            'mode': oct(p.stat().st_mode & 0o777), 'base64': base64.b64encode(b).decode()}
            return b.decode(errors='replace')
        return ''
    def envparse(text):
        result = {}
        for line in text.splitlines():
            if line.strip() and not line.lstrip().startswith('#') and '=' in line:
                k, v = line.split('=', 1)
                try: result[k.strip()] = ' '.join(shlex.split(v))
                except ValueError: result[k.strip()] = v.strip()
        return result
    units, pids = {}, {}
    for name in ('medical-monitor-mqtt.service', 'medical-monitor.service', 'p6-ai.service', 'nginx.service'):
        rc, out, err = run(['systemctl', 'show', name, '-p', 'MainPID', '-p', 'ActiveState', '-p', 'FragmentPath', '-p', 'ExecStart', '-p', 'EnvironmentFiles'])
        raw[name] = {'exit_code': rc, 'stdout': out, 'stderr': err}
        vals = dict(x.split('=', 1) for x in out.splitlines() if '=' in x)
        pid = int(vals.get('MainPID', '0'))
        pids[name] = pid
        units[name] = {'active': vals.get('ActiveState'), 'pid': pid}
        capture(vals.get('FragmentPath', ''))
        if pid:
            proc = Path('/proc') / str(pid)
            raw[name]['cmdline_base64'] = base64.b64encode((proc / 'cmdline').read_bytes()).decode()
            raw[name]['environment_base64'] = base64.b64encode((proc / 'environ').read_bytes()).decode()
            raw[name]['cwd'] = os.readlink(proc / 'cwd')
    broker_processes = []
    for proc in Path('/proc').iterdir():
        if not proc.name.isdigit(): continue
        try:
            if (proc / 'comm').read_text().strip() != 'mosquitto': continue
            args = (proc / 'cmdline').read_bytes().decode().split('\0')
            parent = int(re.search(r'^PPid:\s*(\d+)', (proc / 'status').read_text(), re.M)[1])
            conf = args[args.index('-c') + 1] if '-c' in args else None
            broker_processes.append({'pid': int(proc.name), 'parent': parent, 'config': conf,
                                     'business_child': parent == pids['medical-monitor-mqtt.service']})
        except (FileNotFoundError, PermissionError): continue
    raw['brokers'] = broker_processes
    def conf_tree(path, seen=None):
        seen = set() if seen is None else seen
        if path in seen: return []
        seen.add(path)
        text = capture(path); rows = []
        for line in text.splitlines():
            a = line.strip().split(maxsplit=1)
            if len(a) != 2 or a[0].startswith('#'): continue
            rows.append(tuple(a))
            if a[0] == 'include_dir':
                for p in sorted(Path(a[1]).glob('*.conf')): rows.extend(conf_tree(str(p), seen))
        return rows
    broker = []
    for proc in broker_processes:
        rows = conf_tree(proc['config']) if proc['config'] else []
        directives = {}
        for k, v in rows: directives.setdefault(k, []).append(v)
        acls = []
        for path in directives.get('acl_file', []):
            text = capture(path); role = None; entries = []
            for line in text.splitlines():
                a = line.strip().split()
                if not a or a[0].startswith('#'): continue
                if a[0] == 'user': role = a[1]
                elif a[0] in ('topic', 'pattern'):
                    entries.append({'role': role, 'kind': a[0], 'permission': a[1] if len(a)>2 else 'readwrite', 'topic': a[-1]})
            acls.extend(entries)
        users = []
        for path in directives.get('password_file', []):
            p = Path(path)
            if p.is_file():
                blob = p.read_bytes()
                # 只保留账号名与整文件指纹，不读取/输出密码散列正文。
                users.extend(x.split(':', 1)[0] for x in blob.decode().splitlines() if ':' in x)
                raw['password_file_metadata'] = {'path': path, 'sha256': hashlib.sha256(blob).hexdigest(), 'mode': oct(p.stat().st_mode & 0o777)}
        certs = []
        for path in directives.get('certfile', []):
            capture(path)
            rc, out, err = run(['openssl', 'x509', '-in', path, '-noout', '-dates', '-fingerprint', '-sha256'])
            certs.append({'exit_code': rc, 'stdout': out, 'stderr': err})
        # 不读取keyfile；文件存在不等于持有测试账号或有效ACL已实测。
        broker.append({'process': proc, 'directives': directives, 'acl': acls, 'users': users, 'certificates': certs})
    raw['broker_configuration'] = broker
    backend_env = envparse(capture('/opt/medical-monitor/config/backend.env'))
    proc = Path('/proc') / str(pids['medical-monitor.service'])
    if pids['medical-monitor.service']:
        actualenv = dict(x.split('=', 1) for x in (proc/'environ').read_bytes().decode().split('\0') if '=' in x)
        backend_env.update({k: v for k, v in actualenv.items() if k.startswith('MONITOR_')})
    mqtt_config = {}
    cfg = backend_env.get('MONITOR_MQTT_CONFIG')
    if cfg: mqtt_config = json.loads(capture(cfg))
    raw['backend_effective_env'] = backend_env
    raw['backend_mqtt_config'] = mqtt_config
    source_checks = {}
    if pids['medical-monitor.service']:
        cwd = Path(raw['medical-monitor.service']['cwd'])
        for suffix in ('app/main.py', 'app/hub.py', 'app/models.py', 'app/mqtt_adapter.py'):
            text = capture(cwd/suffix)
            source_checks[suffix] = {'present': bool(text), 'sha256': hashlib.sha256(text.encode()).hexdigest()}
    rc, out, err = run(['nginx', '-T'])
    nginx_rc = rc
    raw['nginx_dump'] = {'exit_code': rc, 'stdout': out, 'stderr': err}
    for path in re.findall(r'^# configuration file (.+):$', out, re.M): capture(path)
    listeners = {}
    for port in (8883, 8884, 18765, 18766, 18775):
        rc, text, err = run(['ss', '-H', '-ltnp', 'sport', '=', ':'+str(port)])
        raw['listener_'+str(port)] = {'exit_code': rc, 'stdout': text, 'stderr': err}
        listeners[str(port)] = bool(text.strip()) if rc == 0 else None
    tls = {'business_session': False}
    if mqtt_config.get('host'):
        try:
            context = ssl.create_default_context(cafile=mqtt_config.get('ca_file') or None)
            # 与运行配置同一SNI/信任链，只做TLS握手，无MQTT CONNECT/PUBLISH。
            with socket.create_connection(('127.0.0.1', int(mqtt_config.get('port', 8883))), timeout=6) as sock:
                with context.wrap_socket(sock, server_hostname=mqtt_config['host']) as conn:
                    cert = conn.getpeercert()
                    tls.update(verified=True, protocol=conn.version(), not_before=cert.get('notBefore'), not_after=cert.get('notAfter'),
                               certificate_sha256=hashlib.sha256(conn.getpeercert(binary_form=True)).hexdigest())
        except Exception as e: tls.update(verified=False, failure_type=type(e).__name__)
    raw['tls'] = tls
    # 当前Broker已有客户端日志可能包含业务/地址，只存EFS原件；不当作身份冲突排除的充分证明。
    rc, out, err = run(['journalctl', '-u', 'medical-monitor-mqtt.service', '-n', '120', '--no-pager', '-o', 'cat'])
    raw['broker_recent_journal'] = {'exit_code': rc, 'stdout': out, 'stderr': err}
    public_broker = []
    for b in broker:
        d=b['directives']; acl=b['acl']
        public_broker.append({'business_child': b['process']['business_child'], 'listeners': d.get('listener', []),
            'allow_anonymous': d.get('allow_anonymous', []), 'per_listener_settings': d.get('per_listener_settings', []),
            'acl_file_referenced': bool(d.get('acl_file')), 'plugin_referenced': bool(d.get('plugin') or d.get('auth_plugin')),
            'password_file_referenced': bool(d.get('password_file')), 'test_username_exists': 'b5-gateway' in b['users'],
            'test_acl_rows': [x for x in acl if x['role']=='b5-gateway'],
            'global_acl_rows_count': sum(x['role'] is None for x in acl),
            'pattern_rows_count': sum(x['kind']=='pattern' for x in acl),
            'acl_role_count': len(set(x['role'] for x in acl)), 'test_client_id_seen_recently': 'b5-c-isolated' in raw['broker_recent_journal']['stdout']})
    public = {'utc': datetime.now(timezone.utc).isoformat(), 'units': units, 'listeners': listeners, 'broker': public_broker,
        'tls': tls, 'backend_gateway_allowlist_includes_test': 'GW-B5-001' in backend_env.get('MONITOR_GATEWAY_IDS','').split(','),
        'backend_gateway_allowlist_explicit': 'MONITOR_GATEWAY_IDS' in backend_env,
        'backend_view_token_configured': bool(backend_env.get('MONITOR_VIEW_TOKEN')),
        'backend_mqtt_gateway_topics_include_test': 'GW-B5-001' in json.dumps(mqtt_config.get('topics', mqtt_config.get('topic',''))),
        'backend_source_files': source_checks, 'nginx_dump_exit_code': nginx_rc,
        'physical_board_access': False, 'cloud_mutations': 0, 'mqtt_connects': 0, 'mqtt_publishes': 0,
        'raw_file_count': len(files), 'errors': errors}
    # listener原文可能含地址；公开只给端口与协议，不输出原始listener字符串。
    for b in public_broker: b['listeners'] = [x.split()[0] for x in b['listeners']]
    return {'private': raw, 'files': files, 'public': public}


def new_private():
    name = 'b5-g0-' + datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ') + '-' + uuid.uuid4().hex[:8]
    out = PRIVATE / name
    out.mkdir(exist_ok=False)
    p = subprocess.run(['cipher', '/E', str(out)], capture_output=True)
    if p.returncode: raise ValueError('EFS_SETUP_FAILED')
    sid = subprocess.check_output(['whoami', '/user', '/fo', 'csv', '/nh'], text=True).strip().split(',')[-1].strip('"')
    p = subprocess.run(['icacls', str(out), '/inheritance:r', '/grant:r', '*'+sid+':(OI)(CI)F', '*S-1-5-18:(OI)(CI)F'], capture_output=True)
    if p.returncode: raise ValueError('ACL_SETUP_FAILED')
    return out


def write_private(path, blob):
    if not path.parent.resolve().is_relative_to(PRIVATE.resolve()): raise ValueError('PRIVATE_ROOT')
    with path.open('xb') as f: f.write(blob)
    attrs = ctypes.windll.kernel32.GetFileAttributesW(str(path))
    if not attrs & 0x4000: raise ValueError('EFS_REQUIRED')


def main():
    out = new_private()
    source = inspect.getsource(remote_snapshot) + '\nimport json\nprint(json.dumps(remote_snapshot()))\n'
    write_private(out/'executed-remote.py', source.encode())
    try:
        p = subprocess.run(['ssh', '-o', 'BatchMode=yes', '-o', 'StrictHostKeyChecking=yes', '-o', 'ConnectTimeout=12',
                            'tencent-codex', 'sudo -n python3 -'], input=source.encode(), capture_output=True, timeout=100)
        write_private(out/'ssh-stdout-private.json', p.stdout)
        write_private(out/'ssh-stderr-private.bin', p.stderr)
        result = json.loads(p.stdout)['public'] if p.returncode == 0 else {'status':'SSH_OR_REMOTE_FAILURE'}
        code = p.returncode
    except subprocess.TimeoutExpired as e:
        write_private(out/'timeout-stdout-private.bin', e.stdout or b'')
        write_private(out/'timeout-stderr-private.bin', e.stderr or b'')
        result, code = {'status':'TIMEOUT'}, 124
    except (ValueError, KeyError):
        result, code = {'status':'PRIVATE_RESPONSE_PARSE_FAILED'}, 1
    result.update(ssh_exit_code=code, tool_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest())
    result['private_stdout_sha256'] = hashlib.sha256((out/'ssh-stdout-private.json').read_bytes()).hexdigest() if (out/'ssh-stdout-private.json').exists() else None
    write_private(out/'summary-private.json', json.dumps(result, indent=2).encode())
    pointer=ROOT/'node-b/build/b5-g0-private-pointer.json'
    pointer.write_text(json.dumps({'base':str(out)}))
    evidence=ROOT/'node-b/evidence/B5-G0'; evidence.mkdir(exist_ok=True)
    (evidence/('cloud-readonly-'+out.name+'.json')).write_text(json.dumps(result, indent=2)+'\n')
    print(json.dumps(result)); return code


if __name__ == '__main__': raise SystemExit(main())
