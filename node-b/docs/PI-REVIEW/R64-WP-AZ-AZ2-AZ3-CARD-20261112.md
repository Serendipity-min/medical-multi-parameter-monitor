# R64 · WP-AZ 执行卡：AZ-2 云端部署 + AZ-3 刷写 C 与现场

**2026-11-12 · PI。** 负责人已放行 AZ-2 和 AZ-3。依据：R62（方案及 §5 接口）、R63（AZ-1 离线 PASS，PI 位级重编结果一致）。
**R63 §3 更正**：喇叭为 **8 Ω / 1 W**，就是 2025-11-02 台架上正常播报用的那一只，阻抗问题解除。

## 1. AZ-2 云端（Codex 执行）
1. **ACL（只做增量）**：先备份现网 ACL 并与仓库 `cloud/broker/acl` 核对。只新增两条：`gateway-c` 的 `topic read mpm/v1/GW-C-001/voice/broadcast`，以及后端账号的 `topic write mpm/v1/GW-C-001/voice/broadcast`。**本轮不收窄 gateway-c 的写权限**（R62 回执中的收窄草案，留到 C 在线可验证上行时再做，作为后续加固项）。用 SIGHUP 让 Mosquitto 重新加载 ACL，**不重启 broker**，Mosquitto 的 PID 必须不变。
2. **后端**：部署 `2c97094` 的 `cloud/backend`，release 名 `wp-az-2c97094`，打包和逐文件核对方法同 S3/S4。env 以 S4 为基线，只增加 `MONITOR_BROADCAST_DEVICE=1`，HR 开关保持关闭。只重启 webbackend；webai、Mosquitto、Nginx 的 PID 不变。
3. **验收**（C 断电时）：健康 `ok`，MQTT 已连接；快照中 `broadcast:null`；页面正常。这时 C 上仍是旧镜像，后端即使发布也无人订阅，没有影响。
4. **回滚**：删除 ACL 新增的两条并 SIGHUP；后端切回 `wp-ay-s4-d30f7e7` 及 S4 env。

## 2. AZ-3 刷写与现场（Codex 和现场执行；PI 远程记录 WSS）
**硬件**
- TTS 模块用独立 5 V 供电，与 C 共地；喇叭 8 Ω / 1 W 接 SPK±；PA2/PA3 按原接线。不接人体，D 板测室温，B 板接模拟器。

**刷写**（做法同 R51 正式安装）
- 刷写前核对候选文件 SHA：boot `ef85ab637e5de088e26403eeed1dd26528f8457cb52dc11ad7ddc403a3a2a841`，code `9d1902461e340a20672be54ef255215ddb95a3936d0030fc4cdb5db818a9d083`。
- **只写 sector0 和 sector4**。sector3 和 Options 不动，写入后回读 sector3，整片哈希应与 R49 记录的 `1808eebf…` 一致。sector0 和 sector4 也回读并比对。刷写完成后断开 J-Link。
- **回退镜像**：WP-AY0，boot `c9caa44f…`，code `125c4b61…`（同样只写 sector0/4）。

**窗口步骤**（开窗前通知 PI 开始记录；时间线注明时钟来源）
1. C 上电，记录**实际拨开关的时刻**，用来计算上电到 ONLINE 的耗时。等进入 LIVE。
2. 约 60 s 后应出现 TEMP 播报，**喇叭读出"体表温度约 X 摄氏度"一次**，页面同时显示。
3. **HR（临时 S8）**：Codex 按 R59 §1 的做法打开 HR 开关，模拟器 75 bpm 保持 ≥2 min，改为 120 bpm（之后不碰）保持 ≥5 min，喇叭应读出"请静坐后复测心率"一次，然后改回 75 bpm。
4. **浸泡 ≥30 min**：设备保持 LIVE，不做任何操作。每 5 min 喇叭读一次 TEMP，每次只读一遍。期间留意模块和喇叭是否发热，用手背接近感受即可。
5. 断电：确认 ≤20 s 清空。复电并保持 ≥2 min：喇叭**不重播旧内容**，约 60 s 后播出新的 TEMP。
6. 收尾：关闭 HR 开关（S8 收尾，env 回到 AZ-2 的状态）。设备断电。

**通过标准**
- 每条播报喇叭只播一次，内容与页面一致；HR 播报在 120 bpm 下出现；断电复电后不重播旧内容。
- **链路回归**：浸泡期间网关不出现 OFFLINE/STALE 抖动，TEMP 和 HR 的 VALID 比例与 R52、R60、R63 相当（PI 用记录统计）；上电到 ONLINE ≤90 s（按真实开关时刻计）。
- 无电气异常，模块和喇叭没有明显发热。

**停止条件**
- 连续 2 条播报喇叭都没出声：停止，检查接线和 5 V 供电，**现场不重新刷写**，只允许回退到 WP-AY0。
- 同一条播报重复播放、读出乱码，或链路明显劣化（网关反复掉线、长时间 STALE）：回退到 WP-AY0。
- 任何电气异常：立即断电。窗口上限 75 min。

## 3. 最终状态（PASS 后）
C = WP-AZ 镜像；后端 `wp-az-2c97094`，`MONITOR_BROADCAST=1`、`MONITOR_BROADCAST_DEVICE=1`，HR 关；页面 `web-20261112-03`。PI 复核后写 R65，WP-AZ 判定 PASS 或 NOT_PASS，然后进入结项。

## 4. 回执
写在 codex 分支：`R64-WP-AZ-AZ2-AZ3-RECEIPT-…`。内容包括：
- ACL 前后差异（不含密码）、release tar SHA、env 摘要、PID 表；
- 刷写日志，sector0/3/4 的回读哈希；
- 时间线；带声音的录像 SHA（证实喇叭发声，只需包含环境声和喇叭声）；
- 发热观察；S8 收尾证据。
