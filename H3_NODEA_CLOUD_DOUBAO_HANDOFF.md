# H3_NODEA_CLOUD_DOUBAO_HANDOFF

更新：2026-10-20。本轮 MQTT 中断归因及隔离恢复回归 **PASS**；整体 H3 仍 **PARTIAL，未正式发布**。下方历史交接保留原始失败与旧镜像状态，以本节的新镜像/测试结论为准。

## MQTT 中断：直接原因与证据边界

确认的直接原因是 **数据在到达 Broker 的 TCP 字节流之前延迟，超过原有5秒确认预算**，不是 Broker 已及时收到并发出 PUBACK、STM32 却漏处理。原路由器路径的自然复现 MID1430：Broker 对1429在 `07:05:06.359487Z` 即发送确认；C的FIN在 `07:05:11.595397Z` 到达时，服务器ACK仍停在384277，而FIN序号384493，缺216字节。缺失段384277–384493到 `07:05:12.480265Z` 才出现，比FIN晚0.884868秒；Broker随即于 `12.480400Z` 接收1430、`12.480474Z` 发PUBACK。TCP捕获内核丢包0。原始头部元数据和限定窗口分别在 `baseline-tcp-corrected.json`、`failure-tcp-window.json`，不保存地址、源端口或载荷。

同一旧镜像 `b1de90885d2e3dd7833bdccf314f085d91de57c334b2bb37b4b118b9f11feaa5`，仅切换RAM Wi-Fi配置后，手机热点从首个确认报告起连续933.183秒、1956次PUBACK无发布失败；另有320.056秒真实WSS观察，A全程ONLINE、B全程OFFLINE，无效值泄露0。电脑热点对照约302秒/432次QoS1确认、最大2937ms，无失败；服务器强制127.0.0.1回环且保留真实证书名称校验，300秒/630次确认、最大30.92ms，无失败。热点TCP仍有重复段，不能称为“无丢包网络”。

这些结果支持原网络路径/射频条件造成超时，不足以唯一判定路由器硬件、无线干扰、WAN或ESP8266协议栈中的具体一项；PC启动快照信道11，C热点诊断信道1，不能声称严格同一BSSID/信道的控制实验。也不把现有证据推演为“STM32所有代码均无问题”。首次 MID218 的证据仅是确认缺失，详证来自本轮 MID1430。原路径长时间失联最终Router lost=673、旧CAN待发项丢弃270，均保留，没有清零掩盖。

## 已修复的固件问题与资源

1. `console()`等待UART TXE时会调用CAN协作服务，周期诊断可重入同一串口行，实际发生 `MQTT_ERROR` 被 `DIAG_BEGIN` 插入。本轮增加输出深度保护，只延后诊断，不停止CAN服务、不推进被延后的诊断时点。真实生产函数Host夹具证明：旧行为返回3，修复返回0；实板注入故障后完整保留 ERROR/BUDGET/IO/PENDING，缺行/交错均0。
2. 新鲜SNTP原来只取模块第一个配置端点，端点不响应会拖长MQTT恢复。本轮按模块已有最多三个端点，在失败后的下次重连轮换，每轮仍只发一个请求；成功后保留该端点。本次板端先实际拒绝index0无回复，随后index1在140ms返回有效样本，故障后再次index1在173ms通过。不内置新地址，不接收旧nonce、未同步/KoD或超1秒RTT样本，不修改监护TTL、QoS/PUBACK/5000ms、CA/SNI或发送频率。模块自身TIME等待仍保留，本次启动曾出现TIME失败后自动获时；C正式冷启动/持久配置仍需后续专项验收。

