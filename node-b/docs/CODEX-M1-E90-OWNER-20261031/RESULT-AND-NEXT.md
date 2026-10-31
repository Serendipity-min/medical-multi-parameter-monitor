# ECG60、ECG90本轮结果与ECG120准备

两场均为负责人直接授权的非人体工程试验；不是PI独立签署验收。

| 场次 | 现场源码 | 正确有效槽 | 有效HR观测值 | 父/worker/采集/review退出 |
|---|---|---|---|---|
| ECG60 | c2085db160fd481259fe15a3a0a0223ad4c99af6 | 120/120 | 60 | 全0 |
| ECG90 | 73d07c70f8e5184a27cddc99f371b76058f38152 | 120/120 | 90 | 全0 |

两场均保留45s预热+120s评价、250Hz原始CH1/CH2及派生RESP50，原seq/IRQ/cycles/status/flags不改；无缺槽、原码序号无缺口、ADC状态和flags正常。ECG90观察采样率249.892424SPS，评价期原码29987条、派生RESP50为5997条；1060块，Host采集164.953s，会话194.25s。Close返回，关闭后态UNKNOWN，SDK原生剩余风险UNRESOLVED。

B身份、完整Flash/options和同次B41012映射匹配，无固件/算法/阈值变更。前两次60失败原件与计数保留；这两场不表示各条件三次独立重复已经完成。RR15的SOURCE_UNKNOWN/ROOT_CAUSE_UNRESOLVED不变。

原评测器exit0，但因生产PI根未配置，原PI_trust_root_verified=false和field_scope_PASS=false保持原值，原status为M1_OFFLINE_RATE_METRICS_ONLY_UNVERIFIED_PI_ROOT；本报告依据负责人真实授权和数值判据分别标记OWNER_AUTHORIZED_ECG60/90_ENGINEERING_METRICS_PASS，不改原正式review。

ECG90结束后已请负责人关闭B/C及拔J-Link电脑端USB，保持C USB拔出；J-Link板端B、CAN和导联不动，SKX设正常ECG120bpm/1mV并保持B/C断电。负责人回复“已完成”，确认B/C断电全暗、J-Link电脑USB/C USB均拔出、正常ECG120bpm/1mV已设好。120禁用计划已登记当期菜单，仍未签卡、未采集。不要求提供上电秒数。

ECG60证据定位node-b/build/m1-owner-retest2-pointer.json，ECG90定位node-b/build/m1-owner-e90-pointer.json；完整原件及私有镜像/身份仅EFS保存。未打开C串口或操作云端，未发送B5START，显式Reset/Halt/Go/Flash为0。当前120准备已完成，B/C保持断电，无新的设备连接。
