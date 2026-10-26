# MPM-B5-001｜Node-B经Gateway-C上云准备唯一交接

日期：2026-10-26。**B5-0至B5-2软件/离线预检通过，真实烧录、配置/ACL改动和上云测试未授权、未执行。** 独立工作区 `E:/medical-monitor-node-b5-cloud`，分支 `codex/node-b5-cloud-integration-20261026`；B39948B、C24104B部署及历史原件保持不变。ESP8266已装C为负责人新事实，本轮不查询设备、不启动串口/调试器、不确认其当前联网状态。

实现源码提交：`c65fbedce7edf5d822c573ef5cdeb6471d1ae3d5`。后续仅交接/元数据提交不改变该源码、构建输入或候选BIN。

## 基线与源码边界

- B4远端核验 `codex/node-b4-dualbus-software-20261023@ffa440b31b8b4993967f0e9aef1b3071a0d1dcfe`。
- H3标签 `h3-ac-mock-eng-20261021-r1`（annotated object `8a9265146a293f8a020df39863943e9de4adce68`）确指向 `a5cdd5b0b1ad48108fd631136e9de69e30582f2d`。
- 从B4建立新分支，按[H3逐文件引入清单](../../gateway/b5/h3-selective-import.json)复用MQTT/TLS、毫秒SNTP、只读持久配置校验、Backend会话失效及七页UI/只读事实层；没有整体合并B4/H3或修改保护分支。原始SHA与本轮改动后源码SHA分别保留。
- Node-B的BIO源、阈值、ADS寄存器与固件不改。B4固定gain4、名义Vref2.42V的单位换算保留；未作绝对电压/阻抗标定，不能用菜单R或ADC codes声明Ω。

## B5-0：冻结原件复核

已重新核对受限EFS中的实际Flash、双备份、完整安装/恢复读回和最新CAN原始文件SHA，见[冻结审计](../evidence/B5-0/frozen-evidence-audit.json)。C实时旧版备份双读一致，历史四阶段“原H3→24104→原H3→24104”均真实退出0、完整Flash一致、options/应用外不变；本轮只读这些文件，没有为了软件准备再烧录。

| 冻结部署/原件 | 身份 |
|---|---|
| B39948B BIN | `676eb7a46ad9cd15c7bf93db51a1931d7711d37c6f2fd636197dc4a85b339b82` |
| C24104B BIN | `127ba765b8144e8f8ae98ef826ac2a98f45f8facb4021ce1888c004e5ca46547` |
| C24104B完整Flash | `b460d917e1d454fdb0882d1f837d91c606363179b817a3896a1df6897b2dcb98` |
| 原H3完整恢复原件 | `1c7ea80359892a96a68503f9a0f054d16d860088f3831b0749b4eb7226549390` |

最新ECG60：B110/110次观察有效、C90/90次HR60与225/225次ECG模型有效、22493个源tick匹配，评价心跳180/180ACK；独立RR15：B110/110、C90/90次RR15有效、4499个源tick匹配。两窗CRC、缺号、C发送失败、TEC/REC均0，NMT/TIME真实ACK保留，质量分别5/10。B队列全采集expired分别559/564，而共同稳态保存快照跨度增量均0；全窗计数不能误写为0，也不等同于全程ADC丢点。起始未授时/排队边缘与稳态分开，过去失败与206025帧/681次RR观察原件不覆盖。

当前冻结sector3为有效H3 CRC记录，但[B5身份不匹配](../evidence/B5-0/frozen-config-identity-gate.json)。因此候选不能使用旧配置直接联网；没有把历史H3配置或备份当今天新实读。

## B5-1：实际CAN→模型→本地TLS Broker/Backend/WSS

