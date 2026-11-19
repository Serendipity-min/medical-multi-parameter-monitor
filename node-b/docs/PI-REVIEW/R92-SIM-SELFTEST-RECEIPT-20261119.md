# R92 · 模拟器自检 MQTT 录制与交付回执

2026-11-19，北京时间。卡片提交 `b16fa866cc01af8790a4e81ac8175e445040c9a9`，SHA-256 `f443b77879ee92106fde20600ab67b304e128a027621bd77148b78aa19985021`。

- PI 的 WSS 从 16:25:03 开始。MQTT 四项只读订阅于 **16:26:54.919** 确认，录制上限 30 分钟。首末记录 **16:26:54.963–16:43:31.571**。
- 现场报告自检结束、设备已断电。按指令停止本次录制，封存于 **16:44:15.570**。停止结果为 `OPERATOR_END`，录制器原生退出码和 SSH 退出码均为 0。
- 共 **4,511 行、2,891,655 B**，JSON 解析错误 0。A **161 行**（状态消息），B **4,350 行**。B 遥测收包时间为 16:30:13.863–16:43:31.571。
- 未修改 R85 录制器。其原字节 SHA-256 为 `d2b4a3d11c761e00f0804582fb8b03d80dfc7e410739fa158be2267fb3f26686`。包装器只换 `r92sim` 前缀，SHA-256 为 `b86ec5983392c0f9c1b6c18553ad9f6acff51020ee2bb1fb35a7e352c2100a07`。

| 服务 | 启动录制前 | 停录前 | 停录后 |
| --- | --- | --- | --- |
| `medical-monitor-mqtt.service` | `mmpm-control status` 返回 0，active | 返回 0，active | 返回 0，active |
| `medical-monitor-h3-webbackend.service` | `mmpm-control status` 返回 0，active | 返回 0，active | 返回 0，active |

**录制与交付 PASS。** 采集服务器与 PI VPS 的文件均为 0600，大小及独立计算的 SHA-256 一致。本地 EFS 副本也通过同一校验。

- 采集服务器 `/home/mmpm-deploy/r83-capture/r92sim-20261119T082651Z-node-ab.jsonl`。
- PI VPS `/home/claudedev/workspaces/mmpm-review/node-b/build/r83-capture/r92sim-20261119T082651Z-node-ab.jsonl`，目录已核对为 Git 忽略范围。
- SHA-256 `3b3ec69a535296dd0e720ab5cbfad780c641ce926d911d0ada64b389ffd0b524`。

各项自检时刻和判定由 PI 写入 R93。
