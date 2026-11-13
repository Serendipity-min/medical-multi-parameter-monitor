# P Web 监护大屏 UI 重构专项合同

> **文件编号**：MPM-P-WEB-SOW-001  
> **版本**：v0.1  
> **日期**：2026-09-20  
> **执行建议对象**：Gemini / Antigravity  
> **项目负责人**：P  
> **代码基线**：`cfb30d0a4a52f36e9dca6733b761741aae226de6`  
> **接口冻结基线**：Backend WebSocket `schema_version = 1`  
> **开发性质**：纯前端视觉与代码结构重构，不修改 Gateway、CANopen、MQTT、Backend 和服务器数据语义。  
> **目标**：在保持现有数据链路和安全边界不变的情况下，将 Web 大屏重构为更接近真实床旁/中央监护仪使用场景的专业监护界面。

---

# 1. 开工结论

经过第三轮复核，当前：

```text
CANopen Test Node
      ↓
Gateway Canonical Model
      ↓
MQTT/TLS
      ↓
Backend
      ↓
WebSocket Snapshot v1
```

已通过当前阶段测试和 CI。

因此：

> **前端不需要继续等待 Backend，可以立即独立重构。**

但必须遵守：

```text
Backend = Frozen
WebSocket Schema v1 = Frozen
MQTT = Frozen
CANopen = Frozen
```

如果前端实现过程中发现必须修改 Backend，必须停止并提交接口变更申请，不能自行修改。

---

# 2. Git 分支要求

PR #2 尚未合并 `main`。

因此 UI 重构必须从当前稳定 head 创建新分支：

```text
cfb30d0
   ↓
dev/p-web-ui-v07
```

建议：

```bash
git switch dev/p-gateway-cloud-v07
git pull --ff-only
git switch -c dev/p-web-ui-v07
```

不要把大量 UI 改动继续塞进 PR #2。

UI 分支完成后：

```text
dev/p-web-ui-v07
        ↓
独立 PR
```

如果 PR #2 已先合入 main，再 rebase 到最终合并点。

---

# 3. 允许修改的范围

默认允许：

```text
cloud/web/**
```

允许新增：

```text
doc/P/03_Web_UI重构/
cloud/evidence/ui-v07/
```

如果需要更新 UI README，也可以修改：

```text
cloud/web/README.md
```

禁止修改：

```text
cloud/backend/**
cloud/broker/**
cloud/deploy/**
gateway/**
doc/P/02_第二阶段_CANopen可靠性/设计/**
MQTT Topic
CANopen OD/PDO
Nginx 运行逻辑
```

---

# 4. 当前前端接口冻结

## 4.1 WebSocket

路径：

```text
/ws/v1/monitor
```

连接后第一帧：

```json
{
  "token": "<view-token>",
  "gateway_id": "GW-C-001"
}
```

Token 不进入 URL。

## 4.2 Snapshot

前端必须兼容：

```text
type
schema_version
gateway_id
gateways
gateway_state
broker_connected
nodes
server_time
streams
replay
event
```

`schema_version`：

```text
1
```

## 4.3 Stream

```text
gateway_id
node_id
stream
timestamp
seq
session_id
validity
source
synthetic
value
samples
sample_rate
unit
```

允许：

```text
validity:
VALID
INVALID
STALE
OFFLINE

source:
LIVE
MOCK
REPLAY
```

---

# 5. UI 的真实使用场景定位

本项目 Web 端不是普通 Dashboard。

应定位为：

> **单床位远程监护大屏 / 中央监护站中的单患者监护视图。**

视觉体验优先考虑：

- 护士站 / 监护台；
- 1920×1080 大屏；
- 夜间长时间观察；
- 一眼读数；
- 波形优先；
- 故障和离线状态明显；
- 操作少；
- 不使用大量营销卡片、渐变、装饰插图。

---

# 6. 真实监护仪参考原则

执行前必须研究真实监护仪官方界面。

优先官方材料：

- Mindray ePM 10M / 12M Operator Manual  
  `https://www.mindray.com/content/dam/xpace/en_us/service-and-support/training-and-education/resource--library/technical--documents/operators-manuals-1/continuous/H-046-019798-00-ePM-10M-ePM-12M-ops-manual-FDA-13.0.pdf`
- Philips IntelliVue MX400  
  `https://www.usa.philips.com/healthcare/product/HC866060`
- Philips IntelliVue MX400 IFU  
  `https://images.philips.com/is/content/PhilipsConsumer/Campaigns/CA08092022_nbp/Mx400_ifu_eng.pdf`
- EDAN iM Series  
  `https://www.edan.com/product/m/PM_iM_Series_(iM80/70/60/50).html`
