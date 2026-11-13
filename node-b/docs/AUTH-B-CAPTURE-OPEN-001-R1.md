# AUTH-B-CAPTURE-OPEN-001 R1｜未接源10秒采集器实板核验

2026-10-22 Asia/Shanghai。负责人已授权B板采集排查；本卡在读取采样前展示。最新PRECHECK-R2同会话5秒观察249.94985SPS、1246帧增量，所有SPI/格式/初始化/溢出错误0。首批129帧在PG15脉冲前已经出现，实际GPIO写0；不将未执行脉冲宣称修复。

对象为READBACK当次UID绑定B，STM32F407ZG/1MiB/RDP0；候选BIN SHA438a8120…、当前整片Flash SHA `f713277a50a5ec8d8a93317f412d5ab1b754e5d619918e57e9efe9dceef24cbb`；原完整Flash双备份SHA69d9efb0…与options及独立恢复副本不动。J5既有供电开关打开，J-Link仅调试，模块J2接开发板5V共GND，START→PG15/DRDY→PA3；模拟器/人体/导联/CAN均断开，输入OPEN_UNKNOWN，不计算准确率。

## 入口与固定绑定

入口supervise_readback.py --operation capture --seconds 10及capture_b.py。真实UID/options参考、候选BIN/新ELF/符号表SHA、31项ARM ABI布局、解析器及全部入口工具SHA绑定在受限capture-profile-r3-02.json，SHA256 `9d17280c4d918f50a3b3d0ce344bff98bf0072fdd20f5db6bd9547fcb305a6ab`。源状态source-open-r3-01.json明确无已知输入，随卡执行manifest冻结其SHA。卡SHA由命令/回执绑定。

DLL9.86a x64 SHA632d0d78…及单探针/VTref3.0–3.6V/SWD1000kHz/无自动复位重试/关闭不go策略沿用READBACK-R2；保留DWT调试使能策略同ADC-PATH。当前会话间暂停原因未确定，不把连接称为零扰动。

## 精确读取和运行状态变化

1. 身份/保护读取白名单同READBACK；开始和结束分别真实读取整片Flash1048576B及options16B核SHA，禁用Flash缓存，UID/options须匹配。
2. 初态若已暂停，仅实际PC在候选Flash范围且CFSR/HFSR0、无LOCKUP时go最多1次；不改PC/栈、不复位；否则STOP。
3. 确认运行后，连续10秒约50ms间隔读槽块0x20001F30/3072B；逐块原样追加文件，每次IO偏移/长度/主机区间/SHA留证。每约0.5秒另读诊断0x20001AE4/120B、统计0x2000018C/48B、启动RREG缓存0x200001BC/12B，各自保留原字节，不宣称原子一致。
4. 运行窗口结束后halt最多1次；确认HALT且无新RESET/LOCKUP，单次读完整RAM `[0x20000000,0x20020000)` 131072B，读前后核稳定暂停。尾段head只取同一RAM偏移0x140、slots只取0x1F30，认证最后已发布127槽，不拼接独立head观察。
5. 仅尾段与最终Flash/身份/options均通过才go最多1次，确认运行。总go最多2、halt最多1、reset0、Flash/options/GPIO/SPI配置写0。失败或STOP无额外恢复/重连。
6. 断开探针会话后离线解析：重复一致版本或已确认尾段才能导出；3:2多版本重复冲突不投票通过，单读pending不补点，跨复位不拼接。原槽版本和CSV私有保存，filtered/逐峰事件只能另做标注为REPLAY的精确C回放，本窗口不伪称实板逐拍事件日志。

普通SDK5s、完整Flash45s、RAM15s；独立监督240秒总上限（包含原件导出），无无限等待。原码/UID/完整Flash/RAM/SDK日志只在受限本地，不入Git；公开摘要保留失败。该10秒仅核验采集器与未接源负例，不替代已知ECG60/90/120各60秒×2，也不解除RLD/源电气准入。成功/STOP即失效，接源另卡。
