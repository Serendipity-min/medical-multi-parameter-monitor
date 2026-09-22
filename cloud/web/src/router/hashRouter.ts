// 路由仅装卸中央视图，连接、状态和 Canvas 循环由应用根部持有。
export const routes = ['overview', 'temp', 'ecg', 'spo2', 'resp', 'nibp'] as const;
export type Route = typeof routes[number];

export class HashRouter {
  public current: Route = 'overview';
  private handle = () => {
    const route = location.hash.slice(2) as Route;
    this.current = routes.includes(route) ? route : 'overview';
    if (location.hash !== `#/${this.current}`) history.replaceState(null, '', `#/${this.current}`);
    this.onChange(this.current);
  };

  constructor(private onChange: (route: Route) => void) {}

  public start(): void {
    window.addEventListener('hashchange', this.handle);
    this.handle();
  }

  public stop(): void {
    window.removeEventListener('hashchange', this.handle);
  }
}
