# Web 监护大屏 UI 重构验收测试计划与执行报告

> **文档编号**：MPM-P-UI-VAL-001  
> **版本**：v1.0  
> **日期**：2026-09-20  
> **状态**：通过验收 (All PASS)  
> **代码基线**：`cfb30d0a4a52f36e9dca6733b761741aae226de6` / `de2f209`  
> **分支**：`dev/p-web-ui-v07`  
> **执行人**：Gemini / Antigravity

---

## 1. 验收概述与目标达成

本报告针对专项合同 `doc/P/03_第三阶段_UI重构/合同/P_Web监护大屏_UI重构专项合同_v0.1.md`（MPM-P-WEB-SOW-001）所规定的全部要求，在本地运行环境下对纯前端重构成果进行了全面、严谨的自动化回归测试与视觉证据采集。

### 核心指标达成情况
1. **真实床旁/中央监护大屏定位达成**：
   - 彻底摆脱浅色 SaaS/运维 Dashboard 风格，全面采用深度暗黑防眩光背景（`#090d14`）与高动态对比度专属生命体征识别色（`--ecg: #00e676`、`--spo2: #00e5ff`、`--resp: #ffd600`、`--nibp: #f8fafc`、`--temp: #ff9100`）；
   - 实现左侧波形区（70%）与右侧大数字区（30%）四行严格水平对齐布局；
   - 在标准 **1920 × 1080 全高清显示器上达成 100% 垂直零滚动**（`scrollHeight <= innerHeight`）。
2. **代码模块化解耦达成**：
   - 彻底解耦原单文件 `main.ts`，将其拆解为集中类型定义（`types.ts`）、纯传输层（`monitorSocket.ts`）、集中响应状态存储（`monitorStore.ts`）、纯映射视图模型（`viewModel.ts`）、Canvas 渲染引擎（`renderer.ts`）、以及 4 个原子 UI 组件；
   - `npm run build`（`tsc --noEmit && vite build`）零警告零错误。
3. **后端与外部协议零改动达成**：
   - Backend、Gateway、CANopen、MQTT、Nginx 零改动；
   - 后端全部 28 项单元测试（`pytest tests/`）100% 通过。
4. **严格本地化展示**：
   - 未向腾讯云公网服务器执行任何部署，所有测试与验证均在本地闭环完成。

---

## 2. 实际修改与新增文件清单

### 2.1 新增设计与验收文档
- `doc/P/03_第三阶段_UI重构/设计/01_临床监护仪UI参考与设计规律分析.md`：迈瑞、飞利浦、理邦对比研究与设计决策；
- `doc/P/03_第三阶段_UI重构/设计/02_UI线框与布局规范.md`：1920×1080 零滚动布局栅格、Design Tokens 及 DOM 测试锚点；
- `doc/P/03_第三阶段_UI重构/验收/01_Web_UI重构验收测试计划与执行报告.md`：本交付执行报告。

### 2.2 前端工程模块化代码 (`cloud/web/`)
- `cloud/web/src/types.ts`：[NEW] 集中 Snapshot v1、Signal、Point 与 ViewModel 类型；
- `cloud/web/src/transport/monitorSocket.ts`：[NEW] 纯 WebSocket 网络传输、首帧 Token 鉴权与指数回退；
- `cloud/web/src/state/monitorStore.ts`：[NEW] 集中状态存储、有界采样缓冲、RR 趋势与采样断点检测；
- `cloud/web/src/model/viewModel.ts`：[NEW] 纯函数映射转换，统一脱敏与合法性格式化；
- `cloud/web/src/waveform/renderer.ts`：[NEW] Canvas 2D 走纸扫描引擎、微网格底纹与 DPR 自适应；
- `cloud/web/src/ui/monitorView.ts`：[NEW] 床旁监护仪 4 行 2 列主 DOM 容器装配；
- `cloud/web/src/ui/numerics.ts`：[NEW] 体征大数字读数面板与离线降暗控制器；
- `cloud/web/src/ui/statusBar.ts`：[NEW] 顶部系统状态栏组件；
- `cloud/web/src/ui/accessDialog.ts`：[NEW] 鉴权对话框组件；
- `cloud/web/src/style.css`：[REWRITE] 深度暗黑监护仪样式、Design Tokens 与响应式媒体查询；
- `cloud/web/src/main.ts`：[REWRITE] 极简启动入口与心跳看门狗调度；
- `cloud/web/README.md`：[UPDATE] 架构图与开发指南更新。

