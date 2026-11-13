# 本机 Mock Gateway

使用与 Backend 相同的虚拟环境。凭据从环境变量或仓库外 JSON 读取：

```json
{
  "device_url": "wss://example.invalid/medical-monitor/device/v1/ingest",
  "browser_url": "wss://example.invalid/medical-monitor/ws/v1/monitor",
  "origin": "https://example.invalid",
  "device_token": "<外部设备令牌>",
  "view_token": "<外部只读令牌>"
}
```

以上是无效占位地址；真实地址与凭据只保存在用户控制的仓库外配置。

```powershell
# 用外部配置实际位置替换路径；不要把凭据复制到命令行。
.\.venv\Scripts\python.exe cloud/tools/mock_gateway/main.py --config <外部配置路径> --control <外部控制文件路径>
```

控制文件参考 `control.example.json`，运行时每 200ms 读取：

| 字段 | 行为 |
|---|---|
| mode | LIVE 或 REPLAY；后者时间回退 60 秒 |
| quality | VALID / INVALID / STALE |
| node_a_online / node_b_online | 独立模拟节点上下线 |
| network_online | false 主动断开；true 自动重连 |
| pause | true 保持网络连接但不发数据，用于验证 5 秒超时 |

不要同时启动两个 GW-DEV-001。每个连接由后端独占。
`--duration 60` 有限运行 60 秒，默认持续运行直到 Ctrl+C。
所有数据均为合成值：ECG 250Hz、PPG/RESP 50Hz，按 200ms 分批传输。
Token 无效不会生成任何有效数据；网络恢复会重连，WSS 使用系统证书校验。
