# R61 · W-AY run4 回执

## S7 开启

**PASS。** 按 [R61 §1](https://github.com/Serendipity-min/medical-multi-parameter-monitor/blob/35fe6d4/node-b/docs/PI-REVIEW/R61-WAY-RUN4-CARD-20261112.md) 执行独立的 run4 开关步骤。C 未枚举 COM15，正式 WSS 为 `OFFLINE`。当前 `backend.env` 与 S4 基线逐字节一致，备份到 `/opt/medical-monitor/backups/wp-ay-s7-r61-v1pqh0da/backend.env` 后，仅追加 `MONITOR_BROADCAST_HR=1`。服务器北京时间 17:25:22.087 完成重启。运行环境确认 HR 开关已加载，健康 `ok`、MQTT 已连接。断电无令牌快照为 `broadcast:null`、`broadcast_history:[]`。

| 服务 | 开启前 PID | 开启后 PID |
| --- | ---: | ---: |
| `medical-monitor-h3-webbackend.service` | 1341021 | 1345280 |
| `medical-monitor-h3-webai.service` | 1244393 | 1244393 |
| `medical-monitor-mqtt.service` | 3253 | 3253 |
| `nginx.service` | 3383 | 3383 |

## run4 现场

待 PI 开始记录和普通 Chrome 朗读就绪。结束后移除 HR 开关，按 S4 基线复核。
