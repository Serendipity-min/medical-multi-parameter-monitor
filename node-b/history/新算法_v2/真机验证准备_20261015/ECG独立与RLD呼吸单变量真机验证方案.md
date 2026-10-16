# 最新通道独立修复固件：ECG独立与RLD/呼吸单变量验证方案

日期：2026-10-15（Asia/Shanghai）。状态：**方案、最新正常候选身份与拟议配置差异已准备；本轮不连接硬件、不烧录、不采集。**

本轮用户补充：目前没有现成模拟设备，第二块F407与采集板同型号；源板拟用J-Link烧录后拔掉探头，以12V/1A直流适配器供电；模块电极插头为RA、LA、RL。因此，先完成软件信号源验证，并准备双F407的非人体DAC源方案。下述外部RLD/呼吸序列暂缓，不能拿软件样本或尚未校准的DAC输出冒充主动模拟器实测。详见同目录 `第二块F407自制ECG工程源方案.md`。

## 1. 目标与成功条件

先确认最新通道独立修复在真机上能够让ECG独立处理输入，再在同一非人体主动ECG源下逐项比较RLD缓冲、呼吸调制和呼吸解调的影响。保留完整原始帧、驱动统计、算法原因码及每次失败，不以显示平滑或出现量程内数字判定测准。

阶段分别评级：

- `ACQUISITION_INTEGRITY`：帧、时序、寄存器、导出完整性。
- `ECG_CHANNEL_INDEPENDENCE`：呼吸失效不导致ECG共同削顶失效或停止处理。
- `ECG_REFERENCE_VALIDATION`：仅在主动模拟源及已知输出核验完成时评估心率。
- `RLD_EFFECT`、`RESP_MOD_EFFECT`、`RESP_DEMOD_EFFECT`：同接线、同源、单变量对照；有效值变差也是真实结果。
- `RESP_RATE_ACCURACY`：本计划不验收；除非后续补齐已知阻抗输入，不能以ECG模拟器或呼吸波形起伏代替呼吸真值。

无已知源时可以得到质量观察，但必须标为 `REFERENCE_UNVERIFIED/ACCURACY_NOT_EVALUATED`；不能完成有效心率验收或唯一归因。只有被动假体/贴片位置不构成主动ECG信号源。

## 2. 当前冻结身份与软件准备边界

| 项目 | 身份 |
| --- | --- |
| 算法源 `bio_v2.c` | SHA-256 `3adca55cb1eb1fa3ed8e4148f837287d0454bcc2c08ae77a8f73deb1dac156a7` |
| 最新正常候选BIN | `438a8120f6df06ce219cdc30c0e5b697ac0e993f98d5a80521b10361536ae3ae`，25284 B |
| 最新正常候选ELF/AXF | `5a3fbbc13fe57a6b3a5fdaf6ead7f80320bff6d622e0e0980fc089a8bcea18bc` |
| 最新profile | `新算法_v2/证据/bio_v2_profile.json`，由对应ELF生成 |
| 最近普通验证 | 原Host 27/27＋通道隔离29/29，ARM退出0；本轮核对归档，不重复执行 |
| 历史受测F407 | UID `<DEVICE_UID_REDACTED>`，家族ID `0x413`、1MiB Flash |

N0/D1使用同一已构建正常候选，不为重命名模式重新编译。E0/R0/M1在本目录 `拟议配置差异/` 中给出精确补丁；**这些差异尚未应用或构建，没有ELF/BIN SHA，不能烧录。** 后续执行前，在隔离诊断副本中只改变这两个初始化寄存器常量及对应诊断说明，普通构建、配置回读Host验证后冻结其ELF/BIN/资源/profile；算法、SPI、队列、显示/CAN、编译选项和Flash布局与本次基线一致。

没有在运行中热改寄存器：配置仅在复位后的初始化阶段写入，避免与DRDY ISR争用SPI。初始化真实回读必须与该轮配置一致。

