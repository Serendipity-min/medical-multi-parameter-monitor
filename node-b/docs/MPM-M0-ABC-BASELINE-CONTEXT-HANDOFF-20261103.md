# MPM M0 三板底座｜上下文交接与复盘

日期：2026-11-03（Asia/Shanghai）。本文件用于新上下文直接接手，不要求重走历史审核。所有PASS只对应下列镜像、窗口和范围；失败、UNKNOWN和延期事项分别保留。

## 1. 先读这几项

1. 本文件。
2. `M0-ABC-BASELINE-20261103/FIVE-NODE-RESULTS.md`：本轮简洁实测结论。
3. 同目录 `RELEASE-MANIFEST.json`、`CURRENT-WINDOW-SUMMARY.json`、三份 `*-CURRENT-C-*-REVIEW.json`。
4. 需要排查某次失败时才读 `FIELD-WINDOW-INDEX.json` 及相应受限原件，不批量重放全部历史。
5. 实际仓库的 `AGENTS.md` 和用户当期指令。附件是阶段依据，不提供超出当前用户请求的自动操作权限。

用户已明确：先完成M0，五板架构下一步再做。不得因本文件出现D/E方案就启动迁移、接板、刷写、正式云变更或合并main。

## 2. 当前结论与Git定位

**M0三板开发底座已经完成所列三场真实300秒窗口：B41516+C ECG60、A42608+B41516+C ECG60、A42608+B41516+C RR18。三窗最终工程联评均退出0。**

- 实际代码仓库：`E:/medical-monitor-node-b5-cloud`。不要误在中文资料目录操作另一仓库。
- 工作分支：`codex/m0-abc-unified-baseline-20261103`。
- 开始基点：`c0b36430cb8262147b2249d18d889892d3c7b0fa`，来自已验收C-only统一运行阶段。
- 本轮交付标签：`baseline/abc-unified-pre-split-v1`。本交接与代码/结果同批提交；精确交付SHA用 `git rev-parse baseline/abc-unified-pre-split-v1^{commit}` 定位，最终回执另给完整SHA，避免在提交自身正文中伪造自引用SHA。
- 没有合并main、创建最终产品release、制作三板通用BIN或开发五板代码。
- 这是非人体、可回退的工程底座，不是临床精度、所有历史问题清零、连续语音或24小时稳定性验收。

本轮合同：中文资料目录 `doc/五板架构设计/FIVE-NODE-V1_五板架构迁移与基线合同.md`；SHA256为 `b4d8c6e5ef3c1d7f753725942fbc4700ec1e07d1a19518b6e60ad004414844a7`。用户仅要求先做M0；合同后续M1/M2不自动执行。

## 3. 最终物理状态——这是最后一次确认，不是未来的实时事实

负责人在最后RR18窗口STOP成功后确认“全部断电熄灭”：

| 项目 | 最后确认状态 |
|---|---|
| A/B/C、屏幕、传感器和MIC/TTS等模块 | 全部断电、熄灭 |
| C USB_UART电脑端 | 已拔；最近使用COM15，未来仍须实际枚举/确认 |
| J-Link电脑端USB | 已拔 |
| J-Link板端 | 留在B |
| 两段CAN | 保持连接，未再次隔离：A.CAN1↔C.CAN1，B.CAN1↔C.CAN2 |
| 导联 | R→RA、黄L→LL、F→RL；最后为RR配置 |
| SKX最后菜单 | 主RR18，独立“波形周期”30，幅度1.5R，窒息0 |
| SKX使用方式 | 测试时电池、充电USB断开、非人体；最终是否关机未单独确认 |
| 温度探头 | 最后对桌面；绝对温度未校准 |
| TTS与喇叭 | 模块与喇叭已分开放置，原电气接线不变 |
| 手机热点最终开关 | 可关闭，但未单独确认，记UNKNOWN |

新上下文不能把这张表当“现在一定断电”或下一次上电授权。需要实物操作时只询问必要的当期状态，不要求精确HH:mm:ss；不要带电转接J-Link板端、CAN或导联。

