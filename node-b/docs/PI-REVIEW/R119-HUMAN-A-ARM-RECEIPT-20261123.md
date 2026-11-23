# R119 · 志愿者甲手臂位置复测 MQTT 录制与交付回执

2026-11-23，北京时间。卡片提交 `05210d9779776f0aca816c776a37ca8c5d8936b1`，卡片 SHA-256 `7ccb3e76fc4415e665ac1d31d3d8cd9274b0ece1e8dccb31356a62128b62d6ad`。

- 首次启动事务 `r119human-20261123T112549Z` 在 SSH 关闭后本机报 `BrokenPipeError` 且退出码为 1。通过独立 SSH 核实该事务在服务器上既无暂存目录也无交付文件，随后启动新事务。
- 唯一实际录制事务 `r119human-20261123T112630Z`。A、B 遥测与状态四项只读订阅于 **19:26:32.626** 确认，上限 60 分钟。
- 现场报告采集结束且设备已断电。核对进程和输出路径，于 **19:55:25.421** 发送停止信号，录制器返回 `OPERATOR_END`，于 **19:55:25.448** 封存。录制器和 SSH 退出码均为 0。独立核查确认本次录制进程已退出。
- 完整原件 **12,221 行，6,786,377 字节**，JSON 解析错误 0。A **4,533 行**，B **7,688 行**。首末记录 **19:26:32.669–19:53:35.376**。A 遥测 **19:29:17.981–19:53:34.956**，B 遥测 **19:29:17.033–19:53:35.376**。
- 沿用 R85 录制器，源码 SHA-256 `d2b4a3d11c761e00f0804582fb8b03d80dfc7e410739fa158be2267fb3f26686`。包装器从 R116 仅替换前缀，SHA-256 `0762bd2ea0dd16933f6b947f1897239f5248811c7271492566710889ed1b6e78`。

| 服务 | 录前 | 停录前 | 停录后 |
| --- | --- | --- | --- |
| `medical-monitor-mqtt.service` | `mmpm-control status` 返回 0，active | 返回 0，active | 返回 0，active |
| `medical-monitor-h3-webbackend.service` | `mmpm-control status` 返回 0，active | 返回 0，active | 返回 0，active |

**文件交付 PASS。** 对采集服务器暂存原件、交付文件、PI VPS 落盘文件和本地 EFS 副本分别核对，字节数和 SHA-256 一致。两台服务器上的交付文件均为 0600，PI 副本位于 Git 忽略路径。

- 采集服务器 `/home/mmpm-deploy/r83-capture/r119human-20261123T112630Z-node-ab.jsonl`
- PI VPS `/home/claudedev/workspaces/mmpm-review/node-b/build/r83-capture/r119human-20261123T112630Z-node-ab.jsonl`
- SHA-256 `bebf0a6a064fbe1e470b1054835186f413f31a0ee7304108a898dae7b551cae6`

现场时标、人工计数与实验判定由负责人和 PI 记录至 R120。
