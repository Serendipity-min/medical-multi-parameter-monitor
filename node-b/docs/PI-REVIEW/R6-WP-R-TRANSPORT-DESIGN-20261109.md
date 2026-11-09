# R6 WP-R 传输优化、DMA 与 168 MHz 设计评估

2026-11-09 · 设计评估。当前候选仍为裸机、HSE 8 MHz。R5 的 230400 与 500000 只提供 ESP→STM32 的 AT 级实测，业务容量和 CAN 并发尚未测。[R5 实板回执](PREFLIGHT-R5-FIELD-RECEIPT-20261109.md)

## 最小软件改动

周期区间为 8 MHz 下按常见 Thumb 路径的量级估算。编译器内联、字符分布、抢占和缓存会改变结果；不能把这些区间相加，也不能代替 DWT 实测。1 µs 等于 8 周期。

| 位置 | 当前每字节工作 | 设计和估计 | 需要保留的语义 |
| --- | --- | --- | --- |
| `reply_byte` | 检查 4096 B 上限、写入字节和 NUL；二进制优先。文本行从第 13 字节起重复比较 `+CIPRECVDATA:`，行终点还辨认 URC、提示符和 OK/FAIL。 | 第 13 字节比较一次并锁存行类型；普通长行典型省一次调用和短比较，约 10–30 周期/后续字节。真正匹配头时约 20–60 周期；短行通常无收益。 | 仍拒绝 12 字节前缀后错误分隔符、空长度、超 256 B 和重复块；二进制中的 NUL、CRLF、CLOSED 仍视作载荷。只在现有依赖读取 `at_response` 的边界维持 NUL，须先审查所有调用。 |
| `await_reply` | 每次轮询先调用 `platform_poll`，再查停止和 UART 错误、出环、解析；空环也会重复轮询。 | 已排队字节先做小块处理，每 4 字节或约 100 µs 让路，两者先到为准。单个非重入调度入口按 20–60 周期估算，满块可摊掉约 15–45 周期/字节；实际业务回调成本单独用 DWT 除以调用数。 | 每字节继续检查截止、错误和停止；环空立即让路。CAN FIFO、IRQ 优先级、5 ms 服务节奏与诊断重入都要复验。 |
| `send_bytes` | 每写 DR 前跑回调和截止/停止检查；TXE 未就绪时继续调用回调；DATA 段更新已写长度。 | 先量 `tx_cyc - txe_cyc` 与 `svc_cyc` 的关系。DMA 或受控 TXE IRQ 可移除逐字节前台投递，典型省数十个前台周期/字节；DMA 设置、短帧和 IRQ 抢占成本待测。 | 部分发送必须保留准确阶段和写入长度，禁止重送未知 MQTT 半帧。长帧必须继续推进 CAN，串口发送终态仍由 AT 和 TCP/MQTT 边界分别确认。 |
| `rx_step` | TX 侧按 TXE 推送一字节；RX 侧从环取一字节并复用 `reply_byte`，终态还解析长度或搬运 ≤256 B，调用方每轮先跑服务。 | 先共享前缀锁存；按已有单 owner 用小块消费已有环字节，约可省一轮入口和服务派发，量级 15–45 周期/后续字节。终态解析与数据搬运按事务摊销。 | `CIPRECVLEN` 到 `CIPRECVDATA` 的状态、空读 5 ms 退让、字节预算、读写 owner 和出错后的 unsync 保持一致。 |

[DWT 插桩与 USART3 路径](../../../gateway/mqtt/src/platform.c) · [现有 CAN 与业务回调](../../../gateway/b5/network_main.c)

## USART3 TX DMA

