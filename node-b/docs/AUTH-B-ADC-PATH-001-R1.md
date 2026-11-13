# AUTH-B-ADC-PATH-001 R1｜零DRDY路径只读诊断

2026-10-22 Asia/Shanghai。依据负责人既有采集排查指令。本卡在访问前展示；BOOT-001已实际核PC080001A0/MSP20002F30并启动BIO_V2，ID/配置真实启动回读符合预期，init_errors=0；5秒irq/captured/delivered/samples全0。该失败原件保留，不归因算法。

仍为当次UID绑定B，J5供电开关负责人确认打开，J-Link仅调试，BOOT跳帽不动，模拟器/人体/CAN不接。候选/完整Flash身份与BOOT-001相同，无其他写入者。固定DLL及连接策略、VTref/单探针门沿用READBACK-R2。

入口supervise_readback.py --operation path和adc_path_b.py，卡/源码SHA冻结。额外明确允许SDK SetSkipDebugDeInit=1：固件以DWT执行SPI微秒延时，默认Close清DEMCR.TRCENA会干扰应用。该策略已脱机解析通过；不使用本版本未确认的SetDbgPowerDownOnClose。保留调试使能可能增加低功耗电流，不把本卡当低功耗测试。此项是调试清理策略变化，不宣称完全不影响目标调试状态。

只读身份与DHCSR，固定BIO诊断120B/ADS统计48B/启动RREG缓存12B（地址同PRECHECK-001），及s_ready 0x20000024/1B。附加下列寄存器每次4B，三轮约0.5秒间隔：

- GPIOA MODER/PUPDR/IDR/ODR/AFRL：0x40020000/0C/10/14/20。
- GPIOG MODER/PUPDR/IDR/ODR：0x40021800/0C/10/14。
- SPI1 CR1/CR2/SR：0x40013000/04/08；不读DR，不发SPI命令。
- EXTI IMR/RTSR/FTSR/PR：0x40013C00/08/0C/14；不清pending。
- SYSCFG_EXTICR1 0x40013808；NVIC ISER0/ISPR0/IABR0：0xE000E100/E200/E300。
- RCC AHB1ENR/APB2ENR：0x40023830/44；DWT CTRL/CYCCNT：0xE0001000/04；DEMCR 0xE000EDFC。

读取输出锁存/输入电平仅代表MCU端，不冒充端到端通断或模块端测量。活动RAM/寄存器非原子，原字节、状态和IO顺序留受限目录。无halt/reset/go/Flash或配置寄存器写，无改线/接源/供电动作；任何身份/ABI/运行异常立即STOP。SDK每次5秒/全会话180秒独立监督，无自动重试恢复。成功或STOP即结束。