补充低频ESP I/O计数、失败时发送/等待预算及SNTP拒绝原因；只记录计数/帧身份，不记录生理值或凭据。`SEND OK`只作ESP栈接受证据，不能当作Broker接收，依据[Espressif官方TCP/IP文档](https://docs.espressif.com/projects/esp-at/en/release-v2.3.0.0_esp8266/AT_Command_Set/TCP-IP_AT_Commands.html)。所有新增行为限H3联网候选宏；P4及原模拟/旧MQTT目标保留。

| 身份/资源 | 实际结果 |
|---|---|
| 工作区/分支 | `E:/medical-monitor-h3` / `dev/h3-nodea-cloud-ai-integration` |
| 修复代码SHA | `ec044cc3e1887f7fd7812d6fd60b06a49d92f5ae` |
| 日志保护/时间冻结SHA | `0c36d8a5185a9bfa5dfffc9486f2b05a64aa8310` / `a63175280939548a4929d102d12d2568c386af37` |
| C当前实板镜像 | 42728B，SHA256 `c3bc10c6bb01831fb7c1f7a44dabb5fc0295fa667045a5428856bd6991250b6f` |
| 写入范围 | `0x08000000–0x0800A6E7`，仅sector0–2；无整片擦除/选项字节写入 |
| ARM资源 | text42632/data88/bss123136；相对旧41612B镜像，文件+1116B、BSS+48B；RAM会话配置仍312B |
| 下载门禁 | C身份/旧应用/新镜像读回、sector7/11、选项字节均一致；RAM配置读回一致；退出0 |
| A | 未烧录，原两份完整备份保留；本轮探头/袖带未连接，无新生理准确性声明 |

最终代码、工具、交接及证据提交由包含本文件的Git提交确定；最终HEAD在推送回执/答复给出，避免伪造文件自引用SHA。当前实板镜像对应上述准确代码SHA，不能用较新的文档提交冒充重新构建的固件。

## 隔离环境回归与原始退出码

| 检查 | 真实结果 |
|---|---|
| Python Backend/AI/下载/恢复/日志与网络工具功能 | 最新135项，退出0；无新豆包调用 |
| 最终工具/日志定向检查 | 最新17项退出0；远端保护SHA核对及git diff检查均退出0 |
| MQTT Host | 旧目标42项退出0；IRQ新鲜授时最新46项退出0，含三端点失败轮换/恢复、边界解析、坏时间停止TLS、原PUBACK门禁 |
| CAN关键回归 | IRQ协议、逐帧顺序、对端断电恢复及Bus-off/未知错误/卡邮箱保护分别退出0 |
| ARM | 隔离、正常联网两个目标均退出0 |
| 新固件正常窗口 | UART 329.234秒，新增PUBACK 693、发布失败0；WSS 320.052秒/3175快照全部GW/A ONLINE、B OFFLINE，无效值泄露0，退出0 |
| 受控网络故障 | 唯一既有C隔离8884连接丢包6.002秒，3包/783B，规则已撤销，退出0；不触及8883或其他连接 |
| 板端超时证据 | MID790、QoS1，5016ms、ack0；发送59ms/等待4957ms；ESP phase3、SEND已确认但无PUBACK；故障日志完整 |
| 故障后恢复 | 同一次C启动、未复位；新鲜授时→TLS→MQTT→新PUBACK，累计1152，仅1次有意失败；缓存0、Router lost=0、replay=20；Broker未收到MID790，`07:59:39.327952Z`已确认MID791，距失败日志约6.992秒 |
| 接收/Host分层 | FOVR=0，SW=0，stale=0，UART=0，CAN fault=0，Host缺报告/缺行/交错0；Node-B仍OFFLINE |
| 云端故障窗口 | 150.008秒观察；ONLINE→STALE→OFFLINE→ONLINE，其中非ONLINE约2.925秒；开始/结束均实际ONLINE，B全程OFFLINE，无效值泄露0；退出0；快照计数不当作秒数 |
| 联合实板判定 | `hardware-assessment.json` 各项均通过，退出0；串口观察和下载进程均退出0 |

证据目录统一为 `gateway/physical_can/evidence/h3/mqtt-interruption-fix/`。新固件同一UART原件/结果为 `uart-20261020T075056Z*`；最终下载为 `c-download-20261020T074926Z.json`。此前42472B诊断候选虽完成读回且下载工具退出0，但未获得新鲜时间、PUBACK为0，**不计联网通过**。初次TCP解析失败、Host夹具链接失败、CRLF源码门禁失败、ROM同步失败及未提交文件门禁失败都保留，见 `prior-attempts.json` 和各原始回执，未覆写为PASS。未运行正式Security Gate、安全扫描或Sanitizer。

## 清理、版本与剩余边界

本轮只使用既有隔离Broker `runtime-37808287a557` 和Backend `runtime-2ffd1d372ace`；未启动隔离AI，新增真实调用/Token/费用均0，之前10请求/7496 Token记录保留。本轮实测结束后，专用network-probe角色已恢复原ACL/密码文件精确哈希，两个隔离服务已停止，两个出口的8884主机规则已撤销，注入规则残留0。电脑恢复原Wi-Fi由用户手动确认；Windows定位权限阻止自动切换/查询，未更改定位设置。临时Wi-Fi配置已删除并查证不存在。自动恢复失败退出1的记录保留，清理最终退出0。正式三服务PID、Nginx/配置哈希和Web index均核对未变。原云安全组8884宽来源条目仍由现场撤销/收敛，不声称已处理。

未修改A/P6/P4/main受保护分支，最终远端核对见 `protected-refs-final.json`；未强推、PR、正式发布或正式回滚。既有A真断电后C恢复修复保留，当前验证没有以强制PC/MSP/VTOR启动A。没有重新开展传感器采集、生产Broker操作、腾讯云变更或麦克风开发。

本轮确认网络传输超时，并修复日志重入与配置端点单点依赖，受控故障能自动恢复；没有宣称更换网络可保证永久无中断。整体H3后续仍待：原路由器/RF/WAN具体环节进一步定位、C持久配置与正常BOOT启动、NIBP有效输入/过期路径，以及正式发布窗口与公网数据范围确认。C仍为下载BOOT接线、RAM临时热点配置；关闭串口后的持续运行及C冷启动未另行验收。已停止本轮真机操作，提交推送后等待审核，不自动休眠电脑。

## 本轮开始前的交接记录（保留历史）


更新：2026-10-20。**A 真断电导致 C 永久锁止：修复并完成实板恢复验证；整体 H3 仍为 PARTIAL，未正式发布。** 下方“上轮交接原始记录”保留历史阻断及原始退出码，其中旧镜像、锁止与停止状态已由本节更新；不删除失败记录。

## 本次修复与代码身份

在 `dev/h3-nodea-cloud-ai-integration` / `E:/medical-monitor-h3` 继续用户授权的修复。固件源码提交 `ab5861c600a4a43b184ff1fe17d13ba9aa11bb96`；UART工具提交 `171c6e86a26a53b4c37e70003fe74318e07433b5`；包含本节及最终证据的提交为其后继，实际最终 HEAD 在 Git 回执提供，避免自引用 SHA。A、P6、P4、main 的远端固定 SHA 均未变，见 `gateway/physical_can/evidence/h3/power-cycle-fix/protected-refs-final.json`。

原联网驱动把无 ACK 与所有 CAN 故障一并永久锁止。现在仅完整联网 IRQ 目标采用 NART 单次发送；确认完整发送失败且 LEC=3 时，停止 TX、保留 RX，进入 PEER_WAIT。只有之后新收到的合法 A 心跳/Boot-up 才清等待，并先丢弃旧 TIME/NMT、定向发送 Node1 NMT START。真实 TXOK 才计成功。未知错误、100ms 卡邮箱、Bus-off 仍锁止，新增首次 ESR/TSR/时间/协议复位快照；不清累计计数、不延长数据有效期或 MQTT 预算。旧 `link_policy.h` 与 P4/bench 路径保留。[ST RM0090](https://www.st.com/resource/en/reference_manual/rm0090-stm32f407-advanced-armbased-32bit-mcus-stmicroelectronics.pdf) 为 NART/ACK 错误及 LEC 软件标记的依据。

修改范围：`peer_tx.h`、联网 `bxcan_network_irq.c`、IRQ 条件编译的共享 CAN 队列与物理 stack、独立 PEER/最终故障诊断、Host 硬件替身与真实驱动恢复测试、受限下载/RAM 恢复工具及脱敏 UART/WSS 观察。未修改或烧录 Node-A，未接人体或开展新的采集、豆包调用。

## 实板断电恢复结果

C 同一 UART 会话 `20261020T062235Z` 全程保持，A 的 J-Link 已拔下，由现场只切换 A/双屏独立供电；C 未复位。精确原件在 `gateway/physical_can/evidence/h3/power-cycle-fix/`。

| 项目 | 实测结果 |
|---|---|
| A 断电前 | Boot-up=1、NMT TXOK=1、TXOK=195，A ONLINE，B OFFLINE |
| A 断电后 | 一次 TERR/LEC3 ACK 错误，TEC=8；PEER_WAIT=1，no_ack=1；不再持续重发；未 Bus-off、未致命锁止 |
| A 恢复供电 | Boot-up=2、NMT TXOK=2、TXOK=564；peer_returns=1、wait=0，TEC=0；C 启动标记仍为1 |
| 新会话 | 云端 `can-1792477355-65538` → `can-1792477355-65540`，捕获 A OFFLINE 后重新 ONLINE；无输入读数保持 INVALID/STALE，不复活旧值 |
| 分层计数 | FOVR/SW/UART/Host 缺行及 Router lost 均0；有意丢弃旧 CAN 发送项158，独立累计并计入原 drop；不是隐藏为零丢失 |
| 恢复判定 | `hardware-assessment.json` 所有11项通过、退出0；RAM恢复/观察进程退出0 |
| 云端连续性 | 完整 WSS 观察退出**1**：一次 MQTT 发布失败后自动重连，网关127个快照非 ONLINE，随后恢复新会话；快照数不等于秒数。B非OFFLINE=0、无效值泄露=0。保留 `actual-wss-restart.json`，不称本轮云端零中断通过 |

本次实测证实 ACK 缺失恢复路径正常；上轮锁止未保存最终寄存器，因此不能倒推上轮一定未 Bus-off。当前只完成无输入的正常冷启动/恢复，不把 Host 合成测量当作新实板生理采集。

## 镜像、保护与测试退出码

C 当前镜像41612B，SHA256 `b1de90885d2e3dd7833bdccf314f085d91de57c334b2bb37b4b118b9f11feaa5`，应用范围 `0x08000000–0x0800A28B`，仅sector0–2。text41516/data88/bss123088，相对上轮40928B镜像增加684B、BSS增加48B；SRAM配置仍312B、预留512B。sector7/11及选项字节在下载前后、最终恢复时均核对未变，未整片擦除。A原两份完整备份保留仓库外，不再备份。

| 验证 | 原始结果 |
|---|---|
| 真实联网驱动 Host 恢复 | 20秒无对端、Boot-up、NMT真实TXOK、旧TIME清理、全新PDO；退出0 |
| 强故障保护 | Bus-off/未知发送错误/100ms卡邮箱分别仍致命锁止，首次快照不变；退出0 |
| IRQ协议/逐帧顺序/旧物理协议 | 各退出0 |
| CANopen/Router | Windows原运行器误执行既有ELF退出1，保留；WSL真实回归退出0 |
| P5兼容 | 原42项、新鲜授时44项均退出0 |
| Backend/AI/工具 | 联合122项退出0；最终下载/恢复/观察定向30项退出0 |
| ARM | 隔离、正常两个目标均退出0 |
| 首次Host夹具 | 故障注入被夹具TXOK覆盖，退出3，修正夹具后通过；原件保留 |
| 下载/主机异常 | 首次ROM握手退出1、未写Flash；第二次已完整烧录读回后，我误判进度中止了主机观察，整体回执1。之后多次ROM同步失败均未写Flash，原件保留；最终复用已证实的自动连接时序恢复RAM、观察退出0，无追加Flash写入 |

最终成功恢复回执 `c-resume-20261020T062156Z.json`，UART原件/结果 `uart-20261020T062235Z*`。完整保护区读取有阶段回执；UART写入有2秒上限，观察期间保持同一串口句柄。手动ROM支路未获本次实板成功验证，不将离线测试替代硬件证据。

## 运行服务、剩余事项与停止状态

仅临时重启隔离 Broker `runtime-37808287a557` 与 Backend `runtime-2ffd1d372ace`，没有启动隔离AI、没有新增模型调用，原10请求/7496 Token流水未改。实测结束已停止这两个活动隔离服务并撤销本轮8884主机临时规则；正式三服务PID、Web、Nginx和配置哈希核对未变，清理退出0，见 `isolation-cleanup.json`。首次清理检查静态文件路径错误退出1，发生在任何清理变更之前，纠正路径后完成。未发布新的 HTTPS 入口或执行正式回滚。

本次锁止问题已解决。整体H3后续仍需处理/复核本轮MQTT短暂中断、NIBP有效输入及90秒过期路径、C持久配置与正常启动方式，并取得合同内正式发布窗口及公网数据范围确认。C仍使用下载BOOT接线和RAM会话配置，断电会丢失配置；请勿把它视为正式常驻固件。原8884云安全组条目仍待现场撤销/收敛；未修改正式云端或其他安全组。当前已结束监听和真机操作；关闭串口后C持续运行状态未另行验证，不作为C冷启动验收。提交推送后等待审核，本次不再次安排电脑睡眠。

## 上轮交接原始记录（历史状态，以下保留原文）

交接日期：2026-10-20。最终裁定：**H3_BLOCKED（已有部分真实链路通过；未正式发布）**。

本轮遵循MPM-H3-001同一合同连续执行。最后正常断电重启A时，C输出 `GW CAN_FAULT_NETWORK_CLOSED_STOP` 后关闭网络并永久停留，未捕获重启Boot-up/新会话；按合同自动停止条款停止真机操作及正式切换。未绕过锁止、重新烧录或把之前通过窗口写成整体H3_PASS。操作者最后报告A已拔下J-Link、独立上电且两屏正常；这不能代替C捕获新Boot-up的验收证据。

## 代码身份与保护基线

| 对象 | 实际SHA/状态 |
|---|---|
| 独立工作区 | `E:/medical-monitor-h3` |
| 集成分支 | `dev/h3-nodea-cloud-ai-integration` |
| 最近代码提交 | `41ddc066b92ccdb46b6ecd442d669a9d1db26b14`，已正常推送 |
| C实板镜像对应源码 | `71eb0948b3e54cbf049f4e23c7c2462a9b3953f9` |
| A固定基线 | `3fa14b00a0823d2855e9dd8bd1c6c8545abb8dc5`，未修改/烧录A |
| P6固定基线 | `77dd14d1ca761a488956f7a4ebf28cb3174835e4`，按路径移植AI/Web，未整分支合并 |
| P4 / main | `67f5f57bd82c6e326e9e78ec9540481c80105e5f` / `50699048010c57ba10f8573461844c525b022a07`，远端复核未变 |
| 仓库 | 按先前明确授权改PRIVATE，保留历史；未强推/PR/合并/正式Security Gate |

本交接及最后停机/清理证据的提交SHA由包含本文件的Git提交确定，最终HEAD另在提交回执中报告；不伪造文件自包含自身提交SHA。

主要修改范围：完整联网独立物理CAN target引入H2R IRQ/128槽队列、保持RPDO→Adapter逐帧顺序；8MHz HSE与新鲜SNTP采样；各层累计计数与受限应用下载工具；只读Backend/AI与第七页整合；保留五槽历史、用持久事务流水替代累计五次上限；保留完整AI API路径；版本化隔离部署、正式发布准备及回滚工具。P4模拟回环及原核心QoS1/PUBACK/AT/TLS门禁未替换，未增加ASR/麦克风/真实TTS播报。

## 真实链路与故障结果

| 项目 | 真实结果与证据 |
|---|---|
| 活跃负载 | 420.080s端到端观察，新鲜PPG连续348.261s，退出0；`cloud/evidence/h3/e2e-probe-restored-observer-console.json` |
| 正常300秒计数 | 03:37:41–03:42:41 UTC精确300.000s；PPG PDO增加14424、0x381/0x481各300、0x681增加320，真实TXOK增加630、TIME增加30；FIFO/软件队列/Router/UART/Host新增丢失及发布失败0；`gateway/physical_can/evidence/h3/fresh-sntp-active-300s.json` |
| MQTT→Backend→WSS | MQTT1226、QoS1收到891、QoS0收到335，内存匹配值/样本差异0；Backend拒收2209→2209、丢弃0；匹配次数包含重复快照，不等同唯一包数 |
| 来源/有效性 | 现场声明非个人测试源，A标MOCK/synthetic；C自身LIVE。A ONLINE时可有源质量INVALID；B全程OFFLINE；无效值可见0，不填充读数/波形 |
| 真实授时 | 实际UDP SNTP样本RTT61ms/估计不确定性30ms；断网后新样本80ms/40ms；新消息年龄中位数PPG306ms、PR504ms、SpO2 383ms，非旧RTC年份检查替代 |
| 断网恢复 | 实际D命令断开Wi-Fi30s，180.058s观察退出0，STALE/OFFLINE后恢复新PPG；B非OFFLINE0、旧值冒充当前0、REPLAY作为当前0；`cloud/evidence/h3/wifi-disconnect-fresh-sntp-recovery.json` |
| 故障缓存 | 断网时32槽历史缓存溢出53条，独立记录，累计不清零；不与正常窗口混为零丢失 |
| 停探头 | 已实际停源，PPG正确STALE、SpO2/PR INVALID并隐藏值；现场确认曾取下探头，失败的连续窗口原样保留 |
| A正常断电重启 | **阻断**：拔下J-Link真断电后C锁止，未获得重启Boot-up与新会话；`gateway/physical_can/evidence/h3/uart-20261020T034336Z-result.json`、对应log、`node-a-power-cycle-stop.json` |
| NIBP | 当前INVALID。没有本轮新的有效血压源，真实有效值及90秒过期完整路径PENDING；不要求连续袖带测量，不声称临床准确度 |

原辅助“三流同时持续VALID300s”指标退出1、最长87.687s，保留在同一结果。新增显式active-ppg门禁对应合同活跃传感器300s，并检查5秒新鲜度、真实非空PPG、A在线、B严格离线及有效SpO2/PR匹配；未把源质量INVALID改为VALID，也未放宽生产TTL。早先600/360秒退出1均保留，不能删除后宣称从未失败。

### 最后阻断的已知事实及推断边界

源码 `gateway/physical_can/src/link_policy.h:21` 在TX等待100ms、TERR或BOFF时锁止；`bxcan_network_irq.c`使物理链路失效；`main.c:100`随即关闭网络并进入无限等待。只有A/C两节点时，A断电后C缺少其他ACK节点，与该严格策略冲突，是当前最强的软件归因方向。最后完整诊断在故障发生前仍显示FOVR/SW/UART/BOFF为0；致命分支没有最终ESR/TSR快照，**不能据此断言本次已实测Bus-off，也不能排除协议复位等其他失效路径**。

下一步应先补充停机原因快照与有界状态机Host/ARM测试，区分预期对端缺席与真实总线故障，在保持时效/累计计数及故障保护前提下审查重入策略；当前固件不应直接转正式使用。本次不继续板端复位/Flash写入。

## 普通测试、退出码与失败原件

| 检查 | 结果/退出码 | 证据入口 |
|---|---|---|
| Node-A Host/Keil | Host编译/运行0；ARMCC5.06u7退出0；A应用源码未改 | `node-a/evidence/a1-host-exit.json`、`a1-keil-exit.json`及同名日志；继承原A验证证据 |
| 物理协议/接收顺序/时钟 | Host 0；旧合并顺序参考故意失败3 | `gateway/physical_can/evidence/h3/host-result.json`、`rx-order-host-result.json`、`hse-regression/` |
| P5原逻辑/IRQ | 42项退出0 | `gateway/physical_can/evidence/h3/hse-regression/`、`fresh-sntp-regression/p5-legacy.json` |
| 新鲜SNTP | 原短读未累计退出1；修复后44项退出0 | `fresh-sntp-regression/p5-fresh.json`与`p5-fresh-final.json`及原始日志 |
| ARM隔离/正常 | 两种fresh-SNTP构建0 | `fresh-sntp-regression/arm-isolated-corrected.json`、`arm-normal-fresh.json` |
| AI/Backend/下载工具 | 既有联合79/后续107/本轮118项退出0；最新定向18项退出0 | `cloud/evidence/h3/ai-backend-joint.log`、`host-observation-regression.json`、`host-observation-targeted.log`与fresh/hse目录 |
| Web | 15项通过，失败0，构建及本地浏览器/监护连接通过 | `cloud/evidence/h3/web-final-test.log`、`browser/` |
| 真实浏览器 | 5项0，新增一次真实豆包调用；桌面/手机无横向溢出 | `cloud/evidence/h3/fresh-sntp-browser/result.json` |
| 真实AI路由 | 已验证保留前缀、401/404/405/超时及合法请求；事实解释可不调用模型 | 隔离AI/Web证据及上述browser目录 |
| Host日志中止 | Windows PermissionError导致原下载工具整体1，Flash读回/保护区仍通过；被动重接后连续记录 | `c-download-20261020T031423Z.json`、`uart-20261020T031546Z-host-failure.json` |
| 其他保留失败 | 原Backend取消异常、错误测试路径退出4、SNTP首次退出1、观察/串口/来源中断退出1；测试夹具缺目录1已修正 | HSE/fresh目录、`host-observation-regression.json`、历史E2E结果 |
| 本轮重启 | DEVICE_STOP / 退出1 | `uart-20261020T034336Z-result.json`，**本轮最终阻断** |

离线AI补测首次session_id格式错误422，未调用模型；修正请求时已恢复网络，200/NOT_CALLED仅证明恢复后事实解释，未冒称本次抓到离线AI。更早真实断网AI结果保留于 `actual-wifi-offline-ai.json`。

## 豆包、用量与截图

实际模型 `doubao-seed-2-0-mini-260428`，服务端DOUBAO/MONITOR；ARK密钥始终在服务器安全配置。浏览器仅临时持独立应用令牌。第三方模型输入仅已授权的来源/有效性最小元数据及一般问题，不传原始PPG/生理数值/人员身份/完整问答历史。

持久流水：旧3次3578 Token完整保留，H3新增7次3918 Token，合计**10请求/7496 Token**，H3七次均VALIDATED；没有累计调用上限，无自动无限重试。并发4、分钟速率12、超时/失败熔断仍有效。账户仅由操作者确认免费额度或安心体验；未核到账单金额，不把费用写成零。明细见 `cloud/evidence/h3/usage-after-fresh-sntp-browser.json`；历史mtime纠正单独记录，不改旧审计字节。

![桌面隔离AI页（问答与读数已隐去）](cloud/evidence/h3/fresh-sntp-browser/desktop.png)

![手机隔离AI页（问答与读数已隐去）](cloud/evidence/h3/fresh-sntp-browser/mobile.png)

截图来自实际CAN接入的隔离UI，辅助来源标签为非个人测试源；不能称正式HTTPS上线截图。设备播报默认关闭、真实喇叭播放未验证。

## 实际服务版本、资源与正式入口

- 实板C：40928B，镜像SHA256 `35d91a1e8db7762af06ef39b289ee871e20ac10cd74046ac988fbf9d9c00ebe4`；仅应用sector0–2，范围0x08000000–0x08009FDF；当前在锁止分支，未恢复原应用。
- ARM text40832/data88/bss123040；镜像比原26660B bench增加14268B。另预留SRAM512B、实际注入312B配置，非Flash持久配置。sector7/11各128KiB摘要及选项字节逐次未变。
- 隔离Backend实际运行过 `runtime-2ffd1d372ace`（源码bd0b5bd5a2169b785a9dd2bd168f83146688ce79），loopback18775；隔离AI `runtime-d32d9b2c1688`，loopback18776，关键AI源哈希与2ffd一致。
- 诊断隔离Broker8884为本轮独立凭据/ACL，未改正式Broker。最终已停止上述3个活动隔离服务并撤销本轮主机8884临时规则；用量流水、凭据受限目录、镜像与备份保留。PC独占Wi-Fi配置/探针Broker角色已恢复/清理。
- 最新发布准备包 `runtime-37808287a557`，源码41ddc066b92ccdb46b6ecd442d669a9d1db26b14，包SHA `37808287a557176031cac5134d2379b09bd71498b34ea802ed157b7b77e81858`。阶段目录 `/opt/medical-monitor-h3/formal/20261020T034945Z`，仅PREPARED；nginx语法0，尚未安装/启动候选正式unit。新增正式Backend配置使用独立MQTT client_id，避免踢掉隔离进程。
- 原Backend/Broker/AI PID分别845095/851111/394625，最终均active且未变；Nginx/静态入口配置原哈希不变。正式AI仍为原版本，旧累计五次限制**尚未由正式入口替换**。
- 原静态release仍为 `stitch-ui-interaction-20260922-113809`；正式HTML SHA `92a48ceea4afb3a3c5b6f34fadd7d3b56063e725321aa2471e3a9285db7a48f0`，正式Nginx片段SHA `8e9509551d97489c6cd6a92d4d44f9d6ef06392f031db285e0b1f05d30143ca2`。
- 正式HTTPS原站保持原样，没有本轮新上线地址；真实入口见本机受限 `C:/Users/Serendipity/.codex/private/medical-monitor-production.json` 的browser_url，连接地址不抄入Git。候选发布后操作入口应为原站 `/medical-monitor/#/ai`，当前不得声称已正式可用。未取得最终公网受众/权限发布窗口确认。

## 回滚结果与停止状态

1. **C应用回滚实际通过**：原sector0–2共49152B SHA `1185e8d74ce5bf320ed3b92a3dfc5d8771b66a99502d0e2ccd31491c83c370a0` 已回写并完整读回，见 `gateway/physical_can/evidence/h3/c-download-20261019T131801Z.json`；随后应用候选。C没有整片备份，不宣称整片可恢复。A原两份1MiB备份SHA `0fd4a4e8417b87a157fdf3e4f7c5a2a553c5aa9f69b4417fcac03c3a73d91516` 保留仓库外。
2. **正式云端未切换**：原路由/服务/静态哈希实际复核未变，见 `cloud/evidence/h3/final-isolation-cleanup.json`。原Web、Nginx、AI unit/env和Backend env备份只在服务器受限stage/backup。不能把nginx语法检查或“未切换”称为已完成正式切换后回滚验收。
3. 将来获准发布后可使用 `cloud/deploy/h3/formal_release.py activate/rollback --plan <上述stage>/plan.json`，仅经SSH别名在服务器执行；本次activate/rollback均未执行。正式unit启动/健康失败自动清理自己的候选；备份/源文件/env/config哈希变更即停止。回滚原路由后正式HTTPS复验仍PENDING。
4. 当前A现场报告正常独立启动，C物理链路锁止、网络关闭、COM15监听已结束。电脑睡眠/USB掉电会丢失C RAM配置，不能以正常Flash配置启动；后续需明确恢复窗口。BOOT0仍为现场下载接线，未擅自移动。

## 待处理事项与后续准入

- 优先修复并验证“A断电/重新上电时C的无ACK锁止和恢复”及停机原因最终快照；通过Host/ARM后在受限硬件窗口复测，捕获实际Boot-up、新会话、旧值失效。不得把强设PC/MSP/VTOR作为验收。
- NIBP有效输入与90秒真实过期路径仍PENDING，需要本轮获准的合格非个人血压测试源；不填示例数值。
- C RAM配置及临时Broker尚不具备重启持久性；正式持久方案须明确保护区与配置写入范围，未授权不改sector7/11。正常生产来源模式尚未实板验收，当前测试源标签必须保留。
- 上述阻断解决后，仍须合同H3-3的一次现场发布窗口与公网数据范围/受众/权限确认，再执行实际HTTPS七页/AI四类问答及真实回滚，不新拆合同，也不把准备包视为已上线。
- 操作者此前新增的腾讯云安全组8884规则尚需在控制台撤销或按后续批准范围收敛；本轮临时主机放行已撤销，未改其他安全组条目。
- 原仓库曾公开且历史有真人来源日志；现PRIVATE不等于撤回既有外部副本，历史未改写。

按用户最后要求保存、正常提交并推送后停止本轮工作并让电脑休眠/睡眠。系统当前支持S3；启用休眠命令因缺少管理员权限退出1，未自行提权。若执行S3将在最终回执准确标明，不把安排请求写成已确认进入电源状态。
