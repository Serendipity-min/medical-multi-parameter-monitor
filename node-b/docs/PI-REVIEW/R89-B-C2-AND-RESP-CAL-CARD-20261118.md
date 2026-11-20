# R89 · B 算法 C2 重刷、RESP 模拟器定标与 P2 真人复测卡

> **R107 更正（2026-11-20）**：R106 模拟器换色验证证实导联线色标为**绿（F）→ RA（ERA，IN2N）、黄（L）→ LA（ELA，IN2P）、红（R）→ RL（RLD 右腿驱动）**，与厂家资料一致；本项目此前采用的“红 R→RA、绿 F→RL”是错的。见 [`R107`](R107-20261120.md)。本卡 S3 模拟器接线实测为 LA−LL（−III），S4 RESP 定标的 ERA 实际接在模拟器 RL 端子上，S5 真人沿用 R87 的错误色标。RESP 定标由 R108 按正确接线重做。

2026-11-18，PI 签发，由 Codex 执行，负责人在现场操作。负责人原话：“我打算做b（C2）和c，答辩暂时不着急，我们先追求有更好的结果。”依据为 R88 §4 第 2、3 条。

## 0. 目的、授权与边界
- **目的**：
  1. **(b) C2**：在 R83 C1 上加 C2（心搏漏检桥接，已锁定后判稳放宽到 ±30%），提高真人 HR 有效率，RESP 行为不变。
  2. **(c) RESP 定标**：模拟器呼吸模式下按已知 ΔR 做只读 MQTT 录制，得到 r 单位与欧姆的换算，判断真人 200–450 r 相当于多少欧姆。
  3. 用 C2 再做一轮 P2 真人（带 A 的 PR 参照和 MQTT 录制），验证 C2 上板后的有效率。
- **分两段放行**：
  - **离线段（本卡签发即放行）**：§2 的实现、主机测试、ARM 构建、安装器 scope 和录制包装器。任一门槛失败即 STOP，不进入现场。
  - **现场段（另需负责人当次放行）**：§3 的 S0–S6。负责人须在现场开始前写明“放行 R89 写入”。没有这句话，Codex 只交离线回执。
- **现场段的授权范围**（放行后）：
  - 实板只对 B：一次 J-Link 会话，写入 sector0–2，不重试；
  - 模拟器验收和 RESP 定标；
  - 电池供电下 GT、A、B、C 上电；一名志愿者，累计接触不超过 30 分钟；
  - 服务器上至多两次只读 MQTT 录制（S3–S4 模拟器一次，S5 真人一次），每次上限 60 分钟。
- **回退**（恢复为 R83 C1）**不默认包含**。负责人须另写“同意 R89 回退一次”，否则出问题时只停止并上报。
- **不在范围**：RR 算法修改；A、C、D、E 的固件；sector3 及以上；options；屏幕工程；向 MQTT 发布；改 Broker、ACL、后端或服务配置；凭据输出或提交；故障注入；D、E 上电；血压。

## 1. 现行基线（事实）
- **B 现装 R83 C1**：应用 40,420 B，`1c28707fa215f2ee068750440cc670cddc8e9629f45d20927fc2676ac168642b`；整片 `a40ad7633b4c2acaa8db0fbb229d635e747fad148f67266610789ac032ce560f`。来源为 `codex/r83-b-c1@cfd6b315c45df5d62e0474ab322956d5a12018fe` 回执。
- **C1 构建参数**：`node-b/tools/build_b4_arm.py --candidate-r6 --diag-reason --diag-cap --algo-c1`。
- **C1 源**：冻结源 `bio_v2.c` 经 `inject_algo_c1` 注入后 SHA-256 为 `e2e2a129866067cad5f3e98025857b8e7119aebc948b4a3a40c5a055f050235c`。PI 用 `cfd6b315` 上的注入函数复现，与 R82/R83 仿真用的 `bio_v2_abs5.c` 逐字节一致。
- **录制器**：`codex/r85-electrode-triage@ae87a5c` 的只读录制器（原字节 `d2b4a3d1…`），R87 已沿用。

