// 纯网络传输层：管理 WebSocket 连接生命周期、首帧 Token 鉴权与指数回退重连。
// 严禁在此模块内引用 DOM 或执行任何 UI 样式与 Canvas 绘制。

import type { Snapshot } from '../types';

export interface TransportCallbacks {
  onSnapshot: (data: Snapshot) => void;
  onStatusChange: (statusText: string, isOnline: boolean) => void;
  onConnectionFailed: (title: string, reason: string) => void;
  onDisconnected: (reason: string) => void;
}

export class MonitorSocket {
  private socket: WebSocket | null = null;
  private token = '';
  private gatewayId = 'GW-DEV-001';
  private intentional = false;
  private retryCount = 0;
  private retryTimer = 0;

  constructor(private callbacks: TransportCallbacks) {}

  public connect(token: string, gatewayId: string): void {
    clearTimeout(this.retryTimer);
    this.token = token;
    this.gatewayId = gatewayId;
    this.intentional = false;

    if (this.socket) {
      this.socket.onclose = null;
      this.socket.close();
      this.socket = null;
    }

    const protocol = location.protocol === 'https:' ? 'wss:' : 'ws:';
    const url = `${protocol}//${location.host}/medical-monitor/ws/v1/monitor`;

    this.callbacks.onStatusChange('正在连接', false);

    const ws = new WebSocket(url);
    this.socket = ws;
    let incompatibleSnapshot = false;

    ws.onopen = () => {
      if (this.socket !== ws) return;
      // 首帧认证：仅在 Payload 中传递 Token 与 gateway_id，Token 严禁进入 URL
      ws.send(JSON.stringify({ token: this.token, gateway_id: this.gatewayId }));
    };

    ws.onmessage = (event: MessageEvent) => {
      if (this.socket !== ws) return;
      try {
        const data = JSON.parse(event.data) as Snapshot;
        if (data.type !== 'snapshot' || data.schema_version !== 1 || !Array.isArray(data.streams)) {
          throw new Error('Unexpected snapshot schema');
        }
        this.retryCount = 0;
        this.callbacks.onStatusChange('监护通道已连接', true);
        this.callbacks.onSnapshot(data);
      } catch (err) {
        // 本地协议校验失败不能误报为令牌错误，保留失败类别供关闭回调使用。
        incompatibleSnapshot = true;
        // 浏览器主动关闭只允许 1000 或 3000–4999；使用应用码避免 close 自身抛错。
        ws.close(4002);
      }
    };

    ws.onclose = (event: CloseEvent) => {
      if (this.socket !== ws) return;
      this.socket = null;
      this.callbacks.onStatusChange('监护通道已断开', false);
      this.callbacks.onDisconnected('连接断开');

      // 对端可能以普通关闭码响应本地主动关闭，不能丢失已确认的格式失败原因。
      if (incompatibleSnapshot || event.code === 1008) {
        this.token = '';
        this.callbacks.onConnectionFailed(
          incompatibleSnapshot ? '数据格式不兼容' : '访问验证失败',
          incompatibleSnapshot
            ? '收到的数据格式与当前页面不兼容，已停止连接。请刷新页面后重试；这不表示访问令牌已过期。'
            : '访问令牌无效或不匹配，或所选网关未获授权。请核对当前站点的完整令牌后重试；本机预览与服务器的令牌可能不同。',
        );
        return;
      }

      if (!this.intentional && this.token) {
        const delay = Math.min(1000 * 2 ** this.retryCount++, 10000);
        this.callbacks.onStatusChange(`${delay / 1000} 秒后自动重连`, false);
        this.retryTimer = window.setTimeout(() => {
          this.connect(this.token, this.gatewayId);
        }, delay);
      }
    };

    ws.onerror = () => {
      // 错误触发后会自然进入 onclose，此处保持状态通知即可
    };
  }

  public disconnect(): void {
    this.intentional = true;
    this.token = '';
    clearTimeout(this.retryTimer);
    if (this.socket) {
      this.socket.onclose = null;
      this.socket.close();
      this.socket = null;
    }
    this.callbacks.onStatusChange('已断开', false);
    this.callbacks.onDisconnected('已断开');
  }

  public changeGateway(newGatewayId: string): void {
    this.gatewayId = newGatewayId;
    if (this.socket) {
      this.socket.onclose = null;
      this.socket.close();
      this.socket = null;
    }
    clearTimeout(this.retryTimer);
    this.callbacks.onDisconnected('切换网关');
    if (this.token) {
      this.connect(this.token, this.gatewayId);
    }
  }

  public getToken(): string {
    return this.token;
  }

  public getGatewayId(): string {
    return this.gatewayId;
  }
}
