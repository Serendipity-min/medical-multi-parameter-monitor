# RR五档各三次：负责人授权B端工程批次

负责人明确选择“按图完成RR12/15/18/24/30各3次独立采集”，并确认B/C断电全暗、C USB及J-Link电脑USB拔出、黄L已LL、R_RA/F_RL、J-Link板端B、CAN不变；SKX电池且充电USB断开，非人体呼吸波形，波形周期30（与主RR分开）、1.5R、apnea0，首档RR12。当前仅准备，一次上电确认后才连接。

授权计数15，每run单独nonce/输出/冷启动人工确认/单次父worker claim/零重试。一次冻结公钥pin与15张有限run的nonce SHA，私钥仅Host内存，按预登记顺序逐场形成当期site/cold和签名；不得提前把未来现场记录填成已完成。前场采集或RR速率评价失败即停止，不签后场、不自动退还次数。源码/工具/commit/tree在整个批次不变，阶段结果先写EFS，批次结束后再写Git，保持每个worker入场工作区干净。

顺序复用M0矩阵：第1轮12→15→18→24→30；第2轮30→24→18→15→12；第3轮18→30→15→24→12。每次独立断电全暗再上电，不能把一段连续记录切三片作重复。只需回复当前档已上电/条件一致，不用报秒数或120秒抢签；每卡Host自动记录一小时起跑有效期。

沿用B41012、原采集器/评测器/ABI：45s预热+120s评价，120固定1Hz槽最早原生观察；正确有效≥118/120，所有已观测有效RR误差≤1/min。CH1/CH2均保留250Hz原码和原seq/IRQ/cycles/status/flags，RESP50仅按seq%5派生。Host I/O180s/会话260s/父265s，预留20s收尾；STOP、身份/full/options、只读地址、原生错误、ROM/HALT门保留。15项受影响离线范围/菜单/签名/判据测试exit0，旧E120卡CLI实际exit2；不重跑已完成历史矩阵。

RR评价仅RR_RATE_SUBFUNCTION，HR真值SOURCE_UNKNOWN/ROOT_CAUSE_UNRESOLVED。HR有效位、数值、观察簇与CH2原码照实保留，不按RR模式屏蔽HR，不伪造Lead-Off、不改算法/阈值、不修改冻结评测器。HR未独立标注前，RR整窗不能宣称完整PASS。若仅RR速率和完整性通过，另报OWNER_AUTHORIZED_RR_RATE_SUBFUNCTION_PASS。

拓扑沿用只读取B、C原J5/CAN作背景、C USB断开；不宣称B/C电气隔离。用户负责现场STOP/保全/断电，已知情接受SDK原生Open/Connect/Close及在途/强杀剩余风险；Close后态UNKNOWN，SDK UNRESOLVED继续保留。PI根None、原PI_trust_root_verified及field_scope_PASS不改，本批次不是PI独立签署验收。

本轮不操作C串口/云端、不发B5START、不Reset/Halt/Go/Flash。ECG本轮60/90/120各1次合格，不能算各3次；旧E3旧固件/周期20的RR12/18/24各2次仅历史参考，不能替代本版周期30重复。旧R6 RR15 RR15数值正常但HR事件导致正式exit3，保持NOT_PASS；源QRS UNKNOWN，不推断CH2无真QRS。

云端策略：先完成本M1的RR多率矩阵。已有独立ECG60和桌面TEMP的端到端工程PASS可复用；RR15已做过含云链路但整窗失败。之后若批准，按M2预登记选择R12/R30端点各一次（及所需ECG90/120）做B→C→Broker→Backend→WSS一致性；不把本B端通过替代端到端验收，不因“增加云”跳过源真值。当前云授权次数0。

完整RR纯预热+采集15×165=2475s=41分15秒，不含预检/人工切换/收尾。输出受限EFS定位node-b/build/m1-owner-rr-batch-pointer.json；旧失败和源码SHA保留。
