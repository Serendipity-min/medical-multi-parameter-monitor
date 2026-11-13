# PREC P0 S0/D0 现场结果 R1

2026-10-23。S0已按负责人批准执行一次，无重试；D0已取得负责人观察回报。**CPU_ROOT_CAUSE_UNRESOLVED**，未签根因关闭，未进入P1。

## S0：ROM异常再次被观察，映像未丢失

三次连接后快照的VTOR均为`0x1FFF0000`；15个运行PCSR样本均在`0x1FFF32EA`–`0x1FFF32F2`，见[完整派生摘要](../evidence/B-PREC-001/state-s0-result.json)。DHCSR均`0x01010001`，本层未见S_HALT，故没有为读取核心PC另行暂停；本轮使用PCSR采样，真实核心R15未读取。不得把采样PCSR说成暂停核心寄存器读值。

Flash全片SHA `f713277a50a5ec8d8a93317f412d5ab1b754e5d619918e57e9efe9dceef24cbb`，options SHA `52d5979da03bd7be45e385920ec7d5901793bab3f6bc1daa0c1c1997f9e91687`，均与冻结候选一致。BIO诊断ABI无效，未取得应用采样推进证据。这里成立的是CPU执行位置异常且Flash仍完整，不能描述为算法丢失。

RCC_CSR均`0x0E000000`，CFSR/HFSR均0；这些粘滞/当次标志不能给出进入ROM的时刻或唯一原因。SYSCFG时钟未开，不据MEMRMP读0推断BOOT锁存。DWT计数在三次快照中不变也只作观察，不单独解释ROM机制。

实际Open/Connect/Close各1；显式reset/halt/go/目标数据写均0。109个调用有成对逐调用日志；继承的Close另有独立心跳开始/结束和SDK OnDisconnectTarget记录，未经过相同序号日志，不能把其缺席误计成Close=0。全程约40.672秒，worker退出3、监督器1、调用方1：取证完成，但当前运行状态不符合应用推进要求，真实非零退出保留。既无第二连接，也无补复位/补go；Close后的状态未知。

该结果是一次连接后的异常观察，仍不能证明连接前已经在ROM，或证明Connect/Close无隐式电气副作用。原始UID、Flash、RAM、SDK/IO/心跳/调用日志及回执仅在EFS加密私有目录，公开文件仅摘要与[SHA索引](../evidence/B-PREC-001/state-s0-private-file-index.json)。

## D0：没有观察到独立应用输出

负责人已批准单次拔除B端JTAG、其他条件不变的D0卡，随后回报：屏幕无波形，电源灯无变化，断开后看不到波形变化，除此暂无异常。后续M0授权答复明确确认“JTAG已拔下”。D0回报没有给出单独的0/10/30秒数值，不能补造时间序列。

D0没有执行启动动作，没有调试器调用，不测PC/VTOR；静态画面不能说明断开后CPU一定仍在ROM，也不能证明已进入Flash应用。独立启动证据记`INDEPENDENT_STARTUP_EVIDENCE_NOT_ESTABLISHED`。现场原话与授权留在私有目录，派生记录见[结果](../evidence/B-PREC-001/disconnect-d0-result.json)。

## 后续边界

M0另获单次人工实体RESET授权，负责人随后回报按RESET仍无可见反应，并补充屏幕接线。串口路由与当前候选不匹配的线索使该屏幕通道尚不能用于判定启动状态；详见[屏幕通道复核](PREC-P0-HMI-PATH-AUDIT-R1.md)。不补造5/15/45秒读值，不签根因关闭。后续任何SDK连接、冷启动、测量或改线需另卡。现阶段不改阈值、不烧录、不切源、不开展CAN。
