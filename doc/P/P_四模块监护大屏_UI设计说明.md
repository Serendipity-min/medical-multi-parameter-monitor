# 四模块监护大屏 UI 设计说明

日期：2026-09-19。依据：用户本轮确认的大屏暂定范围——心电、呼吸、血压、血氧。
主设计流程：`frontend-design`；浏览器验证：`agent-browser`。

## 设计方向与复核

采用仪器式监护布局：浅色应用外框配深蓝信号区，左侧为心电和呼吸连续波形，右侧为血压和血氧。
每个模块的波形、数值、单位、数据质量集中在同一区域，避免从独立波形区跨屏寻找对应数值。

```text
标题 / SIMULATION                 连接数据源 / 全屏
设备与节点状态                     采集时间
┌──────────────────────────┬──────────────────┐
│ 心电 ECG 波形       HR   │ 血压 SYS / DIA   │
├──────────────────────────┼──────────────────┤
│ 呼吸 RESP 波形      RR   │ 血氧 SpO₂ / PR   │
│ RR 算法输出趋势           │ PPG 脉搏波       │
└──────────────────────────┴──────────────────┘
补传状态 / 连接状态 / 模拟数据说明
```

配色：外框 `#edf2f5`，信号底色 `#0c1925`，心电 `#5be0ad`，呼吸 `#e6c179`，
血压 `#b0a3ff`，血氧 `#5dc6ef`。颜色只区分通道，不能代表生理指标是否正常。
字体：中文使用系统雅黑/PingFang，数值使用 Bahnschrift/DIN 系统字体和等宽数字。
桌面优先 1920×1080 单屏展示，手机改为单列。正文左对齐，数值按模块对齐。

方案复核：不采用营销首屏、患者身份占位信息、无实际用途的侧栏或重复 KPI 卡片。
访问令牌移到连接对话框；只提供有效的时间窗口选择、连接/断开与全屏操作。
血压没有连续压力数据，因此只显示上传的 SYS/DIA，不绘制伪造的动脉压波形。

## GitHub 参考与取舍

- [Infirmary Integrated](https://github.com/tanjera/infirmary-integrated)，参考提交 `3298fdab380dbbc9644d9d62518da572cb3929c3`：
  参考其监护仪式深色波形、多通道配色与参数分区，未引入除颤、报警或其他设备控制。
- [VSCC Dashboard](https://github.com/chsbusch-dot/vscc-dashboard-client)，参考提交 `04211a2e50b45e7efd811da63c644f251a454f6c`：
  查看其 `docs/screenshots/dashboard-full.png`，参考波形与数值对应、连续曲线和趋势图的区分。
  沿用本项目 Canvas 2D，不引入其 SciChart/MQTT 技术栈。
- 本机设计资料中的 Linear/Sentry：仅参考字体层级、表面层次和可操作控件的清晰度，未使用其品牌资产。

UI 为本项目重新实现，不复制第三方源码、图标、Logo 或患者信息。

## 数据语义

- 心电：ECG 波形 + HR。
- 呼吸：RESP 波形 + RR 数值 + RR 最近 120 秒趋势。RR 使用上传的算法输出通道；
  当前 Mock 为模拟值，正式 `RESP_RAW → RR` 算法尚未经过真实数据验证。本轮不新增或宣称完成该算法。
- 血压：NIBP 上传的 SYS/DIA 对，不以波形刷新当作新的独立袖带测量。
- 血氧：PPG 波形 + SpO₂ + PR。
- TEMP 暂不展示；后端接口继续保留该字段，前端显式忽略，避免影响后续硬件接入。

LIVE/REPLAY、Invalid/Stale、节点离线语义沿用第一阶段；补传不覆盖实时波形或 RR 趋势。
RR 趋势仅收录当前标签页实际收到的有效 LIVE 值，不提前填充历史；缺失区间留空。
所有页面保留 SIMULATION，波形标注相对幅值，不伪造医学标尺、临床阈值或患者信息。

连续波形依据采集时间映射到浏览器单调时钟；公网到达抖动不应反复清空缓冲。
跳帧、会话变化、源时钟回退和大幅时间跳变会断开或清空曲线，避免伪造连续性。

## 本轮验收与部署

- TypeScript 检查和 Vite 生产构建通过。
- 本地浏览器 15 项检查通过，公网浏览器 15 项检查通过：四模块、RR 趋势、SYS/DIA、
  8/16 秒窗口、全屏、1920×1080 完整布局、连续波形、Invalid、两节点独立离线、
  LIVE/REPLAY 隔离、断线恢复、静默过期、刷新重订阅及手机无横向溢出。
- 公网入口及两份构建资源 SHA-256 与本地构建一致；既有三个页面状态及内容哈希不变。
- 本轮仅更新静态前端，无需开放端口，未修改 Nginx、证书、DNS 或后端服务。
- 文件经本机 `E:/Server_file` 暂存上传，核对大小与 SHA-256 后删除本次暂存文件。

记录目录：[本地验证](../../cloud/evidence/ui-redesign-local/browser-acceptance.json)、
[公网验证](../../cloud/evidence/ui-redesign-public/browser-acceptance.json)、
[部署清单](../../cloud/evidence/ui-redesign-public/deployment.json)、
[静态资源及既有页面核验](../../cloud/evidence/ui-redesign-public/http-verification.json)。
截图位于上述两个 evidence 目录，覆盖 LIVE、REPLAY 和手机页面。

发布目录：`/opt/medical-monitor/web-releases/ui-four-module-20260919-080446`。
入口更新前备份：`/opt/medical-monitor/backups/ui-four-module-20260919-080446/index.html`。
本轮重新设计前的原始入口备份：`/opt/medical-monitor/backups/ui-four-module-20260919-080218/index.html`。
旧哈希资源保留，回滚时可将选定的备份入口复制为目标目录中的临时文件，再原子替换
`/opt/medical-monitor/current/web/dist/index.html`；不需要重启 Backend 或 Nginx。

全部数据仍来自本地 Mock Gateway。本轮不包含真实硬件接入、正式 RR 算法验收、报警或长期稳定性结论。
