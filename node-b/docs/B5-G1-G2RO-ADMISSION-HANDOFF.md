# B5 G1-A / HW0 / G2-RO 联合阶段交接

**G1-A真实云测试入口通过；C新鲜双备份已取得。没有安装42552B、写sector3或执行B5START。** 两条工作流分别执行和记账，Git由主执行者顺序提交；本轮基线`bdc71313c2c6ebff056d4aa5ffdda9a9b334ea7c`，唯一分支`codex/node-b5-cloud-integration-20261026`。

## 实际事务、来源和退出

| 事务 | 次数与真实结果 |
|---|---|
| HW0 | 一次负责人目视回复；两板J5、ESP装板/AT未知、原接法不变、A/INMP441/TTS断开、SKX电池ECG60。屏幕刷新/EN未明确的字段保留NOT_OBSERVED |
| 独立冷态转接 | 另行获得负责人明确批准及完成回报；关B/C/J-Link USB与C USB、等10秒后探针B→C，仅C恢复J5，B断电、C USB断开；不改变CAN/地/BOOT/电极/ESP |
| G2-RO窗口1 | 原授权一次，退出**1**。身份匹配、VTref3300mV，但VTOR=`0x1FFF0000`，DWT采样`0x1FFF3844/0x1FFF36A6/0x1FFF3848`，按`C_RO_ROM_STOP`停；双Flash/options均0；未启用Close续跑；原件保留 |
| G2-RO窗口2 | **负责人随后主动复位C并明确要求重新读取**，使用新的独立一次授权/目录，未复用已消费许可；worker/监督器/调用者退出**0**，双1MiB与双16B均实际SDK读取、不同文件、完整比较一致 |
| G1-A云部署 | 一次，worker/监督器/SSH退出**0**；正式Broker HUP **1**，新Backend/TLS各start **1**；25.70秒内Backend mqtt_connected就绪；未重启正式服务 |
| G1-A独立冒烟 | 一次≤120秒，退出**0**。6条人工MOCK夹具真实Broker→Backend→SSH隧道WSS对应；两个否定发布收到MQTTv5 PUBACK `0x87` |
| 应用安装/sector3写/实际回滚/G3 | **全部0 / NOT_AUTHORIZED / NOT_RUN** |

窗口2工具仍显式reset/halt/go/目标写均0，85次SDK调用；操作者在窗口前的人工复位独立记账，次数未由回复细分，不冒充工具复位或自动重试。此前窗口44次SDK及错误退出1不覆盖。只读观察无法区分ROM发生于冷启动还是调试器介入，**不归因、不宣称修复**。

## 云端真实可用性与驻留状态

G1使用已审B5 Hub/会话代次隔离代码和冻结Web制品，独立`b5-monitor`无登录OS角色、独立Backend/令牌/日志、独立Unix socket和TLS反代。仅`127.0.0.1:18775`监听，原正式nginx/Backend/Hub/AI/P6不改，不新增公网端口，8884未监听。独立nginx pid/lock/五类temp目录均隔离，未使用共享正式temp目录。

真实账号`b5-gateway`只写`mpm/v1/GW-B5-001/#`，`b5-observer`只读该namespace；原ACL/password_file字节前缀、属主/权限保留，完整备份已在服务器root受限目录和本机EFS核验。新ACL SHA `71a311363832b2f656137aed64bc929c543bc07b653991538d7a9b4f9d7ac4c3`；本轮部署r2包SHA `dcee1658be5ce4db2531975069441444a0f50078828321a3e978a8352b520db0`。正式四服务PID、活跃状态、未涉及修改的配置SHA及正式Backend健康保持；Broker未停止/重启。原r1准备包因共享temp目录风险修订，保留但从未执行。

