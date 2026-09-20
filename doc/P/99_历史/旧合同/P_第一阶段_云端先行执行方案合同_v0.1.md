# P 第一阶段执行方案合同：云端先行与模拟 Gateway 联调

> **文件编号**：MMP-P-SOW-001  
> **版本**：v0.1  
> **日期**：2026-09-19  
> **负责人**：P  
> **对应总合同**：《多参数监护仪_总开发合同与系统方案_v0.6》  
> **阶段定位**：在 A/B 开发传感器期间，P 不等待真实硬件链路完成，先独立打通腾讯云、Nginx、Backend、Web 与 Mock Gateway，形成可供 Gateway-C 后续直接接入的云端底座。

---

# 1. 阶段目标

本阶段完成后，应形成以下闭环：

```text
Mock Gateway
    ↓ WSS/TLS
腾讯云 Nginx
    ↓
Backend
    ↓
WebSocket
    ↓
浏览器监护大屏
```

Mock Gateway 先模拟未来 Gateway-C 的数据行为。真实 Gateway-C 完成后，只替换数据源，不重新开发整套云端。

本阶段不依赖：

- AFE4490 血氧模块完成；
- NIBP 模块完成；
- TEMP 模块完成；
- ADS1292R 完成；
- CAN 完成；
- Gateway-C 实物完成。

---

# 2. 设计原则

## 2.1 云端内部数据模型与设备线协议解耦

MMP/2 当前只冻结语义和职责，不冻结最终二进制字节布局。

因此云端程序采用：

```text
Device Transport Adapter
        ↓
统一内部数据模型
        ↓
状态 / 记录 / WebSocket / Web UI
```

第一阶段实现：

```text
MockJsonAdapter
```

后续真实 Gateway-C 接入时增加：

```text
MMP2Adapter
```

Backend 的业务层、数据库层和 Web 层保持不变。

这样不会因为后续 MMP/2 字节帧调整而推翻云端代码。

## 2.2 Mock Gateway 必须模拟真实系统语义

至少模拟：

- Node-A Online / Offline；
- Node-B Online / Offline；
- PPG；
- SpO2；
- PR；
- NIBP；
- TEMP；
- ECG；
- HR；
- RESP；
- RR；
- Gateway 状态；
- LIVE；
- REPLAY；
- Invalid / Stale 等质量状态。

---

# 3. 推荐技术栈

在当前规模下采用轻量、稳定方案：

```text
腾讯云现有 Nginx
        ↓
FastAPI + Uvicorn
        ↓
WebSocket Hub
        ↓
Web Frontend
```

前端建议：

- Vite + TypeScript；
- Canvas 2D 绘制高频波形；
- 不在第一阶段引入复杂图形框架。

部署原则：

- 复用服务器现有 Nginx；
- Backend 仅监听 `127.0.0.1`；
- 公网只开放 80/443；
- 不新启第二套 Nginx 占用 80/443。

---

# 4. 第一阶段目录建议

```text
cloud/
├── backend/
│   ├── app/
│   ├── requirements.txt
│   └── README.md
│
├── web/
│   ├── src/
│   └── README.md
│
├── deploy/
│   ├── nginx/
│   └── README.md
│
└── tools/
    └── mock_gateway/
```

目录只是职责边界，不要求现在把最终工程结构全部冻结。

---

# 5. 执行步骤

## P0-1：创建独立开发分支和云端工作区

目标：

- 从稳定 `main` 创建 P 的独立开发分支；
- 不直接在 `main` 上进行云端开发；
- 建立 cloud/backend/web/deploy/tools 基本目录。

建议分支名：

```text
dev/p-cloud-phase1
```

验收：

- 分支独立；
- `main` 不受开发中代码影响；
- README 说明启动方式。

## P0-2：Backend 最小服务

实现：

- `/health`；
- Gateway 模拟接入 WebSocket；
- Browser 监护 WebSocket；
- Gateway / Node 在线状态；
- 基本日志；
- 开发阶段 Token 从环境变量读取。

验收：

```text
curl /health
→ 200 OK
```

Mock Gateway 建立 WSS 后，Backend 能显示 Gateway 已连接。

## P0-3：Mock Gateway

Mock Gateway 在本地运行，模拟：

```text
GW-DEV-001
├── NODE-A
│   ├── PPG
│   ├── SpO2
│   ├── PR
│   └── NIBP
│
└── NODE-B
    ├── TEMP
    ├── ECG
    ├── HR
    ├── RESP
    └── RR
```

要求可主动切换：

- Online / Offline；
- LIVE / REPLAY；
- 正常值 / Invalid；
- 网络断开 / 重连。

