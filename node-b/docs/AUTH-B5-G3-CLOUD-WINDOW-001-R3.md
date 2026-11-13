# AUTH-B5-G3-CLOUD-WINDOW-001 R3｜ESP保持在板的单次真实ECG云窗，待批准

`enabled=false; owner_approved=false; executions=0`。本卡在R2基础上绑定G2-B R3工具与配置方案，沿用[R1完整判据](AUTH-B5-G3-CLOUD-WINDOW-001-R1.md)，将真实配置字节、服务生命周期与新上电门禁绑定。R1不单独作为现在的执行许可；本轮不接实板、不发AT/B5START。

## 启用前必须实际通过

- G2-A已实际通过，G2-B必须按[新R3卡](AUTH-B5-G2B-SECTOR3-001-R3.md)另批且实际完成；C42552B BIN SHA `d5b9624b3da1129b4e045d3b2f669c00d2d93cb7379b15293ff143fe9f130683`，整片 `acb33fdd39ecb016ecd848ec25eee051635f56ef8138b577a8590d2734ad687e`。B39948B部署保留，采集250SPS，CAN2 500kbps；源不改阈值/ADC寄存器。
- 最近只读回执显示Backend/TLS因驻留超时停止，本轮未重新连接核验；启用前须新鲜核对，须另批并完成[G1-RESUME](AUTH-B5-G1-RESUME-001-R1.md)，确认测试实例实际可用。独立业务身份仅GW-B5-001、b5-gateway、b5-c-isolated；A段OFFLINE，所有消息MOCK/synthetic。不得使用正式GW-C-001或LIVE语义。
- 现场附件记录真实新上电运行/UID/保护、JTAG/USB/供电、CAN与独立参考地、ESP电气状态。ROM/HALT/意外复位立即停止留证，不擅自复位或烧录。负责人停机不能记为独立冷启动验收。
- ESP的实际AT/TLS/CA/SNI/证书存储与SNTP条件需要对应获批的有限检查；既有P分支AT记录不替代今天事实，不能降低证书校验。恢复ESP供电/EN、连线和串口动作须有明确批准，不由本卡标题暗示允许热插。
- 本轮负责人仅确认普通ECG60。未来窗口还须确认1.0mV、电池且USB断开、R→RA、L→LA、F→RL/N、LL空和人体隔离；不把历史记录当新现场确认。若不同，只能另批冷态操作，不自动切源/换线。
- B原码/诊断、C CAN/队列/网络、Broker实收、Backend接受/拒绝与WSS同session取证工具全部就绪并冻结源码SHA/地址范围/日志目录/期限。串口DTR/RTS不得触发BOOT或RESET。工具缺项则本卡不可启用，不用软件模型代替实板证据。

## 固定时窗与判据，不能采后改动

一次完整 `B5START\n`，不试发、不重武装、不重发；Tarm起420秒硬停。60秒内完成真实SNTP、MQTT CONNECT/SUBACK、Broker/Backend/Web同一新会话就绪，冻结T0。45秒预热，`[T0+45,T0+345)`300秒共同评价，15秒尾段；总时长始终不超过Tarm+420秒。

HR目标60±2bpm，稳态保存观察100%有效；RR/TEMP均INVALID，A段OFFLINE；250SPS ECG每100点、50SPS RESP每50点，量纲/源时间/序列/session/boot一致。保持源无效的真实原因，不能为凑双有效修改阈值、把RR菜单值当测量值或将两个模式合为同窗通过。

分别裁定ADC连续与生理有效性、CAN/队列TEC/REC/BOFF和窗口新增错误、Broker逐包实收、Backend模型接受及WSS新会话内容。QoS0发送/CAN ACK/Router ACK不等于Broker/Backend/Web接受，QoS1仅匹配PUBACK也不足替代各层证据。INVALID/STALE/REPLAY及断链自然OFFLINE均保真，七页/AI事实层不得引用失效值，正式AI不接测试流。

ROM/HALT/复位、电气异常、命名空间/来源错误、BOFF/溢出/发送失败、关键记录缺失任一出现即停。到期固件STOP、禁止重连/业务，清理≤2秒；监督器或记录器失败须按预先批准的人工隔离方案停止，不临时无限重试。本卡不含断网/故障注入、RR窗、固件/配置/账号恢复；各项另批。

## 第三阶段准备边界

ESP保持在板供电不等于允许联网，G2-A豁免不能当G3许可。G3单独批准一次真实联网及B5START；当前次数0。独立服务启动仍只用G1-RESUME R1，不可调用会改ACL/发送HUP的旧G1 apply入口代替恢复。测试账号未撤销；正式身份/服务保持不动。

本轮已冻结申请判据，尚未宣称可执行：G2-B实际结果、未来现场附件、ESP实际AT/CA/SNI/SNTP检查、有限resume-only执行器及B/C/Broker/Backend/WSS联合取证工具绑定均须齐全，缺一即不启用。不能用旧人工云日志或本地TLS代替。G3结束后仍按独立R-CFG R3、R-APP R2及R-CLOUD批准执行，失败不自动恢复。
