# ECG90负责人单次采集与ECG120准备

负责人已接收ECG60本轮120/120、HR全60、采集及review exit0结果；随后明确回复“已断电，90已设好，然后准备120”。据此继续同一负责人直接授权台架流程：仅一次M1-E90-R1，然后准备120，120不自动采集。新的上电提示明确说明本场为90；收到当期完成确认后才签卡连接。

复用原采集器、BLink、原评测器与同次B41012映射，仅将负责人薄入口的固定对象改为RUN_ID=M1-E90-R1/TARGET=90，签发者标签、公钥pin和nonce同步独立冻结；依旧拒绝其他run或旧E60卡。测试夹具改为读取固定对象常量，不开放命令行任意目标。没有算法或固件修改。

保持非人体正常ECG90bpm/1mV、R_RA/L_LA/F_RL、SKX电池且充电USB断开；B只读，C原J5/CAN背景，C USB拔出、B无USB、J-Link在B。现场责任及SDK剩余风险接受沿用当期负责人明确承诺。只需确认上电完成，无需精确时刻；卡一小时起跑有效、新nonce父/worker各单次claim、零重试。

165s原码窗口=45s预热+120s评价，120槽至少118正确有效、每条已观测有效HR为90±2；250Hz双通道原码、原seq/IRQ/cycles/status/flags与派生RESP50保留。Host I/O180s/总260s/父265s并预留20s收尾，STOP/身份/完整Flash/options/原生返回/ROM/HALT门不变。Capture及review分别记录实际码，Close后态UNKNOWN和SDK UNRESOLVED继续保留。

11项受影响范围/签名/无精确时钟检查通过exit0；真实旧E60卡CLI退出2。原采集器和评测器字节与ECG60成功现场版本一致，不重复无关历史审计。没有PI独立签署，原review中PI_trust_root_verified和field_scope_PASS维持原值；如通过，另报OWNER_AUTHORIZED_ECG90_ENGINEERING_METRICS_PASS。

120组只复用既有M0卡准备，不签、不采；其余频率、三板、C串口、云端、B5START、Flash、Reset/Go不开放。现场失败保留证据即停，不自动补跑。当前90菜单已由负责人确认，B/C断电，等待当期上电确认。
