# AUTH-B-REPROBE-001 R1｜负责人开关更正后的单次探测

2026-10-22 Asia/Shanghai。负责人明确：“我好像没有开启开关，重新探测一次”。据此提交本卡并只执行一次重新探测；负责人打开B既有J5供电开关，不增加第二路电源。J-Link仅调试，导联/模拟器/人体/CAN仍断开，不改跳帽。

入口supervise_readback.py --operation fault和更新后的fault_snapshot_b.py；卡/工具SHA冻结到当次manifest。仍使用固定9.86a DLL SHA632d0d78…、单探针、3.0–3.6V VTref先行门、SWD1000kHz、无自动复位重试/固件升级/关闭go策略。未满足参考门立即停止，不启用探针供电。

沿用FAULT-001 R1的身份、故障状态、已HALTED才读核寄存器和128KiB RAM一次只读范围；另只读SYSCFG_MEMRMP 0x40013800、GPIOB_IDR 0x40020410、RCC_CSR 0x40023874各4B，以及启动别名0x00000000和Flash0x08000000各64B。用于区分ROM/Flash映射与启动状态；GPIOB读数不是BOOT0实测。

无halt/reset/go/Flash或options写、无下载、无接源、无CAN/云操作。SDK普通5s/RAM15s/总180s监督，异常即停止。真实UID与RAM/向量原件留受限目录，仅公开脱敏结果；原故障快照和成功烧录证据不覆盖。本次成功或STOP即失效。若已经运行，核寄存器不读，活动RAM只作非原子观测。
