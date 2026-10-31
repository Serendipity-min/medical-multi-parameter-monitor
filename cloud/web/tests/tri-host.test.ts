import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import test from 'node:test';
import { toMonitorViewModel } from '../src/model/viewModel';
import { MonitorStore } from '../src/state/monitorStore';
import type { Snapshot } from '../src/types';

const rows: {scenario: string; snapshot: Snapshot}[] = JSON.parse(readFileSync(process.env.T0_SNAPSHOT_INPUT!, 'utf8'));
const get = (name: string) => rows.find(row => row.scenario === name)!.snapshot;

test('真实CAN/序列化/Hub合成输出保持A/B频道、量值与MOCK来源', () => {
  const vm = toMonitorViewModel(get('dual-online'));
  assert.equal(vm.nodeAState, 'ONLINE'); assert.equal(vm.nodeBState, 'ONLINE');
  for (const [key, expected] of Object.entries({ HR:'60', RR:'15', TEMP:'33.1', SpO2:'98', PR:'60', NIBP:'120' })) {
    assert.equal(vm.scalars[key as keyof typeof vm.scalars].formatted, expected);
  }
  assert.equal(vm.scalars.NIBP.subFormatted, '80');
  assert.equal(vm.scalars.HR.nodeId, 'NODE-B'); assert.equal(vm.scalars.SpO2.nodeId, 'NODE-A');
  assert.deepEqual(vm.sources, ['MOCK']);
  for (const [stream, rate, length] of [['ECG',250,100],['RESP',50,50],['PPG',50,50]] as const) {
    const signal = get('dual-online').streams.find(s => s.stream === stream)!;
    assert.equal(signal.sample_rate, rate); assert.equal(signal.samples.length, length);
  }
});

test('HR无效清空、恢复及REPLAY隔离不改变RR/TEMP或A节点', () => {
  const store = new MonitorStore();
  store.ingestSnapshot(get('dual-online'));store.ingestSnapshot(get('invalid-HR'));
  assert.equal(store.currentViewModel.scalars.HR.formatted, '--');
  assert.equal(store.currentViewModel.scalars.RR.formatted, '15');
  assert.equal(store.currentViewModel.scalars.TEMP.formatted, '33.1');
  store.ingestSnapshot(get('restored-HR'));
  assert.equal(store.currentViewModel.scalars.HR.formatted, '60');
  store.ingestSnapshot(get('replay-no-override'));
  assert.equal(store.currentViewModel.scalars.HR.formatted, '60');
  assert.equal(get('replay-no-override').replay!.value, 38);
});

test('B重启/旧epoch不借A在线复活；普通过期与NIBP90秒域分开', () => {
  for (const name of ['B-new-boot','old-epoch-no-reactivation']) {
    const vm = toMonitorViewModel(get(name));
    assert.equal(vm.scalars.HR.formatted, '--'); assert.equal(vm.scalars.TEMP.formatted, '--');
    assert.equal(vm.scalars.SpO2.formatted, '98');
  }
  const stale = toMonitorViewModel(get('ordinary-stale-NIBP-retained'));
  assert.equal(stale.scalars.SpO2.formatted, '--'); assert.equal(stale.scalars.NIBP.formatted, '120');
  const reboot = toMonitorViewModel(get('gateway-new-boot'));
  for (const scalar of Object.values(reboot.scalars)) assert.equal(scalar.formatted, '--');
});
