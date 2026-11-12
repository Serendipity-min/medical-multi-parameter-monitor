// 云端播报（WP-AY）：校验快照中的播报字段，并管理浏览器朗读。文本由后端规则引擎生成，页面不改写措辞。

import type { Broadcast, Snapshot } from '../types';

// 与后端一致：最新一条只在 10 分钟内有效。
export const BROADCAST_TTL_MS = 10 * 60 * 1000;
const HISTORY_LIMIT = 10;

export interface BroadcastState {
  supported: boolean;
  latest: Broadcast | null;
  history: Broadcast[];
}

export function validBroadcast(value: unknown): value is Broadcast {
  if (!value || typeof value !== 'object') return false;
  const item = value as Record<string, unknown>;
  return typeof item.id === 'string' && item.id !== '' && typeof item.ts === 'number' && Number.isFinite(item.ts)
    && typeof item.param === 'string' && (item.level === 'info' || item.level === 'notice')
    && typeof item.text === 'string' && item.text !== '' && typeof item.disclaimer === 'string';
}

// 字段缺失视为后端不支持；畸形条目丢弃，不影响监护数据显示。
export function readBroadcast(snapshot: Snapshot | null): BroadcastState {
  if (!snapshot || !('broadcast' in snapshot)) return { supported: false, latest: null, history: [] };
  const now = snapshot.server_time ?? Date.now();
  const latest = validBroadcast(snapshot.broadcast) && now - snapshot.broadcast.ts <= BROADCAST_TTL_MS ? snapshot.broadcast : null;
  const history = Array.isArray(snapshot.broadcast_history)
    ? snapshot.broadcast_history.filter(validBroadcast).sort((a, b) => b.ts - a.ts).slice(0, HISTORY_LIMIT)
    : [];
  return { supported: true, latest, history };
}

// 后端重启后 id 从 1 重新编号，去重键须带上时间。
export const broadcastKey = (item: Broadcast): string => `${item.id}:${item.ts}`;

export const spokenText = (item: Broadcast): string => `${item.text}${item.disclaimer ? `。${item.disclaimer}` : ''}`;

// 朗读默认关闭。每条播报只读一次；开启前已出现的播报不补读。
export class BroadcastSpeaker {
  public enabled = false;
  private seen = new Set<string>();

  constructor(private synth: SpeechSynthesis | undefined = globalThis.speechSynthesis) {}

  public get available(): boolean {
    return !!this.synth && typeof SpeechSynthesisUtterance !== 'undefined';
  }

  // 必须在用户点击中调用：浏览器只在用户手势后允许页面发声，这里先读一句确认语解锁。
  public setEnabled(on: boolean): void {
    if (!this.available) return;
    this.enabled = on;
    this.synth!.cancel();
    if (on) this.say('播报朗读已开启');
  }

  public offer(item: Broadcast | null): void {
    if (!item || this.seen.has(broadcastKey(item))) return;
    this.seen.add(broadcastKey(item));
    if (this.enabled && this.available) this.say(spokenText(item));
  }

  private say(text: string): void {
    const utterance = new SpeechSynthesisUtterance(text);
    utterance.lang = 'zh-CN';
    this.synth!.speak(utterance);
  }
}
