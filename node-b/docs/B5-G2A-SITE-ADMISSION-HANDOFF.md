# G2-A实际安装与MEM-AP只读窗口交接

**最新状态：G2-A安装与DISARMED启动PASS；负责人另批的修正版MEM-AP第二个只读窗口PASS。** 第一次桥窗口的SDK错误及离线修正原件保留。安装阶段起点为 `7c535558db0a65cf2a11298fb1db80f445fa2ea2`，第二只读窗口起点为 `d74f9ae7592e6d8d88bd29729b6c2837af4f884c`，均在独立分支 `codex/node-b5-cloud-integration-20261026`。没有写sector3、启动测试服务、发B5START或执行恢复。

## 负责人授权与ESP事实

负责人确认C已由J5上电、开发板USB未连接、使用J-Link，ESP装板且原状未改；随后要求ESP暂不移除并执行G2-A及MEM-AP只读。在说明原G2-A电气隔离条件冲突、安装范围及模块自主联网状态未知后，负责人明确答复**“批准豁免”**。

本次记录 `ESP_isolated=false / ESP_isolation_waived_by_owner=true`。P1 ESP-01 VCC/CH_PD直接连接3.3V的板图事实保留，没有把在板供电写成已隔离。冷态拆除ESP电气附件未批准、未执行；供电/源/电极/BOOT/CAN/参考地未操作。豁免只适用于本次应用安装及只读桥，不自动扩展到sector3写入、恢复或云窗。[独立豁免附件](B5-G2A-ESP-OWNER-WAIVER-ATTACHMENT.md)。

## 实际事务与退出

| 独立事务 | 实际执行与结果 |
|---|---|
| 当前C只读准入 | 一次，worker/监督器/调用者退出0；85次SDK调用，双1MiB及双16B真实读取一致；显式reset/halt/go/目标写均0 |
| G2-A42552B安装 | 一次，worker/监督器/调用者退出0；262次SDK调用；halt/download/reset/go各1；完整Flash、options和身份合格，实际RAM4B全零DISARMED |
| MEM-AP只读 | 一次，worker/监督器/调用者退出1；50次SDK调用；Configure=1、返回0；随后SDK CPUID读返回-1；AP/DP寄存器调用0，显式halt/reset/go、解锁/擦写均0；无重试 |
| 修正版MEM-AP第二只读窗口 | 负责人另批新一次许可，不复用旧`.used`；worker/监督器/调用者退出0，325次SDK调用；原始AP/DP读83、仅传输寄存器写166，SDK/原始读取一致，完整Flash/options前后相同、DISARMED；Configure及显式halt/reset/go/目标写均0 |
| sector3写入 / G1-RESUME / G3 / 实际R-CFG/R-APP/R-CLOUD | 全部0 / NOT_AUTHORIZED / NOT_RUN |

复用了冻结安装和读取实现，不修改原ESP门禁、BIO_V2或固件。新入口 `b5_g2_site.py` 仅提供明确豁免scope和独立只读scope，默认禁用；新增8项门禁检查通过，未重跑原27项writer、3项配置C验证或Host/ARM/TLS/UI矩阵。原始启用文件与`.used`分别独占创建，失败后未重发、重连或复位。

## C实时身份与应用安装

当次J-Link读取的C私有UID与既有C原件完全一致，F407/1MiB，VTref3300mV。安装前VTOR=0，SYSCFG映射0，0地址64B与Flash向量一致；DWT的PC采样在应用区、无HALT/Fault。运行态只读未读取真实PC/MSP，不能以采样冒充真实寄存器。RDP字节0xAA，nWRP=0xFFF；sector3/7/11是本合同逻辑保留区，**不能声称这几个扇区已有硬件WRP锁定**。

| 对象 | 实际SHA256 |
|---|---|
| 安装前C24104完整Flash | `b460d917e1d454fdb0882d1f837d91c606363179b817a3896a1df6897b2dcb98` |
| 唯一42552B候选BIN | `d5b9624b3da1129b4e045d3b2f669c00d2d93cb7379b15293ff143fe9f130683` |
| 安装后完整Flash | `3eaf583a703137b09665da5d2bfd7e860cd3a2208bf659b631d7ee4d0541545c` |
| options16B，安装前后不变 | `52d5979da03bd7be45e385920ec7d5901793bab3f6bc1daa0c1c1997f9e91687` |
| sector3整16384B，前后不变 | `1698c8783b4fbdd1bc7fc5a8641babc7b499b58a65be54e7b36c65c6c5b88313` |
| sector7及11，各131072B，前后不变 | `b5a41c3758763bbec72769fab4a2533bf2db0b6312d93d25a695f9e4b9e02260` |

只安装sector0/1/2整49152B，BIN尾部6600B保留；实际复位后读取真实PC/MSP与新Flash向量匹配，再Go一次，启动运行核验通过，B5状态四字节实读 `00000000`。没有写旧H3配置或用旧24104安装卡覆盖新三扇区候选。安装回执的历史底层B4名称由新入口明确标为 `G2A_INSTALL_VERIFIED_DISARMED_PASS`，不混成CAN或生理验收。

