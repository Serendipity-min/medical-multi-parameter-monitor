# AUTH-B-BOOT-001 R1｜现有候选的一次受控启动核验

2026-10-22 Asia/Shanghai。负责人已明确授权重新下载/采集排查，且最新确认“刚才已打开，当前保持打开”。本卡据此在执行前展示一次必要启动核验；不重复供电/探针接线请求。

对象为当次备份UID绑定B，J5既有电源已开，J-Link仅调试；B0/B1负责人确认GND；CAN/导联/模拟器/人体均断开。重新探测实际VTref3300mV、DHCSR30003、VTOR1FFF0000、PC1FFF32EC、CFSR/HFSR0，别名向量与Flash向量一致。记录为ROM_PAUSED而非算法失败，原因尚未确认。

入口supervise_readback.py --operation boot及boot_check_b.py；卡/源码SHA冻结manifest。固定DLL/attach保护策略与READBACK-R2相同。身份/容量/RDP/options须匹配，且初态仍暂停。先只读整片Flash一次，SHA须 `f713277a50a5ec8d8a93317f412d5ab1b754e5d619918e57e9efe9dceef24cbb`；否则不复位。

明确设置SetResetType=0，最多一次SDK正常整器件reset（AIRCR.SYSRESETREQ，允许SDK临时DEMCR复位捕获），暂停下读回实际PC/MSP/XPSR。PC须0x080001A0（或别名0x000001A0），MSP须0x20002F30，与已核合同Flash向量一致。若入口仍在ROM或栈不符，立即停止并保留暂停，不发go，不手动改PC/MSP或BOOT，不再烧录。

仅入口通过，才go最多1次；保持同一会话等待3秒初始化，再按PRECHECK-001固定三个RAM区域各11次/5秒观察。检查实际启动RREG缓存、ABI与采样计数；断开输入不计算HR/RR准确率。保留原字节和活动RAM非原子性质。

无Flash/options写、无接源、无额外halt、无强制PC跳转、无电源或跳帽动作。普通5s/完整Flash45s、总180s独立监督，STOP/超时不自动恢复。成功/STOP即结束此卡；原ROM快照与烧录证据保持。
