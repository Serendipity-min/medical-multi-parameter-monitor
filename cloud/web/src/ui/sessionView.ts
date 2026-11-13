// 趋势页读取同一个 Store；表格仅创建文本节点，来源字符串不能解释为 HTML。
import type { MonitorStore } from '../state/monitorStore';
import { historyCSV, type HistoryEntry } from '../state/sessionHistory';
import type { Route } from '../router/hashRouter';
import { trendChannels } from './parameters';
import type { ScalarChannel } from '../types';

const text = (id: string, value: string) => {
  const element = document.getElementById(id);
  if (element) element.textContent = value;
};
const time = (timestamp: number) => new Date(timestamp).toLocaleTimeString('zh-CN', { hour12: false });
const valueText = (entry: HistoryEntry) => entry.value === null ? '--' : Array.isArray(entry.value) ? entry.value.map(Math.round).join(' / ') : entry.channel === 'TEMP' ? entry.value.toFixed(1) : String(Math.round(entry.value));
const STATE: Record<string, string> = { VALID: '有效', INVALID: '无效', STALE: '过期', OFFLINE: '离线' };
const SOURCE: Record<string, string> = { LIVE: '', MOCK: ' · 演示', REPLAY: ' · 补传' };

export class SessionView {
  public route: Route = 'overview';
  private channel: ScalarChannel = trendChannels[0].channel;

  constructor(private store: MonitorStore) {}

  public mount(route: Route): void {
    this.route = route;
    if (route === 'trends') {
      document.querySelectorAll<HTMLButtonElement>('[data-trend]').forEach((button) => {
        button.onclick = () => { this.select(button.dataset.trend as ScalarChannel); };
      });
      this.select(this.channel);
      document.querySelector<HTMLButtonElement>('#export-csv')!.onclick = () => {
        // 只有显式点击才生成本地 Blob；读取当前会话，不请求后端或上传文件。
        const records = this.store.history.entries(this.channel);
        if (!records.length) return;
        const url = URL.createObjectURL(new Blob([historyCSV(records)], { type: 'text/csv;charset=utf-8' }));
        const link = document.createElement('a');
        link.href = url;
        link.download = `monitor-session-${this.channel}.csv`;
        link.click();
        setTimeout(() => URL.revokeObjectURL(url), 1000);
        text('export-status', `已导出 ${records.length} 条`);
      };
    }
    this.update();
  }

  private select(channel: ScalarChannel): void {
    this.channel = channel;
    const item = trendChannels.find((entry) => entry.channel === channel)!;
    document.querySelectorAll<HTMLButtonElement>('[data-trend]').forEach((button) => button.setAttribute('aria-pressed', String(button.dataset.trend === channel)));
    const canvas = document.getElementById('session-trend');
    if (canvas) canvas.dataset.channel = channel;
    text('trend-title', `${item.label} · ${item.unit}`);
    text('export-status', '');
    this.update();
  }

  public update(): void {
    const store = this.store;
    text('received-at', `最后数据 ${store.lastReceivedAt ? time(store.lastReceivedAt) : '--'}`);
    const freeze = document.getElementById('freeze')!;
    freeze.setAttribute('aria-pressed', String(!!store.frozenAt));
    freeze.textContent = store.frozenAt ? '解冻' : '冻结';
    if (this.route !== 'trends') return;
    const records = store.displayHistory(this.channel);
    text('history-range', `本次会话 · ${records.length} 条`);
    text('history-count', `${records.length} 条`);
    text('trend-start', records.length ? time(records[0].timestamp) : '--');
    text('trend-end', records.length ? time(records.at(-1)!.timestamp) : '--');
    document.getElementById('history-empty')!.hidden = records.some((record) => record.value !== null);
    document.getElementById('table-empty')!.hidden = records.length > 0;
    const body = document.getElementById('history-rows')!;
    const fragment = document.createDocumentFragment();
    for (const entry of records.slice(-40).reverse()) {
      const row = document.createElement('tr');
      for (const value of [time(entry.timestamp), valueText(entry), `${STATE[entry.validity] ?? entry.validity}${SOURCE[entry.source] ?? ''}`]) {
        const cell = document.createElement('td');
        cell.textContent = value;
        row.append(cell);
      }
      fragment.append(row);
    }
    body.replaceChildren(fragment);
    document.querySelector<HTMLButtonElement>('#export-csv')!.disabled = !store.history.entries(this.channel).length;
  }
}
