# MEM-AP窗口SDK读错误原因审查

最新结论：**负责人另批的修正版第二只读窗口已通过，支持修正后的连接方式有效；旧SDK内部失败分支仍未唯一确定，不归因于CPU进入ROM。** 以下保留上一轮失败与离线调查记录，第二窗口补证见末节。

## 真实失败链

已安装42552B并通过全片、options、真实PC/MSP入口与DISARMED核验。随后独立桥窗口中，Configure之前的身份/运行状态、完整Flash、options和状态4B均读取成功；`CORESIGHT_Configure("")`返回0，紧接着CPUID `0xE000ED00` 的4B SDK读返回 **-1**。Python仍在求值 `bridge.probe` 的第一个实参，原始AP/DP调用尚为0。

所以不是“有效读到了不足4字节”，更不是1MiB备份残缺。原包装器将负错误和正的不足长度统一报成 `S3_NATIVE_SHORT_READ`，错误名称不准确。实际返回和旧执行源码SHA保留在[原始失败回执](../evidence/B5-G2A-ADMISSION/bridge-readonly-result.json)，不因后续修正覆盖。

## 新增的SDK诊断证据

SDK日志最后数条回调中存在23B消息，SHA256为 `4011d6adff92ade33bc2ac13745850c56dbb42e5b63794c2ae2aedf2246dd3f2`。对冻结DLL只作磁盘静态分析，发现其静态字符串 **`CPU could not be halted`**（文件偏移0x47C7C8）与该长度和完整SHA完全一致，证明SDK实际报告过暂停失败。这不是根据-1猜测出的错误文本。

当次Python显式Halt/Reset/Go调用均0，但这不能证明SDK内部没有暂停相关行为。旧回调日志只有消息SHA/长度，没有当前API/时间；SDK关闭也可能发出回调，**目前无法将该消息唯一归属于ReadMemEx还是Close，更不能据此确认实际发出过多少次硬件暂停/复位请求**。

## 文档与冻结DLL交叉核对

