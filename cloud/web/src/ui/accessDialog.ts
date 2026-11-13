// 连接对话框。令牌默认只在内存中；勾选“记住此设备”后保存在本浏览器 localStorage，
// 用于专用监护大屏打开即自动连接（负责人 2026-11-11 决定）。令牌永不进入 URL 或 Git。

const STORAGE_KEY = 'mmpm.monitor.viewToken';

export function rememberedToken(): string {
  try { return localStorage.getItem(STORAGE_KEY) ?? ''; } catch { return ''; }
}

export function forgetToken(): void {
  try { localStorage.removeItem(STORAGE_KEY); } catch { /* 存储不可用时无需处理 */ }
}

function rememberToken(token: string): boolean {
  try { localStorage.setItem(STORAGE_KEY, token); return true; } catch { return false; }
}

export interface AccessDialogCallbacks {
  onSubmit: (token: string) => void;
  onDisconnect: () => void;
}

export class AccessDialog {
  private dialog = document.querySelector<HTMLDialogElement>('#access-dialog')!;
  private form = document.querySelector<HTMLFormElement>('#access-form')!;
  private tokenInput = document.querySelector<HTMLInputElement>('#view-token')!;
  private remember = document.querySelector<HTMLInputElement>('#remember-device')!;
  private forgetBtn = document.querySelector<HTMLButtonElement>('#forget-device')!;
  private messageEl = document.querySelector<HTMLElement>('#access-message')!;
  private errorDialog = document.querySelector<HTMLDialogElement>('#connection-error-dialog')!;

  constructor(callbacks: AccessDialogCallbacks) {
    document.querySelector<HTMLButtonElement>('#close-connection-error')!.onclick = () => this.errorDialog.close();
    document.querySelector<HTMLButtonElement>('#retry-access')!.onclick = () => { this.show(); this.tokenInput.focus(); };
    document.querySelector<HTMLButtonElement>('#close-access')!.onclick = () => this.close();
    document.querySelector<HTMLButtonElement>('#disconnect')!.onclick = () => { callbacks.onDisconnect(); this.close(); };
    this.forgetBtn.onclick = () => {
      forgetToken();
      this.refresh();
      this.setMessage('已忘记此设备。当前连接保持，刷新页面后需重新输入令牌。');
    };

    this.form.onsubmit = (e) => {
      e.preventDefault();
      const token = this.tokenInput.value.trim();
      if (!token) return;
      this.tokenInput.value = '';
      this.tokenInput.removeAttribute('aria-invalid');
      if (this.remember.checked) {
        if (!rememberToken(token)) this.setMessage('浏览器不允许保存，本次仅在内存中使用令牌。');
      } else {
        forgetToken();
      }
      this.refresh();
      this.close();
      callbacks.onSubmit(token);
    };
    this.refresh();
  }

  private refresh(): void {
    const stored = !!rememberedToken();
    this.forgetBtn.hidden = !stored;
    this.remember.checked = stored;
    if (!stored) this.setMessage('令牌默认只保存在当前页面内存中。专用监护大屏可勾选“记住此设备”，以后打开自动连接。');
    else this.setMessage('此设备已记住令牌，打开页面会自动连接。');
  }

  public show(): void {
    // 同时只保留一个模态层，避免错误提示藏在设置层后面或拦截全屏操作。
    if (this.errorDialog.open) this.errorDialog.close();
    if (!this.dialog.open) this.dialog.showModal();
  }

  public close(): void {
    if (this.errorDialog.open) this.errorDialog.close();
    if (this.dialog.open) this.dialog.close();
  }

  public setMessage(msg: string): void {
    this.messageEl.textContent = msg;
  }

  public showError(title: string, message: string): void {
    this.close();
    this.tokenInput.value = '';
    if (title === '访问验证失败') {
      // 已记住的令牌失效时一并清除，避免每次打开都自动用失效令牌重试。
      forgetToken();
      this.refresh();
      this.tokenInput.setAttribute('aria-invalid', 'true');
    } else {
      this.tokenInput.removeAttribute('aria-invalid');
    }
    // 失败原因只作为文字显示，既不回显输入令牌，也不解释服务端内容为 HTML。
    document.getElementById('connection-error-title')!.textContent = title;
    document.getElementById('connection-error-message')!.textContent = message;
    this.errorDialog.showModal();
  }
}
