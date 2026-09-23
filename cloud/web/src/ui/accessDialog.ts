// 数据源连接与访问控制对话框组件。
// Token 仅保存在内存中，刷新后自动重置，严禁写入 localStorage 或 URL。

export interface AccessDialogCallbacks {
  onSubmit: (token: string) => void;
  onDisconnect: () => void;
}

export class AccessDialog {
  private dialog: HTMLDialogElement;
  private form: HTMLFormElement;
  private tokenInput: HTMLInputElement;
  private messageEl: HTMLElement;
  private errorDialog: HTMLDialogElement;

  constructor(callbacks: AccessDialogCallbacks) {
    this.dialog = document.querySelector<HTMLDialogElement>('#access-dialog')!;
    this.form = document.querySelector<HTMLFormElement>('#access-form')!;
    this.tokenInput = document.querySelector<HTMLInputElement>('#view-token')!;
    this.messageEl = document.querySelector<HTMLElement>('#access-message')!;
    this.errorDialog = document.querySelector<HTMLDialogElement>('#connection-error-dialog')!;

    document.querySelector<HTMLButtonElement>('#close-connection-error')!.onclick = () => this.errorDialog.close();
    document.querySelector<HTMLButtonElement>('#retry-access')!.onclick = () => {
      this.show();
      this.tokenInput.focus();
    };

    const closeBtn = document.querySelector<HTMLButtonElement>('#close-access');
    if (closeBtn) {
      closeBtn.onclick = () => this.close();
    }

    const disconnectBtn = document.querySelector<HTMLButtonElement>('#disconnect');
    if (disconnectBtn) {
      disconnectBtn.onclick = () => {
        callbacks.onDisconnect();
        this.close();
      };
    }

    this.form.onsubmit = (e) => {
      e.preventDefault();
      const token = this.tokenInput.value.trim();
      if (!token) return;
      this.tokenInput.value = '';
      this.tokenInput.removeAttribute('aria-invalid');
      this.setMessage('令牌仅保存在当前浏览器内存中，刷新或断开后清除。');
      this.close();
      callbacks.onSubmit(token);
    };
  }

  public show(): void {
    // 同时只保留一个模态层，避免错误提示藏在设置层后面或拦截全屏操作。
    if (this.errorDialog.open) this.errorDialog.close();
    if (!this.dialog.open) {
      this.dialog.showModal();
    }
  }

  public close(): void {
    if (this.errorDialog.open) this.errorDialog.close();
    if (this.dialog.open) {
      this.dialog.close();
    }
  }

  public setMessage(msg: string): void {
    this.messageEl.textContent = msg;
  }

  public showError(title: string, message: string): void {
    this.close();
    this.tokenInput.value = '';
    if (title === '访问验证失败') this.tokenInput.setAttribute('aria-invalid', 'true');
    else this.tokenInput.removeAttribute('aria-invalid');
    this.setMessage(message);
    // 失败原因只作为文字显示，既不回显输入令牌，也不解释服务端内容为 HTML。
    document.getElementById('connection-error-title')!.textContent = title;
    document.getElementById('connection-error-message')!.textContent = message;
    this.errorDialog.showModal();
  }

  public isOpen(): boolean {
    return this.dialog.open;
  }
}
