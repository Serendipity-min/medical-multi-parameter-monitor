# B5三路分别实测与传输｜R2批量申请

## 已完成与范围区别

B温度40928B已按R1一次安装通过，实测全片`ceebec5a91835aed3cb70c683fd8de5142e5ba59a2163a1968cec182018b48ae`。15秒独立只读新增69个有效温度帧、串口/校验/溢出新增0，物表To约26.86–27.07℃、环境Ta约26.10–26.20℃。B BIO_V2原源码SHA未变；未启用温度的构建仍逐字节等于历史39948B。R1安装与只读许可已消费，不再写B、不再执行B Reset/Go。

R4原300秒结果仍NOT_PASS（3条标量REPLAY、68点ECG缺口）。本批量是负责人新增的ECG、温度、RR分别传输范围，不把原TEMP INVALID判据改成PASS，也不签同窗ECG/RR有效。历史CPU ROM根因、绝对阻抗及温度标定等独立遗留不消除。

R1对未来C“还原测量时刻”的描述在此澄清：原CAN标量时间是节点报告的整数秒UTC锚，不能直接减帧龄伪装精确测温UTC。新C保留该报告UTC，按保留字帧龄撤销过旧TEMP；模块UART接收tick、原始字节和帧龄另行归档。温度源匹配按真实原帧To、校验、报告秒锚−2500ms至+1000ms区间核对，允许同值多个源帧候选，不声称唯一物理帧身份或绝对精度。本阶段仅非人体物表工程值，非医用补偿体温。

## 对象一：C一次安装与只读

- 新C 43036B，BIN SHA256 `28af9628f428403cc479293adf748e57b68c82a8444458a5ca8de43f311f36d4`；ELF `aecc154766b4c5cc46f339acf22d19890979e51a94c936b524baf6fb882491c1`。
- 当前C42880B实测全片`45274e8ab217777986f666c0a386926d532c5fde2199d86ccd7ffaaed202fc9c`；gen5不动。新C仅让B五路遥测使用原16槽FIFO，保留真实过载/断链REPLAY，增加波形清批原因计数，接收TEMP帧龄但不改变ECG/RR阈值或精度门。
- `B5_C_EGRESS_APP012_UPDATE`一次≤180秒：新鲜双完整Flash/options、身份/保护、正常Flash及DISARMED精确匹配后，Halt≤1、sector0/1/2共49152B写≤1、正常Reset≤1、向量匹配后Go≤1；双完整after/options、所有尾区及DISARMED核验，失败不重试。sector3/options/ESP NVM均不写。ESP在C板供电例外随本次对象明确批准。
- 独立C只读预检一次≤90秒，显式Reset/Halt/Go/写均0。完整Flash/options、私有身份及新ELF符号绑定通过才允许后续。
- 安装前冷态将J-Link B→C：B/C J5关闭、C USB及J-Link电脑USB拔下，全暗10秒；整只排线转C；只恢复C J5与J-Link电脑USB，B断电、C USB_UART断开。通过后按相同步骤冷态回B，再恢复C J5及USB_UART、B J5，观察屏后接J-Link电脑USB。由负责人在工具提示时一次操作；不移动BOOT/CAN跳帽。

## 对象二：必要时仅恢复既有独立测试unit

先只读核对正式服务/PID、配置/ACL/权限、测试入口与原六小时预算。若两个已知独立测试unit已按RuntimeMax到期停止，且原冻结条件全部一致，可使用既有G1-RESUME R2范围新事务：Backend/TLS各start≤1，300秒硬限；不改配置/ACL、不HUP或重启正式Broker，不新增公网端口。仍在运行但预算不足时不擅自重启，等其原定到期；不以缩短业务观察绕过预算。各次G3前真实TLS/Backend/WSS就绪且剩余预算≥805秒。测试账户不自动撤销，不能宣称已清理。

## 对象三：三个独立有限云窗

独立`B5_SEPARATE_CHANNEL_CLOUD_WINDOW`三事务，固定顺序ECG60→TEMP_OBJECT→RR15；每个profile仅一次C人工RESET及一次B5START，合计各≤3，不复位B，不重发失败窗口。三份独立授权/输出目录、工具/DLL/恢复包/SHA及现场附件绑定，不用一个无限制scope。

共同边界保留：未START人工准备300秒，复位后回报30秒、共同就绪60秒、45秒预热＋300秒评价＋15秒收尾、420秒业务硬停、419–422秒STOP实见及20秒被动观察；B250SPS不中断，ECG100@250/RESP50@50、2048B、QoS语义、同会话、旧数据STALE、A OFFLINE及MOCK/synthetic不变。B原码/实际队列、UART源环、C诊断、Broker实收、Backend实际接受计数与WSS逐值核对；不以ACK或SEND OK代替实收。B每窗一只读联合连接，Go/Reset/Halt/烧录0。

| 窗口 | 源/接线 | 稳态与传输判据 |
| --- | --- | --- |
| ECG60 | 普通ECG60/1.0mV，R→RA、L→LA、F→RL/N、LL空；电池无充电USB | HR58–62全稳态有效，RR真实INVALID；ECG≥74250源点、无序列缺口、有效100点批及WSS批次实见；HR≥295条。TEMP独立观察，不借其有效性冒充临床体温 |
| TEMP_OBJECT | 保持上述ECG设置/接线，GY-641V3 PC10/PC11，保持同一非人体被测物，无标准参考源 | TEMP≥295条；协议/帧龄有效，真实UART帧To与Broker值一致，Backend/WSS同会话同值；工程域0–100℃。不要求等于36.5、不计算无真值准确率；To/Ta/Bo及原帧保留 |
| RR15 | 独立呼吸15bpm、1.5R、波形周期30bpm、窒息0s；R→RA、L→LL/F、F→RL/N、LA空；电池无USB | RR14–16全稳态有效，HR真实INVALID；RESP≥14850源点、无序列缺口、有效50点批及WSS实见；RR≥295条。阻抗幅度仍非Ω标定 |

每窗≥590份B稳态诊断、≥2900份WSS、≥58条C诊断；C/B新ADC/CAN/UART丢失、过期、队列丢弃、TEC/REC/BOFF及MQTT失败不得新增；真实历史REPLAY不重标MOCK。ECG/RESP原码映射与原±2ms名义网格门保留。温度UART环至少两份一致字节才归入源证据。

ECG→TEMP不用改源/改线，仅按工具提示独立C RESET一次。TEMP→RR由负责人冷态关闭B J5、拔B端JTAG并关闭SKX，确认B/模块/屏全暗后，仅将黄L由LA移至LL/F，红R和绿F不动；按参数设定电池源，B上电观察后接回JTAG。C供电/USB/CAN/独立地不动；不短接LL/RL、不把RLD接地、不使用人体。没有参考源则只记录上述非人体测量与工程传输。

ROM/HALT/未知、漂移、保护/原生错误、电气异常即STOP_TARGET，本批量不包含额外Reset/Go/重刷恢复。普通软件失败继续安全离线调查，旧窗口NOT_PASS及START消费记录保留；不能改变原门限重判成功。

应用/配置/云恢复均仅备妥，本卡不执行R-APP/R-CFG/R-CLOUD；B回39948、C回42880/42552/C24104及正式联网分别另批。本批量通过后才集中提交数据与唯一交接；不改正式GW-C-001、保护分支、算法阈值或Security Gate。
