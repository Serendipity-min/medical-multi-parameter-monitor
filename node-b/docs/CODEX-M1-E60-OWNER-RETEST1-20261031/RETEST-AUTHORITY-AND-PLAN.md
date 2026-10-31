# ECG60修复版：负责人再次授权的一次试采

负责人本轮明确要求“修复完毕后重新测试，当前BC已断电，需要上电告诉我”。此次是前次失败以后的新一次授权；原失败和旧nonce/worker claim均保留，不重置计数。基线6035c2b3db0522e6d17773ffdc2e6f0831ac67f4包含FLASH_CR/4精确白名单修复，原33项相关离线回归exit0。本轮只更换负责人薄入口的公钥pin和nonce SHA；12项受影响签名/范围/快照检查exit0，实际旧签名卡CLI拒止exit2。原采集器、评测器、STOP逻辑和判据不改。

仅M1-E60-R1正常ECG60bpm/1mV、非人体、R_RA/L_LA/F_RL、SKX电池且充电USB断开。只读取B；C保留原J5供电和CAN应答背景，C USB保持拔出；B无USB，J-Link板端在B。这不是B/C电气隔离，也不是PI独立签署。用户已知情接受SDK剩余风险并负责现场STOP/保全/断电，该责任沿用。

新私钥仅在Host内存存在，签唯一一张当期现场卡后释放，不导出、不冒用PI。PI固定根None保持；父/worker各原子claim一次、零重试。冷启动事实形成后再签，超过120s门即拒止，不回填时间。物理上电报告精度如实登记；分钟精度仅可按最早可能时刻保守核验。

原45s预热+120s评价、原120槽和有效HR60±2/至少118正确有效、250Hz双通道及派生RESP50、原seq/IRQ/status/flags完整性不变。75s预检、165s采集、20s收尾、260s会话/265s监督及原生预算不变。沿用原review，PI_trust_root_verified/field_scope_PASS如实保持false；只可另报负责人授权工程指标结论，不改原PI验收结果。SDK原生副作用UNRESOLVED和Close后态UNKNOWN继续保留。

如本场预检/采集/Close/评测失败，保存原件后停止，不重连/Go/Reset/Flash/补跑。ECG90仅后续准备，C设备控制、云端、B5START、其他23场、三板与固件写入均不授权。当前状态为WAIT_CURRENT_COLD_START_REPORT，尚未连接设备。
