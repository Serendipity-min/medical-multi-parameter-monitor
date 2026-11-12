// 监护总览的 AI 播报条与“朗读播报”软键。播报文本只写入 textContent。

import { BroadcastSpeaker, readBroadcast } from '../model/broadcast';
import type { Broadcast, Snapshot } from '../types';

const time = (ts: number) => new Date(ts).toLocaleTimeString('zh-CN', { hour12: false });

export class BroadcastBar {
  private speaker = new BroadcastSpeaker();
  private key = document.querySelector<HTMLButtonElement>('#speak-toggle')!;
  private rendered = '';

  constructor() {
    this.key.onclick = () => {
      this.speaker.setEnabled(!this.speaker.enabled);
      this.key.setAttribute('aria-pressed', String(this.speaker.enabled));
    };
  }

  public update(snapshot: Snapshot | null): void {
    const state = readBroadcast(snapshot);
    this.key.hidden = !state.supported || !this.speaker.available;
    this.speaker.offer(state.latest);

    const bar = document.getElementById('broadcast');
    if (!bar) return;
    bar.hidden = !state.supported || (!state.latest && !state.history.length);
    // 仅在内容变化时重绘，避免每 500 ms 刷新时收起已展开的历史。
    const signature = JSON.stringify([state.latest?.id ?? null, state.history.map((item) => item.id)]);
    if (bar.hidden || signature === this.rendered) return;
    this.rendered = signature;

    bar.dataset.level = state.latest?.level ?? 'info';
    document.getElementById('broadcast-time')!.textContent = state.latest ? time(state.latest.ts) : '--';
    const text = document.getElementById('broadcast-text')!;
    if (state.latest) {
      const note = document.createElement('small');
      note.textContent = state.latest.disclaimer;
      text.replaceChildren(state.latest.text, note);
    } else {
      text.textContent = '暂无新播报';
    }
    document.getElementById('broadcast-history')!.replaceChildren(...state.history.map(historyItem));
  }

  // 路由切换会重建总览 DOM，下一次更新需要整体重绘。
  public reset(): void {
    this.rendered = '';
  }
}

function historyItem(item: Broadcast): HTMLLIElement {
  const row = document.createElement('li');
  const stamp = document.createElement('time');
  stamp.textContent = time(item.ts);
  const note = document.createElement('span');
  note.textContent = item.disclaimer;
  row.append(stamp, item.text, note);
  return row;
}
