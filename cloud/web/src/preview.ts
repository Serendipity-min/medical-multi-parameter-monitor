// 本地界面预览：只在开发服务器使用，不进入生产构建（vite build 只打包 index.html）。
// ?scene=normal|alarm 直接进入演示数据；?scene=offline 显示未连接状态。
import { createApp } from './app';

const app = createApp();
const scene = new URLSearchParams(location.search).get('scene') ?? 'normal';
if (scene !== 'offline') app.demo.begin(scene === 'alarm');
