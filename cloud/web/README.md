# Web

```powershell
npm ci --no-audit --no-fund
npm run dev
npm run build
```

固定发布前缀为 `/medical-monitor/`。Vite 开发代理转发 API 与浏览器 WebSocket 到回环后端。
生产 `dist` 由 Backend 的 StaticFiles 提供，统一通过现有 Nginx 的一个项目路径代理。
如增加本项目其他页面，继续放在此前缀下，不能占用主站 `/api/` 或修改其他站点路由。

所有页面显示 SIMULATION。令牌只保存在当前标签页内存，不存入 URL、localStorage 或 Git。
离线/过期/无效值显示破折号；REPLAY 到达不会更新 LIVE 面板。
Canvas 绘制相对单位的合成信号，不提供临床标尺或诊断解释。
