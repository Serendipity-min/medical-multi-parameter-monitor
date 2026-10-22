# B2-0 基线、现场映射和信号源核验

2026-10-22，Asia/Shanghai。软件准备完成，实物准入未通过。唯一阶段裁定见 [最终交接](B-ALG-002-FINAL-HANDOFF.md)。

## 项目进度及工作边界

已读本地分支、GitHub 仓库元数据/分支/最近 PR、B-ALG-001 最终交接、模块接线及证据矩阵、VOICE-002 最终交接。远端 Node-B 基线仍为 `c0617b9fc0ee1f1c6b2f3c4ece90b36db7a78740`，新分支 `codex/node-b-bio-v2-field-20261022` 从此精确创建；工作区 `E:/medical-monitor-node-b-field`。原 P5 工作区及其未提交文件不改。

系统为 A 生理参数节点、B ECG/阻抗呼吸节点、C CANopen/MQTT 网关及云端页面。GitHub PR #6 已合入 P4；这不等于 B 实物验收。H3 正式冻结为 `a5cdd5b0b1ad48108fd631136e9de69e30582f2d`，标签对象 `8a9265146a293f8a020df39863943e9de4adce68`；语音分支 `ba61ae2…` 的单短句通过后已恢复 H3。P6 软件来源不代表本轮允许修改或部署。

B0/B1 软件通过，已回放 8412 帧开放输入，但无参考真值；37169 帧原件仍 NOT_RUN，不重造。B 源码 Node-ID3/1Mbps 与 H3 未来 Node-ID2/500kbps 有差异，留待独立三板合同。本轮没有接 CAN、访问硬件或连接服务器。唯一执行者 Codex /root，原 B1 租约已释放，本轮受限目录保存独立租约。

## 候选身份

固件源码未改；本工作区重新 Keil/ARMCC 构建，0 errors、0 warnings。BIN=25284B，SHA256 `438a8120f6df06ce219cdc30c0e5b697ac0e993f98d5a80521b10361536ae3ae`，与合同相同。bio_v2.c SHA256 `3adca55cb1eb1fa3ed8e4148f837287d0454bcc2c08ae77a8f73deb1dac156a7`。

新 AXF SHA256 `cba20bfb543de57e6c3957d1be3fbd519b9f81ba740749eb763d464ec7ed8bee`；新 symbols.txt SHA256 `a556fa4a8d5edb8295be44059251357d288b39bb845b318ff3fc024fde7d2897`。不沿用 B1 ELF 散列；路径变化可改变调试产物，BIN 身份独立核验。31 个 ARM/Host 布局常量再次一致，原旧 profile 再次精确拒绝新 BIN。

全部 source/tool SHA 见 `../evidence/B-ALG-002/source-tool-sha256.json`，ARM/ABI 回执分别为 `arm-receipt.json`、`abi-receipt.json`。这些只证明磁盘候选，当前板上镜像仍 NOT_OBSERVED。

## 实物事实与源码映射分开

负责人当次回报：SKX 已到手；B 板是 STM32F407；CAN 未连接；J-Link 最新更正为连接 B 板（先前“未接”“接C”均已被负责人更正）；RA/LA/RL 通断及隔离资料未知。未获得板卡/模块/模拟器机身照片、完整芯片后缀、模拟器固件/供电/附件、B 当前供电及跳帽状态，不把前轮照片当今日证据。

| 项目 | 当前候选源码/图纸 | 今日实物核验 |
|---|---|---|
| PWDN/RESET | PA0 → 模块 PW | 未确认 |
| START | PG15 → START；PA1 已释放 | 未确认，不沿用 PA1 |
| CS / DRDY | PA2 / PA3，EXTI3 | 未确认 |
| SPI1 | PA5 SCLK、PA7 DIN、PA6 DOUT；Mode1，/128 | 未确认 |
| 采样时基 | 名义250SPS，APB2名义84MHz，SCLK名义656.25kHz | 未实测 |
| 电源 | 图纸 J1/J2 仅取一路，模块5V入口 | 电压、参考、接地未确认 |
| J3 | 模块 CLKSEL，默认不短接/内部时钟 | 未确认；不是开发板P11 |
| RLD | RLDOUT经100kΩ送外部RL | RL兼容性未确认 |

模块图 SHA256 `dd8a66e9019d4a958adb0dc83741261daf8cd45a0a46faea93cb9dbdca14c069`，图纸 V2.0/2020.09；不能因资料目录 V4.1 就称实物为 V4.1。图纸 A1：1/2 标 RLD，3 标 ERA，4 标 ELA，5/6 未接；这是原理图引脚编号，不能当作插头观察面/实物脚序。必须有对应连接器方向、照片及端到端记录。

ERA经R4 56k到IN2N，ELA经R15 56k到IN2P，因此候选 CH2 为 LA−RA（导联I）。CH1 IN1N/IN1P也分别进入 ERA/ELA 路径，调制另经耦合及39k支路；B3 要求源的动态阻抗落在这条 RA–LA 路径。外部 RL 是主动RLD，绝不是GND；不得与LL短接或凭线色猜接。