实际正例为MQTT3.1.1、6条非保留QoS1人工生成MOCK/synthetic：Gateway/Node-B ONLINE、HR60 VALID、RR/TEMP INVALID、100点ECG。Broker观察者逐字节实收6条，Backend接受+6/拒绝+0，WSS会话/内容一致且A OFFLINE。不是ADC原码、C固件传输、QoS0实物负载或G3 300秒证明。负例两用户各一次，仅冻结的`GW-B5-DENY-001`非正式命名空间，实际PUBACK135明确拒绝；未向GW-C-001试探。发布者无read授权来自静态ACL，未把未做的订阅读取负例签PASS。

WSS来自**真实云端TLS经SSH本地转发**，CA/SNI/Origin均校验，私有域名/URL/令牌不放Git；准确入口和访问材料位于G1 EFS的`test-entry-and-lifetime-private.json`、`test-credentials-private.json`，本机忽略指针`node-b/build/b5-g1-private-pointer.json`定位。当前无长期本机隧道或测试客户端驻留，需观察时另在批准窗口建立。没有宣称公网WSS直达或重新跑七页浏览器测试；HTTPS首页字节与冻结B5制品匹配。

独立Backend PID39883、TLS PID39886在末态仍active，`Restart=no`、无自动发布；最大驻留6小时，预计**北京时间2026-10-27 01:59:19**自动到期停止。账号/配置不会自动撤销，R-CLOUD本轮未授权/未执行；下一轮必须先核存活/到期状态，不自动重启服务。应急回退准备见[独立R-CLOUD卡](AUTH-B5-R-CLOUD-EMERGENCY-001-R1.md)，存在原件/方案不等于实测回滚。

## C新鲜双备份与安装/恢复包

| 项目 | 本次实际核验 |
|---|---|
| 全Flash | 两次各1048576B，SHA均`b460d917e1d454fdb0882d1f837d91c606363179b817a3896a1df6897b2dcb98`，与24104B原件逐字节相同 |
| options | 两次各16B，SHA均`52d5979da03bd7be45e385920ec7d5901793bab3f6bc1daa0c1c1997f9e91687` |
| UID/容量/保护 | C私有身份前后及既有原件一致，F407/1MiB、RDP/Flash状态合格；UID只在私有身份原件 |
| 当前运行观察 | VTOR=0，0地址别名与Flash向量相同；末态DWT采样`0x08004AC2/0x08005244/0x080018EC`；运行态未暂停，真实PC/MSP **NOT_OBSERVED**，不以采样冒充真实寄存器 |
| sector3 | 两份各16384B SHA `1698c8783b4fbdd1bc7fc5a8641babc7b499b58a65be54e7b36c65c6c5b88313`；336B头/CRC/committed有效，B5身份不匹配 |
| sector7/11 | 两区各双131072B，相同SHA `b5a41c3758763bbec72769fab4a2533bf2db0b6312d93d25a695f9e4b9e02260`；字节保留不等于宣称硬件WRP已锁 |
| 唯一待审C BIN | **42552B**，SHA `d5b9624b3da1129b4e045d3b2f669c00d2d93cb7379b15293ff143fe9f130683`；实现源码仍`c65fbedce7edf5d822c573ef5cdeb6471d1ae3d5`，未重建 |
| 新鲜app包manifest | `3782fc9caa0f921cc51001191df0ac90e2633710e89f56bae017d2e3d35e73fc` |
| 实际新鲜来源绑定 | `f614271c83b8b6f11992531537ea49ab6434f6f2a7c2481f1cced7ae55f1cad1`，关联两次SDK原码、原件、监督器与授权 |
| 安装应用后完整预期 | `3eaf583a703137b09665da5d2bfd7e860cd3a2208bf659b631d7ee4d0541545c`；sector0/1/2，原尾6600B保留 |
| 默认回退 | 本次新鲜C24104完整1MiB及其原sector3；未实际擦写或演练恢复，不自动恢复历史H3 |

manifest与G0计算同SHA说明字节相同，**不能单靠相同manifest证明本次采集**；新鲜证明另绑本次真实两个ReadMemEx返回及不同文件。纯字节规划器本身的`independent_acquisition_proven=false`未篡改，额外来源绑定承担实际采集证明。

