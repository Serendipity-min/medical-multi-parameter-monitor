# R83 · B 算法 C1 重刷与真人验收、只读 MQTT 录制卡

2026-11-18，PI 签发，由 Codex 执行，负责人在现场操作。负责人原话：“授权C1重刷B，你来签合同，MQTT录制也授权”。依据为 R82 §2.1、§3.1、§4。

## 0. 目的与边界
- **目的**：
  1. 把 B 的 BIO_V2 换成 C1：工频判据改为绝对量，HR 需要 5 个稳定间期。同一次写入恢复主页右上控件 17 的原质量显示，保留左下控件 20 的诊断串。
  2. 在真人验收的同时，只读录制 NODE-B 的 MQTT 遥测，包括带无效标记的 ECG/RESP 波形，供 PI 离线分析 RR 和核对 HR。
- **授权范围**：
  - 离线：实现、主机测试、ARM 构建、录制脚本；
  - 实板：只对 B，一次 J-Link 会话，写入 sector0–2；
  - 模拟器本地验收；
  - 真人验收一轮；
  - 服务器上一次只读 MQTT 录制。
- **回退**（恢复为写前的 R80 v2）**不默认包含**。负责人放行时须另写“同意 R83 回退一次”，否则出问题时只停止并上报。
- **不在范围**：
  - RR 算法修改；A、C、D、E 的固件；sector3 及以上；options；屏幕工程；
  - 向 MQTT **发布**任何消息；修改 Broker、ACL、后端或服务配置；
  - 输出或提交任何凭据；
  - 故障注入。

## 1. 现行基线（事实）
- **B 现装 R80 v2**：应用 40,600 B，`e9f34d78215a57e14a54255f84d8c8ba22b1c5aa8ee0056f97400f59993a5b77`；整片 `7d0e617ed609585e216a8aa258da63767ae8d289d2ec0da11cb7d539756d7d44`。来源为 `codex/r79-b-home-diag@427b093` 回执及 R81。
- **构建入口**：`node-b/tools/build_b4_arm.py`，R80 v2 的参数为 `--candidate-r6 --diag-reason --diag-home`。
- `node-b/firmware/biov2/实验固件` 受 `deployment-freeze.json` 冻结。

## 2. 实现要求
1. **冻结源码不动**，全部在构建副本中注入，延续 R78/R80 的做法。
2. **新增 `--algo-c1`**：对副本的 `HARDWARE/bio_v2.c` 做 `replace_once` 注入。结果必须与下列补丁逐行等价（PI 在 Linux gcc 下以 `-std=c99 -O2 -Wall -Wextra -Werror` 编译通过）：

```diff
@@ -8,7 +8,7 @@
 typedef struct { float b0,b1,b2,a1,a2,z1,z2; } Section;
 typedef struct {
     uint32_t anchor, last_good, minimum, maximum, timeout, intervals[5];
-    uint32_t count, index, candidate_rate, reason;
+    uint32_t count, index, candidate_rate, reason, required;
     uint8_t anchored;
 } Periods;
 typedef struct {
@@ -24,6 +24,12 @@
 static Channel heart, breathing;
 static uint32_t previous_ms, previous_sequence;
 static uint8_t have_sample;
+#ifndef HEART_REQUIRED
+#define HEART_REQUIRED 5u
+#endif
+#ifndef MAINS_ABS_POWER
+#define MAINS_ABS_POWER 9.6e11f /* 约100 mV峰值工频 */
+#endif
 
 static float absolute(float x) { return x<0.0f ? -x : x; }
 static float greater(float a,float b) { return a>b ? a : b; }
@@ -60,6 +66,7 @@
     c->periods.maximum=respiration ? 10000u : 2000u;
     c->periods.timeout=respiration ? 12000u : 4000u;
     c->periods.reason=BIO_V2_WARMUP;
+    c->periods.required=respiration ? 3u : HEART_REQUIRED;
 }
 static uint8_t accept_input(Channel *c,int32_t raw,uint8_t resp,uint32_t now)
 {
@@ -111,7 +118,7 @@
     p->intervals[p->index]=elapsed;p->index=(p->index+1u)%5u;
     if (p->count<5u) p->count++;
     p->candidate_rate=0;p->reason=BIO_V2_NO_CYCLES;
-    if (p->count<3u) return 1;
+    if (p->count<p->required) return 1;
     for (i=0;i<p->count;i++) sorted[i]=p->intervals[i];
     for (i=0;i<p->count;i++) for(j=i+1;j<p->count;j++)
         if(sorted[j]<sorted[i]) {swap=sorted[i];sorted[i]=sorted[j];sorted[j]=swap;}
@@ -183,7 +190,7 @@
     if(c->clipped)reason|=BIO_V2_CLIPPED;
     else if((uint32_t)(now-c->valid_start_ms)<(resp ? 10000u : 5000u))reason|=BIO_V2_WARMUP;
     /* 原始干扰很强时保留滤波波形，但不通过制造量程内数字宣告可信。 */
-    if(fraction>.95f && c->raw_power>10000.0f)reason|=BIO_V2_MAINS;
+    if(c->line_power>MAINS_ABS_POWER)reason|=BIO_V2_MAINS;
     if(!rate)reason|=BIO_V2_NO_CYCLES;
     if(resp) {
         g_bio_v2.rpm_valid=reason==0;g_bio_v2.rpm=reason==0 ? rate : 0;g_bio_v2.rpm_reason=reason;
@@ -210,10 +217,10 @@
     r=good_r ? filter_channel(&breathing,resp,1) : 0.0f;
     /* 先判本次周期的输入资格，再建立周期历史，避免干扰结束后复活噪声历史。
        呼吸低通会把白噪声变成慢起伏，必须有足够低频能量占比才能候选判周期。 */
-    if(good_h && heart.raw_power>10000.0f && heart.line_power>heart.raw_power*.95f) {
+    if(good_h && heart.line_power>MAINS_ABS_POWER) {
         forget_periods(&heart.periods,BIO_V2_MAINS);heart.in_peak=0;
     } else if(good_h)heartbeat(h,now);
-    if(good_r && breathing.raw_power>10000.0f && breathing.line_power>breathing.raw_power*.95f) {
+    if(good_r && breathing.line_power>MAINS_ABS_POWER) {
         forget_periods(&breathing.periods,BIO_V2_MAINS);breathing.armed_trough=0;
         breathing.previous2=breathing.previous;breathing.previous=r;
     } else if(good_r && breathing.clean_power>1.0f && breathing.band_power<breathing.clean_power*.05f) {
```

