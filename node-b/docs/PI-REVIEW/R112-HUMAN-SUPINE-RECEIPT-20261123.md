# R112 · 平躺对照 MQTT 录制与交付回执

2026-11-23，北京时间。卡片提交 `440878be5d6f57dfa4d51dbc4fd07f4564eed18f`，卡片 SHA-256 `950d05d8949bb2539e3722d972094a4a81dc42168c286971cea767bf0f289a26`。

- MQTT 四项只读订阅于 **09:58:27.661** 确认，上限 60 分钟。首末记录为 **09:58:27.704–10:26:30.271**。
- 现场报告采集结束、设备已断电。发出受控停止信号后，SSH 未返回录制器尾部回执，本机 SSH 退出值为 `4294967295`，录制器原生退出码 **UNKNOWN**。独立核查确认本次录制进程已退出，服务器交付文件的修改时刻为 **10:27:22.137**，暂存和交付文件大小及 SHA-256 一致。
- 共 **13,174 行、7,316,188 B**，JSON 解析错误 0。A **4,567 行**，B **8,607 行**。A 遥测收包为 10:00:36.468–10:26:29.741，B 为 10:00:35.985–10:26:30.271。
- 沿用 R85 录制器，原字节 SHA-256 `d2b4a3d11c761e00f0804582fb8b03d80dfc7e410739fa158be2267fb3f26686`。包装器只更换 `r112human` 前缀，SHA-256 `b2319b4ed44fdc23b28c4cffa974af0ae70bc67ecfe3b55503bd2d4f784b3780`。

| 服务 | 启动录制前 | 停录前 | 停录后 |
| --- | --- | --- | --- |
| `medical-monitor-mqtt.service` | `mmpm-control status` 返回 0，active | 返回 0，active | 返回 0，active |
| `medical-monitor-h3-webbackend.service` | `mmpm-control status` 返回 0，active | 返回 0，active | 返回 0，active |

**文件交付 PASS。** 采集服务器和 PI VPS 文件权限均为 0600，独立计算的大小和 SHA-256 一致。本地受限 EFS 副本也通过同一核对。

- 采集服务器 `/home/mmpm-deploy/r83-capture/r112human-20261123T015825Z-node-ab.jsonl`。
- PI VPS `/home/claudedev/workspaces/mmpm-review/node-b/build/r83-capture/r112human-20261123T015825Z-node-ab.jsonl`。已核对为 Git 忽略路径。
- SHA-256 `7b00db1bc60e9040f03971a3fb4748a8605def0e97cb6dad353fab0a20c22bb6`。

现场时标、人工计数与实验判定由负责人和 PI 记录。
