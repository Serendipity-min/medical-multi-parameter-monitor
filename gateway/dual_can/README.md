# MPM-B4-001 软件目标 B4-0.1

独立分支 `codex/node-b4-dualbus-software-20261023`；B 基线 `9988d37cd5470d6857bb535aab1d821cf2581302`，H3 参考 `a5cdd5b0b1ad48108fd631136e9de69e30582f2d`。仅软件验证，所有 BIN 均不具备本轮烧录资格。

| 独立总线 | 两端控制器 | 业务 Node-ID | 位率与终端 |
|---|---|---|---|
| A 段 | A CAN1 ↔ C CAN1 | A=1、C=3 | 500kbps，两端各120Ω |
| B 段 | B CAN1 ↔ C CAN2 | B=2、C=3 | 500kbps，两端各120Ω |

C 使用两个独立 CANopenNode 消费端口，身份均为同一个业务 Gateway 3；OD、HB、SDO、队列与物理入口分开。C 汇聚业务数据，不转发两段 CAN 报文。NMT 按节点选择总线；TIME 和 C 心跳分别在两段发送。错误总线上的节点 PDO/HB/SDO 回执被拒绝。通信复位不重启 ADC、BIO 或屏幕；Node-B 拒绝远程应用复位。

## B2 线协议

沿用 H3 的五路 PDO 布局，每帧8B、小端；SDO 0x602/0x582、HB 0x702/500ms、EMCY 0x082。PDO5 使用厂商扩展 0x680 基址，避免与 SDO 冲突。

| COB-ID | OD | 数据 | 频率 |
|---|---|---|---|
| 0x182 | 2110:01/02 | ECG int32 µV（名义 ADC 换算）+ 原采样 tick u32 | 250Hz |
| 0x282 | 2111:01/02 | RESP int32 相对量×1e6 + 原采样 tick u32 | 50Hz，250SPS每5点抽取 |
| 0x382 | 2120:01..04 | HR×100、RR×100、TEMP×100、保留，均u16 | 1Hz |
| 0x482 | 2100:01/02 | UTC 秒 + 对应整秒的 B TIM2 tick | 1Hz |
| 0x682 | 2130:01/02 | 质量位u32 + 通信启动代次u32 | 1Hz及变化时 |

质量位0/1为本通道算法资格通过的波形，2/3为HR/RR有效，4为TEMP有效，31为合成来源。真实B不设置31；Host夹具在模拟器入口另行标记合成，绝不上云。TEMP尚无实现，值0且位4恒清零。未收到可信TIME或超过30秒失效，撤销CAN有效资格；算法与屏幕继续运行。

ECG换算使用已冻结 BIO 显示缩放和名义 Vref=2.42V、已核验CH2 gain=4；未作绝对幅度标定。RESP始终为相对量，不表示Ω。菜单 R、基线 Z0、ΔZpp 未标定，不补造数值。

B 用 H3 Node-A 静态端口及字典作参考，复用固定 CANopenNode `9b8beed8367241e96ac03f916cd5a500bcb2cf23`。应用遥测对象 SDO 只读。算法源 SHA 固定为 `3adca55cb1eb1fa3ed8e4148f837287d0454bcc2c08ae77a8f73deb1dac156a7`。构建仅在副本中加入 FrameFeed 后置钩子，CAN与ADC共用TIM2毫秒域，不混入屏幕10ms时基。128点有界队列、每次最多8轮；过期/溢出计数，不阻塞采集。Host已验证邮箱停顿期间23250个BIO样本持续推进。

## Gateway 模型、内存与压力

保留 Topic、单位、来源、有效性、会话和原样本末点时间。ECG按100点/400ms分批，RESP/PPG按50点/秒；`sample_rate`仍分别为250/50。Backend与浏览器按样本数量和速率还原时间轴，无需云端代码修改。旧的250点构建 ABI 默认不变；B4全目标统一 `MP_FRAME_MAX_SAMPLES=100`，混链负例编译失败。

B4实时16槽、历史64槽；旧目标仍16/32。5秒发布暂停测试无丢弃，补传50条。更长中断与超容量会发生有计数的有界丢弃，不保证无限断网无损。单路128帧TX队列、96槽RX环（可用95），各路独立预算；CAN2阻塞不能饿死CAN1。ISR每次最多处理FIFO的3帧，协议回调在主循环，每帧立即消费RPDO，避免单槽覆盖。未来毫秒帧留队等待，不误丢。

