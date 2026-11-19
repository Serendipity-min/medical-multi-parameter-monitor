# R94 · P2 第二次复测 MQTT 录制与交付回执

2026-11-19，北京时间。卡片提交 `cf63b1f7de701f4bec8373c90d1cd90d3d1d2799`，SHA-256 `6c789aa0667bb52d38642a1f7647f0c9ca057f4d2e829f0f48a4338a6bcaeca8`。

- 现场回报 PI WSS 已开。MQTT 四项只读订阅于 **17:04:33.007** 确认，录制上限 60 分钟。首末记录 **17:04:33.051–17:28:18.703**。
- 现场回报复测结束、设备已断电。按指令停止本次录制，封存于 **17:29:13.749**。停止结果为 `OPERATOR_END`，录制器原生退出码和 SSH 退出码均为 0。
- 共 **9,952 行、5,444,837 B**，JSON 解析错误 0。A **3,931 行**，B **6,021 行**。A 遥测收包为 17:06:44.006–17:28:18.703，B 为 17:06:51.131–17:28:18.700。
- 沿用 R85 录制器，原字节 SHA-256 为 `d2b4a3d11c761e00f0804582fb8b03d80dfc7e410739fa158be2267fb3f26686`。包装器只换 `r94human` 前缀，SHA-256 为 `7098da9fae5c1444a5b75b6aab3d689d5d6b3d31c4c088ac262edf48bfc3f51b`。

| 服务 | 启动录制前 | 停录前 | 停录后 |
| --- | --- | --- | --- |
| `medical-monitor-mqtt.service` | `mmpm-control status` 返回 0，active | 返回 0，active | 返回 0，active |
| `medical-monitor-h3-webbackend.service` | `mmpm-control status` 返回 0，active | 返回 0，active | 返回 0，active |

**录制与交付 PASS。** 采集服务器与 PI VPS 的文件均为 0600，大小及独立计算的 SHA-256 一致。本地 EFS 副本也通过同一校验。

- 采集服务器 `/home/mmpm-deploy/r83-capture/r94human-20261119T090428Z-node-ab.jsonl`。
- PI VPS `/home/claudedev/workspaces/mmpm-review/node-b/build/r83-capture/r94human-20261119T090428Z-node-ab.jsonl`，目录已核对为 Git 忽略范围。
- SHA-256 `eee4fa8fc5161f5c1d6fe81de94cb1ed2237808a0fed7b4fafdddb8634bdd2fd`。
- 17:13:21.040 在录制持续运行时提交的实时副本为 2,871 行、1,564,280 B，SHA-256 `475ab2c5610d989d31658f37962374f262d405bdfae012004974bef673f13539`。封存后核对该副本与完整原件同长度的文件前段逐字节一致。

现场时刻、质量关和判定由负责人向 PI 报告。
