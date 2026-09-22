// 集中式状态存储：管理波形采样环形缓冲区、RR 趋势、时钟锚点及断点判定。
// 任何视图更新均通过订阅回调触发，避免与 DOM 或 Canvas 直接耦合。

import { getEmptyViewModel, toMonitorViewModel } from '../model/viewModel';
import { SessionHistory, type HistoryEntry } from './sessionHistory';
import type { MonitorViewModel, Point, ScalarChannel, Snapshot, WaveChannel } from '../types';

export type StoreListener = (state: MonitorStore) => void;

export class MonitorStore {
  public currentViewModel: MonitorViewModel = getEmptyViewModel('等待数据');
  public buffers: Record<WaveChannel, Point[]> = { ECG: [], RESP: [], PPG: [] };
  public rrTrend: Point[] = [];
  public windowMs = 8000;
  public connectionText = '未连接';
  public isConnected = false;
  public lastMessageTime = 0;
  public lastReceivedAt = 0;
  public receivedCount = 0;
  public history = new SessionHistory();
  public frozenAt = 0;
  private frozenView: MonitorViewModel | null = null;
  private frozenBuffers: Record<WaveChannel, Point[]> | null = null;
  private frozenHistory: Partial<Record<ScalarChannel, readonly HistoryEntry[]>> | null = null;

  public toggleFreeze(): void {
    // 冻结副本只用于显示。原始快照、缓冲区及历史仍持续更新。
    this.frozenAt = this.frozenAt ? 0 : performance.now();
    this.frozenView = this.frozenAt ? structuredClone(this.currentViewModel) : null;
    this.frozenBuffers = this.frozenAt ? structuredClone(this.buffers) : null;
    this.frozenHistory = this.frozenAt ? Object.fromEntries(
      (['HR', 'RR', 'SpO2', 'PR', 'TEMP', 'NIBP'] as ScalarChannel[]).map((key) => [key, this.history.entries(key).slice()]),
    ) : null;
    this.notify();
  }

  public get displayViewModel(): MonitorViewModel {
    if (!this.frozenView) return this.currentViewModel;
    const result = { ...this.currentViewModel, scalars: { ...this.frozenView.scalars } };
    // 离线或无效优先于冻结，不能让冻结的有效数字掩盖新的故障状态。
    for (const key of Object.keys(result.scalars) as (keyof typeof result.scalars)[]) {
      if (this.currentViewModel.scalars[key].validity !== 'VALID') result.scalars[key] = this.currentViewModel.scalars[key];
    }
    return result;
  }

  public displayBuffer(channel: WaveChannel): Point[] {
    if (this.currentViewModel.waves[channel].validity !== 'VALID') return [];
    return this.frozenBuffers?.[channel] ?? this.buffers[channel];
  }

  public displayHistory(channel: ScalarChannel): readonly HistoryEntry[] {
    return this.frozenHistory?.[channel] ?? this.history.entries(channel);
  }

  public changeGateway(gateway: string): void {
    this.history.clear(gateway);
    this.clearLive('切换网关');
    this.currentViewModel.gatewayId = gateway;
    this.notify();
  }

  private seen: Record<string, string> = {};
  private anchors: Record<string, { session: string; captured: number; local: number }> = {};
  private listeners: Set<StoreListener> = new Set();

  public subscribe(listener: StoreListener): () => void {
    this.listeners.add(listener);
    listener(this);
    return () => this.listeners.delete(listener);
  }

  private notify(): void {
    for (const listener of this.listeners) {
      listener(this);
    }
  }

  public setConnection(text: string, isConnected: boolean): void {
    this.connectionText = text;
    this.isConnected = isConnected;
    this.notify();
  }

  public setWindowMs(ms: number): void {
    this.windowMs = ms;
    this.notify();
  }

  // 断连或切换网关时彻底清空当前读数、波形及序列锚点，杜绝脏数据跨会话残留。
  public clearLive(reason: string): void {
    const gateway = this.currentViewModel.gatewayId;
    this.currentViewModel = getEmptyViewModel(reason);
    this.currentViewModel.gatewayId = gateway;
    this.history.breakContinuity();
    this.frozenAt = 0;
    this.frozenView = null;
    this.frozenBuffers = null;
    this.frozenHistory = null;
    this.buffers.ECG = [];
    this.buffers.RESP = [];
    this.buffers.PPG = [];
    this.rrTrend = [];
    this.seen = {};
    this.anchors = {};
    this.notify();
  }

  public ingestSnapshot(data: Snapshot): void {
    this.lastMessageTime = performance.now();
    this.lastReceivedAt = Date.now();
    this.receivedCount += 1;
    if (this.currentViewModel.gatewayId !== data.gateway_id) this.changeGateway(data.gateway_id);
    this.currentViewModel = toMonitorViewModel(data);
    this.history.ingest(data, this.lastReceivedAt);

    const signals = new Map(
      data.streams.map((signal) => [signal.stream === 'SPO2' ? 'SpO2' : signal.stream, signal]),
    );

    // 1. 处理波形通道采样（ECG, RESP, PPG）
    const waveChannels: WaveChannel[] = ['ECG', 'RESP', 'PPG'];
    for (const name of waveChannels) {
      const signal = signals.get(name);
      const valid = signal?.validity === 'VALID' && signal.source !== 'REPLAY' && signal.sample_rate > 0;
      const key = signal ? `${signal.session_id}:${signal.seq}:${signal.timestamp}` : '';

      if (!signal || !valid) {
        this.buffers[name] = [];
        delete this.seen[name];
        delete this.anchors[name];
        continue;
      }

      if (this.seen[name] !== key) {
        const arrival = performance.now();
        let anchor = this.anchors[name];
        if (
          !anchor ||
          anchor.session !== signal.session_id ||
          Math.abs(anchor.local + signal.timestamp - anchor.captured - arrival) > 5000
        ) {
          anchor = this.anchors[name] = {
            session: signal.session_id,
            captured: signal.timestamp,
            local: arrival,
          };
          this.buffers[name] = [];
        }

        // 逐流采集时间映射到前端单调时钟，消除网络抖动对走纸的冲击
        const end = anchor.local + signal.timestamp - anchor.captured;
        const start = end - ((signal.samples.length - 1) * 1000) / signal.sample_rate;
        const previous = this.buffers[name].at(-1);

        if (previous && start <= previous.t) {
          this.buffers[name] = [];
        }

        this.buffers[name].push(
          ...signal.samples.map((y, i) => ({
            t: start + (i * 1000) / signal.sample_rate,
            y,
            gap: i === 0 && !!previous && start - previous.t > 100, // 采样中断点判定
          })),
        );

        // 维持 16 秒最大有界缓存，防止长周期驻留内存泄漏
        this.buffers[name] = this.buffers[name]
          .filter((point) => point.t >= end - 16000)
          .slice(-16000);

        this.seen[name] = key;
      }
    }

    // 2. 处理 RR 算法趋势带
    const rrSignal = signals.get('RR');
    const rrValid = rrSignal?.validity === 'VALID' && typeof rrSignal.value === 'number';
    const rrKey = rrSignal ? `${rrSignal.session_id}:${rrSignal.seq}:${rrSignal.timestamp}` : '';

    if (!rrValid) {
      this.rrTrend = [];
    } else if (this.seen['RR'] !== rrKey) {
      const now = performance.now();
      this.rrTrend.push({ t: now, y: rrSignal.value as number });
      this.rrTrend = this.rrTrend.filter((point) => point.t >= now - 120000).slice(-121);
      this.seen['RR'] = rrKey;
    }

    this.notify();
  }
}
