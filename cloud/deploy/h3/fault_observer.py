"""隔离断网复测：只记录状态迁移，验证缺席B始终离线与旧值不作当前值。"""
import asyncio
from datetime import datetime, timezone
import json
import time

from cloud.deploy.h3.isolated_server import STATE, load_env


async def observe(seconds=110):
    from websockets.asyncio.client import connect
    env = load_env(STATE / 'backend.env')
    result = {'action': 'ISOLATED_WIFI_FAULT_STRICT_NODE_B',
              'started_utc': datetime.now(timezone.utc).isoformat(),
              'node_b_not_offline': 0, 'invalid_current_value': 0,
              'valid_while_gateway_unavailable': 0, 'replay_used_as_current': 0,
              'unavailable_seen': False, 'recovered_seen': False,
              'raw_measurements_saved': False, 'transitions': []}
    started = time.monotonic()
    previous = None
    async with connect('ws://127.0.0.1:18775/ws/v1/monitor',
                       origin='http://127.0.0.1:18767', max_size=65536) as ws:
        await ws.send(json.dumps({'token': env['MONITOR_VIEW_TOKEN'], 'gateway_id': 'GW-C-001'}))
        while time.monotonic() - started < seconds:
            data = json.loads(await asyncio.wait_for(ws.recv(), 3))
            elapsed = round(time.monotonic() - started, 3)
            nodes = data.get('nodes', {})
            streams = data['streams']
            result['node_b_not_offline'] += int(nodes.get('NODE-B') != 'OFFLINE')
            unavailable = data['gateway_state'] != 'ONLINE'
            result['unavailable_seen'] |= unavailable
            for stream in streams:
                valid = stream['validity'] == 'VALID'
                # 无效数据必须同时隐藏标量和波形；不把REPLAY纳入当前实时值。
                result['invalid_current_value'] += int(not valid and
                    (stream.get('value') is not None or bool(stream.get('samples'))))
                result['valid_while_gateway_unavailable'] += int(unavailable and valid)
                result['replay_used_as_current'] += int(valid and stream['source'] == 'REPLAY')
            # 恢复必须有故障后采集的新鲜PPG，不能仅靠状态包恢复即宣布成功。
            if result['unavailable_seen'] and not unavailable and nodes.get('NODE-A') == 'ONLINE':
                if any(s['stream'] == 'PPG' and s['validity'] == 'VALID' and
                       s['timestamp'] >= data['server_time'] - 5000 for s in streams):
                    result['recovered_seen'] = True
            state = {'gateway': data['gateway_state'], 'nodes': nodes,
                     'validities': {s['stream']: s['validity'] for s in streams}}
            if state != previous:
                result['transitions'].append(dict(elapsed_s=elapsed, **state))
                previous = state
            result['elapsed_s'] = elapsed
    result['exit_code'] = int(not result['unavailable_seen'] or not result['recovered_seen'] or
        any(result[k] for k in ('node_b_not_offline', 'invalid_current_value',
                               'valid_while_gateway_unavailable', 'replay_used_as_current')))
    return result


if __name__ == '__main__':
    try:
        result = asyncio.run(observe())
        print(json.dumps(result, indent=2))
        raise SystemExit(result['exit_code'])
    except Exception as exc:
        print(json.dumps({'exit_code': 1, 'failure_type': type(exc).__name__, 'details_suppressed': True}))
        raise SystemExit(1)
