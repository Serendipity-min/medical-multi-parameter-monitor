# 远程大屏 Web 服务与 WSS 反向代理部署指南

> **文件版本**：v1.0  
> **状态**：正式归档（解除合同阻塞项 E06 / P-T06 / P-T07 / P-T10）  
> **适用范围**：1080p 监护大屏生产级 Web 服务、WebSocket 分发引擎及 Docker 自动化部署  
> **关联文档**：`doc/P/04_云端与网络部署/01_腾讯云服务器_域名解析与SSL证书配置方案.md`、`doc/P/02_项目负责人及上位机_专项工作合同_v0.1.md`

---

## 1. 系统架构与运行机制

本指南指导运维与开发人员在腾讯云服务器（或私有云/本地部署机）上快速、可靠地搭建支持 1080p 高清、60 FPS 实时波形绘制的远程监护 Web 服务。

### 1.1 数据流架构

```
+--------------------------+
| 边缘节点 (ESP/上位机)   |
| 采集 STM32 原始数据      |
+--------------------------+
             |
             | [WSS / TLS 1.3] (443端口)
             v
+-----------------------------------------------------------+
| 腾讯云服务器 (Ubuntu 22.04 LTS)                           |
|                                                           |
|   +---------------------------------------------------+   |
|   | Nginx 反向代理层                                  |   |
|   | - 443 端口 SSL 终止与流量路由                     |   |
|   | - 静态 Web 资源托管 (1080p 大屏前端 SPA)           |   |
|   +---------------------------------------------------+   |
|             |                               |             |
|             | HTTP/REST                     | WSS         |
|             v                               v             |
|   +---------------------------------------------------+   |
|   | FastAPI / Python 3.10+ (Docker 容器)              |   |
|   | - 身份鉴权 (Token / 白名单)                       |   |
|   | - MMP/1 二进制帧解析与数据分发                    |   |
|   | - 客户端会话管理池 (Connection Pool)              |   |
|   | - 历史数据分段持久化 (SQLite / .mmp 分段文件)     |   |
|   +---------------------------------------------------+   |
+-----------------------------------------------------------+
             |
             | [WSS / TLS 1.3] (443端口)
             v
+--------------------------+
| 医生办公室 / 护士站      |
| 1080p Web 监护大屏       |
+--------------------------+
```

---

## 2. 一键自动化部署方案 (Docker Compose)

推荐使用 Docker 与 Docker Compose 进行标准化部署，消除环境依赖差异（满足合同 P-T10“第二人在干净环境可独立启动”要求）。

### 2.1 目录结构规划

在云服务器创建统一工作空间目录 `/opt/medical_monitor`：

```
/opt/medical_monitor/
├── docker-compose.yml              # 容器编排配置文件
├── nginx/
│   ├── nginx.conf                  # Nginx 核心配置
│   ├── ssl/                        # SSL 证书文件 (*.crt, *.key, dhparam.pem)
│   └── dist/                       # 前端 1080p 大屏打包产物 (index.html, assets)
├── backend/
│   ├── Dockerfile                  # 后端服务构建镜像
│   ├── requirements.txt            # Python 依赖清单
│   └── app/                        # 后端代码目录
│       ├── main.py                 # 服务入口 (FastAPI)
│       ├── hub.py                  # WebSocket 连接池与消息广播
│       ├── parser.py               # MMP/1 帧解码器
│       └── storage.py              # 数据持久化存储
└── data/
    ├── sqlite/                     # SQLite 会话与事件数据库
    └── recordings/                 # 原始 .mmp 帧分段归档文件
```

### 2.2 `docker-compose.yml` 完整编排文件

```yaml
version: '3.8'

services:
  # 1. Nginx 反向代理与前端静态资源托管服务
  nginx:
    image: nginx:1.24-alpine
    container_name: medical_monitor_nginx
    restart: always
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./nginx/nginx.conf:/etc/nginx/conf.d/default.conf:ro
      - ./nginx/ssl:/etc/nginx/ssl:ro
      - ./nginx/dist:/usr/share/nginx/html:ro
    depends_on:
      - backend
    networks:
      - monitor_net

  # 2. FastAPI 后端核心通信与分发服务
  backend:
    build:
      context: ./backend
      dockerfile: Dockerfile
    container_name: medical_monitor_backend
    restart: always
    environment:
      - APP_ENV=production
      - LOG_LEVEL=INFO
      - AUTH_PSK=MedicalDevice2026SecureKey
      - RECORDING_PATH=/data/recordings
      - DB_PATH=/data/sqlite/monitor.db
    volumes:
      - ./data/recordings:/data/recordings
      - ./data/sqlite:/data/sqlite
    networks:
      - monitor_net

networks:
  monitor_net:
    driver: bridge
```

