// 全应用只有一个 RAF。路由销毁旧 Canvas 后自然停止该通道绘制，不销毁共享缓冲。
import type { MonitorStore } from '../state/monitorStore';
import type { ScalarChannel, WaveChannel } from '../types';

export const WAVE_COLORS: Record<WaveChannel, string> = {
  ECG: '#75ff9e', RESP: '#ffe37a', PPG: '#bdf4ff',
};
const TREND_COLORS: Record<ScalarChannel, string> = {
  HR: WAVE_COLORS.ECG, RR: WAVE_COLORS.RESP, SpO2: WAVE_COLORS.PPG,
  PR: WAVE_COLORS.PPG, TEMP: '#00daf3', NIBP: '#dfe2eb',
};

export class WaveformRenderer {
  private running = false;
  private animFrameId = 0;

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
    for (const channel of ['ECG', 'PPG', 'RESP'] as WaveChannel[]) {
      const prepared = this.prepareCanvas(`wave-${channel}`);
      if (!prepared) continue;
      const { ctx, width, height } = prepared;
      // 网格仅作视觉定位，不声明物理走纸速度或电压标定。
      ctx.strokeStyle = '#1c242d';
      ctx.lineWidth = .5;
      ctx.beginPath();
      for (let x = 0; x < width; x += 40) { ctx.moveTo(x, 0); ctx.lineTo(x, height); }
      for (let y = 0; y < height; y += 32) { ctx.moveTo(0, y); ctx.lineTo(width, y); }
      ctx.stroke();
      const points = this.store.displayBuffer(channel).filter((p) => now - p.t <= this.store.windowMs && Number.isFinite(p.y));
      if (!points.length) continue;
      const low = Math.min(...points.map((p) => p.y));
      const high = Math.max(...points.map((p) => p.y));
      const span = high - low || 1;
      ctx.strokeStyle = WAVE_COLORS[channel];
      ctx.lineWidth = 1.8;
      ctx.lineJoin = 'round';
      ctx.beginPath();
      let started = false;
      for (const point of points) {
        const x = width * (1 - (now - point.t) / this.store.windowMs);
        const y = height * (.84 - (point.y - low) / span * .68);
        if (x < 0 || x > width) continue;
        if (!started || point.gap) ctx.moveTo(x, y);
        else ctx.lineTo(x, y);
        started = true;
      }
      ctx.stroke();
    }
    this.renderTrend();
  }

  private renderTrend(): void {
    const prepared = this.prepareCanvas('session-trend');
    if (!prepared) return;
    const { ctx, width, height, canvas } = prepared;
    const channel = canvas.dataset.channel as ScalarChannel;
    const records = this.store.displayHistory(channel);
    const values = records.flatMap((r) => r.value === null ? [] : Array.isArray(r.value) ? r.value : [r.value]);
    if (!values.length) return;
    const min = Math.min(...values);
    const max = Math.max(...values);
    const padding = Math.max((max - min) * .15, channel === 'TEMP' ? .1 : 1);
    const low = min - padding;
    const high = max + padding;
    // 横轴是本次真实接收的采集时间范围，不虚构过去一小时的记录。
    const first = Math.min(...records.map((r) => r.timestamp));
    const last = Math.max(...records.map((r) => r.timestamp));
    const xAt = (t: number) => last === first ? width / 2 : 40 + (width - 56) * (t - first) / (last - first);
    const yAt = (value: number) => 12 + (height - 26) * (1 - (value - low) / (high - low));
    ctx.font = '10px Consolas, monospace';
    ctx.fillStyle = '#8996a4';
    ctx.strokeStyle = '#2a323b';
    ctx.lineWidth = .7;
    for (const value of [low, (low + high) / 2, high]) {
      const y = yAt(value);
      ctx.fillText(channel === 'TEMP' ? value.toFixed(1) : String(Math.round(value)), 0, y + 3);
      ctx.beginPath(); ctx.moveTo(36, y); ctx.lineTo(width, y); ctx.stroke();
    }
    ctx.strokeStyle = TREND_COLORS[channel];
    ctx.fillStyle = TREND_COLORS[channel];
    ctx.lineWidth = 1.6;
    let previous: typeof records[number] | null = null;
    for (const record of records) {
      if (record.value === null) { previous = null; continue; }
      const x = xAt(record.timestamp);
      if (Array.isArray(record.value)) {
        // NIBP 只有 SYS/DIA 成对离散结果，不连成虚构的连续压力波形。
        const [sys, dia] = record.value;
        ctx.beginPath(); ctx.moveTo(x, yAt(sys)); ctx.lineTo(x, yAt(dia)); ctx.stroke();
        for (const value of [sys, dia]) { ctx.beginPath(); ctx.arc(x, yAt(value), 2.5, 0, Math.PI * 2); ctx.fill(); }
      } else {
        const y = yAt(record.value);
        if (previous && typeof previous.value === 'number' && previous.segment === record.segment && previous.source === record.source && record.timestamp - previous.timestamp < 10000) {
          ctx.beginPath(); ctx.moveTo(xAt(previous.timestamp), yAt(previous.value)); ctx.lineTo(x, y); ctx.stroke();
        }
        ctx.beginPath(); ctx.arc(x, y, 2, 0, Math.PI * 2); ctx.fill();
      }
      previous = record;
    }
  }
}
