# MPM-B5-ESP-NET-001｜全链审计、授权沿革与局域网单包实测

日期：2026-10-27（北京时间）。唯一交付文件；状态：`OFFLINE_AUDIT_COMPLETE / CONTROLLED_LAN_UDP_BIDIRECTIONAL_PASS / G3_TIME_GATE_BLOCKED`。

基线为 `codex/node-b5-cloud-integration-20261026@71d255066361880af7bd8f9de3b503a76d097469`，开工远端取回一致。阅读了负责人提供的 `B5-ESP-NTP-COMMITS-AUDIT-20261027.md`，将其作为待核对的审计输入，本文结论来自Git、历史执行回执、原始UART/API记录及本机只读状态；文内未来动作均不是已批准执行。

初始离线准备没有连接实板或进行网络测试；追加执行按第0节R2及第12–15节后续授权沿革。始终不识别UID、校验设备镜像、烧录、写sector3、改BIO_V2、启动抓包、改变防火墙、SSH登录云端、恢复服务或发送B5START；没有重跑已通过的Host/ARM/TLS/UI/算法矩阵。历史工具、已消费授权、原码和恢复原件均保留。初始离线审计只新增本文；追加实验新增专用工具、定向测试及安全回执，受限附件不提交Git。

**最终结果：已完成PC受控局域网双向应用原码验证。** 共4次独立SDK会话：前三次发包前停止，第四次28.500秒完成；本轮总计仅一个48B请求和一个48B回复，两方向原码逐字节匹配、nonce一致、socket关闭确认。没有PCAP（负责人明确批准应用原码例外），不把它签为公网UDP123、可信UTC或G3通过。最初公网NTP无回包的唯一机制仍未确定。最新安全证据见[LAN-04回执](../evidence/B5-ESP-NET-PC-04/result.json)。

## 0. 追加执行授权沿革｜AUTH-B5-ESP-NET-PC-001 R2（已消费）

离线交付尚未提交时，负责人追加“准备完毕就进行一次电脑作为接收端的受控局域网双向测试，最终一并提交”；随后对本机防火墙关闭、Pktmon无权限/缺Npcap用户态DLL的实际差异，明确回复“批准，可以进行多次测试排查”。本次具体例外为：不修改防火墙，固定PC IPv4:42023，内核connected UDP只接收固定ESP源IPv4:42024，再核对完整48B与nonce；只取得PC/ESP应用原码，PCAP NOT_RUN，不能宣称防火墙已实现限制或抓包证据完整。后文初始离线草案不代表这些条件已经补齐；本节R2明确覆盖本次实际执行差异。

单窗口独立许可：新nonce、一个48B请求/至多一个48B回复；连续主动接收10秒；PC监听60秒；联合180秒硬限；只查询网络状态/CIPSTA和最小运行态，不重读UID、固件镜像或options。协议命令固定13槽：CIPSTA?、CIPSNTPCFG?、CIPMUX?、CIPRECVMODE?、CIPDINFO?、CIPMODE?、CIPSTATUS、固定UDP建连、完整tuple读回、CIPSEND=48、48B、CIPCLOSE、最终status。主动前置不符即停，不切模式、不灌时间、不自动入网。只在已发送载荷且序列刚好到CIPCLOSE、SDK健康/运行态通过时，允许一次预定关闭清理；原生错误不追加目标访问。普通同伴失败先协作STOP，8秒内退出，180秒硬限或SDK超时仍终止进程并保留目标状态未知，不以杀进程代替关闭socket。

执行器 `b5_esp_net_pc.py`及14项定向离线验证已就绪。监督器负例首次发现worker被终止且没有receipt时对None调用get；在实板前改为缺失回执保留空状态，原失败日志保留，14项随后通过。未重跑原矩阵。旧单包工具只复用受限读桥、正常SDK退出和二进制解析，不消费旧许可；新scope/新授权/.used独占。负责人多次排查许可由本轮主动限为最多3个独立180秒窗口，每窗新nonce/新原件/单次请求；先执行1窗，成功即止，不为了凑次数重发。ROM/HALT/意外复位或SDK原生错误仍立即停止，不自动RESET/Go/烧录。

R2实际启用文件、精确IP和请求、源/测试SHA、卡快照与有效期仅在受限EFS。实际结果见第11–15节；各阶段卡快照和真实次数分别保留，不扩展G3、云服务、正式配置或算法权限。

## 1. 完整提交链及历史裁定

B5实现提交 `c65fbedce7edf5d822c573ef5cdeb6471d1ae3d5` 的直接父提交确为B4 `ffa440b31b8b4993967f0e9aef1b3071a0d1dcfe`；H3选择性引入来源为 `a5cdd5b0b1ad48108fd631136e9de69e30582f2d`，没有整体合并。逐项核对从实现提交到基线的全部26个提交、父链和变更文件清单，并从相应历史提交读取15份关键阶段回执；附录列出全部提交。`c65fbed..71d2550` 的gateway与Node-B/src差异为空，后续诊断没有改动冻结应用源码。这不是本轮重新读回Flash或重验固件SHA。

