# 三个独立最终窗口对象｜R1（待PI逐对象或批量批准，默认全部禁用）

只在APP-INSTALL真实PASS、同一实际部署独立C只读DISARMED及现场准备通过后生效。C候选46456B BIN `1771ee61bde1fda9543ff7d056311d1602719d842552ce09dd7dece4aa19937e`；预期全片 `b9e7518ec2af1b780534a97e769054630e19b6a4600800a6db2dea98b8f675ea`；B固定40928B BIN `a1cf57648ca3787de30c1ad7055634c278fbbde538bb0bc562961bd212182ed2`，B不烧录、不复位/Go。gen5/options/sector7/11不改。

| 独立对象scope | 冻结源 | 独立评价 |
|---|---|---|
| B5_FINAL_ECG60_R1 | 普通ECG60/1.0mV，R→RA、L→LA、F→RL/N、LL空；电池无充电USB | HR58–62 VALID、RR INVALID；ECG≥74250连续源点，RESP源点≥14850且按真实INVALID；HR≥295条 |
| B5_FINAL_TEMP_OBJECT_R1 | 原GY-641V3/3.3V、PC11接收、PC10不发配置；非人体物表；ECG源保持不变 | TEMP≥295条有效报告；B UART CRC/To→CAN→C入口seq/报告UTC/入口UTC→Broker→Backend→WSS一致；模块新鲜度≤2500ms；不宣称临床/绝对温度校准 |
| B5_FINAL_RR15_R1 | 原独立呼吸15bpm/1.5R、波形周期30bpm、窒息0s；RA–LL–RL，LA空，禁止LL/RL短接 | RESP50SPS/50点，≥14850连续源点；RR14–16 VALID且≥295条，HR INVALID；TEMP如实独立上报 |

## 每窗固定权限与门禁

每个scope各有一份私有enabled=false/owner_approved=false的模板、独立输出、剩余次数和.used，START≤1、计划C人工RESET≤1、B联合只读连接≤1。不转用其他窗口token，不自动串行执行下一个。准备≤300秒、C新DISARMED串口行在已批准按键意图后确认，原30秒发送门；60秒共同就绪、45秒预热、300秒共同评价、15秒尾段、420秒业务硬停、20秒被动观察。B每连接总限755秒；异常结束不重发、不复位/Go B。

入口必须是实际当前ESP启动上下文中的可信时间与新鲜nonce NTP完整≤1000ms、TLS CA/CN/SNI及真实测试Broker/Backend/WSS；不能用上次断电前的时间证明本次，也不能人工灌UTC。若TIME门失败，当前START消费后停止，不盲等/追加START。冷启动TIME根因仍有未决项，本轮未擅自改授时端点。

云测试预算≥805秒（覆盖755秒连接及关闭；比合同最低625秒更保守）；只读核验独立Backend/TLS/ACL及正式服务不变，不含服务启动/HUP/改ACL。独立GW-B5-001，全部MOCK/synthetic；A OFFLINE，INMP441/TTS/人体断开，LL/RL不短接，RLD不接地。ESP在板供电例外必须本批明确同意，自主联网状态UNKNOWN。

每窗同时保存B原码/CAN队列/UART4、C原串口和新诊断、Broker原载荷、Backend计数及原WSS。Backend accepted=去重Broker、rejected/dropped=0；≥2900个WSS快照，当前同session/boot/seq/UTC和值，实时批次不得以REPLAY补齐，不允许新增drop/expired/overflow/txfail/mqtt_fail、覆盖或非预期STALE。原2048B、QoS0/QoS1与PUBACK门不变。

新C `B5 LAT`为有界直方图分位上界，9阶段依次为命令、提示符、数据、SEND OK、JSON、MQTT发送、PUBACK、队列驻留、源数据年龄。`B5 TEMP_ENTRY`为最多8项的周期导出环，保留报告UTC并另记C入口UTC，不重写载荷；TEMP窗口按该入口约束B UART原帧，2500ms及原2ms相位界不放宽，缺项/失配/lost非零失败。历史79条未资格温度映射不补造。

原STOP观察419–422秒门保留，另外必须有 `B5 STOP_STATE`：MCU源tick−armed_at（uint32回绕）恰为420000ms、reason=1、phase=CLOSED(7)、unsynced=0、pending=0；主机到达时间单独保留。最后8秒停止开启新事务（1秒准备+原5秒事务+原2秒关闭预算），锁存仍420秒；不延长业务。部分CIPSEND/关闭未确认须人工断电，不把进程退出当MCU或ESP已停止。

## 现场动作仅在批准后安排

先由负责人一次确认真实供电/USB/J-Link/源，不能假定当前已断电。APP在C完成后，独立批准的冷态转接使J-Link在B、C USB_UART实际COM号与原CAN/地不变；记录就绪才提示本窗唯一C RESET。ECG→TEMP不改线/源；TEMP→RR由负责人按既有冷态B/模块/导联操作完成，保持C在已证明AT CLOSED状态，确认B/模块/屏全暗后改黄L到LL/F，不热改线；B正常上电恢复后，记录就绪才提示RR窗C RESET。供电安全事实未知则停止，不临时擅改P4/P6/BOOT。

三个实板状态当前均NOT_RUN；只有三窗各PASS才能签B5_THREE_MODE_NONHUMAN_E2E_ENGINEERING_PASS。CPU ROM、独立冷启动、同窗HR/RR、阻抗/温度绝对精度、CAN故障注入各自保留原状态。R-APP/R-CFG/R-CLOUD和最终物理停机独立办理，不自动恢复正式联网或修改保护分支。
