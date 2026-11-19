# R100 · RR 真值采集 MQTT 录制与交付回执

2026-11-19，北京时间。卡片提交 `2b16955cd2b0aeb99f36b02d4b09e8f1f3a89e9e`，SHA-256 `bc91a51512e86a21947af6d39228d1aa917147322969e2943c1a58fa16bd8e30`。

- 首个 SSH 启动尝试 `r100rr-20261119T112236Z` 在订阅前中断，随后只读检查确认服务器未创建该次录制目录或交付文件。该次传输错误及凭据脱敏后的诊断保存在受限 EFS。
- 实际会话 `r100rr-20261119T112442Z` 的四项只读订阅于 **19:24:45.995** 确认，录制上限 60 分钟。首末记录 **19:24:46.038–19:43:05.460**。
- 现场回报采集结束、设备已断电。按指令停止本次录制，封存于 **19:45:25.187**。停止结果为 `OPERATOR_END`，录制器原生退出码和 SSH 退出码均为 0。
- 共 **7,654 行、4,288,930 B**，JSON 解析错误 0。A **2,805 行**，B **4,849 行**。A 遥测收包为 19:28:25.586–19:43:04.775，B 为 19:28:24.661–19:43:05.460。
- 沿用 R85 录制器，原字节 SHA-256 为 `d2b4a3d11c761e00f0804582fb8b03d80dfc7e410739fa158be2267fb3f26686`。包装器只换 `r100rr` 前缀，SHA-256 为 `7ed3f8056869761f15c56b8501da0fe0c35eaea43dd82afc85a3586ec9e524d3`。

| 服务 | 启动录制前 | 停录前 | 停录后 |
| --- | --- | --- | --- |
| `medical-monitor-mqtt.service` | `mmpm-control status` 返回 0，active | 返回 0，active | 返回 0，active |
| `medical-monitor-h3-webbackend.service` | `mmpm-control status` 返回 0，active | 返回 0，active | 返回 0，active |

**录制与交付 PASS。** 采集服务器与 PI VPS 的文件均为 0600，大小及独立计算的 SHA-256 一致。本地 EFS 副本也通过同一校验。

- 采集服务器 `/home/mmpm-deploy/r83-capture/r100rr-20261119T112442Z-node-ab.jsonl`。
- PI VPS `/home/claudedev/workspaces/mmpm-review/node-b/build/r83-capture/r100rr-20261119T112442Z-node-ab.jsonl`，目录已核对为 Git 忽略范围。
- SHA-256 `0734d690ad5cc0fa7ae46999b7b1815a5a19a131bed31f27cc54e7483f6c696e`。

各阶段时刻、人工计数及 RR 真值判定由负责人和 PI 记录。
