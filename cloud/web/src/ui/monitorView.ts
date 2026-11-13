// 仅静态模板进入 innerHTML；快照字段统一由组件写入 textContent。
import type { Route } from '../router/hashRouter';
import { ADULT_LIMITS, NIBP_LIMITS } from '../model/alarms';
import { trendChannels } from './parameters';
import type { ScalarChannel, WaveChannel } from '../types';

// 床位与患者信息为演示用虚构内容，系统未接入患者身份。
const BED = '01';
const PATIENT = '演示患者 · 成人';

const limits = (channel: ScalarChannel) => {
  const limit = ADULT_LIMITS[channel];
  return limit ? `<span class="limits"><b>${limit.high > 100 && channel === 'SpO2' ? 'OFF' : limit.high}</b><b>${limit.low}</b></span>` : '';
};

export function setupMonitorDOM(container: HTMLElement): void {
  container.innerHTML = `
    <div class="monitor-shell">
      <header class="topbar">
        <div class="bed-info"><span class="bed-no">${BED}<small>床</small></span><span class="patient">${PATIENT}</span></div>
        <div class="alarm-zone">
          <div id="alarm-phys" class="alarm-box" data-priority="none" role="status" aria-live="polite"></div>
          <div id="alarm-tech" class="alarm-box tech" data-priority="none" role="status" aria-live="polite"></div>
        </div>
        <div class="sys-info">
          <span id="demo-badge" class="demo-badge" hidden>演示模式 · 非真实数据</span>
          <span id="mock-badge" class="mock-badge" hidden title="数据帧标记为合成来源（当前网关固件对所有数据标记 MOCK）">MOCK 标记</span>
          <span id="frozen-badge" class="frozen-badge" hidden>已冻结</span>
          <span id="link-state" class="link-state" data-state="off"><i></i><span id="connection">未连接</span></span>
          <span class="clock"><time id="clock">--:--:--</time><span id="today"></span></span>
        </div>
        <div id="alarm-light" class="alarm-light" data-priority="none" aria-hidden="true"></div>
      </header>
      <main id="route-view" class="route-view"></main>
      <footer class="softkeys">
        <nav aria-label="页面">
          <a href="#/overview" data-route="overview">监护</a>
          <a href="#/trends" data-route="trends">趋势</a>
          <a href="#/ai" data-route="ai">AI 助手</a>
        </nav>
        <div class="keys">
          <button id="freeze" aria-pressed="false">冻结</button>
          <button id="demo-toggle" aria-pressed="false">演示</button>
          <button id="speak-toggle" aria-pressed="false" hidden title="用浏览器朗读云端播报，默认关闭">朗读播报</button>
          <button id="open-access">连接</button>
          <button id="fullscreen" aria-pressed="false">全屏</button>
        </div>
        <div class="footnote"><span id="received-at">最后数据 --</span><span>工程样机 · 非临床用途</span></div>
      </footer>
    </div>
    <dialog id="access-dialog" aria-labelledby="access-title"><form id="access-form">
      <div class="dialog-heading"><h2 id="access-title">连接监护数据</h2><button type="button" id="close-access" aria-label="关闭">×</button></div>
      <label for="view-token">访问令牌</label><input id="view-token" type="password" autocomplete="off" placeholder="输入只读访问令牌" required>
      <label class="check"><input id="remember-device" type="checkbox">记住此设备（仅在专用监护大屏上勾选）</label>
      <p id="access-message" role="status">令牌仅保存在当前页面内存中，刷新或断开后清除。</p>
      <div class="local-settings"><span>波形时长</span><button type="button" data-window="8" aria-pressed="true">8 秒</button><button type="button" data-window="16" aria-pressed="false">16 秒</button></div>
      <div class="dialog-actions"><button type="button" id="forget-device" hidden>忘记此设备</button><button type="button" id="disconnect">断开</button><button type="submit" class="primary">连接</button></div>
    </form></dialog>
    <dialog id="connection-error-dialog" class="connection-error" role="alertdialog" aria-labelledby="connection-error-title" aria-describedby="connection-error-message">
      <div class="dialog-heading"><h2 id="connection-error-title">连接失败</h2><button type="button" id="close-connection-error" aria-label="关闭">×</button></div>
      <p id="connection-error-message"></p>
      <div class="dialog-actions"><button type="button" id="retry-access" class="primary">重新输入令牌</button></div>
    </dialog>`;
}

function waveRow(channel: WaveChannel, label: string, note: string): string {
  return `<section class="wave ${channel.toLowerCase()}" data-wave="${channel}">
    <div class="wave-label"><b>${label}</b><span>${note}</span></div>
    <canvas id="wave-${channel}" aria-label="${label} 波形"></canvas>
    <span class="wave-empty" id="empty-${channel}">无波形</span>
  </section>`;
}

