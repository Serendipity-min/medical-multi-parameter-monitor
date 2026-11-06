"""FIELD01 隔离只订阅接收端；不打开串口、不发布MQTT、不改远端服务。"""
import argparse
import contextlib
import hashlib
import json
import os
from pathlib import Path
import secrets
import socket
import subprocess
import sys
import threading
import time
import urllib.request

ROOT = Path(__file__).resolve().parents[2]


def save(path, value):
    path.write_text(json.dumps(value, indent=2) + '\n', encoding='utf-8')


def free_port():
    with socket.socket() as sock:
        sock.bind(('127.0.0.1', 0))
        return sock.getsockname()[1]


class ProjectPrefix:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope['type'] in ('http', 'websocket') and scope['path'].startswith('/medical-monitor/'):
            scope = dict(scope, path=scope['path'][len('/medical-monitor'):],
                         root_path=scope.get('root_path', '') + '/medical-monitor')
        await self.app(scope, receive, send)


def backend():
    sys.path.insert(0, str(ROOT / 'cloud/backend'))
    from app.main import create_app
    import uvicorn
    uvicorn.run(ProjectPrefix(create_app()), host='127.0.0.1',
                port=int(os.environ['FIELD01_HTTP_PORT']), access_log=False)


def run(args):
    from b4_recovery import protected
    import paho.mqtt.client as mqtt
    from playwright.sync_api import sync_playwright

    out = args.output
    out.mkdir()
    protected(out, False)
    save(out / 'scope.json', {'node_profile': 'five', 'subscribe_only': True,
         'device_commands': 0, 'remote_service_changes': 0, 'duration_bound_s': 900})
    settings = json.loads(protected(args.credentials, False).read_text(encoding='utf-8-sig'))
    mqtt_port, http_port = free_port(), free_port()
    config = dict(host='127.0.0.1', port=mqtt_port, tls=False, username='mic-observer',
                  password=settings['roles']['mic-observer'], client_id='field01-backend-' + secrets.token_hex(6))
    save(out / 'mqtt-config-private.json', config)
    token = secrets.token_urlsafe(36)
    save(out / 'local-access-private.json', dict(view_token=token, http_port=http_port))
    (out / 'executed-receiver.py').write_bytes(Path(__file__).read_bytes())
    result = dict(status='NOT_READY', exit_code=1, node_profile='five',
                  hardware_operations=0, MQTT_publications=0, remote_service_changes=0)
    children = []
    client = None
    subscribed = threading.Event()
    counts = {'MQTT_received': 0, 'browser_snapshots': 0}
    browser_errors = []
    with contextlib.ExitStack() as stack:
        wire = stack.enter_context((out / 'MQTT-private.jsonl').open('x', encoding='utf-8'))
        snapshots = stack.enter_context((out / 'browser-snapshots-private.jsonl').open('x', encoding='utf-8'))
        dom_log = stack.enter_context((out / 'browser-display-private.jsonl').open('x', encoding='utf-8'))
        def child(command, name, **kw):
            log = stack.enter_context((out / (name + '-private.log')).open('xb'))
            p = subprocess.Popen(command, stdout=log, stderr=subprocess.STDOUT,
                                 creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0), **kw)
            children.append(p)
            return p
        try:
            tunnel = child(['ssh', '-o', 'BatchMode=yes', '-o', 'StrictHostKeyChecking=yes',
                '-o', 'ExitOnForwardFailure=yes', '-o', 'ConnectTimeout=10',
                '-o', 'ServerAliveInterval=15', '-o', 'ServerAliveCountMax=2', '-N',
                '-L', f'127.0.0.1:{mqtt_port}:127.0.0.1:18885', 'tencent-codex'], 'tunnel')
            until = time.monotonic() + 12
            while True:
                if tunnel.poll() is not None:
                    raise RuntimeError('FIELD01_TUNNEL_EXITED')
                try:
                    with socket.create_connection(('127.0.0.1', mqtt_port), timeout=.2):
                        break
                except OSError:
                    if time.monotonic() >= until:
                        raise TimeoutError('FIELD01_TUNNEL_NOT_READY')
                    time.sleep(.1)
            client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2,
                                 client_id='field01-observer-' + secrets.token_hex(6), reconnect_on_failure=False)
            client.username_pw_set(config['username'], config['password'])
            def connected(c, userdata, flags, reason, properties):
                if not reason.is_failure:
                    c.subscribe('mpm/v1/GW-B5-001/#', 1)
            def suback(c, userdata, mid, codes, properties):
                if codes and all(not x.is_failure for x in codes):
                    subscribed.set()
            def message(c, userdata, m):
                counts['MQTT_received'] += 1
                wire.write(json.dumps(dict(arrival_unix_ns=time.time_ns(), topic=m.topic,
                    qos=m.qos, retain=m.retain, payload_hex=bytes(m.payload).hex())) + '\n')
                wire.flush()
            client.on_connect, client.on_subscribe, client.on_message = connected, suback, message
            client.connect('127.0.0.1', mqtt_port, 15)
            client.loop_start()
            if not subscribed.wait(8):
                raise TimeoutError('FIELD01_SUBACK_NOT_READY')
            env = dict(os.environ, MPM_NODE_PROFILE='five', MONITOR_VIEW_TOKEN=token,
                MONITOR_ALLOWED_ORIGINS=f'http://127.0.0.1:{http_port}', MONITOR_GATEWAY_IDS='GW-B5-001',
                MONITOR_MQTT_CONFIG=str(out / 'mqtt-config-private.json'), MONITOR_WAVE_BATCH_DELIVERY='1',
                MONITOR_LOG_DIR=str(out / 'backend-events'), MONITOR_WEB_DIR=str(ROOT / 'cloud/web/dist'),
                FIELD01_HTTP_PORT=str(http_port))
            web = child([sys.executable, '-X', 'utf8', str(Path(__file__)), '--backend'], 'backend', env=env)
            until = time.monotonic() + 12
            while True:
                if web.poll() is not None:
                    raise RuntimeError('FIELD01_BACKEND_EXITED')
                try:
                    with urllib.request.urlopen(f'http://127.0.0.1:{http_port}/medical-monitor/api/health', timeout=1) as response:
                        health = json.load(response)
                    if health['mqtt_connected']:
                        break
                except (OSError, TimeoutError):
                    pass
                if time.monotonic() >= until:
                    raise TimeoutError('FIELD01_BACKEND_NOT_READY')
                time.sleep(.1)
            with sync_playwright() as playwright:
                browser = playwright.chromium.launch(headless=True)
                try:
                    page = browser.new_page(viewport={'width': 1440, 'height': 1000})
                    page.on('pageerror', lambda e: browser_errors.append(type(e).__name__))
                    def snapshot(payload):
                        data = json.loads(payload)
                        if data.get('type') == 'snapshot':
                            if data['node_profile'] != 'five' or set(data['nodes']) != {'NODE-A', 'NODE-B', 'NODE-D', 'NODE-E'}:
                                raise ValueError('FIELD01_BROWSER_PROFILE_MISMATCH')
                            counts['browser_snapshots'] += 1
                            snapshots.write(json.dumps(dict(arrival_unix_ns=time.time_ns(), snapshot=data)) + '\n')
                            snapshots.flush()
                    page.on('websocket', lambda ws: ws.on('framereceived', snapshot))
                    page.goto(f'http://127.0.0.1:{http_port}/medical-monitor/')
                    page.locator('#open-access').click()
                    # 沿用台架网关身份，只增加本页选项；不替换或注入遥测。
                    page.locator('#gateway-select').evaluate("el => el.add(new Option('FIELD01 GW-B5-001', 'GW-B5-001'))")
                    page.locator('#gateway-select').select_option('GW-B5-001')
                    page.locator('#view-token').fill(token)
                    page.locator('#access-form button[type=submit]').click()
                    until = time.monotonic() + 8
                    while not counts['browser_snapshots'] and time.monotonic() < until:
                        page.wait_for_timeout(100)
                    if not counts['browser_snapshots'] or browser_errors:
                        raise RuntimeError('FIELD01_BROWSER_NOT_READY')
                    ready = dict(node_profile='five', MQTT_SUBACK=True, backend_health=health,
                                 browser_real_websocket=True, http_port=http_port, **counts)
                    save(out / 'READY.json', ready)
                    print(json.dumps(dict(event='FIELD01_RECEIVER_READY', node_profile='five',
                                          hardware_operations=0, MQTT_publications=0)), flush=True)
                    began = time.monotonic()
                    next_display = 0
                    last_nibp_state = None
                    screenshot_index = 0
                    while time.monotonic() - began < (2 if args.check else 900) and not (out / 'STOP_RECEIVER').exists():
                        if any(p.poll() is not None for p in children) or browser_errors:
                            raise RuntimeError('FIELD01_RECEIVER_PROCESS_OR_BROWSER_FAILED')
                        if time.monotonic() >= next_display:
                            display = page.evaluate("""() => Object.fromEntries(
                              ['pressure-sys','pressure-dia','state-NIBP','source-NIBP',
                               'value-TEMP','source-TEMP','node-e','node-d'].map(id =>
                               [id, document.getElementById(id)?.textContent ?? null]))""")
                            dom_log.write(json.dumps(dict(arrival_unix_ns=time.time_ns(), display=display)) + '\n')
                            dom_log.flush()
                            if display['state-NIBP'] != last_nibp_state:
                                last_nibp_state = display['state-NIBP']
                                page.screenshot(path=str(out / f'browser-nibp-state-{screenshot_index}.png'), full_page=True)
                                screenshot_index += 1
                            next_display = time.monotonic() + 1
                        page.wait_for_timeout(100)
                    page.screenshot(path=str(out / 'browser-final.png'), full_page=True)
                    result.update(status='RECEIVER_READINESS_PASS_NOT_DEVICE_ACCEPTANCE' if args.check else 'RECEIVER_STOPPED_REQUIRES_DATA_REVIEW', exit_code=0)
                finally:
                    browser.close()
        except (Exception, KeyboardInterrupt) as error:
            save(out / 'failure-private.json', dict(type=type(error).__name__, detail=str(error)))
            result['error_type'] = type(error).__name__
        finally:
            if client:
                client.disconnect()
                client.loop_stop()
            for p in reversed(children):
                p.terminate()
                try:
                    p.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    p.kill()
                    p.wait(timeout=3)
            result.update(counts, browser_errors=browser_errors, all_own_children_exited=all(p.poll() is not None for p in children),
                          tool_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest())
            save(out / 'receipt-public.json', result)
    print(json.dumps(result), flush=True)
    return result['exit_code']


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--backend', action='store_true')
    parser.add_argument('--output', type=Path)
    parser.add_argument('--credentials', type=Path)
    parser.add_argument('--check', action='store_true')
    arguments = parser.parse_args()
    if arguments.backend:
        backend()
    else:
        if not arguments.output or not arguments.credentials:
            parser.error('--output and --credentials required')
        raise SystemExit(run(arguments))
