# R106 · 导联换色模拟器 MQTT 录制与交付回执

2026-11-20，北京时间。卡片提交 `e1171157b03c6ddfdd4a13eddb533e16d015e4f9`，卡片 SHA-256 `ce4c8048d448fd05805c28ef65b59857f7dcc61b3bddf974ca5e9ef59f9207ce`。

- PI 的 WSS 开始于 11:26:11。MQTT 四项只读订阅于 **11:26:43.310** 确认，录制上限 30 分钟。首末记录 **11:26:43.354–11:42:14.654**。
- 现场确认 **11:42:10** 全部断电。录制结果为 `OPERATOR_END`，封存于 **11:42:29.867**，录制器和 SSH 退出码均为 0。
- 共 **4,093 行、2,608,640 B**，JSON 解析错误 0。A **145 行**（状态），B **3,948 行**。B 遥测收包时间为 11:30:15.569–11:42:14.654。
- 沿用 R85 录制器，原字节 SHA-256 `d2b4a3d11c761e00f0804582fb8b03d80dfc7e410739fa158be2267fb3f26686`。包装器仅换为 `r106sim` 前缀，SHA-256 `2c64593334712ca0b0c4ac046a2f2f8b37c309459db20562eee47a886ee64187`。

| 服务 | 启动录制前 | 停录前 | 停录后 |
| --- | --- | --- | --- |
| `medical-monitor-mqtt.service` | `mmpm-control status` 返回 0，active | 返回 0，active | 返回 0，active |
| `medical-monitor-h3-webbackend.service` | `mmpm-control status` 返回 0，active | 返回 0，active | 返回 0，active |

**录制与交付 PASS。** 采集服务器与 PI VPS 上的文件均为 0600，大小及独立计算的 SHA-256 一致。本地加密副本同样通过校验。

- 采集服务器 `/home/mmpm-deploy/r83-capture/r106sim-20261120T032641Z-node-ab.jsonl`。
- PI VPS `/home/claudedev/workspaces/mmpm-review/node-b/build/r83-capture/r106sim-20261120T032641Z-node-ab.jsonl`，已核对为 Git 忽略路径。
- SHA-256 `5e5d2009de848dc75bf0aad858df25e01f23effcd0345f793dbb64962f761adc`。

现场各段时标和屏显由负责人报告给 PI，色标判定由 PI 按 R106 §4.4 写入 R107。
