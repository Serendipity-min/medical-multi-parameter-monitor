// 仅静态模板进入 innerHTML；快照字段统一由组件写入 textContent。
import { routes, type Route } from '../router/hashRouter';
import { parameters, type Parameter } from './parameters';
import type { ScalarChannel, WaveChannel } from '../types';

const icons: Record<Route | 'settings', string> = {
  overview: '<rect x="3" y="3" width="7" height="7"/><rect x="14" y="3" width="7" height="7"/><rect x="3" y="14" width="7" height="7"/><rect x="14" y="14" width="7" height="7"/>',
  ecg: '<path d="M2 12h5l3-8 4 16 3-8h5"/>',
  spo2: '<path d="M12 2C9 7 5 10 5 15a7 7 0 0 0 14 0c0-5-4-8-7-13Z"/>',
  resp: '<path d="M12 3v9m0-4C7 3 3 9 3 15s6 6 7 2l2-5 2 5c1 4 7 4 7-2S17 3 12 8"/>',
  nibp: '<path d="M4 5h10v14H4zM14 9h3a4 4 0 0 1 4 4v3m-17-6h10"/>',
  temp: '<path d="M9 14V5a3 3 0 0 1 6 0v9a5 5 0 1 1-6 0Zm3-7v10m5-10h4m-4 4h3"/>',
  settings: '<path d="m12 2 3 3h4v4l3 3-3 3v4h-4l-3 3-3-3H5v-4l-3-3 3-3V5h4Z"/><circle cx="12" cy="12" r="3"/>',
};
const labels: Record<Route, string> = { overview: '监护总览', temp: '体温', ecg: '心电', spo2: '血氧', resp: '呼吸', nibp: '血压' };
const svg = (key: Route | 'settings') => `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${icons[key]}</svg>`;

export function setupMonitorDOM(container: HTMLElement): void {
  container.innerHTML = `
    <div class="app-shell">
      <header class="app-header">
        <a class="brand" href="#/overview">${svg('ecg')}<span>多参数监护<small>工程样机 · 未接入患者身份</small></span></a>
        <div class="system-identity"><strong id="gateway-id">GW-DEV-001</strong><span id="connection">未连接</span><i id="connection-dot"></i></div>
        <div class="nodes-status"><span id="gateway" class="node-chip">Gateway · OFFLINE</span><span id="node-a" class="node-chip">Node-A · OFFLINE</span><span id="node-b" class="node-chip">Node-B · OFFLINE</span></div>
        <strong id="source-banner" class="source-banner">等待数据源</strong>
        <div class="system-clock"><time id="clock">--:--:--</time><span id="today"></span></div>
        <button id="open-access" class="button-quiet">连接数据源</button>
      </header>
      <div class="context-bar"><span id="mode">等待数据</span><span id="received-at">最后通信：--</span><strong id="frozen-status" role="status" hidden>DISPLAY FROZEN / 本地显示已冻结</strong></div>
      <main id="route-view" class="monitor-main"></main>
      <div class="technical-strip"><span id="replay-status">尚未收到补传</span><span id="event-status">无事件</span><span id="source-note">暂无有效数据</span><span id="updated">最后采集时间：--</span></div>
      <nav class="bottom-nav" aria-label="监护页面">
        ${routes.map((route) => `<a href="#/${route}" data-route="${route}">${svg(route)}<span>${labels[route]}</span></a>`).join('')}
        <button id="open-settings">${svg('settings')}<span>连接设置</span></button>
        <button id="freeze" aria-pressed="false"><b class="freeze-icon">Ⅱ</b><span>冻结显示</span></button>
      </nav>
    </div>
    <dialog id="access-dialog" aria-labelledby="access-title"><form id="access-form">
      <div class="dialog-heading"><h2 id="access-title">连接与本地显示设置</h2><button type="button" id="close-access" aria-label="关闭连接设置">×</button></div>
      <label for="gateway-select">数据源网关</label><select id="gateway-select"><option value="GW-DEV-001">模拟网关 GW-DEV-001</option><option value="GW-C-001">真机网关 GW-C-001</option></select>
      <label for="view-token">只读访问令牌</label><input id="view-token" type="password" autocomplete="off" placeholder="输入当前网关的访问令牌" required>
      <p id="access-message" role="status">令牌仅保存在当前浏览器内存中，刷新或断开后清除。</p>
      <div class="local-settings"><span>波形显示窗口</span><button type="button" data-window="8" aria-pressed="true">8 秒</button><button type="button" data-window="16" aria-pressed="false">16 秒</button><button type="button" id="fullscreen"><span>全屏显示</span></button></div>
      <p class="muted">设置仅作用于浏览器显示与订阅；工程样机仅供系统联调，不用于临床判断。</p>
      <div class="dialog-actions"><button type="button" id="disconnect">断开连接</button><button type="submit" class="button-primary">验证并连接</button></div>
    </form></dialog>`;
}

function number(channel: ScalarChannel): string {
  return channel === 'NIBP'
    ? '<div class="pressure-reading" id="value-NIBP"><div><small>SYS</small><strong id="pressure-sys">--</strong></div><span>/</span><div><small>DIA</small><strong id="pressure-dia">--</strong></div></div>'
    : `<strong id="value-${channel}" class="vital-number">--</strong>`;
}