## 4. 现有接线与角色

A为已恢复的A42608：CANopen、HKB-08B+血压、血氧采集链和两屏。血氧模块精确型号UNKNOWN；资料在中文工程目录的“血氧”及A相关分支。非人体气路、压力限制和人工停泵泄压方式由负责人确认；泵只由负责人通过A屏手动启动，禁止云端自动充气。

B为B41516：ADS1292系列ECG/RESP、GY641物体温度、HR/RR屏和独立温度屏。

- ECG60：SKX普通ECG、60bpm、1mV，R→RA/L→LA/F→RL。
- RR18：主呼吸率18、另一个独立波形周期菜单30、1.5R、窒息0，R→RA/L→LL/F→RL。
- GY641：3V3/GND、RC→PC10、TD→PC11；沿用已验证UART4接口。独立温度屏为USART3 PB10/PB11。
- B41516已经实现温度屏随传感器刷新，替换旧固定36.5；本轮没有再改B固件。负责人本轮报30.2℃，与B+C窗29.91–30.29℃源范围一致；这不是人体体温标定。

C为STM32F407ZGT6网关。精确PCB版本丝印UNKNOWN，不把MCU型号等同PCB版本。

- MIC：VCC→3V3，GND→GND，L/R→GND，WS→PA4，SCK→PC10，SD→PC12；100nF陶瓷电容及100kΩ电阻由负责人核实。无SD卡，相关引脚未接其他设备。
- TW-TTS：原板上5V输出→V、GND→G、PA2→R、T→PA3；原喇叭SPK±，SPK−不接地。此前确认沿用TTL接口及无RS232/RS485冲突跳帽。本轮未重做电平测量。
- C USART3用于ESP，USART2用于TTS；不要占用现有CAN1/CAN2或这些串口。
- 两段独立500kbit/s CAN，H对H/L对L/参考地共地；每段两端120Ω，既有断电测量约60Ω。本轮沿用原线束/终端，没有把三板并在同一条总线上。
- 线长、支线长度、线材和收发器精确型号UNKNOWN，不推断距离能力。

## 5. 当前实装应用与恢复边界

A/B本轮没有刷写；当前C是本轮必要整改后的统一候选。不要把旧C44520或中间候选的PASS移到当前版本。

| 制品 | 大小/身份 | SHA256 |
|---|---|---|
| A42608.bin | 42608B，未修改 | `953c6acc23dcbfcd5a30f138b03f8a6de9430637b0da5477afb2f09b3f431eeb` |
| B41516.bin | 41516B，未修改 | `e452c2eafd07868c642c530c09c7ec31b07f919cb41886c849fe84b817644fcd` |
| B AXF | 同次实际符号制品 | `37274a57592e5a9e734efa27e2db4385fe41c47dc083e8827a556268813fa80b` |
| B symbols | 同次符号映射 | `8ab3e758488c4c65c12c63388964bfd98def66d3c4aeb6f59c3e5836c142ea7c` |
| C boot.bin | 392B，sector0 | `52ae0854a4418446a548c193e1465ba85f7fb59544b0ff486c0f443101c2d3f5` |
| C code.bin | 54500B，sector4 | `118bb51ad837b24db5b52ee3e2f658c714eaade608d2dd4c20d653637a801042` |
| C ELF | 当前候选 | `4e124697d927c1b6643483c0aed9b743c4f974951dfc131a627f0a88c812c5c8` |
| C HEX | 当前候选 | `dccbcf820fc018376435caeddafb62b84a57b19510d381f599124eee9144bb23` |
| C完整Flash读回 | 只在EFS保留原件 | `fb15578d20d11676a8128b26f5b7b1473464e349adfed45ad0a2a4e2c780f5c5` |

当前公开应用制品目录：`node-b/docs/M0-ABC-BASELINE-20261103/candidate-c-startup-order`。唯一选择由RELEASE-MANIFEST.json的`selected_C_candidate`确定；其他candidate目录是历史候选，不要按文件修改时间猜当前镜像。

