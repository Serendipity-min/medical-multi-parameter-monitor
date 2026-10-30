# 2026-10-30 当前现场事实、失败与后续方案

## 指令冲突及真实执行路线

附件《P1-A PI 验收与 P1-B0 合同》只允许离线；已按原件保存、校验 SHA。同一条用户请求在附件要求之后明确说：“本轮读取C板和B板信息之后完成烧录，即可开始测试”，同时声明“已上电”，要求快速推进；并指示遇 ROM 等待负责人复位，不做根因排查。按照当期明确用户指令优先处理，这构成相对附件的实际范围修改。该修改没有等同于“PI 密码学签名已完成”。

现场没有启用 P1-B CLI、没有以 OFFLINE_MOCK 加载真实 DLL、没有把非空签名/自填 `owner_approved` 当作生产信任根，也没有 monkeypatch 旧 G3 验证器。实际通过本轮受监督交互调用方直接复用库函数；其中输入记录写了 `CURRENT_AUTHENTICATED_OWNER_SESSION_NOT_SIGNED_PI_GATE`，布尔和 SHA 用于记录已收到的当期指令，不是新的权限来源。临时路径绕过了旧业务 CLI 的签名准入流程，这是**已执行的交互授权路线**，不能宣称为符合未来完整 PI 门禁的自动化方案；交付后不得仅凭这些文件再次运行。

本轮实际云动作还包括恢复已有隔离 backend/TLS 两个测试单元，以及 RR 的 TLS/SNTP/AT/MQTT/WSS 采集链；均须如实披露，不能填写“云端零操作”。未修改正式服务配置/ACL/password、未 Broker HUP。完整正式三组测试没有执行。

## 动作时间线与版本

1. 从 `9f5a6641fec2bcdb575f5f9ff549b8e9b0223820` 新建独立分支，核对旧源码/引用。历史审计不重做。
2. 初始 J-Link 在 B，C USB 在 C，负责人已声明两板上电；一次 B 只读会话匹配 B40928 历史身份/全片/options，worker/supervisor 各 0。
3. 负责人确认“J-Link在C，仅C上电，C USB未接”；一次 C 只读会话匹配 C49132，全片/options/身份及 C49132 绑定 DISARMED flags；各 0。
4. 负责人确认“J-Link在B，仅B上电，C及C USB断开”；复用旧安装器烧录 B41012，48KiB sectors0/1/2 写一次，保留候选末尾至 sector2 尾部的原值，其他区域和 options 不变。真实 Halt/BeginDownload/WriteMem/EndDownload/Reset/Go 各一次；没有 ROM 恢复动作，返回值见安装摘要。
5. 恢复已有隔离测试单元，backend/tls 各 start 一次。正式服务 PID 和配置哈希保持一致。六小时 RuntimeMax 自 UTC 08:53:26 起，预计北京时间 22:53:26；未在收尾重连验证到期，账号/ACL未撤销。
6. 负责人确认两板上电、J-Link 在 B、C USB_UART 接电脑、未 RESET；系统当前枚举 CH340 为 **COM6**。模拟器 RESP15bpm、1.5R、apnea0s；独立菜单波形周期经负责人确认30bpm。J3、其余导联未修改，L 留 LL。
7. B/网络/串口准备后请求负责人 C RESET；负责人确认“C RESET已按一次，其余未动”。collector 观察新 DISARMED 后单次八字节 B5START，无自动重试。预热45s、评价300s、尾部15s，MCU业务硬停止420s，末尾被动观察20s。
8. RR 采集总监督546.188s（含准备期），worker/supervisor 各0。C 源码状态 STOP：business_elapsed=420000ms、phase7、reason1、required=written=851、unsynced=pending=0；仍有 live24/cache28，**不称全部队列清空**。B worker、COM、观察器及隧道退出。正式评测一次，NOT_PASS/3。
9. 最终负责人确认 B/C 关闭、C USB 与 J-Link 电脑端拔掉、全部熄灭；J-Link 板端在 B、L 在 LL，其余线保留。没有再次上电或查询硬件；断电状态是负责人目视报告。

本轮 SDK 会话：初始 B、初始 C、B 安装、B RR 采集共四个；不是四个“零控制只读”会话。未发生 ROM，未做 ROM 连接根因排查、自动恢复、第二次烧录或 RR 重试。

当前实装 B BIN 41012B SHA `1dbbf27177caa429f037ac72c43581a519e8ff70ac6224411c9c4ffe9529432d`，完整 Flash `9ff8133d06330a4b05cb15d26bfb51b6f7e1197014692c5267d178d744f4287d`。安装使用已接受候选 BIN；RR 源符号选自同一次 `b4-arm-20261030T062335164483Z`：AXF `e11219c4de3718fc0832a6e6863ec9645836300197f36503cc13d8e8bd9923b7`、symbols `07e2166e9a145bcbdbb592b475b789cf55553ee38cf97c1dd5fcf9aebe7853f8`。没有混用后来构建 AXF。