Mock 数据仅用于系统开发，网页必须显示为 `SIMULATION` 或 `MOCK`，避免与真实测量数据混淆。

## P0-4：Web 大屏 MVP

第一阶段页面至少完成：

- Gateway 状态；
- Node-A / Node-B 状态；
- ECG 模拟波形；
- PPG 模拟波形；
- RESP 模拟波形；
- HR；
- RR；
- SpO2；
- NIBP；
- TEMP；
- 数据最后更新时间。

当前目标是验证数据通路与页面架构，不要求第一版 UI 达到最终视觉效果。

## P0-5：腾讯云 Nginx 部署

建议使用独立子域名：

```text
monitor.<your-domain>
```

Nginx 路径规划建议：

```text
/                  Web
/api/              REST
/device/v1/ingest  Gateway WebSocket
/ws/v1/monitor     Browser WebSocket
```

要求：

- HTTPS；
- WSS；
- Backend 不直接公网监听；
- WebSocket Upgrade 正常；
- 日志可查看；
- 配置修改前备份现有 Nginx 配置；
- `nginx -t` 通过后才 reload。

## P0-6：端到端模拟验收

验证链路：

```text
Mock Gateway
    ↓
Internet / WSS
    ↓
Nginx
    ↓
Backend
    ↓
Web Browser
```

测试：

1. Mock Gateway 连上后页面显示 Online；
2. 停止 Mock Gateway 后页面变为 Offline/Stale；
3. 模拟 ECG/PPG/RESP 可连续绘制；
4. 标量值可刷新；
5. 浏览器刷新后能够重新订阅；
6. Backend 重启后能恢复；
7. Nginx reload 不破坏其他站点；
8. Mock REPLAY 不被显示成当前 LIVE 数据。

---

# 6. 阶段时间建议

P 第一阶段建议 **5～7 个工作日**：

| 时间 | 工作 |
|---|---|
| Day 1 | 分支、目录、Backend `/health`、Nginx 现状备份 |
| Day 2 | Gateway/Browse WebSocket 与内部数据模型 |
| Day 3 | Mock Gateway + 多参数模拟 |
| Day 4 | Web 大屏 MVP |
| Day 5 | 腾讯云 Nginx / HTTPS / WSS 部署 |
| Day 6 | 故障场景与状态测试 |
| Day 7 | 文档、问题整改、阶段验收 |

若已有成熟服务器环境，可压缩；不得为赶工跳过配置备份和 WSS 验证。

---

# 7. 本阶段交付物

```text
cloud/backend/*
cloud/web/*
cloud/deploy/*
cloud/tools/mock_gateway/*
doc/P/P_第一阶段云端执行报告.md
doc/P/P_云端接口语义说明.md
doc/P/P_云端部署与回滚说明.md
```

至少保留：

- Nginx 配置备份；
- 启动方式；
- 环境变量模板；
- Mock Gateway 使用方法；
- 测试截图/日志；
- 已知问题。

---

# 8. 准出条件

满足以下条件，即可认为 P 的云端第一阶段完成：

```text
[ ] 腾讯云 HTTPS 正常
[ ] Gateway WSS 入口正常
[ ] Browser WSS 正常
[ ] Mock Gateway 可以连续发送多参数模拟数据
[ ] Web 能显示 ECG / PPG / RESP 和关键标量
[ ] Node-A / Node-B 在线状态可变化
[ ] LIVE / REPLAY 可以区分
[ ] Invalid 数据不会被显示成正常值
[ ] Backend 不直接暴露公网端口
[ ] 现有 Nginx 其他站点不受影响
[ ] 第二人可按 README 在干净环境启动 Backend/Mock
```

---

# 9. 与后续 Gateway-C 的交接

真实 Gateway-C 完成后，集成步骤应为：

```text
Mock Gateway
    ↓ 替换
STM32F407-C + ESP8266-C
    ↓
MMP/2 Adapter
    ↓
同一 Backend 内部数据模型
    ↓
现有 Web
```

如果后续 MMP/2 二进制格式调整，只修改 Gateway-C 编码和 Backend 的 `MMP2Adapter`，不修改 Web 业务层。

这就是 P 现在提前完成云端的核心价值。

---

# 10. 本阶段不做

为控制范围，第一阶段暂不做：

- 最终医疗 UI 美化；
- 真实患者数据长期存储；
- 复杂用户权限系统；
- MQTT；
- A/B ESP 冷备用；
- Gateway 离线 Flash 缓存；
- 正式 MMP/2 字节级协议；
- 最终数据库选型；
- 最终报警规则。

这些在真实 Gateway-C 和传感器数据进入后逐步补充。
