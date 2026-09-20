# 腾讯云服务器、域名解析与 SSL 证书配置方案

> **文件版本**：v1.0  
> **状态**：正式归档（解除合同阻塞项 E06 / S06 / S07）  
> **适用范围**：多参数心电监护仪系统样机远程大屏、云端 Web API 与 WSS 安全代理  
> **关联文档**：`doc/00_G0准入审查与合同阻塞项消除报告.md`、`doc/P/04_云端与网络部署/02_远程大屏Web服务与WSS反向代理部署指南.md`

---

## 1. 架构目标与安全边界说明

在系统初期开发阶段，系统优先在**实验室受控局域网**内进行 TCP 原始帧调试与回环大屏测试。为了满足远程多终端监护、专家会诊接入以及移动端异地实时查看等拓展需求，必须提供标准、合规、可靠的公网安全云端接入方案。

### 1.1 系统拓扑架构

```
+---------------------------+       LAN/Wi-Fi (802.11 b/g/n)
| 监护仪下位机 (STM32F407)  | ----------------------------------+
| + 模块采集 (ECG/SpO2/NIBP)|                                    |
+---------------------------+                                    v
                                                  +------------------------------+
                                                  | 局域网网关 / 本地上位机 (PC)  |
                                                  | 或 ESP8266/ESP32 Wi-Fi 模块  |
                                                  +------------------------------+
                                                                 |
                                                                 | HTTPS / WSS (TLS 1.2/1.3)
                                                                 | 互联网公网加密信道
                                                                 v
                                                  +------------------------------+
                                                  | 腾讯云服务器 (Lighthouse/CVM)|
                                                  | Public IP + 备案域名 (DNS)   |
                                                  |  +------------------------+  |
                                                  |  | Nginx 反向代理 (443)   |  |
                                                  |  | SSL 证书卸载 / WSS 转发|  |
                                                  |  +------------------------+  |
                                                  |              | (127.0.0.1)   |
                                                  |              v               |
                                                  |  +------------------------+  |
                                                  |  | FastAPI / Node.js 核心 |  |
                                                  |  | WebSocket 分发引擎     |  |
                                                  |  +------------------------+  |
                                                  +------------------------------+
                                                                 |
                                            +--------------------+--------------------+
                                            | (HTTPS / WSS)                           | (HTTPS / WSS)
                                            v                                         v
                             +-----------------------------+           +-----------------------------+
                             | 1080p 远程 Web 监护大屏     |           | 移动端 / 平板远程监控页     |
                             | (Chrome / Edge 浏览器)      |           | (响应式 HTML5 / Canvas)     |
                             +-----------------------------+           +-----------------------------+
```

### 1.2 安全基线与合规原则

1. **明文禁止直接暴露设备**：严禁将监护仪下位机的裸 TCP 端口（如附录 A 的 9001 端口）直接做公网 NAT 映射或直接监听公网。
2. **强制全链路传输加密**：所有跨公网交互必须经过 TLS 1.2 或 TLS 1.3 加密，禁止使用 HTTP 或不加密的 WS。
3. **关键控制指令公网锁死**：远程袖带充气（NIBP Start）等可能危害患者肢体安全的控制命令，默认在公网云端完全锁定。公网接口仅作为**单向监护数据流查看与告警订阅**通道。

---

## 2. 腾讯云服务器规格与环境选型

### 2.1 推荐硬件与实例规格

针对多参数心电监护仪系统样机（支持 1–4 台设备接入，50–100 个客户端并发观看，1080p Web 大屏持续 60 FPS 渲染）：