窗口正常Close使用已验证Flash才启用的退出续跑策略，显式Go0不等于SDK无隐式状态影响；ROM窗口未启用。Close后未再开第三个调试连接。当前保持：J-Link在C、C由J5供电、C USB断开、B断电；没有自动转回或上电B。

## 下一轮最少批准及真实缺口

1. [G2-A新鲜绑定卡](AUTH-B5-G2A-FRESH-001-R1.md)：42552B仅三扇区安装一次，独立应用写入批准。安装器要求ESP隔离，目前ESP装板/隔离未知，须先批准并完成准确冷态电气操作，不能填造true。应用安装不能同时批准恢复、重装或配置写。
2. [G2-B方案绑定卡](AUTH-B5-G2B-SCHEME-BOUND-001-R1.md)：配置编制/预审与物理写入必须在明确范围内分别准备。已绑定新鲜sector3、G1专用凭据来源、312＋24B布局、代次3→4、CRC/committed最后、16048B尾部及恢复组合；纯离线规划器14项检查通过。**本轮未生成含真实口令的新336B/整sector记录；实际记录/写后全片SHA为null，物理配置写入器尚未实现/验收。** 不可仅因G1/G2-RO通过而立即写配置；须先冻结真实配置包/专用写入器/监督器和负例，随后PI单独批准G2-B。
3. G3仍单独批准：G2-A/G2-B均实际通过且ESP AT/CA/SNI、源/接线/安全停机与云服务存活核验后，才可一次B5START。45秒预热＋300秒共同评价＋15秒尾段，420秒硬停的原门禁保留。本轮未向C/ESP发送联网或AT命令，模块自主联网状态未核实；没有实物B→C→云数据或故障注入。

下一轮前的真实PC/MSP及Flash入口证据，应在获批G2-A正常暂停/复位策略内取得；本轮不为补该字段擅自halt。ESP版本的历史P分支回执不替代本机当次版本事实。

## 证据、失败与残余状态

G1实际回执：[汇总](../evidence/B5-G1/execution-summary.json)、[末态](../evidence/B5-G1/final-readonly.json)。G2：[首次ROM停止](../evidence/B5-G1-G2RO/G2RO-result.json)、[用户复位后新窗](../evidence/B5-G1-G2RO/G2RO-owner-reset-02-result.json)。新工具/监督器26项、sector3纯离线14项、G1门禁9项通过；原合成夹具/bytearray实现失败的退出1及原始回执保留，G1未执行的原准备包也保留，不冒充实板/云故障。没有重跑已验收Host/ARM、本地TLS模型链路和七页UI测试。

全部实板/配置/口令/UID/原始云payload与SDK日志只存不同受限EFS事务目录，Git仅代码、脱敏SHA/布尔/真实退出。来源/卡片/工具冻结见[本轮清单](../evidence/B5-G1-G2RO/bindings.json)，Git远端独立取回见[交付回执](../evidence/B5-G1-G2RO/git-delivery.json)。

| 门禁 | 当前裁定 |
|---|---|
| G1-A | **PASS，人工MOCK云入口冒烟范围** |
| HW0 | **COMPLETE，未知项照录** |
| G2-RO | **新鲜双备份PASS；前次ROM停止保留；真实PC/MSP未读** |
| G2-A / G2-B / G3 / 实际R-APP/R-CFG/R-CLOUD | **NOT_RUN / NOT_AUTHORIZED** |
| ROM_ROOT_CAUSE | **UNRESOLVED**，人工复位恢复不是根因关闭 |
| B5独立冷启动 / 同窗HR/RR / 绝对阻抗幅度 / CAN故障注入 | **沿用未通过/未验证状态** |
| 既有ECG/HR、独立RESP/RR名义速率验收 | **原范围保留，不合并同步PASS** |

无BIO_V2阈值/ADC寄存器/冻结固件修改，无P4/main/H3/P6等保护分支、Security Gate或正式三板集成。正常推送独立实验分支并取回核验后停止，等待PI分别决定应用写入和配置准备/写入。