### 不直接运行历史入口

- `install_and_bootcheck.py`绑定早期原Flash SHA；不能将历史预期原件替换成当前板身份结论。
- `capture_v2.py`固定150秒、旧installed profile和未知模拟源说明；不适用于本次90秒、指定condition和已知参考输入。
- 上轮 `capture_normal.py/window_tool.py`依赖上轮冻结清单和运行状态；不能未经核对复制调用。

执行前需要针对本轮计划绑定的安装/采集入口，能够明确读入已冻结profile、当前恢复原件及输入元数据，默认只预览。只在独立工具/诊断副本准备，不修改原入口或伪造installed profile。相关脱机验证是硬件前置步骤，不是已经完成的真机结果。

## 3. 先告诉用户的接线要求

### 3.1 模块—F407数字连接

若已经按下表连接，本轮不需要再换数字线。不得把START重新接回PA1。

| 模块信号 | STM32F407ZGT6 |
| --- | --- |
| PW/PWDN | PA0 |
| START | **PG15** |
| CS | PA2 |
| DR/DRDY | PA3 |
| SCLK/SLCK | PA5 |
| IN/DIN | **PA7（MOSI）** |
| OUT/DOUT | **PA6（MISO）** |
| 5V | 已核验开发板5V供电点 |
| GND | 开发板GND，始终保留 |

保持BOOT0=0，既有BOOT1=0。PA2/PA3与串口/RS485的冲突跳帽保持取下；PA9/PA10既有串口线不需要为本次SWD采集调整。串口号只作记录，不参与此次数据导出。

模块图纸V2.0标明CLKSEL上拉、J3接地；该版本内部时钟使用J3开路，CLK不外接时钟。实物不一致或找不到标号时只记录照片，**不要短接未知焊盘**。数字接线与时钟条件维持各轮相同。

USB、J-Link及供电保持固定，本阶段不更换电源、不拔J-Link 3V3参考线，也不把去J-Link和换电源混入RLD对照。J-Link参考/供电方向仍按已知限制记录。

### 3.2 模拟器—模块模拟端

用户已确认模块电极插头为RA、LA、RL，资料目录为 `ADS1292R模块资料V4.1 - 副本/测试连接`。仍需核对实物适配线与图纸的对应关系；当前没有现成模拟器，改为等待第二块F407的型号/引脚负载、衰减元件、仪器和供电条件。**确认输出及参考结构之前不要求用户随意调整模拟端接线。**

资料图纸的对应关系是：模块 `R/ERA`进入CH2负输入，`L/ELA`进入CH2正输入，`G/ADS1292_RLD`经RLD网络连接外部参考端。若实物与图纸一致、模拟器确有相应患者模拟接口，可按功能配对：

| 模块功能 | 模拟器对应端（型号确认后实施） |
| --- | --- |
| R/ERA | RA/R |
| L/ELA | LA/L |
| G/RLD | RL/RF/N等经该模拟器资料确认的参考/患者端 |

不能按红黄绿颜色猜功能；不把模拟器主动输出端强接RLD驱动端。**模块模拟端G/RLD不是数字接口GND的同义词，不用导线将它短接开发板GND。** 具体插针编号和方向以实物/适配线核验，未核验时表中的功能映射不能直接当成已确认接线指令。

模块图纸中两通道通过模拟前端共用ERA/ELA网络，不能拔整条电极/模拟器线来“单独关掉呼吸”，那也会改变ECG输入。ECG独立阶段通过关闭呼吸调制/解调进行隔离，物理模拟接线维持不变。RLD关闭对照也保持参考导线连接，仅改变RLD缓冲bit，不同时拔RL线。

仅连接非人体主动模拟器。所有活人电极和其它人体连接均不在本计划内。新增或移动接线应在断电状态完成，测试供电/地路径固定后再进入序列；这不是运行中插拔或冷启动故障试验。

