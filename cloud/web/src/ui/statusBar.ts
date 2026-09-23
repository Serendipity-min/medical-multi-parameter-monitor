// 顶部系统状态栏组件：管理网关身份、节点在线指示、走纸窗口调节、时钟及全屏。

import type { MonitorViewModel } from '../types';

export interface StatusBarCallbacks {
  onGatewayChange: (gatewayId: string) => void;
  onWindowChange: (windowSeconds: number) => void;
  onOpenAccess: () => void;
  onCloseAccess: () => void;
  onDisplayError: (message: string) => void;
}

export class StatusBar {
  private gatewaySelect: HTMLSelectElement;
  private gatewayIdEl: HTMLElement;
  private gatewayChip: HTMLElement;
  private nodeAChip: HTMLElement;
  private nodeBChip: HTMLElement;
  private connectionEl: HTMLElement;
  private connectionDot: HTMLElement;
  private sourceBanner: HTMLElement;
  private modeEl: HTMLElement;
  private clockEl: HTMLElement;
  private todayEl: HTMLElement;
  private openAccessBtn: HTMLButtonElement;
  private fullscreenBtn: HTMLButtonElement;

  constructor(callbacks: StatusBarCallbacks) {
    this.gatewaySelect = document.querySelector<HTMLSelectElement>('#gateway-select')!;
    this.gatewayIdEl = document.querySelector<HTMLElement>('#gateway-id')!;
    this.gatewayChip = document.querySelector<HTMLElement>('#gateway')!;
    this.nodeAChip = document.querySelector<HTMLElement>('#node-a')!;
    this.nodeBChip = document.querySelector<HTMLElement>('#node-b')!;
    this.connectionEl = document.querySelector<HTMLElement>('#connection')!;
    this.connectionDot = document.querySelector<HTMLElement>('#connection-dot')!;
    this.sourceBanner = document.querySelector<HTMLElement>('#source-banner')!;
    this.modeEl = document.querySelector<HTMLElement>('#mode')!;
    this.clockEl = document.querySelector<HTMLElement>('#clock')!;
    this.todayEl = document.querySelector<HTMLElement>('#today')!;
    this.openAccessBtn = document.querySelector<HTMLButtonElement>('#open-access')!;
    this.fullscreenBtn = document.querySelector<HTMLButtonElement>('#fullscreen')!;

    // 绑定事件
    this.gatewaySelect.onchange = () => {
      callbacks.onGatewayChange(this.gatewaySelect.value);
    };

    this.openAccessBtn.onclick = () => {
      callbacks.onOpenAccess();
    };

    this.fullscreenBtn.onclick = async () => {
      // 先撤下模态层再进入全屏，否则根元素会盖住弹窗，但弹窗仍拦截主界面点击。
      // 关闭必须同步发生，保留此次真实点击授予的全屏权限。
      callbacks.onCloseAccess();
      this.fullscreenBtn.disabled = true;
      try {
        if (document.fullscreenElement) {
          await document.exitFullscreen();
        } else {
          await document.documentElement.requestFullscreen();
        }
      } catch {
        // 显示设置错误留在弹窗里，避免下一帧连接状态刷新后提示立即消失。
        callbacks.onDisplayError('浏览器未允许切换全屏，可使用浏览器的全屏菜单或按 F11。');
      } finally {
        this.fullscreenBtn.disabled = false;
      }
    };

    document.addEventListener('fullscreenchange', () => {
      this.fullscreenBtn.setAttribute('aria-pressed', String(Boolean(document.fullscreenElement)));
      const span = this.fullscreenBtn.querySelector('span');
      if (span) {
        span.textContent = document.fullscreenElement ? '退出全屏' : '全屏显示';
      }
    });

    document.querySelectorAll<HTMLButtonElement>('[data-window]').forEach((btn) => {
      btn.onclick = () => {
        const sec = Number(btn.dataset.window);
        callbacks.onWindowChange(sec);
        document.querySelectorAll<HTMLButtonElement>('[data-window]').forEach((item) => {
          item.setAttribute('aria-pressed', String(item === btn));
        });
        document.querySelectorAll('.window-start').forEach((label) => {
          label.textContent = `−${sec} 秒`;
        });
      };
    });
  }

  public updateTime(): void {
    const now = new Date();
    this.clockEl.textContent = now.toLocaleTimeString('zh-CN', { hour12: false });
    this.todayEl.textContent = now.toLocaleDateString('zh-CN', {
      year: 'numeric',
      month: '2-digit',
      day: '2-digit',
    });
  }

  public update(vm: MonitorViewModel, isConnected: boolean, connectionText: string): void {
    this.gatewayIdEl.textContent = vm.gatewayId;
    if (this.gatewaySelect.value !== vm.gatewayId) {
      // 若下拉框存在对应选项则同步
      const opt = Array.from(this.gatewaySelect.options).find((o) => o.value === vm.gatewayId);
      if (opt) this.gatewaySelect.value = vm.gatewayId;
    }

    this.gatewayChip.textContent = `Gateway · ${vm.gatewayState}`;
    this.gatewayChip.classList.toggle('online', vm.gatewayState === 'ONLINE');

    this.nodeAChip.textContent = `Node-A · ${vm.nodeAState}`;
    this.nodeAChip.classList.toggle('online', vm.nodeAState === 'ONLINE');

    this.nodeBChip.textContent = `Node-B · ${vm.nodeBState}`;
    this.nodeBChip.classList.toggle('online', vm.nodeBState === 'ONLINE');

    this.connectionEl.textContent = connectionText;
    this.connectionDot.classList.toggle('online', isConnected);

    this.sourceBanner.textContent = vm.sourceBanner;
    this.modeEl.textContent = vm.modeText;

    this.openAccessBtn.textContent = isConnected ? '连接设置' : '连接数据源';
  }

  public getSelectedGatewayId(): string {
    return this.gatewaySelect.value;
  }
}
