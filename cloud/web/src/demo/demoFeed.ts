// 演示模式：本地合成数据，只在设备无实时数据时由用户手动开启。不连接网络或设备，
// 每帧标记 MOCK / synthetic；会话号固定为 demo，便于与真实会话区分。
import type { MonitorStore } from '../state/monitorStore';
import type { Signal, Snapshot } from '../types';

const SESSION = 'local-demo';

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

export class DemoFeed {
  private timer = 0;
  private start = 0;
  private seq = 0;
  private alarm = false;

  constructor(private store: MonitorStore) {}

  public get active(): boolean {
    return this.timer !== 0;
  }

  public begin(alarm = false): void {
    if (this.active) return;
    this.alarm = alarm;
    this.start = Date.now();
    this.seq = 0;
    this.store.clearLive('演示模式');
    // 先放入几次较早的血压结果，用于展示记录列表。
    [[122, 79], [119, 77], [125, 81], [117, 75]].forEach((value, index) => this.store.ingestSnapshot(this.snapshot([
      this.signal('NODE-E', 'NIBP', this.start - (4 - index) * 15 * 60_000, { seq: index + 1, value, unit: 'mmHg' }),
    ])));
    this.tick();
    this.timer = window.setInterval(() => this.tick(), 200);
  }

  public end(): void {
    if (!this.active) return;
    clearInterval(this.timer);
    this.timer = 0;
    this.store.clearLive('退出演示');
  }

  private signal(node: string, stream: string, timestamp: number, extra: Partial<Signal>): Signal {
    return {
      node_id: node, stream, timestamp, seq: this.seq, session_id: SESSION, validity: 'VALID', source: 'MOCK', synthetic: true,
      value: null, samples: [], sample_rate: 0, unit: '', ...extra,
    };
  }

  private snapshot(streams: Signal[]): Snapshot {
    return {
      type: 'snapshot', schema_version: 1, node_profile: 'five', gateway_id: this.store.currentViewModel.gatewayId,
      gateway_state: 'ONLINE', broker_connected: true,
      nodes: { 'NODE-A': 'ONLINE', 'NODE-B': 'ONLINE', 'NODE-D': 'ONLINE', 'NODE-E': 'ONLINE' },
      streams, replay: null, event: null,
    };
  }

  private tick(): void {
    this.seq += 1;
    const now = Date.now();
    const second = Math.floor(now / 1000) * 1000;
    const hr = this.alarm ? 128 : 72 + Math.round(Math.sin(now / 9000) * 2);
    const spo2 = this.alarm ? 87 : 97 + (Math.sin(now / 13000) > 0.6 ? 1 : 0);
    const waves = (rate: number, fn: (t: number) => number) =>
      Array.from({ length: rate / 5 }, (_, i) => fn((now - this.start) / 1000 - (rate / 5 - 1 - i) / rate));
    this.store.ingestSnapshot(this.snapshot([
      this.signal('NODE-B', 'ECG', now, { samples: waves(250, (t) => ecgAt(t, hr)), sample_rate: 250, unit: 'mV' }),
      this.signal('NODE-A', 'PPG', now, { samples: waves(50, (t) => ppgAt(t, hr)), sample_rate: 50, unit: 'a.u.' }),
      this.signal('NODE-B', 'RESP', now, { samples: waves(50, respAt), sample_rate: 50, unit: 'a.u.' }),
      // 标量按 1 Hz 更新，与真实系统一致。
      ...([['NODE-B', 'HR', hr, 'bpm'], ['NODE-A', 'SPO2', spo2, '%'], ['NODE-A', 'PR', hr, 'bpm'], ['NODE-B', 'RR', 15, 'rpm'], ['NODE-D', 'TEMP', 33.6, '°C']] as const)
        .map(([node, stream, value, unit]) => this.signal(node, stream, second, { seq: Math.floor(second / 1000), value, unit })),
      this.signal('NODE-E', 'NIBP', this.start, { seq: 5, value: this.alarm ? [168, 96] : [118, 76], unit: 'mmHg' }),
    ]));
  }
}

// 判定快照是否来自在线设备的实时数据：网关在线且至少一路非补传的有效数据。
export function deviceLive(data: Snapshot | null): boolean {
  return !!data && data.gateway_state === 'ONLINE' && data.streams.some((s) => s.validity === 'VALID' && s.source !== 'REPLAY');
}