| 阶段 | 已核对证据与真实结果 | 保留的边界 |
|---|---|---|
| B4冻结 | [B5-0历史审计](../evidence/B5-0/frozen-evidence-audit.json)：ECG60和独立RR15的B→C共同稳态窗分别通过；C24104安装/回退四阶段退出均0 | 两种源模式分开，不能合成同窗HR/RR有效；B5后续负载不是B4已经通过 |
| G1-A / G2-RO | `961b8f9`中G1人工MOCK六条消息Broker/Backend/WSS一致；G2-RO首次ROM停止，负责人另批复位后的双1MiB及双options读取通过 | 云MOCK为人工夹具，非ADC端到端；两个读取窗口不能合成一次无故障执行 |
| G2-A | `83bff8d`的[安装回执](../evidence/B5-G2A-ADMISSION/install-result.json)：42552B安装sector0/1/2，49152B镜像写入，完整校验、向量启动及DISARMED通过，退出0 | 原ESP在板例外明确；BIN尾部6600B保留；不是新恢复演练PASS |
| MEM-AP | `24e0dcc`保留Configure后SDK四字节读取返回-1，原始DAP尚未开始；`51e1813`的[修正窗口](../evidence/B5-MEMAP-READONLY-02/result.json)退出0、325次API、SDK/DAP一致 | 首次不是正数短读；第二窗不重复Configure。不能从修正后成功唯一倒推历史DLL内部原因或CPU ROM根因 |
| G2-B | `7c961db`的[真实写入](../evidence/B5-G2B-SECTOR3-01/result.json)：一次sector3擦除、83词阶段写入、一次提交字，110.641秒，generation 3→4，完整Flash/options/保留区与DISARMED通过 | 实际写入PASS保留；sector7/11逻辑保留不等于硬件WRP；本轮没有重写 |
| G1恢复 | `a44bbda`的[恢复回执](../evidence/B5-G1-RESUME-01/result.json)：Backend/TLS各start一次，退出0，未HUP/改ACL | 六小时生命周期；不能据历史PASS说现在在线或账号已撤销 |
| G3-01 | `21fe4a3`：单次START后2.078秒`GW FAIL AT`，T0未建立，正式评价0秒；[原件](../evidence/B5-G3-REAL-01/result.json) | `c0a7673`纠正软件RX环无字节≠ESP物理TX无输出。保存区间Broker实收0，不覆盖记录器退出后未知区间 |
| AT/GMR恢复 | `799a942`：负责人重插后AT/GMR实测成功，AT2.3.0.0-dev、SDK v3.4-22-g967752e2；[回执](../evidence/B5-ESP-GMR-REAL-04/result.json) | 同时报告Bin2.2.0(ESP8266_1MB)；不据标签推断新旧模块或无条件支持全部2.3命令；本轮不重新识别 |
| G3-02 | `e50a379`：17.687秒`GW FAIL TIME`，T0未建立，评价0秒；[原件](../evidence/B5-G3-02/result.json) | B的103份HR60诊断有效，不等于联网验收；TEC最高123、REC1、expired增加13057，不能签新传输PASS。后来全暗断电已确认，但具体时刻及420秒内停止未证实 |
| 时间原始查询 | `f5dbc1b`：先ROM停止且UART写0；另批人工复位后查询原文为SNTP关闭、epoch404；[两次回执](../evidence/B5-ESP-TIME-01/result-02.json) | 冷态变化丢失上轮易失状态，不能反推此前启用命令必失败；短格式解析在离线修正，原收据保留 |
| SNTP/DNS/PC | `741f1d2`：[汇总](../evidence/B5-ESP-SNTP-01/investigation-summary.json)：启用/读回OK但1513→1543；选第二目标后2526→2556；DNS三目标均解析，首目标为RFC1918；PC三个单包为超时/有效/有效 | 带引号DNS解析误判只离线修正；PC不是同时/同路径对照；最终SNTP已关闭。原G3默认设置覆盖临时服务器选择，不能据PC成功放行 |
| ESP单包 | `71d2550`：[回执](../evidence/B5-ESP-UDP-NTP-01/result.json)：一个48B请求、SEND OK、未见NTP回包、socket关闭确认 | 首窗false格式解析在发包前停止，0包；修正记录1包，不是重发。worker/监督退出0只表示诊断及收尾完成，不是UDP授时PASS |

结论保持：`B5_G2A_PASS / MEM_AP_READONLY_CROSSCHECK_PASS / B5_G2B_PASS / G1_HISTORICAL_PASS / G3_TIME_GATE_BLOCKED / CLOUD_E2E_NOT_RUN`。历史CPU ROM、B5独立冷启动、同窗HR/RR、绝对阻抗及CAN故障注入各自保留未解决/未验证状态。

## 2. ESP8266 v2.3.0.0原文与冻结实现对照

