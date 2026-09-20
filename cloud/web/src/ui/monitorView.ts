// 主监护屏 DOM 装配层：构建专业医疗监护仪 1080p 零滚动主视图与 Dialog 骨架。

const pulseIcon =
  '<svg viewBox="0 0 32 32" fill="none" aria-hidden="true"><path d="M2 17h7l4-10 6 20 4-10h7" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"/></svg>';
const expandIcon =
  '<svg viewBox="0 0 20 20" fill="none" aria-hidden="true"><path d="M7 3H3v4m10-4h4v4M3 13v4h4m10-4v4h-4" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/></svg>';

export function setupMonitorDOM(container: HTMLElement): void {
  container.innerHTML = `
<div class="app-shell">
  <!-- 顶部系统状态栏 -->
  <header class="app-header">
    <div class="header-left">
      <div class="brand-badge">
        <span class="brand-icon">${pulseIcon}</span>
        <div class="brand-text">
          <h1>多参数监护</h1>
          <span class="brand-sub">床旁/中央大屏视图</span>
        </div>
      </div>
      <div class="simulation-badge">
        <span id="source-banner">等待数据源</span>
      </div>
      <div class="gateway-controller">
        <label for="gateway-select" class="visually-hidden">选择网关</label>
        <select id="gateway-select" title="切换数据源网关">
          <option value="GW-DEV-001">模拟网关 GW-DEV-001</option>
          <option value="GW-C-001">真机网关 GW-C-001</option>
        </select>
        <strong id="gateway-id" class="gateway-tag">GW-DEV-001</strong>
      </div>
      <div class="nodes-status">
        <span id="gateway" class="node-chip">Gateway · OFFLINE</span>
        <span id="node-a" class="node-chip">Node-A · OFFLINE</span>
        <span id="node-b" class="node-chip">Node-B · OFFLINE</span>
      </div>
    </div>

    <div class="header-right">
      <div class="connection-status">
        <span class="dot" id="connection-dot"></span>
        <span id="connection">未连接</span>
      </div>
      <div class="mode-tag" id="mode">LIVE · 等待数据</div>
      <div class="window-control" aria-label="走纸视窗">
        <button data-window="8" class="window-btn active" aria-pressed="true">8 秒</button>
        <button data-window="16" class="window-btn" aria-pressed="false">16 秒</button>
      </div>
      <div class="system-clock">
        <time id="clock">--:--:--</time>
        <span id="today"></span>
      </div>
      <div class="header-actions">
        <button id="open-access" class="button-primary">连接数据源</button>
        <button id="fullscreen" class="button-quiet" title="切换全屏">${expandIcon}<span>全屏显示</span></button>
      </div>
    </div>
  </header>

  <!-- 中央四大核心生理参数成行布局 (70% 波形 + 30% 读数) -->
  <main class="monitor-main">
    <div class="monitor-layout">

      <!-- 行 1: 心电图与心率 (ECG Lead II & HR) -->
      <section class="param-row ecg-row" data-module="ECG" aria-labelledby="ecg-title">
        <div class="waveform-cell">
          <div class="trace-header">
            <div class="channel-title">
              <span class="channel-dot ecg-dot"></span>
              <strong id="ecg-title">ECG II</strong>
              <span class="trace-scale">1.0x &nbsp; 25mm/s</span>
            </div>
            <span id="quality-ECG" class="quality-badge">STALE</span>
          </div>
          <div class="canvas-container">
            <canvas id="wave-ECG" aria-label="ECG 心电模拟波形"></canvas>
            <p class="empty-note" id="empty-ECG">连接数据源后显示心电波形</p>
          </div>
          <div class="wave-axis">
            <span class="window-start">−8 秒</span>
            <span>相对幅值 (mV)</span>
            <span>当前</span>
          </div>
        </div>
        <div class="numeric-cell ecg-numeric">
          <div class="numeric-header">
            <span class="numeric-title">心率 HR</span>
            <span class="numeric-unit">bpm</span>
          </div>
          <div class="numeric-body">
            <strong id="value-HR" class="huge-number">—</strong>
          </div>
          <div class="numeric-footer">
            <span id="state-HR" class="state-tag">STALE</span>
            <span class="source-tag">Node-B · 心电同源</span>
          </div>
        </div>
      </section>

      <!-- 行 2: 血氧容积波与血氧饱和度/脉率 (PPG & SpO2/PR) -->
      <section class="param-row spo2-row" data-module="SpO2" aria-labelledby="spo2-title">
        <div class="waveform-cell">
          <div class="trace-header">
            <div class="channel-title">
              <span class="channel-dot spo2-dot"></span>
              <strong id="spo2-title">PLETH</strong>
              <span class="trace-scale">PPG 容积脉搏波</span>
            </div>
            <span id="quality-PPG" class="quality-badge">STALE</span>
          </div>
          <div class="canvas-container">
            <canvas id="wave-PPG" aria-label="PPG 血氧脉搏模拟波形"></canvas>
            <p class="empty-note" id="empty-PPG">等待有效血氧数据</p>
          </div>
          <div class="wave-axis">
            <span class="window-start">−8 秒</span>
            <span>脉搏容积变化</span>
            <span>当前</span>
          </div>
        </div>
        <div class="numeric-cell spo2-numeric">
          <div class="dual-numeric">
            <div class="numeric-subcell">
              <div class="numeric-header">
                <span class="numeric-title">血氧 SpO₂</span>
                <span class="numeric-unit">%</span>
              </div>
              <div class="numeric-body">
                <strong id="value-SpO2" class="huge-number">—</strong>
              </div>
              <div class="numeric-footer">
                <span id="state-SpO2" class="state-tag">STALE</span>
              </div>
            </div>
            <div class="numeric-divider"></div>
            <div class="numeric-subcell">
              <div class="numeric-header">
                <span class="numeric-title">脉率 PR</span>
                <span class="numeric-unit">bpm</span>
              </div>
              <div class="numeric-body">
                <strong id="value-PR" class="large-number">—</strong>
              </div>
              <div class="numeric-footer">
                <span id="state-PR" class="state-tag">STALE</span>
              </div>
            </div>
          </div>
        </div>
      </section>

      <!-- 行 3: 呼吸阻抗波与呼吸率/趋势 (RESP & RR) -->
      <section class="param-row resp-row" data-module="RESP" aria-labelledby="resp-title">
        <div class="waveform-cell resp-waveform">
          <div class="trace-header">
            <div class="channel-title">
              <span class="channel-dot resp-dot"></span>
              <strong id="resp-title">RESP</strong>
              <span class="trace-scale">胸阻抗呼吸波</span>
            </div>
            <span id="quality-RESP" class="quality-badge">STALE</span>
          </div>
          <div class="canvas-container resp-canvas-box">
            <canvas id="wave-RESP" aria-label="RESP 呼吸模拟波形"></canvas>
            <p class="empty-note" id="empty-RESP">等待有效呼吸数据</p>
          </div>
          <div class="trend-strip">
            <div class="trend-header">
              <span class="trend-title">RR 算法趋势 (最近 120 秒)</span>
              <span id="rr-trend-status" class="trend-status">等待 RR 数据</span>
            </div>
            <div class="trend-canvas-box">
              <canvas id="trend-RR" aria-label="算法输出 RR 呼吸率趋势，最近 120 秒"></canvas>
            </div>
            <div class="trend-axis">
              <span>−120 秒</span>
              <span>当前</span>
            </div>
          </div>
        </div>
        <div class="numeric-cell resp-numeric">
          <div class="numeric-header">
            <span class="numeric-title">呼吸率 RR</span>
            <span class="numeric-unit">次/分</span>
          </div>
          <div class="numeric-body">
            <strong id="value-RR" class="huge-number">—</strong>
          </div>
          <div class="numeric-footer">
            <span id="state-RR" class="state-tag">STALE</span>
            <span class="source-tag">算法输出 · Node-B</span>
          </div>
        </div>
      </section>

      <!-- 行 4: 辅助系统状态 (REPLAY/EVENT/TEMP) 与血压 (NIBP) -->
      <section class="param-row aux-row" data-module="NIBP" aria-labelledby="bp-title">
        <div class="aux-cell">
          <div class="aux-cards">
            <!-- 历史补传独立专区 -->
            <div class="aux-card replay-card" aria-label="历史补传状态">
              <div class="aux-card-title">
                <span class="replay-label">REPLAY</span>
                <strong>历史补传状态</strong>
              </div>
              <p id="replay-status" class="aux-card-content">尚未收到补传</p>
            </div>

            <!-- 系统事件专区 -->
            <div class="aux-card event-card" aria-label="系统与技术事件">
              <div class="aux-card-title">
                <span class="event-icon">⚠</span>
                <strong>系统技术事件</strong>
              </div>
              <p id="event-status" class="aux-card-content">无事件</p>
            </div>

            <!-- 体温卡片 (TEMP) -->
            <div class="aux-card temp-card" aria-label="体温">
              <div class="aux-card-title">
                <span class="channel-dot temp-dot"></span>
                <strong>体温 TEMP</strong>
                <span id="state-TEMP" class="quality-badge">STALE</span>
              </div>
              <div class="temp-body">
                <strong id="value-TEMP" class="large-number">—</strong>
                <span class="temp-unit">°C</span>
              </div>
              <span class="temp-source">红外测温 · Node-B</span>
            </div>
          </div>
        </div>

        <div class="numeric-cell nibp-numeric">
          <div class="numeric-header">
            <div class="channel-title">
              <span class="channel-dot nibp-dot"></span>
              <strong id="bp-title">NIBP 血压</strong>
            </div>
            <span class="numeric-unit">mmHg</span>
          </div>
          <div class="pressure-reading" id="value-NIBP" aria-label="收缩压与舒张压">
            <div class="pressure-item">
              <span class="pressure-sublabel">SYS 收缩</span>
              <strong id="pressure-sys" class="huge-number">—</strong>
            </div>
            <span class="pressure-slash">/</span>
            <div class="pressure-item">
              <span class="pressure-sublabel">DIA 舒张</span>
              <strong id="pressure-dia" class="huge-number">—</strong>
            </div>
          </div>
          <div class="pressure-footer">
            <span id="state-NIBP" class="state-tag">STALE</span>
            <div class="pressure-time">
              <span>上次测量:</span>
              <time id="bp-updated">—</time>
            </div>
          </div>
        </div>
      </section>

    </div>
  </main>

  <!-- 底部时间戳与工程声明栏 -->
  <footer class="app-footer">
    <span id="updated">最后采集时间：—</span>
    <span id="source-note">等待数据来源</span>
    <span class="disclaimer">工程样机 · 仅供系统联调与测试，不用于临床判断</span>
  </footer>
</div>

<!-- 访问令牌鉴权对话框 -->
<dialog id="access-dialog" aria-labelledby="access-title">
  <form id="access-form">
    <div class="dialog-heading">
      <div>
        <span class="small-label">监护安全认证</span>
        <h2 id="access-title">连接监护数据源</h2>
      </div>
      <button type="button" id="close-access" class="close-button" aria-label="关闭连接设置">×</button>
    </div>
    <p class="dialog-desc">请输入只读访问令牌（View Token），订阅所选网关的实时快照与波形流。</p>
    <div class="dialog-field">
      <label for="view-token">监护访问令牌</label>
      <input id="view-token" type="password" autocomplete="off" placeholder="输入只读令牌 (如 view-token-...)" required>
    </div>
    <p id="access-message" role="status">令牌仅在当前浏览器内存中使用，刷新或断开后需重新验证。</p>
    <div class="dialog-actions">
      <button type="button" id="disconnect" class="button-quiet">断开连接</button>
      <button type="submit" class="button-primary">验证并连接</button>
    </div>
  </form>
</dialog>
`;
}
