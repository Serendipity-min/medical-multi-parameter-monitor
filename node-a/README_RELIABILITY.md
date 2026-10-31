# Node-A A1 脱机可靠性候选

原件在 A 分支首提交 `2c4885404723a0a7c303c8c0184940e9ed188108`。README_IMPORT 与源清单描述的是该首提交；当前活动 CANopen 适配已经修改，不能再称全工程原件未改。原 RAR 与 ZIP 身份、164 文件逐字节核对见 IMPORT_IDENTITY / NODE_A_SOURCE_MANIFEST。159 个原文件未改，五个原 CANopen 适配/OD 文件改动，另加两个小型策略头。UART、血氧/血压、双屏及看门狗任务源码均与原件逐字节一致。

- CO_RESET_NOT 正常推进；COMM 只重建 CAN 协议；APP 锁止 CAN、清可信时间与有效性，双屏/采集继续由原主循环调度，等待本地显式初始化。初始化错误不自动紧循环重试。
- 0x1017=500ms、0x1014=0x81，SDO 0x601/0x581；TPDO 0x181/381/481/681，保留 0x281 禁用位。SYNC=0x80，TIME=0x100。0x1018 vendor=0（无注册厂商声明），product=0x4D504D41、revision=0x00010001、serial=0（工程测试身份，不含设备 UID）。
- 实际 Node-A 帧流送入 C 的联合 Host 测试发现第五 TPDO 的 eventTimer 原描述错指 0x1804:04；已改为标准子索引 05、SYNCStartValue 改为 06。质量帧每秒刷新，避免 C 的新鲜度门控拒绝全部读数；首轮联合失败及修复结果均留存于 Gateway 候选证据。
- 时间只来自 CANopen TIME consumer。Gateway 获得可信 SNTP 后每 10s 发送标准 UTC TIME；Node 保存接收 tick 和消息毫秒分量的配对整秒边界。30s 无 TIME 即 epoch=0、有效位撤销；通信复位后必须重新授时。默认屏 RTC 不参与上云。CAN 总线无密码学身份，TIME 的可信性依赖 H1 对隔离实验总线唯一授时者的确认；物理实测延迟/UTC 精度尚未验证。
- PPG eventTimer=0，只在新重采样点请求发送；禁止栈启动/非 OP 的自动请求重复旧波形。输入基于现有 UNO ISR 接收 tick，两个实际点之间线性插值到 20ms 网格，禁止外推；超过 100ms 输入间断重建网格，超过 250ms 的积压丢弃并计数。质量 bit8 明确重采样，不宣称传感器原生 50Hz。源实际帧率与 ISR 接收时间和 ADC 时刻的差异待 H2 测量。原 CAN/屏双环仍独立。
- SpO2/PR 与探头、结果时效、暂停和显示算法已维护的值一致；非法/过期值清零且有效位清除。CAN 的 NIBP 90s 时效与网关/Backend 窗口对齐，测量中/停止中也清除 CAN 有效位；不改变本地屏的历史结果显示。
- 临界区跨 CAN/EMCY/OD 嵌套，恢复最外层原 PRIMASK；CAN_Init 失败返回错误。不重分配 UART 或 GPIO。

普通测试：`python node-a/tests/run_host.py --phase a1`，运行真实原 CANopenNode/OD/app，仅外部 CAN/UART/屏输入使用 Host 桩，不能代替 ARM 或硬件。Keil 使用既有 ARMCC 5.06u7 build960、原 uvprojx，`UV4.exe -r ... -o ...`，只构建，不加 -f/-d。最终 Keil 0 错误、0 告警，原日志与失败回执见 evidence。原件 Host 重复初始化断言确实失败；初次 Host 缺 LSS 链接项、修复中的首次 PPG 自动请求和 Keil 诊断变量依赖失败均保留，不掩盖失败。

本目录没有上板结论：未烧录、未读取 UID/Flash、未通电联板、未连接生产 Broker。H1/H2 需单独授权。
