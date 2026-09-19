"""在本机对真实 HTTPS/WSS 入口执行有限的模拟验收，报告不含凭据/地址。"""

import argparse
import asyncio
import json
from pathlib import Path
import time
import urllib.request
import uuid

from websockets.asyncio.client import connect
from websockets.exceptions import ConnectionClosed
from mock_gateway.main import make_frame


async def until(ws, predicate, timeout=12):
    async with asyncio.timeout(timeout):
        while True:
            message = json.loads(await ws.recv())
            if predicate(message):
                return message


async def verify(config):
    checks = []
    with urllib.request.urlopen(config['origin'] + '/medical-monitor/api/health', timeout=15) as response:
        assert response.status == 200 and json.load(response)['simulation']
    checks.append('HTTPS health and certificate validation')
    origin = config['origin']
    browser_url = config['browser_url']
    async with connect(browser_url, origin=origin) as browser:
        await browser.send(json.dumps({'token': config['view_token']}))
        await until(browser, lambda s: s['protocol'] == 'MVIEW/1')
        checks.append('Browser WSS authenticated')
        async with connect(config['device_url']) as gateway:
            await gateway.send(json.dumps({'token': config['device_token']}))
            assert json.loads(await gateway.recv())['type'] == 'ready'
            session = str(uuid.uuid4())
            seq = 0

            async def send(control=None):
                nonlocal seq
                frame = make_frame(seq, session, control)
                await gateway.send(json.dumps(frame))
                assert json.loads(await gateway.recv())['accepted']
                seq += 1
                return frame

            await send()
            result = await until(browser, lambda s: s['live'] and s['live']['seq'] == 0 and s['live_fresh'])
            assert result['gateway_online']
            assert len(result['live']['nodes']['NODE-B']['signals']['ECG']['samples']) == 50
            checks.append('Gateway WSS and synthetic multi-parameter LIVE')
            await send({'node_a_online': False})
            result = await until(browser, lambda s: s['live'] and s['live']['seq'] == 1)
            assert not result['live']['nodes']['NODE-A']['online']
            assert result['live']['nodes']['NODE-B']['online']
            assert result['live']['nodes']['NODE-A']['signals']['SpO2']['value'] is None
            checks.append('Node-A offline isolates Node-B')
            await send({'node_b_online': False})
            result = await until(browser, lambda s: s['live'] and s['live']['seq'] == 2)
            assert not result['live']['nodes']['NODE-B']['online']
            assert result['live']['nodes']['NODE-A']['online']
            checks.append('Node-B offline isolates Node-A')
            await send({'quality': 'INVALID'})
            result = await until(browser, lambda s: s['live'] and s['live']['seq'] == 3)
            assert result['live']['nodes']['NODE-B']['signals']['HR']['value'] is None
            checks.append('Invalid scalar and waveform suppressed')
            await send()
            await send({'mode': 'REPLAY'})
            result = await until(browser, lambda s: s['replay'] is not None)
            assert result['live']['seq'] == 4 and result['replay']['seq'] == 5
            checks.append('REPLAY does not replace LIVE')
            # 保持 TCP 连接但停止 LIVE，观察服务端计时失效，不依赖浏览器行为。
            result = await until(browser, lambda s: not s['live_fresh'], timeout=10)
            assert result['live']['nodes']['NODE-B']['signals']['HR']['value'] is None
            checks.append('Silent connected gateway becomes stale')
            await send()
            await until(browser, lambda s: s['live_fresh'])
            async with connect(browser_url, origin=origin) as refreshed:
                await refreshed.send(json.dumps({'token': config['view_token']}))
                result = await until(refreshed, lambda s: s['live_fresh'])
                assert result['gateway_online']
            checks.append('Browser resubscription recovers current snapshot')
        result = await until(browser, lambda s: not s['gateway_online'])
        assert not result['live_fresh']
        checks.append('Gateway disconnect immediately invalidates LIVE')
        async with connect(config['device_url']) as gateway:
            await gateway.send(json.dumps({'token': config['device_token']})); await gateway.recv()
            await gateway.send(json.dumps(make_frame(0, str(uuid.uuid4())))); await gateway.recv()
            await until(browser, lambda s: s['live_fresh'])
        checks.append('Gateway reconnection and new session')
    async with connect(config['device_url']) as unauthorized:
        await unauthorized.send(json.dumps({'token': config['view_token']}))
        try:
            await unauthorized.recv()
            raise AssertionError('Viewer token accepted for device')
        except ConnectionClosed as exc:
            assert exc.rcvd and exc.rcvd.code == 1008
    checks.append('Device/view token roles are separated')
    return {'passed': len(checks), 'checks': checks, 'simulation': True,
            'timestamp': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--config', type=Path, required=True)
    parser.add_argument('--report', type=Path, required=True)
    args = parser.parse_args()
    configuration = json.loads(args.config.read_text(encoding='utf-8-sig'))
    try:
        result = asyncio.run(verify(configuration))
    except Exception as exc:
        # 失败报告只包含类型，避免连接异常把实际服务器地址带入版本库。
        print('ACCEPTANCE_FAILED', type(exc).__name__)
        raise SystemExit(1) from None
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding='utf-8')
    print('ACCEPTANCE_PASSED', result['passed'])
