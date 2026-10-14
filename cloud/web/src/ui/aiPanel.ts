// 单一问答实例随路由装卸 DOM，令牌、会话和有界历史只保存在当前浏览器内存。
import type { MonitorStore } from '../state/monitorStore';
import type { ScalarChannel } from '../types';
import { modelLabel, validResponse, voiceLabels, type AiResponse } from './aiResponse';

export class AiPanel {
  private root = document.createElement('section');
  private pending: AbortController | null = null;
  private session = crypto.randomUUID().replaceAll('-', '');
  private gateway = '';
  private attached = false;

  constructor(private getGateway: () => string, private store: MonitorStore) {
    this.root.className = 'ai-page';
    this.root.setAttribute('aria-labelledby', 'ai-title');
    // 仅固定模板使用 innerHTML；问题、模型文字和来源统一走 textContent。
    this.root.innerHTML = `<header class="ai-heading"><div><span class="ai-eyebrow">MONITOR / ASSISTANT</span><h1 id="ai-title">AI 助手</h1><p>监护事实核对 · 数据解释 · 一般健康提示</p></div><a href="#/overview">返回监护总览 ↗</a></header>
      <div class="ai-layout"><section class="ai-conversation" aria-label="文字对话"><div class="ai-section-heading"><h2>文字对话</h2><span>只读监护 · 不控制采集</span></div>
      <div id="ai-history" class="ai-history" role="log" aria-label="问答记录" aria-live="polite" aria-relevant="additions text"><div id="ai-empty" class="ai-empty"><span class="ai-empty-mark" aria-hidden="true">↳</span><h2>从当前监护事实开始</h2><p>回答会保留数据来源与采集回执。模拟数据和历史回放会明确标识。</p><div class="ai-suggestions"><button type="button" data-question="现在心率多少">核对当前心率 ↗</button><button type="button" data-question="解释当前数据来源">解释数据来源 ↗</button><button type="button" data-question="久坐办公有哪些一般健康提示">一般健康提示 ↗</button></div></div></div>
      <form id="ai-form" class="ai-composer" novalidate><label for="ai-question">文字问题</label><textarea id="ai-question" maxlength="500" rows="3" required placeholder="输入问题，例如：解释当前监护数据来源"></textarea><div class="ai-compose-meta"><span>工程样机 · 不用于临床判断</span><span id="ai-count">0 / 500</span></div><p id="ai-status" role="status">准备提问 · 先填写独立 AI 令牌</p><div class="ai-actions"><button type="button" id="ai-cancel" disabled>取消回答</button><button type="submit" id="ai-send">发送问题 ↗</button></div></form></section>
      <aside class="ai-aside"><section class="ai-service"><div class="ai-section-heading"><h2>模型与访问</h2><span>独立 AI 通道</span></div><strong id="ai-mode">尚未收到回答</strong><p id="ai-model">模型使用状态以每条回答回执为准</p><details class="ai-access"><summary>AI 访问令牌</summary><label class="ai-label" for="ai-token">独立令牌 · 仅留在本页内存</label><input id="ai-token" type="password" form="ai-form" autocomplete="off" required placeholder="输入独立 AI 访问令牌"><p>与监护令牌分开，刷新后清除。</p></details></section>
      <section class="ai-current"><div class="ai-section-heading"><h2>当前监护事实</h2><span>共享监护连接</span></div><strong id="ai-gateway"></strong><p id="ai-source"></p><div id="ai-current-facts"></div><details class="ai-receipt"><summary>采集会话与序列</summary><div id="ai-current-receipts"></div></details><p class="ai-caption">实时快照独立于问答记录；冻结监护画面后，这里仍显示最新接收事实。</p></section>
      <section class="ai-playback"><div class="ai-section-heading"><h2>设备播报</h2><span>下行状态</span></div><label class="ai-voice"><input id="ai-voice" type="checkbox">允许下次回答下发播报</label><strong id="ai-voice-status">PAUSED · 设备播报已暂停</strong><p>Broker 接收确认不表示喇叭已播放。状态仅来自回答回执。</p></section></aside></div>`;
    // 将下行状态放在事实长列表前，较矮桌面也能直接看到播放未验证提示。
    this.root.querySelector('.ai-aside')!.insertBefore(this.element('ai-voice-status').closest('section')!, this.element('ai-current-facts').closest('section')!);
    this.element<HTMLButtonElement>('ai-cancel').onclick = () => this.cancel();
    this.element<HTMLFormElement>('ai-form').onsubmit = (event) => { event.preventDefault(); void this.send(); };
    const question = this.element<HTMLTextAreaElement>('ai-question');
    const updateCount = () => { this.element('ai-count').textContent = `${question.value.length} / 500`; };
    question.oninput = updateCount;
    this.root.querySelectorAll<HTMLButtonElement>('[data-question]').forEach((button) => {
      button.onclick = () => { question.value = button.dataset.question!; updateCount(); question.focus(); };
    });
    this.element<HTMLInputElement>('ai-voice').onchange = () => {
      // 开关只约束后续请求，不追改已有回执或取消已下发文本。
      this.status(this.element<HTMLInputElement>('ai-voice').checked ? '下次回答允许下发播报；当前设备播放状态未验证' : '新问题仅显示文字；既有下发不受此开关影响');
    };
    this.update();
  }

