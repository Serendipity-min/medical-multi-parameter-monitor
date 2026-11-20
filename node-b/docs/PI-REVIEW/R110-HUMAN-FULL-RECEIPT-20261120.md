# R110 · 完整流程真人采集 MQTT 录制与交付回执

2026-11-20，北京时间。卡片提交 `ae8451fb10adba2ee51b430c91b084465eda4283`，卡片 SHA-256 `9163afcfa4aac6758c4d42942bed92e3e778df48cd729e3f0039787c718cb847`。

- MQTT 四项只读订阅于 **15:31:46.981** 确认，录制上限 60 分钟。首末记录 **15:31:47.025–15:56:34.649**。
- 现场回报采集完毕并要求停录。封存于 **15:57:27.458**，结果为 `OPERATOR_END`，录制器原生退出码和 SSH 退出码均为 0。
- 共 **11,104 行、6,166,455 B**，JSON 解析错误 0。A **3,848 行**、B **7,256 行**。A 遥测收包为 15:34:23.398–15:56:31.856，B 为 15:34:22.900–15:56:34.649。
- 沿用 R85 录制器，原字节 SHA-256 `d2b4a3d11c761e00f0804582fb8b03d80dfc7e410739fa158be2267fb3f26686`。包装器只更换 `r110human` 前缀，SHA-256 `7005edaaa4568038034971e12b6e52964405150fab9329493d583afea149df6f`。

| 服务 | 启动录制前 | 停录前 | 停录后 |
| --- | --- | --- | --- |
| `medical-monitor-mqtt.service` | `mmpm-control status` 返回 0，active | 返回 0，active | 返回 0，active |
| `medical-monitor-h3-webbackend.service` | `mmpm-control status` 返回 0，active | 返回 0，active | 返回 0，active |

**录制与交付 PASS。** 采集服务器与 PI VPS 上的文件均为 0600，大小及独立计算的 SHA-256 一致。本地加密副本也通过同一校验。

- 采集服务器 `/home/mmpm-deploy/r83-capture/r110human-20261120T073145Z-node-ab.jsonl`。
- PI VPS `/home/claudedev/workspaces/mmpm-review/node-b/build/r83-capture/r110human-20261120T073145Z-node-ab.jsonl`，已核对为 Git 忽略路径。
- SHA-256 `48e9010f5f603f1fdd115ab3c30bb1972402509ec9d67bd9adef2b53bcd834b5`。

现场时标、人工呼吸计数和真值判定由负责人报告给 PI。
