# B0 基线、工具身份与实板准入缺口

日期：2026-10-22，Asia/Shanghai。本文件为B-ALG-001的支持审计，最终裁定只见[B-ALG-001-FINAL-HANDOFF.md](B-ALG-001-FINAL-HANDOFF.md)。

## 1. 起点与本轮观测

指定远端B=f8c99433561b2e110c04ba9fb33c30235910a3e9，开工实际ls-remote相同；GitHub为PRIVATE。
从该SHA新建E:/medical-monitor-node-b-bio-v2，分支codex/node-b-bio-v2-test-20261022；不整体合并其它分支。
语音最终提交ba61ae2c97204f240d8fa6f316eb700aff70d29e已推送/取回核验，仓库外single-writer租约active=false，先停语音再建立B软件租约。
旧B工作区有预存local-evidence/，只读保留。本工作区无.codegraph；按精确文件读取追踪，不生成全库索引。

| 对象 | 本轮状态 |
|---|---|
| B固件源码、Keil工程、startup | 实际读取、散列冻结、离线重建 |
| B实际板卡/UID/Flash/启动方式 | NOT_OBSERVED；未接板、未读SWD |
| ADS1292R模块、电极与线缆 | 负责人说明硬件尚未连接；未测导通、电压、寄存器 |
| B与C的CAN | 未连接；本轮也不要求连接 |
| 模拟器 | 提供SKX2000D+说明书；今天实物型号、设定与校准/电极对未确认 |
| 测量仪器与现场受众 | 本轮未核实；软件只在本机运行，不上传原码/人体数据 |

因此B0只通过软件基线分层审计，硬件身份NOT_OBSERVED、外部输入BLOCKED_SOURCE，不能称作实物B0全部通过。

## 2. 源码、构建与采集工具

当前代码路径firmware/biov2/实验固件/；main先初始化NVIC、屏/时间基准、SPI/ADS，再BioV2_Init，主循环经HrPage交付队列帧。
DRDY ISR读取9B，128×24B静态FIFO交付主循环，BIO_V2在主循环处理；源flags/缺口仍共同失效，局部削顶只影响本路。
不改原算法、阈值、寄存器、采样频率、UI/CAN或startup。

| 固定源/依赖 | SHA256 |
|---|---|
| bio_v2.c | 3adca55cb1eb1fa3ed8e4148f837287d0454bcc2c08ae77a8f73deb1dac156a7 |
| ads1292.c | f99c3d567338f95b4cbae5579554d15e3af4928f8b1a39e0f18b9dbd30192ced |
| spi.c | 5e09707c47cec710172a4e78e7ca21c15c7359d964d0fbe8bf5c2498243a8ec0 |
| ecg_frame_queue.c | cab4719c4151386acbac422f28af517a5b54c8c3c933a52a9207b1c0140e319f |
| 本地arm_cortexM4lf_math.lib，13294064B | ba416f23efb992105c36b67d9002d8142e38877d1010c0e0a1d0f74b83325ab7 |

Keil UV4/ARMCC 5.06 update7 build960，原BIO_V2.uvprojx，STM32F407ZGTx，startup_stm32f40_41xxx.s；原CMSIS/标准库许可头保留。
DSP只使用本地合法原件，先匹配SHA，不入库、不下载替代库；算法C本身不依赖旧CMSIS FIR，但完整工程仍需该链接依赖。
114份源/工具身份含原run_host.py、build_arm.py、标准acq工具及新离线检查，见../evidence/B-ALG-001/B0-source-tool-sha256.json。
原工程88份C/H/S/Keil源散列前后未变，既有归档266文件验证通过；不是全盘/设备备份验证。

BIO_V2诊断tag=0x324f4942、abi_version=2、120B；本轮ARM offsetof常量与Host全部31个值相同。
本轮ELF定位g_bio_v2=0x20001ae4、slots=0x20001f30（3072B）、ADC s_stats=0x2000018c（48B）；同名另一个s_stats不能按首次匹配猜测。
精确地址、字段偏移与本轮BIN/ELF/符号表SHA见../evidence/B-ALG-001/abi/receipt.json。
此表只有OFFLINE_LAYOUT身份：无真实UID/已安装全Flash绑定，不是已批准的实板采集profile。

旧ads1292r_swd_ring24_v1_9f58a890.json绑定9f58a890… BIN且含旧算法字段/地址；本轮用原offline_precheck函数对真实新BIN测试，精确拒绝“bin SHA 不符合适配器”。
参考capture_v2.py.txt是旧现场脚本文本，其中reset/halt尾段不属于本轮软件授权；没有改扩展名或启动。
槽冲突仍由原StableSlots/test_acq检查：两个版本均重复（例如3票/2票）必须pending，不准多数表决；暂停尾段也不能覆盖冲突。
实时120B读取不具有整块原子性，诊断点与原码槽不是同一帧证明；未来仍需冻结profile/稳定版本/尾段规则。