接线依据：[模块V2.0原理图](<<LOCAL_PROJECT>/doc/B/ADS1292R模块资料V4.1 - 副本/原理图PDF/ADS1292模块电路原理图.pdf>)。资料中的SKX-2000照片只是接法参考，不视为用户当前模拟器身份。

## 4. 输入参考、时长与冻结条件

若模拟器支持，首选一个固定的规则ECG设置，例如 **60 bpm、1mV**；幅值是峰值还是峰峰值、对应哪个导联必须按该型号记录，不能擅自假定。使用独立模拟器记录或仪器核验其输出；面板设定与参考波形证据分别归档。

整个序列保持同一心率、幅值、波形类型、参考导线、模拟器供电、线缆位置和模块/板供电。不在同一组比较中同时改增益、滤波阈值或屏幕任务。

每轮主机记录90秒，初始化和预热原件保留；分析按**第一条实际帧之后30秒**截取稳定段，要求认证连续分析跨度至少50秒。不能把90秒墙钟时间直接当作90秒连续ADC记录。

所有条件固定：名义250SPS、CH1SET/CH2SET=40（正常MUX、增益4）、CONFIG1=01、CONFIG2=E0、LOFF=F0、LOFF_SENS=00、RESP2=03、GPIO配置0C、SPI分频128。CH1未取得有效呼吸输入可以无效，不因此判ECG失败。

## 5. 分阶段序列和准确变量

| 顺序 | 条件 | RLD_SENS | RESP1 | 使用镜像 | 目的/有效比较 |
| --- | --- | --- | --- | --- | --- |
| 1 | N0最新正常候选 | EC | EA | 已冻结正常BIN | 首先确认最新通道独立修复，不评价呼吸准确度 |
| 2 | E0 ECG独立基线 | EC | 2A | 待隔离构建E0 | 关闭调制/解调，建立已知ECG可用基线 |
| 3 | R0 RLD缓冲关闭 | CC | 2A | 待隔离构建R0 | 与E0只差PDB_RLD bit5，CH2感测选择仍保留 |
| 4 | E1返回ECG基线 | EC | 2A | 同E0 BIN | 与R0只差bit5，观察恢复和时间漂移 |
| 5 | M1仅呼吸调制开启 | EC | 6A | 待隔离构建M1 | 与E1只差RESP_MOD_EN bit6 |
| 6 | D1增加呼吸解调 | EC | EA | 同最新正常BIN | 与M1只差RESP_DEMOD_EN1 bit7 |
| 7 | E2返回ECG基线 | EC | 2A | 同E0 BIN | 观察整体返回趋势，不作为两项独立因果比较 |

N0→E0以及D1→E2同时改变调制、解调两位，只用于模式建立/返回观察，**不能称为单变量**。主比较是E0/R0/E1、E1/M1和M1/D1。CHOP、CH2感测选择、呼吸相位始终固定，不采用取消感测的C0作为本轮外部ECG基线。

本序列不强行要求R0/M1/D1全部心率PASS。它们若使输入质量/率值恶化，记录为作用结果；先执行预定返回基线，不临时增加试验或改门限追求PASS。E0不能建立可用ECG基线时，不继续声称可以验收呼吸影响；先保存失败并分析输入/配置。

最多7轮、每轮90秒，合计最多10.5分钟记录；身份、安装、回读、分析及恢复另计。相同BIN仍需明确新run和复位初始化，不把同一轮数据复制为重复实验。没有长时间soak、冷断电、真实assert、Broker或任何安全扫描。

## 6. 硬件前置检查、安装与恢复

