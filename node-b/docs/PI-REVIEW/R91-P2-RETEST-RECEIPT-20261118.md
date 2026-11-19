# R91 · P2 复测录制与交付回执

现场卡为 `37c2e1586f029453efb810ed5d38f14d81615172`，文件 SHA-256 `5d16de53658d935d037c1d960ce53b8a06bdef0157b338605e0ada1f61a935db`。录制及交付时间为 **2026-11-19，北京时间**。

| 项目 | 状态 | 记录 |
| --- | --- | --- |
| 录制授权 | PASS | 负责人明确要求启动 `r91human`，只读，上限 60 分钟。后续明确要求停录并交付到采集服务器与 PI VPS。 |
| 现场放行、供电和接触时间线 | UNKNOWN | 本会话只收到录制与交付指令，未收到「放行 R91 复测」原话以及电极、质量关、标记、摘除等现场时标。有遥测收包，现场动作及时间以负责人记录为准。 |
| 质量关、人工对照和 HR 判定 | UNKNOWN | 未收到电极品牌/批号、室温、重贴过程、质量关结果、人工脉搏或同期屏显，不能界定 R91 判定窗。 |
| MQTT 和交付 | PASS | 四项订阅均确认。按指令停止该次录制，录制器和 SSH 退出码均为 0。采集服务器、PI VPS 与本地 EFS 副本的大小及 SHA-256 一致。 |

- MQTT Broker 于 **15:21:44.286** 确认 A、B 的四项订阅。首末记录 **15:21:44.329–16:05:00.436**，封存完成于 **16:06:40.025**。
- A 遥测收包 **15:27:49.518–16:04:59.946**，B 遥测收包 **15:28:04.268–16:05:00.436**。收包时刻单独记录，不能代替现场上电和断电时刻。
- 共 **15,847 行**，A **5,861**，B **9,986**，JSON 解析错误 0。文件 **8,478,817 B**，SHA-256 `f6bfe1d30a92e74641886a979d869677300d9462f54c9e41e0e218f0d2cd1904`。
- 采用 R85 录制器原字节，SHA-256 `d2b4a3d11c761e00f0804582fb8b03d80dfc7e410739fa158be2267fb3f26686`。启动包装器只换 `r91human` 前缀，SHA-256 `55c84ffcd1cc4bbcc0eb5a178ef5ccdb2c0cf19b51366e71186037f076931ca9`。

| 服务 | 启动录制前 | 停录前 | 停录后 |
| --- | --- | --- | --- |
| `medical-monitor-mqtt.service` | `mmpm-control status` 返回 0，active | 返回 0，active | 返回 0，active |
| `medical-monitor-h3-webbackend.service` | `mmpm-control status` 返回 0，active | 返回 0，active | 返回 0，active |

交付位置均为受限文件，权限 0600。

- 采集服务器 `/home/mmpm-deploy/r83-capture/r91human-20261119T072140Z-node-ab.jsonl`。
- PI VPS `/home/claudedev/workspaces/mmpm-review/node-b/build/r83-capture/r91human-20261119T072140Z-node-ab.jsonl`。已验证为 Git 忽略路径，上传后独立计算 SHA-256。
- 本地受限 EFS 同时保存原件与监督日志。版本库仅提交本回执。
