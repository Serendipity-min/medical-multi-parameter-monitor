# ECG60首场工程试验：主机白名单遗漏

**HOST_TOOL_ROOT_CAUSE_CONFIRMED；ECG60_ENGINEERING_NOT_RUN；NO_AUTOMATIC_RETRY。**

现场冻结595c5e21a90787ea9e43a47788ed7be111097941。授权来源为负责人直接授权，非PI独立签署。父/worker各实际exit1，review实际exit2；会话26.172s，唯一次数已消耗。Close尝试并返回，但目标后态UNKNOWN，SDK原生副作用UNRESOLVED。未生成window或blocks文件，没有45+120秒采集结果，不能报心率算法失败或ECG60通过。

## 已确认的因果链

1. 当前B身份与历史参考一致；完整Flash SHA256为9ff8133d06330a4b05cb15d26bfb51b6f7e1197014692c5267d178d744f4287d，options为52d5979da03bd7be45e385920ec7d5901793bab3f6bc1daa0c1c1997f9e91687，同次B41012映射链前置校验通过。这不证明全部硬件健康。
2. 采集器调用b4_runtime.snapshot，继而调用c_b4_readonly.snapshot。后者的SYSTEM包含FLASH_CR=0x40023C10；M1Link构造白名单只包含runtime_state_b.SYSTEM及手列寄存器，遗漏FLASH_CR。
3. 实际IO最后普通读为SYSCFG_MEMRMP=0x40013800；紧接着的FLASH_CR/4在BLink.read白名单检查处拒止，未进入SDK读取。该调用路径来自只读快照，不是Flash写入。
4. 离线只替换BLink原生初始化和传输边界，运行真实M1Link构造、真实BLink.read和真实c_b4_readonly.snapshot：未修补版本重现同一G3_B_READ_SCOPE，2项中1错误，进程exit1。故不是仅靠猜测地址得出的解释。

原21项采集回归使用FakeLink隔离设备，没有覆盖真实M1读取白名单与真实快照的组合；因此其通过未能发现本次遗漏。新增的两项专门覆盖该组合和相邻地址/错误长度仍被拒止。

## 最小修复与验证

M1Link.allowed_reads只新增0x40023C10:{4}。不放开邻近地址、8字节读取、任何写操作或其他SDK接口；不改算法、采样、时间、STOP/Close、原评测器和旧结果。

修补后33项相关离线回归（原21+负责人入口10+真实快照/白名单2）通过，真实exit0；SDK/串口/网络/子进程审计钩子无触发。原快照实际通过该只读地址；0x40023C18/4与FLASH_CR/8仍拒止。该结论是主机修复验证，不是实板复验，也不关闭SDK残余风险。

原入口SHA256=032b921b129fcac223c44f18d88e65ecbee536e772b1715e92fc13dadbd3eb86；修补后=8a66c00620e12f81b13f1cb1e7c2d650129c1d59432bff9bd2d6a7ebdad50aee。现场原执行源码、旧失败、签名卡、父/worker claim、原生日志及镜像均保留EFS；不覆盖、不以修补后SHA冒充原现场SHA。

## 时间与现场状态

初次上电回复误用了未来示例10:30:15，Host准备程序实际exit1，SDK0/nonce0。负责人后更正10.22，仅到分钟；按10:22:00最早可能时间保守校验，cold记录保留60s精度及上界，不声称秒级精确。本次父/worker在新鲜度内通过授权入口，但首次MCU采样uptime门因白名单拒止尚未到达，不能声称MCU冷启动时间已核验。

已请求现场关闭B/C J5并拔J-Link电脑USB；负责人回复先分析再决定重采，未确认断电。因此最终电源状态UNKNOWN_NOT_CONFIRMED_OFF，最后确认的冷启动拓扑是C仅J5、C USB拔出、CAN接B、J-Link在B、L在LA、非人体ECG60/1mV、SKX电池。

## 是否建议重新采集

这个主机阻断已得到实证和最小离线修复，修复后进行一次新的ECG60试采有明确价值。仍需负责人另行决定是否重采，并按当期事实重新冻结commit/tree/工具SHA、独立冷启动和单次授权；旧nonce不退还，不沿用旧签名或创建新卡。本轮不再连接，ECG90继续保持后续准备，未授权执行。