SEGGER将Configure列为接口设置操作，`PerformTIFInit`参数涉及是否输出切换序列。[官方说明](https://kb.segger.com/Using_J-Link_Script_Files)。PyLink实现中SWD空字符串Configure也是用于接口切换；其原始DAP访问前置门禁接受“已经连接到目标”或“已完成CoreSight配置”，并非只能再次Configure。[接口文档](https://pylink.readthedocs.io/en/latest/pylink.html#pylink.JLink.coresight_configuration_required)、[项目原实现](https://github.com/square/pylink/blob/master/pylink/jlink.py)。该包装器行为支持复用连接的修正方案，但不能冒充本机9.86a DLL已经实测支持所有混合访问方式。

本机实际DLL SHA `632d0d78e72b8a55c65945a0c393a9f081082c725fff4ba3081b0a565fd58cff`。未加载DLL或访问设备，只用PE导出解析和objdump核对：ReadMemEx导出RVA0x106550有默认返回-1的路径，且与Connect导出共用内部检查入口RVA0x1117F0（再跳0x75B60）。因此-1既可能来自前置/连接处理，也可能来自后续读处理，不能直接解释为目标内存损坏。**静态分析不表明当次选中了哪条运行时分支**。反汇编片段、定位信息和指纹仅归档EFS，Git仅存SHA/结论。

## 已证实与未证实分开

| 项目 | 裁定 |
|---|---|
| 已连接SDK读成功→Configure返回0→下一CPUID读返回-1 | 实际回执已证实 |
| 负错误被通用包装器误称short-read | 已证实的报错分类缺陷 |
| 插入低层接口重新初始化后未确认高层通道有效便继续读取 | 已证实的工具流程缺口 |
| SDK曾报告CPU could not be halted | 日志指纹与冻结DLL静态文字匹配证实 |
| 接口切换触发高层SDK重连接/暂停相关路径 | 主要机制候选；内部实际分支未证实 |
| 错误一定发生于ReadMemEx内部而非Close回调 | 无时序证据，不能确认 |
| CPU进入ROM、算法消失、Flash被破坏 | 本窗口没有相应证据；错误后未追加读取 |

## 已完成的离线修正

1. 复用既有Device/ForceAttach连接，明确要求SDK仍Connected；只读scope禁止再次调用Configure。SDK的CPUID、Flash前64B、CR/SR基准先读齐，再开始原始DAP读取。
2. 原始传输仍仅允许SELECT、CSW、TAR设置，禁止DRW目标写；Flash解锁、擦除、编程、显式halt/reset/go均不在该scope中。AP访问后仍核对SDK回读、完整Flash/options、身份、DISARMED及运行状态，不以“跳过失败调用”制造PASS。
3. 负SDK返回单独报 `SITE_SDK_MEMORY_NATIVE_ERROR`，非负但不足长度才报 `SITE_SDK_POSITIVE_SHORT_READ`，记录请求地址/长度及实际返回。
4. 全部核验成功前不启用退出续跑；失败使运行证明失效。SDK回调增加单调时间及当时在途主机API，Close单独标记；只存消息SHA/长度，不泄露消息中的设备或配置内容。在途API是时序线索，不假称能看到全部SDK内部子调用。
5. 一次原始AP/DP原生错误即锁死后续AP/DP调用；即使进入finally的传输恢复路径也不得重复原生请求。此时AP状态保留UNKNOWN，不为恢复CSW/TAR而重试。

修正版15项离线测试通过；初始8项及中间13/14项各次回执/原始日志也保留。不重跑既有27项writer、3项配置C或Host/ARM/TLS/UI矩阵。新增重放使用“观察到Configure后读错误”的替身边界，**不是在假对象中证明真实DLL根因或硬件已修好**。

原始执行版已在提交 `83bff8d` 和EFS中保留；截至上一轮归档，新版本仅离线准备，源SHA、静态资料SHA和试验退出见[原因审查回执](../evidence/B5-G2A-ADMISSION/SDK-cause-audit.json)、[最终15项检查](../evidence/B5-G2A-ADMISSION/SDK-fix-offline-04.json)。上一轮没有在失败后追加板卡尝试；此后另获批准的第二窗口单独记于末节。

## 下一步门禁

上一轮提交的[新一次只读窗口](AUTH-B5-G2B-MEMAP-READONLY-002-R1.md)现已获得负责人单独批准并执行一次。C已验证应用仍为42552B，没有重跑G2-A、重新烧录、写sector3或复位。

冻结sector3物理写入器中也有相同初始化混用模式，保持原SHA及27项离线结果；不得因本次只读桥通过就直接启用它，须先核对其连接方式并冻结对应修正。实际配置写入、ESP电气条件/豁免、恢复和云窗仍各自另批。

## 第二个获批窗口的实测补证

在基线 `d74f9ae` 上不改代码，核对冻结源码与DLL SHA后，只执行一次修正版只读会话。实际SDK调用325次，原始AP/DP读取83次、传输设置写166次；AHB MEM-AP IDR类别、CPUID、Flash前64B及CR/SR均与SDK读取一致。CSW/TAR恢复、SELECT规范化0，前后独立完整Flash与options一致，C保持DISARMED、VTOR=0x08000000，未观察到HALT/ROM/Fault或新增复位。

Configure调用0，显式halt/reset/go及Flash/目标内存写0。325次调用无负返回，独立监督器、worker和调用者退出均0。新增27条SDK回调全部具备单调时间和在途API，时间递增；Connect24条、ExecCommand1条、Close2条。上一窗 `CPU could not be halted` 的消息指纹本窗为0，SDK基准先于原始AP/DP操作取得的顺序已核对。

因此可签 **MEM_AP_READONLY_CROSSCHECK_PASS**，关闭“修正后的SDK与原始DAP读路径尚无实板证据”这一缺口。不能把它扩大成Flash编程通过、同窗HR/RR通过或上云通过。原始冻结helper返回的 `NOT_ESTABLISHED_BY_OFFLINE_TESTS` 固定文字没有篡改；这次实板通过来自新独立SDK回执与字节对照，并非把离线标签改成PASS。

本窗同时包含初始化顺序、错误分类、关闭策略和日志等软件修正，不是旧故障的严格单变量复现实验；旧诊断消息到底发生在ReadMemEx还是Close仍不能倒推出唯一答案。没有Close后的第二次硬件探测，历史ROM根因/独立冷启动状态不变。

详细结果和实际27条时序指纹见[窗口结果](../evidence/B5-MEMAP-READONLY-02/result.json)、[API时序核对](../evidence/B5-MEMAP-READONLY-02/API-timing-review.json)。原失败、私有UID、完整Flash/options和原生日志仍独立保存在受限EFS；本轮只读许可已消费，配置写入与云端操作仍未授权。
