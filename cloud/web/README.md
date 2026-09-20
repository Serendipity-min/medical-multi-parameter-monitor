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

大屏按四个模块组织：心电（ECG/HR）、呼吸（RESP/RR 与最近 120 秒 RR 趋势）、
血压（SYS/DIA）、血氧（PPG/SpO₂/PR）。TEMP 暂不展示，接口字段保留。
RR 趋势使用实际收到的 LIVE RR 通道值；当前数据源是 Mock，正式呼吸率算法待真实数据验证。
波形可切换 8/16 秒窗口，支持全屏；访问令牌在“连接数据源/连接设置”对话框中输入。
1920×1080 可完整展示四模块，窄屏依次显示心电、呼吸、血压、血氧。

视觉依据、GitHub 参考和数据边界见 [UI 设计说明](../../doc/P/P_四模块监护大屏_UI设计说明.md)。