### 2.3 验证脚本与视觉证据 (`cloud/`)
- `cloud/tools/local_ui_verification.py`：[NEW] 本地 15 组场景自动化验收与 Playwright 多分辨率截图脚本；
- `cloud/evidence/ui-v07/browser-acceptance.json`：[NEW] 自动化验收结果 JSON；
- `cloud/evidence/ui-v07/1920x1080-live-mock.png`：[NEW] 1080p 标准四模块 + TEMP 监护全屏截图；
- `cloud/evidence/ui-v07/1920x1080-node-a-offline.png`：[NEW] Node-A 离线隔离截图；
- `cloud/evidence/ui-v07/1920x1080-node-b-offline.png`：[NEW] Node-B 离线隔离截图；
- `cloud/evidence/ui-v07/1920x1080-rr-invalid.png`：[NEW] RESP 有波形但 RR INVALID 截图；
- `cloud/evidence/ui-v07/1920x1080-replay.png`：[NEW] 历史补传独立展示与实时清空截图；
- `cloud/evidence/ui-v07/1366x768.png`：[NEW] 1366×768 笔记本屏幕无滚动适配截图；
- `cloud/evidence/ui-v07/mobile-390x844.png`：[NEW] 移动端只读安全流式布局截图；
- `cloud/evidence/ui-v07/fullscreen.png`：[NEW] 全屏模式监护截图。

---

## 3. 测试执行过程与准出核验 (Test Matrix)

执行本地端到端测试脚本 `python cloud/tools/local_ui_verification.py`，15 项场景核验全部通过：

| 序号 | 检验项目 / 场景 | 验收标准 | 测试结果 |
| :--- | :--- | :--- | :--- |
| 1 | **Token 鉴权与连接握手** | 输入 View Token 后通过首帧 WebSocket 建立连接，弹窗自动关闭 | **PASS** |
| 2 | **1080p 四模块骨架** | `document.querySelectorAll("[data-module]").length === 4`，TEMP 呈现，MOCK 标签常驻 | **PASS** |
| 3 | **ECG Canvas 绿色像素** | 检测 Canvas 像素存在 $G > 150$ 且 $G > R \times 1.2$ 的荧光绿走纸迹线 | **PASS** |
| 4 | **RR 数值与 120s 趋势 Canvas** | RR 显示 15，趋势画布检测到琥珀色趋势点折线 | **PASS** |
| 5 | **NIBP SYS/DIA 真实读数** | 正确显示 118 / 76 mmHg，不伪造压力波形 | **PASS** |
| 6 | **走纸窗口切换** | 切换 8 秒 / 16 秒视窗，标签与轴刻度平滑响应 | **PASS** |
| 7 | **1920×1080 零垂直滚动** | `scrollHeight <= innerHeight && scrollWidth <= innerWidth` | **PASS** |
| 8 | **Node-A 离线隔离** | Node-A 离线时，SpO2/PR/NIBP 显示 `—` 且面板变暗；Node-B（ECG/HR/RESP/RR/TEMP）不受影响正常工作 | **PASS** |
| 9 | **Node-B 离线隔离** | Node-B 离线时，ECG/HR/RESP/RR/TEMP 显示 `—` 且面板变暗；Node-A（SpO2/PR/NIBP）不受影响正常工作 | **PASS** |
| 10 | **RESP 波形正常但 RR 无效** | 阻抗呼吸波连续起伏，但 RR 读数强制显示 `—`，趋势带显示 `无有效 RR 数据` | **PASS** |
| 11 | **REPLAY 补传独立专区** | 历史补传到达专用卡片，当前实时波形与标量按规则过期/清空，不发生数据混淆 | **PASS** |
| 12 | **网关数据源切换隔离** | 切换至无数据的真机网关（GW-C-001）时读数彻底置灰清空，切回模拟网关立即恢复 | **PASS** |
| 13 | **1366×768 笔记本屏幕无滚动** | 紧凑布局下同样维持 `scrollHeight <= innerHeight`，零滚动 | **PASS** |
| 14 | **移动端 390×844 无横向溢出** | 单列流式布局，`scrollWidth <= innerWidth`，保证只读巡视体验 | **PASS** |
| 15 | **全屏沉浸模式切换** | 成功触发 Fullscreen API 进入全屏监护状态 | **PASS** |

