# AUTH-B5-G3-CLOUD-WINDOW-001 R4｜联合取证、300秒评价及420秒硬停，待批准

`enabled=false; owner_approved=false; executions=0; B5START=0`。本卡替代R3作为下一次申请，旧卡及回执保留。当前只准备软件及现场附件，没有启动实板云窗。一次性私有授权必须另获负责人明确批准；不能由卡片、工具测试通过或G1/G2许可自动启用。

## 冻结身份与现场前置

| 对象 | 唯一绑定 |
|---|---|
| B现部署 | 39948B，BIN SHA `676eb7a46ad9cd15c7bf93db51a1931d7711d37c6f2fd636197dc4a85b339b82`；全片参考SHA `a1abed50a4c4dbab142a2319d61c047bc43b6816dd62754a080e3f7e12415091` |
| B实际配套ELF | SHA `94e1ed1d188acae350943382645ce49edc1ed91bb043245657de3df1f1f89249`；离线提取BIN与现部署候选一致，不重新构建或烧录 |
| C现部署 | 42552B，BIN SHA `d5b9624b3da1129b4e045d3b2f669c00d2d93cb7379b15293ff143fe9f130683`；G2-B后全片SHA `acb33fdd39ecb016ecd848ec25eee051635f56ef8138b577a8590d2734ad687e` |
| C options | 16B SHA `52d5979da03bd7be45e385920ec7d5901793bab3f6bc1daa0c1c1997f9e91687`；sector3配置CRC/身份/提交字由既有全片覆盖 |
| 私有参考包 | SHA `6c40e584d40fdb263cce369463e0653e92e153830d029e1c03ef4ea8f0224761`；UID、凭据、原件路径不提交Git |

先实际通过[HW准备卡](AUTH-B5-G3-HW-PREP-001-R1.md)：C当前UID/全片/options/保护/Flash运行与DISARMED通过，新鲜回执距G3启用不超过1小时；之后冷态转接、C USB_UART实际COM和B供电事实齐全。[现场附件](B5-G3-SITE-ATTACHMENT-R1.md)内UNKNOWN不能写成true。B只读会话开始后再次核对私有UID、完整Flash/options、运行状态及250SPS推进；CPU ROM/HALT/意外复位立即停，不以复位或重刷恢复准入。

固定源为普通ECG60、1.0mV、电池供电/充电USB断开，R→RA、L→LA、F→RL/N、LL空置；CAN/独立GND保持B CAN1↔C CAN2，500kbps，A段OFFLINE，INMP441/TTS/人体断开。B开发板USB不接；C用原J5和USB_UART，J-Link在B。ESP在板供电，申请本次非隔离例外，自主联网UNKNOWN，不能称为电气隔离通过。

云业务仅GW-B5-001、b5-gateway、b5-c-isolated、独立Backend/Hub与观察令牌。观察器仅b5-observer订阅，不能使用发布客户端踢掉C身份；全部消息MOCK/synthetic，无正式GW-C-001/LIVE数据。测试TLS入口127.0.0.1:18775只通过已有SSH别名转发，不开放8884或公网端口。

G1-RESUME已于北京时间2026-10-27 11:15:45通过；原6小时驻留预计17:15:45结束，可提前停止。**本轮没有重新查询其在线状态。** 启用时必须仍有至少625秒驻留预算，且取得实际TLS、Backend健康/MQTT订阅、观察CONNECT/SUBACK和WSS鉴权快照。若服务已停止或不足预算，停止另批恢复，不自行start/restart，不改Broker ACL/HUP或正式服务。账号/ACL不会随驻留上限自动撤销。

## 精确动作与时间轴

1. 独立监督器校验工具、依赖环境、DLL、卡SHA、私有参考和现场附件，独占输出目录及一次性`.used`标记。预备阶段不超过120秒。C串口115200/8N1，打开前DTR/RTS均请求为false；软件标志不能证明硬件完全无脉冲，观察到重启/异常即停。
2. 一次B J-Link只读连接，禁止显式halt/go/reset/写寄存器/Flash。固定白名单读取原码、120B诊断、寄存器缓存、ADC/CAN计数及PCSR/VTOR等；检查样本推进。若B在启动前仍有新鲜TIME锚，视为意外网关活动而停止，不等待或改状态掩盖。
3. B_READY与NET_READY均成立后，工具才提示负责人**仅按C实体RESET一次**，立即回报，B不复位。串口必须取得本次完整DISARMED启动行；启动行后30秒内完成确认及Backend采前基线。超时不发送START、不追加复位。本卡申请这一次计划内C人工复位；它不用于恢复已发现的ROM/HALT。
4. 前置全部齐全后，只写一次完整8字节`B5START\n`。部分写入或原生错误同样消费许可，禁止重发、重武装或另开窗口。串口写入返回8不等于MCU已接受，不等于云端已接受。
5. 从Tarm起60秒内，取得本次ESP AT版本、SNTP样本及元数据、严格CA/CERT_NAME/SNI/TLS步骤、C MQTT连接、新Gateway/B会话和实际Backend/WSS共同就绪，冻结T0。DISARMED应用无AT透传接口，所以上述实际网络步骤只能在单次START后有界取证；不能拿旧P分支AT记录代替，也不修改ESP固件或降低校验。首次网络失败立即要求人工断电，不能将固件内部重连当成另一次许可。
6. **45秒预热；[T0+45,T0+345)为固定300秒共同评价；15秒尾段只收齐边界批次。Tarm+420秒为MCU业务硬停。** T0最晚Tarm+60，整段不能越过420。T0用新鲜实际WSS的server_time绑定源UTC，主机/服务差不超过1500ms，不假设B/C运行时间相等。

