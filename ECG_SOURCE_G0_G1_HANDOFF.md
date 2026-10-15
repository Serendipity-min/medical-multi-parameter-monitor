# ECG_SOURCE_G0_G1_HANDOFF

日期：2026-10-15（Asia/Shanghai）。唯一综合交接回执；执行范围为 **MPM-ECG-SRC-001 v1.0 的首轮G0/G1**。

合同原件SHA-256：`398c1d0190d29b08e5f28205af0125cfc8c81a2d422775f00a541d0b2e638fc6`。本轮只做文档/源码核对、独立源工程实现和普通脱机测试，不连接或操作开发板。

## 1. 阶段裁定

```ini
G0_DOCUMENT_AND_CODE_REVIEW = COMPLETE
G0_HARDWARE_ADMISSION      = BLOCKED_UNMEASURED_CONDITIONS
G1_SOURCE_IMPLEMENTATION   = COMPLETE
G1_HOST_MMIO_MODEL         = PASS_64_OF_64
G1_ARM_BUILD               = PASS_EXIT_0_ERROR_0_WARNING_0
IDEAL_TRANSFER_MODEL       = PASS_4_OF_4_NOT_PHYSICAL
SOURCE_ANALOG_CALIBRATION  = NOT_MEASURED
G2_G3                     = NOT_AUTHORIZED
B_BOARD_OR_BIO_V2_MODIFIED = NO
REVIEW_BRANCH             = B2_LOCAL
GIT_PUSH                  = PENDING_OWNER_SCOPE_CONFIRMATION
```

G0缺口不能被G1软件PASS覆盖。现在没有源板DAC、衰减后电压、ADS外部输入或真机60/90心率通过的证据。

## 2. Git与原工程保护

- 新建独立本地工作区及 **B2** 分支，起点为只读远端核对相同的P4 `67f5f57bd82c6e326e9e78ec9540481c80105e5f`。没有切换或改写原主工作区。
- 原工作区仍为P5-coremqtt-baremetal，HEAD `47e59a67c949255d35b3f1e7e0f12459407d0ebc`；其既有未提交改动保留。
- 原B板工程、候选/profile及原有已修改文件等 **99个文件SHA核对不变**，原Git脏状态不变。没有reset/clean、P4/main改动或PR操作。
- 本轮审查文件仅准备在B2；提交/推送范围按`artifacts/ecg-source/proposed-push-manifest.json`交负责人确认。未获确认前不推送；不上传完整Flash/固件二进制、真实采集数据、板UID、个人路径/凭据、PDF/局部原理图图片或实物照片。

## 3. G0引脚、供电和接口结论

详细表：[G0_BOARD_AND_INPUT_CONTRACT.md](artifacts/ecg-source/G0_BOARD_AND_INPUT_CONTRACT.md)。

| 项目 | 图纸/芯片可确认项 | 待实物核验 |
| --- | --- | --- |
| S.PA4 | DAC1_OUT，LQFP144芯片40脚，板网STM_DAC/P11.5 | 源板实际引出/附件、P11 5–6是否接入LED负载 |
| S.PA5 | DAC2_OUT，芯片41脚，板网STM_ADC/P11.3 | P11 3–4是否接入电位器滑端；不是可忽略负载 |
| S供电 | 同款图纸J5 DC 6～24V、K1按下外部DC | 用户拟12V/1A；极性/实物电压/纹波和多供电路径未测 |
| B数字线 | PG15 START，PA0 PWDN、PA2 CS、PA3 DRDY、PA5/6/7 SPI | 原接线未改，禁止把B.PA5当源板DAC |
| LA/ELA | 模块图纸经R15/前端到CH2 IN2P | 插头/线束实物通断、模块版本 |
| RA/ERA | 模块图纸经R4/前端到CH2 IN2N | 同上 |
| RL/RLD | RLD输出/反馈网络到外部RL，不是数字GND | 初期目标为悬空绝缘；本轮没有实际改线 |

关键缺口：两板实际身份/当前Flash；源板实物P11状态和供电；ADS AVDD/AVSS/VREF、共模；仪器与BOM测量；跨板参考回路。**G0硬件准入BLOCKED**。本轮未将1MΩ/1kΩ/10kΩ候选电阻或2048码偏置变成已批准接法/实测电压。