## 2. 离线段

### 2.1 C2 补丁（相对 C1）
注入后的 `bio_v2.c` 必须与下列补丁逐行等价，SHA-256 为 `dcaba6feafd89989b5921ee08adf4d4a75f4379b6203cf693ed1beff7aa9c3e7`（LF 行尾，与 C1 源的行尾口径一致）。PI 在 Linux gcc 下以 `-std=c99 -O2 -Wall -Wextra -Werror` 编译通过。

```diff
@@ -8,8 +8,8 @@
 typedef struct { float b0,b1,b2,a1,a2,z1,z2; } Section;
 typedef struct {
     uint32_t anchor, last_good, minimum, maximum, timeout, intervals[5];
-    uint32_t count, index, candidate_rate, reason, required;
-    uint8_t anchored;
+    uint32_t count, index, candidate_rate, reason, required, tolerance;
+    uint8_t anchored, bridge, bridged;
 } Periods;
 typedef struct {
     Section notch1, notch2, hp, lp;
@@ -27,6 +27,9 @@
 #ifndef HEART_REQUIRED
 #define HEART_REQUIRED 5u
 #endif
+#ifndef HEART_TOLERANCE
+#define HEART_TOLERANCE 30u /* 心搏窗口相对中位数的允许偏差，百分比 */
+#endif
 #ifndef MAINS_ABS_POWER
 #define MAINS_ABS_POWER 9.6e11f /* 约100 mV峰值工频 */
 #endif
@@ -50,7 +53,7 @@
 static void forget_periods(Periods *p,uint32_t reason)
 {
     /* 失效清除资格和全部旧间隔；仅保留配置，不重置滤波制造新的阶跃。 */
-    p->count=0;p->index=0;p->candidate_rate=0;p->anchored=0;p->last_good=0;
+    p->count=0;p->index=0;p->candidate_rate=0;p->anchored=0;p->bridged=0;p->last_good=0;
     memset(p->intervals,0,sizeof(p->intervals));p->reason=reason;
 }
 static void configure(Channel *c,uint8_t respiration)
@@ -67,6 +70,8 @@
     c->periods.timeout=respiration ? 12000u : 4000u;
     c->periods.reason=BIO_V2_WARMUP;
     c->periods.required=respiration ? 3u : HEART_REQUIRED;
+    c->periods.tolerance=respiration ? 20u : HEART_TOLERANCE;
+    c->periods.bridge=!respiration;
 }
 static uint8_t accept_input(Channel *c,int32_t raw,uint8_t resp,uint32_t now)
 {
@@ -99,36 +104,53 @@
 }
 static void expire(Periods *p,uint32_t now)
 {
+    /* 可桥接漏检时锚点最长等两个最大间隔，否则慢心率下漏检一拍会先被判过期。 */
+    uint32_t limit=(p->bridge && !p->bridged && p->count>=3u) ? 2u*p->maximum : p->maximum;
     if ((p->count!=0 && (uint32_t)(now-p->last_good)>p->timeout) ||
-        (p->anchored && (uint32_t)(now-p->anchor)>p->maximum))
+        (p->anchored && (uint32_t)(now-p->anchor)>limit))
         forget_periods(p,BIO_V2_EXPIRED);
 }
+static uint32_t window_median(const Periods *p,uint32_t sorted[5])
+{
+    uint32_t i,j,swap;
+    for (i=0;i<p->count;i++) sorted[i]=p->intervals[i];
+    for (i=0;i<p->count;i++) for(j=i+1;j<p->count;j++)
+        if(sorted[j]<sorted[i]) {swap=sorted[i];sorted[i]=sorted[j];sorted[j]=swap;}
+    return sorted[p->count/2u];
+}
 static uint8_t accept_cycle(Periods *p,uint32_t at)
 {
-    uint32_t elapsed, sorted[5],i,j,swap,median,largest;
+    uint32_t elapsed, sorted[5],i,median,largest,tolerance;
     /* 候选时刻与最后合法周期分开。非法候选不能更新合法周期的有效期。 */
     expire(p,at);
     if (!p->anchored) { p->anchor=at;p->anchored=1;p->reason=BIO_V2_NO_CYCLES;return 0; }
     elapsed=(uint32_t)(at-p->anchor);
     if (elapsed<p->minimum) return 0;
+    /* 漏检一拍：间隔为窗口中位数1.75–2.25倍时只前移锚点，不入窗、不改率值；
+       不连续桥接，真实减半时下一间隔照常入窗并判不稳定。 */
+    if (p->bridge && !p->bridged && p->count>=3u) {
+        median=window_median(p,sorted);
+        if (elapsed*4u>=median*7u && elapsed*4u<=median*9u) {
+            p->anchor=at;p->last_good=at;p->bridged=1;return 0;
+        }
+    }
     if (elapsed>p->maximum) {
         forget_periods(p,BIO_V2_EXPIRED);p->anchor=at;p->anchored=1;return 0;
     }
-    p->anchor=at;p->last_good=at;
+    p->anchor=at;p->last_good=at;p->bridged=0;
+    /* 滞回：上一判定有效才用放宽容差维持，首次锁定仍按20%，噪声难以偶然成锁。 */
+    tolerance=p->candidate_rate ? p->tolerance : 20u;
     p->intervals[p->index]=elapsed;p->index=(p->index+1u)%5u;
     if (p->count<5u) p->count++;
     p->candidate_rate=0;p->reason=BIO_V2_NO_CYCLES;
     if (p->count<p->required) return 1;
-    for (i=0;i<p->count;i++) sorted[i]=p->intervals[i];
-    for (i=0;i<p->count;i++) for(j=i+1;j<p->count;j++)
-        if(sorted[j]<sorted[i]) {swap=sorted[i];sorted[i]=sorted[j];sorted[j]=swap;}
-    median=sorted[p->count/2u];largest=0;
+    median=window_median(p,sorted);largest=0;
     for(i=0;i<p->count;i++) {
         uint32_t difference=sorted[i]>median ? sorted[i]-median : median-sorted[i];
         if(difference>largest)largest=difference;
     }
-    /* 最近窗口每个间隔都需在中位周期的20%内；不是只看数值是否在量程内。 */
-    if(largest*100u>median*20u) {p->reason=BIO_V2_UNSTABLE;return 1;}
+    /* 最近窗口每个间隔都需在中位周期的容差内（首次锁定20%，已有效的心搏按HEART_TOLERANCE维持）；不是只看数值是否在量程内。 */
+    if(largest*100u>median*tolerance) {p->reason=BIO_V2_UNSTABLE;return 1;}
     p->candidate_rate=(60000u+median/2u)/median;p->reason=0;return 1;
 }
 static float filter_channel(Channel *c,int32_t raw,uint8_t respiration)
```