function param(channel: ScalarChannel, label: string, unit: string, extra = ''): string {
  return `<section class="param ${channel.toLowerCase()}" data-param="${channel}">
    <div class="param-head"><b>${label}</b><span>${unit}</span></div>
    ${limits(channel)}
    <strong class="param-value" id="value-${channel}">--</strong>
    <span class="param-note" id="note-${channel}"></span>
    ${extra}
  </section>`;
}

export function renderRoute(route: Route, container: HTMLElement): void {
  container.className = `route-view route-${route}`;
  document.querySelectorAll<HTMLElement>('[data-route]').forEach((link) => {
    if (link.dataset.route === route) link.setAttribute('aria-current', 'page');
    else link.removeAttribute('aria-current');
  });
  if (route === 'ai') { container.replaceChildren(); return; }
  if (route === 'trends') {
    container.innerHTML = `<div class="trends">
      <nav class="trend-tabs" aria-label="参数">${trendChannels.map((item, index) => `<button type="button" data-trend="${item.channel}" aria-pressed="${index === 0}" style="--c:${item.color}">${item.label}</button>`).join('')}</nav>
      <section class="trend-chart"><div class="trend-head"><b id="trend-title">${trendChannels[0].label}</b><span id="history-range">本次会话 · 0 条</span></div>
        <div class="trend-canvas"><canvas id="session-trend" data-channel="${trendChannels[0].channel}" aria-label="本次会话趋势"></canvas><span class="wave-empty" id="history-empty">暂无记录</span></div>
        <div class="trend-axis"><span id="trend-start">--</span><span>仅本次浏览器会话，最多保留 60 分钟</span><span id="trend-end">--</span></div></section>
      <section class="trend-table"><div class="trend-head"><b>记录</b><span id="history-count">0 条</span></div>
        <div class="table-wrap"><table><thead><tr><th>时间</th><th>数值</th><th>状态</th></tr></thead><tbody id="history-rows"></tbody></table><p id="table-empty" class="table-empty">暂无记录</p></div>
        <div class="table-actions"><button id="export-csv" disabled>导出 CSV</button><span id="export-status" role="status"></span></div></section>
    </div>`;
    return;
  }
  const sys = NIBP_LIMITS.sys, dia = NIBP_LIMITS.dia;
  container.innerHTML = `<div class="overview">
    <div id="standby" class="standby" hidden><div class="standby-box">
      <strong id="standby-title">未连接</strong><span id="standby-text"></span>
      <div class="standby-actions"><button type="button" id="standby-connect" class="primary">连接</button><button type="button" id="standby-demo">演示模式</button></div>
    </div></div>
    <section id="broadcast" class="broadcast" data-level="info" hidden aria-label="AI 播报">
      <b>AI 播报</b><time id="broadcast-time">--</time>
      <p id="broadcast-text" role="status" aria-live="polite"></p>
      <details id="broadcast-more"><summary>历史</summary><ol id="broadcast-history"></ol></details>
    </section>
    <div class="waves">
      ${waveRow('ECG', 'ECG I', 'RA–LA')}
      ${waveRow('PPG', 'Pleth', 'SpO₂')}
      ${waveRow('RESP', 'Resp', '阻抗')}
    </div>
    <div class="params">
      ${param('HR', 'HR', 'bpm')}
      ${param('SpO2', 'SpO₂', '%', `<div class="sub-param pr"><span>PR</span><strong id="value-PR">--</strong><small>bpm</small></div>`)}
      ${param('RR', 'RR', 'rpm')}
    </div>
    <div class="bottom">
      <section class="param nibp" data-param="NIBP">
        <div class="param-head"><b>NIBP</b><span>mmHg</span></div>
        <span class="limits nibp-limits"><b>${sys.high}/${dia.high}</b><b>${sys.low}/${dia.low}</b></span>
        <div class="nibp-value"><strong id="pressure-sys">--</strong><span>/</span><strong id="pressure-dia">--</strong></div>
        <span class="param-note"><span id="note-NIBP"></span><span>测量时间 <time id="bp-updated">--</time></span></span>
      </section>
      <section class="nibp-list"><div class="param-head"><b>NIBP 记录</b><span>最近 4 次</span></div>
        <table><thead><tr><th>时间</th><th>SYS/DIA</th></tr></thead><tbody id="nibp-rows"></tbody></table><p id="nibp-empty" class="table-empty">本次会话暂无测量</p></section>
      ${param('TEMP', 'T 体表', '°C')}
    </div>
  </div>`;
}