完整字段、真实PC/MSP数值与前后保护区比较见[当前只读](../evidence/B5-G2A-ADMISSION/current-readonly-result.json)、[实际安装](../evidence/B5-G2A-ADMISSION/install-result.json)。当次原件、SDK返回、before/after全片、options、私有身份及恢复包仍在受限EFS；既有24104B恢复原件不覆盖，恢复演练本轮未批准。

## MEM-AP失败的准确位置与原因边界

不是1MiB备份残缺，也不是成功读到不足4B。实际序列为：

1. 新42552B的UID、运行状态、完整1MiB Flash、16B options和DISARMED状态读取成功；Flash与安装后冻结预期相同。
2. `JLINKARM_CORESIGHT_Configure("")`实际返回0。
3. Python求值 `bridge.probe(...)` 的第一个参数，执行SDK `ReadMemEx(0xE000ED00,4,...)` 读取CPUID，实际返回**-1**。
4. 继承的通用包装器将任何不等于请求长度的返回都命名为 `S3_NATIVE_SHORT_READ`；本例应该解释为SDK原生错误，不应解释成少读了几字节。
5. 参数求值已失败，尚未进入 `DapBridge.probe`，AP/DP寄存器读写均0；因此AP索引、IDR、CSW/TAR恢复和原始AHB读取本轮均未取得实板通过证据。

