// 应用组装：模块实例化、依赖注入与生命周期调度。HTML 结构、网络状态机和波形算法各在其模块中。

import './style.css';
import './ui/aiPanel.css';
import { fiveAppliance, defaultGateway } from './gatewayProfile';
import { AccessDialog } from './ui/accessDialog';
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

// 网关由构建配置决定，也可由公开 URL 参数指定；授权仍由 Backend 白名单决定。
function initialGateway(): string {
  const requested = new URLSearchParams(location.search).get('gateway');
  if (requested && /^[A-Za-z0-9-]{1,40}$/.test(requested) && (!fiveAppliance || requested === defaultGateway)) return requested;
  return defaultGateway;
}

export function createApp(): { store: MonitorStore; socket: MonitorSocket } {
  setupMonitorDOM(document.querySelector<HTMLDivElement>('#app')!);

  const store = new MonitorStore();
  const renderer = new WaveformRenderer(store);
  const numerics = new NumericsView();
  const sessionView = new SessionView(store);
  const alarmMonitor = new AlarmMonitor();
  const gateway = initialGateway();
  let alarms: Alarm[] = [];
  let linkExpected = false;

  const socket = new MonitorSocket({
    onSnapshot: (data) => store.ingestSnapshot(data),
    onStatusChange: (statusText, isOnline) => store.setConnection(statusText, isOnline),
    onConnectionFailed: (title, reason) => { linkExpected = false; accessDialog.showError(title, reason); },
    onDisconnected: (reason) => store.clearLive(reason),
  });
  socket.changeGateway(gateway);
  store.changeGateway(gateway);

  // AI 使用独立令牌和接口，不能读写 MonitorSocket 的监护鉴权或状态。
  const aiPanel = new AiPanel(() => socket.getGatewayId(), store);

  const statusBar = new StatusBar({
    onWindowChange: (windowSeconds) => store.setWindowMs(windowSeconds * 1000),
    onOpenAccess: () => accessDialog.show(),
    onCloseAccess: () => accessDialog.close(),
    onDisplayError: (message) => { accessDialog.setMessage(message); accessDialog.show(); },
  });

  const accessDialog = new AccessDialog({
    onSubmit: (token) => {
      linkExpected = true;
      store.clearLive('等待数据');
      socket.connect(token, gateway);
    },
    onDisconnect: () => { linkExpected = false; alarmMonitor.reset(); socket.disconnect(); },
  });

  const evaluateAlarms = () => {
    alarms = alarmMonitor.evaluate(store.currentViewModel, store.isConnected, linkExpected, Date.now());
  };
  const updateView = () => {
    const vm = store.displayViewModel;
    numerics.update(vm, store.isConnected, alarms, store.displayHistory('NIBP'));
    statusBar.update(store.currentViewModel, store.isConnected, store.connectionText, alarms, !!store.frozenAt);
    sessionView.update();
    aiPanel.update();
  };
  const router = new HashRouter((route) => {
    // 离开 AI 只取消待回答；连接、缓冲和问答实例继续由根部持有。
    aiPanel.leave();
    renderRoute(route, document.getElementById('route-view')!);
    if (route === 'ai') aiPanel.mount(document.getElementById('route-view')!);
    sessionView.mount(route);
    updateView();
  });
  router.start();
  store.subscribe(() => { evaluateAlarms(); updateView(); });
  document.getElementById('freeze')!.onclick = () => store.toggleFreeze();

  renderer.start();

  // 时钟、报警延时计时与网络半开看门狗。
  setInterval(() => {
    statusBar.updateTime();
    evaluateAlarms();
    updateView();
    // 连接后连续 5 秒未收到快照，判定为网络半开并清空过期读数。
    if (store.lastMessageTime && performance.now() - store.lastMessageTime > 5000) {
      store.lastMessageTime = 0;
      socket.disconnect();
      store.clearLive('连接超时');
    }
  }, 500);
  statusBar.updateTime();

  return { store, socket };
}
