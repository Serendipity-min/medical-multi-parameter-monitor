// 应用组装：模块实例化、依赖注入与生命周期调度。HTML 结构、网络状态机和波形算法各在其模块中。
//
// 显示状态：
//   未连接 —— 待机层提示连接；记住了令牌的设备打开即自动连接。
//   已连接、设备无实时数据 —— 待机层显示“等待设备上电”，连接保持，设备上线后自动显示。
//   实时 —— 网关在线且有有效数据。
//   演示 —— 仅在非实时状态下由用户手动开启，本地合成数据；设备一上线立即退出演示。

import './style.css';
import './ui/aiPanel.css';
import { fiveAppliance, defaultGateway } from './gatewayProfile';
import { AccessDialog, rememberedToken } from './ui/accessDialog';
import { setupMonitorDOM, renderRoute } from './ui/monitorView';
import { HashRouter } from './router/hashRouter';
import { SessionView } from './ui/sessionView';
import { NumericsView } from './ui/numerics';
import { StatusBar } from './ui/statusBar';
import { MonitorStore } from './state/monitorStore';
import { MonitorSocket } from './transport/monitorSocket';
import { WaveformRenderer } from './waveform/renderer';
import { AiPanel } from './ui/aiPanel';
import { AlarmMonitor, type Alarm } from './model/alarms';
import { DemoFeed, deviceLive } from './demo/demoFeed';
import type { Snapshot } from './types';

// 网关由构建配置决定，也可由公开 URL 参数指定；授权仍由 Backend 白名单决定。
function initialGateway(): string {
  const requested = new URLSearchParams(location.search).get('gateway');
  if (requested && /^[A-Za-z0-9-]{1,40}$/.test(requested) && (!fiveAppliance || requested === defaultGateway)) return requested;
  return defaultGateway;
}

const text = (id: string, value: string) => {
  const el = document.getElementById(id);
  if (el) el.textContent = value;
};

export function createApp(): { store: MonitorStore; socket: MonitorSocket; demo: DemoFeed } {
  setupMonitorDOM(document.querySelector<HTMLDivElement>('#app')!);

  const store = new MonitorStore();
  const renderer = new WaveformRenderer(store);
  const numerics = new NumericsView();
  const sessionView = new SessionView(store);
  const alarmMonitor = new AlarmMonitor();
  const demo = new DemoFeed(store);
  const gateway = initialGateway();
  let alarms: Alarm[] = [];
  let linkExpected = false;
  // 服务器最新快照与到达时刻，独立于演示数据，用于判断设备是否在线和网络半开。
  let serverSnapshot: Snapshot | null = null;
  let serverAt = 0;

  const socket = new MonitorSocket({
    onSnapshot: (data) => {
      serverSnapshot = data;
      serverAt = performance.now();
      if (demo.active) {
        if (!deviceLive(data)) return;
        demo.end();
        alarmMonitor.reset();
      }
      store.ingestSnapshot(data);
    },
    onStatusChange: (statusText, isOnline) => store.setConnection(statusText, isOnline),
    onConnectionFailed: (title, reason) => { linkExpected = false; accessDialog.showError(title, reason); },
    onDisconnected: (reason) => {
      serverSnapshot = null;
      if (!demo.active) store.clearLive(reason);
    },
  });
  socket.changeGateway(gateway);
  store.changeGateway(gateway);

  const connect = (token: string) => {
    linkExpected = true;
    if (!demo.active) store.clearLive('等待数据');
    socket.connect(token, gateway);
  };

  // AI 使用独立令牌和接口，不能读写 MonitorSocket 的监护鉴权或状态。
  const aiPanel = new AiPanel(() => socket.getGatewayId(), store);

  const statusBar = new StatusBar({
    onWindowChange: (windowSeconds) => store.setWindowMs(windowSeconds * 1000),
    onOpenAccess: () => accessDialog.show(),
    onCloseAccess: () => accessDialog.close(),
    onDisplayError: (message) => { accessDialog.setMessage(message); accessDialog.show(); },
  });

  const accessDialog = new AccessDialog({
    onSubmit: connect,
    onDisconnect: () => { linkExpected = false; alarmMonitor.reset(); socket.disconnect(); },
  });

  const live = () => store.isConnected && deviceLive(serverSnapshot);
  const toggleDemo = () => {
    if (demo.active) {
      demo.end();
      if (serverSnapshot) store.ingestSnapshot(serverSnapshot);
    } else if (!live()) {
      demo.begin();
    }
    alarmMonitor.reset();
    updateView();
  };

  const evaluateAlarms = () => {
    alarms = alarmMonitor.evaluate(store.currentViewModel, store.isConnected || demo.active, linkExpected && !demo.active, Date.now());
  };

  const updateStandby = () => {
    const standby = document.getElementById('standby');
    const demoKey = document.getElementById('demo-toggle') as HTMLButtonElement;
    demoKey.setAttribute('aria-pressed', String(demo.active));
    demoKey.textContent = demo.active ? '退出演示' : '演示';
    demoKey.disabled = !demo.active && live();
    if (!standby) return;
    standby.hidden = demo.active || live();
    if (standby.hidden) return;
    const connected = store.isConnected;
    text('standby-title', connected ? '等待设备上电' : linkExpected ? '正在连接…' : '未连接');
    text('standby-text', connected
      ? 'C 板上电并联网后，实时数据会自动显示，无需操作。'
      : '点“连接”输入只读令牌。专用监护大屏可勾选“记住此设备”，以后打开页面自动连接。');
    (document.getElementById('standby-connect') as HTMLElement).hidden = connected;
  };

  const updateView = () => {
    const vm = store.displayViewModel;
    numerics.update(vm, store.isConnected || demo.active, alarms, store.displayHistory('NIBP'));
    statusBar.update(store.currentViewModel, store.isConnected, store.connectionText, alarms, !!store.frozenAt, demo.active);
    updateStandby();
    sessionView.update();
    aiPanel.update();
  };

  const router = new HashRouter((route) => {
    // 离开 AI 只取消待回答；连接、缓冲和问答实例继续由根部持有。
    aiPanel.leave();
    renderRoute(route, document.getElementById('route-view')!);
    if (route === 'ai') aiPanel.mount(document.getElementById('route-view')!);
    if (route === 'overview') {
      document.getElementById('standby-connect')!.onclick = () => accessDialog.show();
      document.getElementById('standby-demo')!.onclick = toggleDemo;
    }
    sessionView.mount(route);
    updateView();
  });
  router.start();
  store.subscribe(() => { evaluateAlarms(); updateView(); });
  document.getElementById('freeze')!.onclick = () => store.toggleFreeze();
  document.getElementById('demo-toggle')!.onclick = toggleDemo;

  renderer.start();

  // 时钟、报警延时计时与网络半开看门狗。
  setInterval(() => {
    statusBar.updateTime();
    evaluateAlarms();
    updateView();
    // 已连接但连续 5 秒没有服务器快照，判定为网络半开：用同一令牌重新连接。
    if (store.isConnected && serverAt && performance.now() - serverAt > 5000) {
      serverAt = 0;
      const token = socket.getToken();
      if (!demo.active) store.clearLive('连接超时');
      if (token) socket.connect(token, gateway);
      else socket.disconnect();
    }
  }, 500);
  statusBar.updateTime();

  // 专用大屏记住了令牌时，打开页面即自动连接。
  const remembered = rememberedToken();
  if (remembered) connect(remembered);

  return { store, socket, demo };
}
