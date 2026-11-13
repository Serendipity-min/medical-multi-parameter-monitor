# 新增 RR15 回放工具上下文审查

审查对象为固定基线 `b9b17a7657f101e8901a24115da8538becc420d0` 的 `node-b/tools/b5_rr15_causal_replay.py`（以下简称 R）。本文件是上下文与未证实假设记录，不是根因裁定、补丁验收或实板许可。只阅读仓库源码，未连接目标、加载目标 SDK、访问串口/网络/云端、运行安全扫描或读取私有 ADC 原码。

## 索引与调用链

`main` → `sealed_raw_frames`（逐块完整性及双副本重建）→ `compile_host`（本机 GCC 生成纯算法共享库）→ `replay`（ctypes 调用 BioV2）→ `mains_projection`（事件前一秒 CH2 的50Hz投影），最后独占创建JSON回执。来源 R L190–236。

真实采集来源：`ads1292.c` ISR → `EcgQueuedFrame` → 单生产者/消费者队列 → `hr_page.c:FrameFeed` → `BioV2_Process`；G3 worker另行读取队列槽形成5692字节非暂停块。来源 `ads1292.c` L175–210、L303–310，`ecg_frame_queue.h` L5–13，`hr_page.c` L286–302，`b5_g3_devices.py` L171–194。

## 跨函数约束与覆盖边界

| 约束 | 已建立的源码依据 | 仍需本轮实证/外部绑定 |
|---|---|---|
| CH2=ECG、CH1=RESP，24位二补码 | R L84–87；`hr_page.c` L295–302；`ads1292.c` L314–324 | 实际制品与该源文件/头文件的封存SHA；源码映射本身一致 |
| 24字节帧布局 | `ecg_frame_queue.h` L7–13：9 bytes、flags、对齐、seq、IRQ cycles、IRQ ms；R L67–87采用seq12、ms20 | IRQ cycles offset16未返回或统计（R L84–87）；padding10–11不应解释为信号 |
| status和双副本规则与冻结重建一致 | R L68–83；`b5_g3_contract.py` L246–263 | 被status掩码排除帧未计数；多版本单次冲突与双重复冲突没有分项统计 |
| 记录时间来自IRQ入口 | `ads1292.c` L181–189，读取函数转交IRQ ms于L309 | R未检查/统计seq步长、IRQ ms步长、IRQ cycles步长、flags分布（R L84–93） |
| 不把读者缺口拼成连续输入 | C `BioV2_Process`在flags、序号不连续或>100ms时断段，`bio_v2.c` L198–205 | 未单独盘点重建丢样；新工具不含冻结重建的high-water boot/seq restart拒止（对照`b5_g3_review.py` L32–49） |
| 同算法C回放 | R L120–143、L153–154调用纯C接口；`bio_v2.h` L20–35 | 本机浮点/编译器与ARM制品不是自动等价证明；相同序号处诊断应实证比较 |
| 原始时戳和源flags传递 | R L153–154原值传入uint32/uint8；flags bit0含义见`ecg_frame_queue.h` L9 | 不能把source flags解释为Lead-Off；status未遮盖的其他位尚需统计；未推断物理导联是否真正脱落 |
| 从原始真实采样初始化 | R L144重置算法，L145预留45s回放预热 | 原MCU此前滤波/周期状态未知；45s不是原云T0，且R的cutoff和持续时间使用非回绕Python差（L145、L155、L175） |
| 云评价窗和六个事件对齐 | R L185–186明确不等同冻结T0 | 没有读diagnostics/T0/事件索引的代码；逐序号与600个SWD诊断及六簇的对齐由本轮上层分析建立 |
| 250Hz/50Hz完整性 | C头文件声明250Hz，`bio_v2.h` L5–7；冻结CAN布局含每5序号RESP点，`b5_g3_contract.py` L261–262 | R只回放两个250Hz ADC通道，没有读取CAN 50Hz记录或检查50Hz下采样连续性 |
| 结果留在受限EFS | R L202–203仅拒绝输出在仓库下；L228–231独占建JSON | 指定EFS根与Windows加密属性检查：**nothing found**。对照既有`b4_recovery.protected` L33–49可见该约束原本在其他工具负责 |

---

## `digest`（R L45–46）

**Purpose / Inputs & Assumptions:** 对调用方提供的内存字节计算SHA256；输入字节已由负责文件读取的调用者确定。

**Outputs & Effects:** 返回十六进制字符串，无外部访问。

**Block-by-Block / Dependencies:** 单一hashlib调用；用于块、完整C源码以及后续回执的身份记录（R L63、L130）。哈希一致证明字节身份，不能单独证明给定expected哈希的来源可信。

