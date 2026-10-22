# AUTH-B-START-PULSE-001 R2｜同会话条件续跑及单次START诊断

2026-10-22 Asia/Shanghai。承接负责人已授权采集排查；本卡执行前展示。R1已STOP于NOT_RUNNING，gpio_write_attempts=0，实际没有发START脉冲。原件保持；不把该次STOP当脉冲失败。

模块/供电/引脚/未接源事实、候选/备份/工具身份、保留DWT策略、PG15两次BSRR写和5秒观测、其他全部禁止项均按 [R1](AUTH-B-START-PULSE-001-R1.md)。新增唯一权限与ADC-PATH-R2相同：连接后若已HALTED，保存DHCSR及实际PC/MSP/XPSR，且只有PC在合同候选范围且CFSR/HFSR均0、无LOCKUP，才允许go最多1次；不改PC/栈，不复位。不符合立即STOP且不写PG15。

将条件续跑、确认计数和必要START脉冲放同一会话；若DRDY已出现则跳过脉冲。仅IRQ仍0时执行R1的PG15低高各一次。会话间暂停原因仍未确定，不冒称SetSkipDebugDeInit已经消除所有运行影响。

无halt/reset/Flash/options/SPI配置写、无接源/改线/上断电动作；SDK5s/会话180s监督。脉冲失败不追加补写；成功/STOP即结束。末态注明Close前观测，不把下次连接暂停混入本窗口ADC判断。
