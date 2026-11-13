# AUTH-B-ECG-MATRIX-001 R1｜普通ECG60/90/120工程速率窗口

2026-10-22 Asia/Shanghai。负责人已明确授权接源采集排查，并已回复按ECG-PILOT卡完成电池/断USB/普通60及R红RA、L黄LA、F绿RL/N、LL/F空置、B供电/J-Link接回且无人/CAN。实板10秒短窗2598稳定帧、序号内缺口0/CH2近轨0、后段实板HR60有效；精确冻结C源Host回放末值60。该短窗不签正式PASS。

本卡在正式采集前提交，覆盖普通ECG60/90/120三档各2个有界窗口，合计最多6会话。当前60沿用负责人已确认的接线/源状态，不要求重接或重新提供J-Link资料。到90/120前必须收到负责人实际菜单设置完成回复并冻结对应source-record，不能先改参考数字再采。任一STOP/异常结束后不自动重试，也不自动进入下一档。没有RESP、人体、CAN/云或Flash写权限。

## 已冻结设备/工具

当前B/模块/单路供电/BOOT/接线/普通ECG电池源均与ECG-PILOT相同；不改导联/电源/JTAG跳帽。BIN SHA438a8120f6df06ce219cdc30c0e5b697ac0e993f98d5a80521b10361536ae3ae、完整Flash SHAf713277a50a5ec8d8a93317f412d5ab1b754e5d619918e57e9efe9dceef24cbb；原完整双备份/options与独立恢复副本不动。自研BIO_V2源码SHA3adca55c…保持不变。

入口supervise_readback.py --operation capture --seconds 92与capture_b.py。92秒为30秒预热+完整60秒评价+2秒尾裕量，避免第一诊断读数延迟使评价段不足60秒。仅增加采集时长选择，不改算法/引脚/寄存器。新受限capture-profile-r3-03.json SHA `4e298cf97e55ea8c7d01aa9509b54ef682256fcad6c9ba30cca835ec1cde1a7f` 绑定当次UID参考、Flash/options、BIN/ELF/符号/ABI、全部入口工具/解析器；旧02和已用源代码副本完整保留。

DLL9.86a固定SHA632d0d78…、无自动复位重试/升级、单探针/VTref3.0–3.6V、SWD1000kHz、关闭不go/保留DWT同前。每会话起止整片Flash各1MiB/options16B核SHA；无fault的Flash暂停点才初始go≤1；运行92秒读3072B槽块，目标约50ms，真实吞吐及每次区间留证，不假称实际都达到目标间隔。每10块另读120B诊断/48B统计/12B启动回读，非原子观测；不是运行中额外SPI RREG。

结束halt≤1，确认暂停后一次128KiB RAM，同一份取head/末127已发布槽，前后核暂停；Flash/身份/options校验后末尾go≤1。每会话总go≤2、halt≤1、reset0、Flash/options/GPIO/SPI配置写0，无源菜单控制或电源动作。普通SDK5s/Flash45s/RAM15s、会话240s独立监督，失败无自动恢复；状态注明Close前观察，会话间暂停不偷偷拼进窗口。

## 采前冻结工程判据

每窗以第一条实板诊断last_sample_ms为锚点，设备时间[+0,+30000)预热，[+30000,+90000)为60秒评价段；92秒原码/确认尾段必须覆盖整个评价区间。源参考为负责人确认的普通档名义60/90/120BPM；厂家校准误差未知，只评设置值一致性，不称医学准确度。

1. 60秒原码首末覆盖到边界±4ms；序号逐帧连续，无补点/跨启动拼接；源flags0，相邻设备时间1–8ms，CH2无|raw|≥8220835（约98%满量程）；多版本重复冲突不多数投票通过。起始pending只在评价区间外才不影响该段，原件仍保留。
2. 全窗观察init/spi/bad_status/overflow均0，主机观察平均采样率240–260SPS。此范围仅链路门，不是时基校准。
3. 评价段至少60条实板诊断观察，首条不迟于+31秒、末条不早于+89秒；**所有已记录观察** hr_valid=1且|HR−名义设置|≤2BPM。不把离散诊断点冒称连续原子实板逐拍流。
4. 冻结C源Host回放从首个保留帧重置初态，评价段逐样本均有效且同样±2BPM；明确标REPLAY，保存filtered/质量/候选与接受事件。回放不能代替第3条实板数据，不报逐峰漏检/敏感性，不宣称Host/ARM逐位完全一致。
5. 每档2窗均满足，且三档6窗/原未接源负例/身份权限/完整性均可追溯，才提出B2_ECG_HR工程速率通过。个别窗口通过不提前签阶段PASS。异常输入先定位，不改阈值造PASS。

分析入口analyze_capture_b.py --formal为纯离线；卡/采集/分析工具、profile及实际source-record SHA各窗开前冻结manifest。UID/Flash/RAM/原码/回放CSV/源记录只存受限field-r3，Git仅脱敏摘要/哈希/测试。I导联绝对幅值不校准；RLD只证明本次接线/工作点可用，不外推所有负载兼容。CH1/RR不作动态阻抗验收；RESP仍待电极对/ΔΩ定义及独立卡。
