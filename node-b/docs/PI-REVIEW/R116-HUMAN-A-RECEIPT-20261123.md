# R116 · 志愿者甲 MQTT 录制与交付回执

2026-11-23，北京时间。卡片提交 `11116aa522048ff53533dbdabadd9c1261666f5a`，卡片 SHA-256 `7c65385081e38b171194b5e653264b7cabe8ea0aa78011bed7547b43a20b1ed6`。

- 录制事务 `r116human-20261123T085733Z`。A、B 遥测和状态四项只读订阅于 **16:57:35.528** 确认，上限 60 分钟。
- 现场报告采集结束。核对录制进程身份后于 **17:37:14.228** 发送停止信号，录制器返回 `OPERATOR_END`，于 **17:37:14.261** 封存。录制器、SSH 退出码均为 0，另行核查确认录制进程已退出。
- 完整原件 **17,914 行，9,850,883 字节**，JSON 解析错误 0。A **6,172 行**，B **11,742 行**。首末记录 **16:57:35.572–17:36:10.476**。A 遥测 **17:00:23.323–17:36:10.476**，B 遥测 **17:00:23.325–17:36:10.274**。
- 沿用 R85 录制器，源码 SHA-256 `d2b4a3d11c761e00f0804582fb8b03d80dfc7e410739fa158be2267fb3f26686`。包装器只替换录制前缀，SHA-256 `fc5e69705e89b53968058fb20fabb319658fd67d5ca11aac53b90dad36803677`。

| 服务 | 录前 | 停录前 | 停录后 |
| --- | --- | --- | --- |
| `medical-monitor-mqtt.service` | `mmpm-control status` 返回 0，active | 返回 0，active | 返回 0，active |
| `medical-monitor-h3-webbackend.service` | `mmpm-control status` 返回 0，active | 返回 0，active | 返回 0，active |

**文件交付 PASS。** 对采集服务器暂存原件、交付文件、PI VPS 落盘文件和本地 EFS 副本分别核对，字节数和 SHA-256 一致。两台服务器上的交付文件均为 0600，PI 副本位于 Git 忽略路径。

- 采集服务器 `/home/mmpm-deploy/r83-capture/r116human-20261123T085733Z-node-ab.jsonl`
- PI VPS `/home/claudedev/workspaces/mmpm-review/node-b/build/r83-capture/r116human-20261123T085733Z-node-ab.jsonl`
- SHA-256 `8adc057ce748a386e13a7d905f0a1d48f9e5837aed36d586fdf8609e2000732c`

现场时标、人工计数与实验判定由负责人和 PI 记录至 R117。
