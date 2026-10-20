# H3-2 隔离链路回执（进行中，尚未准出）

截至 2026-10-20，结论为 **FAIL / 正式发布暂停**。主机监听退出码0仅表示完成取证，不能解释为硬件链路验收通过。

真实路径为 Node-A 物理CANopen → C中断静态队列 → Adapter/Router → ESP8266 AT 2.3.0.0 / SNTP / TLS → 独立8884 Broker → 独立Backend → WSS。来源按操作者批准的非个人测试源标记MOCK/synthetic，未回放R3真人记录，未验证生理测量准确度。Node-B未接入，观测中未出现在线。

| 原始观测入口 | 实际时长 | 关键结果 |
|---|---:|---|
| cloud/evidence/h3/observations/e2e-20261019T132109Z/result.json | 600.076s | MQTT1191、WSS5949；匹配数值未发现不一致；连续有效窗口仅39.548s，退出1 |
| cloud/evidence/h3/observations/e2e-20261019T134417Z/result.json | 900.091s | 等待A期间无有效输入，退出1；不能当作活跃验收 |
| gateway/physical_can/evidence/h3/uart-20261020T010558Z-result.json | 329.219s | FIFO/软件队列/UART/主机日志丢失0；发布失败5，Router累计丢失177 |
| cloud/evidence/h3/observations/e2e-20261020T010618Z/result.json | 900.007s | MQTT1828；数值匹配错误0；最长有效174.875s，退出1 |
| gateway/physical_can/evidence/h3/uart-20261020T011626Z-result.json | 1200.000s | FIFO/软件队列/UART/主机日志丢失0；发布失败18，Router累计丢失423；包含一次已明确记录的隔离Broker重启注入，不是正常稳定网络窗口 |

首次联网镜像缺少应用自身VTOR初始化，已修复；C原应用sector0–2实际回写并读回核验通过。后续UTC小数映射已修正，保留原新鲜度/发送频率；修正后的现场检查中Backend拒收累计658未继续增加。不能把旧失败记录删除或清零后改写成通过。

串口跨夜中断后，恢复工具最初错误地把下载线DTR置False，保持了C复位；已按本机reset_active_high/boot0_active_low极性修正，并在现场A断电条件下复用原成功握手时序。恢复时只核对Flash并写312B预留SRAM，不擦写Flash。RAM配置不具备断电持久性，不能声称C已具备正常持久生产配置。

当前诊断确认存在5000ms发布总预算失败；必须记录实际QoS与在途编号，才能区分QoS0发送和QoS1确认。独立Broker诊断仅输出指定测试客户端的编号、QoS、报文长度、UTC与PUBACK发送事件；原始日志、地址、Topic和载荷不落盘。正式Broker未修改/重启。

另一次0.222s MQTT/WSS观察因并发会话争用共享状态临时文件失败（原结果保留）。工具已改为各会话独立原子状态文件，并发回归通过；工具失败不能替代硬件FAIL归因。

最新候选源码4209876ed659408d7bd8ca22a804d93e76bdee35，镜像39120B，SHA256 6aecb5ea4d03d9f57a051b8701c49bffb8e01d3e5b6dd622e1b3f0f51e50d6cc，仅应用sector0–2。sector7/11与选项字节逐次核对，未改动。正在进行失败报文与Broker回执配对，尚未宣布修复或H3-2 PASS。

当前已通过：两种ARM构建；IRQ目标42项P5普通Host；Backend/AI/受限下载观测105项普通测试。没有执行正式Security Gate或安全扫描，没有PR，没有修改P4/main。原Web/Nginx/AI正式服务未切换，H3-3所需现场发布窗口尚未申请。