---

## 4. 后端零破坏验证 (Zero Backend Breakage Proof)

在 `cloud/backend` 目录下重新运行全体测试：

```powershell
pytest tests/
```

**执行结果**：
```text
============================= test session starts =============================
platform win32 -- Python 3.11.9, pytest-9.1.1, pluggy-1.6.0
collected 28 items

tests\test_monitor.py .................                                  [ 60%]
tests\test_operations.py ...........                                     [100%]

============================= 28 passed in 1.74s ==============================
```

**证明**：前端模块化拆分与 UI 重构没有修改任何后端代码、MQTT 订阅适配器、Hub 快照生成器或数据模型，后端所有功能回归测试 100% 绿色通过。

---

## 5. 视觉验收成果 (Screenshots Showcase)

全套 8 组高分辨率截图已保存在本地 `cloud/evidence/ui-v07/` 目录下：

1. **标准 1080p 实时监护全景**：`cloud/evidence/ui-v07/1920x1080-live-mock.png`  
   - 绿色心电、青色血氧容积、琥珀黄呼吸波形及 120 秒趋势带平稳连续；
   - 心率（72）、血氧（98）、脉率（72）、呼吸率（15）、无创血压（118/76）、体温（36.6）一屏全览。
2. **Node-A 离线隔离状态**：`cloud/evidence/ui-v07/1920x1080-node-a-offline.png`  
   - Node-A 降暗，血氧与血压读数置 `—`；Node-B 心电与呼吸正常运作。
3. **Node-B 离线隔离状态**：`cloud/evidence/ui-v07/1920x1080-node-b-offline.png`  
   - Node-B 降暗，心电与呼吸读数置 `—`；Node-A 血氧正常运作。
4. **RESP 有波形但 RR 无效**：`cloud/evidence/ui-v07/1920x1080-rr-invalid.png`  
   - 呼吸波形正常绘制，RR 读数显示 `—`，趋势带显示 `无有效 RR 数据`。
5. **历史补传独立展示**：`cloud/evidence/ui-v07/1920x1080-replay.png`  
   - 补传信息准确落入辅助卡片，实时读数清空。
6. **1366×768 笔记本屏幕适配**：`cloud/evidence/ui-v07/1366x768.png`  
   - 紧凑排版，无任何滚动条。
7. **移动端 390×844 竖屏流式布局**：`cloud/evidence/ui-v07/mobile-390x844.png`  
   - 单列堆叠，横向无溢出。
8. **全屏沉浸监护**：`cloud/evidence/ui-v07/fullscreen.png`  
   - 满屏视觉呈现。

---

## 6. 已知限制与后续建议

1. **当前数据源性质**：目前主要在本地运行 MOCK 合成波形与标量，因此界面常驻 `MOCK 模拟数据` 标签，符合工程真实性规范。
2. **正式临床报警引擎待集成**：目前通道颜色仅代表参数类型，不包含异常阈值变色（如心动过速变红）。后续若后端接入临床报警逻辑，可在 `viewModel.ts` 中扩展 `AlarmSeverity` 映射。
3. **云端同步建议**：当前阶段代码完全留在本地分支 `dev/p-web-ui-v07` 中。建议在用户充分评审本地截图并确认满意后，再在下一阶段命令下安排服务器静态资源的同步与部署。
