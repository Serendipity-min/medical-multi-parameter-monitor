# P6-V1 旁路文字问答

固定起点 P4 `67f5f57bd82c6e326e9e78ec9540481c80105e5f`。独立 Python/FastAPI 进程，不修改 Telemetry、Hub、原 WebSocket 或遥测 Topic。暂不部署到公网。

安装独立依赖 `python -m pip install -r cloud/ai/requirements.txt`；从仓库根目录启动 `python -m uvicorn cloud.ai.app:create_app --factory --host 127.0.0.1 --port 18766 --no-access-log`。Web 本机 Vite 的 `/medical-monitor/ai/` 代理至该进程。正式 Nginx/服务安装另行授权。

凭据全部由进程外环境注入，不放命令行/仓库。`P6_AI_TOKEN` 至少 32 字符，浏览器输入独立 AI 令牌；不复用模型密钥。`P6_MODEL_MODE` 默认 `MOCK`，`P6_SNAPSHOT_MODE` 默认 `MONITOR`；后者只读现有 `/ws/v1/monitor`，需要外部 `P6_MONITOR_WS_URL`、`P6_MONITOR_VIEW_TOKEN`，可选 `P6_MONITOR_ORIGIN`。只允许加密 WSS 或 loopback WS。测试选 `MOCK` 快照时始终显式标记 synthetic，绝非真人数据。

`P6_ALLOWED_ORIGINS` 可设已授权浏览器来源。所有问题需 Bearer 鉴权；正文 4096B、问题 500 字符、并发 4、全局每分钟 12 请求、最多 128 会话/每会话 4 轮/30 分钟寿命。网关切换清空上下文。错误仅返回固定错误码。

## 模型及事实边界

现在数值类问题优先确定性读取有效事实。节点、网关、来源、session/seq、单位、时间独立检查；INVALID/STALE/OFFLINE/REPLAY 不返回当前数值。不得提交浏览器读数。模拟来源必须明确标注。

V1 的模型解释采用受限模板：豆包选择“数据质量 / 一般复测建议 / 项目架构”类别，服务端验证输出 JSON 并映射经审核的文字。任意模型自由文字不进入答案或播报。此版本是有限范围问答，不能宣称支持开放临床咨询、诊断、处方或治疗。模型不可执行设备控制。

真实服务模式 `DOUBAO` 只从服务器环境读取 `ARK_API_KEY`、`ARK_MODEL_ID`，并要求 `P6_REAL_ACCOUNT_APPROVED=1` 和 `P6_REAL_BUDGET_APPROVED=1`；每进程最多 5 次、单次 64 token、8 秒模型超时。不设置这些批准标志就不能做真实调用。本次真实调用 0 次，状态 `REAL_MODEL_BLOCKED`；HTTP 契约测试使用假响应。

接口依据：[火山方舟官方数据面/鉴权](https://docs.volcengine.com/docs/ark/base-url-and-authentication?lang=zh)。使用官方 HTTPS Chat Completions，不引入 SDK、不自动重试计费请求。

## 下行契约

固定白名单 Topic：`mpm/v1/GW-C-001/voice/reply` 与模拟设备 `mpm/v1/GW-DEV-001/voice/reply`。单独客户端与账户，QoS1、不 retain、至少 5 秒间隔、15 秒有效期。默认关闭。只允许 `P6_MQTT_MODE=ISOLATED`，外部注入 `P6_MQTT_PORT`（大于 1024）、`P6_MQTT_USERNAME`、`P6_MQTT_PASSWORD`；本轮只连接 loopback，生产 Broker 接入未授权。

应用二进制帧为网络字节序：`P6V1` 4B、issued_ms 8B、expires_ms 8B、turn_id 16B、fact_digest 16B、text_len 2B、UTF-8 文本 1–240B。最大载荷 294B；配合固定 Topic 和 QoS1 头仍小于既有 512B MQTT RX。云端返回同一 turn_id/事实摘要和短文本，摘要是来源关联标识，不是认证签名；认证依靠隔离账户/ACL及未来受授权的 TLS。

严格拒绝过期/未来超限、大小异常、非法 Unicode、控制字符与 TW-TTS `[]` 标签；按完整 UTF-8 字符边界截断。模拟接收维护顺序高水位和 8 个 turn_id；重连不重置设备侧去重。无持久存储，掉电后的去重边界留待硬件窗口。

`BROKER_PUBACK_ONLY` 只表示 Broker 收到消息，`SIMULATED_DOWNLINK` 只表示模拟 Gateway 收到；均不能表示喇叭已完成。播报开关控制下一轮是否下发；取消/关闭阻止尚未下发的回答，不能撤回已交给 Broker 的文本。

验证：`python -m pytest cloud/ai/tests -q`；`python cloud/ai/tests/run_isolated.py --runtime <已核验的本机 Mosquitto runtime>`。夹具临时端口、独立账户/ACL、不改生产配置、进程自有并清理。只做普通功能验证，不运行 Security Gate。