[逐点单位/时间核对](../evidence/B5-1/actual-CAN-frame-value-time.json)直接输入B4原生CAN回执，由真实CANopenNode、双总线Gateway、Router、`mp_json`输出，未重造算法波形。ECG250SPS每100点、RESP50SPS每50点；逐批与原PDO固定点值和末点UTC核对，无补点。ECG输出mV、HR bpm、RR breaths/min、RESP相对量；TEMP INVALID/null。波形按末点UTC和名义采样率还原，CAN逐点毫秒量化仍留原件，不声称JSON携带了每点独立时戳。

模拟器实测原CAN质量位未置synthetic。B5在网关出口强制MOCK/synthetic，保留原始帧、有效位和采集时间，不能把非人体SKX数据当LIVE。QoS1历史仍为REPLAY且保留synthetic，旧帧不改时间冒充新采集。

[本地真实TLS链路](../evidence/B5-1/local-Broker-Backend-WSS.json)：独立Mosquitto2.0.21、临时loopback TLS监听、合成账户/CA、专属ACL、实际Backend和真实WSS。ECG输入1228条C模型消息，RR1224条；Backend两案分别接受1271/1267条（含状态和反例），解析拒绝0。数据经Broker和实际MqttAdapter/Telemetry/Hub到WSS，分别验证HR60有效/RR无效、RR15有效/HR无效、TEMP无效和Node-A OFFLINE。

两份历史记录保留原2020本地测试UTC，各案在注入的受控Backend时钟与独立Hub中运行，不将它们拼成一次真实实时测量。验证重复消息、6秒STALE、REPLAY不覆盖当前值、节点新会话清旧读数、OFFLINE清空；本地Broker踢掉测试订阅者后，实际Backend自动重连并重新SUBACK。测试Gateway向正式Gateway主题的本地发布被ACL阻断；PUBACK本身不当作订阅端接受证据。最终复跑另在独占EFS目录逐条保存Broker原载荷与WSS原JSON，并将原件SHA写入回执。早期软件夹具保留了失败日志和当前派生快照别名，未记录每条中间WSS载荷；不把那些别名当不可变原件。正式云窗必须采用独占原件记录。未接正式Broker、未用正式凭据、未开放8884。

[七页浏览器](../evidence/B5-1/seven-page-browser.json)使用agent-browser独立会话，实际Backend/WSS发送上述已验收快照：overview/temp/ecg/spo2/resp/nibp/ai均可访问，显示MOCK、正确60/15及无效“--”。七页共用ViewModel/Store另直接消费两份真实WSS快照，STALE后数值与波形缓存不可作为有效值。浏览器是历史终点快照显示验证，曲线会离开走纸视窗，不冒充连续实时滚动验收。

H3豆包事实模块直接验证INVALID、STALE、OFFLINE和REPLAY没有可引用当前值，回答明确“模拟数据，非真人测量”。没有调用豆包/其他模型、没有TTS或语音下发；AI页服务调用与正式AI部署状态不在本轮结论内。新UI仅增加公开Gateway ID预选 `?gateway=GW-B5-001`，监护令牌仍仅在内存和WSS首帧中，Backend白名单仍最终裁定身份。

## B5-2：唯一C网络送审候选

[候选清单](../deployment/b5-candidate.json)、[ARM输入/构建回执](../evidence/B5-2/ARM-receipt.json)、[Host回执](../evidence/B5-2/Host-receipt.json)与[验证汇总](../evidence/B5-2/validation-summary.json)绑定实际编译文件/header/命令、输出和真实退出码。

[变更源码逐文件清单](../evidence/B5-2/source-freeze.json)覆盖63个本轮工作区代码/样式/链接脚本字节快照，清单SHA256为 `fe403f8ff2c484370e02949cd370a08e869173d66b10b5f6ddbb1491f57f1d38`。提交前仅将5个改动C/测试源的CRLF统一为LF，重新执行Host与ARM，BIN/ELF SHA均保持不变；该字节口径与Git取回比对一致，未顺手格式化未改文件。

