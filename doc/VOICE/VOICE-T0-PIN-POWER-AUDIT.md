# VOICE T0｜引脚、电源与冻结基线

合同：MPM-C-VOICE-001 R1.0；执行日期2026-10-22（Asia/Shanghai）。新工作区 `E:/medical-monitor-c-voice`，分支 `codex/gateway-c-tw-tts-v1-20261022`。H3、A/B/P4/main/P6与H3标签只读。

## 事实及来源

- 开工实际GitHub查询：仓库PRIVATE，H3远端 `a5cdd5b0b1ad48108fd631136e9de69e30582f2d`；annotated tag对象 `8a9265146a293f8a020df39863943e9de4adce68`，peeled commit同上。没有起点漂移。
- H3旧lease两个标志均已释放；本轮新建外部VOICE lease。没有跨会话工具证明，单写入者依据为同一执行者上一轮释放、本轮独立工作区及负责人指派，不声称检测了所有编辑器。
- 负责人本轮说明：TW-TTS未接线，C未供电、USB未接，拟用J-Link；PA2/PA3未接其他模块。实际J-Link是否已接C、A/B供电/总线状态仍须现场核对；本阶段未访问调试器、串口或开发板。
- 用户明确指定现有8Ω1W作为短时低音量播放负载，覆盖合同等待匹配喇叭的默认选择；不把这项选择写成输出功率已测量。
- 本地原理图 `STM32F407_原理图.pdf` 为6页扫描件，标题STM32F4神舟号V2.0，已渲染检查第4/5/6页；数据手册Doc ID022152 Rev2第46/56页核对PA2/PA3、FT和AF7。旧目录 `E:/stm32/stm32` 不存在，实际使用 `E:/stm32/stm32文件`。
- 厂家[使用手册V0.21](https://www.haohaodada.com/new/bbs/forum.php?mod=viewthread&tid=2621)已读取。原天问域名浏览器证书不匹配，未绕过；好好搭搭同一厂家论坛页面打开初次超时，随后成功读取正文。网络资料不能替代现场电气测量。

## 资源映射

| 资源 | 原用途/本轮决定 |
|---|---|
| PA9/PA10 USART1 AF7 | 原控制台，禁止复用；离线候选不启用 |
| PB10/PB11 USART3 AF7 | ESP8266；原ISR默认优先级0，禁止复用；候选不链接ESP |
| PA11/PA12 CAN1 | 原IRQ优先级1，禁止复用；离线候选不启用CAN |
| PA2/PA3 USART2 AF7 | 负责人确认外部未占用；图纸P9第38针PA2、第36针PA3；实物优先依丝印识别，不猜排针方向 |
| P3 2×3串口路由 | 第3针USART2_TX、第4针USART2_RX，可跳接SP3232/RS485；接TTS前必须解除PA2/PA3与板载收发器输出的跳接，不能接DB9/RS232电平 |
| PA2 ETH_MDIO | 图纸另有板载PHY网络连接；候选不初始化ETH、不产生MDC。仍保留板级连接影响，不能称引脚与全板完全隔离 |
| PA0 WK_UP | 图纸按键高电平有效；离线候选按下触发一次，启动时必须先释放，30ms去抖，上电至少2s后才接受 |
| USART2 IRQ | 独立候选优先级15；32B静态SPSC接收队列，单次ISR处理1字节，错误/溢出独立累计 |
| PB12/PB13/PB15 I2S2 | 仅未来资源预审；PB12/13还可能与CAN2/WM8978相交，SD实际板级路线须重审，不接INMP441 |

## 下一次现场接线设计（尚未施工）

| C/电源 | TW-TTS |
|---|---|
| 受审+5V（不是3.3V/J-Link电源） | V |
| GND | G |
| PA2 TX | R（模块输入） |
| PA3 RX，确认T电平后才连接 | T（模块输出） |
| 8Ω1W喇叭两根线 | SPK+ / SPK−；SPK−禁止接GND |

PA3数据手册标FT，必须在MCU正常供电、数字AF模式下使用；这不代表未供电时可向其注入5V。首次先只接G/V测模块T对G空闲电压、5V/3.3V电压，断电后再接UART。若T电平不明、超过适用范围或异常，先停，不凭模块供电推断。

电源总预算、播放峰值/压降、实际扬声器差分功率均NOT_MEASURED。固定v1短句不等于功率≤1W；不默认v5、不升音量、不循环、不把普通示波器地夹接SPK−。出现失真/发热/复位或异常电平立即停电。

## 默认关闭与范围

H3 `cloud/ai/app.py` voice默认false、无publisher时DISABLED；downlink只连loopback。`gateway/mqtt/src/gateway_transport.c:mqtt_event`仍拒绝任何PUBLISH。新TTS源码不在原build glob下，只有新离线build显式定义MP_TTS_BENCH；队列上电DISABLED，只有现场WK_UP才设置v1并播放单条固定短句。

INMP441仅预审：I2S 24位/64SCK来自合同引用，实际上传PDF本轮未找到，不伪称完整重读；PLLI2S、DMA/IRQ和音频缓冲均未分配。现有TTS只增加静态队列，不使用I2S、FreeRTOS、麦克风或ASR。

阶段判定：`T0_SOURCE_REVIEW_COMPLETE / HARDWARE_PINOUT_PENDING / UART_VOLTAGE_PENDING / SPEAKER_POWER_NOT_MEASURED_OWNER_SHORT_TEST_OVERRIDE`。没有实际声学/电气PASS。
