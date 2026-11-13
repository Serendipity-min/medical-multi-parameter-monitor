# R64 · WP-AZ AZ-2 / AZ-3 回执

## AZ-2 云端

**部署及 C 断电验收 PASS。** 2026-11-12，依据 [R64 §1](https://github.com/Serendipity-min/medical-multi-parameter-monitor/blob/d6a5f29/node-b/docs/PI-REVIEW/R64-WP-AZ-AZ2-AZ3-CARD-20261112.md)。现场确认 C 与 TTS 断电，COM15 未枚举。

- 现网与仓库 ACL 的 `gateway-c` 写通配及 `backend-reader` 正式网关读通配一致。现网另有环境专用规则，逐字节保留。备份存于 `/opt/medical-monitor/backups/wp-az-2c97094-r64-qbmvvk8c`。ACL 原 SHA-256 `e7f4676b772f109d99844363e6e017db4f23e825a2cd73ad183e7332db56993f`，新 SHA-256 `bee2be2f28adc4bd531acaa885613925e63f35911a91615a1ff736c92fa3b03b`。把下列两条移除即可逐字节还原。
- 向 Mosquitto 子进程发送 SIGHUP。其 PID 3525 和包装器 PID 3253 均保持。现有日志未提供独立的 reload 确认行，实际设备收包与发声由 AZ-3 验证。
- 源码 `2c9709474d11d09d8538783d44aea189a1864af8`，release `wp-az-2c97094`。未压缩 tar 为 102,400 B，SHA-256 `e0b8f85b8e7b0309b324a4300a95a81b5a7313cecf1fd109386d09e6661811bd`。18 个归档成员与 Git blob 核对一致，服务器解包后逐文件重算通过。
- `backend.env` 以 S4 为基线仅追加 `MONITOR_BROADCAST_DEVICE=1`，文件和进程环境均已核对。保留 `MONITOR_BROADCAST=1`，HR 键未设置。服务器北京时间 18:00:14.561 完成部署核验。
- 健康接口 `ok`、MQTT 已连接。无令牌 WSS 为 `OFFLINE`，`broadcast:null`、`broadcast_history:[]`。Chrome 新上下文显示「等待设备上电」，P3 页面可用。受限截图 SHA-256 `c5a4fe147d6c2dc48a9685be458b583b2dc8d6f059b33b5aa68f8c2374898685`。

| ACL 账号 | 唯一增量 |
| --- | --- |
| `gateway-c` | `topic read mpm/v1/GW-C-001/voice/broadcast` |
| `backend-reader` | `topic write mpm/v1/GW-C-001/voice/broadcast` |

| 进程 | 部署前 PID | 部署后 PID |
| --- | ---: | ---: |
| webbackend | 1348667 | 1353672 |
| webai | 1244393 | 1244393 |
| Broker 包装器 | 3253 | 3253 |
| Mosquitto | 3525 | 3525 |
| Nginx | 3383 | 3383 |

AZ-2 回滚使用已备份 ACL 并向同一 broker 子进程发 SIGHUP。移除 webbackend 的 `80-wp-az.conf` 后执行 daemon-reload，仅重启 webbackend，回到原 `70-wp-ay-s4.conf` 指定的 S4 release 与 env。

## AZ-3 刷写与现场

AZ-2 回执提交时，AZ-3 尚未开始。负责人已确认 R51 的哈希范围：`1808eebf…` 为配置提交后、正式固件安装前的整片 1 MiB SHA。R51 两份归档中的 16 KiB sector3 SHA 均为 `471baff4…`，AZ-3 使用后者核对 sector3，并要求写前、写后逐字节一致。候选与 WP-AY0 回退镜像的离线 SHA 均已核对。

## AZ-3 写入

写入及整片核验 PASS。原生回执 `UNIFIED_C_INSTALL_FULL_VERIFY_PASS`，两次 `JLINKARM_WriteMem` 仅覆盖 sector0 和 sector4。392 B boot 前缀与候选 boot SHA 一致。写后保持 Halt，未观察到加载器复位，J-Link 会话关闭完成。现场关 C 后已确认拔下 J-Link，随后用开关冷启动。

| 对象 | SHA-256 |
| --- | --- |
| 候选 boot | `ef85ab637e5de088e26403eeed1dd26528f8457cb52dc11ad7ddc403a3a2a841` |
| 候选及读回 code（61,228 B） | `9d1902461e340a20672be54ef255215ddb95a3936d0030fc4cdb5db818a9d083` |
| 候选 HEX | `704fff446b551c1191a17761e3a90112af7941428a19f1158d2132fd31a39c7f` |
| 写前整片（WP-AY0） | `5ac90f007ad6389619b255179d1cf4f39213a609f0f7e9c2ab2521b91275fa96` |
| 写后整片 | `659dc636e6aee84e468bb4846f721d124fc15cde3a5eee6289124b42442addad` |
| sector0 读回 | `d4046f3557d68e4fb52d847c24361cca6d08601b4c6a3b2df04aceac795e88b8` |
| sector3 写前、写后（16 KiB） | `471baff468b7ae4253e1048c4660371a9cf01ebd9ed308551107fafb54a7f0be` |
| sector4 读回 | `7ee7a90817157493453f7796db63027107548c920e759f52e81292e4162fd1d2` |
| Options（保持一致） | `52d5979da03bd7be45e385920ec7d5901793bab3f6bc1daa0c1c1997f9e91687` |

R51 配置提交后、WP-AY0 安装前的归档整片 SHA-256 为 `1808eebf84c763697d731ef5095055c394ca6d74920e89441c3d0fd9d11740b6`。上述两份 R51 归档的 sector3 字节相同。负责人和 PI 均已确认使用 16 KiB 的哈希核对。

受限写入证据的 SHA-256：

| 文件 | SHA-256 |
| --- | --- |
| `receipt-private.json` | `6f40494ddf9e0999c6650453cb284fbb6de74ada2c3ed82869fba624dc96f901` |
| `supervisor-private.json` | `08e9b70fba469db788c713b3c8c3b6207af8a9f6bb65e387d429e682730a968a` |
| `io-private.jsonl` | `44cbe67d4892c621105f05168735fd079ce6dd2b41ee58a2c5cf7463638540f8` |
| `sdk-private.log` | `cfc4ffd93cadabd6f7fe5c7b993cf152651e6623b74700b99442dcf38745d881` |
| `heartbeat-events.jsonl` | `ac2bd5b699486858b2dea9cdcb0f2686a2e848d3fff7321d8c0899c2db80a532` |

## AZ-3 现场时间线

北京时间。本机到服务器的 SSH 往返测量得到服务器快 8.136–9.167 s。WSS 每帧同时保留两端时刻。PI 独立记录从服务器 18:06:42.1 开始，预计 19:36:42 结束。

| 本机时刻 | 事件 |
| --- | --- |
| 18:08，秒 UNKNOWN | 现场报 C 拨到 ON，Chrome 朗读关闭。B 接 ECG 模拟器，D 测室温，TTS 独立 5 V，全程无人接入。 |
| 18:08:51.498 | 本机观察到 COM15 枚举。 |
| 18:09:06.552 | 首个 ONLINE，服务器 18:09:14.705。按现场分钟区间，上电到观察 ONLINE 为约 15.1–66.6 s。 |
| 18:09:38.253 | 首个有效 TEMP。 |
| 18:10:39.329 | 首条 TEMP 页面播报，距离首个有效 TEMP 61.1 s。现场确认喇叭有声，未听清内容。 |
| 18:11:19.724 | S8 单独重启 webbackend，WSS 自动重连。 |
| 18:12:21.119 | 新 TEMP 播报，现场确认听清。 |
| 18:14，秒 UNKNOWN | 现场确认模拟器屏显 120 bpm。本机 18:14:07.121 首次观察到有效 120 bpm。 |
| 18:17:08.245 | 一条 HR 播报「请静坐后复测心率。」，距首个有效 120 bpm 181.1 s。 |
| 18:17:21.190 | 下一条 TEMP。现场确认该时段有发声，未录制，逐条听辨和次数待复核。 |
| 18:19，秒 UNKNOWN | 现场回报调回 75 bpm。 |
| 18:20:05.121 | 首个恢复的有效 75 bpm，开始浸泡。 |
| 18:34:13–18:34:22 | 现场移动模拟器。WSS 有 9 个不同采集时间戳的 HR INVALID，约 9.0 s 后恢复 75 bpm。现场估计波形中断约 5 s。网关在线，MQTT 持续连接。 |
| 18:34:22.226–19:04:22.226 | 从恢复有效 HR 起重计无操作浸泡，满 30 分钟。 |
| 19:04，秒 UNKNOWN | 现场第一次关 C。TTS 5 V、B/D、模拟器和热点维持供电。COM15 于 19:04:54.123 消失。 |
| 19:05:08.505 | WSS 为 STALE，当前播报和历史均清空；页面于 19:05:08.776 记录播报区隐藏。 |
| 19:05，秒 UNKNOWN | 现场只给 C 复电。19:05:41.872 枚举 COM15，19:05:54.963 观察到 ONLINE。 |
| 19:07:27.152 | 复电后的新 TEMP，距 ONLINE 92.2 s。现场确认喇叭没有重播旧内容，新体温清楚且只播一次。 |
| 19:09:53.637 | 最终断电期间 COM15 消失。现场回报「19:10:02 关闭」，该时刻比主机观察到 USB 消失晚 8.4 s，接近服务器钟差，实际拨开关的秒数和钟源未能对齐。 |
| 19:10:04.974 | 最终断电后 WSS 的播报及历史清空。19:10:17.729 为 OFFLINE。 |

## AZ-3 观察与判据

- **两次上电到 ONLINE 均在 90 s 内。** 首次按现场 18:08 分钟区间和 COM15 已出现的上界估计为 15.1–66.6 s。即便现场读的是快约 8–9 s 的服务器钟，保守上界仍低于 76 s。复电的 19:05:24.347 主机提示与 COM15 枚举给出 13.1–30.6 s 的范围。真实开关秒数缺失，保留区间。
- **体温链路有实物发声证据。** 首条距 ONLINE 92.8 s，距首个有效 TEMP 61.1 s，现场听见但未听清。S8 重启后的新一条听清。复电后的首条距 ONLINE 92.2 s，晚于卡片的约 60 s 预期，未定位延迟来源。现场确认该条清楚且只播一次。
- **HR 规则与网页。** S8 后有效 75 bpm 连续超过 2 min，HR 播报 0 条。有效 120 bpm 持续超过 5 min，页面只出现 1 条 HR 播报；现场对相邻的 HR 和 TEMP 报告有发声，缺少逐条内容及次数确认。切回 75 bpm 后无新增 HR 播报。
- **30 分钟无操作浸泡。** WSS 17,810 帧均 ONLINE 且 MQTT 已连接，最大帧间隔 455 ms。按各流的不同采集时间戳计，HR 为 1,800/1,800 VALID，TEMP 为 1,801/1,801 VALID，均为 LIVE。浸泡的 6 条 TEMP 首见本机时刻为 18:37:23、18:42:23、18:47:24、18:52:25、18:57:26、19:02:27，相邻间隔 300.1–301.0 s。现场回报均有播报、无异常，包含发热观察。未测量温升。
- **断电清空时限。** 首次断电后清空为 COM15 消失后 14.382 s。按现场开关动作的主机提示和 COM15 消失估计，实际 OFF 到清空约为 14.4–32.0 s。因缺失实际拨 OFF 秒数，严格的 20 s 判据为 UNKNOWN。复电后旧播报为 0，观察 ONLINE 逾 2 min；网页的新事件与现场听到的体温对应。
- **证据范围。** Chrome 朗读全程关闭。录像未录制，带声音视频 SHA 为 NOT_AVAILABLE。实际发声依据现场听辨，截图只验证网页。浸泡的逐条音频内容和次数未作独立复核。未触发 R64 的回退条件，C 仍保留经读回核对的 WP-AZ，现场已执行最终关机。AZ-3 流程完成，整体验收交 PI 裁定。

| 受限证据 | SHA-256 |
| --- | --- |
| WSS 快照记录 | `e2c1b44a6d57568a6a82336bdbbbad9ef1468f1b38e846cae505be4357360728` |
| WSS 与 COM15 事件 | `9258cf3ef92f640051f23b35bc080b8fbafa80ad506218df0ebdfc7f2ab89d10` |
| 页面事件与截图索引 | `adb2f6b5d0fe4217c8ee7d8b09b544cbbf9e0d73a2a81304340e8edfcd7ad226` |
| 浸泡的 10 / 20 / 30 min 记录 | `1041b78ac9a73431e26c622a797322abdc09f1ca8cbfc311f105b62f398a48f5` |
| 首条 TEMP 页面截图 | `bc8df8c879f6d01a11861de441546795ac18d3034b18247970282da49f203c8f` |
| HR 页面截图 | `03a194b8d29ed9f0afd87431fd68f6ef882b6abc3df4df0d37d6e3e3632efce4` |
| 首次断电清空页面截图 | `c5cdbc423670fac6b7df70cb406f9b0a3a6a6a791fafb1d841ba10f6d443062b` |
| 复电后新 TEMP 页面截图 | `77ed26acee99afdbab7af9ea02aedb5f81a5f1a9137a61fb1cbb2eafff98fdc7` |

## S8 收尾

| 动作 | 服务器北京时间 | webbackend PID |
| --- | --- | --- |
| 增加唯一一行 `MONITOR_BROADCAST_HR=1` | 18:11:28.018 | 1353672 → 1356599 |
| 移除该行并恢复 AZ-2 | 19:10:36.115 | 1356599 → 1369804 |

两次仅重启 webbackend。webai 1244393、Mosquitto 3525（包装器 3253）、Nginx 3383 均保持。收尾用 S8 前备份逐字节核对 env，验证进程保留 `MONITOR_BROADCAST=1` 和 `MONITOR_BROADCAST_DEVICE=1`，HR 环境变量已移除。新 WSS 连接显示网关 OFFLINE、MQTT 已连接、`broadcast:null`、`broadcast_history:[]`，P3 页面可用。