  public mount(container: HTMLElement): void { this.attached = true; container.append(this.root); this.update(); }
  public leave(): void { this.attached = false; this.cancel(); }
  private element<T extends HTMLElement>(id: string): T { return this.root.querySelector<T>(`#${id}`)!; }
  private status(text: string): void { this.element('ai-status').textContent = text; }
  private cancel(): void { this.pending?.abort(); }

  public update(): void {
    const gateway = this.getGateway();
    if (gateway !== this.gateway) {
      this.cancel(); this.gateway = gateway;
      this.session = crypto.randomUUID().replaceAll('-', '');
      this.root.querySelectorAll('.ai-turn').forEach((turn) => turn.remove());
      this.element('ai-empty').hidden = false;
      this.element<HTMLInputElement>('ai-voice').checked = false;
      this.element<HTMLTextAreaElement>('ai-question').value = '';
      this.element('ai-count').textContent = '0 / 500';
      this.element('ai-mode').textContent = '尚未收到回答';
      this.element('ai-model').textContent = '模型使用状态以每条回答回执为准';
      this.element('ai-voice-status').textContent = 'PAUSED · 设备播报已暂停';
      this.status('准备提问 · 网关会话已隔离');
    }
    if (!this.attached) return;
    const vm = this.store.currentViewModel;
    this.element('ai-gateway').textContent = gateway;
    this.element('ai-source').textContent = `${vm.sourceBanner} · ${this.store.connectionText}`;
    const fragment = document.createDocumentFragment();
    const receipts = document.createDocumentFragment();
    const labels: Record<ScalarChannel, string> = { HR: '心率', SpO2: '血氧', PR: '脉率', RR: '呼吸率', TEMP: '体温', NIBP: '血压' };
    for (const channel of ['HR', 'SpO2', 'PR', 'RR', 'TEMP', 'NIBP'] as ScalarChannel[]) {
      const reading = vm.scalars[channel];
      const signal = this.store.latestSnapshot?.streams.find((item) => (item.stream === 'SPO2' ? 'SpO2' : item.stream) === channel);
      const row = document.createElement('div'); row.className = 'ai-fact-row'; row.dataset.channel = channel;
      const title = document.createElement('span'); title.textContent = `${labels[channel]} ${channel}`;
      const value = document.createElement('strong'); value.textContent = `${reading.formatted}${reading.subFormatted ? ` / ${reading.subFormatted}` : ''} ${reading.unit}`;
      const meta = document.createElement('small'); meta.textContent = `${reading.validity} / ${reading.source}${signal?.synthetic ? ' / synthetic' : ''} · ${reading.nodeId} · ${reading.updatedTime ?? '--'}`;
      meta.title = signal ? `采集会话 ${signal.session_id} · 序列 ${signal.seq} · ${new Date(signal.timestamp).toISOString()}` : '尚无有效采集回执';
      const receipt = document.createElement('p'); receipt.textContent = `${channel} · ${meta.title}`; receipts.append(receipt);
      row.append(title, value, meta); fragment.append(row);
    }
    this.element('ai-current-facts').replaceChildren(fragment);
    this.element('ai-current-receipts').replaceChildren(receipts);
  }

