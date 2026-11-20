# R108 · 正确色标复测 MQTT 录制与交付回执

2026-11-20，北京时间。卡片提交 `e0ab04e189b43af4426d3024c8332407882b416b`，卡片 SHA-256 `3ab7157c37fccc2c331cbb6ebc84dbd3d736b6233a6124d1696e0dc903e1e603`。

- MQTT 四项只读订阅于 **14:15:17.591** 确认。依现场指令，PI 随后开启 WSS，开始秒数未回报。录制上限 60 分钟，首末记录 **14:15:17.635–15:06:00.824**。
- 现场确认采集结束、设备已断电。按指令停止本次录制，封存于 **15:07:01.407**。结果为 `OPERATOR_END`，录制器原生退出码和 SSH 退出码均为 0。
- 共 **21,714 行、12,431,841 B**，JSON 解析错误 0。A **6,071 行**、B **15,643 行**。A 遥测收包为 14:18:58.780–15:06:00.824，B 为 14:18:58.777–15:06:00.821。
- 沿用 R85 录制器，原字节 SHA-256 `d2b4a3d11c761e00f0804582fb8b03d80dfc7e410739fa158be2267fb3f26686`。包装器只更换 `r108human` 前缀，SHA-256 `6c184b3a5888882600ff1ff5d4b2619b3880c04c38d02e9155531bae00a1ad44`。

| 服务 | 启动录制前 | 停录前 | 停录后 |
| --- | --- | --- | --- |
| `medical-monitor-mqtt.service` | `mmpm-control status` 返回 0，active | 返回 0，active | 返回 0，active |
| `medical-monitor-h3-webbackend.service` | `mmpm-control status` 返回 0，active | 返回 0，active | 返回 0，active |

**录制与交付 PASS。** 采集服务器与 PI VPS 上的文件均为 0600，大小及独立计算的 SHA-256 一致。本地加密副本也通过同一校验。

- 采集服务器 `/home/mmpm-deploy/r83-capture/r108human-20261120T061515Z-node-ab.jsonl`。
- PI VPS `/home/claudedev/workspaces/mmpm-review/node-b/build/r83-capture/r108human-20261120T061515Z-node-ab.jsonl`，已核对为 Git 忽略路径。
- SHA-256 `cf7b00ce0c41514a25d5d1f69862f91bd6423acefc851ee88a2f6bdf8a78aa94`。

现场分段时标、人工呼吸计数和判定由负责人报告给 PI。
