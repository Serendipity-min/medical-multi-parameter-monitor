# P 第一阶段：MQTT/TLS 云端与监护大屏

执行 [P 合同 v0.2](../doc/P/01_第一阶段_MQTT云端/合同/P_第一阶段_GatewayC云端Web执行方案合同_v0.2.md)，分支 `dev/p-gateway-cloud-v07`。

```text
STM32 Paho MQTT 3.1.1 → ESP8266 AT SSL Socket → Mosquitto TLS:8883
                                                    ↓ 只读订阅
服务器合成源 → 独立 Gateway Topic                 FastAPI → WSS → Web
```

Web 位于已有主域名 `/medical-monitor/`。设备不再使用 WSS 上传；WSS 仅用于浏览器。
`GW-DEV-001` 是服务器 Mock，`GW-C-001` 是 STM32 真机合成源，两者均明确标记 MOCK。
四模块展示 ECG、呼吸、血氧、血压，另有 TEMP。RR 趋势来自收到的 RR 数值，RESP 是独立呼吸波形。

## 本机开发

Python 3.11+、Node 22.12+。安装 `cloud/backend/requirements.lock`。
准备仓库外 MQTT JSON：`host, port, username, password, client_id`；可选 `ca_file`。
环境变量：`MONITOR_MQTT_CONFIG` 指向该 JSON，`MONITOR_VIEW_TOKEN` 为至少 32 字符随机只读令牌，
`MONITOR_ALLOWED_ORIGINS=http://127.0.0.1:5173`，`MONITOR_GATEWAY_IDS=GW-DEV-001,GW-C-001`。
真实主机和凭据不得写入示例或 Git。

```text
python -m uvicorn app.main:app --app-dir cloud/backend --host 127.0.0.1 --port 18765 --no-access-log
```

另开终端在 `cloud/web` 执行 `npm ci --no-audit --no-fund`、`npm run dev`。
访问本机 `/medical-monitor/` 输入只读 Token。刷新需重新输入；同一页面断网自动重连。
WebSocket 首帧包含 token、gateway_id，Token 不进入 URL。
合成源：`python cloud/tools/mock_mqtt/main.py --config <外部mock.json> --control <外部控制.json>`。
Mock 配置另含 `gateway_id: GW-DEV-001`。控制文件支持 `mode: MOCK/REPLAY`、`validity: VALID/INVALID/STALE`、
`pause`、`network_online`、`node_a_online`、`node_b_online`；控制入口仅为本机文件。

## 验证与交付

安装 `requirements-dev.txt` 后运行 `python -m pytest cloud/backend/tests -q`；在 `cloud/web` 运行 `npm run build`。

- [部署与回滚](deploy/README.md)
- [当前接口](../doc/P/01_第一阶段_MQTT云端/设计与接口/P_MQTT接口语义_v0.7.md)
- [执行与验收报告](../doc/P/01_第一阶段_MQTT云端/验收/P_MQTT真机云端执行报告_2026-09-20.md)
- [Gateway 构建与恢复](../gateway/mqtt/README.md)
- `tools/mqtt_acceptance.py`：Broker 连接、ACL、QoS1、Retain、LWT 功能验证。
- `tools/browser_acceptance.py`：agent-browser 交互、故障及恢复验证。
- `evidence/mqtt-v07/`：脱敏结果与截图。

Backend 单 worker、内存状态，无长期存储；REPLAY 为独立到达记录，不是历史播放器。
真实传感器、正式 RR 算法、CANopen OD/PDO 和 Flash 离线缓存留待后续阶段。
`tools/mock_gateway`、`tools/acceptance.py`、旧 `deploy/install.py` 为 WSS 历史实现，不用于本次运行。