RM0090 的 DMA1 请求映射支持 USART3_TX 在 Stream3/Channel4。该方案可以和现有 SPI3/I2S3 RX 的 Stream0/Channel0 并存；同一 DMA 控制器仍共享仲裁和总线。Stream3/Channel0 的 SPI2_RX 和 Stream3/Channel3 的 I2S2_EXT_RX 都会与拟议 USART3_TX 争用同一流，若未来切换到这些音频方案，必须改资源分配或保留 IRQ 发送。 [STM32 RM0090 DMA1 请求映射](https://www.st.com/resource/en/reference_manual/rm0090-stm32f407-advanced-armbased-32-bit-mcus-stmicroelectronics.pdf)

| C 侧功能 | 当前实现 | 拟议占用及约束 |
| --- | --- | --- |
| ESP USART3_TX，PB10 | TXE 轮询 | DMA1 Stream3 / Channel4，普通模式，字节宽，固定外设地址，源位于 DMA 可达 SRAM。 |
| ESP USART3_RX，PB11 | USART3 RXNE/错误 IRQ + 8192 B 环 | 保持 IRQ。若以后单独研究 RX DMA，DMA1 Stream1 / Channel4 是 RM0090 候选。 |
| INMP441，SPI3/I2S3 RX | DMA1 Stream0 / Channel0，双缓冲半字，10 ms 块 | 维持已有 DMA 与 SRAM staging。PCM 长缓存位于 CCM，USART DMA 也不可直接从 CCM 取数据。 |
| TTS USART2，PA2/PA3 | RX IRQ、TX 单步，9600 | 保持现有实现；USART2 的 DMA1 Stream5/6 Channel4 不分配。 |
| 双 bxCAN 与 USART1 控制台 | CAN RX FIFO IRQ，控制台轮询 | 无 DMA 资源占用。 |

[麦克风 DMA 与 PLLI2S](../../../gateway/microphone/bench_main.c) · [TTS 串口](../../../gateway/voice/tts_uart_port.c)

设计上先迁移固定生命周期的 MQTT 数据段。用 DMA1 Stream3 IRQ 或主循环取 TC/TE 状态，发送等待仍按现有绝对截止与停止门控推进服务。DMA TC 表示最后一个字节交给 DR，等待 USART TC 才能声明线路发送完毕或允许切速。超时、硬停、DMA 错误要先禁 DMAT、停止 Stream 并核对 EN 清除，记录 NDTR 与 TC 状态。NDTR 只能推算交给外设的字节，最后在 DR 或移位寄存器中的字节状态需单独标记。无法证明完整时锁存 unsync，禁止新命令或重放未知半帧。短 AT 命令可保留轮询，DMA 源在完成前保持有效。实测需覆盖与 I2S 同时运行、两个 CAN FIFO 高水位、停止传播、迟到 SEND OK 和归档恢复。

## 168 MHz 可行性

建议作为独立候选研究。HSE 8 MHz 用主 PLL 的 M=8、N=336、P=2 得到 SYSCLK 168 MHz；Q=7 为 48 MHz 域提供候选。AHB /1、APB1 /4、APB2 /2，分别为 168、42、84 MHz。正常供电范围内需按 RM0090 配置调压档位和 Flash 等待状态；2.7–3.6 V 下 168 MHz 对应 5 WS，先配置再升频。保留 HSE、PLL、时钟切换超时和安全失败路径。 [STM32F407ZG 数据手册](https://www.st.com/resource/en/datasheet/stm32f407zg.pdf) · [STM32 RM0090 时钟与 Flash](https://www.st.com/resource/en/reference_manual/dm00031020-stm32f4-series-reference-manual-stmicroelectronics.pdf)

| 项目 | 设计值或改动 | 必须重做的验证 |
| --- | --- | --- |
| 启动时钟 | `SystemInit` 当前直接切 HSE。改候选时按时钟树设置 PLL，`SystemCoreClockUpdate` 解码新 SWS/分频；替换硬编码 8 MHz 启动诊断。 | 上电、Reset/Go、晶振及锁定失败、回退、寄存器读回和独立频率证据。 |
| USART1/3/2 | OS16 下 USART1 84 MHz / 115200，BRR=729（0x2D9）；USART3 42 MHz / 115200，BRR=365（0x16D），/230400，BRR=182（0x0B6）；USART2 42 MHz / 9600，BRR=4375（0x1117）。将 R6 切速表的 8 MHz 假设改成核验后的 PCLK1。 | 初始串口、动态切速、实际位宽、TC 守护、ESP/TTS/控制台长时间错误与恢复。 |
| bxCAN 500 kbit/s | 42 MHz 档 `6 × (1+11+2) TQ`，采样点 85.71%；原 8 MHz `1 × (1+13+2) TQ`，87.50%。两档标称速率一致。 | 重测双 CAN 全负载、位采样容差、FIFO、总线错误/恢复、五板并发和 ACK。 |
| SysTick 和定时器 | SysTick 1 kHz 重装值从 7,999 改为 167,999。APB1 分频后的通用定时器时钟 84 MHz，APB2 定时器时钟 168 MHz。C 的网络业务时基由 SysTick 提供；盘点候选涉及的定时器、忙等和 DWT cycles→µs 换算。 | 核对 1 ms 节拍、420 秒硬停、5000/90000 ms 期限、延迟和回绕；板间时钟不作连带变更。 |
| I2S/PLLI2S | 当前音频初始化遇主 PLL 开启会失败。由统一时钟入口提供 PLLM=8，避免音频代码改共享 PLLM。PLLI2SN=256、R=5，I2S 时钟 51.2 MHz；I2SDIV=25、ODD=0、64 BCLK/帧得 16 kHz。 | I2S BCLK/WS、10 ms DMA 块、采样连续性、语音同 CAN/网络并发及错误恢复。 |
| 插桩与启动耗时 | DWT 周期时长按 168 MHz 换算，32 位周期计数约 25.6 秒回绕。周期汇总应按相邻样本取模差，不能从一次最终快照推回全窗。 | 原始计数与墙钟对照、快照间隔、采样本身带来的 IRQ 和串口负载。 |

[现用时钟入口](../../../gateway/dual_can/system_hse.c) · [bxCAN 两档位时序](../../../gateway/dual_can/b4_bxcan.c) · [Arm Cortex-M4 TRM](https://developer.arm.com/documentation/100166/0001/)