## 4. G1源板实际实现

独立代码：[ecg-source/](ecg-source/README.md)，不链接BIO_V2、ADS驱动、屏幕/CAN或RTOS。

- 复用ST CMSIS启动/时钟和设备定义，不迁移HAL。名义8MHz HSE→168MHz HCLK→APB1/4→TIM6 84MHz。
- TIM6更新TRGO，PSC=83/ARR=999，名义1kSPS；DMA1 Stream5/Channel7循环表→DAC1 PA4，DAC2 PA5保持2048码。
- 模式OFF/静态偏置/1Hz正弦/60bpm工程QRS/90bpm工程QRS。上电OFF，模式只能在未来获授权源板窗口明确选择。
- 60表1000点、1秒1拍；90表2000点、2秒3拍，避免667点重复造成固定拍频偏差。工程P/Q/R/S/T宽度与极性、码值由固定生成工具提供。
- DHR预装第0点、DMA旋转从第1点开始；强制UG在DAC触发关闭时完成，不多发一次请求。
- 有界停止DMA、错误/欠载优先、待处理错误在模式切换前留证；无自动复位重启至PASS。若不能确认DMA停用则明确高阻故障，不虚报静态输出。
- DMA码缓冲8000B位于普通SRAM `0x20000060`，不在DMA不可访问的CCM；接口寄存器访问宽度经真实ARM编译核对。

上述静态/限幅是程序状态描述，不是已认证物理输出或患者保护。

## 5. 真实普通构建和测试

| 检查 | 结果 | 边界 |
| --- | --- | --- |
| 源板Host实际C＋MMIO模型 | **64/64，编译退出0** | 启动OFF、模式/表/时钟/启动顺序、循环对齐、错误锁存、超时/高阻、IRQ证据保留；无模拟电气或实时DMA仲裁 |
| 源板ARM | **退出0，0错误、0告警** | Keil ARMCC5.06u7 build960，真实生成BIN/AXF/map |
| 理想传递→冻结BIO_V2 | **4/4** | 假定DAC参考3.3V、候选1/1001、ADS参考2.42V/gain4；不含负载/实际SINC/真实电压，不是硬件结果 |
| 既有软件源9/9 | 只核对并整理合成回执 | 本轮未把历史PASS称为新真机测试 |

理想模型稳定段60/90分别给出60/90，有效覆盖均100%；平直和1Hz正弦均无有效HR。输入CH1持续削顶，保护原因保持34，ECG独立处理。该模型显示工程输入在假设传递下能被最新算法识别，**不能确认实际电阻/端子/PGA链已正常**。

平直/正弦末态原因3含现有引擎保留的初始预热标志＋周期不足；它不是测到90秒后仍处在物理启动预热。本轮没有为改原因码或提高有效覆盖而修改BIO_V2。

公开结果：[Host摘要](artifacts/ecg-source/host-summary.json)、[ARM摘要](artifacts/ecg-source/arm-summary.json)、[理想模型](artifacts/ecg-source/ideal-transfer-summary.json)、[合成码表](artifacts/ecg-source/software-waveform.csv)。码表4002行数据含OFF/BIAS标记，实际动态码表为1000/1000/2000点。

### ARM资源与准确产物

| 指标 | 实际值 |
| --- | ---: |
| Code / RO / RW / ZI | 2284 / 8504 / 24 / 9096 B |
| 静态RAM RW+ZI | 9120 B（不等于动态栈实测） |
| BIN字节 | 10812 |

| 产物 | SHA-256 |
| --- | --- |
| 源板BIN | `ae13ba5c776ca875a67a51ff372f50c281a19e114e44d89c7572b3be4f392c3a` |
| 源板ELF/AXF | `5174b71749d2e653db246be637be3358b49e7367c3d603e8e9637b61895ab7aa` |
| 源板map | `5b9b80b646cde7d5cd782889452285271cee5f57b0cc8f1e37ceace6d55ebfe3` |
| 1Hz正弦u16le码流 | `3e56e8d0c3a72d3447f69fc90b6530ca605dccc893a8d4aff0dbca2aa2bd9c59` |
| 60bpm u16le码流 | `f5a4c3bd9b102ef73dc0a2c8a044e50d8d2c301d15b35e3249ddff48ef025b31` |
| 90bpm u16le码流 | `3f9f752ab0756c33b5c21d01f593d7d5c6c26233941c34c42ff7aedf81f6b8e2` |

