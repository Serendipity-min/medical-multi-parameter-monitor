> 归档状态：第一阶段维护参考。CANopen、离线缓存、真实节点章节为后续规划，本轮不执行；安全扫描与凭据轮换须单独明确授权。

# 多参数监护仪 P 端云网关维护手册与工作流程

> **版本**：v1.0  
> **日期**：2026-09-20  
> **适用架构**：CANopen → Gateway-C → MQTT/TLS → Mosquitto → Backend → Nginx/WebSocket → Web  
> **适用范围**：P 负责的 Gateway-C、ESP8266-C、腾讯云 MQTT Broker、Backend、Nginx、Web、部署与回滚。  
> **安全边界**：当前为科研/教学工程样机。未完成真实传感器、正式 RR、24h 全链路稳定性和医疗认证前，不得宣称临床可用。

---

# 1. 系统运行图

```text
Node-A ─┐
        ├── CANopen ── Gateway-C / STM32F407-C
Node-B ─┘                       │
                               │ MQTT Client
                               ↓
                           ESP8266-C
                               │
                           MQTT/TLS
                               ↓
                    Tencent Cloud Mosquitto
                               │
                           MQTT Subscribe
                               ↓
                            Backend
                               │
                           WebSocket
                               ↓
                             Nginx
                               │
                         HTTPS / WSS
                               ↓
                         Browser Web
```

开发期另有：

```text
Mock MQTT Publisher → GW-DEV-001
Gateway-C 合成源     → GW-C-001
```

两者身份必须隔离。

---

# 2. 服务清单

服务器当前项目服务：

| Service | 用途 |
|---|---|
| `medical-monitor-mqtt` | Mosquitto MQTT/TLS Broker |
| `medical-monitor` | FastAPI Backend |
| `medical-monitor-mock` | 服务器 MOCK Publisher |
| `medical-monitor-certificate.timer` | 检查并复制已有 TLS 证书到 Broker |
| Nginx | Web HTTPS / WebSocket / 静态入口 |

关键服务器目录：

```text
/opt/medical-monitor/
├── current -> 当前 release
├── releases/
├── backups/
├── broker/
├── mqtt-config/
└── config/
```

仓库重点目录：

```text
gateway/
cloud/
doc/P/
```

---

# 3. 每次开发前的健康检查

## 3.1 Git

```bash
git status
git branch --show-current
git pull --ff-only
```

确认：

- 当前不是直接在 `main` 上开发；
- 没有未理解的本地修改；
- 分支来源正确。

## 3.2 Server

```bash
sudo systemctl is-active medical-monitor-mqtt
sudo systemctl is-active medical-monitor
sudo systemctl is-active medical-monitor-mock
sudo systemctl is-active medical-monitor-certificate.timer

curl -s http://127.0.0.1:18765/health
sudo nginx -t
```

正常情况下：

```text
Broker active
Backend active
health.status = ok
mqtt_connected = true
nginx config valid
```

## 3.3 Browser

检查：

- Gateway 选择正常；
- Node-A / Node-B 状态正常；
- MOCK/LIVE/REPLAY 标签正确；
- ECG/PPG/RESP 波形是否存在；
- HR/RR/SpO2/PR/NIBP/TEMP 是否更新；
- 无数据时是否正确 STALE/OFFLINE；
- 不允许保留陈旧值并伪装为实时值。

---

# 4. 推荐 Git 工作流程

## 4.1 分支层次

稳定：

```text
main
```

推荐增加：

```text
integration/v0.7
```

功能分支：

```text
dev/p-gateway-cloud-v07
dev/p-canopen-v07
dev/node-a
dev/node-b
```

## 4.2 工作流

```text
合同 / Issue
    ↓
dev branch
    ↓
本地测试
    ↓
Pull Request
    ↓
CI
    ↓
Review
    ↓
integration/v0.7
    ↓
系统联调
    ↓
main
    ↓
Release
```

禁止：

- 直接在 main 做大改；
- 强推覆盖已审历史；
- 将真实 Secret 提交；
- 用口头“测试过”替代证据。

---

# 5. Pull Request 门禁

每个 PR 至少确认：

