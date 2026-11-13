# AUTH-B-PRECHECK-001 R1｜BIO_V2未接源链路检查

2026-10-22 Asia/Shanghai。本卡承接负责人“如果没有问题，就开始链接模拟源，进行采集，排查分析原因”和“重新烧录下载即可”的明确继续执行指令，在实际读取前展示。模拟器暂不连接；只做已授权采集的必要输入前检查。

同一B板/J5单路供电/J-Link仅调试/B0与B1均GND、CAN与人体及模拟器断开。INSTALL-001已实际成功：前2扇区恢复合同候选，整片1MiB回读逐字节一致，其他扇区/options不变，h1/reset1/go1，末态RUNNING。候选BIN SHA438a8120…，安装后完整Flash SHA256 `f713277a50a5ec8d8a93317f412d5ab1b754e5d619918e57e9efe9dceef24cbb`。原Flash双读SHA69d9efb0…及独立恢复副本均保留。

入口supervise_readback.py --operation precheck及precheck_b.py，绑定本卡SHA、工具SHA、当次真实UID/options参考。DLL/连接策略/VTref门/单探针/1000kHz与READBACK-R2相同；关闭不go、禁止自动复位重试/探针升级。读取范围仅为：

| 对象 | 地址/字节 | 次数与用途 |
|---|---|---|
| 设备/状态 | READBACK-R2身份固定白名单 | 开始/结束身份保护核对及DHCSR运行/复位检查 |
| 完整Flash | 0x08000000 /1048576 | 一次，核安装后完整SHA；仅内存比较不替换原备份 |
| BIO_V2诊断 | 0x20001AE4 /120 | 11次，约0.5秒间隔、5秒，核tag0x324F4942及ABI2/计数 |
| ADS统计 | 0x2000018C /48 | 同11次，核捕获/交付推进及错误 |
| 启动RREG缓存 | 0x200001BC /12 | 同11次，真实启动读回；不是本窗口新发SPI RREG |

预期ADS ID73、CONFIG101、CONFIG2E0、LOFFF0、CH1/CH240、RLDEC、LOFF_SENS00、RESP1EA、RESP203、GPIO配置位0C；LOFF_STAT未回读为FF，GPIO低2位是输入电平不要求为0。名义250SPS，5秒计数/主机区间估计240–260仅为链路检查，未做时基校准。init/spi/bad_status/overflow任何非零、ABI/Flash/UID不符或不运行均FAIL/STOP。不因未接源HR显示数值就判准确；输入固定OPEN_UNKNOWN。

各次活动RAM读取不原子，保存原字节、真实IO顺序和主机区间。无目标写、halt/reset/go、擦除/烧录、寄存器配置、模拟器连接或导联操作，不改阈值/供电/跳帽。本次卡不允许长波形采集。

普通调用5s/整片读45s，全会话180s、独立进程监督；STOP/超时终止，无自动恢复或重连。仅允许清读既有RESET粘滞基线，窗口内新增RESET/HALT/LOCKUP立即停止；原件和失败只增不删。成功或停止即失效。通过后另卡准备ECG接源与采集，RESP不在本卡范围。