1. 收集当前接线、模拟器身份/输出参考和非人体确认。记录实际串口和J-Link型号，不沿用历史口头假设。
2. 完成E0/R0/M1隔离副本构建和普通初始化Host测试，归档源码精确Diff、ELF/BIN SHA、资源与每套独立profile；逐项确认`bio_v2.c`和所有非目标源与冻结基线一致。
3. 新工具普通脱机检查必须涵盖错误UID/固件/profile、错误寄存器回读、无样本、短窗口、导出冲突、观察缺口、不同配置被误当单变量、输入真值未知、恢复原件失效。分析依赖在连接前加载，避免历史2.125秒首次导入停顿。
4. 真机窗口开始，核验UID、家族、Flash容量和参考电压；当前1MiB Flash双读一致，保存为**本轮恢复原件**。当前原件与历史SHA不同则记录并核实用途，不能直接套用旧硬编码原件；双读自身不一致或恢复无法保证立即停止。
5. 每次安装核对上一预期全片SHA、候选SHA、长度/应用范围；执行VerifyBin，再独立全片回读。候选区域必须逐字节相同，应用前32KiB之外必须与本轮原件一致，不改Option Bytes。
6. 启动核验ready、实际初始化寄存器回读与ABI；GPIO低位依既有FC mask，不将FF未读项填成测量值。未读的LOFF_STAT不认证接触，LOFF_SENS=00本身也不提供接触证明。
7. 采用下节固定采集/封存方式，每轮立即评级并留原件；计划内普通复位初始化不等于冷断电测试。
8. 结束完整恢复本轮1MiB原件，VerifyBin、独立全片回读和逐字节核验，记录确认时刻的运行/LOCKUP状态。失败停止继续试验，保留原件和日志，不能声称已恢复。

方案准备不授权现在执行上述硬件动作；待用户连接并启动本次非人体窗口后进行。

## 7. 数据采集与失败证据

继续保存原始9字节STATUS/CH1/CH2、24字节槽记录、IRQ序号/DWT/ms/flags、驱动统计、算法诊断和UI状态。轮询周期保持约0.1秒，记录全部请求/确认时刻和主机停顿；128帧窗口约0.512秒，接近/超过保留时间的停顿必须报告。

每轮末端一次HALT请求，确认后读128KiB RAM，再恢复运行并确认；请求、确认分别记录，确认时刻不能叫作精确实际停止瞬间。运行态快照字段非原子，尾段如果在发布中间停下导致不一致，标REVIEW_REQUIRED，不能强行改数据。

运行态版本只按现有稳定认证规则选择；所有冲突版本、pending、多次重复冲突和暂停版本冲突保留。不能用最后读到的版本覆盖不一致原件。帧数必须与末端captured/delivered对应，否则明确区分板端漏采与主机观察缺失。

目录约定（每个run_id唯一，不覆盖）：

```text
OBJ/ECG独立_RLD_RESP验证/窗口_<UTC时间>/
  window_plan.json / precheck_receipt.json / source_manifest.json
  original-flash-a.bin / original-flash-b.bin
  N0_<run_id>/ ... E0_... R0_... E1_... M1_... D1_... E2_...
    session.json / adapter_profile.json / channels.json
    raw/（全部快照、IO日志、HALT时刻、寄存器回读、安装日志）
    raw_manifest.json / acquisition_receipt.json
    derived/analysis_<id>/（稳定帧、CSV、冲突表、质量、频谱、率值回放）
  restore/（恢复命令、VerifyBin、独立全片回读与SHA）
  handoff.json / 综合回执.md
```

Flash、原始采集及潜在敏感元数据仅本地保存。每轮须记录模拟器/模块/板身份、接线照片、设置与输出真值、固件/ELF/profile/tool SHA、准确寄存器、真实退出码和三种独立评级。失败另存run，不重新编辑为PASS；复测必须新建run并指向原失败。

## 8. 预先声明的工程筛查判据