名义250SPS的历史数据包含少量3/4/5ms整数时戳间隔。B4保留原时戳，单步及批次累计相位允许±1ms，不插值；8ms真缺点、重复和倒序仍清批。正常与量化时戳夹具分别验证。B/C发送邮箱选择请求FIFO顺序，避免同COB-ID多邮箱积压时被低号邮箱超车。

最坏100点ECG JSON=1493B，实际coreMQTT PUBLISH=1534B，均小于2048B。未授时记录不入MQTT队列，不造UTC；0毫秒仍可在本机被格式化成合法JSON。温度缺失输出INVALID/null。保留A的血压完成tick、同值身份、90秒时效和代次校验，不能把旧结果当新测量。

## C 资源审查

| 资源 | 软件核对结果 | 实物缺口 |
|---|---|---|
| C CAN1 | PA11 RX、PA12 TX、AF9 | 原H3通道保持；本轮不操作 |
| C CAN2 | PB12 RX、PB13 TX、AF9 | 当前C板P4、U2实物版本/跳帽未现场核验 |
| 板图V2.0第5页 | P4 1/2为CAN2_RX/PB12，3/4为CAN2_TX/PB13；U2=TJA1050/5V，R1=120Ω | V2.0图不能替代V3.1等实际板卡确认 |
| 共享资源 | CAN2依赖CAN1时钟；CAN2SB=14，bank0..13给CAN1、14..27给CAN2 | 尚无实板寄存器及收发证据 |
| C 时钟 | 沿用H3的8MHz HSE，PCLK1=8MHz；1×16TQ=500kbps | 驱动同时支持42MHz/6×14TQ，拒绝其它时钟 |
| I²S2 | PB12 WS/PB13 CK与CAN2冲突；默认PB15 SD | 未来INMP441实际布线未确认，不能宣称兼容 |