| 资源类别 | 推荐配置 | 最低配置 | 说明 |
|---|---|---|---|
| **实例类型** | 腾讯云轻量应用服务器 (Lighthouse) 或 CVM | 腾讯云轻量应用服务器 | 轻量应用服务器性价比高，自带流量包 |
| **CPU / 内存** | 2 核 CPU / 4 GB 内存 | 2 核 CPU / 2 GB 内存 | 4 GB 内存可充裕运行 Nginx + Python/Node.js + SQLite/Redis |
| **系统盘** | 60 GB SSD / 高性能云硬盘 | 40 GB SSD | 用于存储系统日志与原始数据分段缓存 |
| **公网带宽** | 5 Mbps – 8 Mbps 峰值 | 3 Mbps 峰值 | 1 台监护仪全参数波形约 15–25 KB/s，5 Mbps 可支持 20+ 客户端流畅并发 |
| **操作系统** | Ubuntu Server 22.04 LTS 64位 | Debian 11 / Ubuntu 20.04 | 统一采用 Debian/Ubuntu 系，软件包稳定且安全补丁更新及时 |

### 2.2 腾讯云安全组（防火墙）规则配置

在腾讯云控制台【安全组 / 防火墙】中严格配置入站规则，未声明端口一律默认拒绝：

| 优先级 | 协议类型 | 端口范围 | 源 IP | 策略 | 用途说明 |
|---|---|---|---|---|---|
| 1 | TCP | `22` | 管理员公网 IP 或 `0.0.0.0/0` (建议限定IP) | 允许 | SSH 远程管理维护（建议改端口或仅公钥认证） |
| 2 | TCP | `80` | `0.0.0.0/0` | 允许 | HTTP 端口（仅用于 Let's Encrypt 证书验证及自动 301 重定向至 443） |
| 3 | TCP | `443` | `0.0.0.0/0` | 允许 | HTTPS / WSS 核心安全端口，Web 静态资源与 WebSocket 流量统一入口 |
| 4 | 全部 | 全部 | `0.0.0.0/0` | **拒绝** | 拦截所有其他端口（如 8000、3000、3306、6379、9001，严禁对外暴露） |

---

## 3. 域名注册与 DNS 解析配置

### 3.1 域名解析规范

建议为医疗监护系统分配独立二级子域名（例如 `monitor.yourdomain.com`）：

1. 进入**腾讯云 DNSPod 控制台**（或其它域名注册商 DNS 管理面板）。
2. 添加解析记录：
   - **主机记录**：`monitor`（对应完整域名 `monitor.yourdomain.com`）
   - **记录类型**：`A`
   - **线路类型**：默认
   - **记录值**：填入腾讯云服务器公网 IPv4 地址（如 `123.xx.xx.xx`）
   - **TTL**：`600`（10 分钟）
3. 验证解析生效：
   在本地终端执行命令验证：
   ```bash
   ping monitor.yourdomain.com
   # 或者使用 nslookup
   nslookup monitor.yourdomain.com
   ```
   输出 IP 与腾讯云公网 IP 一致即代表解析配置成功。

### 3.2 备案须知与应对策略

> [!IMPORTANT]
> **中国大陆境内服务器 ICP 备案合规性**：  
> 若腾讯云服务器节点位于中国大陆境内（如北京、上海、广州、成都等），依据工信部规定，域名必须完成 **ICP 备案**及**公安联网备案**。未备案域名的 HTTP/80 与 HTTPS/443 流量会在云厂商边界直接被拦截阻断并重定向至备案提示页。  
> 
> **研发期过渡方案**：
> 1. **已有已备案域名**：直接在已有备案主域名下解析二级子域名（二级子域名共享主域名备案资质，无需重复申请）。
> 2. **免备案过渡节点**：若尚无备案域名且需立即进行外网联调，可选择腾讯云中国香港（Hong Kong）或海外节点轻量服务器，无需备案即可直接通过 80/443 访问。
> 3. **公网 IP + 自签名证书 / 动态 DNS（仅限内部测试）**：在无域名情况下，可通过公网 IP 直连并在 Nginx 部署自签名证书，客户端通过关闭证书强校验进行样机内测（生产环境禁止）。

---

## 4. SSL / TLS 证书申请与管理

为了保障浏览器与云端服务器之间的通信安全，并规避现代浏览器对 WebCrypto / WebSocket 的安全限制（混合内容限制 Mixed Content Policy 要求 HTTPS 页面中必须使用 WSS:// 协议），必须为域名部署由受信任 CA 颁发的数字证书。