| 项目 | 判据 |
| --- | --- |
| 身份/配置 | UID、BIN/profile/ABI、初始化实际回读匹配；ready=1；无漂移 |
| 采集连续性 | 认证序号完整、双通道配对；IRQ/captured/delivered一致，无SPI/STATUS/溢出/初始化/长间隔错误；每帧flags=0 |
| 时序/跨度 | 名义DWT168MHz下中位采样率250SPS±1%，无>6ms异常间隔；分析至少50秒连续认证输入 |
| 独立保护 | CH1确实削顶时仍保留CLIPPED且无有效呼吸率；ECG未削顶时继续处理，不因CH1清ECG周期；若实际未出现CH1削顶，记NOT_EXERCISED，不人为短接/异常注入制造条件 |
| 已知ECG参考 | 固定规则源、参考已核验：稳定段HR valid覆盖≥90%，有效HR误差≤max(2 bpm，参考值的2%)；所有无效间隔、最大连续无效时长仍需报告 |
| 实机/回放口径 | valid覆盖以逐帧Host回放给出，注明它不是ARM逐帧计数；ARM按实际稀疏快照报告有效覆盖和误差，稳定段快照至少20个；暂停末态/公共整数状态作对应核验 |
| 未知参考 | 不计算准确度PASS；只报告连续性、ADC质量和算法资格，状态REFERENCE_UNVERIFIED |
| 对照效果 | 输出各轮RMS/偏置/削顶、24–26/49–51/99–101Hz带RMS、QRS候选/受理、原因码及参考HR误差/valid；不预设“开RLD必然改善” |
| 恢复 | 本轮1MiB原件与独立恢复回读逐字节相同；否则RESTORE_NOT_VERIFIED |

功率统一采用原始ADC码、相同分带/去趋势/窗长，例如Hann 4096点、半窗重叠，报告实际DWT推算采样率；分带边界插值积分。在线mains指标不是严格频谱功率比，与Welch带功率分别报告。5/10秒分块属于同一轮的时间块，不冒充独立重复。

这里90%及误差限是本次提前约定的规则模拟输入工程筛查，不是设备规格、患者准确度、临床准出或法规认证。无需降低削顶/噪声/周期保护以取得PASS。

## 9. STOP与有限失败处理

- 人体连接、硬件身份不符、双读备份不一致、无法保证恢复、镜像/profile漂移、Flash越界、异常供电或疑似硬件异常：STOP。
- 初始化/寄存器错误、板端采集错误、源时序异常、导出不完整：保留失败，停止有效心率和因果验收；只进行已明确的安全恢复，不临时换线/改代码补测。
- 率值不稳定/工频升高但身份和采集完整：记录FAIL_EFFECT或FAIL_REFERENCE；允许预定返回基线，用于区分作用与时间漂移，不改门限和原件。
- 新接线、源设置、工具或固件变化必须创建新condition并明确变化，不能继续并入已冻结的单变量比较。

## 10. 准备状态回执

```ini
LATEST_NORMAL_FIRMWARE_IDENTITY = FROZEN
CHANNEL_ISOLATION_HOST_ARM      = PREVIOUS_PASS_HASH_REVERIFIED
HARDWARE_TEST_PLAN              = PREPARED
E0_R0_M1_PATCHES                = PREPARED_NOT_APPLIED
E0_R0_M1_ARM_ARTIFACTS          = NOT_BUILT
WINDOW_INSTALL_CAPTURE_ENTRY   = ADAPTATION_AND_OFFLINE_CHECK_PENDING
COMMERCIAL_SIMULATOR            = CURRENTLY_UNAVAILABLE
SOFTWARE_SOURCE_REPLAY          = PASS_9_CHECKS_NO_HARDWARE
DIY_F407_ANALOG_SOURCE          = DESIGN_ONLY_COMPONENTS_CALIBRATION_PENDING
ANALOG_LEAD_LABELS              = RA_LA_RL_USER_CONFIRMED_ADAPTER_MAPPING_PENDING
HARDWARE_EXECUTED_THIS_TURN     = NO
```

同目录 `validation_plan.json`记录条件和依赖，`simulator_intake.template.json`供录入当前实物信息，`preparation_manifest.json`冻结本轮输入/方案/差异SHA。它们是准备资料，不是硬件PASS回执。
