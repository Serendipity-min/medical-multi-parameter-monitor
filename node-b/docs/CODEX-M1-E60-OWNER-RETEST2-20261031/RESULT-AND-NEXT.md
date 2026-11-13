# ECG60本轮结果与后续准备

OWNER_AUTHORIZED_ECG60_ENGINEERING_METRICS_PASS。现场源码c2085db160fd481259fe15a3a0a0223ad4c99af6；本次负责人直接授权，非PI独立签署。

父进程/worker/监督/采集/原评测器实际退出均0。45s预热+120s评价，120/120正确有效、缺槽0，有效HR观测值均60；原码序号无缺口，ADC状态/flags正常，观察采样率249.893938SPS。评价期原码29987条，按原seq派生RESP50为5997条。原始帧、IRQ、cycles、status、flags均保留，无插值或补点。稳定原码41233条，1060块；Host采集164.969s，会话194.25s，Close返回，后态UNKNOWN，SDK残余风险UNRESOLVED。

B当前身份、完整Flash和options均与同次历史参考一致。前两次失败仍保留，不折算为三次独立合格重复。原正式review的PI_trust_root_verified=false和field_scope_PASS=false保持原值，原status为M1_OFFLINE_RATE_METRICS_ONLY_UNVERIFIED_PI_ROOT；本报告依据真实负责人授权及原数值判据另报工程指标通过，不改写PI验收。

负责人已确认B/C断电、板卡全暗、C USB和J-Link电脑USB拔出；J-Link板端B、CAN和导联不变，SKX已设置正常ECG90bpm/1mV。新指示是继续90然后准备120。90采用新独立nonce/签名/会话，不能重用已消费的60卡。当前90计划及菜单已准备，但尚未采集；120尚未设置、尚未采集。

所有原件、同次制品、源码快照、输入哈希、退出回执和原签名存于EFS，定位node-b/build/m1-owner-retest2-pointer.json。未操作C串口/云端、未发B5START、未显式Reset/Halt/Go/Flash；不改变RR15的SOURCE_UNKNOWN/ROOT_CAUSE_UNRESOLVED。