当次正常配置预期：CONFIG1/CONFIG2=01/E0，CH1SET/CH2SET=40/40，RLD_SENS=EC，LOFF/LOFF_SENS=F0/00，RESP1/RESP2=EA/03，GPIO预期0C但实际输入低位按mask核对。尚无今日寄存器回读；初始化缓存 g_ads_readback 不等于采集结束时重新 SPI 回读。若要求再次 SPI 读取，须明确授权对应动作及必要软件提案。

## SKX-2000D+ 兼容性

说明书原件 `doc/B/SKX2000D+说明书.pdf`，629590B/12页，SHA256 `27fe9e4a37a761ab7df939bf49693942dbf3e5692f09e2e10311106053503cc8`。本轮再次核SHA并查看12页渲染；中文文本映射损坏，以可见页面为准。文件在原工作区，未复制进新分支。

| 依据页 | 可以支持 | 不能支持 |
|---|---|---|
| 1–2 | I导联RA–LA，II导联RA–LL，RL列参考/反馈 | 实际触点、RLD负载容限/隔离 |
| 4、6 | 普通ECG 20–300bpm，覆盖60/90/120；正常ECG同步20bpm呼吸 | I导联绝对1mV误差、今天实物频率准确度 |
| 1、4 | 文中幅度固定与菜单幅度表并存 | 不把菜单或II幅度当I导联标定保证 |
| 5、11 | 呼吸5–120rbpm，基础1K，0.3R–3.0R、默认1.5R | R的精确定义、峰峰/峰值、变化端子对和调制频率下行为 |

结论：`ECG_SOURCE_RECEIVED_COMPATIBILITY_UNCONFIRMED`。先验证节律，不声称幅度标定。RL当前不得给出接到模拟器的执行指令。B3同时保留 `B3_BLOCKED_ELECTRODE_PAIR` 与 `B3_BLOCKED_REFERENCE`：有菜单/低频电压/静态DMM数值仍不足以证明阻抗路径。

### 负责人新增附件及厂商演示核对

负责人提供的字母对照图只证明模拟器自己的 R=RA、L=LA、F=LL、RF/N=RL，并不证明模块第三根标F线对应LL。重新查看用户指定V4.1副本中的F103和F429模拟器演示图：绿色接RA、黄色接LA、红色接RL，LL空置。该演示显示旧SKX-2000，并非本次SKX-2000D+实物兼容认证；不能按颜色认定今天线缆触点，也不能把厂商图直接当本次接线授权。

本模块图纸ERA/ELA/RLD功能优先于通用三导联字母：若证实线缆R→ERA、L→ELA、第三根F→RLD，则拟议对照应为R→源RA、L→源LA、F（实际RLD）→源RL/RF/N；最后一项仍以主动RLD兼容性准入及现场卡为前提。若F确实对应另一输入路径，需重新评估，不强行套表。禁止仅因附件写F=LL就把模块RLD接LL，禁止桥接LL/RL。

算法选择也重新查到实际调用：当前候选main初始化BioV2_Init，hr_page把CH2/CH1原码送BioV2_Process并从BioV2_GetHeart/GetResp取值。另一个“心率+呼吸+体温(用心电算呼吸)”目录algo.c包含bh_feed/心搏反推呼吸和旧RespRate流程，保留作历史资料，不切换成本合同算法。这里的“呼吸率RR”也不能与心电R–R间期混称。当前板上实际算法仍未读取确认。

器件级边界参考 [TI ADS1292R Rev.C](https://www.ti.com/lit/ds/symlink/ads1292r.pdf)：含主动 RLD 和阻抗呼吸调制/解调；器件功能不保证第三方模拟器兼容。扇区边界参考 [ST RM0090](https://www.st.com/resource/en/reference_manual/rm0090-stm32f4xx-reference-manual-stmicroelectronics.pdf)。本轮不作法规/医疗精度合规裁定。

## 采集适配缺口

新离线profile见 `../acquisition/field-biov2/profile.offline.json`，它有意使用独立schema，旧采集器不得接受。g_bio_v2=`0x20001ae4`/120B/ABI2，slots=`0x20001f30`/3072B，head/tail=`0x20000140/144`，ADC stats=`0x2000018c`/48B，初始化寄存器缓存=`0x200001bc`/12B。

旧 acq_storage 对 stats 地址写死 `0x2000020c`，旧 acq_swd 仅周期读前2KB RAM，不能取得新 g_bio_v2；还含主动reset、halt/go流程。既有工具不改，不给它换地址后上板。新工具 field_profile.py 只做离线身份/布局/观察元数据核验，没有硬件后端；因此 `BLOCKED_CAPTURE_ADAPTER` 是真实缺口。

BIO_V2只公开最后滤后值、候选/接受峰计数和末周期时间，没有逐拍事件日志。后续可在冻结原码上用同一源码离线逐帧回放得到滤后序列和接受计数变化，明确标 REPLAY；实时非原子诊断只作观察。不能把稀疏RAM读取或回放峰事件标成实板逐样本记录。完整实时逐拍留存若必要，须先审最小采集/诊断改动，重建及新授权；不得以本轮软件准备宣称其已实现。
