// 直接消费本轮真实WSS快照；验证七页共用的状态层，不复制其判定逻辑。
import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import assert from 'node:assert/strict';
import { toMonitorViewModel } from '../../cloud/web/src/model/viewModel';
import { MonitorStore } from '../../cloud/web/src/state/monitorStore';
import { routes } from '../../cloud/web/src/router/hashRouter';
import type { Snapshot } from '../../cloud/web/src/types';
assert.equal(routes.length, 7);
for (const label of ['ECG', 'RR']) {
  const snap = JSON.parse(readFileSync(join(process.argv[2], `${label}-WSS-snapshot-private.json`), 'utf8')) as Snapshot;
  const vm = toMonitorViewModel(snap);
  assert.equal(vm.sourceBanner, 'MOCK 模拟数据');
  assert.equal(vm.scalars.HR.formatted, label === 'ECG' ? '60' : '--');
  assert.equal(vm.scalars.RR.formatted, label === 'RR' ? '15' : '--');
  assert.equal(vm.scalars.TEMP.formatted, '--');
  const store = new MonitorStore();store.ingestSnapshot(snap);
  assert.ok(store.displayBuffer(label === 'ECG' ? 'ECG' : 'RESP').length);
  const stale = structuredClone(snap);
  for (const s of stale.streams) { s.validity = 'STALE';s.value = null;s.samples = []; }
  store.ingestSnapshot(stale);
  assert.equal(store.displayViewModel.scalars.HR.formatted, '--');
  assert.equal(store.displayViewModel.scalars.RR.formatted, '--');
  assert.equal(store.displayBuffer('ECG').length, 0);
  assert.equal(store.displayBuffer('RESP').length, 0);
  console.log(`SEVEN_PAGE_SHARED_STATE_PASS ${label} actual_WSS_MOCK INVALID STALE`);
}
