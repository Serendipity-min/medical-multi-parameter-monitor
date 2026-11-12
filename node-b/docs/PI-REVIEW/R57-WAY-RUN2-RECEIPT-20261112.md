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

**现场执行完成，R57 整体未达到全部通过判据。** 75 bpm 负向对照、断电清空、复电不补播及新播报生成均有现场记录。120 bpm 段没有 HR 播报，连续有效输入不足。首轮探头贴肤时长与部分音频细节仍待 PI 裁定。

PI 独立记录于服务器北京时间 16:07:56 开始，计划至 17:27:56。文件为 PI 侧 `node-b/build/w-ay/w-ay-run2.jsonl`。本机无令牌 WSS 连续记录 15,733 帧，C 首次启动后的相邻快照最大间隔为 484 ms。现场确认电脑听到预检提示语并开启朗读。预检阶段 Windows 曾报交流供电，当时五板断电。现场断开电源后，Windows 复验电池供电 79%，才发上电提示。两段 C 通电期间本机电源采样均为电池。ECG 只接模拟器。无血压测量、Flash 写入、串口命令或设备播报下发。

### 电源台账

下表使用北京时间的 Windows 本机时钟，服务器约快 8 s。组回报的分钟级时刻、COM15 代理时刻和实际拨开关的时刻分别记录。无独立观察的设备时刻标为 UNKNOWN。

| 设备 | 首次上电 | 首次断电 | 唯一一次复电 | 最终断电 |
| --- | --- | --- | --- | --- |
| A 板 | 组回报约 16:13，单台 UNKNOWN | 随组确认已断电，单台 UNKNOWN | 组回报已开启，单台 UNKNOWN | 组回报约 16:33，单台 UNKNOWN |
| B 板 | 有效 ECG/HR 证明在用，单台 UNKNOWN | 随组确认已断电，单台 UNKNOWN | 有效 HR 证明在用，单台 UNKNOWN | 组回报约 16:33，单台 UNKNOWN |
| C 板 | 组回报约 16:13，COM15 16:13:04.032 | COM15 消失 16:28:08.651，开关秒数 UNKNOWN | COM15 16:29:31.750，开关秒数 UNKNOWN | 负责人约 16:33，COM15 消失 16:33:09.577 |
| D 板 | LIVE TEMP 证明在用，单台 UNKNOWN | 随组确认已断电，单台 UNKNOWN | LIVE TEMP 证明在用，单台 UNKNOWN | 组回报约 16:33，单台 UNKNOWN |
| E 板 | 是否曾上电 UNKNOWN，未测血压 | 单台 UNKNOWN | 是否曾上电 UNKNOWN | 组回报约 16:33，单台 UNKNOWN |
| ECG 模拟器 | 75 bpm 对照开始前已在用，开关时刻 UNKNOWN | 随组确认已断电，单台 UNKNOWN | 75 bpm 在用，开关时刻 UNKNOWN | 组回报约 16:33，单台 UNKNOWN |
| 其他独立工装 | 单台及开关时刻 UNKNOWN | 随组确认已断电，单台 UNKNOWN | 单台及开关时刻 UNKNOWN | 组回报约 16:33，单台 UNKNOWN |
| 血压泵 | 未启动 | 不适用 | 未启动 | 不适用 |

热点无切换回报。J-Link 依现场预检断开。最终负责人确认断电，C 的 COM15 消失且 WSS 为 OFFLINE。COM15 枚举到 ONLINE 分别为 16.554 s 和 52.443 s。精确通电时刻缺失，两个时长均以枚举为起点。

### 操作与观测

以下为本机北京时间。播报的服务器原时刻附在同一行。

| 本机时刻 | 事件 |
| --- | --- |
| 16:13:20.586 | 首次观测到网关 ONLINE。 |
| 16:13:24.746 | 首个有效 LIVE 75 bpm。保持 75 bpm 至切换提示至少 246.0 s，HR 播报 0 条。 |
| 16:14:24.279 | 首条 TEMP，服务器 16:14:32.409。按服务器字段计，距 ONLINE 63.596 s。 |
| 16:17:31.408 | 提示切换至 120 bpm，人工实际切换秒数 UNKNOWN。 |
| 16:18:49.689 | 首个有效 LIVE 120 bpm。现场确认模拟器设为 120 bpm、B 屏 ECG 波形连续。 |
| 16:19:24.914 | 第二条 TEMP，服务器 16:19:33.078。 |
| 16:23:04.636 | 首个有效 120 bpm 后已观测 254.947 s，提示调回 75 bpm，负责人回报约 16:23 切回。 |
| 16:24:09.962 | 主机记下切回确认，随后确认有效 LIVE 75 bpm 已恢复。 |
| 16:24:24.914 | 第三条 TEMP，服务器 16:24:33.095。 |
| 约 16:24–16:27 | 负责人在网页输入 AI 令牌并问两题，截图收到后结束问答。 |
| 16:28:21.012 | 首次断电后 WSS 为 STALE，`broadcast:null`、`broadcast_history:[]`。 |
| 16:28:35.662 | WSS 首次转为 OFFLINE，保持播报为空。 |
| 16:30:24.193 | 复电后 ONLINE。 |
| 16:31:27.316 | 新 TEMP 播报，服务器 16:31:35.520，距复电后 ONLINE 63.120 s。 |
| 16:33:24.133 | 最终断电后再次观测到 WSS 清空。 |
| 16:33:35.661 | WSS OFFLINE，保持播报为空。 |