### 方案 A：腾讯云免费 TrustAsia DV SSL 证书（推荐）

适合腾讯云全套托管用户，图形化申请，操作简单：

1. 登录腾讯云控制台，进入【SSL 证书】产品页。
2. 点击【申请免费证书】：
   - 证书类型：TrustAsia 域名型型 (DV) 免费版
   - 保护域名：输入 `monitor.yourdomain.com`
   - 验证方式：选择【DNS 验证】（若域名在腾讯云解析，勾选“自动添加 DNS 解析”，系统将在数分钟内自动完成校验并签发）。
3. 证书签发后，点击【下载】：
   - 服务器类型选择 `Nginx`。
   - 解压后获得两个核心文件：
     - `monitor.yourdomain.com_bundle.crt`（包含证书公钥及中间 CA 证书链）
     - `monitor.yourdomain.com.key`（证书私钥，切勿泄露）
4. 上传证书至服务器：
   ```bash
   sudo mkdir -p /etc/nginx/ssl
   # 将 crt 与 key 拷贝到该目录
   sudo chmod 600 /etc/nginx/ssl/monitor.yourdomain.com.key
   ```

---

### 方案 B：Let's Encrypt + Certbot 自动化签发与自动续期

适合全自动化运维，免费签发，支持定时自动续期。

#### 1. 安装 Certbot 及 Nginx 插件
```bash
sudo apt update
sudo apt install -y certbot python3-certbot-nginx
```

#### 2. 一键申请证书
确保域名 DNS 已正确解析至本机，且防火墙已放行 80/443 端口：
```bash
sudo certbot --nginx -d monitor.yourdomain.com
```
在交互向导中输入通知邮箱、同意许可协议，Certbot 会自动验证域名并生成证书文件，证书路径默认保存在：
- 证书链：`/etc/letsencrypt/live/monitor.yourdomain.com/fullchain.pem`
- 私钥：`/etc/letsencrypt/live/monitor.yourdomain.com/privkey.pem`

#### 3. 验证与配置自动续期
Let's Encrypt 证书有效期为 90 天，Certbot 自带 systemd timer 定时器。测试自动续期机制：
```bash
sudo certbot renew --dry-run
```
若提示 `Congratulations, all simulated renewals succeeded`，则表示定时续期系统运行正常。

---

## 5. Nginx 高性能反向代理与 WSS 核心配置

Nginx 作为云端流量统一入口，承担三项核心职责：
1. **HTTP (80) 全站强制跳转 HTTPS (443)**；
2. **托管 Web 1080p 监护大屏静态资产（HTML/JS/CSS/WebAudio 报警音效）**；
3. **反向代理后端 RESTful API (`/api/`) 及长连接 WebSocket / WSS (`/ws/`)**。

### 5.1 生成高强度 Diffie-Hellman 参数（推荐安全强化）
```bash
sudo openssl dhparam -out /etc/nginx/ssl/dhparam.pem 2048
```

### 5.2 生产环境 Nginx 完整配置文件

编辑 `/etc/nginx/sites-available/medical_monitor.conf`：