- EDAN iX Series 产品资料。

参考这些产品的：

- 波形区；
- 大数字区；
- ECG / HR；
- RESP / RR；
- SpO2 / Pleth / PR；
- NIBP；
- TEMP；
- 顶部状态栏；
- 报警/故障信息区；
- 全屏信息密度。

**只提取设计规律，不复制厂商品牌、Logo、商标、独有图形和像素级 Trade Dress。**

---

# 7. 推荐视觉结构

## 7.1 1920×1080 主模式

建议从当前“网页 Dashboard”重构为更接近监护仪：

```text
┌────────────────────────────────────────────────────────────┐
│ Patient / Device / Gateway / Time / Connection / Source   │
├────────────────────────────────────────┬───────────────────┤
│ ECG                                    │ HR                │
│ ~~~~~~~/\~~~~~~~~/\~~~~~~~~~~~~~~~~~   │  73 bpm           │
├────────────────────────────────────────┼───────────────────┤
│ PLETH / PPG                            │ SpO2  98 %        │
│ ~~~~~╭──╮~~~~╭──╮~~~~~~~~~~~~~~~~     │ PR    73 bpm      │
├────────────────────────────────────────┼───────────────────┤
│ RESP                                   │ RR    16 /min     │
│ ~~~~╭────╮~~~~╭────╮~~~~~~~~~~~~      │ TEMP  36.7 ℃     │
├────────────────────────────────────────┼───────────────────┤
│ Status / Event / Replay                │ NIBP 116 / 74    │
│ Node-A / Node-B / Gateway              │ mmHg             │
└────────────────────────────────────────┴───────────────────┘
```

建议比例：

```text
Waveform area 65~72%
Numeric area 28~35%
```

这只是布局原则，不要求完全按 ASCII 像素实现。

---

# 8. 参数视觉优先级

一级：

```text
ECG + HR
SpO2 + PPG
RESP + RR
NIBP
```

二级：

```text
PR
TEMP
Node Status
Gateway Status
```

三级：

```text
Gateway selector
MOCK / LIVE / REPLAY
Debug source
Last update
```

三级信息必须存在，但不能占据监护主画面大量面积。

---

# 9. 通道颜色

可以使用监护仪常见的稳定通道识别颜色，但：

> 颜色只用于“参数识别”，不能在 Backend 没有报警语义时代表“临床正常/异常”。

建议：

```text
ECG / HR       绿色系
SpO2 / PPG/PR  青/蓝系
RESP / RR      黄/琥珀系
NIBP           白/紫系
TEMP           暖白/橙系
```

禁止前端自行：

```text
HR > 100 → 红
SpO2 < 90 → 红
```

除非 Backend 后续正式提供 Alarm 状态。

---

# 10. 状态显示规则

## VALID

正常显示。

## INVALID

必须：

```text
--
```

或者：

```text
No Signal
```

不能：

```text
0
```

## STALE

显示：

```text
STALE
```

数值清空。

## OFFLINE

模块区域降低亮度，并明确：

```text
OFFLINE
```

不能继续显示上一次健康值。

---

# 11. MOCK / LIVE / REPLAY

## MOCK

开发测试时：

```text
MOCK
```

必须始终可见。

不要因为视觉不好看隐藏。

## LIVE

真实数据：

```text
LIVE
```

## REPLAY

历史：

```text
REPLAY
```

必须独立区域。

历史不能看起来像实时波形。

---

# 12. 不允许伪造的 UI 功能

禁止出现：

- “患者姓名”假数据；
- “床号 01”假数据；
- 虚假的医疗报警；
- 虚假的 NIBP 测量状态；
- 虚假的心律失常诊断；
- 假的 PI；
- 假的 MAP；
- 假的 ECG Lead；
- 假的临床正常范围；
- 假的 RR 算法状态；
- 云端 NIBP Start / Stop；
- 远程危险控制按钮。

没有数据就不显示或标：

```text
Not Available
```

---

# 13. 当前 NIBP UI

Backend 当前 NIBP：

```text
[SYS, DIA]
```

因此主显示：

```text
116 / 74 mmHg
```

不要自行添加：

```text
MAP
PR-NIBP
Inflating
Cuff Pressure
```

除非后续 Backend 提供。

可以显示：

```text
Last update
Validity
```

---

# 14. RR UI

当前：

```text
RESP waveform
RR numeric
```

必须分开。

正式 RR 算法尚未完成时：

```text
RR = --
```

UI 不得从 RESP waveform 自己计算 RR。

---

# 15. 波形设计

继续采用：

```text
Canvas 2D
```

不改成大量：

```text
SVG path
DOM nodes
```