### R57 验收

| 项目 | 现场结果 |
| --- | --- |
| 首条 TEMP | **时间与数值 PASS，连续贴肤证据不完整。** 首条在 63.596 s 生成，播报与同帧 TEMP 源值差 0.03 °C，按 P3 的一位小数格式复算时相同。首条处于负责人描述的贴肤读数范围，实际贴好时刻和连续贴肤 ≥7 min 为 UNKNOWN。AI 问答时的 TEMP 属负责人说明的室温范围。后续独立浏览器记录的显示差分别为 0.1、0.0、0.0 °C。 |
| HR 75 bpm | **PASS。** 有效对照超过 4 min，HR 播报 0 条。 |
| HR 120 bpm | **NOT_PASS。** 模拟器保持 120 bpm，未生成预期播报。观察段去重后有 153 个 VALID、103 个 INVALID HR 快照采集时刻，最长连续有效且大于 100 bpm 段仅 51.580 s。规则遇到 INVALID 会清空该参数的判断窗口，现场未满足持续越界前提。HR 输入间歇无效的根因为 UNKNOWN。 |
| 浏览器朗读 | **有声已验证，逐条验收未完。** 普通 Chrome 听到开启确认语，前两条 TEMP 有逐条确认。收尾回复为“三条均能听到”。WSS 共记录四条 TEMP，第三条与复电后新播报的逐条对应、免责声明是否完整及每条播放次数为 UNKNOWN。独立浏览器捕获到的三条播报均未进入报警区。 |
| AI 问答 | 仅两问，截图保留原文。“现在心率多少”“现在体温多少？”均返回实时监护数据，页面标明本轮未调用模型，设备播报标记为 PAUSED。回答未见诊断性用语，两个数值均与问答区间内对应 LIVE、VALID 快照一致。请求精确时刻与同帧对照为 UNKNOWN。 |
| 断电清空 | **PASS，以 COM15 消失为代理。** 两次 WSS 清空分别耗时 12.361 s 和 14.556 s，页面播报条分别于约 12.707 s 和 14.633 s 隐藏。实际拨动开关到清空的精确时长为 UNKNOWN。 |
| 复电 | **PASS。** 前 60 s 无旧播报。保持 ONLINE 至少 126.605 s，三条旧播报键均未重现。ONLINE 63.120 s 后产生新 TEMP，复电阶段探头留在室温且无人连接。 |

### S5 收尾

服务器北京时间 16:34:15.824，移除 `MONITOR_BROADCAST_HR=1`，逐字节核对 `backend.env` 已恢复到 S4 备份内容。仅 webbackend 重启，PID 从 1326766 变为 1333401。webai、Mosquitto、Nginx PID 仍为 1244393、3253、3383。运行进程保留播报开关，HR 开关已移除。健康为 `ok`、MQTT 已连接，无令牌 WSS 为 OFFLINE，播报及历史为空。此时现场已收尾，可通知 PI 停止记录并复核。

### 受限证据

原始帧、截图和 AI 回答留在本机 EFS `WP-AY-W-20261112-run2`。下表记录 SHA-256，PI 的独立记录另行保管。

| 证据 | SHA-256 |
| --- | --- |
| 普通 Chrome 预检前截图 | `d102c6b70a12142764bc27cb37b6fba7bffab26f766837e193e30cf547d37add` |
| 普通 Chrome 两条 AI 问答原文及回执截图 | `ea14ff19d921fb39074da864ef605949fd835f33bc0c1f6093feb989b47ca220` |
| 第二条 TEMP 页面 | `a7bd6940aabe6c20e2e2635adb27ba91c8c9a589aa08494b67b187a9cdd9cca7` |
| 第三条 TEMP 页面 | `689fe2b08ca0a8f62cae1b6d2b9a02d6a4d67bc5b25ce9b210f6ada5b2fc0ddf` |
| 首次断电后页面播报条隐藏 | `79729d74326d68bedddc6d23cc43d2ef039284fcdb53cf370e3d3293e53e6bce` |
| 复电新 TEMP 页面 | `4c327298e9f528e2b88841ae76235400e6d6261800f5dee999cb790fdbffcc08` |
| 最终断电后页面播报条隐藏 | `55b05014319c34a96c8b9ea47c2f4bd2d3115e62ab746de4c78bf8414a66ec7a` |
| 本机 WSS 快照，15,733 帧 | `3451c30b44952ba7aab6749e022099f23a27424932e98ed5d45cecf5119aad91` |
| 本机事件记录 | `04e5fdd85c33789420ad107ec59b3979443301e2ba099e4b81d0b0fcf78107af` |
| 页面取证事件记录 | `8308e48bbc70d2b7931fd5e8fbfd13a1c5b0aca1d7888bdce371c0b228aa5339` |
