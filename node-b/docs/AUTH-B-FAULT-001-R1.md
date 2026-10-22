# AUTH-B-FAULT-001 R1｜未接源停止原因只读快照

2026-10-22 Asia/Shanghai。负责人已授权恢复固件及采集排查。本卡在执行前展示，承接PRECHECK-001实际NOT_RUNNING异常，只读保存原因，不再次下载或恢复运行，不重复已获供电/探针接线确认。

对象仍为READBACK实际UID绑定的B，J5既有供电/J-Link仅调试、B0/B1接GND；CAN/模拟器/人体断开。候选整片校验已经通过，原完整双备份不动。SDK9.86a x64固定SHA及attach guard、单探针/参考电压/SWD1000kHz/关闭不go均沿用READBACK-R2。

入口supervise_readback.py --operation fault与fault_snapshot_b.py，卡SHA与源码SHA冻结。只读READBACK的身份/保护/DHCSR地址；追加SCB ICSR/VTOR/SHCSR/CFSR/HFSR/DFSR/MMFAR/BFAR：0xE000ED04/08/24/28/2C/30/34/38各4B；DEMCR0xE000EDFC及DWT_CTRL0xE0001000各4B；RAM `[0x20000000,0x20020000)` 131072B一次。不改写W1C故障状态。

先记录DHCSR。只有已HALTED才通过SDK取寄存器列表/名称并只读取R0–R15、PC/SP/LR、XPSR/MSP/PSP/CONTROL/PRIMASK/BASEPRI/FAULTMASK；不暂停运行中的CPU来取PC，不调用WriteReg。记录读取前后状态。活动RAM若仍运行则仅观测，不冒称暂停原子快照。

无halt/reset/go/Flash/options/目标寄存器写、无接源/改线/上断电；若意外状态或SDK错误即停止，无自动重试。普通调用5s、RAM15s、会话180s监督。原RAM/UID/SDK输出仅受限本地，公开只脱敏故障原因。卡成功/STOP即结束，不能把故障快照当成ECG采集或恢复授权。
