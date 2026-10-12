// AI 旁路面板只传问题和网关身份；监护读数由服务端只读获取，令牌仅留在内存。
export class AiPanel {
  private dialog: HTMLDialogElement;
  private pending: AbortController | null = null;
  private session = crypto.randomUUID().replaceAll('-', '');
  private gateway = '';

  constructor(private getGateway: () => string) {
    const button = document.createElement('button');
    button.id = 'open-ai';
    button.textContent = 'AI 文字问答';
    document.querySelector('.app-header')!.append(button);
    this.dialog = document.createElement('dialog');
    this.dialog.className = 'ai-panel';
    this.dialog.setAttribute('aria-labelledby', 'ai-title');
    // 固定模板使用 innerHTML；模型答案、事实和问题一律写 textContent。
    this.dialog.innerHTML = `<div class="dialog-heading"><div><h2 id="ai-title">AI 文字问答</h2><p>解释监护读数与项目知识</p></div><button type="button" id="ai-close" aria-label="关闭 AI 问答">×</button></div>
      <div class="ai-source"><strong id="ai-gateway"></strong><span id="ai-mode">等待 AI 服务</span></div>
      <form id="ai-form"><label for="ai-token">AI 访问令牌</label><input id="ai-token" type="password" autocomplete="off" required placeholder="输入 AI 服务的独立访问令牌">
      <div id="ai-history" class="ai-history" role="log" aria-label="问答记录"><p class="muted">可输入“现在心率多少”或“解释当前数据来源”。模拟与历史数据会明确标注。</p></div>
      <label for="ai-question">文字问题</label><textarea id="ai-question" maxlength="500" rows="3" required placeholder="输入问题"></textarea>
      <label class="ai-voice"><input id="ai-voice" type="checkbox">开启设备播报</label><p class="muted">暂停后，新问题仅显示文字。下发确认不表示喇叭已播完。</p>
      <p id="ai-status" role="status" aria-live="polite">准备提问</p><div class="dialog-actions"><button type="button" id="ai-cancel" disabled>取消回答</button><button type="submit" id="ai-send" class="button-primary">发送问题</button></div></form>`;
    document.body.append(this.dialog);
    button.onclick = () => { this.changeGateway(); this.dialog.showModal(); };
    this.element<HTMLButtonElement>('ai-close').onclick = () => this.dialog.close();
    this.dialog.onclose = () => this.cancel();
    this.element<HTMLButtonElement>('ai-cancel').onclick = () => this.cancel();
    this.element<HTMLFormElement>('ai-form').onsubmit = (event) => { event.preventDefault(); void this.send(); };
    this.element<HTMLInputElement>('ai-voice').onchange = () => {
      this.status(this.element<HTMLInputElement>('ai-voice').checked ? '设备播报已开启；等待下次回答' : '设备播报已暂停');
    };
  }

  private element<T extends HTMLElement>(id: string): T { return this.dialog.querySelector<T>(`#${id}`)!; }
  private status(text: string): void { this.element('ai-status').textContent = text; }
  private changeGateway(): void {
    const gateway = this.getGateway();
    if (gateway !== this.gateway) {
      this.cancel(); this.gateway = gateway;
      this.session = crypto.randomUUID().replaceAll('-', '');
      this.element('ai-history').replaceChildren();
      this.element<HTMLInputElement>('ai-voice').checked = false;
    }
    this.element('ai-gateway').textContent = gateway;
  }
  private cancel(): void {
    if (this.pending) { this.pending.abort(); this.status('已取消回答'); }
  }
  private async send(): Promise<void> {
    if (this.pending) return;
    this.changeGateway();
    const controller = new AbortController(); this.pending = controller;
    const send = this.element<HTMLButtonElement>('ai-send'), cancel = this.element<HTMLButtonElement>('ai-cancel');
    send.disabled = true; cancel.disabled = false; this.status('正在回答…');
    const timeout = window.setTimeout(() => controller.abort('timeout'), 15000);
    const question = this.element<HTMLTextAreaElement>('ai-question').value.trim(), gateway = this.gateway;
    try {
      const response = await fetch('/medical-monitor/ai/api/v1/text', {
        method: 'POST', signal: controller.signal,
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${this.element<HTMLInputElement>('ai-token').value}` },
        body: JSON.stringify({ session_id: this.session, gateway_id: gateway, question, voice: this.element<HTMLInputElement>('ai-voice').checked }),
      });
      if (!response.ok) throw new Error(String(response.status));
      const data = await response.json();
      // 等待期间切换了网关或取消时，旧回答不得进入当前记录。
      if (controller.signal.aborted || gateway !== this.getGateway()) return;
      if (data.gateway_id !== gateway || data.session_id !== this.session || !Array.isArray(data.facts) || typeof data.answer !== 'string') throw new Error('schema');
      const turn = document.createElement('article'); turn.className = 'ai-turn';
      const prompt = document.createElement('h3'); prompt.textContent = question;
      const answer = document.createElement('p'); answer.className = 'ai-answer'; answer.textContent = data.answer;
      const facts = document.createElement('div'); facts.className = 'ai-facts';
      for (const fact of data.facts) {
        const row = document.createElement('p');
        row.textContent = `${fact.label} · ${fact.node_id} · ${fact.validity} / ${fact.source}${fact.synthetic ? ' / synthetic' : ''} · ${new Date(fact.timestamp).toLocaleTimeString()} · ${fact.session_id} #${fact.seq}`;
        facts.append(row);
      }
      const provenance = document.createElement('small'); provenance.textContent = `回答 ${data.turn_id} · 事实 ${data.fact_digest}`;
      turn.append(prompt, answer, facts, provenance);
      const history = this.element('ai-history'); history.append(turn);
      while (history.children.length > 8) history.firstElementChild!.remove();
      history.scrollTop = history.scrollHeight;
      this.element('ai-mode').textContent = data.model_mode === 'MOCK' ? 'MOCK · 未完成真实豆包接入' : '豆包 · 经核验解释';
      const voiceLabels: Record<string, string> = { PAUSED: '设备播报已暂停', DISABLED: '设备播报服务未启用', BROKER_PUBACK_ONLY: '下发已被 Broker 接收，播报状态未验证', RATE_LIMITED: '播报频率受限', DOWNLINK_FAILED: '播报下发失败' };
      this.status(`回答完成 · ${voiceLabels[data.voice_status] ?? '播报状态未知'}`);
    } catch (error) {
      if (controller.signal.aborted) this.status(controller.signal.reason === 'timeout' ? '回答超时，请重试' : '已取消回答');
      else this.status(error instanceof Error && error.message === '401' ? 'AI 访问验证失败，请核对独立令牌' : '回答失败，请检查 AI 服务后重试');
    } finally {
      clearTimeout(timeout); this.pending = null; send.disabled = false; cancel.disabled = true;
    }
  }
}
