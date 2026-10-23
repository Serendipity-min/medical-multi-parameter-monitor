# Node-B 当前阶段唯一交接报告｜B4-0.1

2026-10-23，MPM-B-PREC-001状态冻结及MPM-B4-001软件集成准备；随后按负责人追加授权完成一次独立冷启动及前后只读核验。**软件构建与离线验证通过；当前25488B修正版一次独立冷启动通过；真实B+C CAN准入仍BLOCKED。** 本报告是唯一阶段交接入口，不把软件测试写成实物验收，不自动进入联动。

实验分支 `codex/node-b4-dualbus-software-20261023`，独立工作区 `E:/medical-monitor-node-b4-software`。开工时远端B基线已核验为 `codex/node-b-precan-closeout-20261023@9988d37cd5470d6857bb535aab1d821cf2581302`；H3参考固定为 `a5cdd5b0b1ad48108fd631136e9de69e30582f2d`。仅此新分支提交推送；B/B2/H3/P4/main/P6/语音/历史实测分支与标签不修改，无PR、合并或Security Gate。

## 冻结后的三个状态分别签署

| 门禁 | 正式状态 | 证据边界 |
|---|---|---|
| 屏重启引发MCU复位修复 | **SCREEN_RESET_MCU_RESET_FIX_PASS** | 最新25488B实板修正版，屏白色供电/串口插头重启后恢复波形；221次观察中MCU运行时间和BIO计数持续推进，屏07上电报告只恢复UI，不再调用MCU复位 |
| 历史CPU进入ROM根因 | **CPU_ROM_ROOT_CAUSE_UNRESOLVED** | PC=0x1FFF32F0、VTOR=0x1FFF0000是真实历史观察，Flash完整；ROM中等待USART3接收得到支持，进入机制没有确定，不能写成算法丢失或已修复 |
| 独立冷启动 | **INDEPENDENT_COLD_BOOT_SINGLE_TRIAL_PASS** | 本次拔下B端JTAG及J5，负责人确认板/模块/两屏全部熄灭、等待10秒，再仅接J5；JTAG断开时波形恢复并持续刷新。接回后MCU运行时间由4871002ms降为34023ms，BIO计数由1216965降为8164并继续推进；Flash运行、无Fault。仅当前25488B的一次功能验证，不代表重复启动可靠性或B4新候选验收 |

J-Link退出时遗留Flash HALT导致画面冻结，与历史进入ROM是两个问题；退出续跑已修正并观察恢复。BOOT0约1.0mV、BOOT1约0.9mV只是200mV直流档的静态读数，不代表复位锁存。NRST未测。无新证据支持将ROM归因于BOOT跳帽、电源、USB或屏复位中的任何单一因素。负责人决定ROM根因保留未解决，待再次出现时排查；本次冷启动不关闭该问题。

[本次冷启动前后回执摘要](../evidence/B4-001/independent-coldboot-20261023.json)保留真实退出码、工具SHA、加密原件逐文件SHA及负责人观察。后核验运行时间34023→37174ms、BIO计数8164→8951；VTOR=0x08000000，运行PC采样均在Flash，CFSR/HFSR=0，ADC初始化/SPI/队列溢出/长间隔错误均0。RCC_CSR由0x1e000000变为0x0e000000，含BOR/PAD/POR、软件复位标志清除，佐证重新启动；不是BOOT锁存或电源波形测量。两次软件会话各连接/关闭一次，显式reset/halt/go及Flash写入均0，正常关闭续跑。负责人未给出独立观察的精确秒数，回读在启动34–37秒，不能宣称已测满原拟45秒。启动快照HR/RR均暂未有效，不作为双通道评价。先前开关对照未重启的反证保留在原冻结回执，不覆盖。

## 当前部署与恢复原件

当前已验收修正版源码基线是 `9988d37`，**部署冻结对象是25488B，BIN SHA256 `b8e74577dae7a5a1f6caa27687193f5128f89bd70781f06a1d80b0c74d409b44`**。旧25284B仅留作历史证据，永久退出新硬件部署候选身份。