完整产物及原始日志保存在各次`ecg-source/build/arm-*/`，仅本地；公开摘要提供SHA。第三方启动/平台字节不改，来源和SHA见platform-provenance.json，保留版权许可头。

## 6. 失败证据保留

本轮ARM先后3次失败：漏CMSIS SIMD头（3错误）；TIM字段访问类型不符（7错误）；部分字段改16位后CNT/ARR仍需32位（2错误）。补齐原来源依赖、按混合宽度修复独立源板驱动后通过；后续待处理IRQ留证修复再次通过。共5次ARM记录，3失败＋2通过。

每次独立目录的原日志、退出码、输入SHA及相关失败源副本保留；不覆盖或删除。首次离线工程脚本还保留“system头文件位置误判”失败。初始59项通过回执保留，最后64项是针对新增错误留证边界的真实复测，不伪造旧回执。

失败索引：[build-attempts.json](artifacts/ecg-source/build-attempts.json)。没有新硬件测试，故没有本轮真实DAC/ADS失败数据或通过数据。

完整Git空白检查另发现ST原件/B端快照继承的行尾空格。为保持原字节SHA没有清洗这些源文件，完整检查如实保留为失败；本轮新实现/工具/文档的聚焦空白检查单独记录。目录内属性确保审查快照不被Git自动CRLF转换，磁盘SHA与暂存Git blob SHA分别列入推送清单，不隐藏历史空白问题。

## 7. B端审查资料与身份

`review/biov2-current/`含BIO_V2、ADS驱动、SPI/FIFO、hr_page、时基/延时、GPIO使用所在main/启动/时钟、中断及相关CAN/蜂鸣器接口源码快照。

- BIO_V2实际源SHA：`3adca55cb1eb1fa3ed8e4148f837287d0454bcc2c08ae77a8f73deb1dac156a7`。
- 最新B候选BIN：`438a8120f6df06ce219cdc30c0e5b697ac0e993f98d5a80521b10361536ae3ae`；ELF：`5a3fbbc13fe57a6b3a5fdaf6ead7f80320bff6d622e0e0980fc089a8bcea18bc`。
- 27个板级源文件逐字节相同；构建脚本归档。只有审查版地址生成器去掉真实UID，原SHA和审查SHA明确区分；原生成器未改。
- **今天板上镜像未知**，没有把候选SHA当已烧录SHA。
- 当前源与上一正常回读为RLD_SENS=EC、RESP1=EA、CH2增益4/250SPS、SPI /128。合同目标S_DAC_ECG_ONLY是CC/2A；本轮未应用B配置变化，G3前须明确取得目标配置的批准/候选/身份。
- 8412帧开放输入与修复后回放只以脱敏计数/原因摘要整理，不公开真实原码或患者信息。9项原软件源仅合成数据，未混用为真机证据。

审查包是源码复核材料，不是可用于B板烧录的完整工程。[B源身份清单](artifacts/ecg-source/biov2-source-manifest.json)及[配置摘要](artifacts/ecg-source/current-acquisition-config.json)给出每项实际身份和未知值。

## 8. 待负责人确认

1. **推送范围**：仅本回执、独立源板代码/平台/普通工具与测试、B端脱敏源快照、公开合成样本与结果/身份清单；用SSH推送独立B2。清单确认前不推送，不创建PR。
2. G2前补齐源板实物/两组P11跳帽、供电、仪器、BOM和输出校准条件；须下一轮明确硬件授权。本轮不自动申请/启动G2/G3。
3. 候选衰减/串联电阻及偏置/共模未批准；不能按图现在跨接两板，不能将源板12V接模块或输出针脚。
4. G3前核验B板实际镜像、模块接口/模拟电源，以及CC/2A测试配置来源。若需要超出授权的B驱动/算法改动，停止并交负责人裁定。

停止于G0/G1脱机交付；不进行RLD人体等效闭环、呼吸阻抗、长期测试、Security Gate或其它阶段开发。