```text
[ ] 合同/Issue 范围明确
[ ] 无真实密钥
[ ] 文档不与最终总合同冲突
[ ] Python tests 通过
[ ] Web build 通过
[ ] 第三方依赖来源明确
[ ] 部署可回滚
[ ] 关键证据已脱敏
[ ] 已知限制已记录
[ ] Reviewer 完成
```

推荐 CI：

```text
backend:
  pytest

web:
  npm ci
  npm run build

security:
  secret scan

vendor:
  Paho upstream SHA check

gateway:
  compile（有 ARM 工具链 runner 时）
```

硬件测试继续人工执行并保存 JSON / 截图 / 白名单日志。

---

# 6. 发布与回滚

## 6.1 发布前

必须完成：

1. 本地测试；
2. Web build；
3. Python 依赖锁定；
4. Bundle SHA-256；
5. 当前服务器配置备份；
6. 唯一 release 编号；
7. 回滚路径确认。

## 6.2 发布顺序

```text
上传 bundle
   ↓
校验 SHA-256
   ↓
创建新 release
   ↓
安装离线依赖
   ↓
启动/检查 MQTT
   ↓
原子切换 current
   ↓
restart Backend
   ↓
health check
   ↓
nginx -t
   ↓
reload Nginx
   ↓
功能验收
```

旧 release 不覆盖。

## 6.3 回滚

任何关键步骤失败：

```text
停止新增辅助服务
   ↓
current 切回 previous
   ↓
恢复 backend.env
   ↓
restart Backend
   ↓
必要时停止新 Broker
   ↓
health check
```

失败 release 保留用于排错，不立刻递归删除。

---

# 7. Mosquitto 维护

## 7.1 基线

正式设备入口：

```text
8883 / MQTT over TLS
allow_anonymous false
```

账号职责：

```text
mock-publisher → 只能写 GW-DEV-001
gateway-c      → 只能写 GW-C-001
backend-reader → 只读授权 Gateway
```

## 7.2 ACL

最小权限：

- Gateway 不可跨 Gateway 写；
- Gateway 不可 subscribe；
- Backend 不可 publish；
- Mock 不可访问 GW-C-001。

新增 Gateway 时：

1. 创建独立用户名；
2. 创建独立 Client ID；
3. 添加 ACL；
4. 先用测试凭据验证；
5. 再交付设备配置。

## 7.3 日志

已按首轮复核启用 error/warning/notice，经白名单日志代理转换后写入 journald 与独立轮转文件。

- Broker：`/opt/medical-monitor/logs/broker/broker.jsonl`；Backend：`/opt/medical-monitor/logs/backend/backend.jsonl`。
- 每个来源 5MiB ×（当前 + 7 份备份），不保证固定天数；保留 UTC 时间、错误类别、数字错误码与计数。
- 原始文本、地址、口令和 Payload 不落盘。真实运行日志不整体提交 Git。
- 详细保留策略、诊断方法、QoS1 与认证边界见 [运行日志与排障](运行日志与排障.md)。

---

# 8. Backend 维护

## 8.1 Health

```bash
curl -s http://127.0.0.1:18765/health
```

重点字段：

```text
status
mqtt_connected
accepted
rejected
dropped
```

解释：

- `mqtt_connected=false`：Broker/网络/凭据；
- `rejected` 持续增长：Topic/Payload/数据模型不匹配；
- `dropped` 增长：Backend 消费速度或异常发布频率问题。

## 8.2 Restart

```bash
sudo systemctl restart medical-monitor
```

重启后：

1. service active；
2. health 恢复；
3. MQTT 重订阅；
4. retained 状态恢复；
5. Browser 自动重连。

当前 Backend 单 worker、内存状态、clean_session=True。后端停机期间不积存该会话的 QoS1 消息，重启不保留完整历史；retained 不等于历史存储。

---

# 9. Nginx 维护

每次修改：

```bash
sudo nginx -t
sudo systemctl reload nginx
```

禁止：

- 未验证直接 restart；
- 覆盖全局 `nginx.conf`；
- 修改其他项目 server block；
- 将 Backend 端口暴露公网。

当前 Nginx 只负责：

- Web；
- REST；
- Browser WebSocket。

MQTT 8883 直接由 Broker 提供 TLS listener。

---

# 10. TLS 证书维护

## 10.1 服务器证书

检查：