批准且实际使用的C下载范围只有sector0 `0x08000000–0x08003FFF` 和sector4 `0x08010000–0x0801FFFF`。sector1–3、sector5–11及Options保持原字节；不整片擦除、不改保护位。每次必要修复使用既有完整备份、目标身份、当前镜像核对、分段安装和1MiB读回，成功后才执行已授权Reset/Go。SDK安装原生Reset/Go与现场采集“不手工RESET”不是同一动作，日志分别记录。

当前构建：`node-b/build/b4-c-arm-20261103T130525139282Z`。只读默认C44520的BIN/ELF仍分别为 `5f4690eca0a00334ff1a9b653be2a0b99cba034b869ae4592dd36a042a147442` / `5b198faeaa87bffe5e026a067c19e23db20d1cfb8612a951087551bc4ed18599`，本轮默认构建逐字节一致。

## 6. 三个当前C窗口及真实退出码

所有场次先共同在线、45秒预热，再固定300秒评价；保留250Hz/50Hz原始帧、序号及IRQ时间戳，没有插值补足点数。

| 窗口 | 实板数据核对 | TEMP | 血压与语音 | 最终退出 |
|---|---|---|---|---|
| BC-ECG60-20261103T131035262559Z | ECG74757、RESP14962点，映射错误0 | 297条全部源匹配，WSS最大源龄3892ms | 125块、原始PCM逐字节一致，ASR/AI/TTS/负责人核对通过 | 采集0、B关闭0、STOP0、联评0 |
| ABC-ECG60-20261103T132147149024Z | ECG74615、RESP14879点，映射错误0 | 297条全部源匹配，最大4819ms | 最新101/64源完成tick/打包值/网页一致；90秒失效。语音通过 | 采集0、B关闭0、STOP0；原联评3，薄评测器修正后0 |
| ABC-RR18-20261103T133401161687Z | ECG74513、RESP14931点，映射错误0；RR18判据通过 | 298条全部源匹配，最大4636ms | 98/62源/网页一致及90秒失效，语音通过 | 采集0、B关闭0、STOP0、联评0 |

每窗Broker→Backend→WSS→真实网页有实收证据；Backend接收分别3139、3333、3321条，拒收/丢弃0。语音均真实MIC→125块/64000B→ASR→实际AI调用→MQTT回包→C TTS ACK/DONE→负责人可闻核对。没有Host发布测量数据、B5START、B/A烧录或在RR模式人为强制关闭HR。

ECG与RR分模式验证，不能拼成同窗双参数源真值；RR模式下HR仍按原算法有效性传输。当前RR18通过不证明RR15没有QRS，也不关闭历史RR异常。

## 7. 性能预算与必须保留的风险

C Flash总加载54892B，sector4余11036B；普通SRAM在8KiB栈、24KiB堆预留后另余15808B，CCM余1536B。实际三窗观测栈上界3524/3532/3564B，不是全路径最坏栈或堆使用证明。

| 指标 | B+C ECG60 | ABC ECG60 | ABC RR18 |
|---|---:|---:|---:|
| 音频首末块跨度 | 93.619s | 234.463s | 224.368s |
| C首次报告播放完成相对评价开始 | 147.735s | 293.093s | 283.734s |
| 实时队列最高水位 | 16 | 21 | 21 |
| 实时队列overflow增量 | 0 | 0 | 0 |
| expired增量 | 0 | 0 | 0 |
| A沿用最新值合并replaced增量 | 0 | 398 | 374 |
| 旧历史缓存覆盖增量 | 0 | 340 | 317 |
| C UART累计计数首末 | 0→0 | 0→0 | 0→0 |

**不要把Backend丢弃0、B主波形连续，改写成所有A/B流全历史零丢失。** A仍沿用最新值合并，真实满载下旧历史缓存被覆盖；A完整PPG历史连续性未由本轮证明。Host压力例没有覆盖掉这些真实负载现象。

