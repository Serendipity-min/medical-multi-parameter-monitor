# R59 · W-AY run3 回执

## S6 开启

**PASS，2026-11-12。** 按 [R59 §1](https://github.com/Serendipity-min/medical-multi-parameter-monitor/blob/14f6bce25e7f47ea50706c94b6cf6e9b3db82097/node-b/docs/PI-REVIEW/R59-WAY-RUN3-CARD-20261112.md) 执行。负责人确认 C 断电、无人体连接；COM15 未枚举，初始无令牌 WSS 为 `OFFLINE`。

- 操作对象为 `wp-ay-s4-d30f7e7/backend.env`。写入前核对与 S4 部署态基线逐字节一致，并另存本轮备份 `/opt/medical-monitor/backups/wp-ay-s6-r59-pdm40vdl/backend.env`。写入后核对为 S4 基线仅追加一行 `MONITOR_BROADCAST_HR=1`。运行进程已加载该开关。
- 服务器北京时间 16:51:08.754 完成重启。健康 `ok`，MQTT 已连接。C 断电时无令牌快照返回 `broadcast:null`、`broadcast_history:[]`，网关 `GW-C-001` 为 `OFFLINE`。页面仍加载 P3 资源。
- 开窗前 SSH 时间取样中最短往返为 604 ms，服务器比本机快 +8.190 至 +8.794 s。后文时间线区分两套时钟。

| 服务 | 开启前 PID | 开启后 PID |
| --- | ---: | ---: |
| `medical-monitor-h3-webbackend.service` | 1333401 | 1337555 |
| `medical-monitor-h3-webai.service` | 1244393 | 1244393 |
| `medical-monitor-mqtt.service` | 3253 | 3253 |
| `nginx.service` | 3383 | 3383 |

## W-AY run3 现场

S6 已验收。等待 PI 记录与普通 Chrome 朗读预检后开窗。窗口结束后移除 HR 开关，仅重启监护后端并复验 env。
