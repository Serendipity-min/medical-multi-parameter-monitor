// 参数数值面板：数值、无效原因和报警闪烁状态。有效性用文字说明，颜色只表示通道与报警。

import type { Alarm } from '../model/alarms';
import type { HistoryEntry } from '../state/sessionHistory';
import type { MonitorViewModel, ScalarChannel, ScalarReading, WaveChannel } from '../types';

const NOTE: Record<string, string> = { INVALID: '信号无效', STALE: '无数据', OFFLINE: '离线' };
const time = (timestamp: number) => new Date(timestamp).toLocaleTimeString('zh-CN', { hour12: false });

export class NumericsView {
  private setText(id: string, text: string): void {
    const el = document.getElementById(id);
    if (el) el.textContent = text;
  }

  private connected = false;

  private note(reading: ScalarReading): string {
    if (!this.connected) return '';
    return reading.validity === 'VALID' ? '' : NOTE[reading.validity] ?? reading.validity;
  }

  public update(vm: MonitorViewModel, connected: boolean, alarms: readonly Alarm[], nibpHistory: readonly HistoryEntry[]): void {
    this.connected = connected;
    for (const channel of ['HR', 'SpO2', 'PR', 'RR', 'TEMP'] as ScalarChannel[]) {
      const reading = vm.scalars[channel];
      this.setText(`value-${channel}`, reading.formatted);
      this.setText(`note-${channel}`, this.note(reading));
    }

    const nibp = vm.scalars.NIBP;
    this.setText('pressure-sys', nibp.formatted);
    this.setText('pressure-dia', nibp.subFormatted ?? '--');
    this.setText('bp-updated', nibp.validity === 'VALID' ? nibp.updatedTime ?? '--' : '--');
    this.setText('note-NIBP', this.note(nibp));

    // 报警参数整块反色闪烁，颜色取该参数最高优先级；PR 报警显示在 SpO₂ 块上。
    const byChannel = new Map<ScalarChannel, Alarm>();
    for (const alarm of alarms) if (alarm.channel && !byChannel.has(alarm.channel)) byChannel.set(alarm.channel, alarm);
    document.querySelectorAll<HTMLElement>('[data-param]').forEach((el) => {
      const channel = el.dataset.param as ScalarChannel;
      const alarm = byChannel.get(channel) ?? (channel === 'SpO2' ? byChannel.get('PR') : undefined);
      el.dataset.alarm = alarm?.priority ?? 'none';
      el.dataset.validity = vm.scalars[channel].validity;
    });

    for (const channel of ['ECG', 'PPG', 'RESP'] as WaveChannel[]) {
      const wave = vm.waves[channel];
      const empty = document.getElementById(`empty-${channel}`);
      if (empty) {
        empty.hidden = wave.validity === 'VALID';
        empty.textContent = !connected ? '未连接' : wave.validity === 'OFFLINE' ? '无波形' : wave.validity === 'STALE' ? '等待波形' : '信号无效';
      }
    }

    const body = document.getElementById('nibp-rows');
    if (body) {
      const rows = nibpHistory.filter((entry) => Array.isArray(entry.value)).slice(-4).reverse();
      const fragment = document.createDocumentFragment();
      for (const entry of rows) {
        const row = document.createElement('tr');
        for (const value of [time(entry.timestamp), (entry.value as number[]).map(Math.round).join(' / ')]) {
          const cell = document.createElement('td');
          cell.textContent = value;
          row.append(cell);
        }
        fragment.append(row);
      }
      body.replaceChildren(fragment);
      const empty = document.getElementById('nibp-empty');
      if (empty) empty.hidden = rows.length > 0;
    }
  }
}