当前音频装配240秒、C整轮300秒、M0 Host等待305秒，评价仍300秒；医疗新鲜度5秒、血压90秒不变。ABC ECG60只剩约6.9秒整轮余量。后续扩展五板/连续语音前必须正视吞吐和公平调度压力，不能继续只加超时来宣称性能解决，也不能放宽医疗时效或关闭原始波形。

## 8. 新M0评测器的血压修正——不是改旧正式结果

ABC ECG60一个窗口收到127/64和101/64两个固件上报完成代次，后者与负责人屏幕值一致。旧M0薄评测器要求每一代都在后续快照中显示过期；但网页模型只保留最新值，前一代被替代后本来就不会再次作为当前值出现。因此初次联评退出3，仅 `NIBP_NEW_SOURCE_OR_EXPIRY`。

处理：保存原评测源码及SHA、原退出3和原始WSS；只修改新增 `node-b/tools/m0_review.py` 的代次生命周期判断。被可信新代次在90秒内替代的旧值允许记SUPERSEDED，但不得再有效复活；最新代次仍必须按原90秒失效，重复包不延长寿命。负例覆盖过期仍有效、旧值复活、重复包与同值新代次。修正后ABC退出0，B+C使用同版复核也为0。

旧 `abc_two_group_review.py`、`b5_g3_review.py`、`b5_channel_review.py` 等冻结评测器及旧正式结果未修改。详见 `NIBP-LIFECYCLE-REVIEW-CORRECTION.json`。

负责人没有回答实际手动启动次数，所以保持UNKNOWN；两个固件完成代次不能被报告成两次物理测量，更不能据此声称模块绝对精度通过。

## 9. 实现究竟改了什么

- `gateway/b5/egress.h`、`gateway/mqtt/src/gateway_transport.*`：单coreMQTT连接内3遥测在途槽+1音频槽，各自packet-ID/ACK/5秒预算；音频每250ms至多竞争一次，并让医疗QoS1推进；保持医疗优先和有界缓冲。
- `gateway/dual_can/b4_gateway.c`：排队IRQ跨重新授时锚点时使用有符号时间差，避免无符号绕回造成伪质量切换，不改原始采样时间。
- `gateway/dual_can/b4_bxcan.*`、`gateway/b5/network_main.c`：明确NVIC分组、CAN优先级3、MIC DMA优先级8及真实寄存器/IRQ诊断；冻结武装前UART累计基线，新错误仍故障。
- `gateway/microphone/unified_audio.*`：保留2秒、16kHz、125块/64kB协议，有限整轮预算300秒。MIC格式/时钟/DMA采样主体继续复用原实现。
- `gateway/microphone/field.py`：真实回执交错解析、故障时仍尝试全局STOP、连接失同步/过早STOP及时失败；当前M0装配预算240秒，其他默认90秒保持。
- `cloud/backend/app/hub.py/main.py`：仅任务环境启用有界波形批推送，队列8；慢客户端明确1013关闭，不能静默覆盖波形批。原默认最新快照行为不变。
- `cloud/backend/app/mqtt_adapter.py`：隔离Backend允许仅loopback明文MQTT，默认TLS保留，非loopback禁止明文；健康标签如实区分loopback/TLS。
- `cloud/microphone/protocol.py/worker.py`：新合法起始块可替代中断会话，重复块不续期；有限装配参数90/180/240，默认90。
- `node-b/tools/m0_field.py/m0_review.py/m0_cloud.py`：薄编排/薄评测/本任务隔离服务，复用既有B原码、UART温度、Broker/WSS、网页工具，没有另造采集系统。
- `m0_stop_completion.py`：只处理一个旧窗口已完成300秒、语音已完成、已STOP但Host提前返回的严格边界；只I/Q/D补证，不新录音、不补跑，不改原退出1。
- B只读入口使用同次B41516符号，4MHz；默认旧工具1000kHz及旧期限不变。M0工程会话上界1200秒，避免人为精确上电时刻要求。

