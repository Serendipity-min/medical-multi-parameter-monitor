# B5快速桥公网NTP通过及gen5/G3准备交接

2026-10-28；独立分支`codex/node-b5-cloud-integration-20261026`。本轮从`e992e04e2f82b3fc8e54ae2471b82bbaf1b7e91c`继续，仅消费负责人新批准的一次180秒快速桥单包窗口；之后全部工作为离线准备。

## 实际裁定

| 对象 | 本轮结果 | 证据边界 |
| --- | --- | --- |
| 快速桥新鲜公网NTP | `FRESH_PUBLIC_NTP_PASS` | 一次连接、一个新nonce、48B请求/48B回复；原完整区间595ms≤1000ms；同一冻结C判定函数通过 |
| SNTP正常启停/配置读回/时间推进 | 保留前轮PASS | 本轮不重复启用SNTP；本轮入口确认已停，退出清理通过 |
| gen5配置及回退包 | `OFFLINE_PACKAGE_PASS_PHYSICAL_WRITE_NOT_RUN` | EFS生成并逐字节重建；不是新鲜实板读回、安装或恢复演练 |
| gen5写入器及G3引用适配 | 离线PASS | 新独立scope、默认禁用；79项相关Python测试及3项C记录校验通过 |
| gen5真实sector3写入 | `NOT_RUN` | 无新Flash/sector3许可；最后已知实板仍为B5应用42552B＋gen4 |
| G1测试Backend/TLS当前状态 | `UNKNOWN` | 本轮未连接云服务器、未启服务；账号/ACL并未因驻留到期自动撤销 |
| Broker→Backend→WSS G3 | `NOT_RUN` | 本轮未发送B5START，不能以NTP回复或历史G1人工MOCK替代真实链路验收 |

## 本次现场证据

快速桥使用已冻结的命令计划、已成功ESP DNS回复绑定的固定公网目的和新请求nonce，仅调用一次UDP发送；未切Wi-Fi、未启SNTP、未改接线，未重发。返回包originate与本次nonce一致，LI、mode、stratum、时间字段及同一`sntp_sample.h`判定通过。

完整门仍从**CIPSEND开始前到完整CIPRECVDATA回复观察结束**，595ms是保守主机区间，不是直接测得的线上RTT。未用较短子区间替代原门，也未设置MCU系统时间。前一窗口2578ms不通过1000ms的失败、453ms局部取证及首次SYSSTORE ERROR全部保留；本次是另批新窗口，不能倒改旧结论。

1519次SDK调用，预算15469；原生负返回0。socket关闭、CIPSTATUS读回及接收模式由1恢复0均通过；SNTP保持停止。调用者、worker、监督器真实退出码均0，`cleanup_verified=true`、`Close_completed=true`。入口及退出VTOR均`0x08000000`，PC采样位于Flash，Fault为0、DISARMED为true；未出现本窗口ROM/HALT。**Close后运行状态未额外观察，仍为UNKNOWN**，不以Close成功签发独立启动或CPU根因结论。

本轮Reset/Go/Flash/sector3/B5START均0，不重复读UID、全片或options。原始AT回复、48B原码、完整SDK原生返回及单调时钟、授权消费、监督器和调用者回执均在既有受限EFS；34个实际执行绑定源码逐个核对并封存。实测后共享工具适配的SHA另列，不冒充本次执行版本。

公共脱敏证据目录：`node-b/evidence/B5-G3R6-FAST-01/`，包括`result.json`、`timing.json`、`executed-source-bindings.json`。私有位置通过本机忽略文件`node-b/build/b5-g3r6-fast-pointer.json`和`b5-gen5-offline-pointer.json`查找；不在Git存储地址、SSID、口令、UID或原始配置。

## gen5的最小变更及恢复

配置来源是既有G2-B写后双全片/options相同的gen4原件，以及已成功入网/授时的私有Wi-Fi引用。本次离线先确认这两份历史双读与模板逐字节一致，再生成gen5。**它仍需下一次写入事务在同一连接中重新双读真实Flash/options并匹配后才能解锁**；历史PASS不当今天现场附件。

336B记录仅修改SSID、Wi-Fi口令、generation 4→5和CRC；MQTT主机/账户/Client ID、测试业务身份、minimum_epoch、应用及配置尾部16048B全部原字节保留。options、sector7/11不变，Vref及BIO_V2参数不涉及。直接使用候选C校验函数检查gen5已提交有效、未提交无效及gen4有效，三次退出均0。