3. **新增 `--diag-cap`**：只做 R80 中控件 20 的注入（`H%lu R%lu M%u`），**不删除也不改写**控件 17 的原质量写入。`--diag-home` 保留，用于复现 R80。C1 镜像的参数为 `--candidate-r6 --diag-reason --diag-cap --algo-c1`。
4. **主机测试**（Windows 和 Linux 都能运行；`run_host.py` 编译副本要支持指定源文件）：
   1. 用 C1 副本跑既有 `node-b/firmware/biov2/tests/run_host.py` 的全部 27 例，必须全部通过。
   2. 新增以下用例，沿用 `run_host.py` 中的 `sample()`，QRS 为 10000 码：
      - **工频不再误杀**：`mains` 取 5000、10000、30000、100000、1000000 码（R 波的 0.5–100 倍），各跑 65 s，结束时 HR 有效且与 60 相差不超过 2。
      - **极大工频**：`mains` 为 2,000,000 码，接近 `MAINS_ABS_POWER`，HR 无效且原因码含 64。按实际阈值取一个能触发的幅度，并在回执中写明。
      - **纯噪声**：白噪声 2000 码，以及白噪声加 `mains` 70000 码；6 个固定种子，各 180 s；每例 HR 有效帧不超过 2%，并记录最长连续有效时长。
      - **5 个间期**：从预热结束到首次 HR 有效，至少累积 5 个被接受的间期（可用 `hr_accepted` 和 `hr_fresh_intervals` 判定）。
   3. 扩充 `node-b/tests/test_build_b4_diag_reason.py`：`--algo-c1` 锚点唯一，`--diag-cap` 不改动控件 17。
5. **构建门槛**（任一项不满足就 STOP，不下载）：
   - 冻结源码校验通过；
   - 复现 `f2276540…`、R78 `24612613…`、R80 v2 `e9f34d78…`，三者都要逐字节一致；
   - C1 BIN 不超过 49,152 B，0 错误 0 警告；
   - 记录 BIN/AXF/MAP 的 SHA 和资源用量；
   - 用封存的 R80 写后整片，计算 C1 的写后整片预期 SHA。
6. **安装器**：新建 scope，仿照 R80，绑定以下内容：
   - 本卡 SHA；
   - 写前应用区 `e9f34d78…`（40,600 B）和写前整片 `7d0e617e…`；
   - C1 的 SHA 和字节数；
   - 扇区 [0,1,2]，1 次会话，不重试。
7. **只读录制脚本**，例如 `node-b/tools/r83_mqtt_readonly_capture.py`：
   - 读取服务器上后端已有的 MQTT 配置文件（路径作为参数传入），**不打印、不保存凭据**；
   - 使用独立的 `client_id`（如 `r83-readonly-<UTC>`），`clean_session`；
   - **只订阅** `mpm/v1/GW-C-001/NODE-B/telemetry/+` 和 `mpm/v1/GW-C-001/NODE-B/status`，QoS 0；代码里没有 publish 调用；
   - 每条消息写一行 JSON：主机接收毫秒、topic、原始 payload 字符串；
   - 有时长上限，到时退出；退出时输出行数和 SHA-256。
   - 提交前做两项检查：用本机临时 Broker 或模拟客户端测试；用 `grep` 确认没有 `publish`。
   - 这一点会写进回执：录到的波形在 C 侧已标为 INVALID 时同样保留。

