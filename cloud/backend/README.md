# Backend

从仓库根目录按 [cloud README](../README.md) 启动。
`requirements.lock` 固定测试过的运行依赖，`requirements-dev.txt` 追加测试依赖。

环境变量：

| 名称 | 用途 |
|---|---|
| MONITOR_DEVICE_TOKEN | 设备接入凭据，至少 32 字符 |
| MONITOR_VIEW_TOKEN | 浏览器只读凭据，至少 32 字符且与设备 Token 不同 |
| MONITOR_ALLOWED_ORIGINS | 浏览器允许的 Origin，逗号分隔，无尾部斜杠 |
| MONITOR_GATEWAY_ID | 默认 GW-DEV-001 |
| MONITOR_WEB_DIR | 可选，构建后静态文件的绝对目录 |

公网入口通过 Nginx `/medical-monitor/` 前缀代理。Backend 原生路由为：
`/health`、`/api/health`、`/device/v1/ingest`、`/ws/v1/monitor`。

两个 WebSocket 均在首帧接收 `{"token":"<由外部环境提供>"}`。
设备通过后收到 `{"type":"ready"}`，每帧返回 `ack/accepted`。
浏览器认证后自动订阅 GW-DEV-001，不需要额外 SUBSCRIBE 请求。
浏览器必须发送允许的 Origin；原生 Mock 可以不发送 Origin。

生产必须限制为单 worker，并使用 `--ws-max-size 65536 --ws-max-queue 8`。
日志只包含连接/断开/拒绝等事件，不输出 Token 或原始载荷。