**与 R88 原型的差别（PI 离线定稿时改的，事实）**：
- R88 的 C2 原型是“无条件 ±30%”。在 40 个白噪声种子（2000 码，各 180 s）上，它的 HR 误报有效率均值 1.19%，10 个种子超过 2%，R83 门槛中的种子 5 达到 5.8%，**不合格**。逐项拆分后确认：误报全部来自 ±30%，漏检桥接本身与 C1 完全相同。
- 定稿改为**滞回**：首次锁定仍按 ±20%，只有上一判定有效时才按 ±30% 维持。40 个种子的均值降到 0.18%，最大 2.13%（种子 32，不在 R83 的种子 1–6 中）；C1 为 0.08%、最大 1.01%。
- 原型里锚点超过 2 s 就过期，心率低于约 60 时漏检一拍桥接不上。定稿让可桥接时锚点最长等 4 s，并规定不连续桥接。

### 2.2 PI 离线门槛结果（已完成，事实）
1. **主机用例**：在 C2 源上跑 `run_host.py` 既有 27 例、R83 的 19 例 C1 用例，以及附录 A 的 11 例 C2 用例，共 **57/57 PASS**。C1 源在 C2 用例上有 6 例失败（漏检 5 例、早搏 1 例），这符合预期，说明这些用例确实能区分 C1 和 C2。

   | C2 用例 | C1 | C2 |
   |---|---|---|
   | 每 6 拍漏 1 拍，HR 40/50/60/75/100（20 s 后有效率） | 均 0% | 均 100%，数值准确 |
   | 呼吸性窦律 ±10% / ±15%，HR 65 | 100% / 83.9% | 100% / 100%，61–72 |
   | 每 10 拍一次早搏加代偿，HR 60 | 37.0% | 100%，恒为 60 |
   | HR 120 突降到 60：旧值最长残留 | 1.0 s | 2.0 s（门槛 ≤2.5 s） |
   | HR 60 突升到 120：旧值最长残留 | 0.01 s | 0.01 s |
   | 停搏：最后一拍后 HR 仍有效的时长 | 2.0 s | **4.0 s**（门槛 ≤4.3 s） |
