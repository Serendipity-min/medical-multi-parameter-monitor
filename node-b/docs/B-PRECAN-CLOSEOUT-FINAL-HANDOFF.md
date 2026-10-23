# Node-B 当前阶段唯一交接报告｜B4-0.3

2026-10-23，MPM-B-PREC-001状态冻结及MPM-B4-001软件/隔离实板准备。**最新状态：B39948B候选已安装→恢复原件→重新安装，均整片核验通过；C曾观察ROM/HALT；完整原件未变，随后按追加授权一次正常复位＋有条件Go，原H3已恢复Flash运行。C根因仍UNRESOLVED，未烧录C候选、未开始180秒CAN窗口，联动准入仍BLOCKED。** 下列历史软件/冷启动章节保留原时点，当前状态以本节和“本轮G4实际结果”为准，不把软件测试写成实物验收。

## 本轮G4实际结果（最新）

| 项目 | 实际结论 | 边界 |
|---|---|---|
| B候选安装与恢复 | **B_INSTALL_RESTORE_REINSTALL_FULL_VERIFY_PASS** | B候选39948B/SHA676eb7…，sector0/1/2；三次操作均完整1MiB、options、扇区外原尾部核验及Flash启动通过。恢复时整片SHA为原d2ea7c…，再安装后a1abed…；不是CAN或生理验收 |
| B采样短窗 | **B_ADC_SHORT_WINDOW_OBSERVED_PASS** | SKX开机后约249.933 SPS，935点推进，新增削顶0、ADC错误不增长；仅短窗，不能替代完整CAN共同评价 |
| C启动核验 | **C_ORIGINAL_FLASH_BOOT_AFTER_ONE_NORMAL_RESET_PASS** | 当前已恢复原H3，末次4组PCSR在Flash、VTOR=0x08000000、CFSR/HFSR=0。下列为此前异常原件： 同一C身份/保护寄存器与备份包相符；首次PCSR三个样本均在ROM，VTOR=0x1FFF0000；负责人要求复核一次后PCSR=0x1FFF36C8/36B2/369E，VTOR仍相同。复核DHCSR=0x01010001、CFSR/HFSR=0、MEMRMP=0、RCC_CSR=0x0E000000。未读取复位瞬间BOOT锁存，不确定进入机制 |
| C候选/恢复 | **NOT_EXECUTED_ROM_ENTRY_BLOCKED** | 当前备选为23744B/SHA73d113…，仅软件冻结；首次及复核各44次SDK调用、reset/halt/go/write均0且未开始下载。随后按负责人排查要求保留原暂停态，仅只读核心/1MiB Flash/options/ROM，223次SDK调用、状态控制/写入0，整片1c7ea8…和options均与原件完全相同；C恢复演练未执行 |
| CAN真实收发/恢复 | **NOT_TESTED** | 物理接线与60.8Ω为负责人已报告事实；没有C候选、NMT/TIME或完整实测窗，不能签发收发PASS。未进行故障注入 |
| 同窗HR/RR | **NOT_VALIDATED** | SKX曾关机，B曾观察CH1正满量程、CLIPPED及HR/RR无效；之后负责人开机并报告默认普通ECG60，短窗削顶停止。未冻结当前幅度真值，也未取得共同稳态窗，不归因于算法阈值 |
| 历史ROM根因 | **CPU_ROM_ROOT_CAUSE_UNRESOLVED** | B历史ROM与本轮C当前ROM分别记录；本轮B工具退出造成的Flash HALT另列，不把它当作历史ROM已归因 |

本轮B运行监测器有一次新增退出路径缺陷：信号质量判断在启用健康Flash退出续跑之前失败，后一次读取实际观察HALT。已如实停止并保留失败原件；负责人单独批准有条件一次Go，执行前完整Flash/options/身份及实际暂停PC=0x08003AD0、MSP=0x20004C08均通过，实际Go1、reset/halt/download0，恢复后ADC推进。修正为健康CPU先锁定退出续跑，再解析RAM/质量；故障CPU仍停止。初始化错误拒绝入场，ADC累计错误保留原值，评价窗检查新增错误，不清零；此前bad_status=1不冒充本窗新增错误。14项运行判据及7项一次Go测试包含相关负例。

现场最新事实：B CAN1↔C CAN2，B P6 CAN_RX/PA11及CAN_TX/PA12，C P4分别CAN2_RX/PB12及CAN2_TX/PB13；B/C独立GND已连、断电测H–L为60.8Ω、A段断开、ESP已隔离、无外接INMP441/TTS。B为J5供电，C为USB_UART供电；没有虚记成C J5。板图第3页可追溯USB到板5V及收发器供电设计，但未新增实测电源电压。最后J-Link在C；C最后4组读取在原H3 Flash运行，正常关闭启用续跑；不追加复位/Go或重新刷写。