MCU到期必须停止CAN业务、AT业务、发送和重连；现固件只允许最多2秒网络关闭清理。监督器独立检查串口/API截止和Tarm+422前的`B5 STOPPED NO_AUTOREARM`。之后至Tarm+440仅被动观察自然STALE/OFFLINE，最后清理5秒；这20秒不是联网业务延长。含预备的外部总预算最多565秒。

如果STOP未确认、监督器/记录器失败或出现异常，结束电脑进程**不算MCU停机**：负责人须按预先批准的停止步骤关闭B/C J5、拔C USB与J-Link电脑端USB，确认全部熄灭。没有负责人可即时执行此步骤就不启用。不得自动reset、烧录、恢复配置、重启服务或无限重试；未取得物理停止证据记UNKNOWN并保留失败。

## 采前冻结的评价判据

| 层 | 300秒共同评价 |
|---|---|
| 生理/ADC | HR58–62bpm，保存观察100%有效；RR/TEMP INVALID/null；B诊断至少590份，间隔不超过1.5秒，实际名义采样率247.5–252.5SPS，无新增ADC丢帧/SPI/队列/初始化错误，CH2无近满量程 |
| 原码到CAN到Broker | ECG100点@250SPS，RESP50点@50SPS；至少74250个连续ECG源点、14850个间隔5源序号RESP点，任何中间断点不通过。队列固定点数值逐点完全一致，不能把原ADC codes直接当mV；RESP即便携带波形也保持INVALID |
| CAN/队列 | B/C记录TEC/REC/BOFF、错误/队列增量；共同窗无新增溢出、过期、丢弃、发送失败或复位，C rx/txack推进。5秒C诊断至少58份、间隔不超过8秒；轮询只能证明保存观察，不能宣称捕获了两次观察间所有峰值 |
| 实际Broker/Backend | 原始Topic、载荷、QoS、retain/dup及新session保存；波形QoS0、标量/状态QoS1。Backend accepted增量与实收去重消息数一致、rejected/dropped为0。Backend仅提供聚合计数，不能冒充逐条服务端接受日志 |
| WSS | 至少2900份共同评价快照；A OFFLINE、B/Gateway ONLINE，HR有效、RR/TEMP遮蔽；每个共同窗ECG批次实际出现在WSS，值与Broker一致；自然结束后可见STALE/OFFLINE |

B原码环、真实CAN样本队列和TIME锚用已验证ELF布局的一次5692B连读取证；活体非原子块必须有至少两次相同版本，无两个重复冲突版本才认证。保留全部原件和冲突，不能投票删错。网关只传批末UTC及名义率，按现代码允许两端反推最多±2ms采样相位，**不允许电压值容差**。ECG是gain4/Vref2.42V名义mV，不是绝对电压校准；RESP是relative，不是Ω。

当前42552B没有逐CAN报文串口跟踪，NMT/TIME只能依据冻结实现、B实际TIME锚、ACK及计数联合取证；不伪造完整NMT/TIME载荷日志。QoS0发送成功、CAN ACK、Router ACK及QoS1 PUBACK均不替代实际Broker、Backend及WSS证据。正式AI不接测试流，本卡不执行豆包调用，也不重跑七页UI测试。

## 停止与归档

ROM/HALT/意外复位、保护/身份漂移、电气异常、错误命名空间、非MOCK、意外会话变化、BOFF/溢出/发送错误、原生DLL错误/短读、关键记录缺失或预算不足任一停止。预热期与全程错误原样保留，不能只报告稳态掩盖启动失败。

原码、完整Flash/options、UID、实际端点/令牌、日志均存现有受限EFS；Git仅安全摘要/SHA/计数/真实退出码。冻结入口为`b5_g3_joint.py`、五个G3模块、必要既有依赖、独立监督与离线复核器；[冻结清单](../evidence/B5-G3-PREP/bindings.json)列出精确SHA/地址白名单/环境。默认执行器仅输出计划，私有HW/G3模板均未启用。

不改BIO_V2阈值、ADS寄存器、B/C固件或sector3，不合并保护分支，不运行Security Gate。ROM根因UNRESOLVED、独立冷启动、同窗HR/RR双有效、阻抗绝对标定及故障注入保持原状态。G3后R-CFG→R-APP和R-CLOUD仍分别批准，本卡没有回滚或清理云账号权限。
