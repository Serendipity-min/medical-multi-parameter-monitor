import './style.css';

type Signal = { quality: 'VALID' | 'INVALID' | 'STALE'; value: number | number[] | null; samples: number[]; sample_rate: number };
type Frame = { mode: 'LIVE' | 'REPLAY'; seq: number; session_id: string; captured_at: number; nodes: Record<string, { online: boolean; signals: Record<string, Signal> }> };
type Snapshot = { gateway_online: boolean; live_fresh: boolean; gateway_id: string; live: Frame | null; replay: Frame | null };
const app = document.querySelector<HTMLDivElement>('#app')!;
const channels = [ ['HR', '心率', 'bpm'], ['SpO2', '血氧饱和度', '%'], ['RR', '呼吸率', '次/分'], ['PR', '脉率', 'bpm'], ['NIBP', '无创血压 · SYS / DIA', 'mmHg'], ['TEMP', '体温', '°C'] ];
app.innerHTML = `
  <header><div class="brand"><span class="brand-icon">＋</span><div><p class="eyebrow">MULTI-PARAMETER MONITOR</p><h1>多参数监护工作台</h1></div></div><span class="simulation">SIMULATION · 模拟数据</span></header>
  <main><section class="toolbar"><div><span class="dot" id="connection-dot"></span><strong id="connection">未连接</strong><span class="subtle" id="gateway-id">GW-DEV-001</span></div><div class="node-list"><span id="gateway">Gateway · OFFLINE</span><span id="node-a">Node-A · OFFLINE</span><span id="node-b">Node-B · OFFLINE</span></div></section>
  <section class="access"><form id="access-form"><label for="view-token">监护访问令牌</label><input id="view-token" type="password" autocomplete="off" placeholder="输入只读令牌"><button type="submit">连接监护</button><button type="button" id="disconnect" class="secondary">断开</button></form><p id="access-message">令牌仅在当前页面内存中使用。刷新页面后请重新连接。</p></section>
  <section class="section-heading"><div><p class="eyebrow">REAL-TIME TELEMETRY</p><h2>实时监护 <span id="mode">LIVE · 等待数据</span></h2></div><p id="updated">最后采集时间：—</p></section>
  <div class="monitor-grid"><section class="wave-panel">${['ECG', 'PPG', 'RESP'].map((name, i) => `<article class="wave wave-${name.toLowerCase()}"><div class="wave-label"><h3>${name} <span>${['心电', '光电容积脉搏波', '呼吸阻抗'][i]}</span></h3><span id="quality-${name}">STALE</span></div><canvas id="wave-${name}" aria-label="${name} 模拟波形"></canvas></article>`).join('')}<p class="wave-foot">8 秒显示窗口 · 信号缺失处断开绘制 · 幅值为模拟相对单位</p></section>
  <section class="metrics">${channels.map(([name, label, unit]) => `<article class="metric" data-channel="${name}"><p>${label}<span>${name}</span></p><div><strong id="value-${name}">—</strong><span class="unit">${unit}</span></div><small id="state-${name}">STALE</small></article>`).join('')}</section></div>
  <section class="replay"><div><h3>历史补传 <span>REPLAY</span></h3><p>补传只在此处标记，不覆盖实时数值、波形或节点状态。</p></div><p id="replay-status">尚未收到补传</p></section>
  <footer><span>工程联调环境 · 所有信号均为 MOCK，不用于临床判断</span><span>PHASE 01 / CLOUD FIRST</span></footer></main>`;

const text = (id: string, value: string) => { document.getElementById(id)!.textContent = value; };
let socket: WebSocket | null = null;
let token = '';
let intentional = false;
let retryTimer = 0;
let retry = 0;
let lastMessage = 0;
let latest: Snapshot | null = null;
let lastKey = '';
let lastSeq = -1;
let lastSession = '';
type Point = { t: number; y: number };
const buffers: Record<string, Point[]> = { ECG: [], PPG: [], RESP: [] };
const colors: Record<string, string> = { ECG: '#54e3b0', PPG: '#65cafa', RESP: '#edc778' };

function clearLive(reason: string) {
  text('mode', `LIVE · ${reason}`);
  for (const [name] of channels) { text(`value-${name}`, '—'); text(`state-${name}`, 'STALE'); }
  for (const name of Object.keys(buffers)) { buffers[name] = []; text(`quality-${name}`, 'STALE'); }
  text('gateway', 'Gateway · OFFLINE'); text('node-a', 'Node-A · OFFLINE'); text('node-b', 'Node-B · OFFLINE');
}