## 3. 现场步骤
**S0–S2 写入（只给 B 上电，接模拟器，不接触人体）。** 同 R80：写前整片读两次，必须一致且等于 `7d0e617e…`；写入 sector0–2 一次；写后整片等于 §2 第 5 条的预期 SHA，身份、options、sector3–11 不变；安装器按标准流程 Reset/Go，然后 Close，物理拔掉 J-Link。

**S3 模拟器验收（不接触人体，每步拍照）。**
1. ECG 模式，接线 R→RA、L→LA、F→RL，B 断电再上电：60 s 内 HR 为 60，控件 20 显示 `H0`；**控件 17 恢复原质量数字，可读，没有重叠**。
2. 断开导联 30 s，H 不为 0；接回后恢复 H0，HR 60。
3. 可选：呼吸模式，冷接 RA–LL、20 bpm，R0、RR 20。做完改回 ECG 接法。

**S4 真人验收与 MQTT 录制。** 安全前提同 R74 §1：整条导电链不接市电，GT 用充电宝，电脑用电池，志愿者知情同意、无植入设备，有专人看护，累计接触不超过 30 分钟。
1. **上电**：按 GT → B → C 的顺序，A、D、E 保持断电。至少提前 5 分钟通知 PI，PI 开始录 WSS；**Codex 在服务器上启动只读录制**，时长上限 60 分钟。
2. **贴电极**：确认 B、C 都已在线后，按 R76 S2 贴法贴电极（RA 右锁骨下、LA 左下胸、RL 右下腹，先用酒精擦拭皮肤）。
3. **静坐 5 分钟**：报开始时刻。第 2、4 分钟时，安全员各数一次 **60 s 桡动脉脉搏**和 **60 s 呼吸次数**，同时记下屏上 HR、RR 以及控件 20 的读数，并报各自的起止时刻。
4. **节律呼吸 2 分钟**：节拍器每分钟 12 次。同样数一次呼吸，并记录屏上读数。
5. **收尾**：先摘电极，再依次断开 C、B、GT，报告时刻。停止录制，计算 SHA。
6. **录制文件交给 PI**：放到服务器上 `mmpm-deploy` 用户可读的目录 `/home/mmpm-deploy/r83-capture/`（属主为 mmpm-deploy，权限 0600）。PI 用 scp 取回，存到 VPS 上 git 忽略的 `node-b/build/`，核对 SHA 后通知 Codex 删除服务器上的这份副本。原件存受限 EFS。

## 4. 判定
- **安装**：PASS 条件同 R80，任一核对不一致即 FAIL。
- **模拟器**：S3 第 1、2 项都满足，控件 17 可读。
- **真人 HR（C1 目标）**：
  - 静坐 5 分钟内，从首次有效算起，HR 有效占比至少 80%；
  - 两次人工脉搏对照，屏上 HR 与人工值相差均不超过 10%；
  - 控件 20 中 H 不再出现 64。
- **真人 RR**：本卡**只采数据，不判定**。记录 R 值、屏上 RR 和人工呼吸次数。RR 的结论由 PI 用录制数据离线分析后另行给出。
- **MQTT 录制**：PASS 条件为：
  - 录制覆盖 S4 全程；
  - 含 NODE-B 的 ECG/RESP 批次，包括 INVALID；
  - 没有任何 publish；
  - 后端服务状态不受影响（可用 `mmpm-control status` 核对）。

## 5. 停止条件
**安装和目标板**：遇以下情况立即停止，保存原件，不重试，不额外执行 Go/Reset。只有已获回退授权时，才能恢复 R80 v2 一次。
- §2 第 5 条的门槛任一项失败（不下载）；
- 写前核对不符；
- 出现 HALT/ROM，身份或 Flash 漂移；
- 安装后屏不亮、反复复位，或模拟器下 HR、波形异常。

**真人环节**：遇以下情况先摘电极，再断电，然后上报。
- 任何不适；
- 发现接入了市电；
- 冒烟、发热或异味。

**MQTT 录制**：脚本报错，或后端服务异常时，立即停止录制，不重试，不碰后端。

## 6. 回执（新分支 `codex/r83-b-c1`，基于含本卡的提交；文件 `R83-B-C1-RECEIPT-20261118.md`）
- 卡片 SHA；代码提交；测试命令和结果，新用例要给出逐例数值。
- 三份基线的复现结果；C1 产物的 SHA 和资源用量；写后整片的预期值与实测值；身份和 options 核对；原生动作计数和退出码。
- S3 照片清单和读数。
- S4 时间线，以及每次人工对照的数值和屏上读数。
- 录制文件的行数、起止时刻、SHA-256 和交付位置；`mmpm-control status` 的结果。
- 回退是否获得授权、是否执行。
- 每项按 PASS / FAIL / NOT_RUN / UNKNOWN 填写。凭据、热点名称、志愿者身份都不写入回执。