C新23744B候选SHA256 `73d1138f248188593f1be16e628b171a539e00867f324bcef36cdbe34310c0b6`。新增USART1/CH340 230400/8N1原始CAN及实际网关模型记录，32B固定帧带CRC/递增序号；256槽有界队列，满时显式丢弃计数。唯一接收命令B4START，每启动最多一次；等待最多5分钟，启动后180秒停协议窗口，不自动复位/重新武装。主机仅在C安装整片回执及B本轮新鲜READY均通过后发一次固定START；端口打开前DTR/RTS已禁用，不操作USB下载。500秒主机事务上限与180秒CAN窗区分记录；尚未在C执行该固件/串口采集。

121项B4/C Python测试（95项B4、18项C只读、8项C启动）、13阶段B4 Host回归、4阶段台架Host回归及C ARM构建通过；预期编译/参数负例分别保留真实退出1/2。C取证编码器在固定230400带宽模型下3260帧、CRC错误0、丢弃0；满环负例257帧且显式序号缺口1。180秒合成输入穿过真实CANopen/网关/Router及取证编码器，58315条记录、585次模型值/末点时间校验通过，评价窗ECG22500/RESP4500。均为离线结果，不能代替实板。新增取证后非取证网络目标曾因可选变量未使用退出1，修正同一控制器指针使用后，台架/网络ARM均通过；台架BIN SHA保持73d113…，网络链接回归38644B/SHA3e689a…只作软件产物，禁止用作本台架候选。新C原件恢复包sector0/1，清单SHA e32fdf3e…；旧21700B及所有失败轮次保留。BIO源/阈值、ADS寄存器和B已冻结BIN均未为此改变。

**负责人要求的C ROM归因排查：** 追加只读取证中真实暂停PC=0x1FFF36C0、MSP=0x20001D50。C系统ROM SHA ca1ae7…与此前B实际ROM逐字节相同；对照相同ROM反汇编，这是GPIO输入/下载接口检测循环，USART1/3的CR1及BRR均0，不是当前应用算法或Fault处理。实际Flash完整且与原件相同，不支持“固件被擦坏/本轮C候选导致”解释。H3参考目标C/H源码中未发现主动ROM跳转或SYSRESETREQ调用路径，仅有VTOR设回Flash；不能因此排除所有间接软件或硬件机制。

负责人确认C BOOT0/B1跳帽均接地，但曾插拔USB并见Windows识别警告。主机一度无COM15，随后负责人说明USB尚未接回；接回后CH340/COM15正常枚举，所以不把端口缺失当作硬件损坏或ROM根因。接回后只读仍为ROM向量及HALT，没有自动Go/复位。静态BOOT1输入为0，不是复位瞬间锁存；SYSCFG时钟在本轮快照未开启，MEMRMP读数0不能据以证明实际启动映射。

