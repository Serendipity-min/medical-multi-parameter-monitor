import { defineConfig } from 'vite';

// 所有资源与接口归入项目子路径，避免覆盖主站及其他项目的 /api。
export default defineConfig({
  base: '/medical-monitor/',
  server: {
    proxy: {
      '/medical-monitor/api': {
        target: 'http://127.0.0.1:18765',
        rewrite: (p) => p.replace('/medical-monitor', ''),
      },
      '/medical-monitor/ws': {
        target: 'ws://127.0.0.1:18765',
        ws: true,
        rewrite: (p) => p.replace('/medical-monitor', ''),
      },
    },
  },
});