源码字节与实际编译/部署回执固定；部分CRLF差异会使普通Git diff行数偏大，可用 `git diff --ignore-space-at-eol` 看功能差异，不要为减少diff而在交付时改掉已执行源码字节。

最终提交核对：39个仓库内编译输入中33个与Git对象逐字节一致，另外6个未修改输入仅为既有LF/CRLF checkout转换，规范化内容完全相同；实际工作区SHA均与构建回执一致。改动的编译文件、选定头文件及Host工具字节一致，实际部署Backend/worker也一致。详见SOURCE-BYTE-PROOF.json。不要为这个既有换行转换扩改第三方代码。

## 10. 遇到的问题及后续复盘

| 问题 | 证据/处理 | 当前状态与复盘重点 |
|---|---|---|
| 只在队列全空/半满时发音频，造成饥饿 | 多轮真实87/112等未完成块数保留；ACK后机会和在途槽整改 | 当前三窗完成；真实ABC吞吐仍紧，不称彻底解决容量问题 |
| 旧装配90/180秒与真实上传不匹配 | 91.29s和192.90s原始到达回放反例；有限改240/300 | 期限调整有实证，但不能不断加超时替代调度分析 |
| 排队帧跨重新校时出现伪缺口 | 真实缺口79+100点及Host反例3→0，修有符号差 | 保持原IRQ时间戳、序号，禁止插值掩盖 |
| WSS最新快照丢短突发波形批 | 约27ms突发被100ms快照覆盖；任务队列/立即推送整改 | 仍需区分网页/观察器问题和MCU采样问题 |
| HTTPS健康探针误停 | 3秒探针超时但MQTT/WSS仍活；M0改首尾健康+持续流观察 | 不动其他旧工具默认；不要把主机探针问题直接判MCU坏 |
| 串口控制回执打断诊断行 | 真实 `replUNI RECORDING` / 下一行尾段 | 只对已知回执提取、逻辑拼接，原始字节和时间不改 |
| TTS初始化没ACK/早期AT本地中止 | 准备失败均未录音；TTS分开放置后有ACK，但因果未证实 | “磁场影响”只是现场猜测；AT约7ms本地中止不等于ESP回应超时 |
| 我新增启动日志引入过早STOP | console会调用服务回调，CAN尚未初始化；移到初始化及两段link设置之后，真实驱动反例3→0、ARM顺序核对 | 必须复盘：诊断本身可能改变时序；不要再为几条日志增加复杂状态机或盲目反复刷写 |
| UART历史累计错误基线一直为0 | 真实控制路径Host旧3/新0；武装时取累计基线，新错误仍故障，计数不清零 | 软件缺陷已修；早期现场AT中止是否由此造成，缺直接计数证据仍UNKNOWN |
| STOP工具遇phase8先报错，未发送X | 新定向负例先失败，修后仍发全局STOP且不冒称TTS静音 | 目标停止与主机失败分别记录；不能用Close成功代替现场静音证明 |
| B源ECG约8.7秒HR无效 | 115308窗真实ADC同算法回放复现；早期ECG正例仍全有效 | ROOT_CAUSE_UNRESOLVED；没改B算法、阈值或Lead-Off，不能只拟合失败窗 |
| RR18早期漂移/间歇无效 | 121015准备失败、122410部分窗66个无效RR观测等保留 | 当前一次严格300秒RR18通过不撤销早期失败，更不证明RR15源端是否有QRS |
| 两个NIBP代次造成假评测失败 | 原退出3、修正后0，见第8节 | 区分“替代”“90秒失效”“物理测量次数”；不要为补证反复启泵 |
| Host压力例通过但真实A历史仍覆盖 | 真实ABC覆盖340/317，live overflow0 | 必须保留；不能用Mock宣称原生性能/全历史完整性已解决 |
| J-Link切板后曾遇ROM | 一次安装前C_RO_ROM_STOP，无Flash写入、Close0，人工处理后下一独立事务成功 | 成因UNKNOWN；不自动Reset/Go、改保护位或因用户猜测就认定“正常短暂影响” |
| 语音录到噪声/错过说话 | 早期用户说完再回复、PC外放未实际发生；改手机先持续播放再回复后取得一致录音/ASR | 先核对刺激覆盖录音窗，别先重写驱动或让用户不断重说 |

