# G3首次现场窗｜AT阶段停止与版本补证

本次获批G3 R4已执行一次，真实进程/worker/监督均退出1，许可消费。首次完整B5START只发送一次，C在约2.078秒后输出`GW FAIL AT`；未取得新鲜共同T0，300秒评价NOT_RUN，不签上云通过。失败原件和所有恢复档案保留，未复位/烧录/自动重试或修改正式云配置。

## 分层证据

- HW一次C只读PASS：UID/保护、完整Flash/options、正常Flash运行及DISARMED匹配；一连接/关闭，目标状态/Flash写0。
- 随后负责人按HW步骤确认全部熄灭10秒并完成冷态转接，J-Link在B、C USB_UART为COM6，B/C原J5供电、源普通ECG60/1.0mV/RA–LA–RL及隔离条件确认，负责人可即时切电。负责人仅按C实体RESET一次，串口取得新DISARMED行后才START。
- B停止前保留94份诊断，观测速率250SPS、HR均60有效、RR均无效，新增ADC错误0；这不是300秒联网负载验收。
- 云观察者实际CONNECT=0、SUBACK=1，隔离Backend健康/MQTT订阅和714份WSS快照正常。START后Broker实收0，Backend accepted/rejected/dropped均未增加。观察器正常不能替代设备云数据接受。
- C最后已收CAN帧，记录`rx=99, txack=0, txfail=0, overflow=0, esr=0, uart_err=0, session=0`。不能据此宣布CAN整窗或C→Broker通过。
- 首因是C的网络步骤失败；B随后返回`G3_STOP_REQUESTED`是联合STOP传播，不是独立证明B再次进入ROM或ADC失败。

## 已知原因与未知

冻结源码的第一步是`step("AT","AT",2000)`，之后才是ECHO、模式、GMR、Wi-Fi、时间和TLS/MQTT。约2秒的失败支持未取得及时成功响应，但原程序未输出ESP原始回复，**不能据此区分完全无字节、ERROR、UART错误或其他拒绝**。此次记录未进入GMR，不知道当前ESP版本。

板图与代码一致：USART3 PB10/PB11、115200，经C P5到ESP-01 P1；P4仅CAN2。负责人随后明确确认C P5是正确ESP路径，因此当前登记P5路线为负责人确认正确，不将此前缺项直接当作根因。未作通断或电平实测。

历史P阶段旧AT1.1.0.0与后来的2.3.0.0-dev都曾响应基础AT。历史成功不代表当前状态，但也不支持“本次AT失败必然因为旧模块”。下一步应实际读取GMR，并记录新响应/错误；不重刷ESP、不改BIO阈值、不改云配置。

原G3冻结硬停为北京时间2026-10-27 **14:12:54.661**。首次失败后记录会话已关闭并提示人工切B/C J5及C/J-Link USB；负责人要求先离线分析，尚未确认切电。当前**未取得固件STOP行、未确认物理停止**；到期仅是源码预期，不能冒称已观察到MCU停止。没有重新开串口或发B5START补证。

## 最小补证方案

[独立GMR查询卡](AUTH-B5-ESP-GMR-001-R1.md)不安装临时固件、不跨接CH340到ESP；冷态把J-Link转C，只给C J5供电、USB_UART断开。确认当前C正常且DISARMED后，用已验证MEM-AP流程向UART_DR写固定AT/GMR最多12字节，由既有运行中RX环返回实际版本。它包含新的易失UART字节写许可，不能冒称沿用“C零写只读”卡；默认禁用，待本笔明确批准。

更换物理模块与AT固件版本是两件事。即使GMR读到2.x，也只证明当前AT身份，不能自动签TLS、云端、独立冷启动、双通道同步、阻抗标定或CPU根因通过。本G3失败已经冻结，后续查询或修正不能覆盖本次原件。


## 后续真实补证：A与备用B均无RX

R1只读入口再次处于ROM，未开始AT；R2经负责人另批一次正常C RESET后，在Flash正常/原件身份匹配时仅发AT四字节，115200下新RX=0、UART新增错误0、未发GMR，完整Flash/options及DISARMED保持不变。R1异常收尾多读一份ROM快照的问题已在修正版纠正，14项定向测试通过，旧源码/快照未覆盖。

负责人随后同意换备用模块。R3按相同接线/波特率/命令完成B对照，结果仍无新RX，仍未到GMR；完整Flash/options前后相同。参见 `../evidence/B5-ESP-GMR-REAL-01/`、`../evidence/B5-ESP-GMR-REAL-02/`、`../evidence/B5-ESP-GMR-REAL-03/`。当前真实AT版本UNKNOWN；不能把型号ESP-01S、灯不亮或换件结果当成固件版本/损坏证明。下一步先看C P5与P1/P2实际照片和共同供电/EN/启动路径，再决定新的有限测量；不自动重试或刷写。


证据边界补充：A/B的“新RX=0”来自运行中C的软件RX环，不是ESP物理引脚波形或USART_DR直接测量。已离线核对R3保存的实际Flash向量，USART3向量与冻结ELF强处理函数一致；这不能证明当时NVIC使能/挂起、GPIO复用、USART_SR与实际引脚信号均正常。后续应把C接收中断/路由、P5实物和供电/EN一起排查，不能仅凭两次缓存为空认定两个模块均无输出或损坏。