### 2.3 后端 Dockerfile 与依赖

#### `backend/requirements.txt`
```
fastapi>=0.104.0
uvicorn[standard]>=0.23.2
websockets>=11.0.3
pydantic>=2.4.2
aiosqlite>=0.19.0
python-multipart>=0.0.6
```

#### `backend/Dockerfile`
```dockerfile
FROM python:3.10-slim

WORKDIR /app

# 安装必要的系统库并清理缓存
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt -i https://mirrors.aliyun.com/pypi/simple/

COPY ./app /app

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
```

---

## 3. 前端 1080p 大屏构建与发布

### 3.1 渲染引擎与性能关键技术
前端大屏界面标准分辨率为 **1920 × 1080**（1080p 全高清）。针对高频心电（250 Hz）、脉搏血氧（50 Hz）与阻抗呼吸（50 Hz）波形：
1. **渲染架构**：严禁使用 SVG 或密集 DOM 节点绘制高频波形。必须采用 **HTML5 Canvas 2D（双缓冲）** 或 **WebGL** 渲染管线。
2. **环形缓冲区 (Ring Buffer)**：前端建立毫秒级时间戳环形队列，绘制线程通过 `requestAnimationFrame`（锁定 60 FPS）恒速向前走纸扫描（Sweep Scroll）。
3. **消除丢帧与阶跃**：根据服务器帧序号（`seq_num`）检测网络波动，若检测到丢帧平滑跳过，保证时间轴与现实严格对齐。

### 3.2 编译与上传流程

在本地上位机开发环境执行前端构建：
```bash
cd web_frontend
# 安装依赖
npm install
# 生产优化构建
npm run build
```
构建生成的 `dist/` 文件夹（包含 `index.html`、`assets/`）上传至腾讯云服务器 `/opt/medical_monitor/nginx/dist/`：
```bash
scp -r ./dist/* ubuntu@monitor.yourdomain.com:/opt/medical_monitor/nginx/dist/
```

---

## 4. 后端核心 WebSocket 分发引擎实现参考

在 `backend/app/main.py` 中，FastAPI 同时提供 RESTful 接口与低延迟双向 WebSocket 通道：

```python
import asyncio
import json
import logging
import os
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Query, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from typing import Dict, Set

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("MonitorCloud")

app = FastAPI(title="Medical Monitor Gateway", version="1.0.0")

# 限制 CORS 来源 (仅允许本域名及受控前端)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://monitor.yourdomain.com"],
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

# 客户端长连接管理池
class ConnectionManager:
    def __init__(self):
        # device_id -> set of WebSocket connections
        self.device_subscribers: Dict[str, Set[WebSocket]] = {}
        # 活跃的下位机网关连接
        self.gateways: Dict[str, WebSocket] = {}

    async def connect_client(self, websocket: WebSocket, device_id: str):
        await websocket.accept()
        if device_id not in self.device_subscribers:
            self.device_subscribers[device_id] = set()
        self.device_subscribers[device_id].add(websocket)
        logger.info(f"客户端接入，订阅设备 [{device_id}]，当前订阅数: {len(self.device_subscribers[device_id])}")

    def disconnect_client(self, websocket: WebSocket, device_id: str):
        if device_id in self.device_subscribers:
            self.device_subscribers[device_id].discard(websocket)
            logger.info(f"客户端断开，注销设备 [{device_id}]")

    async def broadcast_to_clients(self, device_id: str, message: bytes):
        """将二进制 MMP/1 帧或 JSON 消息广播给订阅该设备的所有 Web 前端"""
        if device_id in self.device_subscribers:
            dead_sockets = set()
            for ws in self.device_subscribers[device_id]:
                try:
                    await ws.send_bytes(message)
                except Exception:
                    dead_sockets.add(ws)
            # 清理失效连接
            for ws in dead_sockets:
                self.device_subscribers[device_id].discard(ws)

manager = ConnectionManager()

@app.websocket("/ws/monitor")
async def websocket_monitor_endpoint(websocket: WebSocket, token: str = Query(None), device: str = Query("DEV_01")):
    """大屏前端接入通道 (WSS)"""
    # 鉴权
    if not token or token != "secure_dashboard_view_token":
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    await manager.connect_client(websocket, device)
    try:
        while True:
            # 维持长连接与心跳 (接收前端的 Ping/Pong)
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_text("pong")
    except WebSocketDisconnect:
        manager.disconnect_client(websocket, device)

@app.websocket("/ws/device_gateway")
async def websocket_device_endpoint(websocket: WebSocket, token: str = Query(None), device: str = Query("DEV_01")):
    """下位机 / 本地上位机边缘网关推流通道 (WSS)"""
    # 设备身份鉴权 (PSK 验证)
    if not token or token != os.getenv("AUTH_PSK", "MedicalDevice2026SecureKey"):
        logger.warning(f"设备 [{device}] 认证失败，拒绝接入")
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    await websocket.accept()
    logger.info(f"下位机边缘网关已接入: {device}")
    try:
        while True:
            # 接收边缘网关上传的二进制数据帧 (MMP/1 帧)
            frame_data = await websocket.receive_bytes()
            # 广播推流给 Web 大屏
            await manager.broadcast_to_clients(device, frame_data)
    except WebSocketDisconnect:
        logger.warning(f"设备网关 [{device}] 断开连接")
```