2. **真人录制重放**（把真实 C 代码编进夹具，跳过滤波，直接喂录到的滤波 ECG；脚本 `node-b/build/r83-analysis/r89/`，git 忽略）：

   | 数据 | C1 | C2 |
   |---|---|---|
   | P2 胸部 R87，16:42–16:47:51 | 46.9% | **65.8%** |
   | 踝部 R83 | 36.0% | 50.3% |
   | 腕部 R85 | 0.2% | 2.3% |
   | 模拟器 R83 | 87.0%，HR 60 | 87.0%，HR 60 |
   | 导联开路 R83 / 白噪声 | 0% / 0% | 0% / 0% |

   - P2 各分钟（C1→C2）：42 分 38.5→63.2%，43 分 45.1→51.2%，44 分 70.8→77.8%，45 分 44.9→84.8%，46 分 42.5→67.7%，47 分 37.7→46.9%。
   - **与 A 的 PR 一致性**（逐秒配对，PR 取 ±1 s 内最近值）：C1 147/188（78%）在 ±10% 内，C2 194/246（79%）；绝对差中位数都是 3 bpm。C2 有效秒数多了，但一致率没有下降。
   - C1 重放 47% 而板上实发 63%，差异来自 MQTT 缺段（R88 §2.4）。**推断**：C2 上板后 P2 有效率可能在 75–85%，需要 S5 验证。
3. **已知的行为变化**（写入回执，供结项口径引用）：
   - 信号消失后，HR 最迟 4 s 失效（C1 为 2 s），仍在实时数据 5 s 有效期内。导联开路会因削顶立即失效，不受影响；
   - 心率突然减半时，旧值最多残留约 2 s；
   - 噪声误报略增（均值 0.08%→0.18%）；
   - RESP 路径的容差仍为 20%，不桥接；既有 6 例呼吸用例全部通过。