## 3. 引脚、时基及未来连接边界

| B端 | 模块/用途 | 本轮证据 |
|---|---|---|
| PA0 | PW/PWDN-RESET | 源码 |
| PG15 | START | 当前源码；不能沿用PA1 |
| PA2 | CS | 源码 |
| PA3 | DRDY/EXTI3 | 源码 |
| PA5 / PA6 / PA7 | SCLK / DOUT→MISO / MOSI→DIN | SPI1 Mode1，/128 |
| PA9 / PA10 | USART1屏 | 与C语音PA2/PA3是不同MCU，不复制C固件到B |
| PF8 | 蜂鸣器 | 现有工程 |
| PA11 / PA12 | 既有CAN1 | 保持与A/C物理隔离 |
| 模块5V/GND | 仅按模块图J1/J2其中一路 | 实测未进行 |

源码CONFIG1=01（名义250SPS）、CONFIG2=E0、CH1/2SET=40、RLD_SENS=EC、RESP1=EA/RESP2=03；没有今天的实际回读。
TIM2给1ms算法时戳、屏SysTick为10ms、DWT做微秒时序；名义168MHz/84MHz不替代实测采样时钟。
驱动IRQ间隔>6ms记录flags，算法时间缺口>100ms共同失效，不能混用两个门槛。
PA1与板载PHY共网的历史问题保留；模块J3为时钟选择，图纸默认不短接，不是开发板P11。

模块图：RA经外网到IN2N，LA到IN2P；RL是主动RLD反馈，不当作GND或LL，不与LL/GND短接。
未来按端到端导通确认触点，不按颜色猜线；未提供今天实物接线证明，不下发上电/连接指令。
另外当前B源码CO_NODE_ID=3、CAN=1Mbps，而H3保留未来Node-ID2；这是后续三板合同的兼容缺口，本轮不修改、不接总线。

## 4. SKX-2000D+说明书复核

原件12页，629590B，SHA256=27fe9e4a37a761ab7df939bf49693942dbf3e5692f09e2e10311106053503cc8。
来自负责人附件doc/B/SKX2000D+说明书.pdf；未复制受限资料包/模板到库。中文文本映射损坏，已逐页查看渲染图，结论据可见页面，不据乱码提取。

| 页码 | 资料能证明的内容 | 仍不能证明 |
|---|---|---|
| 1–2 | I导联用RA–LA；II用RA–LL，RL列参考/反馈；另有I导联定标说明 | 实物插孔、电缆导通、RL主动反馈兼容性 |
| 1、4、6–8 | 普通ECG标称20–300bpm、列0.5/1/2mV；正常波形导联图；普通波形同步20bpm呼吸 | 页面也说ECG幅度固定；不能把II幅度或菜单值直接当I导联精确mV/校准证书 |
| 5、11 | 呼吸5–120rbpm；基础阻抗1K，幅度原文0.3R–3.0R、默认1.5R | 动态阻抗作用RA–LA还是RA–LL；今天实测ΔΩ/频率及输出误差 |
| 1–3 | 内置电池、microUSB充电和菜单操作 | 今天的供电/USB共地状态及现场仪器能力 |

ECG/B2与RESP/B3来源分别准入。手册使商用源成为可调查候选，但还不能替代实物型号、I导联幅值/频率参考和阻抗电极路径证明。
S板历史BIAS数字/物理不一致及动态未验收仍保留；不输出几伏DAC直入毫伏模拟端的接线方案。

## 5. 历史与当前软件结果边界

采样连续性、PA1/PG15对照、内部SHORT/TEST的历史结果仍仅属当轮；未认领为今天实板成绩。
本轮实际重跑27算法、28隔离、2561 FIFO断言、27采集工具、S模型34/19/9；ARM退出0，无旧算法符号。
新增13项离线检查含初始化/新周期/时间边界、双回绕、历史8412帧；不增加算法阈值、不修算法C。
8412帧原SHA=2dc6b0ac56c5d6901abfda4c0ea851b28d54e2c55b02b2d760740c43ad2b7ccf，CH1全正顶轨；旧共同清空已复现，新版保留全部帧但HR/RR仍无效。
37169帧CSV指定SHA=943d59b3dc723820a0d287b06534c4be31fd91442977f978a2e38d8422b3ce53，本轮在项目原件和负责人下载目录未找到精确文件，NOT_RUN，不拿另一个CSV代替。
50/100/25Hz合成负例通过只表明该夹具被拒，无法证明真实输入的误检/漏检/噪声来源。

当前可以推进软件交接，物理窗口必须先获得AUTH-B-ECG-01及独立AUTH-B-RESP-01；不为本轮收尾请求空白授权。