更早的M1_PHASE_TIMEOUT等主机会话预算问题不是MCU故障证据；当前M0不要求用户每次精确报秒。仍必须核实实际冷启动、正确板端目标和危险接线。

## 11. 不能被本轮PASS关闭的事项

- RR15的SOURCE_UNKNOWN/ROOT_CAUSE_UNRESOLVED：SKX RESP模式是否实际携带QRS尚无独立源端参考实验结论。禁止推断CH2一定无QRS、按RR模式强制屏蔽HR、伪造Lead-Off或只凭失败窗改阈值。
- RR24/RR30历史失败、TEMP180末帧异常及早期源HR/RR无效负例。
- SDK Open/Close隐式副作用、ROM成因、独立冷启动的所有最坏硬件路径。
- 温度是物体温度，压力/温度/SpO2绝对精度、血氧模块型号、物理测量次数与固件代次关系。
- A完整PPG/全历史无损、长时间满载、五板扩展吞吐、连续语音及24h长测。
- 监护事实AI问答、成年人家庭测量教学规则冻结、最终部署映射和正式产品合并。

不能把“工程确认回复发声”写成AI已经基于当前血压/体温做出可靠医学判断。

## 12. 原始证据与私有入口

受限EFS总目录：
`E:/medical-monitor-node-b-precan-private/20261023/m0-abc-baseline-20261103T062523681450Z`

本机忽略的 `node-b/build/m0-current-pointer.json` 指向它；`m0-group-current-pointer.json` 指向最后RR18场。总目录 `CURRENT-STATE-private.json` 是本轮继续工作入口，不是未来实时物理证明。

重要指针：

- `BC-current-C-pass-pointer.json`。
- `ABC-current-C-ECG60-pass-pointer.json`。
- `ABC-current-C-RR18-pass-pointer.json`。
- `C-startup-order-install-pointer.json`：当前实装、构建、原备份及上一安装。
- `C-M0-startup-order-installed/probe`：下载前后完整Flash、Options、目标身份、SDK/下载器动作与读回。
- 原C44520完整备份引用为 `E:/medical-monitor-node-b-precan-private/20261023/final-system-20261102T114520309079Z/P0-C-current-readonly`，通过现有回执核对，不另建替代备份或读取私钥。

每窗目录中：`runtime-inputs-private.json`、`tool-source-sha256.json`、`C-installed-reference-private.json`、`owner-preparation-private.json`、`owner-confirmation-private.json`、`capture/B` 原ADC/CAN/UART/诊断、`capture/cloud-events-private.jsonl`、`field-capture-*` 原始C串口/PCM/WAV/MQTT块、云端语音回执、真实网页观察、各子进程退出码和M0联评。

ABC ECG60额外保留 `executed-original-m0-review.py`、`M0-review-original.json` 与 `M0-review-corrected.json`，不得覆盖原退出3。B+C也保留同版修正评测的复核结果。

定向证据目录包括 `ABC-RR18-slow-upload-offline`、`UART-prearm-counterexample-final-source`、`startup-order-counterexample`、`B41516-source-quality-offline-replay`。只读需要的那一项，别因上下文交接重新跑65+17项旧矩阵。

Git只放应用制品、源码、脱敏摘要和必要证据。完整Flash/UID/Options/原ADC/音频/热点口令/令牌/真实服务器地址仍在EFS。不要把真实值写进脚本、日志或版本库；优先既有SSH别名 `tencent-codex`，不读取私钥。

## 13. 云端与进程收尾

本轮只使用独立任务Broker/worker/ingress/Backend/TLS实例。5个单位都已stop，原生退出0，is-active查询返回4并显示inactive（瞬态单位卸载后的预期状态，不是停止失败）：