### 2.3 Codex 实现要求
1. **冻结源码不动**，延续 R78/R80/R83 的构建副本注入。
2. **新增 `--algo-c2`**（要求同时给出 `--algo-c1`）：在 C1 注入之后，用 `replace_once` 把副本变成 §2.1 的结果。注入后 `bio_v2.c` 的 SHA-256 必须等于 `dcaba6fe…`；若因行尾不同而不等，回执中写明，并给出统一成 LF 后的 SHA。
3. **主机测试**：在 `node-b/firmware/biov2/tests/run_host.py` 中加 `--c2-cases`，代码与附录 A 等价。用 C2 副本运行 `--c1-cases --c2-cases`，必须 57/57，C2 用例的数值与 §2.2 表一致；再用 C1 副本运行同样参数，记录失败的 6 例。
4. **扩充 `node-b/tests/test_build_b4_diag_reason.py`**：`--algo-c2` 锚点唯一；不带 `--algo-c1` 时报错；注入结果的 SHA 符合第 2 条。
5. **构建门槛**（任一项不满足就 STOP，不下载）：
   - 冻结源码校验通过；
   - 复现 R6 `f2276540…`、R78 `24612613…`、R80 v2 `e9f34d78…`、R83 C1 `1c28707f…`，四者都逐字节一致；
   - C2 参数为 `--candidate-r6 --diag-reason --diag-cap --algo-c1 --algo-c2`，产物命名 `R89_C2_NODE_B.bin`；不超过 49,152 B，0 错误 0 警告；
   - 记录 BIN/AXF/MAP 的 SHA 和资源用量，并与 C1 对比；
   - 用封存的 R83 写后整片 `a40ad763…` 计算 C2 写后整片的预期 SHA。
6. **安装器**：新建 scope，仿照 R83，绑定本卡 SHA、写前应用区 `1c28707f…`（40,420 B）、写前整片 `a40ad763…`、C2 的 SHA 和字节数、扇区 [0,1,2]、1 次会话、不重试。
7. **录制**：沿用 R85 录制器，不修改，只改运行名前缀（`r89sim-<UTC>-node-ab.jsonl`、`r89human-<UTC>-node-ab.jsonl`）。提交前复跑它的 3 项模拟用例，并用 `grep` 确认没有 publish。

## 3. 现场段（须先有“放行 R89 写入”）
安全前提同 R74 §1：整条导电链不接市电，GT 用充电宝，电脑用电池，有专人看护。

**S0–S2 写入**（只给 B 上电，接模拟器，不接触人体）：同 R83。写前整片读两次，必须一致且等于 `a40ad763…`；写入 sector0–2 一次；写后整片等于 §2.3 第 5 条的预期，身份、options、sector3–11 不变；按标准流程 Reset/Go，然后 Close，物理拔掉 J-Link，再给 B 断电。

**S3 模拟器 ECG 验收**：
1. 至少提前 5 分钟通知 PI，PI 开始录 WSS；Codex 启动第一次只读录制（`r89sim`）。
2. 按 GT → B → C 上电，A、D、E 保持断电。模拟器 ECG 模式，接线 R→RA、L→LA、F→RL。
3. 60 s 内 HR 为 60，控件 20 显示 `H0`，控件 17 可读。保持 2 分钟，并报开始时刻。
4. 断开导联 30 s，H 不为 0；接回后 60 s 内恢复 H0、HR 60。报断开和接回的时刻。

**S4 RESP 定标**（(c)，不接触人体）：
1. B 断电，接线改为 R→RA、L→LL、F→RL，LA 空着（同 R81 §6）。模拟器切到呼吸模式，呼吸率 20 bpm，窒息 0 s。给 B 上电。
2. 依次设置下列幅度，每档保持 **90 s**，报每档的起始时刻（精确到秒）。在每档最后 10 s 记录屏上 RR 和控件 20 的 R 值：
   1. 1.5R；
   2. 1.0R；
   3. 0.5R；
   4. 1.0R，呼吸率改为 12 bpm；
   5. 如果模拟器能关闭呼吸输出，或幅度能设为 0，则做 60 s 作为噪声底；否则此档记 NOT_RUN。
3. 拍一张模拟器设置屏（含型号和基础阻抗，如果有显示）。只拍设备，不拍人。
4. 做完后，按 C、B、GT 的顺序断电。停止 `r89sim` 录制，计算 SHA。

