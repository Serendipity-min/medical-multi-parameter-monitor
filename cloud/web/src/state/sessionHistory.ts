// 浏览器本次会话的标量记录；不请求历史接口，也不把补传混入实时趋势。
import type { ScalarChannel, Signal, Snapshot, Validity } from '../types';

export interface HistoryEntry {
  channel: ScalarChannel;
  timestamp: number;
  received: number;
  session: string;
  segment: number;
  seq: number;
  source: string;
  validity: Validity;
  value: number | number[] | null;
  unit: string;
}

const channels: ScalarChannel[] = ['HR', 'RR', 'SpO2', 'PR', 'TEMP', 'NIBP'];
const MAX_POINTS = 3600;
const MAX_AGE_MS = 60 * 60 * 1000;

export class SessionHistory {
  private records: Partial<Record<ScalarChannel, HistoryEntry[]>> = {};
  private latest: Partial<Record<ScalarChannel, Signal>> = {};
  private segments: Partial<Record<ScalarChannel, number>> = {};
  private gateway = '';

  public clear(gateway: string): void {
    this.gateway = gateway;
    this.records = {};
    this.latest = {};
    this.segments = {};
  }

  public breakContinuity(): void {
    // 断线保留已接收记录，但后续曲线不能跨越断线区间连线。
    for (const channel of channels) this.segments[channel] = (this.segments[channel] ?? 0) + 1;
  }

  public ingest(snapshot: Snapshot, received = Date.now()): void {
    if (snapshot.gateway_id !== this.gateway) this.clear(snapshot.gateway_id);
    for (const signal of snapshot.streams) {
      const channel = (signal.stream === 'SPO2' ? 'SpO2' : signal.stream) as ScalarChannel;
      if (!channels.includes(channel) || signal.source === 'REPLAY') continue;
      const previous = this.latest[channel];
      const sameSession = previous?.session_id === signal.session_id;
      // 快照会重复携带旧标量；同序列或倒退时间不能生成新历史点。
      if (sameSession && (signal.seq <= previous!.seq || signal.timestamp <= previous!.timestamp)) continue;
      if (!Number.isFinite(signal.timestamp)) continue;
      if (previous && !sameSession) this.segments[channel] = (this.segments[channel] ?? 0) + 1;
      this.latest[channel] = { ...signal };
      const usable = signal.validity === 'VALID' && (
        typeof signal.value === 'number' ? Number.isFinite(signal.value) :
        channel === 'NIBP' && Array.isArray(signal.value) && signal.value.length >= 2 && signal.value.slice(0, 2).every(Number.isFinite)
      );
      const entry: HistoryEntry = {
        channel, timestamp: signal.timestamp, received, session: signal.session_id,
        segment: this.segments[channel] ?? 0, seq: signal.seq, source: signal.source,
        validity: usable ? 'VALID' : signal.validity === 'VALID' ? 'INVALID' : signal.validity,
        value: usable ? (Array.isArray(signal.value) ? signal.value.slice(0, 2) : signal.value) : null,
        unit: signal.unit,
      };
      this.records[channel] = [...(this.records[channel] ?? []), entry]
        .filter((item) => received - item.received <= MAX_AGE_MS).slice(-MAX_POINTS);
    }
  }

  public entries(channel: ScalarChannel, now = Date.now()): readonly HistoryEntry[] {
    // 即使断线后没有新帧，读取时也执行保留时限；刷新页面自然丢弃整个实例。
    this.records[channel] = (this.records[channel] ?? []).filter((item) => now - item.received <= MAX_AGE_MS);
    return this.records[channel]!;
  }
}

export function historyCSV(records: readonly HistoryEntry[]): string {
  const cell = (value: unknown): string => {
    const text = String(value ?? '');
    // 仅对文本列做表格公式前缀保护，兼容逗号、引号和换行。
    const safe = /^[\s]*[=+\-@]/.test(text) ? `'${text}` : text;
    return `"${safe.replaceAll('"', '""')}"`;
  };
  const rows = records.map((item) => [
    new Date(item.timestamp).toISOString(), item.channel, item.value === null ? '' : String(item.value),
    item.unit, item.validity, item.source, item.session, item.segment, item.seq,
  ].map(cell).join(','));
  return '\uFEFFtimestamp,channel,value,unit,validity,source,session,segment,seq\r\n' + rows.join('\r\n');
}
