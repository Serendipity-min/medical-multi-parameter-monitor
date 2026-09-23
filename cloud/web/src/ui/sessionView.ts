// 详情页读取同一个 Store；表格仅创建文本节点，来源字符串不能解释为 HTML。
import type { MonitorStore } from '../state/monitorStore';
import { historyCSV, type HistoryEntry } from '../state/sessionHistory';
import type { Route } from '../router/hashRouter';
import { parameters } from './parameters';

const text = (id: string, value: string) => {
  const element = document.getElementById(id);
  if (element) element.textContent = value;
};
const time = (timestamp: number) => new Date(timestamp).toLocaleTimeString('zh-CN', { hour12: false });
const valueText = (entry: HistoryEntry) => entry.value === null ? '--' : Array.isArray(entry.value) ? entry.value.map(Math.round).join(' / ') : entry.channel === 'TEMP' ? entry.value.toFixed(1) : String(Math.round(entry.value));

export class SessionView {
  public route: Route = 'overview';

  constructor(private store: MonitorStore) {}

  public mount(route: Route): void {
    this.route = route;
    const button = document.querySelector<HTMLButtonElement>('#export-csv');
    if (button && route !== 'overview') {
      button.onclick = () => {
        // 只有显式点击才生成本地 Blob；读取当前会话，不请求后端或上传文件。
        const records = this.store.history.entries(parameters[route].scalar);
        if (!records.length) return;
        const url = URL.createObjectURL(new Blob([historyCSV(records)], { type: 'text/csv;charset=utf-8' }));
        const link = document.createElement('a');
        link.href = url;
        link.download = `monitor-session-${route}.csv`;
        link.click();
        setTimeout(() => URL.revokeObjectURL(url), 1000);
        text('export-status', `已导出 ${records.length} 条本次会话记录`);
      };
    }
    this.update();
  }

  public update(): void {
    const store = this.store;
    text('received-at', `最后通信：${store.lastReceivedAt ? time(store.lastReceivedAt) : '--'} · 已收 ${store.receivedCount} 帧`);
    const frozen = !!store.frozenAt;
    document.getElementById('frozen-status')!.hidden = !frozen;
    const freeze = document.getElementById('freeze')!;
    freeze.setAttribute('aria-pressed', String(frozen));
    freeze.querySelector('span')!.textContent = frozen ? '恢复显示' : '冻结显示';
    document.querySelectorAll('.window-start').forEach((label) => { label.textContent = `−${store.windowMs / 1000} 秒`; });
    if (this.route === 'overview') return;
    const p = parameters[this.route];
    const vm = store.displayViewModel;
    const scalar = vm.scalars[p.scalar];
    text('detail-node', `${p.node} · ${p.node === 'Node-A' ? vm.nodeAState : vm.nodeBState}`);
    text('detail-updated', `最近采集：${scalar.updatedTime ?? '--'}`);
    const records = store.displayHistory(p.scalar);
    text('history-range', `本次会话 · ${records.length} 条`);
    text('history-count', `${records.length} 条`);
    text('trend-start', records.length ? time(records[0].timestamp) : '--');
    text('trend-end', records.length ? time(records.at(-1)!.timestamp) : '--');
    document.getElementById('history-empty')!.hidden = records.some((record) => record.value !== null);
    document.getElementById('table-empty')!.hidden = records.length > 0;
    const body = document.getElementById('history-rows')!;
    const fragment = document.createDocumentFragment();
    for (const entry of records.slice(-12).reverse()) {
      const row = document.createElement('tr');
      for (const value of [time(entry.timestamp), valueText(entry), `${entry.validity} / ${entry.source}`]) {
        const cell = document.createElement('td');
        cell.textContent = value;
        row.append(cell);
      }
      fragment.append(row);
    }
    body.replaceChildren(fragment);
    document.querySelector<HTMLButtonElement>('#export-csv')!.disabled = !store.history.entries(p.scalar).length;
  }
}
