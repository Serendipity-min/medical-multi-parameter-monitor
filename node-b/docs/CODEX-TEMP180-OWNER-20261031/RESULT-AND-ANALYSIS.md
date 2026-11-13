# 桌面TEMP三分钟：完整采集，保留一次校验未通过

负责人直接授权的180秒非人体窗口已完成；状态NOT_PASS。父进程、worker、监督器和工程评估真实退出码均3，SDK Close成功；不是超时或连接失败，没有重采。冻结正式420秒联评器未运行，也没有启动云端。

| 观察 | 结果 |
| --- | --- |
| 实际采集时长 | 180.000秒 |
| 完整会话 | 209.437秒 |
| 观察 / 1Hz观察槽 | 360 / 180 |
| 物表温度 | 26.45–26.85°C |
| MCU数据年龄 | 0–220毫秒 |
| 新增有效帧 | 823 |
| overflow / UART / checksum / header错误增量 | 全0 |
| 末帧原码校验不一致 | 1/360，索引212，约106.141秒 |
| 绝对准确度 | NOT_CALIBRATED，桌面无独立温度标准 |

所有观察均present，温度范围及新鲜度符合事前边界，帧持续推进；但一次未暂停CPU的64字节TEMP诊断快照中，保存的12字节last_frame头正确、累加校验不一致。该条object诊断和原帧object均为26.64°C，age220毫秒，累计解析checksum/header错误不增长。该条used=11，解析frame尚未收完，不能拿它当完整UART校验帧。单次诊断中的帧和字段不是原子发布。

源码gy641_feed先验证帧，再更新温度字段、memcpy(last_frame)、last_ms、present及frames；Host同时从运行中RAM读64字节，存在跨更新观察的可能。附近20条有效快照未找到可完全拼成本异常的两帧字节组合，因此不能把读取撕裂写成已证实根因。ROOT_CAUSE_UNRESOLVED，sensor_fault_confirmed=false；没有证据直接将本条归因到模块、接线或物理串口。也不因错误计数为0而抹去该条不一致。

原NOT_PASS及全部原码保留，不改判、不放宽校验、不修改共享b4_runtime/M1Link、固件或旧冻结评测器。后续若专门核验，应复用已有UART4环形缓冲两次一致的源字节证据，或为TEMP诊断新增有界稳定性观察，再独立授权复验；本轮不自行追加窗口。温度读数可用于样机功能观察，不能作为校准准确度或正式端到端验收通过。

当前工具只新增TEMP180薄入口与4项相关离线评估测试，复用B41012身份、全片/options同次制品、只读白名单、STOP、原生单调用、父worker与Close门。事前签署固定Git ff4c17990d043a374a74649760ee760083fae020，29项工具SHA与单次nonce；签名和父worker消费记录核验通过，所有TEMP输入文件SHA核对通过。测试私钥仅Host内存，签卡后已释放引用，未导出；不是PI生产私钥。

现场仍为非人体桌面、原温度模块3V3/GND、负责人报告RC→PC10/TD→PC11；固件PC11 UART4接收、PC10输入，不新增发送或模块配置写入。沿用B/C原J5/CAN背景、J-Link板端B、C USB断开，未改接线、未RESET/HALT/GO/Flash/B5START、未操作C串口或云端。SDK原生剩余副作用UNRESOLVED，Close后CPU状态UNKNOWN；最终负责人确认“已全部断电熄灭”，板端J-Link、CAN和R_RA/L_LL/F_RL保留，SKX最终电源未知。

受限原件见本地node-b/build/m1-owner-temp180-pointer.json，公开只提供统计及SHA。汇总推送按负责人本轮新指令执行，之前暂停时不推送的指令已被本次明确修改。