```nginx
# 1. HTTP 流量强制跳转至 HTTPS
server {
    listen 80;
    listen [::]:80;
    server_name monitor.yourdomain.com;

    # 用于 ACME / Let's Encrypt 挑战验证
    location /.well-known/acme-challenge/ {
        root /var/www/html;
    }

    location / {
        return 301 https://$host$request_uri;
    }
}

# 2. HTTPS / WSS 核心服务配置
server {
    listen 443 ssl http2;
    listen [::]:443 ssl http2;
    server_name monitor.yourdomain.com;

    # SSL 证书与私钥路径 (以腾讯云证书为例，Let's Encrypt 请替换为 fullchain.pem 与 privkey.pem)
    ssl_certificate /etc/nginx/ssl/monitor.yourdomain.com_bundle.crt;
    ssl_certificate_key /etc/nginx/ssl/monitor.yourdomain.com.key;
    ssl_dhparam /etc/nginx/ssl/dhparam.pem;

    # TLS 安全协议与现代密码套件 (禁用 SSLv3, TLS 1.0, TLS 1.1)
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers 'ECDHE-ECDSA-AES128-GCM-SHA256:ECDHE-RSA-AES128-GCM-SHA256:ECDHE-ECDSA-AES256-GCM-SHA384:ECDHE-RSA-AES256-GCM-SHA384:DHE-RSA-AES128-GCM-SHA256:DHE-RSA-AES256-GCM-SHA384';
    ssl_prefer_server_ciphers on;

    # SSL 会话缓存优化 (提升握手性能)
    ssl_session_cache shared:SSL:10m;
    ssl_session_timeout 1d;
    ssl_session_tickets off;

    # 安全响应头加固
    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;
    add_header X-Content-Type-Options nosniff always;
    add_header X-Frame-Options SAMEORIGIN always;
    add_header X-XSS-Protection "1; mode=block" always;

    # Gzip 压缩传输 (大幅降低大屏前端资源加载耗时)
    gzip on;
    gzip_vary on;
    gzip_min_length 1024;
    gzip_proxied expired no-cache no-store private auth;
    gzip_types text/plain text/css text/xml text/javascript application/x-javascript application/xml application/json;
    gzip_disable "MSIE [1-6]\.";

    # -------------------------------------------------------------
    # 静态 Web 资源托管 (1080p 大屏前端)
    # -------------------------------------------------------------
    root /var/www/medical_monitor/dist;
    index index.html;

    location / {
        try_files $uri $uri/ /index.html;
        expires 1h;
        add_header Cache-Control "public, no-transform";
    }

    # 静态资源缓存控制 (带哈希的文件永久缓存)
    location ~* \.(?:ico|css|js|gif|jpe?g|png|woff2?|eot|ttf|svg|wav|mp3)$ {
        expires 30d;
        add_header Cache-Control "public, max-age=2592000, immutable";
        access_log off;
    }

    # -------------------------------------------------------------
    # RESTful API 反向代理 (/api/)
    # -------------------------------------------------------------
    location /api/ {
        proxy_pass http://127.0.0.1:8000/;
        proxy_http_version 1.1;

        # 传递真实客户端 IP 与主机头
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        # 超时设置
        proxy_connect_timeout 10s;
        proxy_read_timeout 60s;
        proxy_send_timeout 60s;
    }

    # -------------------------------------------------------------
    # WebSocket / WSS 长连接反向代理 (/ws/)
    # 用于传输多参数实时高频波形 (ECG 250Hz, SpO2 50Hz, RESP 50Hz)
    # -------------------------------------------------------------
    location /ws/ {
        proxy_pass http://127.0.0.1:8000/ws/;
        proxy_http_version 1.1;

        # WebSocket 协议升级核心头
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";

        # 客户端信息透传
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        # 关闭代理缓冲区 (实现低延迟实时推流)
        proxy_buffering off;
        proxy_cache off;

        # 保持连接超时设置 (防止云端代理由于无交互切断长连接)
        # 心跳包建议设置为 5-10s 一次，read_timeout 设为 3600s
        proxy_read_timeout 3600s;
        proxy_send_timeout 3600s;
    }

    # 拒绝访问隐藏文件
    location ~ /\. {
        deny all;
        access_log off;
        log_not_found off;
    }
}
```

### 5.3 启用配置并测试
```bash
# 创建软链接启用站点
sudo ln -sf /etc/nginx/sites-available/medical_monitor.conf /etc/nginx/sites-enabled/

# 检查 Nginx 语法
sudo nginx -t

# 重新平滑加载配置
sudo systemctl reload nginx
```

---

## 6. 客户端安全连接示例与验证

### 6.1 前端大屏安全连接 (JavaScript / TypeScript)

前端大屏通过原生 WebSocket 发起 WSS 连接，利用浏览器内建的 TLS 堆栈自动进行 CA 证书强校验：

```javascript
// 生产环境自动适配 wss:// 协议与当前域名
const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
const host = window.location.host;
const wsUrl = `${protocol}//${host}/ws/monitor?token=${encodeURIComponent(sessionAuthToken)}`;

