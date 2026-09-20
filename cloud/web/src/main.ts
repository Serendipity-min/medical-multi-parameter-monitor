import './style.css';

type Signal = { node_id: string; stream: string; timestamp: number; seq: number; session_id: string; validity: 'VALID' | 'INVALID' | 'STALE' | 'OFFLINE'; source: 'LIVE' | 'MOCK' | 'REPLAY'; synthetic: boolean; value: number | number[] | null; samples: number[]; sample_rate: number; unit: string };
type Snapshot = { gateway_id: string; gateway_state: string; nodes: Record<string, string>; streams: Signal[]; replay: Signal | null; event: { value: string } | null };
type Point = { t: number; y: number; gap?: boolean };
const pulseIcon = '<svg viewBox="0 0 32 32" fill="none" aria-hidden="true"><path d="M2 17h7l4-10 6 20 4-10h7" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"/></svg>';
const expandIcon = '<svg viewBox="0 0 20 20" fill="none" aria-hidden="true"><path d="M7 3H3v4m10-4h4v4M3 13v4h4m10-4v4h-4" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/></svg>';
const channels = ['HR', 'RR', 'NIBP', 'SpO2', 'PR', 'TEMP'];
const app = document.querySelector<HTMLDivElement>('#app')!;
app.innerHTML = `
<div class="app-shell">
<header class="app-header"><div class="identity"><span class="identity-mark">${pulseIcon}</span><div><h1>多参数监护</h1><p>心电 · 呼吸 · 血压 · 血氧</p></div><span class="simulation"><span id="source-banner">等待数据源</span></span></div><div class="header-actions"><div class="clock"><time id="clock">--:--:--</time><span id="today"></span></div><button id="open-access" class="button-primary">连接数据源</button><button id="fullscreen" class="button-quiet">${expandIcon}<span>全屏显示</span></button></div></header>
<main>
<section class="device-bar" aria-label="设备连接状态"><div class="device-identity"><span class="device-symbol">${pulseIcon}</span><div><span class="small-label">监护设备</span><label class="small-label" for="gateway-select">选择网关</label><select id="gateway-select"><option value="GW-DEV-001">模拟网关</option><option value="GW-C-001">Gateway-C 开发板</option></select><strong id="gateway-id">GW-DEV-001</strong></div></div><div class="nodes"><span id="gateway" class="node-chip">Gateway · OFFLINE</span><span id="node-a" class="node-chip">Node-A · OFFLINE</span><span id="node-b" class="node-chip">Node-B · OFFLINE</span></div><div class="connection"><span class="dot" id="connection-dot"></span><span id="connection">未连接</span></div></section>
<div class="monitor-frame">
<div class="monitor-topline"><div><span class="live-indicator"></span><strong>实时监护</strong><span id="mode">LIVE · 等待数据</span></div><div class="window-control" aria-label="波形显示窗口"><span>显示窗口</span><button data-window="8" aria-pressed="true">8 秒</button><button data-window="16" aria-pressed="false">16 秒</button></div></div>
<div class="monitor-layout">
<section class="module ecg-module" data-module="ECG" aria-labelledby="ecg-title"><div class="module-heading"><h2 id="ecg-title"><span class="channel-symbol">ECG</span>心电图</h2><span class="channel-note">连续心电波形</span></div><div class="signal-and-number"><div class="signal-area"><div class="trace-caption"><span>ECG</span><span id="quality-ECG">STALE</span></div><canvas id="wave-ECG" aria-label="ECG 心电模拟波形"></canvas><div class="wave-axis"><span class="window-start">−8 秒</span><span>相对幅值</span><span>当前</span></div><p class="empty-note" id="empty-ECG">连接数据源后显示心电波形</p></div><div class="numeric-panel"><span class="numeric-label">心率 <span>HR</span></span><strong id="value-HR" class="large-number">—</strong><span class="number-unit">bpm</span><span id="state-HR" class="quality">STALE</span></div></div><div class="module-footer"><span>来源 <strong>Node-B</strong></span><span>心电与呼吸同源采集</span></div></section>
<section class="module bp-module" data-module="NIBP" aria-labelledby="bp-title"><div class="module-heading"><h2 id="bp-title"><span class="channel-symbol">NIBP</span>血压</h2><span id="state-NIBP" class="quality">STALE</span></div><div class="pressure-reading" id="value-NIBP" aria-label="收缩压与舒张压"><div><span>收缩压 <b>SYS</b></span><strong id="pressure-sys">—</strong></div><span class="pressure-slash">/</span><div><span>舒张压 <b>DIA</b></span><strong id="pressure-dia">—</strong></div></div><div class="pressure-unit"><span>无创血压</span><strong>mmHg</strong></div><div class="pressure-details"><span>最新上传时间</span><time id="bp-updated">—</time></div><div class="module-footer"><span>来源 <strong>Node-A</strong></span><span>只读监护</span></div></section>
<section class="module resp-module" data-module="RESP" aria-labelledby="resp-title"><div class="module-heading"><h2 id="resp-title"><span class="channel-symbol">RESP</span>呼吸</h2><span class="algorithm-tag">RR 输出 · 以来源标签为准</span></div><div class="signal-and-number"><div class="signal-area"><div class="trace-caption"><span>呼吸波形</span><span id="quality-RESP">STALE</span></div><canvas id="wave-RESP" aria-label="RESP 呼吸模拟波形"></canvas><div class="wave-axis"><span class="window-start">−8 秒</span><span>相对幅值</span><span>当前</span></div><p class="empty-note" id="empty-RESP">等待有效呼吸数据</p></div><div class="numeric-panel"><span class="numeric-label">呼吸率 <span>RR</span></span><strong id="value-RR" class="large-number">—</strong><span class="number-unit">次/分</span><span id="state-RR" class="quality">STALE</span></div></div><div class="trend-strip"><div class="trend-heading"><span>呼吸率趋势 <small>算法输出</small></span><span id="rr-trend-status">等待 RR 数据</span></div><canvas id="trend-RR" aria-label="算法输出 RR 呼吸率趋势，最近 120 秒"></canvas><div class="trend-axis"><span>−120 秒</span><span>当前</span></div></div><div class="module-footer"><span>来源 <strong>Node-B</strong></span><span>正式算法待实测验证</span></div></section>
<section class="module spo2-module" data-module="SpO2" aria-labelledby="spo2-title"><div class="module-heading"><h2 id="spo2-title"><span class="channel-symbol">SpO₂</span>血氧</h2><span id="state-SpO2" class="quality">STALE</span></div><div class="oxygen-numbers"><div><span class="numeric-label">血氧饱和度</span><div class="oxygen-value"><strong id="value-SpO2" class="large-number">—</strong><span>%</span></div></div><div class="pulse-reading"><span class="numeric-label">脉率 <span>PR</span></span><strong id="value-PR">—</strong><span class="number-unit">bpm</span><span id="state-PR" class="quality">STALE</span></div></div><div class="signal-area pleth-area"><div class="trace-caption"><span>PPG 脉搏波</span><span id="quality-PPG">STALE</span></div><canvas id="wave-PPG" aria-label="PPG 血氧脉搏模拟波形"></canvas><p class="empty-note" id="empty-PPG">等待有效血氧数据</p></div><div class="module-footer"><span>来源 <strong>Node-A</strong></span><span>相对幅值</span></div></section>
</div><section class="temperature-strip" aria-label="体温"><span>体温 TEMP</span><strong id="value-TEMP">—</strong><span>°C</span><span id="state-TEMP">STALE</span><span id="event-status">无事件</span></section><div class="monitor-bottomline"><span id="updated">最后采集时间：—</span><span id="source-note">等待数据来源</span></div></div>
<section class="replay" aria-label="历史补传状态"><div><span class="replay-label">REPLAY</span><strong>历史补传</strong><span id="replay-status">尚未收到补传</span></div><p>补传独立显示，不覆盖当前监护</p></section><footer><span>工程样机 · 仅供系统联调，不用于临床判断</span><span>多参数监护 / P 第一阶段</span></footer>
</main></div>
<dialog id="access-dialog" aria-labelledby="access-title"><form id="access-form"><div class="dialog-heading"><div><span class="small-label">监护连接</span><h2 id="access-title">连接数据源</h2></div><button type="button" id="close-access" class="close-button" aria-label="关闭连接设置">×</button></div><p>输入只读访问令牌，订阅所选网关的监护数据。</p><label for="view-token">监护访问令牌</label><input id="view-token" type="password" autocomplete="off" placeholder="输入只读令牌" required><p id="access-message" role="status">令牌仅在当前页面内存中使用，刷新后需重新连接。</p><div class="dialog-actions"><button type="button" id="disconnect" class="button-quiet">断开连接</button><button type="submit" class="button-primary">连接监护</button></div></form></dialog>`;