**S5 P2 真人复测**（(b) 验收）：
1. 安全前提同上，另加志愿者知情同意、无植入设备，以及 R87 §0 的隐私同意（不拍胸部照片）。
2. Codex 启动第二次只读录制（`r89human`）。按 GT → A、B → C 上电，D、E 保持断电。
3. **先确认 A、B 在云端 ONLINE，再接触人体**（纠正 R87 的流程偏差）：先戴左手 SpO₂ 指夹，A 屏有读数后，再按 R87 §1 贴 P2。分别报戴指夹和贴好电极的时刻。
4. 流程同 R87 §2：静坐 1 分钟，屏气 10 s，正常呼吸 2 分钟，屏气 10 s，节拍器 12 次/分做 1 分钟，屏气 10 s。**每个标记都报开始时刻（精确到秒）**。另在正常呼吸段由安全员数一次 60 s 桡动脉脉搏，并记下同期屏上 HR。
5. 先摘电极和指夹，再依次断开 C、A、B、GT。停止录制，计算 SHA。

**S6 交付**：两份录制都放到 `/home/mmpm-deploy/r83-capture/`（属主 mmpm-deploy，权限 0600）。PI 用 scp 取回，核对 SHA 后通知 Codex 删除服务器副本。原件存受限 EFS。录制前后各做一次 `mmpm-control status`。

## 4. 判定
- **离线段**：§2.3 第 2–5 条全部满足。
- **安装**：PASS 条件同 R83，任一核对不一致即 FAIL。
- **模拟器 ECG**：S3 第 3、4 项都满足。
- **RESP 定标**：本卡**只采数据**。录制覆盖 S4 各档并有时刻，即为 PASS。换算和真人 ΔR 的判读由 PI 在 R90 中给出。
- **真人 HR（C2 目标）**：
  - 从贴好电极后第一次有效算起，到最后一个屏气标记结束，B 的 HR 有效占比至少 80%；
  - 与 A 的 PR 配对（±1 s），至少 80% 在 ±10% 内；
  - 人工脉搏对照与屏上 HR 相差不超过 10%。
- **真人 RR**：只采数据，不判定。
- **MQTT 录制**：覆盖对应步骤全程，含 NODE-A、NODE-B 的全部批次（包括 INVALID），没有任何 publish，后端服务状态不受影响。

## 5. 停止条件
- **离线**：§2.3 任一门槛失败，停止并回执，不进入现场。
- **安装和目标板**：写前核对不符；出现 HALT/ROM，身份或 Flash 漂移；安装后屏不亮、反复复位，或模拟器下 HR、波形异常。立即停止，保存原件，不重试，不额外执行 Go/Reset。只有已获回退授权时，才能恢复 C1 一次。
- **真人**：有任何不适、发现接入了市电、冒烟、发热或异味时，先摘电极和指夹，再断电，然后上报。
- **录制**：脚本报错或后端异常时，停止录制，不重试，不碰后端。
- **设备**：GT 红灯常亮或 C 反复复位时，摘电极、断电、上报。

## 6. 回执（新分支 `codex/r89-b-c2`，基于含本卡的提交；文件 `R89-B-C2-RECEIPT-20261118.md`）
- 卡片 SHA；代码提交；测试命令和结果，C2 用例逐例给出数值，另列 C1 副本的 6 例失败。
- 四份基线的复现结果；C2 产物的 SHA 和资源用量（与 C1 对比）；写后整片的预期与实测；身份和 options 核对；原生动作计数和退出码。
- S3、S4 每一步的时刻和屏上读数；S4 的模拟器设置照片清单。
- S5 时间线：上电、ONLINE、戴指夹、贴电极、各标记、摘除、断电，以及人工脉搏对照数值。
- 两份录制的行数（按 A、B 分开）、起止时刻、SHA-256、交付位置；`mmpm-control status` 结果。
- “放行 R89 写入”和“同意 R89 回退一次”是否获得、回退是否执行。
- 每项按 PASS / FAIL / NOT_RUN / UNKNOWN 填写。凭据、热点名称、志愿者身份都不写入回执。