每个波形独立 Buffer。

需要支持：

- ECG；
- PPG；
- RESP；
- 网络断点；
- Stale；
- 8s / 16s 可视窗口；
- resize；
- fullscreen。

---

# 16. 波形断点

如果：

```text
seq discontinuity
timestamp gap
session change
```

前端：

```text
断线
重新起笔
```

不能：

```text
直线连接
```

这会制造伪连续波形。

---

# 17. 软件结构重构要求

当前 `main.ts` 过于集中。

Gemini 必须至少拆分为：

```text
src/
├── types.ts
├── transport/
│   └── monitorSocket.ts
├── state/
│   └── monitorStore.ts
├── model/
│   └── viewModel.ts
├── waveform/
│   └── renderer.ts
├── ui/
│   ├── monitorView.ts
│   ├── numerics.ts
│   ├── statusBar.ts
│   └── accessDialog.ts
├── style.css
└── main.ts
```

`main.ts`：

> 只做初始化和组装，不再包含整页 HTML、WebSocket 状态机和完整波形算法。

---

# 18. 技术栈限制

继续：

```text
Vite
TypeScript
Vanilla DOM
Canvas 2D
```

本轮不引入：

```text
React
Vue
Angular
大型 UI Framework
Chart.js
ECharts
```

理由：

- 当前 UI 规模不需要；
- 避免扩大依赖；
- 保持嵌入式项目维护简单；
- Canvas 实时波形已经验证。

如果 Gemini 认为必须引入框架，需要先停止并说明理由。

---

# 19. CSS 设计要求

建立：

```text
Design Tokens
```

例如：

```text
--monitor-bg
--panel-bg
--grid-line
--text-primary
--text-muted
--ecg
--spo2
--resp
--nibp
--temp
```

禁止：

- 到处硬编码颜色；
- 每个组件自己发明字号；
- 大量阴影；
- 大圆角卡片；
- 渐变背景；
- 玻璃拟态；
- 营销型 Hero UI。

目标：

> 像监护仪，不像 SaaS Dashboard。

---

# 20. 连接入口

当前 View Token 输入 Dialog 可以保留。

但主监护界面不应长期显示：

```text
大号“连接数据源”
```

连接后应收敛为小型状态区域。

Gateway 切换也应从主视觉降级到：

```text
顶部设备区
或
设置抽屉
```

---

# 21. 报警区域

可以预留：

```text
Alarm / Event Banner
```

但当前 Backend 没有正式 Alarm Severity。

因此只允许显示：

```text
FAULT Event
Offline
Stale
```

不能自己定义：

```text
High Alarm
Medium Alarm
Low Alarm
```

除非 Backend 将来提供 severity。

---

# 22. 响应式

必须验证：

```text
1920×1080
1366×768
2560×1440
```

重点是：

```text
1920×1080
```

必须：

- 无纵向滚动；
- 四类主要参数一屏可见；
- 数字足够大；
- 波形至少占主要空间。

移动端：

```text
只读降级布局
```

允许纵向排列。

---

# 23. 浏览器全屏

保留：

```text
Fullscreen API
```

全屏后隐藏非必要：

- 网页外框；
- Debug 提示；
- 说明文字。

只保留：

- 波形；
- 数值；
- 状态；
- 时间；
- 来源。

---

# 24. 字体

中文：

```text
Microsoft YaHei UI
PingFang SC
```

数字：

```text
系统无衬线数字字体
```

不依赖外部网络字体。

服务器离线/内网环境也必须正常显示。

---

# 25. 与 Backend 的隔离层

Gemini 必须实现：

```text
WebSocket Snapshot
      ↓
ViewModel
      ↓
UI
```

例如：

```ts
toMonitorViewModel(snapshot)
```

UI 不应该到处写：

```ts
snapshot.streams.find(...)
```

否则未来 Schema 增加字段会难维护。

---

# 26. Snapshot v1 类型必须集中定义

放：

```text
src/types.ts
```

禁止在多个文件重复定义：

```ts
type Signal ...
type Snapshot ...
```

---

# 27. 状态 Store

建议 Store 管理：

```text
connection
gateway
nodes
latestStreams
waveBuffers
replay
event
```

Transport 不直接操作 DOM。

---

# 28. Transport

`monitorSocket.ts` 负责：

- URL；
- WebSocket；
- Auth First Frame；
- reconnect；
- Snapshot decode；
- callback。

禁止：

```text
transport 里修改颜色
transport 里画 Canvas
```

---

# 29. Canvas Renderer

单独负责：

```text
samples
timestamp
sample_rate
gap
window
resize
draw
```

不关心：

```text
MQTT
Gateway
Token
CANopen
```

---

