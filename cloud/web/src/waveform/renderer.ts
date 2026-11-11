// 全应用只有一个 RAF。路由销毁旧 Canvas 后自然停止该通道绘制，不销毁共享缓冲。
// 波形采用监护仪常见的扫描擦除方式：写入位置从左到右循环，前方留一段擦除间隙。
import type { MonitorStore } from '../state/monitorStore';
import type { WaveChannel } from '../types';
import { CHANNEL_COLORS } from '../ui/parameters';

export const WAVE_COLORS: Record<WaveChannel, string> = {
  ECG: CHANNEL_COLORS.HR, PPG: CHANNEL_COLORS.SpO2, RESP: CHANNEL_COLORS.RR,
};
const ERASE_FRACTION = 0.025;

export class WaveformRenderer {
  private running = false;
  private animFrameId = 0;
  // 幅值范围平滑跟随，避免每帧自动缩放造成波形跳动。
  private ranges: Partial<Record<WaveChannel, { low: number; high: number }>> = {};

  constructor(private store: MonitorStore) {}

  public start(): void {
    if (this.running) return;
    this.running = true;
    const loop = () => {
      if (!this.running) return;
      this.render();
      this.animFrameId = requestAnimationFrame(loop);
    };
    this.animFrameId = requestAnimationFrame(loop);
  }

  public stop(): void {
    this.running = false;
    cancelAnimationFrame(this.animFrameId);
  }

  private prepareCanvas(id: string) {
    const canvas = document.getElementById(id) as HTMLCanvasElement | null;
    if (!canvas || !canvas.clientWidth || !canvas.clientHeight) return null;
    const width = canvas.clientWidth;
    const height = canvas.clientHeight;
    const dpr = window.devicePixelRatio || 1;
    if (canvas.width !== Math.round(width * dpr) || canvas.height !== Math.round(height * dpr)) {
      canvas.width = Math.round(width * dpr);
      canvas.height = Math.round(height * dpr);
    }
    const ctx = canvas.getContext('2d');
    if (!ctx) return null;
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.clearRect(0, 0, width, height);
    return { ctx, width, height, canvas };
  }

  public render(): void {
    const now = this.store.frozenAt || performance.now();
    const windowMs = this.store.windowMs;
    for (const channel of ['ECG', 'PPG', 'RESP'] as WaveChannel[]) {
      const prepared = this.prepareCanvas(`wave-${channel}`);
      if (!prepared) continue;
      const { ctx, width, height } = prepared;
      const points = this.store.displayBuffer(channel).filter((p) => now - p.t <= windowMs && Number.isFinite(p.y));
      if (!points.length) { delete this.ranges[channel]; continue; }
      let low = Infinity, high = -Infinity;
      for (const p of points) { if (p.y < low) low = p.y; if (p.y > high) high = p.y; }
      const range = this.ranges[channel];
      if (range) {
        range.low = Math.min(low, range.low + (low - range.low) * 0.05);
        range.high = Math.max(high, range.high + (high - range.high) * 0.05);
      } else {
        this.ranges[channel] = { low, high };
      }
      const { low: lo, high: hi } = this.ranges[channel]!;
      const span = hi - lo || 1;
      const cursor = (now % windowMs) / windowMs;
      ctx.strokeStyle = WAVE_COLORS[channel];
      ctx.lineWidth = channel === 'ECG' ? 2.2 : 2;
      ctx.lineJoin = 'round';
      ctx.beginPath();
      let lastX = -1;
      for (const point of points) {
        const position = (point.t % windowMs) / windowMs;
        // 擦除间隙内是上一轮扫描的旧数据，不绘制。
        const ahead = (position - cursor + 1) % 1;
        if (ahead > 0 && ahead < ERASE_FRACTION) { lastX = -1; continue; }
        const x = position * width;
        const y = height * (0.9 - (point.y - lo) / span * 0.8);
        if (lastX < 0 || point.gap || x < lastX) ctx.moveTo(x, y);
        else ctx.lineTo(x, y);
        lastX = x;
      }
      ctx.stroke();
    }
    this.renderTrend();
  }

  private renderTrend(): void {
    const prepared = this.prepareCanvas('session-trend');
    if (!prepared) return;
    const { ctx, width, height, canvas } = prepared;
    const channel = canvas.dataset.channel as keyof typeof CHANNEL_COLORS;
    const color = CHANNEL_COLORS[channel];
    const records = this.store.displayHistory(channel);
    const values = records.flatMap((r) => r.value === null ? [] : Array.isArray(r.value) ? r.value : [r.value]);
    if (!values.length) return;
    const min = Math.min(...values);
    const max = Math.max(...values);
    const padding = Math.max((max - min) * 0.15, channel === 'TEMP' ? 0.2 : 2);
    const low = min - padding;
    const high = max + padding;
    // 横轴是本次真实接收的采集时间范围，不虚构过去的记录。
    const first = Math.min(...records.map((r) => r.timestamp));
    const last = Math.max(...records.map((r) => r.timestamp));
    const left = 64, right = 16, top = 16, bottom = 16;
    const xAt = (t: number) => last === first ? (left + width - right) / 2 : left + (width - left - right) * (t - first) / (last - first);
    const yAt = (value: number) => top + (height - top - bottom) * (1 - (value - low) / (high - low));
    ctx.font = '15px "Bahnschrift", "DIN Alternate", "Roboto Condensed", "Arial Narrow", sans-serif';
    ctx.fillStyle = '#8a8f96';
    ctx.strokeStyle = '#26292e';
    ctx.lineWidth = 1;
    for (let i = 0; i <= 4; i++) {
      const value = low + (high - low) * i / 4;
      const y = yAt(value);
      ctx.fillText(channel === 'TEMP' ? value.toFixed(1) : String(Math.round(value)), 8, y + 5);
      ctx.beginPath(); ctx.moveTo(left, y); ctx.lineTo(width - right, y); ctx.stroke();
    }
    ctx.strokeStyle = color;
    ctx.fillStyle = color;
    ctx.lineWidth = 2;
    let previous: typeof records[number] | null = null;
    for (const record of records) {
      if (record.value === null) { previous = null; continue; }
      const x = xAt(record.timestamp);
      if (Array.isArray(record.value)) {
        // NIBP 只有 SYS/DIA 成对离散结果，画成竖线标记，不连成连续曲线。
        const [sys, dia] = record.value;
        ctx.lineWidth = 3;
        ctx.beginPath(); ctx.moveTo(x - 7, yAt(sys)); ctx.lineTo(x + 7, yAt(sys)); ctx.moveTo(x, yAt(sys)); ctx.lineTo(x, yAt(dia)); ctx.moveTo(x - 7, yAt(dia)); ctx.lineTo(x + 7, yAt(dia)); ctx.stroke();
      } else {
        const y = yAt(record.value);
        if (previous && typeof previous.value === 'number' && previous.segment === record.segment && previous.source === record.source && record.timestamp - previous.timestamp < 10000) {
          ctx.beginPath(); ctx.moveTo(xAt(previous.timestamp), yAt(previous.value)); ctx.lineTo(x, y); ctx.stroke();
        } else {
          ctx.beginPath(); ctx.arc(x, y, 2, 0, Math.PI * 2); ctx.fill();
        }
      }
      previous = record;
    }
  }
}