function render(data: Snapshot) {
  latest = data;
  text('gateway-id', data.gateway_id);
  text('gateway', `Gateway · ${data.gateway_online ? 'ONLINE' : 'OFFLINE'}`);
  text('mode', `LIVE · ${data.live_fresh ? '实时模拟' : 'STALE / 等待实时数据'}`);
  const frame = data.live;
  if (frame) {
    text('updated', `最后采集时间：${new Date(frame.captured_at * 1000).toLocaleString('zh-CN', { hour12: false })}`);
    const key = `${frame.session_id}:${frame.seq}`;
    // 断线、跳帧或会话变化时清空窗口，避免在缺失区间伪造连续波形。
    if (key !== lastKey && (frame.session_id !== lastSession || frame.seq !== lastSeq + 1)) {
      for (const name of Object.keys(buffers)) buffers[name] = [];
    }
    for (const [nodeId, node] of Object.entries(frame.nodes)) {
      text(nodeId === 'NODE-A' ? 'node-a' : 'node-b', `${nodeId === 'NODE-A' ? 'Node-A' : 'Node-B'} · ${node.online && data.live_fresh ? 'ONLINE' : 'OFFLINE'}`);
      for (const [name, signal] of Object.entries(node.signals)) {
        const valid = data.live_fresh && node.online && signal.quality === 'VALID';
        const quality = !data.live_fresh || !node.online ? 'STALE' : signal.quality;
        if (name in buffers) {
          text(`quality-${name}`, quality);
          if (!valid) buffers[name] = [];
          else if (key !== lastKey) {
            const end = performance.now();
            buffers[name].push(...signal.samples.map((y, i) => ({t: end - (signal.samples.length - 1 - i) * 1000 / signal.sample_rate, y})));
            // 缓冲区有时间和点数双重上限，后台标签页也不会无限增长。
            buffers[name] = buffers[name].filter(p => p.t >= end - 8000).slice(-8000);
          }
        } else {
          const value = signal.value;
          text(`value-${name}`, valid && value !== null ? Array.isArray(value) ? value.join(' / ') : name === 'TEMP' ? value.toFixed(1) : Math.round(value).toString() : '—');
          text(`state-${name}`, quality);
        }
      }
    }
    lastKey = key; lastSeq = frame.seq; lastSession = frame.session_id;
  } else clearLive('等待数据');
  // 即使从未收到 LIVE，也必须显示连接与 REPLAY 独立状态。
  text('gateway', `Gateway · ${data.gateway_online ? 'ONLINE' : 'OFFLINE'}`);
  if (data.replay) text('replay-status', `已收补传 #${data.replay.seq} · 采集于 ${new Date(data.replay.captured_at * 1000).toLocaleString('zh-CN', {hour12: false})}`);
  else text('replay-status', '尚未收到补传');
}

function connect() {
  clearTimeout(retryTimer);
  intentional = false;
  const ws = new WebSocket(`${location.protocol === 'https:' ? 'wss:' : 'ws:'}//${location.host}/medical-monitor/ws/v1/monitor`);
  socket = ws;
  text('connection', '正在连接');
  ws.onopen = () => ws.send(JSON.stringify({ token }));
  ws.onmessage = event => {
    if (socket !== ws) return;
    try {
      const data = JSON.parse(event.data);
      if (data.protocol !== 'MVIEW/1' || data.simulation !== true) throw Error('Unexpected frame');
      retry = 0; lastMessage = performance.now();
      text('connection', '监护通道已连接');
      document.getElementById('connection-dot')!.classList.add('online');
      text('access-message', '已连接 · SIMULATION 模式');
      render(data);
    } catch { ws.close(1008); }
  };
  ws.onclose = event => {
    if (socket !== ws) return;
    document.getElementById('connection-dot')!.classList.remove('online');
    clearLive('连接断开');
    text('connection', '监护通道已断开');
    if (event.code === 1008) { token = ''; text('access-message', '访问令牌或来源校验失败，请重新输入。'); return; }
    if (!intentional && token) {
      const delay = Math.min(1000 * 2 ** retry++, 10000);
      text('access-message', `${delay / 1000} 秒后自动重连…`);
      retryTimer = window.setTimeout(connect, delay);
    }
  };
}

document.querySelector<HTMLFormElement>('#access-form')!.onsubmit = event => {
  event.preventDefault();
  const input = document.querySelector<HTMLInputElement>('#view-token')!;
  if (!input.value.trim()) return;
  token = input.value.trim(); input.value = '';
  if (socket) { socket.onclose = null; socket.close(); }
  clearLive('等待数据'); lastKey = ''; retry = 0; connect();
};
document.getElementById('disconnect')!.onclick = () => {
  intentional = true; token = ''; clearTimeout(retryTimer); socket?.close(); clearLive('已断开');
};

setInterval(() => {
  // 浏览器收不到服务器状态时自行失效，不能让正常数值一直停留在屏幕上。
  if (lastMessage && performance.now() - lastMessage > 5000) {
    clearLive('连接超时');
    if (socket?.readyState === WebSocket.OPEN) socket.close();
  }
}, 500);

function draw() {
  const now = performance.now();
  for (const name of Object.keys(buffers)) {
    const canvas = document.querySelector<HTMLCanvasElement>(`#wave-${name}`)!;
    const width = canvas.clientWidth, height = canvas.clientHeight, dpr = devicePixelRatio || 1;
    if (canvas.width !== Math.round(width * dpr) || canvas.height !== Math.round(height * dpr)) {
      canvas.width = Math.round(width * dpr); canvas.height = Math.round(height * dpr);
    }
    const ctx = canvas.getContext('2d')!;
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0); ctx.clearRect(0, 0, width, height);
    ctx.strokeStyle = '#1a3039'; ctx.lineWidth = 0.5; ctx.beginPath();
    for (let x = 0; x < width; x += 28) { ctx.moveTo(x, 0); ctx.lineTo(x, height); }
    for (let y = 0; y < height; y += 28) { ctx.moveTo(0, y); ctx.lineTo(width, y); }
    ctx.stroke(); ctx.strokeStyle = colors[name]; ctx.lineWidth = 1.7; ctx.beginPath();
    let started = false;
    for (const point of buffers[name]) {
      const x = width * (1 - (now - point.t) / 8000), y = height * (0.65 - point.y * 0.43);
      if (x < 0) continue;
      if (!started) { ctx.moveTo(x, y); started = true; } else ctx.lineTo(x, y);
    }
    ctx.stroke();
  }
  requestAnimationFrame(draw);
}
requestAnimationFrame(draw);
