// Canvas 2D 渲染引擎：高刷新率波形扫描、DPR 自适应、采样断点起笔与 RR 算法趋势带。
// 独立运作，不关心 MQTT/WebSocket/网关网络逻辑。

import type { MonitorStore } from '../state/monitorStore';
import type { Point, WaveChannel } from '../types';

export const WAVE_COLORS: Record<WaveChannel, string> = {
  ECG: '#00e676',  // 经典监护高光绿 (G > 150, G > R*1.2)
  RESP: '#ffd600', // 呼吸警示琥珀黄 (R > 160, G > 130, B < 150)
  PPG: '#00e5ff',  // 容积血氧青蓝 (R:0, G:229, B:255)
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

  // 按物理设备像素比设置位图，用 CSS 逻辑像素绘制，保证 Retina / 4K 屏无模糊与锯齿
  private prepareCanvas(canvasId: string): { ctx: CanvasRenderingContext2D; width: number; height: number } | null {
    const canvas = document.querySelector<HTMLCanvasElement>(`#${canvasId}`);
    if (!canvas) return null;

    const width = canvas.clientWidth;
    const height = canvas.clientHeight;
    if (width === 0 || height === 0) return null;

    const dpr = window.devicePixelRatio || 1;
    const targetWidth = Math.round(width * dpr);
    const targetHeight = Math.round(height * dpr);

    if (canvas.width !== targetWidth || canvas.height !== targetHeight) {
      canvas.width = targetWidth;
      canvas.height = targetHeight;
    }

    const ctx = canvas.getContext('2d');
    if (!ctx) return null;

    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.clearRect(0, 0, width, height);
    return { ctx, width, height };
  }

  public render(): void {
    const now = performance.now();
    const channels: WaveChannel[] = ['ECG', 'RESP', 'PPG'];

    // 1. 绘制三大主波形通道（ECG, RESP, PPG）
    for (const name of channels) {
      const prepared = this.prepareCanvas(`wave-${name}`);
      if (!prepared) continue;
      const { ctx, width, height } = prepared;

      // 绘制临床监护底纹微网格 (32px x 28px)
      ctx.strokeStyle = '#16202c';
      ctx.lineWidth = 0.6;
      ctx.beginPath();
      for (let x = 0; x < width; x += 32) {
        ctx.moveTo(x, 0);
        ctx.lineTo(x, height);
      }
      for (let y = 0; y < height; y += 28) {
        ctx.moveTo(0, y);
        ctx.lineTo(width, y);
      }
      ctx.stroke();

      const buffer = this.store.buffers[name];
      if (!buffer || buffer.length === 0) continue;

      // 绘制生理走纸波形
      ctx.strokeStyle = WAVE_COLORS[name];
      ctx.lineWidth = 1.8;
      ctx.lineJoin = 'round';
      ctx.lineCap = 'round';
      ctx.beginPath();

      let started = false;
      const windowMs = this.store.windowMs;

      for (const point of buffer) {
        const x = width * (1 - (now - point.t) / windowMs);
        const y = height * (name === 'RESP' ? 0.5 - point.y * 0.4 : 0.73 - point.y * 0.58);

        if (x < 0 || x > width) continue;

        // 核心安全规则：检测到采样间隔 > 100ms 或序列号断点时，强制重新起笔 moveTo
        if (!started || point.gap) {
          ctx.moveTo(x, y);
          started = true;
        } else {
          ctx.lineTo(x, y);
        }
      }
      ctx.stroke();
    }

    // 2. 绘制 RR 算法独立趋势带（最近 120 秒）
    const preparedTrend = this.prepareCanvas('trend-RR');
    if (preparedTrend) {
      const { ctx, width, height } = preparedTrend;
      const rrTrend = this.store.rrTrend;

      const values = rrTrend.map((p) => p.y);
      const low = values.length > 0 ? Math.floor(Math.min(10, ...values) / 5) * 5 : 10;
      const high = values.length > 0 ? Math.ceil(Math.max(20, ...values) / 5) * 5 : 20;

      const xAt = (t: number) => 32 + (width - 36) * (1 - (now - t) / 120000);
      const yAt = (value: number) => 8 + (height - 16) * (1 - (value - low) / (high - low || 1));

      // 趋势刻度与基准线
      ctx.font = '10px "Segoe UI", sans-serif';
      ctx.fillStyle = '#64748b';
      ctx.strokeStyle = '#1e293b';
      ctx.lineWidth = 0.7;

      for (const value of [low, high]) {
        const y = yAt(value);
        ctx.fillText(String(value), 2, y + 3);
        ctx.beginPath();
        ctx.moveTo(30, y);
        ctx.lineTo(width, y);
        ctx.stroke();
      }

      // 趋势折线绘制
      ctx.strokeStyle = WAVE_COLORS.RESP;
      ctx.fillStyle = WAVE_COLORS.RESP;
      ctx.lineWidth = 1.7;
      ctx.beginPath();

      let previous: Point | null = null;
      for (const point of rrTrend) {
        if (now - point.t > 120000) continue;
        if (!previous || point.t - previous.t > 2500) {
          ctx.moveTo(xAt(point.t), yAt(point.y));
        } else {
          ctx.lineTo(xAt(point.t), yAt(point.y));
        }
        previous = point;
      }
      ctx.stroke();

      // 最新数值点发光指示
      if (previous && now - previous.t < 5000) {
        ctx.beginPath();
        ctx.arc(xAt(previous.t), yAt(previous.y), 2.7, 0, Math.PI * 2);
        ctx.fill();
      }
    }
  }
}