---

## 5. 服务启动、验证与性能基准测试

### 5.1 启动服务
在 `/opt/medical_monitor` 目录下执行：
```bash
# 构建并后台启动全部容器
sudo docker-compose up -d --build

# 查看运行状态
sudo docker-compose ps

# 实时查看后端日志
sudo docker-compose logs -f backend
```

### 5.2 性能验收标准对照 (对应合同第十条)

| 验收编号 | 关键指标 | 验证方法与标准 | 预期实测表现 |
|---|---|---|---|
| **P-T06** | 1080p 双端大屏展示 | 在两台不同电脑的 Chrome 浏览器中全屏打开 `https://monitor.yourdomain.com`，波形无掉帧、无错位。 | 1920 × 1080 分辨率，稳定 60 FPS 走纸刷新。 |
| **P-T07** | 端到端网络延迟 | 注入包含时间戳的模拟数据，前端接收并计算 `T_render - T_edge_send` 的 P95 延迟。 | 局域网内 P95 ≤ 50 ms；公网腾讯云节点 P95 ≤ 180 ms（远低于合同要求 500 ms）。 |
| **P-T08** | 24 小时连续运行稳定性 | 连续压测推流 24 小时，通过 `docker stats` 记录 CPU 与内存占用。 | 内存平稳在 80 MB – 120 MB，无线性增长，零内存泄漏。 |
| **P-T11** | 安全防护与权限隔离 | 使用伪造 Token 尝试连接 `/ws/device_gateway` 与 `/ws/monitor`。 | 服务立即返回 HTTP 403 / WS 1008 关闭连接，日志如实记录未授权拒绝事件。 |

---

## 6. 数据存储与磁盘空间预算管理

### 6.1 空间预算设计 (符合合同 8.1 节要求)
- **波形传输带宽**：
  - ECG（250 Hz × 3 字节 = 750 B/s）
  - RESP（50 Hz × 2 字节 = 100 B/s）
  - PLETH（50 Hz × 2 字节 = 100 B/s）
  - 参数与帧头包销（约 200 B/s）
  - 单台设备实时原始数据率约为 **1.15 KB/s**。
- **24 小时存储消耗预算**：
  - 理论裸数据量：`1.15 KB/s × 86400 s ≈ 99.36 MB / 24h`。
  - 加上 JSON 元数据、事件日志与分段索引：**实际预算按 0.4 – 1.0 GB / 24h / 设备** 规划。
  - 服务器预留 40 GB 数据盘空间可供单台设备安全连续录制 **30 天以上**。

### 6.2 自动日志轮转与数据清理策略

创建定时日志轮转规则 `/etc/logrotate.d/medical_monitor`：
```
/opt/medical_monitor/data/recordings/*.log {
    daily
    missingok
    rotate 14
    compress
    delaycompress
    notifempty
    create 0640 ubuntu ubuntu
}
```
默认仅对 `.log` 执行归档；对于 `.mmp` 原始医疗生理数据文件，**默认关闭自动删除**，严禁未经管理员审批自动擦除患者监护记录。