```bash
openssl x509 -in <certificate> -noout -dates -issuer -subject
```

Broker 证书刷新后：

```bash
sudo systemctl status medical-monitor-mqtt
```

然后执行 MQTT TLS 验收。

## 10.2 ESP8266 CA

ESP `client_ca` 与服务器证书更新是两个独立对象。

每次服务器证书链变化前检查：

```text
新证书链根 CA
   ↓
ESP client_ca 是否仍信任
```

若根 CA 变化：

1. 备份 ESP 原 CA；
2. 测试模块写新 CA；
3. 回读 verify；
4. 正确 SNI/CCN 正向测试；
5. 错误 CA/错误名称负向测试；
6. 再升级正式 Gateway。

禁止关闭证书校验来规避证书问题。

---

# 11. MQTT 凭据轮换

轮换采用“双凭据过渡”：

```text
创建新凭据
   ↓
更新 Broker/ACL
   ↓
独立验证新凭据
   ↓
更新 Gateway 配置
   ↓
观察重连
   ↓
撤销旧凭据
```

不要先删除旧凭据。

凭据：

- 不进 Git；
- 不进截图；
- 不进普通日志；
- 不长期保存在聊天记录。

---

# 12. Gateway-C 固件维护

## 12.1 烧录前

必须：

- 确认板型；
- 备份完整 Flash；
- 双读一致；
- 计算 SHA-256；
- 存仓库外。

## 12.2 Build

当前：

```bash
python gateway/mqtt/build.py
```

检查：

- 项目代码无 warning；
- text/data/bss 无异常暴涨；
- Paho 上游版本/补丁无意外变化。

## 12.3 Provision

配置从仓库外 JSON 生成。

禁止：

- Wi-Fi/MQTT 密码写进源码；
- 配置 bin 提交仓库；
- 未备份直接覆盖未知 sector。

## 12.4 烧录后检查

```text
Wi-Fi
DNS
SNTP/time
CA verify
CCN/SNI
TLS
MQTT CONNECT
PUBLISH
Keepalive
Reconnect
```

---

# 13. ESP8266 维护

正常不刷 AT 固件。

需要修改时记录：

- AT Version；
- Bin Version；
- Flash Partition；
- CA Partition；
- 原镜像/CA 备份。

项目依赖：

```text
Wi-Fi
TCP
TLS Socket
AT interface
```

不依赖 ESP MQTT AT。

---

# 14. MOCK / LIVE / REPLAY

开发 Mock：

```text
GW-DEV-001
source=MOCK
synthetic=true
```

Gateway-C 合成验证：

```text
GW-C-001
source=MOCK
synthetic=true
```

真实节点：

```text
source=LIVE
synthetic=false
```

禁止：

- Synthetic 标 LIVE；
- MOCK 与真实人体数据无标签混用；
- REPLAY 覆盖实时读数；
- REPLAY 触发实时报警。

---

# 15. 故障排查

## 15.1 Web 显示 Gateway Offline

从上到下：

```text
Browser
 ↓
Backend
 ↓
Broker
 ↓
Gateway MQTT
 ↓
ESP Wi-Fi/TLS
```

检查：

```bash
curl -s http://127.0.0.1:18765/health
sudo systemctl status medical-monitor
sudo systemctl status medical-monitor-mqtt
sudo ss -ltnp | grep 8883
```

Broker/Backend 正常时查 Gateway 白名单串口状态。

## 15.2 MQTT TLS 失败

依次检查：

1. 系统时间；
2. DNS；
3. CA；
4. SNI；
5. CCN；
6. 8883；
7. Broker 证书；
8. Firewall / Security Group。

禁止改用明文 1883 作为“临时修复”。

## 15.3 Browser WebSocket 失败

检查：

```text
Nginx
→ Backend
→ Origin
→ View Token
```

命令：

```bash
sudo nginx -t
sudo systemctl status medical-monitor
```

## 15.4 单路 Stale

Gateway 在线但单 Stream Stale：

- 查对应 Node；
- 查 seq；
- 查 timestamp；
- 查是否继续 publish；
- 查数据字典单位/Stream。

不要通过单纯延长 timeout 隐藏采集故障。

## 15.5 dropped 增长

处理顺序：

