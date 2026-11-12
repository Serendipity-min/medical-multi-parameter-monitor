# R55 · WP-AY S4-B 与 W-AY 回执

2026-11-12。依据 [R55 §3–§4](https://github.com/Serendipity-min/medical-multi-parameter-monitor/blob/43c31be/node-b/docs/PI-REVIEW/R55-20261112.md)。本次交付 S4-B，W-AY 等 PI 独立复核后开窗。

## S4-B 部署

- **PASS**。源码 `d30f7e7ae848b7557d5071257e24760abf4ca5a7` 的 `cloud/backend` 已部署为 `wp-ay-s4-d30f7e7`。未压缩 tar 为 102,400 字节，SHA-256 `118e76bb447e661fc8ce8ee97d7bf87e70c680b50aa3b973f53fc003a1c167dc`。本机通过 `git -c core.autocrlf=false archive --format=tar` 生成，18 个文件与提交中的 Git blob 逐字节核对。服务器解包后，18 个文件逐一匹配对应 SHA-256。
- 备份位于 `/opt/medical-monitor/backups/wp-ay-s4-d30f7e7/`，含 S3 release、env、systemd 单元与 drop-in。新 env `/opt/medical-monitor-h3/formal/wp-ay-s4-d30f7e7/backend.env` 的原始字节为 S3 env 加一行 `MONITOR_BROADCAST=1`，`MONITOR_BROADCAST_HR` 未设置。原有公开查看、five 档、网关与 Origin 白名单、MQTT 配置和查看令牌均按运行态核验保留。
- 只重启 `medical-monitor-h3-webbackend.service`。健康端点为 `ok`，MQTT 已连接。验收后复查后端 PID 一致，自动重启计数为 0。

| systemd 单元 | 部署前 PID | 部署后 PID |
| --- | ---: | ---: |
| `medical-monitor-h3-webbackend.service` | 1262544 | 1313299 |
| `medical-monitor-h3-webai.service` | 1244393 | 1244393 |
| `medical-monitor-mqtt.service` | 3253 | 3253 |
| `nginx.service` | 3383 | 3383 |

## C 断电验收

负责人确认 C 开关 OFF、电源灯灭。正式站点 B2 静态资源仍为 `index-DCGTKRxv.js` 和 `index-DxLjsS5m.css`。无令牌 WSS 在后端直连和全新浏览器会话中均取得以下快照字段。

```json
{"gateway_id":"GW-C-001","node_profile":"five","gateway_state":"OFFLINE","broker_connected":true,"broadcast":null,"broadcast_history":[]}
```

正式页面显示“等待设备上电”，未弹出令牌框。截图保存在本机 EFS 的 `WP-AY-S4-B-20261112/s4-b-offline-standby.png`，SHA-256 `b2a7f19bdc26a8f67b0aa3f83ee7a9d9387f3a23f9f02ed3d7eda0a46bcb649d`。浏览器回执 SHA-256 `1713747e28ce1b5de8bc7985cbc0052530e67475a5fa3ad175f47c8f3fe6f18d`。

WebAI 健康为 `ok`，模式 `MONITOR`。以原运行账户和有效配置调用已有 `SnapshotReader`，成功读取同一 `five / GW-C-001 / OFFLINE` 快照，且新播报字段为空。

| 本机／服务器记录 | Asia/Shanghai |
| --- | --- |
| 旧 release 备份归档 | 2026-11-12 15:08:54 |
| 部署、健康及直接快照核验完成 | 2026-11-12 15:08:56 |
| 正式浏览器无令牌验收 | 2026-11-12 15:09:11 |

## 回滚

仅关闭播报时，从 `/opt/medical-monitor-h3/formal/wp-ay-s4-d30f7e7/backend.env` 删除 `MONITOR_BROADCAST=1` 后执行 `sudo systemctl restart medical-monitor-h3-webbackend.service`。如需退回 S3 源码，移出 S4 的 `70-wp-ay-s4.conf`，使原 S3 drop-in 重新生效，再执行 `sudo systemctl daemon-reload` 和同一条后端重启命令。此次未执行回滚。

## W-AY 状态

**NOT_RUN，等待 PI 复核 S4-B。** 负责人已说明下一窗口拟使用 2 位志愿者和 4 位现场安全观察者，ECG 继续由模拟器输入，血压泵独立供电。以上为现场计划，尚无上电、测量、朗读、LIVE WebAI 读数、NIBP E 屏照片或复电证据。PI 确认 S4-B 后，开窗前通知 PI 开始记录，再按 R55 §4 执行。