# 30. UI 验收场景

必须完成以下 fixture：

1. Gateway Offline；
2. Gateway Online；
3. Node-A Offline；
4. Node-B Offline；
5. ECG LIVE；
6. ECG MOCK；
7. RESP 有波形但 RR INVALID；
8. SpO2 VALID；
9. NIBP VALID；
10. TEMP VALID；
11. Stream STALE；
12. REPLAY 到达；
13. FAULT Event；
14. Browser reconnect；
15. Gateway 切换。

---

# 31. 视觉验收证据

必须保存：

```text
1920x1080 live/mock
1920x1080 node-a-offline
1920x1080 node-b-offline
1920x1080 rr-invalid
1920x1080 replay
1366x768
mobile
fullscreen
```

路径：

```text
cloud/evidence/ui-v07/
```

---

# 32. UI 参考分析交付

编码前先写：

```text
doc/P/03_Web_UI重构/
├── UI参考分析.md
└── UI线框与布局说明.md
```

必须回答：

- Mindray/Philips/EDAN 共性是什么；
- 哪些设计可以复用；
- 哪些不能照搬；
- 本项目为什么选当前布局；
- 参数颜色为什么这样分配；
- Web 和床旁仪的差异怎么处理。

---

# 33. 测试要求

最低：

```bash
cd cloud/web
npm ci --no-audit --no-fund
npm run build
```

还必须重跑现有：

```text
Backend tests
CANopen C→Backend compatibility
Browser fixture
```

虽然不改 Backend，也必须证明没有破坏兼容性。

---

# 34. 不允许通过删测试“修复”

若测试失败：

```text
修代码
```

不能：

```text
删除断言
删除场景
屏蔽错误
```

---

# 35. 性能要求

目标：

- Canvas 动画稳定；
- 长时间不产生 DOM 节点积累；
- Buffer 有界；
- 断线后不无限缓存；
- 1920×1080 CPU 使用合理；
- Browser 10Hz Snapshot 不触发整个页面重建。

---

# 36. 可访问性

至少：

- 状态不只靠颜色；
- OFFLINE / STALE 有文字；
- Button 有 aria；
- Canvas 有 aria-label；
- 键盘可打开连接 Dialog；
- Fullscreen 可退出。

---

# 37. 视觉版本流程

## U0 参考研究

不改代码。

## U1 线框

提交：

```text
UI线框与布局说明
```

## U2 静态重构

使用 MOCK fixture。

## U3 实时数据

接当前 WebSocket v1。

## U4 异常状态

验证 Offline / Stale / Replay。

## U5 公网页面

只在 P 授权后部署。

---

# 38. Git 提交建议

```text
docs(web): add clinical monitor UI reference analysis

refactor(web): split transport state and waveform renderer

feat(web): rebuild bedside monitor layout

test(web): add monitor UI browser acceptance

docs(web): add UI refactor acceptance report
```

不要一个 Commit 包含：

```text
Backend
Gateway
UI
Docs
```

全部一起改。

---

# 39. 准出条件

```text
[ ] Backend/Gateway 零修改
[ ] WebSocket Schema v1 不变
[ ] Vite build 通过
[ ] 原 Browser 数据逻辑继续通过
[ ] MOCK 标签明确
[ ] LIVE/REPLAY 不混淆
[ ] INVALID/STALE/OFFLINE 不显示旧值
[ ] ECG/PPG/RESP Canvas 正常
[ ] HR/RR/SpO2/PR/NIBP/TEMP 正常
[ ] 1920×1080 无纵向滚动
[ ] 1366×768 可用
[ ] mobile 可读
[ ] fullscreen 正常
[ ] 无虚假临床报警
[ ] 无远程危险控制
[ ] UI 参考分析完成
[ ] Screenshot Evidence 完成
[ ] 独立 PR 完成
```

---

# 40. 最终交付

```text
cloud/web/
doc/P/03_Web_UI重构/
cloud/evidence/ui-v07/
```

并输出：

```text
P_Web_UI重构执行报告.md
```

报告必须列：

- 基线 Commit；
- 实际修改文件；
- 截图；
- 测试；
- 未修改 Backend 证明；
- 已知限制；
- 下一步建议。

---

# 41. 最终执行指令

Gemini 本轮任务是：

> **在完全不改变 cfb30d0 后端、CANopen、MQTT 和 Gateway 数据逻辑的情况下，仅重构 Web 前端，使其从“通用网页 Dashboard”升级为“真实监护仪/中央监护单床位视图风格”，同时保持所有状态语义和测试边界。**

遇到 Backend 缺字段：

> **显示 unavailable / placeholder，提交接口需求，不自行修改后端。**
