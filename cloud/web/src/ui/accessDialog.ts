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

  constructor(callbacks: AccessDialogCallbacks) {
    this.dialog = document.querySelector<HTMLDialogElement>('#access-dialog')!;
    this.form = document.querySelector<HTMLFormElement>('#access-form')!;
    this.tokenInput = document.querySelector<HTMLInputElement>('#view-token')!;
    this.messageEl = document.querySelector<HTMLElement>('#access-message')!;

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
      this.close();
      callbacks.onSubmit(token);
    };
  }

  public show(): void {
    if (!this.dialog.open) {
      this.dialog.showModal();
    }
  }

  public close(): void {
    if (this.dialog.open) {
      this.dialog.close();
    }
  }

  public setMessage(msg: string): void {
    this.messageEl.textContent = msg;
  }

  public isOpen(): boolean {
    return this.dialog.open;
  }
}
