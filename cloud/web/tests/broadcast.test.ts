// 播报字段校验与朗读去重回归：只用合成快照和替身语音接口，不连接网络或设备。
import assert from 'node:assert/strict';
import test from 'node:test';
import { BROADCAST_TTL_MS, BroadcastSpeaker, readBroadcast, spokenText } from '../src/model/broadcast';
import type { Broadcast, Snapshot } from '../src/types';

const item = (overrides: Partial<Broadcast> = {}): Broadcast => ({ id: 'b1', ts: 1_000_000, param: 'TEMP', level: 'info',
  text: '当前体表温度约 31.2 °C', disclaimer: '仅供参考，不构成医疗建议，如有不适请咨询医生', ...overrides });
const snapshot = (extra: Partial<Snapshot> = {}): Snapshot => ({ type: 'snapshot', schema_version: 1, gateway_id: 'GW-C-001',
  gateway_state: 'ONLINE', nodes: {}, server_time: 1_000_000, streams: [], replay: null, event: null, ...extra });

test('未升级的后端不带播报字段时隐藏，null 表示支持但暂无播报', () => {
  assert.deepEqual(readBroadcast(null), { supported: false, latest: null, history: [] });
  assert.equal(readBroadcast(snapshot()).supported, false);
  const empty = readBroadcast(snapshot({ broadcast: null, broadcast_history: [] }));
  assert.equal(empty.supported, true); assert.equal(empty.latest, null);
});

test('最新播报超过 10 分钟不再显示，历史按时间倒序且最多 10 条', () => {
  const fresh = readBroadcast(snapshot({ broadcast: item(), server_time: 1_000_000 + BROADCAST_TTL_MS }));
  assert.equal(fresh.latest?.id, 'b1');
  assert.equal(readBroadcast(snapshot({ broadcast: item(), server_time: 1_000_001 + BROADCAST_TTL_MS })).latest, null);
  const history = Array.from({ length: 12 }, (_, i) => item({ id: `h${i}`, ts: i }));
  const state = readBroadcast(snapshot({ broadcast: null, broadcast_history: history }));
  assert.equal(state.history.length, 10); assert.equal(state.history[0].id, 'h11');
});

test('畸形播报被丢弃，不影响快照其余部分', () => {
  const bad = [null, {}, item({ level: 'high' as Broadcast['level'] }), item({ text: '' }), item({ ts: Number.NaN }), item({ id: 3 as unknown as string })];
  for (const value of bad) assert.equal(readBroadcast(snapshot({ broadcast: value as Broadcast })).latest, null);
  const state = readBroadcast(snapshot({ broadcast: null, broadcast_history: [...bad, item()] as Broadcast[] }));
  assert.deepEqual(state.history.map((entry) => entry.id), ['b1']);
});

test('朗读默认关闭；开启后每条只读一次，开启前已出现的不补读，后端重启后同 id 新播报照读，关闭即停止', () => {
  const spoken: string[] = [];
  let cancelled = 0;
  const saved = Object.getOwnPropertyDescriptor(globalThis, 'SpeechSynthesisUtterance');
  Object.defineProperty(globalThis, 'SpeechSynthesisUtterance', { value: class { lang = ''; constructor(public text: string) {} }, configurable: true });
  try {
    const synth = { speak: (u: { text: string }) => spoken.push(u.text), cancel: () => { cancelled++; } } as unknown as SpeechSynthesis;
    const speaker = new BroadcastSpeaker(synth);
    assert.equal(speaker.enabled, false);
    speaker.offer(item({ id: 'old' }));
    assert.deepEqual(spoken, []);
    speaker.setEnabled(true);
    speaker.offer(item({ id: 'old' }));
    speaker.offer(item({ id: 'new' }));
    speaker.offer(item({ id: 'new' }));
    speaker.offer(item({ id: 'new', ts: 2_000_000 }));
    assert.deepEqual(spoken, ['播报朗读已开启', spokenText(item({ id: 'new' })), spokenText(item({ id: 'new' }))]);
    assert.match(spoken[1], /体表温度.*仅供参考/);
    assert.equal(spokenText(item({ text: '请检查指夹佩戴后复测。' })), '请检查指夹佩戴后复测。仅供参考，不构成医疗建议，如有不适请咨询医生');
    speaker.setEnabled(false);
    speaker.offer(item({ id: 'later' }));
    assert.equal(spoken.length, 3); assert.equal(cancelled, 1);
  } finally {
    if (saved) Object.defineProperty(globalThis, 'SpeechSynthesisUtterance', saved);
    else delete (globalThis as Record<string, unknown>).SpeechSynthesisUtterance;
  }
});

test('浏览器不支持朗读时开关无效', () => {
  const speaker = new BroadcastSpeaker(undefined);
  assert.equal(speaker.available, false);
  speaker.setEnabled(true);
  assert.equal(speaker.enabled, false);
});

test('没有中文语音或朗读出错时给出状态，有中文语音时指定该语音', () => {
  const saved = Object.getOwnPropertyDescriptor(globalThis, 'SpeechSynthesisUtterance');
  type Fake = { text: string; voice?: { lang: string }; onerror?: (event: { error: string }) => void };
  const made: Fake[] = [];
  Object.defineProperty(globalThis, 'SpeechSynthesisUtterance', { value: class { lang = ''; constructor(public text: string) { made.push(this as unknown as Fake); } }, configurable: true });
  try {
    for (const [voices, expected] of [[[{ lang: 'en-US' }], 'no-voice'], [[{ lang: 'en-US' }, { lang: 'zh-CN' }], null]] as const) {
      const statuses: string[] = [];
      const synth = { speak: () => {}, cancel: () => {}, getVoices: () => voices } as unknown as SpeechSynthesis;
      new BroadcastSpeaker(synth, (status) => statuses.push(status)).setEnabled(true);
      assert.equal(statuses.includes('no-voice'), expected === 'no-voice');
      if (!expected) assert.equal(made.at(-1)!.voice?.lang, 'zh-CN');
    }
    const statuses: string[] = [];
    new BroadcastSpeaker({ speak: () => {}, cancel: () => {}, getVoices: () => [] } as unknown as SpeechSynthesis, (status) => statuses.push(status)).setEnabled(true);
    made.at(-1)!.onerror!({ error: 'not-allowed' });
    made.at(-1)!.onerror!({ error: 'interrupted' });
    assert.deepEqual(statuses, ['failed']);
  } finally {
    if (saved) Object.defineProperty(globalThis, 'SpeechSynthesisUtterance', saved);
    else delete (globalThis as Record<string, unknown>).SpeechSynthesisUtterance;
  }
});
