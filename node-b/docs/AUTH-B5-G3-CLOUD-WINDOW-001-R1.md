# AUTH-B5-G3-CLOUD-WINDOW-001 R1｜单次ECG云窗，禁用

`enabled=false; owner_approved=false; executions=0`。仅当G1、G2-RO、G2-A、G2-B及负责人现场准入全部通过才可批准。[共同绑定](B5-G0-SPLIT-AUTHORIZATIONS.md)适用。当前均未执行，不得发送命令。

## 采前冻结

- B39948B、C42552B与新sector3全片/SHA；B250SPS、CAN2 500kbps；A段断开，人体/INMP441/TTS隔离，ESP仅按本卡明确批准的供电/串口/天线状态恢复。先确认DISARMED，不发送试探B5START。真实供电、USB、参考地与停止手段写入现场附件；串口设置DTR/RTS为不触发BOOT/RESET后才打开。
- SKX电池/充电USB断开，普通ECG60bpm、1.0mV；R→RA、L→LA、F→RL/N，LL空；无主动RLD接地。**本卡不授权改变当前源状态或换线**：如与此不同，先另批冷态切换。HR目标58–62bpm、稳态有效观察100%；RR/TEMP必须INVALID，如源产生未知RR也不得宣称有效或混签同步。任何新增削顶/采样缺口都记录，不采后剔除失败段。
- G1选定独立Gateway、Broker角色和测试Backend/Web入口、Origin/访问令牌；记录TLS/SNI/CA和ESP AT版本实际检查。TLS握手通过不等于ESP信任链可用；模块命令不支持、证书/时钟不合格即停止，不降级TLS、关闭证书校验或改用8884。
- 原码与各层观察先就绪：B CH1/CH2和诊断、C串口/CAN/队列/网络、Broker专属订阅、Backend接受/拒绝、浏览器WSS。所有观察工具、固件及日志绑定SHA/UTC/源session/boot，任何一层漏录不开始。

## 一次命令与固定窗口

只允许发送完整`B5START\n`一次，不能重发或自动重武装。命令时刻Tarm起硬限420秒；≤60秒取得本轮新鲜SNTP、MQTT CONNECT/SUBACK、Backend接受及Web新会话快照，共同就绪时刻T0必须冻结。未就绪则失败停止。

T0到T0+45秒预热；`[T0+45s,T0+345s)`300秒共同评价；再15秒尾段，始终不超过Tarm+420秒。提前就绪也不扩大或移动评价窗。T0定义、边界时间戳与所有异常固定保存。

## 各层判据分别裁定

1. B源原码/序号/UTC及ADC计数250SPS连续、ADC错误无新增、CH2峰/幅度与HR原因码可追踪；首尾整批之外不补点。源失效照录INVALID，不改BIO_V2阈值/寄存器。
2. C CAN2真实RX/TXOK、NMT/HB/TIME、TEC/REC/BOFF、CAN/UART溢出和队列expired/drop。共同评价无新增丢失/过期/溢出/发送失败/BOFF；原始累计值与窗口增量分开。ECG每100点、250SPS，RESP每50点、50SPS，量纲与源时间/序号一一可核对。
3. Broker按实际收到的Topic、payload、序列/会话和源点数取证。q0_transport只是C字节发送；q1_puback只是匹配PUBACK；CAN ACK只证明总线，均不替代Broker记录。
4. 独立Backend逐包模型接受与质量字段、源MOCK/synthetic、INVALID、REPLAY/STALE及节点OFFLINE；Web WSS同会话/源点/HR有效和RR/TEMP无效，A段OFFLINE。不能用Broker实收冒充Backend或Web接受。七页/AI事实层不引用无效/过期/重放值，正式AI服务不接本次测试流。
5. 时间戳/会话、批次/点数、内容误差按采前绑定的B5模型定义核对；传输准确性与生理有效性单独判。C止发后只读观察自然离线/STALE，不额外延长实板业务窗。

当前卡不含断网/重连/CAN故障注入、RR模式切换或第二云窗。这些需另卡；未做就NOT_RUN。RR15另批冷态RA–LL–RL和独立窗口，不将两窗合为同窗双有效。

到时固件STOP、取消邮箱/禁止新业务及重连，仅≤2秒CIPCLOSE清理；记录真实退出。任板ROM/HALT/意外复位、身份/配置漂移、电气异常、错误命名空间/LIVE误标、越权、BOFF/溢出/发送失败、关键日志丢失立即停止；负责人按预先批准的停机附件隔离ESP/停止专用会话，不复位或重刷掩盖。回滚R-APP/R-CFG/R-CLOUD均另批，不能默认自动执行。