CAN2必须保持CAN1时钟开启，禁止运行中单独复位CAN1或重分共享过滤器。[ST双CAN说明](https://community.st.com/stm32-mcus-60/stm32-in-dual-can-configuration-bxcan-filter-bank-explanation-and-relation-with-can2-start-bank-parameter-136737)、[RM0090](https://www.st.com/resource/en/reference_manual/rm0090-stm32f407-advanced-armbased-32bit-mcus-stmicroelectronics.pdf)支持时钟/过滤器规则；[STM32F407数据手册](https://www.st.com/resource/en/datasheet/stm32f407vg.pdf)列出AF9与I²S2复用。

编译宏 `B4_I2S2_PB12_PB13=1` 与本目标互斥。不能简单改用PB10作为I²S2时钟，它也是当前ESP USART3_TX路径；I²S3 PC10/PC12等替代需另审所有UART/SDIO/JTAG资源。本轮不改麦克风或语音固件。

## 仅离线复现

```text
python node-b/tools/run_b4.py
python node-b/tools/build_b4_arm.py
python gateway/dual_can/build_arm.py --network-link
python gateway/canopen/build_host.py
python gateway/canopen/tools/check_canonical.py
```

Keil ARMCC5、MinGW和ARM GCC/STM32 SPL来自既有本机安装；外部DSP按固定SHA核验。C完整网络目标只从冻结H3提交提取源码到构建目录，不包含任何真实凭据，不执行固件或建立连接。旧参考模型头按本目标100点ABI替换，并单列实际头文件SHA；冻结传输C源未修改。此目标没有声称已复现实板H3镜像或已验证配置区恢复，C烧录须先取得其备份与分区审查。

全部实际结果、部署冻结和残余风险仅汇总于 [唯一阶段交接报告](../../node-b/docs/B-PRECAN-CLOSEOUT-FINAL-HANDOFF.md)。本目录不是现场操作授权。


## B4-0.2 隔离C台架及恢复工具（软件准备完成，未部署）

`python gateway/dual_can/build_arm.py --bench` 构建独立 `B4_GATEWAY_BENCH`：不链接ESP、MQTT、持久配置读取、Flash写入、INMP441或语音驱动；实际ELF符号及源白名单再次核验。`--bench`与`--network-link`互斥，后者仍只是旧完整网络链接回归，不能用于此次隔离台架。

本地TIME以固定2020-01-01测试纪元加MCU单调时基生成，每10秒刷新；它**不是校准UTC**，不读取屏幕RTC，不上云。CANopen TIME帧本身不能表达这个来源，隔离边界靠本固件完全没有网络入口以及明确的RAM诊断 `test_time_only=1` 保证，不能把本台架记录导入正式LIVE数据。首次台架仅B段发NMT到Node2；A段协议发送关闭，CAN1共享时钟保留，底层仍初始化双CAN而未启用音频。外部ESP模块自身是否自动联网仍属于未来实物隔离核对，程序不初始化它不等于证明其供电后无线状态。

软件窗口180秒，结束关闭两段协议发送和TIME资格，不复位。`g_b4_bench`保存启动/停窗状态及16条有界聚合记录，覆盖计数明确；它不是连续原始帧采集器，RAM快照也不能冒充原子同步采样。未来实测仍需独立采集B原码/诊断和CAN回执。内部Router的online/ack仅代表本地RAM消费者，绝非WiFi在线或MQTT ACK。

台架链接脚本把应用限制在Flash前48KiB（sector0/1/2），不能覆盖0x0800C000后的配置区。当前构建21700B，仅软件候选；这不证明C现有配置位置或实际板状态。恢复工具依据真实候选长度选择扇区，不能因为链接允许48KiB就固定擦满48KiB。

`python node-b/tools/run_b4_bench.py` 运行纯Host台架协议及合成NOR回归。B4恢复工具入口为 `python node-b/tools/b4_recovery.py --help`：

- `prepare`核对两份完整1MiB Flash、两份16B options、前后身份与RDP/WRP；核对候选SHA、栈/Flash入口和48KiB上限，生成受影响扇区安装包、原始扇区回退包及期望完整镜像。
- 新BIN末尾到擦除扇区末尾使用现场原件填充；sector3和之后逐字节保留。`verify --phase installed/restored`分别与期望完整镜像/备份整片比对，同时核对options、身份和包清单SHA；头部相同但配置区损坏仍失败。
- 实际整片、身份、配置及包只允许既有受限EFS目录；输出独占创建、失败不覆盖。合成模式只允许build目录、显式假UID及镜像标记，绝不把真实原件当合成夹具公开。
- **该工具只有文件输入输出，没有SDK连接/读取/下载入口。** 一致的双文件不自动证明独立实板双读；后续读回器、实际布局审查、有限现场操作与恢复演练仍需单独授权和补证。现在不生成真实C恢复包，不伪造其备份存在。

B恢复目标始终是已验收25488B修正版及对应完整Flash；旧25284B只作历史。B CAN候选39948B跨32KiB，不能调用旧固定32KiB last-round下载工具；新工具的离线NOR模型验证了sector0/1/2和部分编程失败后的原件回退。

资源资料详见[本轮来源及核对](../../node-b/evidence/B4-001/bench-r1/resource-audit.json)，构建/负例/加密归档见[台架阶段结果](../../node-b/evidence/B4-001/bench-r1/stage-results.json)。不修改H3、P4、P5/P6或语音分支，不改变BIO阈值。


## B4-0.3 ECG单位修正

旧软件候选39948B使用`display*242/600`（gain6），现已撤销其硬件部署候选资格并保留原件。CH2SET=0x40对应gain4，与冻结初始化RREG缓存一致；BIO显示量约为滤波ADC码×10^6/2^23，正确通信换算为`int64(display)*126877696/209715175`整数µV，网关统一除1000输出mV。其中已补偿TI第29页LSB分母2^23−1与UI分母2^23的差异；整数除法向零截断，显示量→µV误差<1µV；上游UI量化/滤波与Vref误差另计。参考2.42V未经绝对校准，不改变ADC寄存器/滤波/算法阈值，不能借此解释或修复既有HR周期失败。

新39948B B候选SHA256 `676eb7a46ad9cd15c7bf93db51a1931d7711d37c6f2fd636197dc4a85b339b82`，仍需评估sector0/1/2；C21700B隔离候选不变。`run_b4.py`新增真实B入队/PDO字节→网关mV JSON→既有Backend序列测试，涵盖正负、INT32边界、2000001个显示输入及65536个随机输入；最坏MQTT1534B<2048B。软件通过不能继承为实板电压/同步有效性或CAN传输PASS。

精确C只读卡、同窗补证卡及G4尚缺门禁见[本轮准入审查](../../node-b/docs/B4-HARDWARE-ADMISSION-REVIEW.md)。
