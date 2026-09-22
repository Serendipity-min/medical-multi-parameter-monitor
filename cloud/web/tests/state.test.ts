// 固定状态回归：仅合成 MOCK 数据，不连接设备、网络或外部主机。
import assert from 'node:assert/strict';
import test from 'node:test';
import { SessionHistory, historyCSV } from '../src/state/sessionHistory';
import { MonitorStore } from '../src/state/monitorStore';
import { toMonitorViewModel } from '../src/model/viewModel';
import type { Signal, Snapshot } from '../src/types';

const signal = (overrides: Partial<Signal> = {}): Signal => ({ node_id: 'NODE-B', stream: 'RR', timestamp: Date.now(), seq: 1, session_id: 'test-session', validity: 'VALID', source: 'MOCK', synthetic: true, value: 15, samples: [], sample_rate: 0, unit: '次/分', ...overrides });
const snapshot = (streams: Signal[], gateway = 'GW-DEV-001'): Snapshot => ({ type: 'snapshot', schema_version: 1, gateway_id: gateway, gateway_state: 'ONLINE', nodes: { 'NODE-A': 'ONLINE', 'NODE-B': 'ONLINE' }, streams, replay: null, event: null });

test('历史从空开始，重复快照、同序列和倒退时间不生成伪历史', () => {
  const history = new SessionHistory();
  const item = signal();
  assert.equal(history.entries('RR').length, 0);
  history.ingest(snapshot([item]));
  history.ingest(snapshot([item]));
  history.ingest(snapshot([signal({ ...item, timestamp: item.timestamp + 10 })]));
  history.ingest(snapshot([signal({ ...item, seq: 2, timestamp: item.timestamp - 1 })]));
  assert.equal(history.entries('RR').length, 1);
});

test('设备新会话与断连分段，切换网关清空', () => {
  const history = new SessionHistory();
  const item = signal();
  history.ingest(snapshot([item]));
  history.ingest(snapshot([signal({ ...item, session_id: 'new-session' })]));
  assert.notEqual(history.entries('RR')[0].segment, history.entries('RR')[1].segment);
  history.breakContinuity();
  history.ingest(snapshot([signal({ ...item, session_id: 'new-session', seq: 2, timestamp: item.timestamp + 1 })]));
  assert.notEqual(history.entries('RR')[1].segment, history.entries('RR')[2].segment);
  history.ingest(snapshot([], 'GW-C-001'));
  assert.equal(history.entries('RR').length, 0);
});

test('无效记录无数值，REPLAY 不进入实时历史', () => {
  const history = new SessionHistory();
  history.ingest(snapshot([signal({ validity: 'INVALID' })]));
  assert.equal(history.entries('RR')[0].value, null);
  history.ingest(snapshot([signal({ source: 'REPLAY', seq: 2, timestamp: Date.now() + 10 })]));
  assert.equal(history.entries('RR').length, 1);
});

test('保留数量上限与 60 分钟时限同时生效', () => {
  const history = new SessionHistory();
  const now = Date.now();
  for (let i = 0; i < 3700; i++) history.ingest(snapshot([signal({ seq: i, timestamp: now + i })]), now + i);
  assert.equal(history.entries('RR', now + 3700).length, 3600);
  assert.equal(history.entries('RR', now + 3600000 + 3700).length, 0);
});

test('非有限标量和不完整血压不显示为有效数字', () => {
  const vm = toMonitorViewModel(snapshot([signal({ value: NaN }), signal({ stream: 'NIBP', value: [118, Infinity] })]));
  assert.equal(vm.scalars.RR.formatted, '--');
  assert.equal(vm.scalars.NIBP.formatted, '--');
});

test('RR 标量无效不误判 RESP 波形质量', () => {
  const vm = toMonitorViewModel(snapshot([signal({ validity: 'INVALID' }), signal({ stream: 'RESP', samples: [0, 1], sample_rate: 50 })]));
  assert.equal(vm.scalars.RR.formatted, '--');
  assert.equal(vm.waves.RESP.validity, 'VALID');
});

test('冻结只冻结显示，继续接收历史；新无效状态优先清空', () => {
  const store = new MonitorStore();
  const item = signal();
  store.ingestSnapshot(snapshot([item]));
  store.toggleFreeze();
  store.ingestSnapshot(snapshot([signal({ ...item, seq: 2, timestamp: item.timestamp + 1, value: 20 })]));
  assert.equal(store.displayViewModel.scalars.RR.formatted, '15');
  assert.equal(store.currentViewModel.scalars.RR.formatted, '20');
  assert.equal(store.displayHistory('RR').length, 1);
  assert.equal(store.history.entries('RR').length, 2);
  store.ingestSnapshot(snapshot([signal({ ...item, seq: 3, timestamp: item.timestamp + 2, validity: 'STALE' })]));
  assert.equal(store.displayViewModel.scalars.RR.formatted, '--');
  store.toggleFreeze();
  assert.equal(store.displayHistory('RR').length, 3);
});

test('断连清除当前值并保留分段历史；显式切换网关清空', () => {
  const store = new MonitorStore();
  store.ingestSnapshot(snapshot([signal()]));
  store.clearLive('断开连接');
  assert.equal(store.currentViewModel.scalars.RR.formatted, '--');
  assert.equal(store.history.entries('RR').length, 1);
  store.changeGateway('GW-C-001');
  assert.equal(store.history.entries('RR').length, 0);
});

test('CSV 来自真实会话条目并转义文本单元格', () => {
  const history = new SessionHistory();
  history.ingest(snapshot([signal({ session_id: 'a,b"c' })]));
  const csv = historyCSV(history.entries('RR'));
  assert.match(csv, /MOCK/);
  assert.ok(csv.includes('"a,b""c"'));
  assert.equal(csv.split('\r\n').length, 2);
});
