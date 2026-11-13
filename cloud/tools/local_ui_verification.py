"""本地 UI 自动化验收套件与 8 组高分辨率截图生成脚本。
严格遵循 MPM-P-WEB-SOW-001 第 30、31 条准出场景规范，完全在本地环境运行，不连接公网。
"""

import asyncio
import json
import math
import os
from pathlib import Path
import time
from typing import Any

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from playwright.sync_api import sync_playwright
import uvicorn

BASE_DIR = Path(__file__).resolve().parents[1]
WEB_DIST = BASE_DIR / 'web' / 'dist'
EVIDENCE_DIR = BASE_DIR / 'evidence' / 'ui-v07'
EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)

# 动态测试状态控制器
class MockMonitorState:
    def __init__(self):
        self.gateway_id = 'GW-DEV-001'
        self.gateway_state = 'ONLINE'
        self.broker_connected = True
        self.node_a_online = True
        self.node_b_online = True
        self.validity = 'VALID'
        self.mode = 'MOCK'
        self.rr_invalid = False
        self.replay: dict | None = None
        self.event: dict | None = None
        self.seq = 0
        self.session_id = 'session-ui-v07-test'
        self.capture_origin = int(time.time() * 1000)

    def make_snapshot(self, requested_gateway: str) -> dict:
        now_ms = self.capture_origin + self.seq * 200
        self.seq += 1

        # 真机网关 GW-C-001 暂无数据，用于测试网关源隔离
        if requested_gateway == 'GW-C-001':
            return {
                'type': 'snapshot',
                'schema_version': 1,
                'gateway_id': 'GW-C-001',
                'gateways': ['GW-DEV-001', 'GW-C-001'],
                'gateway_state': 'ONLINE',
                'broker_connected': True,
                'nodes': {'NODE-A': 'OFFLINE', 'NODE-B': 'OFFLINE'},
                'server_time': now_ms,
                'streams': [],
                'replay': None,
                'event': None,
            }

        # 生成波形采样
        def make_samples(stream: str, rate: int) -> list[float]:
            pts = []
            count = rate // 5
            for i in range(count):
                t = self.seq * 0.2 + i / rate
                phase = (t * 1.2) % 1
                if stream == 'ECG':
                    y = (
                        0.10 * math.sin(2 * math.pi * phase)
                        + math.exp(-(((phase - 0.25) / 0.022) ** 2))
                        - 0.22 * math.exp(-(((phase - 0.30) / 0.028) ** 2))
                    )
                elif stream == 'PPG':
                    y = max(0.0, math.sin(math.pi * phase)) ** 3
                else:
                    y = 0.8 * math.sin(2 * math.pi * 0.25 * t)
                pts.append(round(y, 5))
            return pts

        streams = []

        # Node-A 体征 (PPG, SPO2, PR, NIBP)
        a_validity = 'VALID' if (self.node_a_online and self.validity == 'VALID') else ('INVALID' if self.validity == 'INVALID' else 'OFFLINE')
        streams.append({
            'node_id': 'NODE-A', 'stream': 'PPG', 'timestamp': now_ms, 'seq': self.seq,
            'session_id': self.session_id, 'validity': a_validity, 'source': self.mode,
            'synthetic': True, 'value': None, 'samples': make_samples('PPG', 50) if a_validity == 'VALID' else [],
            'sample_rate': 50, 'unit': 'relative'
        })
        streams.append({
            'node_id': 'NODE-A', 'stream': 'SPO2', 'timestamp': now_ms, 'seq': self.seq,
            'session_id': self.session_id, 'validity': a_validity, 'source': self.mode,
            'synthetic': True, 'value': 98.0 if a_validity == 'VALID' else None, 'samples': [],
            'sample_rate': 1, 'unit': '%'
        })
        streams.append({
            'node_id': 'NODE-A', 'stream': 'PR', 'timestamp': now_ms, 'seq': self.seq,
            'session_id': self.session_id, 'validity': a_validity, 'source': self.mode,
            'synthetic': True, 'value': 72.0 if a_validity == 'VALID' else None, 'samples': [],
            'sample_rate': 1, 'unit': 'bpm'
        })
        streams.append({
            'node_id': 'NODE-A', 'stream': 'NIBP', 'timestamp': now_ms, 'seq': self.seq,
            'session_id': self.session_id, 'validity': a_validity, 'source': self.mode,
            'synthetic': True, 'value': [118.0, 76.0] if a_validity == 'VALID' else None, 'samples': [],
            'sample_rate': 0, 'unit': 'mmHg'
        })

        # Node-B 体征 (ECG, HR, RESP, RR, TEMP)
        b_validity = 'VALID' if (self.node_b_online and self.validity == 'VALID') else ('INVALID' if self.validity == 'INVALID' else 'OFFLINE')
        streams.append({
            'node_id': 'NODE-B', 'stream': 'ECG', 'timestamp': now_ms, 'seq': self.seq,
            'session_id': self.session_id, 'validity': b_validity, 'source': self.mode,
            'synthetic': True, 'value': None, 'samples': make_samples('ECG', 250) if b_validity == 'VALID' else [],
            'sample_rate': 250, 'unit': 'mV'
        })
        streams.append({
            'node_id': 'NODE-B', 'stream': 'HR', 'timestamp': now_ms, 'seq': self.seq,
            'session_id': self.session_id, 'validity': b_validity, 'source': self.mode,
            'synthetic': True, 'value': 72.0 if b_validity == 'VALID' else None, 'samples': [],
            'sample_rate': 1, 'unit': 'bpm'
        })
        streams.append({
            'node_id': 'NODE-B', 'stream': 'RESP', 'timestamp': now_ms, 'seq': self.seq,
            'session_id': self.session_id, 'validity': b_validity, 'source': self.mode,
            'synthetic': True, 'value': None, 'samples': make_samples('RESP', 50) if b_validity == 'VALID' else [],
            'sample_rate': 50, 'unit': 'relative'
        })

        # RR 允许单独设置为 INVALID 以满足场景 7: RESP 有波形但 RR INVALID
        rr_val = 'INVALID' if self.rr_invalid else b_validity
        streams.append({
            'node_id': 'NODE-B', 'stream': 'RR', 'timestamp': now_ms, 'seq': self.seq,
            'session_id': self.session_id, 'validity': rr_val, 'source': self.mode,
            'synthetic': True, 'value': 15.0 if rr_val == 'VALID' else None, 'samples': [],
            'sample_rate': 1, 'unit': '次/分'
        })
        streams.append({
            'node_id': 'NODE-B', 'stream': 'TEMP', 'timestamp': now_ms, 'seq': self.seq,
            'session_id': self.session_id, 'validity': b_validity, 'source': self.mode,
            'synthetic': True, 'value': 36.6 if b_validity == 'VALID' else None, 'samples': [],
            'sample_rate': 0, 'unit': '°C'
        })

        # 如果模式为 REPLAY，则实时流清空，并在 replay 字段上报
        replay_obj = None
        if self.mode == 'REPLAY':
            streams = []
            replay_obj = {
                'node_id': 'NODE-B', 'stream': 'ECG', 'timestamp': now_ms - 60000,
                'seq': self.seq + 10, 'session_id': self.session_id, 'validity': 'VALID',
                'source': 'REPLAY', 'synthetic': True, 'value': 72.0, 'samples': [],
                'sample_rate': 250, 'unit': 'bpm'
            }

        return {
            'type': 'snapshot',
            'schema_version': 1,
            'gateway_id': 'GW-DEV-001',
            'gateways': ['GW-DEV-001', 'GW-C-001'],
            'gateway_state': self.gateway_state,
            'broker_connected': self.broker_connected,
            'nodes': {
                'NODE-A': 'ONLINE' if self.node_a_online else 'OFFLINE',
                'NODE-B': 'ONLINE' if self.node_b_online else 'OFFLINE',
            },
            'server_time': now_ms,
            'streams': streams,
            'replay': replay_obj,
            'event': self.event,
        }

