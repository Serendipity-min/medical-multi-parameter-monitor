// 本地显示报警回归：只用合成视图模型，不连接网络或设备。
import assert from 'node:assert/strict';
import test from 'node:test';
import { AlarmMonitor, ALARM_DELAY_MS, highestPriority } from '../src/model/alarms';
import { getEmptyViewModel } from '../src/model/viewModel';
import type { MonitorViewModel, ScalarChannel } from '../src/types';

const vm = (values: Partial<Record<ScalarChannel, number | number[]>>): MonitorViewModel => {
  const model = getEmptyViewModel();
  model.gatewayState = 'ONLINE';
  model.waves = { ECG: { validity: 'VALID', source: 'MOCK' }, PPG: { validity: 'VALID', source: 'MOCK' }, RESP: { validity: 'VALID', source: 'MOCK' } };
  for (const [channel, value] of Object.entries(values)) {
    model.scalars[channel as ScalarChannel] = { ...model.scalars[channel as ScalarChannel], rawValue: value, validity: 'VALID', source: 'MOCK' };
  }
  return model;
};

test('连续参数越限需持续 10 s 才报警，恢复后立即清除', () => {
  const monitor = new AlarmMonitor();
  assert.deepEqual(monitor.evaluate(vm({ SpO2: 88 }), true, true, 0), []);
  assert.deepEqual(monitor.evaluate(vm({ SpO2: 88 }), true, true, ALARM_DELAY_MS - 1), []);
  const alarms = monitor.evaluate(vm({ SpO2: 88 }), true, true, ALARM_DELAY_MS);
  assert.equal(alarms.length, 1);
  assert.equal(alarms[0].priority, 'medium');
  assert.equal(alarms[0].channel, 'SpO2');
  assert.deepEqual(monitor.evaluate(vm({ SpO2: 96 }), true, true, ALARM_DELAY_MS + 1), []);
  // 中断后重新计时，单帧离群值不会累计成报警。
  assert.deepEqual(monitor.evaluate(vm({ SpO2: 88 }), true, true, ALARM_DELAY_MS + 2), []);
});

test('严重越限为高优先级并排在最前', () => {
  const monitor = new AlarmMonitor();
  monitor.evaluate(vm({ SpO2: 80, HR: 125 }), true, true, 0);
  const alarms = monitor.evaluate(vm({ SpO2: 80, HR: 125 }), true, true, ALARM_DELAY_MS);
  assert.deepEqual(alarms.map((alarm) => alarm.priority), ['high', 'medium']);
  assert.equal(highestPriority(alarms), 'high');
});

test('血压按单次测量立即判定；体表温度不报警', () => {
  const monitor = new AlarmMonitor();
  const alarms = monitor.evaluate(vm({ NIBP: [168, 96], TEMP: 31 }), true, true, 0);
  assert.deepEqual(alarms.map((alarm) => alarm.id), ['NIBP-high']);
});

test('技术报警：通道断开、网关离线和波形无效', () => {
  const monitor = new AlarmMonitor();
  assert.deepEqual(monitor.evaluate(getEmptyViewModel(), false, false, 0), []);
  assert.deepEqual(monitor.evaluate(getEmptyViewModel(), false, true, 0).map((alarm) => alarm.id), ['link']);
  const offline = vm({});
  offline.gatewayState = 'OFFLINE';
  assert.deepEqual(monitor.evaluate(offline, true, true, 0).map((alarm) => alarm.id), ['gateway']);
  const noEcg = vm({});
  noEcg.waves.ECG = { validity: 'INVALID', source: 'MOCK' };
  assert.deepEqual(monitor.evaluate(noEcg, true, true, 0).map((alarm) => alarm.text), ['ECG 信号无效']);
});
