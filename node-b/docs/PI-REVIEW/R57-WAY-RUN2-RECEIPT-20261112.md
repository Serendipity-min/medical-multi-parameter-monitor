# R57 · W-AY run2 回执

## S5 后端开关

**PASS，2026-11-12。** 按 [R57 §1、§6](https://github.com/Serendipity-min/medical-multi-parameter-monitor/blob/f863a1b07203bf65bdd5bf21ce66d5934bac0b8d/node-b/docs/PI-REVIEW/R57-WAY-RUN2-CARD-20261112.md) 执行。负责人确认五板及 ECG 模拟器断电、人体未接探头；COM15 未枚举，正式 WSS 初始快照为 OFFLINE。

- release 为 `wp-ay-s4-d30f7e7`。把原 `backend.env` 备份到服务器 `/opt/medical-monitor/backups/wp-ay-s5-r57-j_a2k8k_/backend.env`。逐字节比对确认新文件仅追加一行 `MONITOR_BROADCAST_HR=1`，运行进程已加载该开关。服务器时钟约 16:06:03 完成重启。
- 健康接口为 `ok`、MQTT 已连接，webbackend 自动重启计数为 0。C 断电时，无令牌 WSS 返回 `GW-C-001 / five / OFFLINE`、`broadcast:null` 和 `broadcast_history:[]`。正式页面加载 P3 的 `index-BsS2VLL9.js`。
- 上下文时差实测：服务器比 Windows 本机快约 8 秒。四次 SSH 时间取样中，最短往返 750 ms，对应偏差区间为 +8.209 至 +8.959 s。后续时间线注明时钟来源。

| 服务 | 操作前 PID | 操作后 PID |
| --- | ---: | ---: |
| `medical-monitor-h3-webbackend.service` | 1313299 | 1326766 |
| `medical-monitor-h3-webai.service` | 1244393 | 1244393 |
| `medical-monitor-mqtt.service` | 3253 | 3253 |
| `nginx.service` | 3383 | 3383 |

run2 收尾时删除 `MONITOR_BROADCAST_HR=1` 一行并仅重启 webbackend，再核验健康、断电快照和其余三个 PID。备份原件留在服务器受限目录。

## W-AY run2 现场

S5 回执提交时五板仍断电。待 R57 §3 的普通 Chrome 朗读预检通过、PI 连续记录就绪后进入 §4。