使用Espressif实际ESP8266 release-v2.3.0.0版本的[TCP/IP命令](https://docs.espressif.com/projects/esp-at/en/release-v2.3.0.0_esp8266/AT_Command_Set/TCP-IP_AT_Commands.html)、[基础命令](https://docs.espressif.com/projects/esp-at/en/release-v2.3.0.0_esp8266/AT_Command_Set/Basic_AT_Commands.html)和[消息定义](https://docs.espressif.com/projects/esp-at/en/release-v2.3.0.0_esp8266/AT_Command_Set/index.html)。Context7只返回较新ESP32示例，未拿它代替本机版本依据。

- UDP `CIPSTART`可指定本地端口和peer模式；peer模式0固定远端，和`CIPRECVMODE`不是同一个参数。上次省略本地端口，不是语法错误，但实际源端口未留证。
- 接收模式0主动以`+IPD`交付；模式1缓存后由MCU读取。该版本文档明确包含UDP被动模式及缓存满丢包说明，不能套用“ESP8266 UDP一概不支持被动”的说法。`CIPRECVDATA`用于被动模式，主动模式的ERROR不是独立链路故障证据。
- `SEND OK`只表明送交协议栈，不保证对端收到；`CIPSNTPCFG`的OK也不等于已经同步。省略服务器会使用默认集合。时间查询和设置是不同权限；本方案不设置时间。

冻结路径在[gateway_transport.c](../../gateway/mqtt/src/gateway_transport.c:376)及[platform.c](../../gateway/mqtt/src/platform.c:250)：

1. AT/ECHO/易失设置/入网后，设置单连接和被动接收；执行`CIPSNTPCFG=1,0`的返回值被忽略。之后最多15轮`SYSTIMESTAMP?`，每轮命令预算2000ms并延时1000ms；只有达到配置minimum_epoch才通过第一关，否则输出`GW FAIL TIME`。G3-02没有保存该阶段原始AT响应，所以不能从失败行区分设置拒绝、未同步或解析问题。
2. 编译确有`MP_H3_FRESH_SNTP`：第一关通过才调用[fresh_sntp](../../gateway/mqtt/src/gateway_transport.c:319)，读取服务器配置，再发一个原始UDP请求，使用共用`esp_mqtt_send/recv`。要求48B、originate匹配、LI/版本/mode/stratum合法、时间下界及处理时延合理、RTT≤1000ms、关闭成功；随后才进入CA、名称、SNI、TLS和MQTT。
3. 第一关不会因PC受控回包成功而自动解除。共用接收器按被动长度查询及读数据工作；本机主动单包诊断与固件被动接收并非同一条已验证路径。收到主动包的实验结果也不能直接签该被动路径PASS。
4. G3主机要求60秒内建立新鲜T0；Wi-Fi最多30秒、TIME查询预算及后续授时/TLS共用这一准备窗口。成功耗时仍缺实测，不能把最坏预算相加当成实际TIME失败根因，亦不能改60秒或1秒判据以制造通过。

没有修改以上实现，也没有把内置SNTP故障、共用接收器问题或路由器封UDP123提前裁为根因。

## 3. 最新单包原始复核

本轮从受限EFS重新读取原授权、DNS原文、48B请求、原生API日志、各段baseline/原始AT回复及关闭时序；没有重读设备。

| 项目 | 离线重新核对 |
|---|---|
| 请求 | 48B，首字节0x23；40–47为本次唯一8B标识，原SHA `14117f664573a7131ef04bcf6f5f6c3bc12138b9f20d10fa4ebc21e6906b9bba`。该字段只用于匹配，不是线缆发送时刻或给设备授时的证据 |
| 实际发送 | 从AP写寄存器日志重建221个UART_DR字节，与11槽冻结计划及计划SHA完全一致；仅一个48B载荷，payload marker已消费 |
| 目的/本地端口 | 目的为既有第二DNS结果UDP123，地址只在EFS。`CIPSTART`没有本地端口参数；只在建连前/关闭后查status，建连回复也不带本地端口，故实际本地端口为`UNKNOWN_NOT_CAPTURED`，不能补写123或猜一个随机值 |
| RX覆盖 | 发送段28B、被动读取28B、关闭27B，对应下一baseline的head差恰好相等，未记录字节分别0/0/0，四项错误/消费计数均0；各阶段原文未见+IPD，实际回包文件0 |
| 时间 | 载荷最后UART写后约0.437秒见SEND OK；主观察截止send+2秒；约3.281秒见close完成、3.718秒完成最终status。这是SDK观察时点，不是服务器RTT |
| 收尾/限制 | CIPCLOSE OK、STATUS2且无连接；C退出运行态/DISARMED通过，SDK会话关闭。不是全片完整性复验；没有数据支持“2秒后永不回包”或“AP/服务器已收到” |

两条执行记录均保留：R1因`CIPDINFO:false`格式提前停止，socket打开0/载荷0/退出1；修正后R2载荷1、worker/监督退出0。主动模式下额外被动读取ERROR照录，不能作为第二个独立网络失败证据。nonce/LI/stratum等回包校验为`NOT_RUN_NO_REPLY`，没有伪造包或补零。

## 4. Windows受控回复端：本机已知条件与缺口

只读检查时间：**2026-10-27T10:29:31.154115+00:00 UTC**。精确本机IPv4、前缀、网卡信息、端口清单及未来目的绑定保存在既有受限EFS；本文不刊登私有地址。

| 条件 | 当前结果 | 对实测的影响 |
|---|---|---|
| 目的IPv4/网卡 | 一条物理默认IPv4接口，ifIndex6、RZ616 Wi-Fi 6E 160MHz；固定其唯一IPv4为`PC_LAN_IP` | 它是本机端点候选，不是已证实ESP可达。ESP源IPv4仍缺；未来核对路由，禁止默认把同Wi-Fi当同可达LAN |
| UDP123 | 由svchost持有 | 不占用/停止现有服务；改选本机高位UDP42023 |
| UDP42023 | 当前无占用且不在系统UDP排除范围 | 本轮未bind，不能保证未来仍空闲；正式bind失败即停，不自动换端口 |
| 网络分类/策略 | 无线接口为Public；ActiveStore三种profile的Enabled均False，Inbound=Block/Outbound=Allow | **防火墙当前未启用。新增Allow规则本身不能实施来源限制。** 本轮不启用或修改全局策略；恢复适用防护或使用另一台受防护测试机，必须另批 |
| 抓包工具 | 有Pktmon和运行中Npcap；PATH/默认目录没有Wireshark/tshark/dumpcap，Npcap raw80211=0 | PC成为端点后无需无线monitor；本轮不安装工具/驱动或切网卡模式 |
| 抓包准入 | `pktmon status`实际返回拒绝访问；本机help确认支持list JSON | 管理员上下文/现有会话/组件编号未验证。ifIndex6不是Pktmon component ID，严禁直接代入 |
| 其它路径 | Meta Tunnel处于Up；本轮未动代理、路由或共享 | 未来对ESP地址做本机只读路由选择，确认报文走选定物理接口；不自动关闭代理/改网络 |

[微软Pktmon](https://learn.microsoft.com/en-us/windows-server/networking/technologies/pktmon/pktmon)可记录本机网络栈；这里让PC成为唯一请求目的端，避免把旁路电脑抓不到第三方单播误判成ESP没发包。本机抓不到时还须核对抓包位置、服务绑定及丢包计数。[组件列表](https://learn.microsoft.com/en-us/windows-server/administration/windows-commands/pktmon-list)与[过滤器](https://learn.microsoft.com/en-us/windows-server/administration/windows-commands/pktmon-filter-add)按本机版本读回后冻结，不假定管理员权限已经具备。

## 5. PC单次回复器与抓包设计（未部署）

固定`PC_LAN_IP:42023 ← ESP_IP:42024`。只绑定该PC IPv4，不绑定0.0.0.0/IPv6，不发现或广播；单个`recvfrom`接受上限49B，实际长度必须48、peer IP/port准确、请求全部48B与本次固定请求相同，才允许一次sendto。任何错误、超长、旧nonce或其他来源立即退出而不回复；不等待“下一个正确请求”。回复从同一绑定socket回到原peer，不另建随机源端口socket。

新离线请求已生成但**未发送**：48B，byte0=0x23，1–39为0，40–47为新的随机8B nonce，和已消费请求不同；原文/nonce只存EFS。请求SHA `19e6cdeddee95290ec8708e7020c4defd25ebd2e6fad07de1f34d63dbc82de08`；nonce SHA `974762df05ccac54613dde0d138fcdf696273375876904dafaaebef145c25300`。nonce不是可信UTC。

回复为48B测试报文：byte0=0xE4（LI3/VN4/mode4），byte1=16，12–15为`TEST`，24–31逐字节复制请求40–47；32–39/40–47分别记录PC收到/发出时的NTP格式时间，其他字段固定0。PC只读取现有时钟，不调整时钟；完整实际回复另存原码及SHA。**LI3/stratum16明确非授时源**，本实验只判路径/字节/nonce一致，不能调用原NTP合法授时判据给它签有效UTC。该定义符合[RFC5905字段语义](https://www.rfc-editor.org/rfc/rfc5905.html)，并让冻结G3校验必拒绝，避免测试PC冒充可信时钟。

抓包先准备、回复器READY后才允许ESP发送：只记录上述IPv4二元组、UDP42023/42024、完整包长。优先在确定的物理NIC组件及必要本机栈丢弃点取证，记录位置/方向并按同一nonce去重，不能把同一包在多层出现算多次发送。保存ETL/PCAPNG及应用原文；没有PCAP/抓包工具成功证据时，只能签应用收发观察，不能签双向线缆取证完整。抓包最多180秒/16MiB，不覆盖旧文件；既有Pktmon会话/过滤器未知或存在时停止，不清空别人的过滤器或停止其它会话。

受限防火墙规则草案依据[New-NetFirewallRule](https://learn.microsoft.com/en-us/powershell/module/netsecurity/new-netfirewallrule?view=windowsserver2025-ps)：唯一事务名、Inbound/UDP、LocalAddress=PC_LAN_IP、LocalPort=42023、RemoteAddress=ESP_IP、RemotePort=42024、InterfaceAlias=固定无线接口、Program=固定Python路径、Profile=Public、EdgeTraversal=Block。以下条件先于创建：启用的适用profile及既有显式阻断/GPO已审阅，管理员能力可用，源IP已冻结，当前profile/路由未漂移。本轮三profile关闭，故此项**BLOCKED，不能称规则已生效**。不全局关闭防火墙、不把网络改为Private、不开放LocalSubnet/Any来源，不自动安装或改系统代理。若负责人不允许恢复适用防护，保留阻塞或选择另一个受防护端点，不静默扩大权限。

未来批准的本地事务必须包含精确清理：60秒监听超时、最多一次请求/回复；硬限180秒。关闭自己socket/抓包，仅撤销自己创建且instance/name匹配的规则与filter，验证42023不再监听及新规则不存在；失败不重启服务或自动扩大规则。启用Public配置文件属于额外系统变更，必须事先冻结影响及回退，不隐含在一条入站Allow许可里。

## 6. 独立授权草案：AUTH-B5-ESP-NET-PC-001 R1

**`DRAFT / enabled=false / owner_approved=false / NOT_EXECUTABLE`。旧AUTH-B5-ESP-UDP-NTP-001及其marker已经消费，禁止复用。本文不是实际执行许可。**

| 项目 | 固定范围/门禁 |
|---|---|
| 目的与次数 | 只用受限附件中的PC_LAN_IP:42023；ESP本地42024、UDP peer模式0；一个上述新nonce，一个48B请求，PC至多一个48B回复，重试0/替代目标0 |
| 时间 | 原始接收从最后载荷UART写完成起连续10秒，包括SEND OK等待；不能收到一包就提前关闭或换baseline漏包。PC监听60秒，联合事务180秒硬停，无限等待/自动续期0 |
| 现场 | 沿用已知C/ESP，不重新识别UID/固件SHA；只核实Flash运行态、VTOR/DHCSR/Fault、DISARMED和串口错误。ROM/HALT/异常复位/native错误立即停，人工复位/Go/重刷0；上电或转接不含在本草案，确需时另列电气步骤 |
| 源网络附件 | ESP当前IPv4未知：未来若另批，可在同一新窗口仅一次`AT+CIPSTA?`取得站点IP，不读取MAC/UID或Wi-Fi密码。先固定该源IP并完成路由、受限防火墙和抓包附件，再允许UDP建连；未知时不开放宽泛规则 |
| 被动/主动前置 | SNTP保持关闭、CIPMUX0、CIPMODE0、CIPRECVMODE0、CIPDINFO0/false、无既存socket、已联网；这些仅查询，异常即停，不自动改配置或重新入网。实际若为被动1，不临时改为主动；改用另一张精确卡 |
| 命令次序 | 网络前置通过后，`CIPSTART="UDP","PC_LAN_IP",42023,42024,0`一次；建连后`CIPSTATUS`一次核对完整peer/local tuple；`CIPSEND=48`一次，得到提示后48B原码一次；连续记录主动+IPD，不再发CIPRECVDATA；10秒后CIPCLOSE一次，最终status一次确认无socket |
| 固定字节/窗口绑定 | 新工具必须冻结整个命令计划及SHA、请求SHA、DLL/监督器/源代码SHA、读写白名单、独占一次性marker和本次私有附件。旧单包工具目的端口固定123且缺建连后status，**不能直接拿旧执行器改参数上板** |
| 接收与判据 | 以长度解析二进制（含NUL/OK/ERROR），主动数据可在SEND OK之前或之后到达；从发送到close/status全程归档。核对PC请求、PC回复、ESP原文同nonce/同48B；不把SDK观察时点当线缆RTT，不将路径PASS改名授时PASS |
| 收尾 | 正常socket关闭并确认无连接；C保持DISARMED，已验证健康状态下使用既有正确SDK退出策略。若原生错误不再追加目标访问；无法证明socket关闭时按另批应急步骤由负责人切C供电/J-Link USB，不把进程退出当MCU或网络停止 |
| 永久禁令 | Flash/sector3/算法/ESP固件/人工系统时间写入0，TLS绕过0、B5START/G3/MQTT0、正式云/ACL变更0；不改源、电极、CAN、跳帽或B供电 |

**实际启用前尚缺**：新scope执行器/监督器及必要纯离线负例；ESP源IP附件；PC管理员抓包权限、Pktmon实际组件/空闲会话证明；适用防火墙的启用及规则许可；现场供电/连接是否沿用的单次事实附件。新私有草案没有有效期许可、工具SHA、`.used`或执行目录；不能仅凭本文存在进入实测。

下一步工具必要负例仅围绕新范围：错误目的/端口/nonce、旧marker、ROM/HALT、SDK短读/超时、监听失败、不同源、47/49B、二进制内嵌终止词、早到/迟到/重复回复、错误本地端口、环覆盖缺口、关闭未证实和180秒监督器退出。不是重跑已通过固件/算法矩阵；本轮仅设计，未冒称这些新执行器负例通过。

## 7. 未来证据如何归因

| PC入口抓包 | PC应用接收/回复及出口抓包 | ESP主动+IPD | 可以说什么 |
|---|---|---|---|
| 无 | 无 | 无 | 先排抓包组件、绑定、路由、主机策略及ESP/AP路径；不能认定ESP没发或路由器封包 |
| 有 | 应用无接收/无回复 | 无 | 请求已达PC观测点，本机防火墙/服务绑定/响应器优先；不能归因公网NAT |
| 有 | 应用发送且出口见匹配回复 | 无 | 回程/AP隔离/ESP接收或ESP→MCU路径待查；PC出口并不证明无线交付到ESP |
| 有 | 请求/回复完整匹配 | 有且同nonce48B | `CONTROLLED_LAN_UDP_BIDIRECTIONAL_PASS`；不证明公网、UDP123、内置SNTP或G3授时 |
| 不完整 | 仅sendto成功 | 任意 | 降级为应用层观察，不能把sendto/SEND OK当物理发送或对端收到 |

不登录路由器也能缩小故障范围，但不会凭单一结果把AP、路由、NAT、ESP接收、UART或内置SNTP合成一个根因。

## 8. 可选受控公网端点（只设计）

状态`NOT_SELECTED / NOT_DEPLOYED / NOT_AUTHORIZED`。仅选另行指定的非生产主机/隔离测试实例及既有SSH别名，先只读审阅UDP占用、出口、现有业务和防火墙。一次独立授权只选一个高位端口与一个公网IPv4，冻结源出口允许范围、nonce、48B请求/回复、主机入口/出口抓包、60秒监听和180秒硬停，应用只接受一次且不放大。地址/凭据只入受限附件，不提交仓库。

高位端口通过只证明该UDP路径/NAT回程；UDP123是另一项独立对照，不能自动补测。没有已批准的可用非生产端点就跳过，不对现有正式监护服务器开放端口、不停chronyd/Windows Time、不改正式防火墙或NTP服务，不用公网第三方试错。恢复/撤销仅针对本次创建的服务、socket和精确规则，启动/停止/变更权限必须在未来卡中逐项列明。

## 9. G1到期风险及新鲜只读核验草案

历史最后查询为北京时间2026-10-27 17:10:17，Backend/TLS当时active，剩余约327秒，少于原G3预检要求的625秒；历史预计六小时上限为17:15:45。本文本机检查时已越过该预期时刻，**当前真实存活UNKNOWN，需要新鲜只读核验；不能直接断言已经停止。** 账号/ACL不会随服务停止自动撤销，不声称环境已清理。

另列`AUTH-B5-G1-LIFECYCLE-RO-002 R1 / DRAFT_DISABLED`：沿用受限部署包和既有SSH别名，一次SSH、远端45秒/本地55秒硬限、重试0；仅systemctl show两个既有测试unit的Active/SubState/Result/PID/RuntimeMax/Restart/启动退出时间，读取监听18775/8884及正式unit状态/PID、配置hash/测试角色残留（不输出口令/令牌），原始返回EFS。复用[b5_g1_lifecycle_readonly.py](../tools/b5_g1_lifecycle_readonly.py)的只读逻辑，调用前绑定新授权/监督及当前源码，**本轮不运行它**。不start/restart/reset-failed/daemon-reload/HUP，不改ACL、Backend、Hub、正式站点或证书，不MQTT CONNECT/发布、不打开WSS。实际健康/TLS握手要另列范围，不能把unit active当完整服务验收。若到期停住，只报告并等独立恢复批准。

## 10. 本轮验证与下一轮最少配合

已完成：远端基线一致；全链26提交/15历史回执核对；冻结应用源码未变；原221B发送计划及RX覆盖复核；本机IPv4/候选端口/排除范围/profile只读盘点；一次新的离线请求/nonce及禁用草案生成；受限附件EFS属性检查。离线准备时没有运行旧矩阵或实板/UDP/云探测，之后追加实测见第11–15节。Pktmon状态只读返回拒绝访问；一条不适用于本机的`list --help`语法返回错误，后用`comp list help`只读确认语法，未启动抓包。

负责人下一轮只需一次决定/配合：是否允许在本机管理员上下文完成只读抓包准入，以及是否允许审查并恢复Public防护（否则选另一台已有防护的受控电脑）；现场沿用C/J-Link则不转接，确需上电/移动时另列一次步骤。ESP网络IPv4可由未来明确批准的CIPSTA查询取得，不需负责人查路由器型号、登录后台或重复提供板卡/固件资料。随后工具SHA/现场附件齐全，才提交可执行的新卡等待PI批准；不是现在让负责人改网络或操作硬件。

正式G3继续独立审批，必须同时满足内置SNTP门禁、新鲜合法UDP授时、TLS/AT实物兼容、测试服务剩余预算、B/C联合记录与可执行停止/恢复条件。PC测试数据永远MOCK，不进入真人LIVE语义。

## 附录A：26个提交完整索引

下表来自实际Git历史；阶段回执以原提交版本读取，不用今日累积交接替代当时失败事实。

| 提交 | 内容与本次裁定 |
|---|---|
| [`c65fbed`](https://github.com/Serendipity-min/medical-multi-parameter-monitor/commit/c65fbedce7edf5d822c573ef5cdeb6471d1ae3d5) | B4父基线上的B5源码与42552B软件候选；既有离线PASS保留 |
| [`baa08b8`](https://github.com/Serendipity-min/medical-multi-parameter-monitor/commit/baa08b850c9bd5e62ace7682a937b9c68423a0fa) | 冻结实现与交付引用，非新增实板 |
| [`c2f0114`](https://github.com/Serendipity-min/medical-multi-parameter-monitor/commit/c2f0114c0df2f93d25e0fd271862f692d1991d57) | G0真实云准入只读与分开的禁用卡 |
| [`bdc7131`](https://github.com/Serendipity-min/medical-multi-parameter-monitor/commit/bdc71313c2c6ebff056d4aa5ffdda9a9b334ea7c) | G0独立远端回读记录 |
| [`961b8f9`](https://github.com/Serendipity-min/medical-multi-parameter-monitor/commit/961b8f957689dc52860fdb101051167b906e8c7e) | G1人工MOCK部署PASS；G2-RO首次ROM停止/另批后双读PASS |
| [`72a0220`](https://github.com/Serendipity-min/medical-multi-parameter-monitor/commit/72a02209c0ba205163be46bfa83ed3ae50d49925) | G1/G2-RO独立远端交付核验 |
| [`7c7c625`](https://github.com/Serendipity-min/medical-multi-parameter-monitor/commit/7c7c6250db2a5c584ec33709a3eeb23fc3022bbd) | sector3真实加密包/写入器离线准备，保留停机检查点 |
| [`7c53555`](https://github.com/Serendipity-min/medical-multi-parameter-monitor/commit/7c535558db0a65cf2a11298fb1db80f445fa2ea2) | 离线准备远端核验，尚非写入 |
| [`83bff8d`](https://github.com/Serendipity-min/medical-multi-parameter-monitor/commit/83bff8d4ff33184dc985a2b30acb980cb465abbc) | G2-A安装PASS；首次MEM-AP切换失败原件保留 |
| [`24e0dcc`](https://github.com/Serendipity-min/medical-multi-parameter-monitor/commit/24e0dcc00d55b971332f96da6f0cd457ff4657e9) | SDK原生-1及Configure时序审计；离线修正 |
| [`d74f9ae`](https://github.com/Serendipity-min/medical-multi-parameter-monitor/commit/d74f9ae7592e6d8d88bd29729b6c2837af4f884c) | G2-A及MEM-AP审计远端回读 |
| [`51e1813`](https://github.com/Serendipity-min/medical-multi-parameter-monitor/commit/51e1813a038a5c7a1df9afd4562ad5d910b1ba09) | 修正版MEM-AP实板交叉核验PASS |
| [`0140c98`](https://github.com/Serendipity-min/medical-multi-parameter-monitor/commit/0140c98dda6c923ce805584dd0c46bb9d1a6a499) | MEM-AP通过记录独立远端回读 |
| [`056791a`](https://github.com/Serendipity-min/medical-multi-parameter-monitor/commit/056791a38c6897d6cab66fe942d6ccf0d4a5f97a) | sector3写入器绑定已验证连接流程；必要离线准备 |
| [`478e77a`](https://github.com/Serendipity-min/medical-multi-parameter-monitor/commit/478e77abf8813a4e4089a22600d8224a98175dc0) | 连接流程写入器远端回读记录 |
| [`7c961db`](https://github.com/Serendipity-min/medical-multi-parameter-monitor/commit/7c961db042ea3547788766444cc7aceba5f5ac18) | G2-B一次真实sector3写入PASS，保留所有边界 |
| [`a44bbda`](https://github.com/Serendipity-min/medical-multi-parameter-monitor/commit/a44bbda028f1baaf1810361b85370b5c535e244c) | 仅测试Backend/TLS恢复PASS，G3仍DISARMED |
| [`9f32611`](https://github.com/Serendipity-min/medical-multi-parameter-monitor/commit/9f32611f5e1b9da977c851a3c9da0605e14023d3) | G3联合工具/标准/待批现场卡准备 |
| [`1c6da7c`](https://github.com/Serendipity-min/medical-multi-parameter-monitor/commit/1c6da7ce45d86ce6cfe47866fdf53e22354acc1a) | G3前C真实只读准入PASS记录 |
| [`21fe4a3`](https://github.com/Serendipity-min/medical-multi-parameter-monitor/commit/21fe4a392153997b0c2434228ad9b32e4a0d01d0) | G3-01 AT失败与备用模块查询原件；正式评价0秒 |
| [`c0a7673`](https://github.com/Serendipity-min/medical-multi-parameter-monitor/commit/c0a7673c83ca63630ebd1f99fc6a85f58d6e2da2) | 纠正RX软件环为零的证据边界 |
| [`799a942`](https://github.com/Serendipity-min/medical-multi-parameter-monitor/commit/799a9429b12d62fed3bb7f56b572606f2e24380b) | 重新插接后AT/GMR恢复PASS，不唯一认定原故障机制 |
| [`e50a379`](https://github.com/Serendipity-min/medical-multi-parameter-monitor/commit/e50a37900f986b22e6b20e70a33136ea6dbc89d9) | G3-02 TIME失败，正式评价0秒，保留停止证据缺口 |
| [`f5dbc1b`](https://github.com/Serendipity-min/medical-multi-parameter-monitor/commit/f5dbc1b5d67d389738b5c46ac3dfde9b9357021b) | ROM停止原件与另批后的原始时间查询 |
| [`741f1d2`](https://github.com/Serendipity-min/medical-multi-parameter-monitor/commit/741f1d2573845bfb766fb466490150e579a687c3) | SNTP启用/DNS/PC参照/目标选择；ESP有效UTC仍BLOCKED |
| [`71d2550`](https://github.com/Serendipity-min/medical-multi-parameter-monitor/commit/71d255066361880af7bd8f9de3b503a76d097469) | 一次48B ESP请求，无回包观察，socket关闭已证实 |

## 附录B：受限归档与交付核验

原始PC地址/前缀/端点占用/profile、历史回执检查清单、API/环复核、新请求/nonce及禁用目的包均存既有受限EFS的新`ESP-NET-OFFLINE-*`目录；本地忽略的`node-b/build/b5-esp-net-offline-pointer.json`可定位。没有复制固件或私有配置到Git。本报告只包含安全状态和来源SHA，不包含实际目的IP、Wi-Fi密码、令牌、UID或原始网络地址。

正常提交仅限B5独立分支，提交后使用独立远端取回逐字节核对本文并检查干净工作区；实际结果写忽略的交付回执及EFS，不能在提交前预签通过。无保护分支合并、PR、历史标签操作或Security Gate；完成交付后停止，等待PI批准。

## 11. LAN-01实际执行：发包前拓扑门禁停止

R2工具及14项离线验证通过后，按负责人明确批准的防火墙关闭/无PCAP例外执行一次独立窗口。C最小入口在Flash、VTOR=0x08000000、DISARMED；SDK会话1406次API，UART只查询98B，没有重读UID/Flash/options。单次CIPSTA?返回的有效私有站点IP不在PC物理无线IPv4前缀内，后续PC本机只读Find-NetRoute显示去ESP选路为ifIndex14 Meta Tunnel，而不是已冻结的ifIndex6物理无线。因此触发LAN_NOT_LOCAL_PEER。

实际ESP载荷0、PC监听0、回复0；两worker/监督/调用者退出均1，调用者耗时5.141秒。PC的失败是监督器协作STOP，不是另一个网络超时。UDP socket从未打开，不能把socket_close_confirmed=false读成关闭失败。C失败出口最小运行态通过、退出续跑策略启用、主机会话已关闭；没有RESET/Go、烧录、阈值或云端动作。新授权窗口已消费，不能复用.used；本轮许可下尚未发送新UDP。

[安全回执](../evidence/B5-ESP-NET-PC-01/result.json)及源码绑定/离线成功与负例均保留；原码只入EFS。这只是局域网试验前置未成立，**不证明之前公网UDP123失败由电脑VPN造成**。负责人已收到一次配合步骤：仅把电脑连到ESP原来那个Wi-Fi/非访客LAN，不改C/ESP配置、不复位、不先关VPN；完成后只读核对新IPv4/选路再用新nonce和新授权窗口。未取得完成事实前不再次连接实板或发包。

## 12. 负责人追加易失Wi-Fi切换｜AUTH-B5-ESP-NET-PC-001 R3

负责人给出目标Wi-Fi和口令，并提供当前Windows网络截图。文字名称含“网络”后缀而截图SSID字段不含，实际目标采用截图与本机当前SSID相符的已保存WLAN profile；口令只从本机该WLAN凭据存储导出至既有EFS，未放进源码、命令行、公开日志或版本库。首次按NetworkProfile名称导出没有XML；改用实际WLAN profile，netsh导出消息指出文件落在EFS中的另一个路径，已按返回路径验证范围/EFS并归档。未改Windows profile、网络分类、代理、路由或防火墙。

目标当前在PC可见列表只有信道44（5GHz）；未见同名2.4GHz不能直接断言不存在。ESP8266仅支持2.4GHz，依据Espressif官方数据手册；下一窗只允许一次易失CWJAP验证，不扫描其它ESP网络或重刷模块。新增前缀顺序：CIPSNTPCFG?确认关闭、CIPSTATUS确认无socket、SYSSTORE=0、SYSSTORE?确认0、CWJAP一次（30秒内），随后原LAN前置与单包序列。前缀或连网失败则不发UDP，不自动换SSID/口令。新16项定向离线检查通过，旧窗口原工具和回执不改。

R3为第2个独立180秒窗，新nonce/新精确计划/新.used；已批准的应用原码和防火墙例外继续明确绑定。本次只改ESP RAM中的Wi-Fi连接，不写C sector3、不执行ESP持久化设置、不灌时间或启动G3。即使新LAN通过，冻结C配置仍指向原网络；未来G3会按旧配置重新CWJAP，新持久化包/CRC/generation需另批，不能据临时切换放行。

## 13. LAN-02实际结果与最后一个LAN-03窗口

LAN-02执行19.703秒，SYSSTORE=0及读回0均OK；一次CWJAP约16.110秒后原始返回+CWJAP:3/ERROR，尚未进入CIPSTA及UDP阶段。PC回复器未打开、UDP载荷/回复均0，所有worker/监督/调用者退出1。C保持DISARMED、正常Flash失败出口、SDK健康关闭（1609次API、UART99B）。完整SSID原始字节与Windows profile hex逐字节相同，排除本次UTF8/转义差异；PC当时仅见该SSID信道44。不能由此认定路由器永久没有2.4GHz，也不能把尚未发包的窗口记成UDP无回复。见[安全回执](../evidence/B5-ESP-NET-PC-02/result.json)。

负责人随后提供另一个确切2.4GHz SSID并明确口令沿用，截图信道7。本机读回确认当前SSID已变化、PC IPv4未变、Public分类、42023空闲、防火墙现状未变；原工作进程均已退出。AUTH-B5-ESP-NET-PC-001 R4仅绑定这个新目标、从既有EFS凭据沿用口令、新nonce、新.used与LAN-03目录，不复用前两窗。工具源码不变，沿用已通过的16项离线验证不重复运行。只进行一次SYSSTORE=0易失连接与条件单包；仍是180秒硬限、10秒主动接收。该窗为本轮预先约束的最后一个独立窗口，成功即停止，不自动补公网NTP或G3。

## 14. LAN-03主机误判原件与纠正执行R5

LAN-03在原始STATUS5且无任何CIPSTATUS连接条目时，被主机入网前门禁误标LAN_WIFI_PREEXISTING_SOCKET。实际只查询30B、499次API、2.766秒，CWJAP=0、PC监听=0、载荷/回复=0；所有worker/监督/调用者退出1，C健康Flash/DISARMED出口及SDK正常关闭。原因是错误复用了“已联网且无socket”的入网后谓词到入网前，不是实板ROM、密码错误或新网络拒绝。见[原件摘要](../evidence/B5-ESP-NET-PC-03/result.json)。

已修正为入网前允许STATUS2/4/5，但只要有连接条目仍拒绝；入网后仍必须已联网。增加针对STATUS5及实际连接条目的负例，17项离线验证通过。负责人此前明确允许多次排查且最新指定的新2.4GHz目标尚未真正尝试，本次只补做这一未完成目标的一次连接/条件单包，另存AUTH-B5-ESP-NET-PC-001 R5、第四次SDK会话LAN-04、新nonce/新.used；不把它伪装成原三次之内，不复用任何已消费授权，不做第五次自动重试。仍180秒硬限、CWJAP至多1、应用请求/回复各至多1、主动接收10秒，ROM/HALT/native错误立即停、RESET/Go/烧录/G3均0。

## 15. LAN-04最终实测通过与故障归因边界

新2.4GHz目标按一次SYSSTORE=0/读回0后CWJAP成功，CIPSTA确认与PC同网段；建连后CIPSTATUS核对PC目的42023、ESP本地42024。PC独占绑定固定IPv4/42023并connected到固定ESP/42024，只接收完整预定48B后回复一次。ESP在固定10秒主动观察内收到唯一+IPD帧，其48B与PC实际发出的48B逐字节相同，originate与新请求nonce匹配；PC收到的请求也与冻结请求逐字节相同。

| 最终指标 | 实测 |
|---|---|
| SDK会话/本轮应用UDP | 4次会话；前三次载荷0，最后一次请求1、回复1；没有第五次自动尝试 |
| 最后窗口耗时/退出 | 28.500秒；PC/ESP worker、监督及调用者均0 |
| 原码与RX | 请求48B/回复48B双向完全一致；主动记录88B，RX头覆盖缺口0 |
| 实际UART计划 | 原生API重建348B，与18槽冻结计划及SHA完全一致，包括唯一CWJAP与唯一48B载荷 |
| 本机选路 | 测后去ESP选路ifIndex6物理无线；不再是先前旧子网去ifIndex14 TUN的路径；未改代理或系统路由 |
| socket收尾 | ESP CIPCLOSE及最终无连接status通过；PC socket关闭，本机只读42023无监听 |
| C状态与退出 | 4918次SDK调用；退出前VTOR=0x08000000、Flash运行采样、Fault=0、DISARMED；正常SDK退出。未追加Close后的独立实板读取 |
| 时间语义 | 回复LI3/stratum16/refid TEST，明确非授时源；不安装时钟、不签有效UTC或1秒RTT |
| 例外与写入 | 无PCAP；Windows防火墙保持原关闭状态（明确批准）；只切ESP易失Wi-Fi，MCU Flash/sector3、UID/镜像复核、RESET/Go、B5START均0 |

已确定的失败机制分开登记：

1. LAN-01本机与ESP不在同一前缀，本机去旧ESP地址选TUN；这是PC局域网实验的前置不符，不能倒推原公网NTP失败由电脑VPN造成。
2. LAN-02使用与后来可用2.4GHz不同的SSID；CWJAP返回3（未找到目标AP），本机当时只见该SSID的5GHz信道44。原SSID字节无编码差异。新准确SSID/信道7下连网成功，支持这次接入目标不匹配的解释；不是“密码已被证实错误”，也不证明路由器永久没有2.4GHz。
3. LAN-03为主机脚本把未联网STATUS5错当已有socket；只读30B后停止。纠正后LAN-04通过，原误判和原授权不回填，不因载荷0隐去第4次会话。
4. 当前2.4GHz LAN下的ESP UDP主动收发、UART中断及长度帧提取已取得正向证据，不再只有SEND OK。但该证据不是AP/WAN抓包，也不是公网123或内置SNTP的对照，最初GW FAIL TIME/公网无回复仍不能唯一归给AP、NAT、服务器或SNTP内部处理。

后续有判别力的方案是**另行有界授权**在当前已打通的网络上，对一个固定公网端点/UDP123取得真实合法NTP回复，并保留内置SNTP启用/读回/时间推进证据；若前者通过而后者仍失败，才进一步收窄到内置SNTP路径/版本/配置。当前没有发该公网请求、启用SNTP或重启G3。不能用本次非授时PC回复人工过TIME门禁。

本轮未改C冻结应用/sector3，最后关闭SDK前实测为Flash运行且DISARMED；关闭后未追加独立实板观察。最后确认ESP RAM已连到负责人指定的新2.4GHz网络，SYSSTORE=0。**sector3中的Wi-Fi仍是原配置**，下一次正常G3入口会按冻结配置重连，不能假定本次易失网络切换永久生效。若负责人希望未来G3沿用新网络，必须生成新的受限配置包/CRC/generation并另批sector3事务；本轮没有做。

最终保留的状态为 `CONTROLLED_LAN_UDP_BIDIRECTIONAL_PASS / INTERNET_UDP123_NOT_RETESTED / BUILTIN_SNTP_UNRESOLVED / G3_TIME_GATE_BLOCKED / CPU_ROM_ROOT_CAUSE_UNRESOLVED`。G1测试Backend/TLS未新鲜读取或恢复；预期到期时间已过但真实存活仍UNKNOWN，账号/ACL未撤销。四次执行源、授权快照、所有原始字节/负例/真实退出码和凭据仅存既有受限EFS。17项新工具定向离线检查最终通过，不重复已通过的应用/算法/TLS/UI矩阵。全部进程/主机会话已结束，本轮停止，不再发包。