  private receipt(data: AiResponse, turn: HTMLElement): void {
    const badge = document.createElement('strong'); badge.className = 'ai-turn-label'; badge.textContent = modelLabel(data);
    const details = document.createElement('details'); details.className = 'ai-receipt';
    const summary = document.createElement('summary'); summary.textContent = `回答依据 · ${data.facts.length} 项事实 · ${data.voice_status}`;
    details.append(summary);
    for (const fact of data.facts) {
      const row = document.createElement('p'); row.textContent = `${fact.label} · ${fact.node_id} · ${fact.validity} / ${fact.source}${fact.synthetic ? ' / synthetic' : ''} · ${new Date(fact.timestamp).toLocaleString()} · ${fact.session_id} #${fact.seq}`;
      details.append(row);
    }
    const provenance = document.createElement('p'); provenance.textContent = `回答 ${data.turn_id} · 会话 ${data.session_id} · 事实 ${data.fact_digest}`;
    const voice = document.createElement('p'); voice.textContent = `${data.voice_status} · ${voiceLabels[data.voice_status] ?? '播报状态未知'}`;
    details.append(provenance, voice); turn.append(badge, details);
    this.element('ai-mode').textContent = modelLabel(data);
    this.element('ai-model').textContent = data.model_evidence?.reported_model ?? data.model_evidence?.requested_model ?? '本轮无模型调用回执';
    this.element('ai-voice-status').textContent = `${data.voice_status} · ${voiceLabels[data.voice_status] ?? '播报状态未知'}`;
  }

  private async send(): Promise<void> {
    if (this.pending || !this.attached) return;
    this.update();
    const question = this.element<HTMLTextAreaElement>('ai-question').value.trim();
    const token = this.element<HTMLInputElement>('ai-token').value.trim();
    // 自行校验并展开令牌区，避免原生验证尝试聚焦折叠 details 内的输入框。
    if (!question || question.length > 500) { this.status('请输入 1–500 字的问题'); this.element('ai-question').focus(); return; }
    if (!token) {
      this.root.querySelector<HTMLDetailsElement>('.ai-access')!.open = true;
      this.status('请填写独立 AI 令牌'); this.element('ai-token').focus(); return;
    }
    const controller = new AbortController(); this.pending = controller;
    const gateway = this.gateway, session = this.session;
    const send = this.element<HTMLButtonElement>('ai-send'), cancel = this.element<HTMLButtonElement>('ai-cancel');
    send.disabled = true; cancel.disabled = false; this.status('正在回答…');
    // 请求开始即撤下上一轮模型标签；无回执时不能继承“本轮使用豆包”。
    this.element('ai-mode').textContent = '等待本轮模型回执';
    this.element('ai-model').textContent = '请求尚未返回，模型使用状态待确认';
    const turn = document.createElement('article'); turn.className = 'ai-turn';
    const prompt = document.createElement('h3'); prompt.textContent = `你 · ${question}`;
    const answer = document.createElement('p'); answer.className = 'ai-answer'; answer.textContent = '等待回答…';
    turn.append(prompt, answer);
    const history = this.element('ai-history'); this.element('ai-empty').hidden = true; history.append(turn);
    // 至多保存八轮；移除旧 DOM 一并释放长文本和回执，路由切换不增加实例。
    while (history.querySelectorAll('.ai-turn').length > 8) history.querySelector('.ai-turn')!.remove();
    history.scrollTop = history.scrollHeight;
    const timeout = window.setTimeout(() => controller.abort('timeout'), 15000);
    try {
      const response = await fetch('/medical-monitor/ai/api/v1/text', {
        method: 'POST', signal: controller.signal,
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
        body: JSON.stringify({ session_id: session, gateway_id: gateway, question, voice: this.element<HTMLInputElement>('ai-voice').checked }),
      });
      if (!response.ok) throw new Error(String(response.status));
      const data: unknown = await response.json();
      // 旧网关、旧会话、离页和已取消请求不得回填到当前页面。
      if (controller.signal.aborted || !this.attached || gateway !== this.getGateway() || session !== this.session) return;
      if (!validResponse(data, gateway, session)) throw new Error('schema');
      answer.textContent = data.answer; this.receipt(data, turn);
      this.status(`回答完成 · ${voiceLabels[data.voice_status] ?? '播报状态未知'}`);
      this.element<HTMLTextAreaElement>('ai-question').value = '';
      this.element('ai-count').textContent = '0 / 500';
    } catch (error) {
      if (gateway !== this.getGateway() || session !== this.session) return;
      const message = controller.signal.aborted ? controller.signal.reason === 'timeout' ? '回答超时，请重试' : '已取消回答'
        : error instanceof Error && error.message === '401' ? 'AI 访问验证失败，请核对独立令牌'
        : error instanceof Error && error.message === 'schema' ? '回答回执不匹配，已拒绝展示' : '回答失败，请检查 AI 服务后重试';
      answer.textContent = message; this.status(message);
      this.element('ai-mode').textContent = '本轮未取得有效模型回执';
      this.element('ai-model').textContent = '请查看本轮错误或取消状态';
    } finally {
      clearTimeout(timeout); this.pending = null; send.disabled = false; cancel.disabled = true;
      if (this.attached) history.scrollTop = history.scrollHeight;
    }
  }
}
