# ECG120负责人单次采集计划

负责人已确认正常ECG120bpm/1mV、B/C断电全暗准备完成，随后明确要求“采集120组，已上电”。本次授权仅一次M1-E120-R1，沿用已成功采集ECG60和90的同一工具链；没有后续场次自动授权。

基线31c8c9f880e8fb08f2ea876b6ebf0c069f2151b7，仅变更负责人薄入口的固定AUTHORITY/RUN_ID/TARGET和本次公钥pin/nonce SHA。采集器、评测器、算法、固件、映射、测试字节不改。11项受影响范围/签名/无精确时钟检查exit0，实际旧90卡CLI拒止exit2。所有原失败和旧计数保留。

现场条件沿用当期准备确认：非人体正常ECG120bpm/1mV、R_RA/L_LA/F_RL、SKX电池且充电USB断开；只读B当前B41012，C原J5/CAN背景、C USB拔出、B无USB、J-Link在B。不是B/C电气隔离，用户负责STOP/保全/断电，SDK原生剩余风险UNRESOLVED。

不要求秒级上电时刻或120s抢签；电脑记录收到完成确认的时间，不冒称物理精确上电时间。新独立卡一小时起跑有效期、单次nonce父/worker原子claim、零重试。原码165s=45s预热+120s评价，120槽至少118正确有效，每条已观测有效HR须120±2。250Hz双通道、原seq/IRQ/cycles/status/flags和派生RESP50保留。I/O180s/总会话260s/父265s并预留20s收尾，STOP/身份/Flash/options/只读地址/原生错误/ROM/HALT门保留。

采集和review各留真实码；原PI根None和正式review的PI_trust_root_verified/field_scope_PASS不改。如通过只另报OWNER_AUTHORIZED_ECG120_ENGINEERING_METRICS_PASS，不代表PI验收、三个频率各三次独立重复或全项目完成。未改旧RR15 SOURCE_UNKNOWN/ROOT_CAUSE_UNRESOLVED。

除该次B读取采集，不执行C串口、云端、B5START、Reset/Halt/Go、Flash或其他频率。失败保留原件后停止，不重连、不自动补跑。当前仅冻结工具，尚未连接设备。