| 产物 | 冻结值 |
|---|---|
| B5_CLOUD_MOCK_GATEWAY.bin | **42552B**；SHA256 `d5b9624b3da1129b4e045d3b2f669c00d2d93cb7379b15293ff143fe9f130683` |
| ELF SHA256 | `3c726f61f76eadac4909826203ca84dee65521aec448ad477ddca0c3c58795d8` |
| 布局 | sector0/1/2、应用≤48KiB；链接ASSERT禁止越过0x0800C000 |
| ARM资源 | text42456B/data88B/bss104448B；128KiB区余26536B（含既有堆栈预留口径，非实测栈高水位） |
| 恢复布局包manifest | `ba21721a0e7d8654c29b7be2b848c4eacc7b9e9da6ccc0adefb1deb61f789c5a`；[离线布局记录](../evidence/B5-2/offline-layout-plan.json) |

这是唯一正式送审候选，**hardware_execution_enabled=false**。当前实际B/C部署仍为39948/24104B。早期网络链接/中间BIN均非部署候选，失败日志和中间包在受限EFS保留。

候选采用当前B4 NART=0仲裁重传处理与有界STOP取消邮箱，不能退回早期单次发送丢心跳版本。首轮C CAN1静默、A过滤器/发送禁用，只启用C CAN2对B，Node-ID仍A1/B2/C3；CAN1共享时钟和过滤器分界14保留。实际ELF的CAN1_RX0、CAN2_RX0和USART3强向量逐项核验；SDK CAN2_RX0 IRQ64对应向量80。CAN2 PB12/PB13与默认I²S2冲突构建负例真实退出1，麦克风/TTS均未链接；不预先改A/C其他固件。

H3 coreMQTT/TLS、CA/名称/SNI、鲜活SNTP nonce/RTT/epoch与毫秒时间、sector3提交/CRC机制复用。专用身份为GW-B5-001、Client ID b5-c-isolated、角色b5-gateway；遗嘱与遥测使用同一编译期命名空间，旧H3配置身份不匹配就拒绝。没有配置/Flash写入符号，没有回退读sector7/11。未武装不推进CANopen/TIME、不自动联网，固定完整B5START才武装；超长命令整行拒绝。

最多420秒，总预算为60秒连接准备＋45秒预热＋300秒共同评价＋15秒尾段；故障或到时停止CAN发送、禁止新网络业务/重武装，允许≤2秒CIPCLOSE清理。诊断固定输出CAN ACK/发送失败、ESR、RX/UART溢出、队列和MQTT计数；q0_transport仅表示发送完成，q1_puback才表示匹配Broker PUBACK，两者都不是Backend/Web接受证明。

100点最坏整数ECG JSON1492B、实际coreMQTT包1534B，小于2048B；不截断。实时16槽/历史64槽，过期遥测转REPLAY、旧状态丢弃，重连先新实时后历史。1000帧离线队列负载保留64、如实丢弃936，不能承诺任意断网无损。真实coreMQTT错误/迟到/缺失PUBACK、QoS0短写、连接/保活、TLS失败和下行拒绝回归通过。Host以真实bxCAN ISR/主循环配合模拟ESP字节等待：5秒等待收1737帧、环高水位7、溢出0；饿死350ms负例检出15次溢出。该结果不代替ESP实物AT延迟、ARM耗时或B ADC在真实联网负载下的连续性验收。

## 验证回执与复跑

| 检查 | 结果/真实退出 |
|---|---|
| B5 Host | 18编译/运行阶段PASS，入口420秒/溢出停止、配置、SNTP、QoS、压力等；冲突编译负例1按预期保留 |
| B5 ARM | 0；完整网络候选、实际向量、Flash边界及禁止写入符号检查通过 |
| B4隔离台架回归 | 14阶段PASS；互斥CLI负例2，其他退出0 |
| Python | Backend34、原安装工具20、B5独立C012门禁4均通过 |
| Web | TypeScript/Vite构建0、状态/AI15项0、两份真实WSS状态检查0、浏览器七路0 |
| 本地TLS Broker/Backend/WSS与CAN数值时间 | 均0；实际正式云端、ESP联网和300秒真实云窗均NOT_RUN |

