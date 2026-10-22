# AUTH-B-START-PULSE-001 R1｜未接源单次START脉冲诊断卡

2026-10-22 Asia/Shanghai。承接负责人已授权的B板下载、采集排查任务；本卡在任何写GPIO动作前提交展示。最新现场：模块丝印ADS1292_V2.0，电源灯亮，J2接开发板5V并共GND，J1空置；负责人仅见J1/J2，不能据图中J3存在假定实物CLKSEL。START→PG15、DRDY→PA3负责人确认；模拟器、人体、CAN均未接。

固定候选及当前完整Flash SHA同INSTALL-001/BOOT-001；真实UID/options绑定READBACK实际原件。J5既有供电开关打开，J-Link仅调试，BOOT跳帽不动。SDK9.86a固定DLL SHA/单探针/参考电压/无自动复位重试/关闭不go策略同READBACK-R2，并沿用ADC-PATH的SetSkipDebugDeInit=1保留DWT。

入口supervise_readback.py --operation pulse与start_pulse_b.py，SHA随卡manifest冻结。先核身份/ABI、运行态、s_ready=1、init_errors=0、PG15配置为输出且ODR高。若已有DRDY计数则不发脉冲，记录PULSE_NOT_NEEDED；不冒称链路验收。

**唯一运行期目标写：**SDK JLINKARM_WriteU32 对 GPIOG_BSRR `0x40021818` 先写 `0x80000000`（仅复位PG15），确认PG15输出锁存低；保持至少20ms；再写 `0x00008000`（仅置位PG15），确认输出锁存高。实际脉宽含主机/USB延迟，原IO与时序留证，不称精密20ms。最多各一次、共两次32位GPIO写，不写ODR整字，不改其他GPIO、ADS寄存器或SPI。MCU不halt/reset/go。

这会暂停/重启ADC转换，是明确列出的非只读诊断动作。之后固定BIO诊断120B/统计48B/启动RREG缓存12B（同PRECHECK地址）各11次、约5秒；另读PA3和PG15锁存状态。原码只在断开输入下保留末帧观测，不算HR/RR准确率。任何部分写失败或状态异常立即停止，不在finally自动补高/复位；若低后失败，报告START可能保持低，等待精确恢复卡。

无Flash/options写、无阈值修改、无接线/上断电/跳帽改变、无模拟器输出/人体/CAN/云操作。普通调用5s/会话180s监督，失败不重试。身份/工具/卡SHA不符不开会话。全部原件受限保存；成功或STOP即结束。若仍无DRDY，不能据此认证模块时钟/端到端通断，需要模块端测量或连接器证据，而不是继续盲写。