const text = (id: string, value: string) => { document.getElementById(id)!.textContent = value; };
const accessDialog = document.querySelector<HTMLDialogElement>('#access-dialog')!;
const buffers: Record<string, Point[]> = { ECG: [], RESP: [], PPG: [] };
const colors: Record<string, string> = { ECG: '#5be0ad', RESP: '#e6c179', PPG: '#5dc6ef' };
let rrTrend: Point[] = [];
let socket: WebSocket | null = null;
let token = '';
let intentional = false;
let retryTimer = 0;
let retry = 0;
let lastMessage = 0;
let windowMs = 8000;
const seen: Record<string, string> = {};
const anchors: Record<string, { session: string; captured: number; local: number }> = {};
const gatewaySelect = document.querySelector<HTMLSelectElement>('#gateway-select')!;

function setNode(id: string, label: string, state: string) {
  text(id, `${label} · ${state}`);
  document.getElementById(id)!.classList.toggle('online', state === 'ONLINE');
}
function setScalar(name: string, signal: Signal | null, valid: boolean, quality = 'STALE') {
  const value = signal?.value ?? null;
  text(`state-${name}`, quality);
  if (name === 'NIBP') {
    // SYS/DIA 保持同一测量结果，不补算未上传的 MAP。
    text('pressure-sys', valid && Array.isArray(value) ? String(Math.round(value[0])) : '—');
    text('pressure-dia', valid && Array.isArray(value) ? String(Math.round(value[1])) : '—');
  } else text(`value-${name}`, valid && typeof value === 'number' ? (name === 'TEMP' ? value.toFixed(1) : String(Math.round(value))) : '—');
}
function clearLive(reason: string) {
  text('mode', reason); text('source-banner', '等待数据源'); text('source-note', '暂无有效数据');
  for (const name of channels) setScalar(name, null, false);
  for (const name of Object.keys(buffers)) {
    buffers[name] = []; text(`quality-${name}`, 'STALE');
    document.getElementById(`empty-${name}`)!.hidden = false;
  }
  rrTrend = []; text('rr-trend-status', '等待 RR 数据'); text('bp-updated', '—');
  text('updated', '最后采集时间：—'); text('replay-status', '尚未收到补传'); text('event-status', '无事件');
  for (const key of Object.keys(seen)) delete seen[key];
  for (const key of Object.keys(anchors)) delete anchors[key];
  setNode('gateway', 'Gateway', 'OFFLINE'); setNode('node-a', 'Node-A', 'OFFLINE'); setNode('node-b', 'Node-B', 'OFFLINE');
}
function render(data: Snapshot) {
  text('gateway-id', data.gateway_id);
  setNode('gateway', 'Gateway', data.gateway_state);
  setNode('node-a', 'Node-A', data.nodes['NODE-A']); setNode('node-b', 'Node-B', data.nodes['NODE-B']);
  const sources = [...new Set(data.streams.map(signal => signal.source))];
  text('mode', `${data.gateway_state} · ${sources.join(' / ') || '等待数据'}`);
  text('source-banner', sources.includes('MOCK') ? 'MOCK 模拟数据' : sources.join(' / ') || '等待数据源');
  text('source-note', sources.includes('MOCK') ? '含合成数据，用于系统联调' : '来源和有效性见各参数标签');
  const latest = Math.max(0, ...data.streams.map(signal => signal.timestamp));
  text('updated', `最后采集时间：${latest ? new Date(latest).toLocaleString('zh-CN', { hour12: false }) : '—'}`);
  const signals = new Map(data.streams.map(signal => [signal.stream === 'SPO2' ? 'SpO2' : signal.stream, signal]));
  for (const name of [...channels, ...Object.keys(buffers)]) {
    const signal = signals.get(name);
    const valid = signal?.validity === 'VALID';
    const quality = signal ? `${signal.validity} · ${signal.source}` : 'OFFLINE';
    const key = signal ? `${signal.session_id}:${signal.seq}:${signal.timestamp}` : '';
    if (name in buffers) {
      text(`quality-${name}`, quality);
      document.getElementById(`empty-${name}`)!.hidden = valid;
      if (!signal || !valid) { buffers[name] = []; delete seen[name]; delete anchors[name]; continue; }
      if (seen[name] !== key) {
        const arrival = performance.now();
        let anchor = anchors[name];
        if (!anchor || anchor.session !== signal.session_id || Math.abs(anchor.local + signal.timestamp - anchor.captured - arrival) > 5000) {
          anchor = anchors[name] = { session: signal.session_id, captured: signal.timestamp, local: arrival };
          buffers[name] = [];
        }
        // 逐流采集时间映射到单调时钟；网络到达抖动不改变波形时间轴。
        const end = anchor.local + signal.timestamp - anchor.captured;
        const start = end - (signal.samples.length - 1) * 1000 / signal.sample_rate;
        const previous = buffers[name].at(-1);
        if (previous && start <= previous.t) buffers[name] = [];
        buffers[name].push(...signal.samples.map((y, i) => ({ t: start + i*1000/signal.sample_rate, y, gap: i === 0 && !!previous && start-previous.t > 100 })));
        buffers[name] = buffers[name].filter(point => point.t >= end-16000).slice(-16000);
      }
    } else {
      setScalar(name, signal ?? null, valid, quality);
      if (name === 'NIBP') text('bp-updated', valid ? new Date(signal!.timestamp).toLocaleTimeString('zh-CN', {hour12:false}) : '—');
      if (name === 'RR') {
        if (!valid || typeof signal?.value !== 'number') { rrTrend = []; text('rr-trend-status', '无有效 RR 数据'); }
        else if (seen[name] !== key) {
          const now = performance.now();
          // 只积累当前有效 RR；REPLAY 从未进入 streams，不会污染趋势。
          rrTrend.push({t: now, y: signal.value});
          rrTrend = rrTrend.filter(point => point.t >= now-120000).slice(-121);
          text('rr-trend-status', `最近 120 秒 · ${signal.source}`);
        }
      }
    }
    seen[name] = key;
  }
  text('replay-status', data.replay ? `${data.replay.stream} #${data.replay.seq} · ${new Date(data.replay.timestamp).toLocaleTimeString('zh-CN', {hour12:false})}${data.replay.synthetic ? ' · 模拟补传' : ''}` : '尚未收到补传');
  text('event-status', data.event ? `事件：${data.event.value}` : '无事件');
}