- `mpm-unified-c-mqtt-20261103`
- `mpm-unified-c-worker-m0-240-20261103`
- `mpm-unified-c-ingress-20261103`
- `mpm-m0-baseline-backend`
- `mpm-m0-baseline-tls`

实际部署的Backend三文件、worker/protocol SHA与当前源码一致；见 `OWN-CLOUD-CLEANUP.json`。正式服务、ACL未修改。不要在新上下文为了“恢复状态”自动启动服务或改生产云配置。

## 14. 如何恢复，以及哪些动作必须停目标

先读 `M0-ABC-BASELINE-20261103/RESTORE-ENTRY.md`。使用 `gateway/microphone/unified_install.py` 的plan-only入口与现有私有完整备份、身份核验、分段工具，不重写烧录系统，不把boot/code拼成单个连续BIN。

未知CPU状态、HALT/ROM、错误目标、Flash漂移、配置区或保护位风险、异常电压/接线、异常泵压时STOP_TARGET，保全原件并交现场处理；仍继续授权内安全的离线排查。不自动反复重刷、不强设PC/MSP/VTOR、不改保护位；下载失败或读回不一致不启动。

当前M0交付不授权新一轮实板测试、A/B固件变化、五板迁移、正式云变更或main合并。下一轮以用户新指令为准。

## 15. 高效执行，避免过度工程化

用户明确采用研发效率优先模式：没有新增PI数字签名、nonce、一次性执行卡或人为测试次数限制。不要把旧P1禁用申请当新阶段门禁，更不能假称PI独立签署。原B/C禁用申请无需为了M0改成AUTHORIZED。

- 在当前批准范围内，普通编译、脚本、通信、协议、临时环境问题自主定位，做必要最小修改和相关验证；不用每个小错误都停下来要批准。
- 问现场人员的是确实缺少的实物动作/状态：断电转线、正确J-Link目标、实际屏幕结果、异常停泵。已经明确授权的操作不重复申请；不要求人为精确报上电秒数。
- 先读现成指针/回执并复用工具，不重造采集、烧录、云端和评测全链路。不要重复历史R5三窗、已验收65+17项、完整M1多率矩阵或无关Security Gate。
- 优先复现实证故障再修复；测试调用真实实现，Mock只隔离物理端口。Host通过不得写成真实SDK副作用/真实容量已解决。
- 默认最小实现：入口一次校验，内部不重复判定；不滥用try/catch、不堆泛化抽象和假想防御。只写解释必要约束的中文注释。
- 失败回执、源SHA、原生返回、原始时间与前后版本必须留存；修复使用新事务/新结果文件，不覆盖旧失败来“通过”。
- 评测缺陷要明确版本和理由。本轮只修新M0适配器，旧冻结器/正式结论不动；不能通过更换判据掩盖真实源数据或时效失败。
- 现场日志要核对进程是否结束和文件新鲜度；不要拿停止后的旧tail宣称“还在采集”。停止/退出码、Broker实收、网页实收、负责人可闻证明各自核对。
- 安全扫描需要用户明确授权。普通开发不自动启动全量扫描、安装新依赖、生产服务变更或保护分支合并。
- 正常Git交付集中在阶段末完成。不要每修一个小错误就push，也不要为交接再做一轮全量审计。

## 16. 下一步留给新指令

用户说五板架构下一步再做。合同建议温度及屏B→D、血压及屏A→E，C保持两条CAN（A+E / B+D），拟议Node-ID D=4/E=5；这些都未实装、未写入任何板。

新阶段若批准，从本次真实通过的标签创建独立分支。先明确当前C的吞吐/历史缓存/语音余量，再做最小静态角色、协议归属及D/E移植；不要默认添加四套CANopen实例、动态注册平台或中继架构。传感器/屏迁移、统一镜像、正式合并和云端正式配置均等用户下一步指令。

本轮交接的核心是：**知道哪些真实通过、哪些只是Host通过、哪些失败仍在、当前实物全断电，以及下一步没有自动开始。**