## 附录 A · `run_host.py` 的 `--c2-cases` 用例（与 PI 离线版等价）
放在 R83 的 `if args.c1_cases:` 块之后、历史回放之前；参数解析加 `parser.add_argument('--c2-cases',action='store_true')`。

```python
if args.c2_cases:
    import bisect
    def beat_feed(beats,rpm=15):
        # 按给定心搏时刻合成 QRS/T，幅度与 sample() 相同；beats 为秒
        def feed(t):
            i=bisect.bisect_left(beats,t-.5);ecg=200000.0
            for b in beats[i:i+4]:
                ph=t-b;ecg+=10000*math.exp(-.5*(ph/.012)**2)+1800*math.exp(-.5*((ph-.23)/.055)**2)
            return int(round(ecg)),int(round(640000+1200*math.sin(2*math.pi*rpm/60*t)))
        return feed
    def regular(hr,seconds,start=.3):
        n=int(seconds*hr/60)+2;return [start+k*60/hr for k in range(n)]
    def track(seconds,beats):
        # 逐样本记录 (时刻, 有效HR或0)
        lib.BioV2_Init(1000);rows=[]
        feed=beat_feed(beats)
        for i in range(int(seconds*250)):
            t=i/250;h,r=feed(t);lib.BioV2_Process(h,r,1000+i*4,i+1,0)
            rows.append((t,d.hr if d.hr_valid else 0))
        return rows
    def summary(name,rows,after,ok_value,need_pct):
        part=[v for t,v in rows if t>=after];valid=[v for v in part if v]
        pct=100*len(valid)/len(part)
        res={'case':name,'hr_valid_pct':round(pct,1),'hr_min':min(valid) if valid else 0,'hr_max':max(valid) if valid else 0,
             'pass':pct>=need_pct and all(ok_value(v) for v in valid)}
        results.append(res);return res
    for hr in (40,50,60,75,100):
        b=regular(hr,120);b=[x for k,x in enumerate(b) if k%6!=5]
        summary(f'c2_missed_every_6th_hr_{hr}',track(120,b),20,lambda v,hr=hr:abs(v-hr)<=2,90)
    for amp in (.10,.15):
        b=[.3]
        while b[-1]<122:b.append(b[-1]+60/65*(1+amp*math.sin(2*math.pi*.25*b[-1])))
        summary(f'c2_rsa_{int(amp*100)}pct_hr_65',track(120,b),20,lambda v:abs(v-65)<=10,80)
    b=[.3]
    while b[-1]<122:
        k=len(b);b.append(b[-1]+(.7 if k%10==0 else 1.3 if k%10==1 else 1.0))
    summary('c2_ectopic_every_10_hr_60',track(120,b),20,lambda v:abs(v-60)<=3,50)
    for a,c in ((120,60),(60,120)):
        b=regular(a,40);b=[x for x in b if x<40];b+=[b[-1]+60/c*(k+1) for k in range(int(40*c/60)+2)]
        switch=max(x for x in b if x<40);rows=track(80,b)  # switch 为旧节律最后一拍
        stale=[t-switch for t,v in rows if t>switch and v and abs(v-a)<=10]
        fin=[v for t,v in rows if t>=75]
        res={'case':f'c2_rate_{a}_to_{c}','stale_old_rate_s':round(max(stale),3) if stale else 0,
             'final_valid_pct':round(100*sum(1 for v in fin if v)/len(fin),1),'final':fin[-1],
             'pass':(max(stale) if stale else 0)<=2.5 and fin[-1] and abs(fin[-1]-c)<=2}
        results.append(res)
    b=[x for x in regular(60,40) if x<40]
    rows=track(60,b);last=b[-1]
    held=[t-last for t,v in rows if t>last and v]
    results.append({'case':'c2_asystole_after_60','invalid_after_last_beat_s':round(max(held),3) if held else 0,
                    'held_values':sorted(set(v for t,v in rows if t>last and v)),
                    'pass':(max(held) if held else 0)<=4.3})
```
