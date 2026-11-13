# R55 · WP-AY S4-B 与 W-AY 回执

2026-11-12。依据 [R55 §3–§4](https://github.com/Serendipity-min/medical-multi-parameter-monitor/blob/43c31be/node-b/docs/PI-REVIEW/R55-20261112.md)。本回执包含 S4-B 部署和 PI 复核放行后的 W-AY 现场记录。

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

## W-AY 现场回执

**已完成一次 NIBP 测量，窗口最终裁定待 PI。** 依据 [R55 §4–§5](https://github.com/Serendipity-min/medical-multi-parameter-monitor/blob/fe37d1eaccfdb8d04e4dafe5590fe95e59bcd710/node-b/docs/PI-REVIEW/R55-20261112.md)。PI 的独立记录由负责人确认自 15:13 开始。C 沿用正式镜像 `125c4b61…`，本次使用一次正常上电。全程无串口发送、Flash 写入、远程启动或现场服务改动，HR 播报继续关闭。

负责人确认两位成年志愿者知悉公开页面与 PI 记录并同意，四位现场观察者已分工。使用电池供电，ECG 接模拟器，血压泵独立供电。J-Link 从 C 断开后，Windows 核对笔记本使用电池，电量 79%，再发出冷启动提示。连续记录期间未见电气异常或受测者不适报告。

### 时间线

以下为本机收到事件的北京时间。COM15 和人工回执为代理边界，开关拨动、探头放置及 E 屏启动的精确时刻均为 UNKNOWN。

| 时刻 | 事件 |
| --- | --- |
| 15:26:50.767 | COM15 首次枚举。负责人随后确认五板和模拟器已上电，人体未接触设备。 |
| 15:29:17.301 | WSS 首次观测到网关 ONLINE，距 COM15 枚举 146.5 s。 |
| 15:29:18.688 | 首个 LIVE、非合成、VALID 体温快照。 |
| 15:29:52.074 | 发出放置 A 指夹、D 体温探头和开启朗读的提示。 |
| 15:30:20.531 | 首条 TEMP 播报，距首个有效体温快照 61.843 s。探头放置动作与首条播报的先后为 UNKNOWN。 |
| 15:30:47.929 | 收到指夹和体温探头已就位、朗读已开启的确认。 |
| 15:35:20.729 | 第二条 TEMP 播报，距首条 300.198 s。 |
| 15:37:53.512 | 探头就位确认后已过 425.6 s，发出一次 NIBP 测量提示。 |
| 15:39:06.344 | WSS 收到唯一一条有效实时 NIBP 结果。 |
| 15:39:06.450 | WSS 收到与该结果对应的唯一一条 NIBP 播报。 |
| 15:39:14.949 | 主机开始监视断电，随后提示先取下附件，再关 C 和其余设备。 |
| 15:39:57.383 | COM15 消失，作为 C 断电的本机代理时刻。 |
| 15:40:02.862 | 连续记录末次快照，网关仍为 ONLINE，播报仍在。 |
| 15:40:03.174 | 记录器检测到交流电并退出，距 COM15 消失 5.791 s。 |
| 15:40:38.243 | 后续无令牌快照已为 OFFLINE，播报为空，距 COM15 消失 40.860 s。页面显示待机。 |

### 验收逐项

| R55 项 | 现场证据与状态 |
| --- | --- |
| 体温就绪、限频与显示一致 | **PASS（观测到的规则行为）**。探头就位确认到血压提示间有 425.6 s，快照连续显示 LIVE、VALID。两条 TEMP 播报间隔 300.198 s，期间无重复，播报值与页面两次均相差 0.0 °C。首条出现在就位确认之前，真实放置时刻及该条是否来自已接触皮肤的探头为 UNKNOWN。 |
| NIBP 一次测量 | **PASS（结果与播报）**。负责人确认 E 屏出结果并已泄压。WSS 一条 LIVE、非合成、VALID 结果对应一条播报，分类与 E 屏照片所示测量结果一致。泵启动和测量耗时为 UNKNOWN。 |
| 朗读及报警区 | **朗读 NOT_PASS**。负责人确认已开启朗读，现场未听到声音。免责声明的朗读和单条播放次数未验收，原因 UNKNOWN。快照播报文字带免责声明，取证浏览器未发现播报文字进入报警区。 |
| WebAI LIVE 兼容性 | **PASS**。只做一次健康与现有 `SnapshotReader` 的只读核对，返回 `ok`，可读 `five / GW-C-001 / ONLINE` 快照和 LIVE 有效流，同时存在新增播报字段。该时点尚无播报，不调用模型。 |
| 断电后 20 s 内清空 | **UNKNOWN**。断电后约 5.5 s 的最后一个连续快照仍有播报，随后记录器因检测到交流电提前退出。后续独立浏览器确认 `OFFLINE`、`broadcast:null`、`broadcast_history:[]`，并核对播报条隐藏，但未覆盖 20 s 边界。请 PI 用其连续 WSS 记录复核。 |
| 复电后前 60 s 无旧播报 | **NOT_RUN**。现场未确认 20 s 判据，保持断电，未复电。 |
| 最终现场状态 | 负责人确认人体附件全部取下、五板及工装均已断电，C 断电约为北京时间 15:40，精确秒数 UNKNOWN。主机复查 COM15 仍未枚举。后端最终健康 `ok`，MQTT 仍连接。 |

### 本机受限证据

截图、记录和生理读数只留在本机 EFS 归档 `WP-AY-W-20261112-run1`。仓库只记摘要和 SHA-256。

| 证据 | SHA-256 |
| --- | --- |
| 开窗前待机截图 | `ebf89a56ec73cf48037ac8e2eb85f2baae52aef6d44b3fef1f3627875e4ef327` |
| 第一条 TEMP 播报截图 | `2339441ee98293d41de654f858bc9a62bacd48d1831ba760e9b710937ee5496d` |
| 第二条 TEMP 播报截图 | `2f682ca316d2eb97ee0b8721cd7013d8f3659ded910468083cce75d473926fb8` |
| NIBP 播报截图 | `b3ee7a4b950f762857ef84fe17364784e05f45df72b87b8dd0eec973bee401c8` |
| 断电后待机、播报条隐藏截图 | `97176b875a020dba6edc6cb6a4100495ea5999c208daab4934672c2026d0ec55` |
| 本机连续快照（1,010 行） | `8f76517efa856d2cb8b299c9433872be4e033d0a18ee97b09333124552b2f350` |
| 本机事件记录 | `ceaecda8c63b90a3af58f09aed4b6da531fdc0e506cff44a1ef2302b978ed2fc` |
| E 屏照片 | `87fd027cf226e3a3b36af8c2145d68e83b19584f009035df9cb30461def6163a`（EFS 归档 `e-screen-1.jpg`，与原文件 SHA 一致） |
