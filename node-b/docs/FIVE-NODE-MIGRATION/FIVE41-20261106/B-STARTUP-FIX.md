# ECG五板预检停止与B启动竞态修复

本次在发送C的B5START之前停止，预热和300秒评价均未开始。不能据此签两段41Ω的传输通过或失败。原始事务、镜像核对、工具返回和接收端证据保留，未自动重试。负责人随后确认全部断电；异常发热/复位/屏状态未补充，记未知。

B旧实装40,032B与冻结SHA匹配，CPU无Fault、Flash运行态正常，三次PC样本分别位于BCan_Interrupt+6、BCan_Interrupt、CAN1_RX0_IRQHandler+6。两次BIO处理计数没有推进，因此预检拒绝启动C。旧观察器未将这两份BIO/ADC/CAN原始和解码快照落盘，不能据此断言ADC原始采集也已停住；该取证缺口已补。

真实B驱动在CO_CANmodule_init内启用接收中断，而应用的running直到后续协议栈初始化完成才置1。邻板若已发帧，FIFO接收中断可在running=0时反复进入并直接返回，主循环无法完成初始化和消费ADC队列。三次现场PC与此路径吻合，但本次没有读取running及FIFO/IER的现场值，故现场归因仍待修复后的实板快照确认。该代码缺陷自身已由真实驱动和SPL寄存器替身复现：旧版原生退出23，256次早到IRQ；修复版冷启动与通信重建原生0，两个待收帧均正常交付，没有提前清FIFO或补造数据。

修复只将CAN中断使能推迟到CO_CANsetNormalMode，应用此时已就绪。不改变ADC、BIO、屏、采样率、CAN位率/PDO/队列、C/云端调度或任何超时。新B ARM构建原生0、0错误0警告，BIN40,040B；147份编译输入仅B4/CO_driver.c有变化，其余146份一致。原码槽、处理队列、BIO、ADC、时钟、CAN七个RAM符号地址与长度不变。

本次修改后的B观察器保存两次预检原始及解码快照后再作判断；保留原采样推进和完整性判据。已冻结新B镜像的精确长度/SHA，旧40032B镜像不能进入新观察窗口。原失败事务的工具SHA和已执行副本不改写，新事务独立准备，未启动。

B现已安装并通过1MiB完整回读核对，仅写sector0/1/2，配置/Options及区外保留，原生退出0。随后仅B上电进行约2秒只读本地检查：BIO、ADC IRQ、捕获、交付均增加520点，设备跨度2080ms，250SPS，长间断和ADC队列溢出增量均0，Close完成；不发Halt/Reset/Go或写Flash。因其余节点断电，CAN ESR非零原样记录，不能判本地CAN链路通过。见[B-STARTUP-INSTALL-RESULT.json](B-STARTUP-INSTALL-RESULT.json)及[B-STARTUP-LOCAL-CHECK.json](B-STARTUP-LOCAL-CHECK.json)。C计数候选仍是此前已验证的实装，不需要重刷。D当前实装引用旧共享驱动，本轮没有重建或重刷D；其它节点的启动行为继续按现场记录，不能从B修复推断全部节点已通过。

当前仅B上电、J-Link在B，其余板断电。下一步按负责人上电回执先断电再冷启动五板，启动新的ECG事务；不自动复位、重跑或提交/push。

见[B-STARTUP-FIX.json](B-STARTUP-FIX.json)、[ECG60-PREARM-STOP.json](ECG60-PREARM-STOP.json)和[B-STARTUP-INSTALL-PLAN.json](B-STARTUP-INSTALL-PLAN.json)。