## 当前 RR15 正式失败

冻结评测器 SHA `14838db66a5142f24a010109de6f67a76d4f386a0b3914afb5b32b9a751dda91`，本轮未修改；R5 criteria 及历史记录保持原样。私有正式报告 SHA `deb0c703a5d25c72c6fe737358fcbf9603d098f20861ac2f56df7df0398654c3`。

失败集合：`B_RR_VALID15_HR_INVALID`、`HR_EXPECTED_INVALID`、`WSS_TARGET_CHANNEL_INVALID`。评价期 RESP14994 点；ECG74226 点在 RR 模式不是目标通道，不额外拼成 ECG 窗口裁定。Broker2774，Backend accepted2774/rejected0/dropped0，WSS2974 snapshots，观察到目标波形301批；不能仅凭这些计数宣称云链路和生理条件全部通过。

B 诊断600帧全部 RR15，其中20帧 HR非零；10次云 HR更新分布在约13.93、53.93、54.93、88.93、89.93、90.93、114.93、165.93、166.93、177.93s，HR为52/64/82/73/38/58/39。六个 B 诊断簇见 [RR15-HR-offline-causal-summary.json](../../evidence/CODEX-R6-P1B0-20261030/RR15-HR-offline-causal-summary.json)，云/B offset使用各自产物定义，不混当同一瞬间。

HR有效帧 ECG RMS 约41–58 codes，mains fraction约0.89–0.92，与无效帧范围重叠。ADS通道增益寄存器为4；名义2.42V参考换算约3–4.2μVrms，**不是校准测量**。现有算法峰值门槛含30codes/2.5倍带内RMS，工频拒绝条件为 fraction>0.95 且 raw_power>10000，本窗不触发。此证据支持低幅噪声造成过检的可能性，尚不能确认“模拟器没有真实QRS”；说明书亦不足以证明当前实际接线输出。不得先抬阈值、硬置 HR=0、伪造 lead-off 或调低验收门槛。

后续方案：先保留六簇、前后无效帧和现有原始 ECG 为固定离线负例，核对实际 ECG 成分/质量判定；若需核心算法修改，另立最小候选与已知 ECG60/90/120 正例守恒要求，PI 审查后冻结。此次不修改算法或补跑实板。

## 同窗 TEMP 的额外观察与工具偏差

这不是独立 TEMP_OBJECT 正式窗口。600个诊断中46个负 age，22个不满足原 `[-10,2500]ms` 范围，最小-22ms、最大202ms；B41012 没有证明已满足该判据。

`b4_runtime.snapshot` 先读 BIO，再读 ADC/寄存器/CAN/ESR，最后读 TEMP。它用两个时刻的 MCU 字段计算 age，存在非原子读偏差。根据实际原生返回日志，995个 BIO 与995个诊断按顺序一一对应，再取后继 TEMP 读；评价期600条全部匹配，BIO→TEMP返回跨度0/16/32ms（最小/中位/最大），主机 monotonic 报告分辨率15.625ms。不能把这些主机跨度当作精确 MCU 校正，也不能将负age全归因于固件调度。

第一次离线匹配使用严格小于时间戳，遇相等时间戳会配到前一帧，报告出现虚高跨度。原件保留为 `RR15-TEMP-read-skew-analysis.json`；正确的顺序配对结果是 [RR15-TEMP-read-skew-analysis-02.json](../../evidence/CODEX-R6-P1B0-20261030/RR15-TEMP-read-skew-analysis-02.json)，明确 supersedes 前版。`age+host_span` 仅为诊断估计，不可代替冻结原始 age 或重判 PASS。

建议先离线设计 **BIO1→TEMP→BIO2** 夹逼读，保留两次 MCU tick、TEMP tick、主机区间及原码，以同一采样 epoch 或边界建立可证实的观察口径；必要时再讨论固件原子快照。新现场读取增加次数须另授权并冻结工具，本轮未实施。不得用 clamp 归零或改 reviewer 掩盖失败。

## 封存和下一步

本轮仅复用工具并做必要薄入口、Mock和 joint 调用参数改动；核心固件、驱动、安装器、云业务逻辑、旧联评器、旧卡都未改。私有 UID/整片/Options/凭据/真实端点不上 Git；公开摘要和关键私有原件摘要索引足够定位当期执行，不把历史副本说成两次新读。

当前停在 PI 审查：B/C 后续单板申请 HALT、可信现场签署未就绪、SDK残余未解决、Gate F未签、RR15未通过、独立TEMP/ECG60未跑、B5结项拒止。已提出可执行的离线排障方案；停止目标后没有停止安全证据分析，也没有擅自扩大现场次数。