**Open Questions:** expected哈希是否来自已封存的本轮RR15/ECG60真实证据索引，须由调用方在实际运行前核实。

---

## `sealed_raw_frames`（R L49–93）

**Purpose:** 从重复SWD队列快照重建有至少两份完全相同原件的ADC帧，保留seq、IRQ ms、CH2/CH1、flags。

**Inputs & Assumptions:** window路径和完整blocks.bin哈希为调用者选择；idx及binary存在检查在L53–54。默认信任JSON行结构及row['data']字段类型，结构错误自然抛异常（L59–64）。目录在受限EFS、idx来源、采集ABI/地址绑定成立的检查：**nothing found**。

**Outputs & Effects:** 顺序读取两个文件，内存累计Counter，返回按数值seq排序的五元组和块/稳定/未认证数；不写原件（L55–93）。

**Block-by-Block:**

- L58–76按索引顺序读取固定5692字节、验证块长/offset/SHA、拒止额外尾字节，再验证全部二进制SHA。保障整个读取的原件身份，不能用某几块代替完整文件。
- L66–71只把nonzero seq且status掩码合格的24字节帧纳入版本计数，条件等同冻结`decode_block`（`b5_g3_contract.py` L258–260）及ISR status条件（`ads1292.c` L205–206）。其他status样本被跳过，没有拒止计数。
- L78–87只接受恰有一个版本重复≥2次；单重复版本附带一次性其他版本仍会被接受，和冻结`Versions.stable`一致（`b5_g3_contract.py` L246–252）。f[6:9]/f[3:6]正确解成有符号24位；seq/IRQ ms/flags仍是原值。
- L88–93按seq数值排序，拒止空流。跨复位/seq回绕、IRQ cycles异常和缺口统计没有在排序前建立。冻结重建还对每块high-water值递增作拒止（`b5_g3_review.py` L38–41）；新工具没有此步骤。

**Cross-Function Dependencies:** `replay`把返回列表直接作为唯一算法输入；C会根据flags/序号缺口断段，未被重建的帧不可能自然恢复。`mains_projection`又以seq推断均匀250Hz。对于缺口，C断段与独立频谱的处理并不等价。

**Open Questions:** 每个实际流是否单一启动epoch？哪些seq缺失/冲突？flags是否全0？IRQ cycles与ms是否支持250Hz且没有溢出/异常？需在解释回放前回答。

---

## `mains_projection`（R L96–117）

**Purpose / Inputs & Assumptions:** 独立估计事件前250个seq范围内CH2的50Hz线投影；默认rate250，按整数seq取样（L98–100）。

**Outputs & Effects:** 返回原码RMS、单频投影能量比例、峰值/RMS与样本数；不是BioV2内部line_power/raw_power定义，不是阻抗或电压标定（L113–117）。无文件写入。

**Block-by-Block:**

- L98–102最多容许缺失5%样本，只在不足95%时报“INSUFFICIENT_CONTIGUOUS_SOURCE”。这没有建立“所有样本连续”的条件。
- L103–116去均值后使用`enumerate(ac)`的密集i而非原始seq偏移/IRQ时间相位。缺口被压缩时，50Hz相位基础变化；该结果不能在未核实无缺口时当连续信号频谱证明。
- DC时提前返回；非DC时比例被限制到1。仅50Hz，未分析100Hz、低频呼吸相位、前后/左右对照或QRS形态。

**Dependencies / Open Questions:** `replay`只对每episode开始前一秒调用，不能独自区分真实QRS、工频和呼吸耦合。真实流的无缺口条件、事件后对照、同类正例形态及RESP相位证据尚待上层分析。

---

## `compile_host`（R L120–131）

**Purpose / Inputs & Assumptions:** 用指定本机gcc将单个纯C算法文件编为共享库。source及compiler由CLI提供，源码引入的头文件及编译器来源需调用者冻结。

**Outputs & Effects:** 运行一次本机编译子进程，180s超时，生成指定输出库；失败抛带截断stderr的异常，成功回传source SHA和exit0（L121–131）。不是MCU构建，不触发目标工具。

**Block-by-Block / Dependencies:** C99/O2/Wall/Wextra/Werror/ffp-contract=off/shared，非Windows追加fPIC，最后链接lm（L121–127）。源码SHA在编译后计算（L130）。完整command、stdout/stderr、compiler二进制/版本SHA、引用bio_v2.h SHA、生成库SHA的记录：**nothing found**。

**Open Questions:** 生成库是否来自本轮精确baseline C/header、编译器版本是什么、120B C结构各offsetof是否与ctypes一致？Windows加载后临时库的寿命/清理路径是否实际完成？后者代码没有显式unload，不能仅凭静态阅读认定结果。

---

## `replay`（R L134–187）

