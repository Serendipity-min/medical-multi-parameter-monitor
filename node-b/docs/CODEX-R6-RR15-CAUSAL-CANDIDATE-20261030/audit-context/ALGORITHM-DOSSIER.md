# BioV2 心率调用链与离线语料上下文

基线：`b9b17a7657f101e8901a24115da8538becc420d0`。这是 context-building 记录，不是根因裁定或候选阈值建议。仅查阅源码、有限原件元数据及封存哈希；未连接硬件/串口/云端、未回放独立留出、未修改算法。

## 同算法来源与公开 ABI

- 当前算法 C SHA256 为 `3adca55cb1eb1fa3ed8e4148f837287d0454bcc2c08ae77a8f73deb1dac156a7`。与已安装 B41012 同一次构建 `b4-arm-20261030T062335164483Z/firmware/HARDWARE/bio_v2.c` 逐字节一致，构建 `receipt.json.bio_source_sha256` 亦匹配；该构建原件为本机只读核对，不把构建通过冒称设备根因证据。
- 公共接口是250Hz、CH2 ECG/CH1 RESP原始整数码，Process收原始 sample_ms、sequence、flags；`BioV2Diag`固定字段顺序，ABI版本2。时间/序号/raw保留是接口约束，valid仅为工程资格。[bio_v2.h:5-35](../../../firmware/biov2/实验固件/HARDWARE/bio_v2.h)
- ABI检查不能只看Python结构大小：应同时绑定实际 C/header SHA及字段offset。原Host回归和channel isolation均检查120B；C源码`BioV2_Init`写tag `0x324f4942`、abi_version2。[bio_v2.c:87-92](../../../firmware/biov2/实验固件/HARDWARE/bio_v2.c)

## 来源和时基调用链

1. ADS DRDY ISR记录 `irq_sequence`、DWT `irq_cycles`、TimeBase `irq_ms`；IRQ间隙超过6ms置flag，SPI或status失败不入队；队满丢新帧并计数，保留序号缺口。[ads1292.c:175-212](../../../firmware/biov2/实验固件/HARDWARE/ads1292.c)
2. `ADS1292_ReadFrame`返回原9字节，发布同一帧的IRQ ms/sequence/flags，未用主机采样时间代替。[ads1292.c:303-310](../../../firmware/biov2/实验固件/HARDWARE/ads1292.c)
3. `hr_page.FrameFeed`将CH1三字节解为RESP，CH2解为ECG，直接调用同一 `BioV2_Process(ecg,resp,sampleMs,sequence,flags)`，不先经旧滤波/保持器。[hr_page.c:286-302](../../../firmware/biov2/实验固件/HARDWARE/hr_page.c)
4. getter另以当前 `TimeBase_GetMs()`调用Tick，可能在没有新帧时清资格。仅逐帧Process的回放没有复现这些实际UI/CAN getter时刻；若与档案SWD诊断不符，这是必须核对的条件，不能立即改阈值。[hr_page.c:398-404](../../../firmware/biov2/实验固件/HARDWARE/hr_page.c)、[bio_v2.c:233-249](../../../firmware/biov2/实验固件/HARDWARE/bio_v2.c)

## 心率内部语义

| 函数/数据 | 保证及依赖 |
|---|---|
| configure | 清通道状态；250Hz系数：50/100Hz双notch，心率高通+低通；心率合法间隔273..2000ms、timeout4000ms；呼吸1500..10000ms/timeout12000ms。[C:50-63] |
| accept_input | 单路达到±8304721码时重置本路资格，clip恢复重新预热；不把另一通道clip当作本通道故障。[C:64-78] |
| filter_channel | 原码DC估计后滤波；raw_power与line_power的EMA系数.001，band_power为.004；line_power来自被notch去掉部分，**不是独立傅里叶50Hz占比**。[C:127-141] |
| heartbeat | 对心率带通输出绝对值找峰；入口门为max(30codes,2.5倍带内RMS)，离峰条件为半门或>200ms；计候选后需宽12..160ms、peak>=1.05gate及5s预热，再交周期资格。[C:143-160] |
| accept_cycle | 第一个峰只锚定；过短不更新anchor；合法间隔会更新last_good并入最近最多5间隔，至少3间隔；所有间隔须在中位数20%内，rate按中位数四舍五入。[C:99-126] |
| expire | 间隔窗口过时或锚定太久时清所有旧间隔与资格；uint32差值处理ms wrap。[C:93-98] |
| Process质量分支 | 对心率仅在raw_power>10000且line_power>95%raw_power时清峰资格；呼吸另有band/clean比例门。不同通道路径不能混当相同质量门。[C:198-226] |
| publish | reason合并clip/warmup/mains/no_cycles，reason==0才valid、否则rate置0；归一化line/raw上限1；公开RMS为滤波band RMS。[C:178-197] |