function reading(p: Parameter): string {
  const unit = p.scalar === 'NIBP' ? 'mmHg' : p.scalar === 'TEMP' ? '°C' : p.scalar === 'SpO2' ? '%' : p.scalar === 'RR' ? '次/分' : 'bpm';
  const title = { HR: '心率 HR', SpO2: '血氧 SpO₂', RR: '呼吸率 RR · 算法输出', NIBP: '无创血压 NIBP', TEMP: '红外体温 TEMP', PR: '脉率 PR' }[p.scalar];
  return `<div class="reading"><div class="panel-heading"><strong>${title}</strong><span>${unit}</span></div>${number(p.scalar)}<div class="reading-meta"><span id="state-${p.scalar}">STALE · OFFLINE</span><span>${p.node}</span></div>${p.scalar === 'NIBP' ? '<span class="measurement-time">最近测量 <time id="bp-updated">--</time></span>' : ''}</div>${p.scalar === 'SpO2' ? '<div class="pr-reading"><span>脉率 PR <small>bpm</small></span><strong id="value-PR">--</strong><small id="state-PR">STALE · OFFLINE</small></div>' : ''}`;
}

function wave(channel: WaveChannel, route: Route, detail = false): string {
  const name = channel === 'ECG' ? 'ECG · 单导联 RA–LA' : channel === 'PPG' ? 'PLETH · 容积脉搏波' : 'RESP · 阻抗呼吸';
  return `<section class="wave-panel ${route}" data-module="${channel === 'PPG' ? 'SpO2' : channel}"><div class="panel-heading"><a href="#/${route}"><strong>${name}</strong>${detail ? '' : '<span class="open-mark">↗</span>'}</a><span id="quality-${channel}">STALE</span></div><a class="canvas-container" href="#/${route}" aria-label="${name}详情"><canvas id="wave-${channel}" aria-label="${name}，相对幅值"></canvas><span class="empty-note" id="empty-${channel}">等待有效波形</span></a><div class="wave-axis"><span class="window-start">−8 秒</span><span>相对幅值 · ${channel === 'ECG' ? '250' : '50'} Hz</span><span>当前</span></div></section>`;
}

function trend(channel: ScalarChannel, title: string): string {
  return `<section class="trend-panel"><div class="panel-heading"><strong>${title}</strong><span id="history-range">本次会话 · 尚无记录</span></div><div class="trend-canvas-box"><canvas id="session-trend" data-channel="${channel}" aria-label="${title}，本次会话实际收到的记录"></canvas><span class="empty-note" id="history-empty">收到新记录后显示趋势</span></div><div class="wave-axis"><span id="trend-start">--</span><span>仅本次浏览器会话 · 最多保留 60 分钟</span><span id="trend-end">--</span></div></section>`;
}

export function renderRoute(route: Route, container: HTMLElement): void {
  container.className = `monitor-main route-${route}`;
  document.querySelectorAll<HTMLElement>('[data-route]').forEach((link) => {
    if (link.dataset.route === route) link.setAttribute('aria-current', 'page');
    else link.removeAttribute('aria-current');
  });
  if (route === 'overview') {
    container.innerHTML = `<div class="overview-layout"><div class="overview-waves">${wave('ECG', 'ecg')}${wave('PPG', 'spo2')}${wave('RESP', 'resp')}</div><div class="overview-numerics">${['ecg', 'spo2', 'resp', 'nibp', 'temp'].map((key) => {
      const p = parameters[key as keyof typeof parameters];
      return `<a href="#/${p.route}" class="numeric-tile ${p.route}" aria-label="打开${p.title}">${reading(p)}</a>`;
    }).join('')}</div></div>`;
    return;
  }
  const p = parameters[route];
  container.innerHTML = `<div class="detail-heading ${route}"><div>${svg(route)}<h1>${p.title}<small>${p.english}</small></h1><span>${p.subtitle}</span></div><a href="#/overview">返回总览 ↗</a></div>
    <div class="detail-layout ${route}"><div class="detail-main">
      <section class="detail-vital"><div class="detail-reading">${reading(p)}</div><div class="sensor-summary"><span>采集配置</span><strong>${p.device}</strong><span>${p.subtitle}</span><div><span id="detail-node">${p.node} · OFFLINE</span><span id="detail-updated">最近采集：--</span></div></div></section>
      ${p.wave ? wave(p.wave, route, true) : ''}
      ${trend(p.scalar, p.scalar === 'NIBP' ? 'SYS / DIA · 离散测量记录' : `${p.scalar} · 本次会话趋势`)}
      <div class="detail-note"><span>${p.wave ? '波形采用相对幅值显示，不提供临床物理标定。' : '仅显示已接收测量结果。'}</span><span>有效性来自数据帧，不表示传感器自检通过。</span></div>
    </div><aside class="detail-aside"><section class="device-panel"><div class="panel-heading"><strong>采集信息</strong><span>静态配置说明</span></div><dl>${p.facts.map(([key, value]) => `<div><dt>${key}</dt><dd>${value}</dd></div>`).join('')}</dl><p>节点在线只代表通信状态。</p></section>
      <section class="history-panel"><div class="panel-heading"><strong>最近记录</strong><span id="history-count">0 条</span></div><p class="history-caption">本次会话 · 断线保留 / 切换网关清空</p><div class="history-table-wrap"><table><thead><tr><th>采集时间</th><th>数值</th><th>有效性 / 来源</th></tr></thead><tbody id="history-rows"></tbody></table><p id="table-empty">尚未收到记录</p></div><button id="export-csv" disabled>导出本次会话 CSV</button><span id="export-status" role="status"></span></section>
    </aside></div>`;
}