| 原件/模板 | SHA256 |
| --- | --- |
| 未改的C候选42552B | `d5b9624b3da1129b4e045d3b2f669c00d2d93cb7379b15293ff143fe9f130683` |
| gen4全片before | `acb33fdd39ecb016ecd848ec25eee051635f56ef8138b577a8590d2734ad687e` |
| gen5全片after模板 | `a5239d616523621593b5e76fd70212aa199e72603b85e359492d642448fff528` |
| gen5完整sector3 | `25ad0fab2d6c3ed65f78021db4fc81dd0b29e9f89411ffb9946d74eb136f4878` |
| gen5已提交336B记录 | `c7031c8f1a16dadd8dd19ca102749773e01787dbdaa1121d7a53ee41fac645aa` |
| options原件 | `52d5979da03bd7be45e385920ec7d5901793bab3f6bc1daa0c1c1997f9e91687` |
| B5应用＋原gen3配置中间目标 | `3eaf583a703137b09665da5d2bfd7e860cd3a2208bf659b631d7ee4d0541545c` |
| 接收B5前C24104完整检查点 | `b460d917e1d454fdb0882d1f837d91c606363179b817a3896a1df6897b2dcb98` |

`b5_gen5_writer.py`独立支持三个scope：`B5_GEN5_WIFI_WRITE`、`B5_GEN5_REVERT_GEN4`、`B5_GEN5_RCFG_ORIGINAL_GEN3`。均使用已验证MEM-AP连接流程、SDK原始DAP交叉核验、扇区提交字最后写及前后双全片/options；每对象一次180秒，erase/commit/Halt/正常Reset/向量匹配后Go各≤1，无自动重试或恢复。原3↔4入口没有获得5的权限。

三个配置授权模板、HW及G3模板已经绑定包、工具和本卡SHA，但全部`enabled=false; owner_approved=false; expires_unix=0`，无新`.used`。现场附件未知值不填true，ESP在板非隔离例外仍须在每个实际写入/恢复对象分别批准。G3工具新增gen5包与**实际安装PASS、完整after SHA及成功Close回执**门；未写入时不能用模板通过。

恢复分两类：gen5→gen4只退测试配置；完整原部署收尾应gen5→原gen3，再单独R-APP恢复sector0/1/2到上述C24104。**C24104不是历史H3**。旧R-APP要求ESP隔离，本次在板联网许可不覆盖它；须另批冷态移除ESP或完成该恢复器在板例外适配，否则保持BLOCKED。部分写失败不符合完整before时不得套用这三个正常转换scope。

## 离线验证及真实失败

- gen5新增11项通过：最小字节变更、完整重建、默认禁用、独立scope、当前现场及ESP例外、时间PASS回执、代次与镜像、提交字最后写、两类逆转换、漂移/超时/损坏负例、监督器选择新入口、G3真实安装门。
- 既有sector3写入器受影响回归27项及G3联合工具41项通过。未重跑旧Host/ARM、TLS、UI、算法六窗或全片现场矩阵。
- 首轮77项中4项旧夹具失配保留退出1：FakeLink缺少IsConnected、旧卡SHA缺失、原始DAP错误锁存后仍期待继续调用；修正夹具后一次旧ESP错误预期仍退出1，改为当前明确的对象级例外预期后通过。未为测试通过放松实际设备门禁。
- 封存公共测试日志及精确工具SHA见`tests.json`和`gen5-offline-manifest.json`。所有真实配置/完整镜像仍在EFS，未进入Git。

## 下一轮最少批准及停止位置

统一审批草案为`node-b/docs/B5-GEN5-AND-G3-OBJECT-AUTHORIZATION-DRAFT.md`，各对象独立，当前不执行：

1. **gen5实际写入**：批准一次上述180秒对象及ESP在板供电例外，补齐一次当前现场事实；同事务实时身份/保护/全片/options/运行状态通过才写。ROM/HALT/漂移即停，不能自动复位后重跑。
2. **云就绪**：独立只读确认隔离Backend/TLS驻留及正式服务不变；若过期，再独立批准既有两个测试unit各start≤1，不改正式ACL/Broker/Backend。G3要求剩余驻留至少625秒；当前不能宣称服务可用。
3. **HW及G3**：真实gen5安装PASS后，独立C只读准入；再按一次冷态步骤转J-Link到B、接C USB_UART、B上电并冻结实际COM/源。准备完成后仅按单独G3批准，计划内C RESET≤1、8B `B5START\n`≤1，300秒评价/420秒硬停，ECG60/1.0mV、HR58–62、RR/TEMP INVALID、A OFFLINE、MOCK/synthetic及所有既定数量/时效判据不变。必须真实取得Broker、Backend及WSS同session实收。
4. **每项恢复另批**：R-CFG、R-APP及R-CLOUD分别绑定，不把故障清PG/锁Flash当原件恢复，不把服务到期当账号撤销。

现在不需要转接、上电、切源或再复位。本轮仅新增一个公网包；后续物理步骤只在对应对象批准并就绪后一次说明。CPU ROM根因、独立冷启动、ECG/RESP同窗双有效、阻抗绝对标定、CAN故障注入均保持原状态。未改算法阈值、固件应用、正式云环境或保护分支，未启动Security Gate。
