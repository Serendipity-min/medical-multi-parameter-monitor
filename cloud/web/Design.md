# Stitch 六页面监护界面设计规范

版本：2026-09-22 / Stitch ICU Patient Monitor UI，适用于当前工程样机。原始素材的诊断、报警和硬件控制设想不构成本项目能力声明。

> Visual style may resemble professional bedside monitors, but every displayed metric, diagnostic statement, alarm state, sensor status and control must be supported by the project's current data model. Unsupported clinical features must not be invented.

## 视觉基线

沿用用户提供的 `home_overview` 与 `_1` 至 `_5` 六页。按 2026-09-22 用户预览反馈增强饱和度：背景 `#080e16`，读数面板 `#121c27`，前景 `#e8f1fc`；ECG/HR 绿色 `#39ff84`，PPG/SpO2/PR 红色 `#ff5267`，RESP/RR 黄色 `#ffdf32`，TEMP 青色 `#00e5ff`。NIBP 标题与 DIA 使用 `#55ddff`，SYS 使用近白色。颜色区分参数，血氧红色不代表报警。

字体使用本机 Segoe UI / Microsoft YaHei，数值使用 Consolas / Cascadia Mono 等宽数字。无网络字体、CDN、Tailwind 或图标字体；图标为内联 SVG。2–4px 小圆角、细分隔线，无装饰阴影或过渡动画。活动导航与导出按钮跟随通道颜色；趋势填充只沿真实收到的有效连续片段，不表示正常值区间。

```text
共享状态栏 / MOCK 来源 / 最后通信 / 当前本地时钟
总览：三路波形约 68% | HR、SpO2+PR、RR、NIBP、TEMP 约 32%
详情：主读数 + 配置 | 采集信息
      波形 / 趋势  | 最近记录 / CSV
共享技术状态 / 六页导航 / 连接设置 / 本地冻结
```

全局状态与底部导航固定，中央内容区域在窄屏可滚动。1920×1080 总览和详情核心区域完整；1600×900、1366×768 总览零滚动；390×844 采用单列，不能横向溢出。大读数和曲线为视觉中心，配置说明与技术状态降低视觉权重。

## 数据与医疗语义

| 页面 | 仅展示的项目能力 | 不得沿用素材内容 |
|---|---|---|
| ECG | ADS1292R / Node-B；单导联 RA–LA，RA/LA/RL 静态配置；250Hz；HR 标量 | Lead II、ST/QT/PVC、诊断、R 峰统计、物理走纸标定、电极正常 |
| SpO2 | AFE4490 / Node-A；红光/红外光；PPG 50Hz；SpO2 与 PR | PI、灌注等级、AC/DC、探头正常、未经上报的滤波参数 |
| RESP | ADS1292R 阻抗呼吸 / Node-B；50Hz；RR 算法标量 | Ω 标定、RA-LL、载波频率、呼吸暂停报警、节律诊断 |
| NIBP | HKB-08 / Node-A；SYS/DIA 离散测量及时间 | MAP、连续压力波、测量/放气遥控、CRC/阀门状态 |
| TEMP | GY-641 V3 / MLX90614 / Node-B；I²C；非接触额温；1–3cm 静态说明 | 环境温 Ta、To、校准状态、FOV、生理诊断或丢包结论 |

非 VALID 数字显示 `--`。波形与算法标量分别判定质量。Node ONLINE 只表示通信状态，不能推断电极、探头或测量有效。顶部标明工程样机和未接入患者身份；MOCK 在六页保持可见；REPLAY 使用独立技术状态区，不覆盖实时值。

## 共享状态、历史和控制

- HashRouter 只切换视图；六页共享一个 MonitorSocket、MonitorStore、SessionHistory、AccessDialog 和 RAF 循环。
- 只有当前页的 Canvas 进入 DOM；路由和缩放不清除原始波形缓冲。
- 历史初始为空，按每流 session / seq / timestamp 去重。设备新会话、断线分段，切换 Gateway 清空；每标量最多 3600 条且不超过 60 分钟。刷新清空。最近记录表最多 12 行。
- 趋势坐标来自已收到记录的采集时间。无效记录断线；NIBP 只画成对离散结果。不存在演示性的过去一小时曲线或预填历史。
- 冻结只冻结浏览器显示副本，持续接收与积累历史；顶部显示 DISPLAY FROZEN。新的 INVALID/STALE/OFFLINE 优先清空，避免冻结数字掩盖故障。CSV 导出当前真实接收会话，可能包含冻结期间接收的新记录。
- CSV 在用户点击后由本地 Blob 生成，无自动导出、上传或历史请求；文本单元格转义并防公式解释。
- 连接设置只提供 Gateway、内存只读令牌、8/16 秒本地窗口与全屏。没有临床报警、血压远程控制或校准入口。
- 切换全屏前同步关闭设置弹窗，避免隐藏的模态层盖字和拦截点击；全屏内仍可重新打开设置、切换路由、冻结和导出。权限拒绝在设置内提示，不覆盖连接状态。手机横屏取消外框最小高度，底部导航留在视区。
- 动态快照和历史字符串使用 textContent；令牌不进入 URL、日志、localStorage、sessionStorage。
- 访问验证失败使用独立 alertdialog 提示，可关闭或重新输入；与设置弹窗互斥，普通模式和全屏均可操作。收到不兼容数据单独提示，不能误报为令牌过期；本地显示的帧计数仅表示累计收到的快照数，不表示文件归档。

验收实现见 `cloud/tools/stitch_ui_acceptance.py`，固定状态测试见 `cloud/web/tests`。旧 UI 线框保留为历史记录，本规范和本轮合同优先。

完整交互回归见 `cloud/tools/stitch_ui_interaction_acceptance.py`：先校验点击中心实际命中目标，再由浏览器真实点击；同时检查全屏 API、Escape、路由、显示窗口、CSV、重连和七种视区。线上模式只读取既有服务运行配置并浏览页面，凭据只在内存和 stdin 中使用。

## 本机 MOCK 预览节奏

`preview_signals.py` 仅生成本机明确标记 MOCK 的样例数据：血压每 30 秒一组 SYS/DIA，心率/脉率/血氧/呼吸率每秒一条，体温每 2 秒一条；波形每 200ms 分包。值按确定性缓慢变化，心电/脉搏与呼吸相位连续，历史仍从浏览器收到的第一条开始。调度落后时跳过过去的时间槽，不能补造测量历史。此节奏不是设备采集或临床测量策略。

功能验收可选择 `fixed` 场景保证精确断言，结束后恢复默认变化场景。重启预览可用 `--reuse-config` 复用本机仓库外的临时令牌，同时使用新的采集会话标识。
