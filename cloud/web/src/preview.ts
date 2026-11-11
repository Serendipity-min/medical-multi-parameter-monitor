// 本地界面预览：只在开发服务器使用，不进入生产构建（vite build 只打包 index.html）。
// 合成数据一律标记 MOCK / synthetic，不连接网络或设备。
import { createApp } from './app';
import type { Signal, Snapshot } from './types';

const { store } = createApp();
const scene = new URLSearchParams(location.search).get('scene') ?? 'normal';
const alarm = scene === 'alarm';
const session = 'preview-session';
const start = Date.now();
let seq = 0;

const ecgAt = (t: number, bpm: number) => {
  const phase = (t * bpm / 60) % 1;
  const g = (c: number, w: number, a: number) => a * Math.exp(-((phase - c) ** 2) / (2 * w * w));
  return g(0.18, 0.025, 0.12) - g(0.29, 0.008, 0.12) + g(0.31, 0.01, 1.1) - g(0.335, 0.01, 0.25) + g(0.56, 0.045, 0.28);
};
const ppgAt = (t: number, bpm: number) => {
  const phase = (t * bpm / 60) % 1;
  return Math.exp(-((phase - 0.22) ** 2) / 0.006) + 0.35 * Math.exp(-((phase - 0.48) ** 2) / 0.01);
};
const respAt = (t: number) => Math.sin(2 * Math.PI * t * 15 / 60);

const signal = (node: string, stream: string, timestamp: number, extra: Partial<Signal>): Signal => ({
  node_id: node, stream, timestamp, seq, session_id: session, validity: 'VALID', source: 'MOCK', synthetic: true,
  value: null, samples: [], sample_rate: 0, unit: '', ...extra,
});

function tick(): void {
  seq += 1;
  const now = Date.now();
  const second = Math.floor(now / 1000) * 1000;
  const hr = alarm ? 128 : 72 + Math.round(Math.sin(now / 9000) * 2);
  const spo2 = alarm ? 87 : 97 + (Math.sin(now / 13000) > 0.6 ? 1 : 0);
  const waves = (rate: number, fn: (t: number) => number) =>
    Array.from({ length: rate / 5 }, (_, i) => fn((now - start) / 1000 - (rate / 5 - 1 - i) / rate));
  const data: Snapshot = {
    type: 'snapshot', schema_version: 1, node_profile: 'five', gateway_id: store.currentViewModel.gatewayId,
    gateway_state: 'ONLINE', broker_connected: true,
    nodes: { 'NODE-A': 'ONLINE', 'NODE-B': 'ONLINE', 'NODE-D': 'ONLINE', 'NODE-E': 'ONLINE' },
    streams: [
      signal('NODE-B', 'ECG', now, { samples: waves(250, (t) => ecgAt(t, hr)), sample_rate: 250, unit: 'mV' }),
      signal('NODE-A', 'PPG', now, { samples: waves(50, (t) => ppgAt(t, hr)), sample_rate: 50, unit: 'a.u.' }),
      signal('NODE-B', 'RESP', now, { samples: waves(50, respAt), sample_rate: 50, unit: 'a.u.' }),
      // 标量按 1 Hz 更新，与真实系统一致。
      ...[['NODE-B', 'HR', hr, 'bpm'], ['NODE-A', 'SPO2', spo2, '%'], ['NODE-A', 'PR', hr, 'bpm'], ['NODE-B', 'RR', 15, 'rpm'], ['NODE-D', 'TEMP', 33.6, '°C']]
        .map(([node, stream, value, unit]) => signal(node as string, stream as string, second, { seq: Math.floor(second / 1000), value: value as number, unit: unit as string })),
      signal('NODE-E', 'NIBP', start, { seq: 5, value: alarm ? [168, 96] : [118, 76], unit: 'mmHg' }),
    ],
    replay: null, event: null,
  };
  store.ingestSnapshot(data);
}

if (scene !== 'offline') {
  store.setConnection('监护通道已连接', true);
  // 先放入几次较早的血压结果，用于展示记录列表。
  [[122, 79], [119, 77], [125, 81], [117, 75]].forEach((value, index) => store.ingestSnapshot({
    type: 'snapshot', schema_version: 1, gateway_id: store.currentViewModel.gatewayId, gateway_state: 'ONLINE', nodes: {},
    streams: [signal('NODE-E', 'NIBP', start - (4 - index) * 15 * 60_000, { seq: index + 1, value, unit: 'mmHg' })],
    replay: null, event: null,
  }));
  tick();
  setInterval(tick, 200);
}