工作区已有本机GCC/ARM SDK、Node依赖与仅解包的Mosquitto运行库，未安装系统Broker服务。主要入口：

```text
python -X utf8 node-b/tools/b5_audit.py --b4-worktree E:/medical-monitor-node-b4-software --out <新受限EFS目录>
python -X utf8 node-b/tools/run_b5_host.py
python -X utf8 node-b/tools/b5_check_frames.py
python -X utf8 node-b/tools/run_b5_local.py
python -X utf8 gateway/dual_can/build_arm.py --b5
python -X utf8 node-b/tools/run_b4_bench.py
python -X utf8 -m unittest discover -s node-b/tests -p test_b5_install_scope.py -v
```

私有指针与原始CAN只在本机忽略目录引用；复跑需先建立新的EFS输出，不覆盖旧派生数据。软件准备中的编译/夹具失败全部保留：100点ABI下旧250点测试构造越界、旧身份断言、过早快照/序列选择、手工disconnect误作自动重连、错用CAN2_TX向量号的验证器、诊断声明缺失及初次WSL解包参数问题。修正的是工具/夹具/原型或检查器；不把中间失败改成0，不用它们推断实板ROM或传感器故障。全部源、原码/派生快照、BIN/ELF、原生日志和逐文件SHA留受限EFS；Git仅源码、构建/聚合证据，不含Flash/options/UID/真实凭据。

## 准入门禁与下一轮边界

| 门禁 | 当前状态 |
|---|---|
| B5-0冻结审计；B5-1隔离模型/接收链；B5-2软件候选 | **PASS，仅软件/离线** |
| B4 ECG60与独立RR15的测量及B→C传输 | **各自PASS，原件保留** |
| SCREEN_RESET_MCU_RESET_FIX_PASS | 历史通过保留，B固件未改 |
| CPU_ROM_ROOT_CAUSE_UNRESOLVED | **UNRESOLVED**，不主动重试或用烧录掩盖 |
| INDEPENDENT_COLD_BOOT_NOT_VALIDATED | **NOT_VALIDATED**，历史观察/计数差异保留 |
| 同源同窗ECG/RESP同时有效 | **NOT_VALIDATED**，不合并两种源模式 |
| 绝对阻抗幅度标定 | **IMPEDANCE_AMPLITUDE_NOT_CALIBRATED_INSTRUMENT_REQUIRED** |
| 受控CAN故障注入恢复 | **NOT_TESTED**；Host溢出负例和MQTT重连不是实物CAN故障恢复 |
| 新C候选实际安装/恢复、冷启动、ESP负载 | **NOT_RUN**，C24104B旧演练不能替代B5三sector实测 |
| 云身份/ACL/测试Backend路由、sector3专用配置 | **PENDING_PI**，未创建、未改正式环境 |
| B→C→真实8883→Backend→WSS≥300秒 | **NOT_AUTHORIZED / NOT_RUN** |

[真实上云现场计划R1](AUTH-B5-CLOUD-ISOLATED-001-R1.md)准确列明新鲜C全片/options、独立C012安装scope、sector3另批、ESP隔离、420秒预算、分层接受证据、停止和原H3恢复。当前全部禁用，不向负责人重复索要已有资料；待PI决定实际测试身份/配置、隔离入口和动作授权后再准备新鲜绑定。

B5真实云工程窗通过后才起草A+B+C并发合同：A CAN1↔C CAN1、B CAN1↔C CAN2，两段500kbps/各两端120Ω，物理H/L不并联，业务ID1/2/3保留；另审CAN1重新启用、双段公平性、NMT/TIME、Node-A恢复、RAM/AT压力和音频资源。不能提前合并P4、删除历史分支或自动进入三板。当前所有临时Broker、Backend、浏览器均已关闭；无硬件、云端、Security Gate或保护分支操作。提交推送后停止，等待PI审批。
