// 应用启动器：仅负责模块组装、依赖注入与生命周期调度。
// 严禁在此堆砌 HTML 结构、网络状态机或波形算法。

import './style.css';
import { AccessDialog } from './ui/accessDialog';
import { setupMonitorDOM, renderRoute } from './ui/monitorView';
import { HashRouter } from './router/hashRouter';
import { SessionView } from './ui/sessionView';
import { NumericsView } from './ui/numerics';
import { StatusBar } from './ui/statusBar';
import { MonitorStore } from './state/monitorStore';
import { MonitorSocket } from './transport/monitorSocket';
import { WaveformRenderer } from './waveform/renderer';

// 1. 初始化 DOM 结构
const app = document.querySelector<HTMLDivElement>('#app')!;
setupMonitorDOM(app);

// 2. 实例化状态存储与 Canvas 渲染器
const store = new MonitorStore();
const renderer = new WaveformRenderer(store);
const numerics = new NumericsView();
const sessionView = new SessionView(store);

// 3. 实例化纯网络传输层
const socket = new MonitorSocket({
  onSnapshot: (data) => {
    store.ingestSnapshot(data);
  },
  onStatusChange: (statusText, isOnline) => {
    store.setConnection(statusText, isOnline);
  },
  onConnectionFailed: (title, reason) => {
    accessDialog.showError(title, reason);
  },
  onDisconnected: (reason) => {
    store.clearLive(reason);
  },
});

// 4. 实例化顶部状态栏与鉴权弹窗
const statusBar = new StatusBar({
  onGatewayChange: (gatewayId) => {
    store.changeGateway(gatewayId);
    socket.changeGateway(gatewayId);
  },
  onWindowChange: (windowSeconds) => {
    store.setWindowMs(windowSeconds * 1000);
  },
  onOpenAccess: () => {
    accessDialog.show();
  },
  onCloseAccess: () => {
    accessDialog.close();
  },
  onDisplayError: (message) => {
    // 全屏权限失败只影响本地显示，重新呈现设置提示，不改变数据连接。
    accessDialog.setMessage(message);
    accessDialog.show();
  },
});

const accessDialog = new AccessDialog({
  onSubmit: (token) => {
    store.clearLive('等待数据');
    socket.connect(token, statusBar.getSelectedGatewayId());
  },
  onDisconnect: () => {
    socket.disconnect();
  },
});

// 5. 状态订阅：状态驱动 UI 刷新
const updateView = () => {
  const state = store;
  numerics.update(state.displayViewModel);
  statusBar.update(state.currentViewModel, state.isConnected, state.connectionText);
  sessionView.update();
};
const router = new HashRouter((route) => {
  renderRoute(route, document.getElementById('route-view')!);
  sessionView.mount(route);
  updateView();
});
router.start();
store.subscribe(updateView);
document.getElementById('open-settings')!.onclick = () => accessDialog.show();
document.getElementById('freeze')!.onclick = () => store.toggleFreeze();

// 6. 启动 Canvas 渲染循环
renderer.start();

// 7. 定时器：系统时钟刷新与网络超时看门狗
setInterval(() => {
  statusBar.updateTime();

  // 若连接成功后连续 5 秒未收到任何快照帧，判定为网络半开并清空过期读数
  if (store.lastMessageTime && performance.now() - store.lastMessageTime > 5000) {
    store.lastMessageTime = 0;
    socket.disconnect();
    store.clearLive('连接超时');
  }
}, 500);
