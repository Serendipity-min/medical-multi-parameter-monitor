// 设备在线判定回归：只用合成快照，不连接网络或设备。
import assert from 'node:assert/strict';
import test from 'node:test';
import { deviceLive } from '../src/demo/demoFeed';
import type { Signal, Snapshot } from '../src/types';

const signal = (overrides: Partial<Signal> = {}): Signal => ({ node_id: 'NODE-B', stream: 'HR', timestamp: 1, seq: 1, session_id: 's', validity: 'VALID', source: 'MOCK', synthetic: true, value: 70, samples: [], sample_rate: 0, unit: 'bpm', ...overrides });
const snapshot = (gateway_state: string, streams: Signal[]): Snapshot => ({ type: 'snapshot', schema_version: 1, gateway_id: 'GW-C-001', gateway_state, nodes: {}, streams, replay: null, event: null });

test('网关在线且有非补传有效数据才算设备实时', () => {
  assert.equal(deviceLive(null), false);
  assert.equal(deviceLive(snapshot('OFFLINE', [])), false);
  assert.equal(deviceLive(snapshot('ONLINE', [])), false);
  assert.equal(deviceLive(snapshot('ONLINE', [signal({ validity: 'STALE' })])), false);
  assert.equal(deviceLive(snapshot('ONLINE', [signal({ source: 'REPLAY' })])), false);
  assert.equal(deviceLive(snapshot('ONLINE', [signal()])), true);
});
