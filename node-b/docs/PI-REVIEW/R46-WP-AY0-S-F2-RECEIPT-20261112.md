# R46 · WP-AY0 S 与 F2 交付回执

**2026-11-12 · S 已完成，F2 合成回归通过。** F2 源码 `d04abacd5bf98e4ac4c00b95dfd2cd11fa6f1fbd`。正式固件仍为 R46 复核的 code `125c4b61a48a72dc2348aacb868ce31f8b5bd79cc3c26286b2508fac317c85d2`。B 实板窗口为 `NOT_RUN`。 [R46 §4、§5](https://github.com/Serendipity-min/medical-multi-parameter-monitor/blob/62128c9/node-b/docs/PI-REVIEW/R46-20261112.md) · [F 制品与回执](R45-WP-AY0-F-OFFLINE-20261112.md)

## S 正式云切换

| 项目 | 执行与核验 |
| --- | --- |
| 备份 | `/opt/medical-monitor/backups/wp-ay0-s-79143ba`，仅管理员可读。包含原运行时归档、原后端环境、MQTT 配置和 Broker passwd/ACL/conf、相关 systemd 单元及初始状态。已核验的后端源码包也归档于此。 |
| 后端 | 部署 `79143ba:cloud/backend` 到独立 release `wp-ay0-s-79143ba`，重用已验证的 H3 Python 环境。源码包 17,736 B，SHA-256 为 `6ba7a78bf8d8d692efc7e7479c72e1ef318a9543bf1a2d60ca8a7254776bec3b`。设置 `MPM_NODE_PROFILE=five`、`MONITOR_GATEWAY_IDS=GW-C-001`。 |
| MQTT | H3 旧订阅角色只覆盖历史 A/B 范围，本次改用已有 `backend-reader` 和独立 client ID `wp-ay0-backend-reader`。TLS `mosquitto_sub` 订阅 `mpm/v1/GW-C-001/#` 收到成功 SUBACK。为 `gateway-c` 设新口令并验证 TLS CONNACK。发布权限仍是 `mpm/v1/GW-C-001/#`，探测只连接和断开。 |
| 账号与旧模拟 | 从生产 passwd/ACL 删除 `b5-gateway` 和 `mock-publisher`，去除 `GW-DEV-001` 主题授权。Broker 子进程接收 SIGHUP 并保持原 PID，其他账号规则保留。 |
| 查看令牌 | 新令牌的实际浏览器鉴权通过。原令牌在运行后端的 WSS 鉴权收到关闭码 1008。新令牌和新网关口令经负责人本机受限文件分别交接。 |
| 页面 | 正式入口由 Chrome 通过 HTTPS 加载。新令牌经 WSS 收到 `node_profile=five`、`GW-C-001`、A/B/D/E 四节点和网关 `OFFLINE`，界面显示“等待设备上电”。正式硬件遥测实收为 `NOT_RUN`。 |

| systemd 单元 | 状态 | 启动设置 |
| --- | --- | --- |
| `medical-monitor-h3-webbackend.service` | active，健康端点返回 `ok`、`mqtt_connected=true` | enabled |
| `medical-monitor-h3-webai.service` | active，进程保持原 PID | enabled |
| `medical-monitor-mqtt.service` | active | enabled |
| `medical-monitor.service` | inactive | disabled |
| `medical-monitor-mock.service` | inactive | disabled |

管理员回滚入口为 `/opt/medical-monitor/backups/wp-ay0-s-79143ba/rollback.py`。该脚本恢复旧 H3 后端工作目录、Broker 配置及原服务启用状态，后端继续使用轮换后的查看令牌。回滚脚本完成语法验证，实网回滚为 `NOT_RUN`。网页静态发布命令 `mmpm-control publish-production --rollback` 对应 Web 制品回退。

## F2 正式 sector3 写入器

- `b5_sector3_write.py` 及监督器新增 `--formal-cloud`。正式授权 scope 为 `WP_AY0_FORMAL_SECTOR3_PROVISION`，绑定正式批次卡、工具哈希、已验收的 C 板双读备份和 `WP_AY0_FORMAL_SECTOR3_OFFLINE_V1` manifest。默认计划禁用执行，实际执行经独立监督和一次性标记。
- 加载时从原 sector3 与目标整片复原打包输入并重建包，核对 manifest 和文件字节。连接后双读整片与 Options，并以打包输入 SHA 约束实时读回。Halt 后再次核对整片 SHA。任一次源漂移都在 Flash 写入引擎前停止。
- 复用现有扇区 3 擦除、字地址白名单、未提交态读回、CRC、单次提交的引擎。写后两次整片必须等于 `expected-full-committed-private.bin`，并核对 Options 和 C 身份。正式路径读回成功后保持 Halt，Reset 和 Go 配额均为 0，由 B 批次卡安排后续断电和冷启动。
- 合成测试覆盖包重建、双读备份绑定、Halt 前后源漂移零写入、sector3 范围、写后整片错误拒绝以及正常提交。相关定向 pytest 共 **134 项、40 个子例通过**。本阶段没有设备连接或 Flash 写入。

B 的应用安装应以写入正式 sector3 后的已核验整片作为保护区基线。B 批次卡需绑定现场备份及其 SHA、正式配置写入包、应用镜像和回退对象。 [打包器](../../tools/b5_sector3_package.py) · [写入器](../../tools/b5_sector3_write.py) · [监督器](../../tools/b5_sector3_write_supervisor.py)