以上 `[C:n]` 均指 `node-b/firmware/biov2/实验固件/HARDWARE/bio_v2.c` 的基线行号。

**关键字段：`hr_last_cycle_ms`是最后一次合法峰的绝对设备毫秒时刻 `Periods.last_good`，不是周期时长。** `accept_cycle`在C:110写last_good=at，publish在C:194复制它；真正周期是相邻有效峰时刻差及内部intervals。不得把回放工具同名字段直接解释成心搏间隔。

计数语义也不同：`hr_candidates`在峰退出时增加，不代表已通过宽/幅门；`hr_accepted`在accept_cycle返回1时增加，可能仍不足3个周期或UNSTABLE。`hr_fresh_intervals`是目前保留间隔数，非独立QRS真值。[C:114-125,154-158,194]

## 已有可复用离线回归

- `node-b/firmware/biov2/tests/run_host.py`：ECG40/60/90/120/180，RESP6/12/15/24/30/40，零/DC、1/8/25/50/100Hz非QRS正弦、适中工频叠加QRS、固定seed白噪声、u32时间wrap、过期/孤峰/恢复、flags/缺号/clip/getter超时。源码中合成QRS为Gaussian QRS/P/T，不是真实患者标签。ECG通过门主要是最终有效和±2bpm，**没有预登记所有稳态样本有效比例**。[run_host.py:38-94](../../../firmware/biov2/tests/run_host.py)
- `node-b/firmware/biov2/tests/run_channel_isolation.py`：原共同失效复现、两轨单路clip与恢复、健康通道逐样本不变、clip边界、共同sequence/flags/time失败、getter过期、wrap、120B ABI；当前C与旧before-isolation C同时编译。[run_channel_isolation.py:44-86](../../../firmware/biov2/tests/run_channel_isolation.py)
- `node-b/tests/run_pretest.py`：100/101ms超时边界、flags/缺号/时间反转、时间+序号同时wrap、Init清资格、预热及3间隔门，可选已封存旧8412帧表征，不把无参考历史输出当准确度。[run_pretest.py:84-152](../../../tests/run_pretest.py)
- 三个入口都是CPU/Host；前两个需要独立新 `NODE_B_TEST_OUT`，编译日志和结果不可覆盖。普通合成测试未预置独立holdout，不能将它们的既有通过称为本次候选的未知留出成绩。[run_host.py:13-25](../../../firmware/biov2/tests/run_host.py)

## 真实语料位置、seal与建议用途

本机历史 ECG 原件根为 `E:/medical-monitor-node-b-field-private/field-r3`；结果/复制原件应仍保存在受限EFS，不提交波形。`matrix-ecg{60,90,120}-r3-{01,02}/receipt-private.json`六份均与已公开 [historical-receipt-index.json:47-79](../../../evidence/B-PREC-001/historical-receipt-index.json) SHA匹配。

CSV统一字段：`source_seq,device_ms,irq_cycles,status_raw,flags_raw,ch1_raw,ch2_raw,integrity`。每目录还留存 `running-slots-private.bin`、`chunks-private.jsonl`、`final-paused-ram-private.bin`、`export-summary-private.json`，可从封存槽重建并核对CSV，不应仅拿本次自算CSV SHA代替原件认证。历史ECG receipt没有直接顶层绑定CSV SHA，需完整导出/原slot链验证；现有analysis-summary含CSV SHA和source_record SHA，但该派生分析本身也须核验来源。

