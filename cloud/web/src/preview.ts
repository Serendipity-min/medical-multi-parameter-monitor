// 本地界面预览：只在开发服务器使用，不进入生产构建（vite build 只打包 index.html）。
// ?scene=normal|alarm 直接进入演示数据；?scene=offline 显示未连接状态；?scene=broadcast 在演示数据上叠加合成播报。
import { createApp } from './app';
import type { Broadcast } from './types';

const app = createApp();
const scene = new URLSearchParams(location.search).get('scene') ?? 'normal';
if (scene === 'broadcast') {
  const disclaimer = '仅供参考，不构成医疗建议，如有不适请咨询医生';
  const now = Date.now();
  const history: Broadcast[] = [
    { id: 'p2', ts: now - 30_000, param: 'NIBP', level: 'notice', text: '本次血压 146/92 mmHg，高于一般参考范围，建议静坐 5 分钟后复测。', disclaimer },
    { id: 'p1', ts: now - 400_000, param: 'TEMP', level: 'info', text: '当前体表温度约 31.2 °C（体表温度低于体温，不作判断）。', disclaimer },
  ];
  const ingest = app.store.ingestSnapshot.bind(app.store);
  app.store.ingestSnapshot = (data) => ingest({ ...data, server_time: Date.now(), broadcast: history[0], broadcast_history: history });
}
if (scene !== 'offline') app.demo.begin(scene === 'alarm');