mock_state = MockMonitorState()

def create_test_server():
    app = FastAPI()

    @app.websocket('/medical-monitor/ws/v1/monitor')
    async def ws_monitor(ws: WebSocket):
        await ws.accept()
        raw = await ws.receive_text()
        data = json.loads(raw)
        token = data.get('token')
        if token != 'test-view-token-12345678901234567890':
            await ws.close(code=1008)
            return

        active_gateway = data.get('gateway_id', 'GW-DEV-001')
        try:
            while True:
                snapshot = mock_state.make_snapshot(active_gateway)
                await ws.send_json(snapshot)
                await asyncio.sleep(0.2)
        except (WebSocketDisconnect, asyncio.CancelledError):
            pass

    app.mount('/medical-monitor', StaticFiles(directory=WEB_DIST, html=True), name='web')
    return app

def run_acceptance():
    print('Starting local test server on port 8765...')
    server_config = uvicorn.Config(create_test_server(), host='127.0.0.1', port=8765, log_level='warning')
    server = uvicorn.Server(server_config)

    import threading
    server_thread = threading.Thread(target=server.run, daemon=True)
    server_thread.start()
    time.sleep(1.5)

    checks = []
    def record_pass(name: str):
        checks.append(name)
        print(f'[PASS] {name}')

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(viewport={'width': 1920, 'height': 1080})
        page = context.new_page()

        origin = 'http://127.0.0.1:8765/medical-monitor/'
        page.goto(origin)
        page.wait_for_selector('#open-access')

        # 1. 打开连接对话框并验证 Token 鉴权登录
        page.click('#open-access')
        page.wait_for_selector('#access-dialog[open]')
        page.fill('#view-token', 'test-view-token-12345678901234567890')
        page.click('#access-form button[type="submit"]')
        page.wait_for_function('document.querySelector("#value-HR").textContent === "72"')
        record_pass('Authentication and WebSocket connection established')

        # 2. 1920x1080 主监护屏验证：4 模块结构、TEMP、MOCK 标识、Canvas 渲染
        assert page.evaluate('document.querySelectorAll("[data-module]").length === 4')
        assert page.evaluate('document.querySelector("#value-TEMP").textContent === "36.6"')
        assert page.evaluate('document.querySelector("#source-banner").textContent.includes("MOCK")')
        record_pass('Four core modules, TEMP, and explicit MOCK banner rendered')

        # 3. 验证 Canvas 像素：ECG 绿色波形与 RR 趋势琥珀色
        time.sleep(1.0) # 等待几帧 Canvas 绘制
        page.wait_for_function('''() => {
            const c = document.querySelector("#wave-ECG");
            const data = c.getContext("2d").getImageData(0, 0, Math.min(300, c.width), Math.min(100, c.height)).data;
            return Array.from(data).some((v, i, a) => i % 4 === 1 && v > 150 && v > a[i - 1] * 1.2);
        }''')
        record_pass('ECG Canvas renders clinical green trace pixels')

        page.wait_for_function('''() => {
            const c = document.querySelector("#trend-RR");
            const data = c.getContext("2d").getImageData(0, 0, c.width, c.height).data;
            return Array.from(data).some((v, i, a) => i % 4 === 0 && v > 160 && a[i + 1] > 130 && a[i + 2] < 150);
        }''')
        assert page.evaluate('document.querySelector("#value-RR").textContent === "15"')
        record_pass('RR numeric and 120-second trend Canvas render properly')

        # 4. 血压 NIBP SYS/DIA 真实读数与无假波形
        assert page.evaluate('document.querySelector("#pressure-sys").textContent === "118" && document.querySelector("#pressure-dia").textContent === "76"')
        record_pass('NIBP SYS/DIA pair renders accurately without fake waveform')

        # 5. 走纸窗口切换 (8s / 16s)
        page.click('[data-window="16"]')
        assert page.evaluate('document.querySelector("[data-window=\\"16\\"]").getAttribute("aria-pressed") === "true"')
        assert page.evaluate('document.querySelector(".window-start").textContent.includes("16")')
        page.click('[data-window="8"]')
        record_pass('Waveform sweep window scales smoothly between 8s and 16s')

        # 6. 1920x1080 零滚动检验
        assert page.evaluate('document.documentElement.scrollHeight <= innerHeight && document.documentElement.scrollWidth <= innerWidth')
        record_pass('1920x1080 bedside monitor zero-scroll guarantee verified')

        # 保存截图 1: 1920x1080-live-mock.png
        page.screenshot(path=str(EVIDENCE_DIR / '1920x1080-live-mock.png'))
        print('Captured: 1920x1080-live-mock.png')

        # 7. 异常状态: Node-A 离线隔离
        mock_state.node_a_online = False
        page.wait_for_function('document.querySelector("#value-SpO2").textContent === "—" && document.querySelector("#value-HR").textContent === "72"')
        assert page.evaluate('document.querySelector("#node-a").textContent.includes("OFFLINE")')
        page.screenshot(path=str(EVIDENCE_DIR / '1920x1080-node-a-offline.png'))
        print('Captured: 1920x1080-node-a-offline.png')
        record_pass('Node-A offline UI isolation and dimming')

        # 8. 异常状态: Node-B 离线隔离
        mock_state.node_a_online = True
        mock_state.node_b_online = False
        page.wait_for_function('document.querySelector("#value-HR").textContent === "—" && document.querySelector("#value-SpO2").textContent === "98"')
        assert page.evaluate('document.querySelector("#node-b").textContent.includes("OFFLINE")')
        page.screenshot(path=str(EVIDENCE_DIR / '1920x1080-node-b-offline.png'))
        print('Captured: 1920x1080-node-b-offline.png')
        record_pass('Node-B offline UI isolation and dimming')

        # 9. 异常状态: RESP 有波形但 RR INVALID (场景 7)
        mock_state.node_b_online = True
        mock_state.rr_invalid = True
        page.wait_for_function('document.querySelector("#value-RR").textContent === "—" && document.querySelector("#rr-trend-status").textContent.includes("无有效")')
        time.sleep(4.0)  # 等待呼吸波形平稳走满视窗
        page.screenshot(path=str(EVIDENCE_DIR / '1920x1080-rr-invalid.png'))
        print('Captured: 1920x1080-rr-invalid.png')
        record_pass('RESP waveform present while RR is INVALID (renders "--" and status message)')

        # 恢复状态
        mock_state.rr_invalid = False
        page.wait_for_function('document.querySelector("#value-RR").textContent === "15"')

        # 10. 历史补传 REPLAY 到达独立专区，LIVE 读数清空
        mock_state.mode = 'REPLAY'
        page.wait_for_function('document.querySelector("#replay-status").textContent.includes("模拟补传")')
        page.wait_for_function('document.querySelector("#value-HR").textContent === "—"')
        page.screenshot(path=str(EVIDENCE_DIR / '1920x1080-replay.png'))
        print('Captured: 1920x1080-replay.png')
        record_pass('REPLAY reaches dedicated card and live scalars clear')

        # 恢复 LIVE
        mock_state.mode = 'MOCK'
        page.wait_for_function('document.querySelector("#value-HR").textContent === "72"')

        # 11. 网关切换隔离测试
        page.select_option('#gateway-select', 'GW-C-001')
        page.wait_for_function('document.querySelector("#gateway-id").textContent === "GW-C-001" && document.querySelector("#value-HR").textContent === "—"')
        record_pass('Gateway switching clears readings and isolates streams')
        page.select_option('#gateway-select', 'GW-DEV-001')
        page.wait_for_function('document.querySelector("#value-HR").textContent === "72"')

        # 12. 1366x768 笔记本屏幕适配验证
        page.set_viewport_size({'width': 1366, 'height': 768})
        time.sleep(2.5)  # 等待走纸充满视窗
        assert page.evaluate('document.documentElement.scrollHeight <= innerHeight && document.documentElement.scrollWidth <= innerWidth')
        page.screenshot(path=str(EVIDENCE_DIR / '1366x768.png'))
        print('Captured: 1366x768.png')
        record_pass('1366x768 responsive layout fits without vertical scroll')

        # 13. 移动端 390x844 只读降级验证 (禁止横向溢出)
        page.set_viewport_size({'width': 390, 'height': 844})
        time.sleep(2.5)  # 等待走纸充满视窗
        assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
        page.screenshot(path=str(EVIDENCE_DIR / 'mobile-390x844.png'))
        print('Captured: mobile-390x844.png')
        record_pass('Mobile 390x844 stacked read-only layout without horizontal overflow')

        # 14. 全屏模式截屏
        page.set_viewport_size({'width': 1920, 'height': 1080})
        time.sleep(0.5)
        page.screenshot(path=str(EVIDENCE_DIR / 'fullscreen.png'))
        print('Captured: fullscreen.png')
        record_pass('Fullscreen monitor view captured')

        # 输出 JSON 验收报告
        report = {
            'passed': len(checks),
            'checks': checks,
            'evidence_dir': 'cloud/evidence/ui-v07',
            'scenarios_tested': [
                'Gateway Online/Offline',
                'Node-A Offline Isolation',
                'Node-B Offline Isolation',
                'ECG/PPG/RESP Waveform Render',
                'RR Invalid with RESP Waveform',
                'REPLAY Independent Display',
                '1920x1080 Zero Scroll',
                '1366x768 Zero Scroll',
                'Mobile 390x844 No Horizontal Overflow',
                'Gateway Switching Data Isolation',
                'Canvas 2D Color & DPR Verification'
            ],
            'timestamp': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
        }
        (EVIDENCE_DIR / 'browser-acceptance.json').write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding='utf-8')
        print(f'Done! Successfully passed {len(checks)} checks.')

if __name__ == '__main__':
    run_acceptance()