**Purpose:** 对确定的原始帧按原值调用C算法，统计45s回放预热之后的逐样本HR/RR有效性和HR episode。

**Inputs & Assumptions:** libpath应是刚编译的本机BioV2库；rows非空由L89–90建立。`C.CDLL`会加载它，符号/参数原型在L135–143绑定。没有目标SDK导入，但这本身不是任意libpath授权器。

**Outputs & Effects:** 修改共享库的全局算法状态，返回汇总字典和前24episode；没有完整逐帧回放轨迹或IRQ cycles输出（L177–186）。

**Block-by-Block:**

- L135–143绑定两函数参数，读`g_bio_v2`，只检查Python结构总长120。固定宽度字段顺序与`bio_v2.h` L20–27吻合；C侧sizeof/offsetof及tag/abi_version值的显式核验：**nothing found**。
- L144–155在捕获起点重新初始化，不恢复MCU先前filter/period状态；所有帧均喂C，只是前45s不计入结果。L145/L155未使用uint32回绕比较。原始真实云T0不由此建立，L185–186已明确披露。
- L153–172原样传CH2/CH1、IRQ ms、seq、flags。C会处理缺口/flags/削顶并持续记录原码与时间（`bio_v2.c` L198–231）；它并不验证主机帧的真实性。
- L162–175把HR有效片段和序号连续性组合成episode，保留范围与最后`hr_last_cycle_ms`。此字段实际是最后已接受峰时间戳：`accept_cycle`将`last_good=at`（C L110），`publish`将它赋给diagnostic（C L194）；**不是周期时长**。周期证据须从前后accepted峰时间差或内部intervals另行建立，不能把该字段直接当IBI。
- L175持续时间使用Python差再加名义4ms；IRQ ms抖动、回绕、seq缺口和确切episode结束点的定义需在实际报告注明。

**Cross-Function Dependencies:** 实机`FrameFeed`传入IRQ时间，但UI会以真实当前TimeBase调用`BioV2_GetHeart/GetResp`（`hr_page.c` L398–404）；Getter调用`BioV2_Tick`并可能触发expire/断段（C L233–249）。新工具只调Process，没有消费时刻/Getter/Tick调度回放。这是诊断逐点比对时的已知语义边界，不能把计数不同立即解释为算法根因。

**Open Questions:** 主机baseline逐seq的rate/reason/候选/accepted/cycle时间与原SWD诊断匹配多少？哪些差异来自初态、缺口、Tick调度或浮点？六个现场误报是否在同seq范围得到同机制重现？目前源码本身不回答。

---

## `main`（R L190–236）

**Purpose / Inputs & Assumptions:** CLI接受两个窗口路径与完整blocks SHA、baseline/candidate C、gcc、输出路径；调用者负责选择真实数据和不可泄漏的受限路径（L191–208）。

**Outputs & Effects:** 读取原件、生成临时本机库、加载并回放、独占写结果JSON，打印状态/计数及私有路径（L209–235）。没有设备/串口/云端操作代码；真实外部交互是本机GCC子进程和新host共享库加载。

**Block-by-Block / Dependencies:**

- L201–203只排除仓库内结果；输入/EFS加密属性/指定私有根的准入检查：**nothing found**。L228会递归创建任意指定外部目录。调用方须保证private输出确在受限EFS。
- L209使用OS默认临时目录存算法host库，未选择EFS；源码没有把ADC帧写到该临时目录（ADC只在内存与来源EFS中），不应误称“已经把原始ADC泄漏到temp”。制品SHA及清理完成状态仍未留回执。
- L211–219分别重置baseline/candidate并跑同两流，未内置ECG90/120、其他噪声或独立RR holdout；L223–227只是限制说明字符串，不是数据集资格门。
- L229独占创建输出防止覆盖既有回执；异常没有统一私有错误回执或进程exit账本，依赖上层调用方保存真实stderr/返回码。

**Open Questions:** 正例/噪声/留出集合是否真实独立、有正确标签与冻结SHA，且在候选门槛决定之前预登记？若缺样本，是否保持ROOT_CAUSE_UNRESOLVED/不做固件候选？这是本轮上层裁决，不由该工具的成功退出0表示已满足。

## 本轮后续验证应保持的区别

1. 字节SHA/队列解码正确，与物理源类别/QRS确证是不同结论。
2. C回放成功，与原设备同初态/同浮点/同Tick调度及同T0不是同一结论。
3. episode重现，与工频/呼吸耦合的物理因果解释仍须独立证据。
4. 单个RR负例消失，与ECG60/90/120、其他噪声及独立holdout非回归门全部满足不是同一结论。

以上均是源码可见的前置条件或待验证问题，不给出算法修改方案或根因裁定。
