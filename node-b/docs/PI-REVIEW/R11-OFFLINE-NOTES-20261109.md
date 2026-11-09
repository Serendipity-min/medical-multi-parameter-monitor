# R11 离线回执与设计

## WP-AD：拆分五板 `service()` 重活

W1 受限串口直接给出 `can_poll_cycles_max=50623`（8 MHz 下 6.328 ms）、`service_gap_max=10 ms`、`console_max=51 ms`、ESP RX 环高水位 32。`can_poll_cycles_max` 包围的是 `b4_hw_poll()`，`svc_max_cyc=53340` 包围的是整次回调，两项峰值没有同一时刻的关联证据。`console_max` 是单次控制台输出经过时间，期间等待 TXE 仍可推进服务。 [W1 实板回执](R10-W1-TLS-FIX-FIELD-RECEIPT-20261109.md)

现有 1.7 ms 是带快速返回成本假设的估算。`b4_gateway_tick()` 每次经过两个 CANopen 实例的 `CO_process`、RPDO 和四个节点的状态检查，即使无帧也有固定成本。`b4_hw_poll()` 每段都有邮箱、ESR 和链路处理，再按实际排队帧数调用 `b4_gateway_receive()`。入队发生在波形出批、标量和周期状态等边界。`field01_poll()` 有每次源活性检查、每 100 ms 的错误趋势判断和触发停止的路径。无音频构建的 `unified_audio_local_poll()` 是空内联。

分段 DWT 方案仅供后续测量镜像。维持原 5 ms 调度，分别累计快速返回、`b4_gateway_tick`、`b4_hw_poll` 固定段、每帧 `b4_gateway_receive`、嵌套 `mp_router_put`、`local_control` 和 `field01_poll` 的次数、周期及峰值。父段给包含值，逐段归因用减去嵌套的独占值。用静态桶按每次 poll 的实际出队帧数 0、1、2、3–4、5–8、9+ 汇总，并分别记录波形点、出批、标量、状态及时间同步事件。中断时间保留为实况开销，同时记录 IRQ 次数和周期作为解释；空对照先测 DWT 读数和记账本身的成本。仅在既有诊断时隙导出摘要。

零帧桶给出固定成本，同类帧桶的差分估计边际成本，含出批的样本单列。当前无法把约 0.9 ms 判给每帧。优化先看测量结果：若固定段占优，考察两段状态扫描及无变化的链路更新能否复用结果，保持心跳失效和状态事件的时点。每个 5 ms tick 省 50 µs 约释放 1% CPU。若帧段占优，先优化重复节点查找与队列访问，保持原始到达时间、每段预算和帧顺序；按约 370 帧/s，每帧省 50 µs 约释放 1.85% CPU。批处理不得推迟或合并同一 RPDO 槽的处理，现有逐帧调用用于避免数据覆盖。以上节省量是换算，实际收益待插桩。

## WP-AE：F-P115 构建门控

Windows 用 `--field01 --no-audio --transport-profile --esp-passthrough` 且省去 `--esp-230400`，构建入口退出 2。`build_arm.py` 对 FIELD01 插桩组合要求 `args.esp_passthrough == args.esp_230400`，因此尚未生成 F-P115。该约束属于构建矩阵。没有 ARM 制品和 VPS 位级对照。W3 待后续放行；届时构建矩阵及冷启动、透传退出、错误锁存和 115200 保持路径需一起验证。

## WP-AF：USART3 TX DMA 方案

接入点仅为 `send_bytes()` 的 `ESP_AT_DATA` 分支，普通模式在收到 `CIPSEND` 提示符后进入，透传在通过时间预算和三连加号检查后进入。AT 命令、CRLF、透传转义和接收沿用现有实现。USART3 TX 使用 DMA1 Stream3 Channel4，与当前 I2S3 麦克风 RX 的 Stream0 分开。DMA 源必须在 DMA 可访问的 SRAM，整个传输期间保持有效。使用单次、内存到外设、字节宽度、内存递增，目的地址固定 USART3 DR。 [STM32 RM0090，DMA1 请求映射及 USART DMA 发送](https://www.st.com/resource/en/reference_manual/dm00031020-stm32f405-415-stm32f407-417-stm32f427-437-and-stm32f429-439-advanced-arm-based-32-bit-mcus-stmicroelectronics.pdf)

1. 沿用现有串口事务的绝对 deadline、业务与关闭余量、UART 错误门控和唯一写入者。启动前核对 stream 已关闭，清该 stream 的标志，配置 `PAR/M0AR/NDTR`，然后使能 stream 和 USART `DMAT`。等待期间继续调用 `platform_poll()`，由原 5 ms 节流决定重活频率。可先采用主循环检查标志，避免新增 IRQ 优先级竞争。
2. DMA 完成只表示最后一字节写入 DR，USART `TC` 才表示最后的停止位离线。两者都在原 deadline 内等待。普通模式成功后继续等待 `SEND OK`，透传成功后沿用原 MQTT 层；不把 DMA 完成当作 MQTT 送达。
3. STOP、deadline、USART 错误或 DMA `TE/DME/FE` 时先停 `DMAT`，再禁用 stream，并按原硬停止边界做有界确认。取 `NDTR` 记录写入外设的字节数。未观察到 TC 时不声称字节已完整离线。部分帧或边界无法确认时，普通模式沿用 `unsync`，透传沿用 `PASS_UNKNOWN`，终止本事务，按既有冷启动规则处理。失败路径不可从头发送同一片段。若 stream 无法确认停下，保持独占，不交还或复用缓冲区。
4. 验收覆盖启动前拒绝、TC 迟到、STOP 与完成同周期、各类 DMA 错误、已发前缀及故障后的命令禁入。实测 CAN/USART 错误、TX 每字节耗时、最大服务间隔及 I2S 同时活动的仲裁；TX 指标拆分 DMA 等待墙钟与 CPU 开销。

按 W1 约 479 B/包，普通 115200 的 117 µs/B 有效发送约 56.0 ms。8N1 线速约 86.8 µs/B，对应 41.6 ms，理想节省约 14.5 ms/包。保留其余开销，122.7 ms/包降至约 108.2 ms，即约 9.2 批/s，仍低于 W1 约 10.44 批/s 的入队率。DMA 当前仅为设计，冻结镜像未加入 DMA。