const ws = new WebSocket(wsUrl);

ws.binaryType = 'arraybuffer'; // 接收高频二进制压缩波形帧

ws.onopen = () => {
    console.log('[WSS] 成功建立加密长连接通道');
    // 发送身份验证与流订阅请求
    ws.send(JSON.stringify({
        type: 'SUBSCRIBE',
        device_id: 'MONITOR_NODE_01',
        channels: ['ECG_LEAD_II', 'RESP', 'PLETH', 'PARAMS']
    }));
};

ws.onmessage = (event) => {
    if (event.data instanceof ArrayBuffer) {
        // 二进制高性能解析波形
        parseBinaryWaveformFrame(event.data);
    } else {
        // JSON 参数与生理告警
        const msg = JSON.parse(event.data);
        handleTelemetryMessage(msg);
    }
};

ws.onerror = (err) => {
    console.error('[WSS] 连接异常:', err);
};

ws.onclose = (event) => {
    console.warn(`[WSS] 连接关闭 (code: ${event.code}), 启动指数退避重连...`);
    scheduleReconnect();
};
```

### 6.2 边缘网关 / 本地上位机推流安全客户端 (Python)

本地上位机或 ESP8266 网关向云端转发 MMP/1 数据时，同样必须通过安全 SSL 封装：

```python
import asyncio
import ssl
import websockets
import json

SERVER_WSS_URL = "wss://monitor.yourdomain.com/ws/device_gateway"
DEVICE_PSK = "medical_device_secret_key_2026"
DEVICE_ID = "DEV_F407_001"

async def device_cloud_push_loop():
    # 严格校验云端证书链
    ssl_context = ssl.create_default_context()
    
    headers = {
        "X-Device-ID": DEVICE_ID,
        "X-Auth-Token": DEVICE_PSK
    }
    
    while True:
        try:
            print(f"正在建立云端 WSS 安全通道: {SERVER_WSS_URL}")
            async with websockets.connect(SERVER_WSS_URL, ssl=ssl_context, extra_headers=headers) as ws:
                print("云端通道连接成功，开始上报监护遥测数据...")
                while True:
                    # 模拟读取本地下位机 MMP/1 帧并加密推送到云端
                    payload = await get_next_mmp_frame_from_local_stm32()
                    await ws.send(payload)
        except Exception as e:
            print(f"云端推流中断: {e}，5秒后重试...")
            await asyncio.sleep(5)

if __name__ == "__main__":
    asyncio.run(device_cloud_push_loop())
```

---

## 7. 故障排查与运行维护清单

| 故障现象 | 可能诱因 | 检查与排查手段 |
|---|---|---|
| **浏览器提示“证书无效 / 不安全”** | 证书域名不匹配、中间证书缺失或证书已过期 | ① 检查 Nginx 是否配置完整的 `bundle.crt`（含中间 CA）；② 检查访问域名与证书 CN 是否完全一致；③ 使用 `certbot certificates` 查看有效期。 |
| **WSS 连接报错 1006 / 403 Forbidden** | Nginx 未正确处理协议升级头，或反代超时中断 | ① 检查 Nginx 中 `proxy_set_header Upgrade $http_upgrade;` 与 `Connection "upgrade";`；② 检查后端服务是否正常运行监听 8000；③ 检查后端 CORS / Origin 白名单。 |
| **公网无法访问（超时）** | 腾讯云安全组未放行 443 端口，或域名未备案被阻断 | ① 登录腾讯云控制台检查实例防火墙 443 入站规则；② 检查域名在工信部的 ICP 备案状态；③ 在服务器本机 `curl -k https://127.0.0.1` 确认服务本地存活。 |
| **大屏波形卡顿、偶发断线** | Nginx `proxy_buffering` 开启导致波形蓄积，或网络抖动 | ① 确认 `proxy_buffering off;`；② 确认前端与后端已启用 5–10s 周期性心跳探测包（Ping/Pong）；③ 检查客户端至服务器的 Ping 延迟与丢包率。 |
