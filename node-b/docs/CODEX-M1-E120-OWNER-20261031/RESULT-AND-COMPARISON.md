# ECG120本轮结果及ECG60/90/120对照

OWNER_AUTHORIZED_ECG120_ENGINEERING_METRICS_PASS。现场源码60381603c1f2044693ddf37c0f12888e6ed0e75e。负责人直接授权的非人体工程试验，不是PI独立签署验收。

| 速率 | 正确有效槽 | 有效HR观测值 | 父/worker/采集/review实际退出 |
|---|---|---|---|
| ECG60 | 120/120 | 60 | 全0 |
| ECG90 | 120/120 | 90 | 全0 |
| ECG120 | 120/120 | 120 | 全0 |

每种速率本轮各一次合格试采；不等于各三次独立重复已完成，也不代表全项目/三板/云端验收。前两次60失败、原native返回和旧nonce仍保留，不重新打印或覆盖为通过。

ECG120保持45s预热+120s评价、原120槽与HR120±2判据；无缺槽，评价快照中HR无失效，有效HR观测均120。原码序号无缺口、ADC状态及flags正常，观察采样率249.895453SPS；评价期原码29987条、按原seq派生RESP50为5997条。保存原始CH1/CH2、seq/IRQ/cycles/status/flags，没有插值、补点或改写时间。

本次1060块，Host采集165.125s，完整会话194.453s，父/worker/监督/采集/原review均exit0，Close返回。Host耗时略过165s但在既定180s I/O余量内，原码评价仍严格按[anchor,anchor+165000)裁剪；总260s/父265s及收尾预留保持，未降低原评价判据。实际关闭后态UNKNOWN，SDK原生剩余风险UNRESOLVED；这不因本场通过而关闭。

B当前身份、完整Flash/options与同次B41012参考一致。没有固件、HR算法或阈值修改；未显式Reset/Halt/Go/Flash、未发B5START，未操作C串口/云端。RR15的SOURCE_UNKNOWN/ROOT_CAUSE_UNRESOLVED维持原值。

原正式review退出0，status=M1_OFFLINE_RATE_METRICS_ONLY_UNVERIFIED_PI_ROOT，PI_trust_root_verified=false、field_scope_PASS=false如实保留；依据当期负责人直接授权和原数值判据另报工程指标通过，不冒充PI验收。输入hash、原签名、父/worker claim、源码和完整数据均受限保存。

用户结束后回复“已断电”，确认B/C关闭；按当期收尾问题，C USB保持拔出、J-Link电脑USB已拔，板端J-Link在B、CAN及R_RA/L_LA/F_RL不动，未按RESET。SKX设置最后确认为正常ECG120bpm/1mV，不推断模拟器是否另行关闭。

证据定位：60为node-b/build/m1-owner-retest2-pointer.json，90为node-b/build/m1-owner-e90-pointer.json，120为node-b/build/m1-owner-e120-pointer.json；私有UID/完整镜像/原始数据只在EFS。对应公开摘要、校验清单和三组对照随本目录交付。当前无后续会话或新卡，停止设备操作。
