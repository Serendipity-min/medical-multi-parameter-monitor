# C49132与Node-B微调度候选三路独立窗口｜R6

状态：PROPOSED_NOT_FROZEN（草案预注册，默认禁用，等待PI正式书面签署；field_execution_authorized = false；不复用已消费的旧许可、旧START或旧令牌）。

## 1. 固件与硬件身份基线

唯一当前候选与基线：
- 实装 Gateway-C：49132B，BIN SHA `72131dbb5ef6bc0e0d33e328925c685403bae928aea9447a81f8291c6ae5c1ab`，ELF SHA `10051aa990cff78882d94870ad99509011f140439d01e76aa0e47f2bcfc44b0b`，完整 1MiB Flash SHA `9bba23b436f079183296fa98dcaeed047eb919ba8597d75a85bc144bc48417fd`，91份编译输入指纹 `84ea9a8699c5915ec2b5846374c04cf4fd845d2b0a4b17287143a2aa4643639e`。
- 候选 Node-B（微调度补丁）：41012B，BIN SHA `1dbbf27177caa429f037ac72c43581a519e8ff70ac6224411c9c4ffe9529432d`，AXF SHA `e11219c4de3718fc0832a6e6863ec9645836300197f36503cc13d8e8bd9923b7`，symbols SHA `07e2166e9a145bcbdbb592b475b789cf55553ee38cf97c1dd5fcf9aebe7853f8`。
- 历史实装 Node-B（基线对照）：40928B，BIN SHA `a1cf57648ca3787de30c1ad7055634c278fbbde538bb0bc562961bd212182ed2`，完整 Flash SHA `ceebec5a91835aed3cb70c683fd8de5142e5ba59a2163a1968cec182018b48ae`。
- gen5 参数保持；C 应用区不足 20 字节余量，严禁追加业务日志或代码重刷。
- ESP 在板供电非隔离例外须对此批显式确认沿用。

## 2. 独立 Scope 与判据定义

三个独立 scope 均绑定到当前 C49132 与采前冻结判据，严禁放宽或调整 criteria 参数：

| 对象 | 独立 Scope | 物理与信号配置 | 判据与质量标准 |
|---|---|---|---|
| E-R6 | `B5_FINAL_ECG60_R6` | 普通 60bpm / 1.0mV，R→RA，L→LA，F→RL/N，LL空置；SKX 电池供电、充电 USB 断开；非人体 MOCK。 | 45s 预热 ＋ 300s 评价 ＋ 15s 尾段，420s 业务硬停；ECG 连续源点 ≥ 74250，RESP 源点 ≥ 14850；HR 58–62 且有效标量 ≥ 295；RR 保持真实 INVALID/null；WSS 快照 ≥ 2900。 |
| T-R6 | `B5_FINAL_TEMP_OBJECT_R6` | GY-641V3 模块 3.3V/GND，TD→B PC11(UART4 RX 9600)，B PC10 仅输入；禁止写配置或改线；非人体物表。 | 至少 295 条有效 TEMP 标量，UART 源帧校验通过、源龄维持严格 `[-10, 2500] ms`，C TEMP_ENTRY 精确 seq/epoch/boot/采集报告 UTC 与源值核对，原 2ms 相位界保持；Broker→Backend→WSS 各层值一致；不伪造同窗 ECG/RR 有效。 |
| R-R6 | `B5_FINAL_RR15_R6` | 唯一批准冷态改线：黄L 从 LA 移至 LL/F，R 接 RA，绿F 接 RL/N，LA 空置；SKX-2000D+ 现场主菜单呼吸率【RR】= 15 bpm（严禁设为 30 bpm！），阻抗变化量菜单 1.5R，阻抗基准心率/呼吸波形周期菜单 30 bpm，窒息时间菜单 0s；SKX 电池供电，无充电 USB。 | RESP 50SPS、连续源点 ≥ 14850，RR 14–16 稳态有效 ≥ 295 条；无真实 QRS 时 HR 必须 INVALID/null；ECG 不宣称本窗有效；同源序号/CAN/UTC/Broker/Backend/WSS 完整验证。 |

> [!IMPORTANT]
> **SKX-2000D+ 模拟器呼吸工况设置防错核心规则**：
> - **主菜单呼吸率【RR】**：必须且只能设为 **15 bpm**。严禁误设为 30 bpm（误设将重演 R5 窗口因工况错设导致的不合格）。
> - **阻抗基准心率 / 呼吸波形周期菜单**：设为 **30 bpm**（作为 1.5R 阻抗调制载波基准）。
> - **阻抗变化量**：设为 **1.5R**。
> - **窒息时间**：设为 **0s**。

## 3. 机器准入互锁与现场执行硬门禁

1. **机器互锁拒绝未签署清单（Machine Interlock）**：
   - 主机准入程序 `validate()` 对 `version == 'R6'` 默认执行严格机器互锁拦截；
   - 必须核验由 PI 正式书面签署的 `node-b/evidence/B5-R6-PATCH01/R6-FREEZE-MANIFEST.json`（要求 `status == 'FROZEN_GATE_F_SIGNED'`、有效 `pi_signature` 且指纹匹配候选 B41012B）；
   - 若未签署或 `field_execution_authorized != true`，主机程序直接抛出 `CHANNEL_R6_FIELD_EXECUTION_BLOCKED_UNSIGNED_FREEZE` 阻断执行；禁止仅凭 `owner_approved = true` 绕过门禁。
2. **离线 MOCK 隔离**：
   - 离线单元测试与仿真验证必须显式声明 `execution_mode = 'OFFLINE_MOCK'`，严禁与现场实机令牌混淆。

## 4. 一次确认、逐对象独立消费规则

1. 逐对象独立性：每个窗口必须具备独立的私有令牌文件、数据输出目录、`.used` 标记、START 尝试记录与结束证据。一个窗口的失败不自动消耗下一窗口。
2. 启动与重置限制：
   - 每个窗口仅允许 `C 计划内人工 RESET ≤ 1`（在观察就绪提示后执行）；
   - 必须等待新 DISARMED 启动行核实后，才发送 `B5START\n`（严格仅一次 8 字节）；
   - `reset_confirmation` 必须为 `SERIAL_DISARMED_AFTER_INTENT`，且 `owner_manual_reset_preapproved` 为 `true`；
   - 禁止自动重试、禁止无限循环发送 START、禁止自动连续复位。
3. 时间与预算限制：
   - 准备时间 300 秒，启动行确认后 30 秒 START 门，60 秒共同就绪门；
   - 业务硬停门 420000ms（420s），20 秒被动观察；B 连接上限 755 秒；云驻留预算要求 `test_service_expiry_unix > time.time() + 805` 秒。
   - MCU 源 STOP 应达到 420000ms / reason1 / CLOSED7 / unsynced0 / pending0，保留原 419–422 秒主机观察门。
4. 预检新鲜度约束：
   - R6 批次严格执行 `preflight <= 3600s`，禁止继承 R5 批次 86400 秒临时特许；必须在断电前或实板准入时进行当期独立核验。
5. 安全停机与离线处理：
   - 遇到任何 ROM/HALT/Fault、身份或 Flash 漂移、UNSYNCED、原生 SDK 错误、TLS 异常、关键 worker 退出码非 0，立即执行 `STOP_TARGET` 并请求负责人安全断电；
   - 停止危险目标操作，转入离线安全排查，不自动执行任何 Flash 擦写、代码回退或向正式云服务转移。
