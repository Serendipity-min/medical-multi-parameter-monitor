# Web 监护大屏 (Phase 3 专业床旁/中央大屏架构)

> **定位**：单床位远程监护大屏 / 中央监护站单患者视图 (Bedside & Central Monitor View)  
> **技术栈**：Vite 7 + TypeScript 5 + 原生 Canvas 2D + 标准 CSS Variables (无重型前端框架依赖)  
> **接口基线**：Backend WebSocket Snapshot v1 (`/ws/v1/monitor`, `schema_version = 1`)

---

## 1. 快速上手

```powershell
# 安装依赖
npm ci --no-audit --no-fund

# 本地热重载开发服务器
npm run dev

# 静态类型检查与生产编译
npm run build
```

- **统一前缀**：固定发布前缀为 `/medical-monitor/`。生产 `dist/` 由 Backend 的 `StaticFiles` 托管或由 Nginx 反向代理。
- **Token 鉴权**：访问令牌仅保存在当前标签页内存中，在首次连接的 WebSocket 第一帧上报，**绝对不存入 URL、localStorage 或 Git**。

---

## 2. 软件模块化架构

遵循专项合同 MPM-P-WEB-SOW-001，前端代码全面拆分为 9 大高内聚模块：

```text
cloud/web/src/
├── types.ts                   # 集中定义 Snapshot v1 / Signal / ViewModel / Point 数据模型
├── transport/
│   └── monitorSocket.ts       # 纯网络传输层：WebSocket 状态机、首帧 Token 鉴权、指数退避重连
├── state/
│   └── monitorStore.ts        # 集中式状态存储：环形采样缓冲区、RR 趋势、时间锚点与断点检测
├── model/
│   └── viewModel.ts           # 纯函数转换层：Snapshot -> MonitorViewModel，格式化与脱敏
├── waveform/
│   └── renderer.ts            # Canvas 2D 渲染引擎：高刷新率平滑扫描、微网格底纹、DPR 自适应
├── ui/
│   ├── monitorView.ts         # 床旁大屏主 DOM 装配与四行生命体征容器
│   ├── numerics.ts            # 体征数值读数组件 (HR / SpO2 / PR / RR / NIBP / TEMP)
│   ├── statusBar.ts           # 顶部状态栏组件 (网关/节点指示、时钟、视窗调节、全屏)
│   └── accessDialog.ts        # 数据源只读令牌认证与网关切换对话框
├── style.css                  # 临床监护仪 Design Tokens、1080p 零滚动与响应式布局
└── main.ts                    # 轻量启动器：模块装配、状态订阅与超时看门狗
```

---

## 3. 核心视觉规范与临床设计

参考迈瑞（Mindray ePM/BeneVision）与飞利浦（Philips IntelliVue MX400）人机工程规范：
1. **暗黑防眩基底**：全屏采用 `#090d14` 近黑色低反光纯色背景，消除夜间视觉疲劳。
2. **左波右数、水平对齐（70% : 30%）**：
   - **Row 1**：ECG Lead II 心电走纸波形 ↔ HR 心率大读数 (bpm)
   - **Row 2**：PLETH 脉搏容积波形 ↔ SpO₂ 血氧饱和度 (%) + PR 脉率 (bpm)
   - **Row 3**：RESP 胸阻抗呼吸波形 + 120 秒 RR 趋势折线 ↔ RR 呼吸率 (/min)
   - **Row 4**：辅助系统状态 (REPLAY 补传独立专区、系统事件、红外体温 TEMP) ↔ NIBP 无创血压 (SYS/DIA mmHg)
3. **通道识别色彩（Design Tokens）**：
   - 心电/心率：`--ecg: #00e676` (监护绿)
   - 血氧/脉率：`--spo2: #00e5ff` (医疗青蓝)
   - 呼吸/呼吸率：`--resp: #ffd600` (警示黄)
   - 无创血压：`--nibp: #f8fafc` (高光冷白)
   - 红外体温：`--temp: #ff9100` (暖橙色)
4. **状态与异常展示规范**：
   - `VALID`：大号等宽高对比清晰读数。
   - `INVALID`：强制显示 `—`，严禁显示 `0`（防止临床误判）。
   - `STALE`：清空读数，标牌标注 `STALE`。
   - `OFFLINE`：对应通道明显降低亮度并标明 `OFFLINE`。
   - `MOCK`：在未连接真实硬件时，顶部 `MOCK 模拟数据` 标签常驻可见。
   - `REPLAY`：历史补传独立展示在专用卡片中，绝不污染或覆盖当前实时波形。

---

## 4. 响应式与全屏支持

- **1920 × 1080**：绝对零垂直/水平滚动条，一屏总览四大生理模块与系统状态。
- **1366 × 768**：紧凑笔记本自适应缩放，字体与网格弹性收缩，同样维持零纵向滚动。
- **移动端 (390 × 844)**：单列纵向安全流式布局，保证床旁移动巡视时的只读可读性，杜绝任何横向溢出。
- **全屏沉浸**：点击“全屏显示”可触发浏览器原生 Fullscreen API，全屏专注监护。

---

## 5. 相关设计与验收文档

- 临床监护仪参考分析：[01_临床监护仪UI参考与设计规律分析.md](../../doc/P/03_第三阶段_UI重构/设计/01_临床监护仪UI参考与设计规律分析.md)
- UI 线框与布局规范：[02_UI线框与布局规范.md](../../doc/P/03_第三阶段_UI重构/设计/02_UI线框与布局规范.md)
- 验收测试计划与执行报告：[01_Web_UI重构验收测试计划与执行报告.md](../../doc/P/03_第三阶段_UI重构/验收/01_Web_UI重构验收测试计划与执行报告.md)
