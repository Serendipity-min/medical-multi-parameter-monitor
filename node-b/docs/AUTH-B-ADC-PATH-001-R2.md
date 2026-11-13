# AUTH-B-ADC-PATH-001 R2｜会话间暂停与零DRDY核验

2026-10-22 Asia/Shanghai，负责人已授权恢复候选及采集排查。R1会话已停止，实际NOT_RUNNING，没有读取路径数据；原件保留。本卡展示后执行一次，替代本次R1但不覆盖历史。

身份/供电/未接源状态、SDK固定SHA和参考门、SetSkipDebugDeInit=1策略、读取地址及三轮间隔全部与 [R1卡](AUTH-B-ADC-PATH-001-R1.md)一致，另增加CFSR0xE000ED28、HFSR0xE000ED2C、VTOR0xE000ED08各4B和已暂停时SDK实际PC/MSP/XPSR读取。

R1在实际设置保留DWT策略后发现目标已暂停。当前须区分先前默认关闭调试清理造成的暂停与应用自身故障，不能直接认定算法或硬件失败。先保存DHCSR；LOCKUP停止。若已HALTED，仅在PC位于已校验候选 `[0x08000000,0x080062C4)` 且CFSR/HFSR均0时，明确允许go最多1次，保留当前PC/栈，不复位、不改PC/寄存器。PC在ROM/其他区域或存在fault则立即STOP且不go。

确认运行后执行R1相同GPIO/EXTI/SPI/ADC只读检查。无halt/reset/Flash/options写、无接源/改线/跳帽/供电动作，普通5s/会话180s独立监督，无自动重试。关闭禁止额外go并保留调试使能。记录会话结束前状态，不把Close前确认冒称Close后独立观测。成功/STOP即结束此卡。