板图第2/3页显示BOOT0跳帽经R55=10kΩ接实际BOOT0，CH340自动下载电路Q3经R44=1kΩ也驱动该点，DTR/RTS同时参与RESET/BOOT路径。故跳帽接地不绝对排除USB电路驱动BOOT0；“USB/启动锁存”是待检验的主要假设，实际BOOT0后经负责人测得0V，排除当前持续被拉高，但未捕获复位边沿，不签根因PASS。[ST AN2606第34节](https://www.st.com/resource/en/application_note/an2606-stm32-microcontroller-system-memory-boot-mode-stmicroelectronics.pdf)支持F407系统ROM的启动条件与接口检测流程，不证明本台架的实际触发瞬间。已修正外部ai_serial_console的串口构造顺序为打开前固定DTR/RTS，纯替身验证通过、旧文件EFS留存；没有重载现有MCP进程或操作真实串口，这不是C实板修复验收。窗口中显式reset=0也不能当作硬件绝无复位的证明。

**C一次正常复位的实际回执：** 负责人单独允许一次正常器件复位、仅原向量匹配后Go≤1、零烧录。第一次连接44次SDK调用发现初态已变Flash，实际reset/go仍0，保留初态变化并未用其宣称捕获原因。按同一总动作预算核验当前原件并完成一次正常Reset、一次Go，第二次250次SDK调用。复位后真实PC=0x080080C8、MSP=0x20020000与原Flash向量一致，4组后采样均Flash、Fault0，RCC_CSR=0x1E000000。SDK正常复位出现软件复位标志，不宣称实测了NRST脉冲或BOOT锁存。原固件完整SHA1c7ea8…在动作前重新核验，Flash/options/PC-MSP-VTOR强制写均0，未安装C候选。结论只为当前原固件可恢复启动；USB/调试器/BOOT瞬态触发未捕获，CPU_ROM_ROOT_CAUSE_UNRESOLVED不变。源码更新同时确保健康Flash初态在后续解析失败时也启用退出续跑，计划复位前取消旧健康标记，失败不得隐式Go；相关8项负例/预算测试通过。

实际动作、负例、工具/源码及原件索引见[本轮G4证据](../evidence/B4-G4-001/stage-results.json)及[安装/恢复/复核回执](../evidence/B4-G4-001/B-install-recovery-runtime.json)。含UID/配置/Flash/BIN/原生SDK日志的文件仅受限EFS，不提交GitHub；所有下文“未烧录/旧候选”描述仅保留对应历史阶段。B当前部署见[唯一部署索引](../deployment/current.json)。下一步需PI裁定C残余启动风险及是否继续候选安装/恢复和隔离CAN窗口；本次仅完成原固件启动验证，不自动联动。故障恢复和同窗有效性仍需后续补证，不改阈值、不进入正式云环境。

实验分支 `codex/node-b4-dualbus-software-20261023`，独立工作区 `E:/medical-monitor-node-b4-software`。开工时远端B基线已核验为 `codex/node-b-precan-closeout-20261023@9988d37cd5470d6857bb535aab1d821cf2581302`；H3参考固定为 `a5cdd5b0b1ad48108fd631136e9de69e30582f2d`。仅此新分支提交推送；B/B2/H3/P4/main/P6/语音/历史实测分支与标签不修改，无PR、合并或Security Gate。

## 冻结后的三个状态分别签署

| 门禁 | 正式状态 | 证据边界 |
|---|---|---|
| 屏重启引发MCU复位修复 | **SCREEN_RESET_MCU_RESET_FIX_PASS** | 最新25488B实板修正版，屏白色供电/串口插头重启后恢复波形；221次观察中MCU运行时间和BIO计数持续推进，屏07上电报告只恢复UI，不再调用MCU复位 |
| 历史CPU进入ROM根因 | **CPU_ROM_ROOT_CAUSE_UNRESOLVED** | PC=0x1FFF32F0、VTOR=0x1FFF0000是真实历史观察，Flash完整；ROM中等待USART3接收得到支持，进入机制没有确定，不能写成算法丢失或已修复 |
| 独立冷启动 | **INDEPENDENT_COLD_BOOT_SINGLE_TRIAL_PASS** | 本次拔下B端JTAG及J5，负责人确认板/模块/两屏全部熄灭、等待10秒，再仅接J5；JTAG断开时波形恢复并持续刷新。接回后MCU运行时间由4871002ms降为34023ms，BIO计数由1216965降为8164并继续推进；Flash运行、无Fault。仅当前25488B的一次功能验证，不代表重复启动可靠性或B4新候选验收 |

J-Link退出时遗留Flash HALT导致画面冻结，与历史进入ROM是两个问题；退出续跑已修正并观察恢复。BOOT0约1.0mV、BOOT1约0.9mV只是200mV直流档的静态读数，不代表复位锁存。NRST未测。无新证据支持将ROM归因于BOOT跳帽、电源、USB或屏复位中的任何单一因素。负责人决定ROM根因保留未解决，待再次出现时排查；本次冷启动不关闭该问题。

[本次冷启动前后回执摘要](../evidence/B4-001/independent-coldboot-20261023.json)保留真实退出码、工具SHA、加密原件逐文件SHA及负责人观察。后核验运行时间34023→37174ms、BIO计数8164→8951；VTOR=0x08000000，运行PC采样均在Flash，CFSR/HFSR=0，ADC初始化/SPI/队列溢出/长间隔错误均0。RCC_CSR由0x1e000000变为0x0e000000，含BOR/PAD/POR、软件复位标志清除，佐证重新启动；不是BOOT锁存或电源波形测量。两次软件会话各连接/关闭一次，显式reset/halt/go及Flash写入均0，正常关闭续跑。负责人未给出独立观察的精确秒数，回读在启动34–37秒，不能宣称已测满原拟45秒。启动快照HR/RR均暂未有效，不作为双通道评价。先前开关对照未重启的反证保留在原冻结回执，不覆盖。

## 原独立验收恢复点（25488B，当前B4部署另见顶部）

CAN安装前已独立验收的修正版源码基线是 `9988d37`，**恢复冻结对象是25488B，BIN SHA256 `b8e74577dae7a5a1f6caa27687193f5128f89bd70781f06a1d80b0c74d409b44`**。旧25284B仅留作历史证据，永久退出新硬件部署候选身份。

- 最新修正版完整Flash：1048576B，SHA256 `d2ea7cbf7081b20f82a4a6ca6dde4918b9c4d4b194a3c6c358c2d74012993316`，前25488B与修正版BIN逐字节相同。
- options原件：16B，SHA256 `52d5979da03bd7be45e385920ec7d5901793bab3f6bc1daa0c1c1997f9e91687`。软件阶段未访问设备；追加冷启动前后只读核验已确认当前BIN及options一致，没有写入。
- BIO_V2源 SHA256 `3adca55cb1eb1fa3ed8e4148f837287d0454bcc2c08ae77a8f73deb1dac156a7`；全部冻结固件文件逐个核验，算法和阈值不变。
- 历史f713…整片、失败原件、旧工具SHA、ECG/RR实测数据和历史标签全部保留。

[部署入口](../deployment/current.json)现区分当前39948B隔离B4部署、25488B原恢复点及未安装C候选；原软件阶段的`hardware_deployment_authorized=false`只属于以下历史冻结清单。[冻结清单](../evidence/B4-001/deployment-freeze.json)包含完整源码文件SHA、AXF/符号/实板回执SHA。L1 BIN/AXF、L2完整Flash/options及本轮软件BIN/ELF/原始构建失败均在受限ACL、NTFS EFS加密目录；本轮又建立并逐字节校验了恢复副本。具体归档位置、加密核验和ZIP SHA见[阶段结果](../evidence/B4-001/stage-results.json)。Git不提交固件、设备身份、私有原码或私有配置。

## 既有工程结论与本轮离线发现

[ECG60/90/120 BPM各两轮通过](B-ALG-002-ECG-MATRIX-RESULTS.md)、[RESP12/18/24次分各两轮通过](RESP-E3-MATRIX-001-RESULTS-R1.md)保持原名义源速率范围。RR六窗共206025帧、681/681次稳态保存观察有效；本轮未覆盖或重算旧验收，不把这些不同模式的结果合并成同步通过。

本轮只分析既有E3的CH2和原Host滤波回放。每窗45秒预热后取90秒共同时间范围，原码与当次采集回执SHA核验一致。序号缺口、削顶和ADC错误均为0；毫秒域存在每窗24–28次非4ms间隔，这是实际时间量化/时钟差异的观察，不冒充物理采样时钟标定。

| 呼吸档/轮次 | HR有效观察/稳态观察 | 有效时出现的HR值 | CH2 49–51Hz能量占比 |
|---|---|---|---|
| 12/1 | 0/113 | 无 | 82.3% |
| 12/2 | 3/114 | 104×3 | 85.8% |
| 18/1 | 4/114 | 59×1、101×3 | 81.4% |
| 18/2 | 0/113 | 无 | 85.2% |
| 24/1 | 0/113 | 无 | 85.4% |
| 24/2 | 3/114 | 133×3 | 84.9% |

合计HR仅10/681次有效，主要为NO_CYCLES、UNSTABLE、EXPIRED，部分叠加MAINS。多数偶发有效值也不构成稳定ECG60输出证据。CH2工频主导、缺乏稳定QRS资格，支持“当前RESP模式下HR未通过”，不能仅归咎算法阈值；没有源端校准波形证据来区分输出能力、幅度、接线/共模等成因。**不签发B_ECG_RESP_SIMULTANEOUS_ENGINEERING_PASS，也不提前签发SOURCE_SIMULTANEOUS_CAPABILITY_BLOCKED。** 未使用未知输入真值计算准确率。

CH2直流/幅度/RMS、峰候选和接受增量、滤波幅度、原因码、失效观察时刻、ADC计数及原件SHA见[离线分析](../evidence/B4-001/existing-ch2-analysis.json)。回放是冻结C源Host结果，不是ARM逐位复现；保存诊断非原子，也不是每帧连续有效率。

J-Link拔下时RESP发生基线阶跃但周期/刷新继续，是负责人照片和观察；事发瞬间没有连续原码和精确事件时刻。地参考/耦合或机械瞬态只是待验证假设；不能据此认定MCU复位、ROM进入或阻抗幅度变化。不用改阈值/软件平移掩盖。后续若另批现场，应固定供电/调试器拓扑后再预热，并单独取得同源时间关联数据。

阻抗幅度保持 **IMPEDANCE_AMPLITUDE_NOT_CALIBRATED_INSTRUMENT_REQUIRED**：现有电池万用表不能完成32kHz动态阻抗绝对标定，按负责人要求跳过。Z0、Zmin、Zmax、ΔZpp仍为未知/null；R菜单和ADC codes不写成Ω。

## B4软件实现与资源核验

采用两段独立500kbps总线：A CAN1↔C CAN1、B CAN1↔C CAN2，每段两端各120Ω；业务身份A1/B2/C3。C双端口只汇聚业务数据，不转发两段CAN帧。B从旧Node3/1Mbps/单TPDO转换为Node2/500kbps/五PDO，线协议兼容H3对象布局。

B算法源、ADS1292R引脚/250SPS配置及屏重启修复不动；在构建副本内加入采集后置通信钩子。ADC/BIO/TIME都使用TIM2毫秒域，避免与屏10ms时基混用。静态CANopenNode、128点有界队列、过期/溢出计数、每次任务最多8轮；邮箱拥塞不复位或停止算法，应用SDO只读，NMT通信复位不影响BIO，远程应用复位被拒绝。尚未实现温度采集，CAN温度始终INVALID/null。

C CAN2为PB12/PB13 AF9，与I²S2默认WS/SCK冲突，编译互斥负例已验证。共享CAN1时钟与28组过滤器按14/14划分，禁止单独复位CAN1；保持H3的8MHz HSE，实际PCLK1校验后配置500kbps。V2.0板图第5页存在P4↔U2/TJA1050/5V及R1/120Ω，但当前C实际版号/跳帽/收发器供电未现场确认，不声明实物就绪。不改INMP441、语音分支或C实板固件。

Gateway保留H3的单位、来源、时间/会话、血压完成tick与同值身份校验。ECG每100点分批（250Hz），RESP/PPG每50点；全B4构建使用一致100点模型ABI，旧目标默认250点不变。真正样本缺口/重复仍清批，允许整数毫秒±1ms量化且整批累计误差限±1ms；不插造样本，不改BIO阈值。最坏ECG JSON1493B、完整coreMQTT PUBLISH1534B，小于2048B。

C完整网络软件目标复用冻结H3的MQTT/AT C源，在独立构建目录链接；公共模型头按B4 ABI绑定并记录实际SHA。没有真实凭据或配置写入，没有执行该固件、联网、云端部署或语音合并。新候选不能继承原H3实物验收，C配置区/恢复方案须在联动准入时单独确认。

协议/资源/复现命令见[软件目标说明](../../gateway/dual_can/README.md)。

## 实际构建与回归证据

- B ARMCC5：0错误、0警告；新BIN仅软件候选，身份/大小/SHA见[原gain6历史B构建](../evidence/B4-001/final-node_arm.json)，本轮修复后B构建见B4-003证据。当前实板仍是25488B修正版。
- C ARM GCC：双CAN、数据模型、Router及完整H3 MQTT传输链接成功；未下载。[最终C构建](../evidence/B4-001/final-gateway_arm.json)保留真实命令/退出码、头文件与参考源SHA。
- B4实际生产适配器产生正常250SPS和含量化间隔的编码夹具，经双总线真实CANopenNode消费；验证五PDO、TIME过期、NMT、SDO只读、错段/坏DLC、重启清批、8ms缺点/重复点、温度无效、单路阻塞隔离与有界溢出。Host不是实物验收。
- 5秒MQTT发布暂停期间CAN持续服务，无丢弃并补传50条；超容量负例有明确丢弃计数，不声称无限断网无损。
- 真实C输出经既有Backend解码与Hub：976条、11种流，其中222个100点ECG批次，温度88条均INVALID；未修改云端源码或启动服务。
- 原B普通回归7组全部退出0，算法27/27、通道隔离28/28；屏复位Host2项通过。旧CANopen协议12项、流水线11项、重启/分配回收17项通过。
- I²S2冲突及混用模型ABI均以真实编译退出1拒绝，这是预期负例；其它正式软件阶段退出0。原始失败轮次保留，不能只展示最后成功。

[最终Host回执](../evidence/B4-001/final-host.json)、[原B回归](../evidence/B4-001/final-baseline_regression.json)、[分级归档/失败历史/真实退出码](../evidence/B4-001/stage-results.json)提供复核入口。软件阶段新源码/工具/报告的冻结快照SHA见[源码索引](../evidence/B4-001/source-index.json)，此索引不覆盖随后冷启动报告更新；软件阶段Git交付见[交付回执](../evidence/B4-001/git-delivery.json)，追加冷启动提交另行推送及远端取回校验。

## 新增隔离台架与离线恢复准备（R3）

负责人确认C也为STM32F407ZGT6。本轮已从P4/P5/P6及语音分支核对资源，并读取本地神舟号板图、STM32数据手册及新INMP441 PDF；不再反复索要可查资料。P6明确麦克风仅预留、UART TTS不启用I²S；INMP441资料确认24位I²S/每帧64SCK。参考板PB12/PB13同时连接CAN2与WM8978时钟，PC3/PC2是板载音频数据路径，不能把预留PB15当已确认外接线。具体来源提交、PDF SHA和页码见[资源核对](../evidence/B4-001/bench-r1/resource-audit.json)；实际跳帽/外接线仍不能从文档推定。

新增 `build_arm.py --bench` 独立C台架：无ESP/MQTT、持久配置读写、INMP441/语音驱动，ELF符号及源白名单核验；21700B BIN SHA256 `4b42863ac27867c9ba7ced1a464ca52ac069b9e2e095c2982d6cb382d07f1c5b`，代码/RO21616、data84、bss93128B，48KiB应用链接限制。固定2020-01-01测试纪元加本地tick，每10秒提供TIME；不是校准UTC、没有云端通路，只在RAM诊断标注TEST_TIME。首次仅B段NMT/TIME发送，A段协议发送关闭，共享CAN1时钟仍开启；180秒停窗且不复位。16条聚合记录环有覆盖计数，不是完整原始帧采集。外部ESP自身供电后状态未实测，未来还需核对隔离。

新增 `b4_recovery.py` 仅处理离线文件：一致双备份/身份/保护核验、候选SHA/向量/48KiB边界、受影响扇区安装及回退包、整片和options一致性核验。保留新BIN之后的原尾部及配置；真实包限制受限EFS，合成夹具限制build，输出不覆盖。工具**没有硬件连接/读取/烧录入口**，不能将文件一致性宣称实板独立双读或恢复演练。19项合成NOR单元测试与12项CLI正负例通过，包含跨32KiB、配置损坏、部分编程失败后回退、错身份/RDP/WRP、损坏包/清单SHA拒绝；未修改旧固定32KiB下载工具。

Host台架测试、本地TIME/回绕/有界RAM/停窗、ARM禁联网构建全部通过；`--bench --network-link`以真实退出2拒绝互斥参数。旧完整C网络目标构建回归BIN SHA仍为b5cd31c9…；两种目标都未运行或烧录。日志、实际退出码、源码SHA及加密归档入口见[本轮阶段结果](../evidence/B4-001/bench-r1/stage-results.json)。B算法源与冻结固件文件逐项SHA未变，当前25488B部署/原完整Flash不变；旧25284B没有恢复候选资格。仅软件准备完成，C真实备份/布局/现场电气和HR/RR共同稳态门禁仍未完成。

## MPM-B4-0.3 最终准入准备（本轮新增，软件/离线）

**ECG单位不一致已修复。** 最近留存实板RREG初始化缓存为7301e0f04040ec00ffea030c，CH2SET=0x40，与冻结ads1292.c及TI手册第56页对应gain4；不是本轮新读取寄存器。BIO显示量约为滤波ADC码×10^6/2^23，旧B4按gain6乘242/600存在单位偏差。TI第29页LSB=Vref/(2^23−1)，新B4除增益4外还补偿UI分母差：int64(display)×126877696/209715175得到整数µV，PDO单位不变，网关除1000输出mV；未改ADS寄存器、BIO源或阈值。换算在算法之后，不能据此把既有CH2/HR失败解释成单位错误或宣称已恢复。Vref=2.42V仍是名义参考，未经绝对校准。

2000001个显示量、65536个随机int32及24位输入、15个固定/边界点，连同真实B队列/PDO字节→mV JSON→既有Backend的100点序列均通过。显示量转µV最大误差0.999999399µV；合成24位码经现有float UI缩放链的最大观察误差1.592092465µV（不是仪器校准不确定度）。最坏100点JSON1493B/完整MQTT1534B<2048B，250点超容量负例拒绝；B4正常/量化时戳、5秒压力及CANopen策略回归保持通过。

修复后B ARMCC5为0错误0警告，Code36328/RO3144/RW1480/ZI18088；**新软件BIN39948B，SHA256 `676eb7a46ad9cd15c7bf93db51a1931d7711d37c6f2fd636197dc4a85b339b82`**。仍跨32KiB，安装评估sector0/1/2，新BIN末尾原尾部保留。旧39948B/gain6候选（SHA ea3e9412…）与中间39944B/gain4仅UI近似候选（SHA4312f7…）均退出部署候选，全部原件保留；新旧均可能39948B，不能仅按大小识别。C21700B/SHA4b4286…候选保持冻结未改。当前板上B仍25488B/b8e745…，本轮没有烧录。

**现场事实已补齐，不重复索要型号。** 负责人报告J-Link仍在B、C尚未接入/拟J5、USB未接，C P4无跳帽/跨接、无INMP441/TTS、全部CAN断开。[引脚电源表](B4-03-PIN-POWER-CHECKLIST.md)明确P4 1–2为CAN2_RX/PB12、3–4为TX/PB13，参考外部CAN2针2 H/针1 L、TJA1050/5V；当前空P4不构成已通路。参考地、实际端子/终端/供电与C网络隔离仍需授权现场核对，不把资料当实物电气验收。USB烧录偏好已记录，目前不授权USB下载/BOOT切换。

**两张独立卡已准备，尚未获批执行。** [C当次只读卡](AUTH-C-B4-03-READONLY-001-R1.md)对应新默认关闭工具：唯一连接、2×完整1MiB Flash＋2×16B options，正常运行时只读，reset/halt/go/target writes均0；拒绝探针仍在B、ROM/HALT/新复位/Fault/非闲置锁定Flash，原件仅EFS。sector3为0x0800C000–0x0800FFFF；sector7为0x08060000–0x0807FFFF；sector11为0x080E0000–0x080FFFFF，分别取SHA且不写。旧P文件把0x080E0000称sector7是历史编号混用，本轮按F407真实编号处理。历史H3应用/配置只做来源比较，不能替代今天原件；不匹配也留存，不自动刷回历史版本。15项C只读替身测试通过，包含错误授权/目标与保护状态，真实C读取仍0；备份成功也不等于恢复演练。

[B同步必要补证卡](AUTH-B-B4-03-SYNC-001-R1.md)依据本机手册第12页“普通ECG同步20bpm呼吸”的明确支持：同RA–LL–RL，普通ECG60/2mV、呼吸幅度1.5R/窒息0s/波形周期20bpm；先保持既有电气门禁，之后一次45秒预热＋90秒共同评价＋2秒尾段，硬限180秒、零reset/halt/go/写入。专用源profile不冒用旧E3，原槽使用当前25488B修正版地址0x20001F38（旧E3地址不适用），保存运行槽重复一致认证与非原子诊断。15项合成判据/门禁测试通过；保存观察100%同窗有效仍需原码/滤波/周期复核才签最终同步PASS。CAN传输始终独立裁定。本轮不登记SOURCE_SIMULTANEOUS_CAPABILITY_BLOCKED，也不宣称同步工程已通过。

**G4可执行卡暂不签发。** [准入矩阵](B4-HARDWARE-ADMISSION-REVIEW.md)只保留DISABLED草案，明确还缺C当次备份/H3恢复身份、实物电气、新候选实际下载/回退工具及批准、两板同时取证路径和完整原始CAN采集安排。现只有一只J-Link，C的16条聚合RAM环不等于完整CAN日志；采集路径未冻结前不能以双屏或Host回放替代真实CAN验收。未来必须包含NMT/HB/PDO、250SPS连续性、质量语义、TEC/REC/BOFF、故障恢复与实板回退，不把备份当演练。本轮只提交C只读与B补证卡等待PI逐项批准，不接CAN、不测阻、不烧录、不写云、不运行Security Gate。

源码/新BIN、实际Host/ARM退出码、默认关闭计划、卡SHA及受限归档见[本轮阶段证据](../evidence/B4-003/stage-results.json)。CPU_ROM_ROOT_CAUSE_UNRESOLVED继续待复现；冷启动和屏复位既有结论保持，不自动关闭残余风险。

## 准入与停止点

[B+C准入审查R3](B4-HARDWARE-ADMISSION-REVIEW.md)已按负责人要求一次列清同源双通道有效性、实际CAN2/收发器/跳帽/接地与I²S2冲突，以及B/C候选和恢复边界。本地TIME禁联网目标与离线安装/回退工具已完成软件准备；B4跨旧32KiB范围已覆盖合成验证，但仍缺C实板备份、实际布局及受审读回/执行入口。仅资料准备，disabled=true，无现场动作；ROM按负责人决定待复现处理，未冒称根因关闭。

软件阶段没有硬件动作；随后追加授权仅完成上述一次B独立断电启动及前后只读核验。没有接B+C CAN、没有烧录B/C，没有改变电极/源模式，没有修改算法阈值、正式腾讯云或执行Security Gate。**本轮软件修复与两张必要现场卡准备完成，当前修正版单次独立冷启动通过；G4实物CAN准入仍BLOCKED，等待PI先审核C只读/B补证卡。**


## C COM15读取及同型板CAN2复核（2026-10-23追加）

负责人确认A/B/C均同型开发板；C现接COM15，ESP8266仍在板上，INMP441/TTS及所有CAN均未连接，J-Link仍在B。操作系统识别COM15为USB-SERIAL CH340（VID1A86/PID7523）；这只证明串口桥存在，不能替代STM32 UID/型号或固件身份。一次info请求未返回MCP预期JSON，ok=false。随后按负责人提供的E:/stm32/ai_serial_console检查本机实现，发现该目录就是当前MCP来源，协议要求ai-console专用JSON固件；info中的chip字段还是编译期字符串，不是UID/芯片寄存器读回。没有刷入该控制台固件。

追加一次115200/8N1、5秒被动接收成功（实际5.047秒、退出0、526B、SHA256 `08de6ea9baacb2da66fb1511ba194cc4a1acc058347ad974cdd8bf4a0646a646`），发送字节0。收到7行文本而非JSON；完整原件存受限EFS，不公开未知业务文本。与冻结H3源码格式完全匹配的GW METRICS报告can=0、drop=186、cache=0、lost/replay=0、A/B均离线；GW CANPROOF报告hb/boot/p181/p381/p481/p681/nmt/time/txok均0、txfail=1、TEC=8、REC=0、LEC=3、BOFF=0。LEC=3按SPL定义为ACK错误，与未接CAN对端相容；日志值不等于新读CAN2寄存器，也不能反推缺线之外的唯一故障原因。C正在输出网关应用日志，但精确固件SHA/UID/Flash/启动PC未获得，C完整备份仍未完成。第一次MCP没有暴露原生进程退出码，记null；被动读取退出0只代表接收事务完成。

同时确认一个影响运行状态的工具边界：MCP用Serial(port=...)先打开端口，再设置DTR/RTS=False；不能仅由info命令名或readOnlyHint推断端口打开没有控制线跳变。flash.py --probe也会使用DTR/RTS控制复位及BOOT0，因此没有执行。追加被动客户端在port=None时先配置DTR/RTS=False再打开，不发下载同步字节、不清输入缓冲。没有NRST/BOOT瞬态或复位标志证据，不能据此认定本次实际复位，也不能把该潜在机制宣布为历史ROM根因；CPU_ROM_ROOT_CAUSE_UNRESOLVED保留。不修改外部控制台工具，不运行其烧录或扫描入口。

再次查看本地原理图第4/5/6页，并核对冻结双CAN驱动：B CAN1 PA11/PA12，经P6 CAN路径及U3；C CAN2 PB12/PB13 AF9，经P4的1–2（RX）及3–4（TX）与U2。参考U2/U3均TJA1050、5V供电，外部CAN座针2=H、针1=L、各自120Ω终端。CAN1与CAN2是各MCU内部控制器编号，不要求两端编号相同；两端同为500kbps即可按既有方案B CAN1↔C CAN2通信。C软件保持CAN1共享时钟、CAN2 filter start14及独立中断/队列，PB12/PB13不启用I²S2；无外接麦克风/TTS减少外部争用，但不能推断板载WM8978已物理隔离。COM15为CH340/USART1路径，与PA11/PA12的USB_SLAVE资源不同。

裁定为CAN2_DOCUMENT_AND_SOFTWARE_FEASIBLE_PHYSICAL_ADMISSION_PENDING，不签真实CAN收发PASS。C P4最近事实为空，尚未连通MCU与收发器；实际端子/供电/终端、参考地及P6路径仍需现场核对。ESP在板不等于已联网，也不等于已隔离；其现有网络状态未测，未发AT、改凭据或执行云端命令。C当次Flash/options备份、恢复及共同稳态有效性门禁继续保留。读取UID/启动状态/完整Flash应转用接C的J-Link；本轮不要求负责人现在转接，不复位、不改BOOT、不接CAN、不烧录、不改算法。详见[实际读取回执与CAN2复核](../evidence/B4-003/c-com15-can2-site-review.json)。


## C身份/完整备份PASS与接线准备（2026-10-23最新）

负责人把J-Link由B转C并明确授权按当前状态只读核验及完整备份。工具新增仅该授权可用的现状备份分支，明确ESP在板、USB最近为COM15且不再发串口命令，电源/BOOT/网络不操作；不把备份当作已隔离台架。底层SDK白名单、双读数量、故障停止及180秒上限不变；18项C替身和15项同步门禁测试通过（6阶段含缺授权退出1负例均按预期）。原只读卡与冻结工具索引保留历史，没有拿旧条件伪报本次现场。

**C_CURRENT_DOUBLE_FULL_READ_PASS，真实退出0，唯一连接79次SDK调用。** CPUID0x410FC241、IDCODE低12位0x413、容量1024KiB、RDP0，UID前后相同且排除B（UID原值只存EFS）。PC运行样本前后均在Flash，VTOR=0x08000000、CFSR/HFSR=0、Flash闲置且锁定；窗口无新复位/HALT/ROM证据。显式复位/暂停/续跑/目标写入均0，正常退出使用已修正的续跑策略。历史ROM根因依旧UNRESOLVED，不将C当前正常状态当B历史根因关闭。

2×1048576B Flash逐字节相同，SHA256 `1c7ea80359892a96a68503f9a0f054d16d860088f3831b0749b4eb7226549390`；2×16B options相同，SHA256 `52d5979da03bd7be45e385920ec7d5901793bab3f6bc1daa0c1c1997f9e91687`。sector3/7/11独立保存哈希，既有H3应用43172B及sector3配置336B分别匹配历史来源。原件、UID、options、SDK回执、执行源码快照及离线恢复包均保存本机受限EFS目录，本次公开资料只有状态、数值和SHA，不含固件/凭据。

C21700B冻结候选只读入离线工具，已根据当次双备份形成sector0/1安装与原件回退包，包SHA `7c45912d4eead456fc49f46df8c9439ff8b1a96bbe97c53bf4d192cbc467b298`；保持原尾部、sector2/3/7/11及options。离线包载入/重建核验通过不等于已经安装或恢复演练，C实际固件仍原H3，B仍25488B，两个B4候选均未部署。

接线继续**B CAN1↔C CAN2**：H↔H、L↔L、板GND↔板GND；B P6为1–3/2–4 CAN路径、C P4为1–2/3–4两组，C P4现为空，需要在以后获准断电窗口补齐。参考各板已有120Ω终端，不重复添加，不互并电源，不碰RLD或短LL/RL，A段断开。控制器号无需两端一致；若改成B CAN2↔C CAN2，需要另改B驱动并重新验证，不属于当前候选。准确接线与未就绪条件见[检查表](B4-03-PIN-POWER-CHECKLIST.md)。

G3身份与备份子项关闭；实际恢复、网络隔离、电气通路及双板连续取证仍待完成，G4维持DISABLED，CAN真实收发NOT_TESTED、双通道同步NOT_VALIDATED。没有接CAN、烧录、改算法阈值、操作云端或运行Security Gate。[C实际备份和工具/原件SHA回执](../evidence/B4-003/C-current-readback/receipt.json)提供复核入口。