| 别名 | CSV帧数 | 本次只读计算CSV SHA256 | 预登记候选用途（尚未回放） |
|---|---:|---|---|
| matrix-ecg60-r3-01 | 23109 | a5160a4f4e12425e8cd396faeab821c8b781d88de55e3b782448ef61e17a4177 | 开发正例 |
| matrix-ecg60-r3-02 | 23096 | 437813bdc03e9eb27b09c25a9240d0bbff6757d3d06130760482b77d894fae9a | 独立留出，未做特征/回放 |
| matrix-ecg90-r3-01 | 23093 | 5d7d0a6f95c24eed9560b1864f53dd8553ac713a305d3349a4e2d49aa6f44b9e | 开发正例 |
| matrix-ecg90-r3-02 | 23096 | 5f46fd6a838c4e3ddbee38f2f32342b49b62ff5d19edea71ebe81826c0c024ad | 独立留出，未做特征/回放 |
| matrix-ecg120-r3-01 | 23105 | 95d2675bb8caf5cfe89b6595579e2bab743b6112a4cc891b1c6248941b629a9e | 开发正例 |
| matrix-ecg120-r3-02 | 23108 | 8f26c377700409b436738610c2a170db026872fc77e5f96a9e363c57d84edcfe | 独立留出，未做特征/回放 |

`capture-open-r3-01`仅2609帧，CSV SHA `6ef5fb3301f3f42ab6f5b4aa8be26f512f1b71b754db824bf30fd5e2095af070`；receipt匹配公开索引，但时长不足45s，且开放输入没有QRS真值，不能直接作为长期纯噪声合格负例。

独立历史RESP12/18/24的两次矩阵：同根 `resp-003/e3-matrix-r1/capture-{12,18,24}-r{1,2}`，各34333..34343帧。六份receipt均匹配公开historical-receipt-index，而且各CSV均匹配receipt.stable_raw_sha256；可作为不同呼吸工况的补充噪声/耦合候选，但不能仅凭RESP菜单就断定CH2没有真实QRS。`resp-003/e1-03`仅2593帧，不够45s长期回放。未对这些波形做本次特征或回放。

### 独立RR15留出（R5）

受限根 `E:/medical-monitor-node-b-precan-private/20261023/time-init-field-6cd64b90/owner-observed-RR15-R5-5bb61eef/joint`，不是本轮六事件R6窗口。负责人已要求留出到开发冻结之后；本任务仅seal验证，未做波形特征或算法回放。

- 工况site的SHA匹配authorized-once引用：RESP15bpm、1.5R、周期30bpm、apnea0，R RA/L LL/F RL/N，无人体；不是当前ECG接线。
- authorized-once所引用bundle SHA匹配；bundle中的B ELF、symbols、full、identity、options文件均匹配各自引用SHA。其B完整Flash为旧B40928 `ceebec5a…`，与当前B41012不同；**算法C相同性须随回放源码链核实，不以整片不同或相同反推。**
- 3561个5692B block全部offset连续、每block SHA匹配，无未索引尾字节。全片block文件20269212B，SHA `0351f74c6c71feaab98374fdb340c7d3c3cbde4acacc63abdbdcd629984a5b97`；index SHA `28dc9d6bdb007487f42f466998300bb0b5a2e5913b83984f353f70140e19c02e`；diagnostics SHA `fe1c9be7cd23ef94b497200ef78416478bbebf7bb8691c3ad8d2b37001bbf00d`。这些全文件SHA为本次输入pin，原公开manifest主要绑定正式/进程回执，不虚称它预先公布了这三个whole-file SHA。
- 私有正式报告、joint回执、supervisor回执均匹配 [R5 manifest:18-21](../../../evidence/B5-GEMINI-R5/RR15-WINDOW-01/manifest.json) 已公布SHA；原RR15正式NOT_PASS/3和采集0不改判。

## 必须留给根因阶段核实的假设

1. 三个峰资格周期是否来自真实QRS：**nothing found** in公开valid/速率字段本身；需要波形形态、峰宽/显著性、50/100Hz分量及RESP相位，不能以HR看似合理当真值。
2. host与目标浮点/编译器及初始化前史是否足以复现已存SWD诊断：本阶段未证明；应先对齐源序号和设备epoch，再讨论补丁。
3. 独立RR15/ECG留出不能参与选择阈值；当前只做文件/封存核对，没有观察它们本轮特征或回放结果。
4. 250Hz原始样本连续与50Hz后级节奏是采样/发布链性质，单靠BioV2合成率值正确不能证明；候选需保留原始IRQ时间、序号、状态位、flags及原ABI/判据并另验。
