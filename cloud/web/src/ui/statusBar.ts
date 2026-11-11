// 顶栏：连接状态、演示数据标识、时钟、报警区与报警灯；底栏按键中的全屏与波形时长。

import { highestPriority, type Alarm } from '../model/alarms';
import type { MonitorViewModel } from '../types';

export interface StatusBarCallbacks {
  onWindowChange: (windowSeconds: number) => void;
  onOpenAccess: () => void;
  onCloseAccess: () => void;
  onDisplayError: (message: string) => void;
}

const LINK_LABEL: Record<string, string> = { on: '已连接', off: '未连接', wait: '连接中' };

export class StatusBar {
  private fullscreenBtn = document.querySelector<HTMLButtonElement>('#fullscreen')!;
  private openAccessBtn = document.querySelector<HTMLButtonElement>('#open-access')!;

  constructor(callbacks: StatusBarCallbacks) {
    this.openAccessBtn.onclick = () => callbacks.onOpenAccess();

    this.fullscreenBtn.onclick = async () => {
      // 先同步关闭模态层，保留本次点击授予的全屏权限。
      callbacks.onCloseAccess();
      try {
        if (document.fullscreenElement) await document.exitFullscreen();
        else await document.documentElement.requestFullscreen();
      } catch {
        callbacks.onDisplayError('浏览器未允许全屏，可按 F11 或使用浏览器菜单。');
      }
    };
    document.addEventListener('fullscreenchange', () => {
      this.fullscreenBtn.setAttribute('aria-pressed', String(Boolean(document.fullscreenElement)));
      this.fullscreenBtn.textContent = document.fullscreenElement ? '退出全屏' : '全屏';
    });

    document.querySelectorAll<HTMLButtonElement>('[data-window]').forEach((btn) => {
      btn.onclick = () => {
        callbacks.onWindowChange(Number(btn.dataset.window));
        document.querySelectorAll<HTMLButtonElement>('[data-window]').forEach((item) => item.setAttribute('aria-pressed', String(item === btn)));
      };
    });
  }

  public updateTime(): void {
    const now = new Date();
    document.getElementById('clock')!.textContent = now.toLocaleTimeString('zh-CN', { hour12: false });
    document.getElementById('today')!.textContent = now.toLocaleDateString('zh-CN', { month: '2-digit', day: '2-digit', weekday: 'short' });
  }

  public update(vm: MonitorViewModel, isConnected: boolean, connectionText: string, alarms: readonly Alarm[], frozen: boolean): void {
    const state = isConnected ? 'on' : connectionText === '正在连接' || connectionText.includes('重连') ? 'wait' : 'off';
    const link = document.getElementById('link-state')!;
    link.dataset.state = state;
    document.getElementById('connection')!.textContent = isConnected ? LINK_LABEL.on : connectionText || LINK_LABEL[state];
    // 合成数据只用固定标识提示，不在每个参数上重复来源。
    document.getElementById('demo-badge')!.hidden = !vm.sources.includes('MOCK');
    document.getElementById('frozen-badge')!.hidden = !frozen;
    this.openAccessBtn.textContent = isConnected ? '连接设置' : '连接';

    const phys = alarms.filter((alarm) => !alarm.technical);
    const tech = alarms.filter((alarm) => alarm.technical);
    for (const [id, list] of [['alarm-phys', phys], ['alarm-tech', tech]] as const) {
      const box = document.getElementById(id)!;
      box.dataset.priority = highestPriority(list);
      // 报警区同时最多显示两条，其余以计数提示，避免顶栏溢出。
      box.textContent = list.length ? list.slice(0, 2).map((alarm) => alarm.text).join('  ·  ') + (list.length > 2 ? `  +${list.length - 2}` : '') : '';
    }
    document.getElementById('alarm-light')!.dataset.priority = highestPriority(alarms);
  }
}