1. 发布频率；
2. Payload 大小；
3. Backend CPU；
4. Broker 状态；
5. 再评估有界队列。

禁止直接改成无限队列。

---

# 16. 数据字典维护

新增参数必须先进入数据字典：

```text
参数需求
  ↓
来源/单位/状态
  ↓
CANopen Object Dictionary
  ↓
Gateway Canonical Data Model
  ↓
MQTT Topic/Payload
  ↓
Backend
  ↓
Web
```

不能在前端临时新造字段而上下游不知道。

---

# 17. CANopen 维护流程

对象字典冻结后：

- Index/Sub-index 变更视为接口变更；
- PDO Mapping 变更必须同步 A/B/P；
- Heartbeat 时间统一；
- EMCY Code 建立项目字典；
- Node ID 固定并文档化。

不兼容变更：

1. 新版本；
2. 更新 OD；
3. 更新 Gateway；
4. 更新测试；
5. 再联调 A/B。

---

# 18. 离线缓存维护

目标：

```text
网络正常 → LIVE

网络断开 → Buffer

网络恢复 → LIVE 优先
             +
           REPLAY 低优先补传
```

必须检查：

- 写入失败；
- 容量满；
- 擦写寿命；
- 掉电恢复；
- 重复补传；
- seq/time；
- REPLAY 不进实时告警。

---

# 19. 备份策略

## Git

- main；
- integration；
- release tag。

## Server

- current；
- releases；
- backups；
- backend env；
- mqtt-config；
- Broker ACL/password；
- Nginx 项目 snippet；
- systemd units；
- certificate source mapping。

## Hardware

- STM32 原始完整 Flash；
- ESP AT/分区信息；
- ESP 原 CA；
- Gateway 配置版本。

敏感备份全部仓库外保存。

---

# 20. 第三方依赖升级

依赖升级不能混入业务功能 PR。

流程：

```text
dependency branch
   ↓
Release Notes / CVE
   ↓
License
   ↓
Lockfile
   ↓
Unit Test
   ↓
Gateway Hardware Test
   ↓
PR
```

Paho 还需同步：

- upstream commit；
- SHA；
- PATCHES；
- license。

---

# 21. 真实人体数据前额外门禁

在开始上传可关联的真实人体数据前：

```text
[ ] 不使用共享测试 Token
[ ] 访问范围明确
[ ] 数据保留周期明确
[ ] MOCK/LIVE 分离
[ ] 备份权限明确
[ ] 普通日志不记录 Payload
[ ] 公网危险控制关闭
[ ] 测试流程经项目负责人确认
```

Web 页面不得作为临床诊断依据。

---

# 22. 周期维护计划

| 周期 | 内容 |
|---|---|
| 每次开发 | Git、服务、health、Nginx |
| 每周 | Broker/Backend 错误、磁盘、release/backups |
| 每月 | 证书剩余期、依赖安全、凭据清单、备份恢复 |
| 每次发布 | 回归 + 回滚验证 |
| 协议变更 | 数据字典 + OD + MQTT + Web 一致性 |
| 最终联调 | 24h + 故障注入 |

---

# 23. 项目标准工作流程

```text
需求 / 合同
    ↓
接口定义
    ↓
开发分支
    ↓
实现
    ↓
本地自动测试
    ↓
硬件 / Server 专项测试
    ↓
证据归档
    ↓
PR
    ↓
CI
    ↓
Review
    ↓
Integration
    ↓
系统联调
    ↓
Main / Release
    ↓
部署
    ↓
部署后验收
    ↓
运行维护
```

任何步骤都必须可回退，禁止只有“前进”没有“回滚”。

---

# 24. 当前维护优先级

第一阶段本轮整改（实现与 CI 结果见阶段验收目录）：

1. 修正 G0 的 HKS/MMP 旧描述；
2. `upgrade_mqtt.py` 将安全 `assert` 改为显式检查；
3. 增加 Broker error/warning 日志；
4. 增加最小 CI。

第二阶段参考（用户明确尚不执行）：

5. CANopen 第二阶段；
6. 数据字典；
7. Gateway 离线缓存；
8. 真实 A/B 接入。

最终：

9. RR 正式算法；
10. 真实四模块；
11. 24h；
12. 最终样机评审。