主要嫌疑在**脚本从已连接的高层内存读取切到低层CoreSight配置后，没有验证接口状态便继续调用高层SDK读**。SEGGER官方说明该Configure路径涉及调试接口初始化/切换序列，它不是可任意穿插而假定无状态影响的纯元数据查询。[SEGGER接口说明](https://kb.segger.com/Using_J-Link_Script_Files)、[PyLink官方接口文档](https://pylink.readthedocs.io/en/latest/pylink.html)。

负责人随后要求继续排查再写报告，本轮只追加离线调查：原SDK消息指纹已与DLL静态文字 `CPU could not be halted` 匹配，确认SDK报告过暂停失败，但旧日志没有在途API/时间，不能唯一归属于ReadMemEx或Close，也不能据显式Halt=0宣称SDK内部硬件暂停尝试必为0。冻结DLL的静态控制流显示ReadMemEx与Connect共用检查入口，但当次内部运行分支未观测。详细证据、限制和修正见[原因审查](B5-MEMAP-SDK-ERROR-CAUSE-AUDIT.md)。

这支持审查调用顺序，但**尚未证明**具体是DLL连接上下文、SWD切换或DP/AP状态中的哪一项，不能从一个-1断言根因已关闭，更不能推断CPU进入ROM。Configure前真实观测为Flash运行、VTOR=0x08000000、Fault=0；错误后按卡未再读硬件，当前运行状态未重新确认。实际关闭使用了先前已验证Flash的退出续跑策略，显式Go为0；不把SDK关闭语义描述成“绝无运行状态影响”。

精确返回及执行源码SHA见[桥失败回执](../evidence/B5-G2A-ADMISSION/bridge-readonly-result.json)。实际执行的新入口源码已另存EFS，未在失败后修改代码冒充本次执行版本。所有窗口的成功、失败和原始退出保留。

## 下一步与未完成项

- 当前G2-A实际安装PASS保留，不能因桥失败重复安装或重刷。当前唯一C应用已是42552B，后续不得再把24104B当当前部署。
- **MEM_AP_READONLY_CROSSCHECK_PASS，限第二次获批只读窗口。** 复用已连接上下文、禁止重复Configure的冻结修正版在本机DLL与C板实测通过；原来15项离线检查及开发回执不重跑、不覆盖。新增27条SDK回调均带在途API和单调时间；Connect阶段24条、ExecCommand1条、Close2条，无原生负返回，也未出现上一窗的暂停失败消息指纹。读路径门禁已取得实板证据，不等于raw Flash编程已经验证。
- 冻结专用sector3写入器也存在同样的“Configure后直接SDK读取”模式，原27项替身测试不能替代这次实际失败证据。它的旧SHA和配置包不改，但**不得据旧离线PASS直接启用物理写入**；须先完成这一准入缺口，不在暂停的CPU上自动试错。
- [第二次单次只读卡](AUTH-B5-G2B-MEMAP-READONLY-002-R1.md)已由负责人明确批准，实际执行1次后许可已消费。独立授权、原码、源码及API时序分别归档，见[实测结果](../evidence/B5-MEMAP-READONLY-02/result.json)、[时序核对](../evidence/B5-MEMAP-READONLY-02/API-timing-review.json)。没有复位、重装G2-A或改变供电/接线；不追加第三次连接。实际执行源SHA仍为冻结修正版 `44751b86728c5fb75c6960135c99470d5297d3b83a60d468ec53aafee14a949c`，没有边测边改代码。
- ESP AT/TLS/自主联网状态未查询；云服务当前存活本轮未再核查或启动。历史G1人工MOCK PASS保留，不代表真实B→C→云通过。CPU ROM根因、B5独立冷启动、同窗HR/RR、绝对阻抗和故障注入均保持原未完成状态。

本轮无B固件/算法修改、无源模式/电极操作、无保护分支合并、无Security Gate。第二窗口通过支持当前连接方式在本机有效，但不是严格单变量根因实验：旧日志中暂停失败究竟属于ReadMemEx还是Close仍无法追溯，也不关闭历史CPU ROM问题。SDK正常Close前最后一次硬件观察为Flash运行；Close后没有追加探测，不签独立冷启动或退出后长期运行验收。

交付后停止。G2-B配置写入前仍须核对物理写入器是否已采用本次成功连接方式、冻结相应源码/SHA和必要负例，并另获配置写入批准；本次ESP在板豁免不自动覆盖该写事务。随后G1服务恢复、G3和回滚继续分别批准，不自动启用。

## 2026-10-27追加｜G2-B连接流程离线收尾与第三阶段准备

当前追加只做软件与申请准备。G2-A安装PASS、MEMAP_READONLY_02实际PASS及所有原件不变。本轮实板会话、Flash写入、复位、AT、云服务启动、B5START、恢复均为0。

sector3写入器已采用成功只读窗的已连接SDK流程：禁止Configure，不重连；暂停后IsConnected=1，先完整读取SDK CPUID/Flash头/CR/SR，再做原始MEM-AP交叉核验；退出恢复CSW/TAR并规范化SELECT=0。负返回和非负短读分开记录，SDK消息指纹带在途API/单调时间；AP/DP原生错误锁禁止后续原始清理访问，回调错误也禁止失败清理。仅最终全片/身份、正常向量启动和DISARMED通过后才开启Close续跑。读路径实测证据不冒充raw Flash编程通过。

本次写入器SHA `5464387e61ecbd1d109539996e06648a0e47d0ac601f674a3e1d449a045e0c3d`，旧SHA `39befcee1c7426c0b74222509fbe86759da0f3d4d18521f6729bb95ac2a52107`及历史依赖在原提交/EFS保留。protocol、监督器、planner和42552B BIN均未改。真实配置包15个文件离线逐一校验并重建相等，仍绑定原20cba97d…；没有重新生成配置或修改凭据。

16项定向验证退出0，覆盖真实Engine+MEM-AP+NOR替身的完整写入和反向恢复、提交字最后写、四次全片/四次options独立调用、无连接/身份漂移/暂停后武装变化、SDK错误日志与停止锁、事务专属ESP例外及卡/工具漂移。未重复既有27项writer、15项只读入口、C配置3项、Host/ARM/TLS/UI矩阵。前4次新测试存在替身适配/计数错误，均退出1并保留日志；第5次12项通过，第6次新增授权检查后16项通过。包校验脚本首次因编码名utf8-sig无效退出1，改为utf-8-sig后退出0，未进入DLL或硬件。

| 项目 | 当前裁定 |
|---|---|
| G2-A安装、MEM-AP读路径 | 既有实际PASS，未重跑 |
| G2-B连接流程与真实配置包离线验证 | PASS_OFFLINE；新工具已冻结 |
| raw Flash物理写入 / 配置启动验收 | NOT_AUTHORIZED / NOT_RUN |
| ESP | 保持在板供电，ESP_isolated=false；自主联网UNKNOWN，不发AT |
| G1测试服务 | 最近只读回执为驻留超时停止；本轮未新查、未启动；账号/ACL仍保留 |
| G3真实上云 | NOT_AUTHORIZED / NOT_RUN；ECG60、RR/TEMP INVALID、A OFFLINE、MOCK判据冻结 |
| CPU ROM / B5独立冷启动 / 同窗双有效 / 阻抗标定 / 故障注入 | 原状态保留，不随离线验证升级 |

下一次配置申请只用[配置R3](AUTH-B5-G2B-SECTOR3-001-R3.md)，明确批准一次sector3写入及本事务ESP非隔离例外；不借用安装豁免或旧卡。私有启用模板仍disabled/owner_approved=false/有效期0，现场最新核对项未虚填。恢复单独用[R-CFG R3](AUTH-B5-R-CFG-001-R3.md)，再另批R-APP R2；未演练恢复。

第三阶段准备见[检查表](B5-G2B-TO-G3-PREPARATION.md)及[G3 R3](AUTH-B5-G3-CLOUD-WINDOW-001-R3.md)。实际配置通过之后，服务恢复和G3分别批准，不自动串行执行。G1旧apply会修改ACL/HUP，不能拿它代替只启动两个独立unit的resume-only工具。有限resume-only工具、ESP实机TLS条件和五层联合记录工具完整绑定尚须补齐，现不宣称G3可执行。

新工具/卡/日志/包校验与真实退出见 `../evidence/B5-G2B-CONNECTED-PREP/`。源码原件与私有禁用模板另存受限EFS；无固件、配置凭据、UID明文进入Git。仅正常推送独立B5分支并远端回读，完成后等待分项批准。
