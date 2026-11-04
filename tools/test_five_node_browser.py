"""本机浏览器显示回归；WebSocket 边界注入明确合成快照，不连接云或设备。"""
from pathlib import Path
import atexit
import functools
import http.server
import threading
import copy
import json
import time
from playwright.sync_api import sync_playwright, expect

ROOT = Path(__file__).resolve().parents[1]
out = ROOT / 'node-b/build/five-node-m1/browser'
out.mkdir(parents=True, exist_ok=True)
webroot = ROOT / 'node-b/build/five-node-m1/webroot'
server = http.server.ThreadingHTTPServer(('127.0.0.1', 0), functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(webroot)))
threading.Thread(target=server.serve_forever, daemon=True).start()
atexit.register(server.server_close)
atexit.register(server.shutdown)
url = f'http://127.0.0.1:{server.server_port}/medical-monitor/'
stamp = int(time.time() * 1000)


def signal(node, stream, value, unit):
    return dict(node_id=node, stream=stream, value=value, unit=unit, timestamp=stamp, seq=1,
                session_id='synthetic-five-node-browser', validity='VALID', source='MOCK',
                synthetic=True, samples=[], sample_rate=0)


snapshot = dict(type='snapshot', schema_version=1, node_profile='five', gateway_id='GW-DEV-001',
                gateway_state='ONLINE', broker_connected=True, server_time=stamp,
                nodes={f'NODE-{n}': 'ONLINE' for n in ('A', 'B', 'D', 'E')},
                streams=[signal('NODE-D', 'TEMP', 30.2, 'degC'), signal('NODE-E', 'NIBP', [120, 80], 'mmHg'),
                         signal('NODE-B', 'HR', 60, 'bpm')], replay=None, event=None)
with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page(viewport={'width': 1440, 'height': 1000})
    errors = []
    page.on('pageerror', lambda e: errors.append(str(e)))
    page.add_init_script('''window.WebSocket = class {
      constructor() { window.testSocket=this; setTimeout(()=>this.onopen?.(),0); }
      send() {} close() {}
    };
    window.emitSnapshot = data => window.testSocket.onmessage({data:JSON.stringify(data)});''')
    page.goto(url)
    page.wait_for_load_state('networkidle')
    page.locator('#open-access').click()
    page.locator('#view-token').fill('synthetic-browser-fixture')
    page.locator('#access-form button[type=submit]').click()
    page.wait_for_function('Boolean(window.testSocket && window.testSocket.onmessage)')
    page.evaluate('data=>window.emitSnapshot(data)', snapshot)
    expect(page.locator('#node-d')).to_have_text('Node-D · ONLINE')
    expect(page.locator('#node-e')).to_have_text('Node-E · ONLINE')
    expect(page.locator('#value-TEMP')).to_have_text('30.2')
    expect(page.locator('#source-TEMP')).to_have_text('NODE-D')
    expect(page.locator('#source-NIBP')).to_have_text('NODE-E')
    page.screenshot(path=str(out / 'five-node-overview.png'), full_page=True)
    for route, node in (('temp', 'NODE-D'), ('nibp', 'NODE-E')):
        page.goto(url + f'#/{route}')
        expect(page.locator('#detail-node')).to_contain_text(node)
        expect(page.locator('#detail-source')).to_have_text(node)
        page.screenshot(path=str(out / f'five-node-{route}.png'), full_page=True)
    expired = copy.deepcopy(snapshot)
    expired['nodes']['NODE-D'] = 'OFFLINE'
    for item in expired['streams'][:2]:
        item['validity'] = 'OFFLINE' if item['stream'] == 'TEMP' else 'STALE'
        item['value'] = None
    page.evaluate('data=>window.emitSnapshot(data)', expired)
    expect(page.locator('#pressure-sys')).to_have_text('--')
    expect(page.locator('#node-d')).to_have_text('Node-D · OFFLINE')
    expect(page.locator('#node-b')).to_have_text('Node-B · ONLINE')
    page.screenshot(path=str(out / 'five-node-expired.png'), full_page=True)
    assert not errors, errors
    browser.close()
(out / 'receipt.json').write_text(json.dumps(dict(status='PASS', scope='BROWSER_SYNTHETIC_WEBSOCKET_BOUNDARY',
    page_errors=errors, checks=['D_E_status', 'D_temperature', 'E_NIBP', 'detail_sources', 'expired_NIBP_hidden', 'D_offline_B_online']), indent=2), encoding='utf-8')
print('FIVE_NODE_BROWSER_PASS')