function connect() {
  clearTimeout(retryTimer); intentional = false;
  const ws = new WebSocket(`${location.protocol === 'https:' ? 'wss:' : 'ws:'}//${location.host}/medical-monitor/ws/v1/monitor`);
  socket = ws; text('connection', '正在连接');
  ws.onopen = () => ws.send(JSON.stringify({ token, gateway_id: gatewaySelect.value }));
  ws.onmessage = event => {
    if (socket !== ws) return;
    try {
      const data = JSON.parse(event.data);
      if (data.type !== 'snapshot' || data.schema_version !== 1 || !Array.isArray(data.streams)) throw Error('Unexpected frame');
      retry = 0; lastMessage = performance.now();
      text('connection', '监护通道已连接'); text('open-access', '连接设置');
      document.getElementById('connection-dot')!.classList.add('online');
      text('access-message', '已连接，请查看每个参数的数据来源。'); render(data);
    } catch { ws.close(1008); }
  };
  ws.onclose = event => {
    if (socket !== ws) return;
    document.getElementById('connection-dot')!.classList.remove('online');
    clearLive('连接断开'); text('connection', '监护通道已断开');
    if (event.code === 1008) {
      token = ''; text('access-message', '访问令牌或来源校验失败，请重新输入。');
      if (!accessDialog.open) accessDialog.showModal();
      return;
    }
    if (!intentional && token) {
      const delay = Math.min(1000 * 2 ** retry++, 10000);
      text('connection', `${delay / 1000} 秒后自动重连`); retryTimer = window.setTimeout(connect, delay);
    }
  };
}
// 切换网关时重建订阅并清空旧读数，防止两个数据源混到同一监护屏。
gatewaySelect.onchange = () => {
  if (socket) { socket.onclose = null; socket.close(); }
  clearLive('切换网关'); lastMessage = 0;
  if (token) connect();
};
document.getElementById('open-access')!.onclick = () => accessDialog.showModal();
document.getElementById('close-access')!.onclick = () => accessDialog.close();
document.querySelector<HTMLFormElement>('#access-form')!.onsubmit = event => {
  event.preventDefault();
  const input = document.querySelector<HTMLInputElement>('#view-token')!;
  if (!input.value.trim()) return;
  token = input.value.trim(); input.value = '';
  if (socket) { socket.onclose = null; socket.close(); }
  // 新订阅清空旧计时，避免首帧到达前被上一会话的过期计时器关闭。
  clearLive('等待数据'); lastMessage = 0; retry = 0;
  accessDialog.close(); connect();
};
document.getElementById('disconnect')!.onclick = () => {
  intentional = true; token = ''; lastMessage = 0; clearTimeout(retryTimer); socket?.close();
  clearLive('已断开'); text('connection', '已断开'); text('open-access', '连接数据源'); accessDialog.close();
};
document.querySelectorAll<HTMLButtonElement>('[data-window]').forEach(button => {
  button.onclick = () => {
    windowMs = Number(button.dataset.window) * 1000;
    document.querySelectorAll<HTMLButtonElement>('[data-window]').forEach(item => item.setAttribute('aria-pressed', String(item === button)));
    document.querySelectorAll('.window-start').forEach(label => { label.textContent = `−${windowMs / 1000} 秒`; });
  };
});
document.getElementById('fullscreen')!.onclick = async () => {
  try {
    if (document.fullscreenElement) await document.exitFullscreen();
    else await document.documentElement.requestFullscreen();
  } catch { text('connection', '浏览器未允许全屏，可使用 F11'); }
};
document.addEventListener('fullscreenchange', () => {
  document.querySelector('#fullscreen span')!.textContent = document.fullscreenElement ? '退出全屏' : '全屏显示';
});
setInterval(() => {
  const now = new Date();
  text('clock', now.toLocaleTimeString('zh-CN', { hour12: false }));
  text('today', now.toLocaleDateString('zh-CN', { year: 'numeric', month: '2-digit', day: '2-digit' }));
  // 网络半开时前端仍会清空过期读数。
  if (lastMessage && performance.now() - lastMessage > 5000) {
    clearLive('连接超时'); if (socket?.readyState === WebSocket.OPEN) socket.close();
  }
}, 500);
function prepareCanvas(id: string) {
  const canvas = document.querySelector<HTMLCanvasElement>(`#${id}`)!;
  const width = canvas.clientWidth, height = canvas.clientHeight, dpr = devicePixelRatio || 1;
  if (canvas.width !== Math.round(width * dpr) || canvas.height !== Math.round(height * dpr)) {
    canvas.width = Math.round(width * dpr); canvas.height = Math.round(height * dpr);
  }
  const ctx = canvas.getContext('2d')!;
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0); ctx.clearRect(0, 0, width, height);
  return { ctx, width, height };
}
function draw() {
  const now = performance.now();
  for (const name of Object.keys(buffers)) {
    const { ctx, width, height } = prepareCanvas(`wave-${name}`);
    ctx.strokeStyle = '#20303d'; ctx.lineWidth = .6; ctx.beginPath();
    for (let x = 0; x < width; x += 32) { ctx.moveTo(x, 0); ctx.lineTo(x, height); }
    for (let y = 0; y < height; y += 28) { ctx.moveTo(0, y); ctx.lineTo(width, y); }
    ctx.stroke(); ctx.strokeStyle = colors[name]; ctx.lineWidth = 1.8; ctx.lineJoin = 'round'; ctx.beginPath();
    let started = false;
    for (const point of buffers[name]) {
      const x = width * (1 - (now - point.t) / windowMs), y = height * (name === 'RESP' ? .5 - point.y * .4 : .73 - point.y * .58);
      if (x < 0 || x > width) continue;
      if (!started || point.gap) { ctx.moveTo(x, y); started = true; } else ctx.lineTo(x, y);
    }
    ctx.stroke();
  }
  const { ctx, width, height } = prepareCanvas('trend-RR');
  // 自适应轴仅用于显示，不画临床正常区间，不把 RESP 幅值当作 RR。
  const values = rrTrend.map(p => p.y);
  const low = Math.floor(Math.min(10, ...values) / 5) * 5, high = Math.ceil(Math.max(20, ...values) / 5) * 5;
  const xAt = (t: number) => 32 + (width - 36) * (1 - (now - t) / 120000);
  const yAt = (value: number) => 8 + (height - 16) * (1 - (value - low) / (high - low));
  ctx.font = '10px "Segoe UI", sans-serif'; ctx.fillStyle = '#8295a4'; ctx.strokeStyle = '#233440'; ctx.lineWidth = .7;
  for (const value of [low, high]) {
    const y = yAt(value); ctx.fillText(String(value), 0, y + 3); ctx.beginPath(); ctx.moveTo(30, y); ctx.lineTo(width, y); ctx.stroke();
  }
  ctx.strokeStyle = colors.RESP; ctx.fillStyle = colors.RESP; ctx.lineWidth = 1.7; ctx.beginPath();
  let previous: Point | null = null;
  for (const point of rrTrend) {
    if (now - point.t > 120000) continue;
    if (!previous || point.t - previous.t > 2500) ctx.moveTo(xAt(point.t), yAt(point.y));
    else ctx.lineTo(xAt(point.t), yAt(point.y));
    previous = point;
  }
  ctx.stroke();
  if (previous && now - previous.t < 5000) { ctx.beginPath(); ctx.arc(xAt(previous.t), yAt(previous.y), 2.7, 0, Math.PI * 2); ctx.fill(); }
  requestAnimationFrame(draw);
}
requestAnimationFrame(draw);