- 最新修正版完整Flash：1048576B，SHA256 `d2ea7cbf7081b20f82a4a6ca6dde4918b9c4d4b194a3c6c358c2d74012993316`，前25488B与修正版BIN逐字节相同。
- options原件：16B，SHA256 `52d5979da03bd7be45e385920ec7d5901793bab3f6bc1daa0c1c1997f9e91687`。软件阶段未访问设备；追加冷启动前后只读核验已确认当前BIN及options一致，没有写入。
- BIO_V2源 SHA256 `3adca55cb1eb1fa3ed8e4148f837287d0454bcc2c08ae77a8f73deb1dac156a7`；全部冻结固件文件逐个核验，算法和阈值不变。
- 历史f713…整片、失败原件、旧工具SHA、ECG/RR实测数据和历史标签全部保留。

[部署入口](../deployment/current.json)区分当前25488B、整片恢复与B4仅软件候选；`hardware_deployment_authorized=false`。[冻结清单](../evidence/B4-001/deployment-freeze.json)包含完整源码文件SHA、AXF/符号/实板回执SHA。L1 BIN/AXF、L2完整Flash/options及本轮软件BIN/ELF/原始构建失败均在受限ACL、NTFS EFS加密目录；本轮又建立并逐字节校验了恢复副本。具体归档位置、加密核验和ZIP SHA见[阶段结果](../evidence/B4-001/stage-results.json)。Git不提交固件、设备身份、私有原码或私有配置。

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

- B ARMCC5：0错误、0警告；新BIN仅软件候选，身份/大小/SHA见[最终B构建](../evidence/B4-001/final-node_arm.json)。当前实板仍是25488B修正版。
- C ARM GCC：双CAN、数据模型、Router及完整H3 MQTT传输链接成功；未下载。[最终C构建](../evidence/B4-001/final-gateway_arm.json)保留真实命令/退出码、头文件与参考源SHA。
- B4实际生产适配器产生正常250SPS和含量化间隔的编码夹具，经双总线真实CANopenNode消费；验证五PDO、TIME过期、NMT、SDO只读、错段/坏DLC、重启清批、8ms缺点/重复点、温度无效、单路阻塞隔离与有界溢出。Host不是实物验收。
- 5秒MQTT发布暂停期间CAN持续服务，无丢弃并补传50条；超容量负例有明确丢弃计数，不声称无限断网无损。
- 真实C输出经既有Backend解码与Hub：976条、11种流，其中222个100点ECG批次，温度88条均INVALID；未修改云端源码或启动服务。
- 原B普通回归7组全部退出0，算法27/27、通道隔离28/28；屏复位Host2项通过。旧CANopen协议12项、流水线11项、重启/分配回收17项通过。
- I²S2冲突及混用模型ABI均以真实编译退出1拒绝，这是预期负例；其它正式软件阶段退出0。原始失败轮次保留，不能只展示最后成功。

[最终Host回执](../evidence/B4-001/final-host.json)、[原B回归](../evidence/B4-001/final-baseline_regression.json)、[分级归档/失败历史/真实退出码](../evidence/B4-001/stage-results.json)提供复核入口。软件阶段新源码/工具/报告的冻结快照SHA见[源码索引](../evidence/B4-001/source-index.json)，此索引不覆盖随后冷启动报告更新；软件阶段Git交付见[交付回执](../evidence/B4-001/git-delivery.json)，追加冷启动提交另行推送及远端取回校验。

## 准入与停止点

[B+C准入缺口审查R2](B4-HARDWARE-ADMISSION-REVIEW.md)已按负责人要求一次列清同源双通道有效性、实际CAN2/收发器/跳帽/接地与I²S2冲突，以及B/C候选和恢复边界。新增核对指出B4超过旧32KiB工具范围，C完整网络目标不能直接用于隔离台架；需先准备本地TIME与禁联网目标、C实板备份及配置保留方案。仅资料准备，disabled=true，无现场动作；ROM按负责人决定待复现处理，未冒称根因关闭。

软件阶段没有硬件动作；随后追加授权仅完成上述一次B独立断电启动及前后只读核验。没有接B+C CAN、没有烧录B/C，没有改变电极/源模式，没有修改算法阈值、正式腾讯云或执行Security Gate。**软件准备完成，当前修正版单次独立冷启动通过；实物CAN准入仍BLOCKED，停止并等待PI审核新的现场合同。**
