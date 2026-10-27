# B5-002阶段唯一交接｜G3在AT阶段停止，ESP身份补证

## 最新状态｜2026-10-27

最新R3备用模块对照已完成并停止：负责人已确认冷态替换、DIP-8方向及一次正常C RESET，J-Link在C、C J5、B断电、C USB断开；保持P5/P7/115200/固定查询不变。备用B同样只有4字节AT写请求、新RX=0、新UART错误=0，GMR未发送，版本仍UNKNOWN；C身份、完整Flash/options和DISARMED核验一致。见[R3真实回执](../evidence/B5-ESP-GMR-REAL-03/result.json)。原A与备用B都不能据本次结果判定为旧/新或损坏；共同供电/EN/启动/实际串口路径/波特率仍待物理补证，不自动重复查询、改参数或刷模块。

当前所有SDK/串口会话均已结束，R1/R2/R3许可均消费。C保持原42552B及G2-B配置、现装备用B，B断电；G3没有重启。下一步优先取得C P5及P1/P2插座可读丝印的近照，核实共同路由/并接设备；没有额外测量或硬件窗口授权时不继续连接或写UART。

G3 R4已获批并真实执行一次：C复位由负责人仅按一次，完整B5START只发送一次；C约2.078秒后输出GW FAIL AT，联合worker/监督退出1，无T0、300秒正式评价0秒，许可消费，不自动重试或恢复。见[AT停止复核](B5-G3-01-AT-STOP-REVIEW.md)和[真实G3回执](../evidence/B5-G3-REAL-01/result.json)。B保存94份诊断均HR60有效/RR无效、250SPS且无新增ADC错误；云观察CONNECT/SUBACK、Backend健康/MQTT订阅和WSS正常，但记录期间START后Broker实收0、Backend接受增量0，不能签B到云通过。

负责人随后确认C P5路线正确，当前A模块为ESP-01S且灯不亮；尚不能据此判A损坏或AT版本旧。新增GMR查询未刷C/ESP固件：R1入口VTOR=1FFF0000、PC均在ROM，UART写0停止；原件和异常收尾多读的一份ROM快照保留。已修正ROM直接Close，14项新增离线测试通过。负责人另批一次C正常人工RESET后，R2确认C运行Flash、完整镜像/options符合，固定115200 AT写4字节但新RX=0、新UART错误0，未发GMR；收尾完整Flash/options逐字节未变、DISARMED不变。见[R1](../evidence/B5-ESP-GMR-REAL-01/result.json)及[R2](../evidence/B5-ESP-GMR-REAL-02/result.json)，当前AT版本仍UNKNOWN。

根据负责人新的换备用模块指令，已准备[R3单模块对照](AUTH-B5-ESP-GMR-001-R3.md)：A原件保留，备用记B，不先贴旧/新或坏/好标签；只更换模块，P5/波特率/固定查询逻辑不变。新的物理完成附件未齐前执行器保持禁用，不自动再跑原R1/R2/G3。最多一次正常人工C RESET属于本次对照启动准备，仍ROM立即停，不追查ROM根因。替换后AT成功也只能关联模块/插接状态，不能确定A唯一故障原因。

G3失败后的420秒固件STOP行未取得；负责人最初要求先分析，随后已为独立GMR准备确认全暗10秒冷断电，这仅是后续物理隔离证据，不补签G3到期自停。正式云配置、B/C应用、sector3/options、BIO阈值均未改；GMR新增权限仅UART_DR固定字节，不冒称全目标零写只读。历史ROM根因、独立冷启动、同窗HR/RR、阻抗绝对标定及故障注入状态原样保留。

以下为此前检查点；其中“G3未启动/待现场”不覆盖以上最新真实结果。

负责人已批准HW卡一次C只读及G3 R4进入许可，并明确ESP保持在板供电。HW实际首窗已PASS：一连接/关闭、1MiB Flash与16B options各一次，退出0；UID/保护匹配、PC采样均在Flash、VTOR=0x08000000、无HALT/Fault，DISARMED=0。完整Flash及options与G2-B后冻结原件逐字节一致，sector3/7/11未变。显式halt/go/reset/Flash写/AT/B5START均0，未重试；原件仍只存受限EFS，见[真实C准入回执](../evidence/B5-G3-HW-PREFLIGHT-01/result.json)。

当前等待负责人按已批准HW卡完成一次冷态转接、C USB_UART及B J5上电，并回报实际COM和源/电气附件。G3许可已取得，不再重复申请；执行器在现场齐全前保持禁用，B5START仍0。下方“尚待批准/待现场”的描述为此前软件准备检查点，不覆盖本段最新实际进展。独立测试服务本次尚未新鲜查询，不自动启动或恢复。

G2-A唯一42552B应用实际安装PASS；MEM-AP第二只读窗口PASS；G2-B R3首次真实sector3写入PASS，耗时110.641秒，完整Flash/options及DISARMED合格。写后全片SHA `acb33fdd39ecb016ecd848ec25eee051635f56ef8138b577a8590d2734ad687e`，候选BIN及sector3外所有字节未变。

负责人另批G1-RESUME R2后，独立Backend/TLS已实际恢复PASS，TLS CA/SNI、Backend健康和MQTT订阅通过；18775监听、8884未监听，正式服务PID与配置未变。仅两个测试unit各start1，无ACL/HUP/正式环境改写。北京时间11:15:45启动，原6h驻留上限预计17:15:45；测试账号/ACL仍在，未自动撤销。

G3联合取证工具现已完成软件准备，41项定向离线测试通过：真实B原码/过滤后CAN队列映射、Broker原始载荷、实际Backend聚合计数/WSS、单次START及独立420秒监督。完整300秒软件合成夹具逐点核对75000个ECG点和15000个RESP点；改坏波形值或QoS均拒绝。这不是实板或真实云窗验收。默认计划退出0，两个禁用许可CLI负例均按预期退出1，未消费授权。失败原件及历次退出码保留。

[HW准备卡](AUTH-B5-G3-HW-PREP-001-R1.md)、[G3 R4卡](AUTH-B5-G3-CLOUD-WINDOW-001-R4.md)与[现场附件](B5-G3-SITE-ATTACHMENT-R1.md)已冻结；工具、DLL、地址白名单、24个依赖源码及环境SHA见[绑定清单](../evidence/B5-G3-PREP/bindings.json)。实际COM、冷态转接、源/电气完成事实与一次新鲜C只读回执仍缺，私有授权均禁用。未来计划内C人工RESET仅在B/云端观察器就绪后一次，由G3 R4另批，不能现在提前按。

本次软件准备没有连接J-Link/串口或云端、没有发送AT/B5START、没有复位/烧录/改配置，BIO阈值与固件不变。G3 B5START=0，300秒实板云窗NOT_RUN；C最后实测DISARMED，不能冒称本轮重新读到。G1服务本轮未重新查询，17:15:45只是原驻留预计上限，启动前要实时健康和至少625秒预算，不能自行重启。ROM根因、独立冷启动、同窗双有效、阻抗标定和故障注入保留原状态。

最新详细交接见[B5-G2A-SITE-ADMISSION-HANDOFF](B5-G2A-SITE-ADMISSION-HANDOFF.md)，实板配置证据见 `../evidence/B5-G2B-SECTOR3-01/`，服务恢复见 `../evidence/B5-G1-RESUME-01/`。恢复R-CFG→R-APP及R-CLOUD仍各自另批且未执行。

---

## 以下为G0历史检查点

以下“本轮/当前/未授权”均指G0当时；最新进展以上方汇总和各期原件为准，历史不覆盖。

> 本文保留G0阶段结论。负责人后续单独授权的G1-A/HW0/G2-RO实际结果，现以[B5-G1-G2RO-ADMISSION-HANDOFF](B5-G1-G2RO-ADMISSION-HANDOFF.md)交接；本轮G2-A/G2-B/G3仍未授权。

本报告是B5-002唯一阶段交接，不替换历史B4/B5-001原始验收。**G0只读审查已完成；尚不能安装或启动云窗。** 审计详情、真实配置指纹和隔离方案见[B5-G0报告](B5-G0-CLOUD-READONLY-ADMISSION.md)。

## 冻结与已执行

开工远端/本地基线`baa08b850c9bd5e62ace7682a937b9c68423a0fa`，实现`c65fbedce7edf5d822c573ef5cdeb6471d1ae3d5`；本轮源码/文档变更只在`codex/node-b5-cloud-integration-20261026`，不改冻结B5实现。交付提交由本文件所属Git提交及后续远端取回回执定位，避免把自引用SHA写成不可实现的固定值。

唯一42552B BIN SHA `d5b9624b3da1129b4e045d3b2f669c00d2d93cb7379b15293ff143fe9f130683`；ELF SHA `3c726f61f76eadac4909826203ca84dee65521aec448ad477ddca0c3c58795d8`。B39948B/C24104B冻结原件及320份不可变归档复核一致，没有重建/烧录或重新跑现有Host/ARM、本地TLS模型链路、七页UI。

本轮实际动作：只读SSH进程/有效配置路径/源码/ACL/认证元数据/TLS证书；TLS握手无MQTT CONNECT；磁盘恢复布局与保护区比较；19项恢复校验和11项权限拒绝测试，退出0。两次工具前置失败退出1保留，随后成功回执退出0。G0无COM/J-Link/ESP操作、无MQTT发布、无云写入/reload/restart、无Security Gate。

## 真实差异及下一步

1. 8883及外部TLS1.2可达，证书有效；8884未监听。但B5账号/ACL不存在，Backend白名单无GW-B5-001，隔离测试入口未部署。正式服务均保留。
2. 实际Backend Hub缺少已审B5的会话代次隔离，不能仅加白名单。优先专用Backend＋loopback TLS/WSS＋SSH观察，不新增公网端口；公网WSS直达备选需另批独立测试域名/证书及443 SNI站点。
3. 当前C sector3的336B记录CRC有效、B5身份不匹配，不能直接启动或改宏绕过。应用跨sector0/1/2，旧24104B卡不能套用；配置sector3另卡提交，committed最后写，余16048B保留。
4. G0已按C24104历史全片重算离线包，但**FRESH_READBACK_REQUIRED**：须另批新scope的一次非侵入C双1MiB/双16Boptions与身份/配置读回，然后重新绑定包，不能把G0复制/内存重算当新鲜双读。
5. 默认回退目标是本次新鲜C24104＋原sector3。应用回退、配置回退、云专属资源撤销分别批准；恢复历史H3或恢复正式联网均不是默认许可。

[分卡索引](B5-G0-SPLIT-AUTHORIZATIONS.md)：G1云配置、G2-RO新鲜读回、G2-A应用、G2-B配置、G3单次420秒云窗及三个独立回滚对象，全部`enabled=false / owner_approved=false`。当前G2新读回scope/配置写入器仍缺离线验收绑定，卡片不代表执行工具已准入。负责人不批准下一阶段时保持现状。

## 分项裁定

| 门禁 | 当前裁定 | 补证 |
|---|---|---|
| G0 | **READONLY_REVIEW_COMPLETE / ADMISSION_BLOCKED** | 不代替后续许可 |
| B5_SOFTWARE_OFFLINE | **PASS，沿用已裁定** | 本轮不重跑 |
| C_INSTALL | **NOT_RUN** | 新鲜原件、三扇区安装独立批准和实读 |
| SECTOR3_TEST_CONFIG | **BLOCKED / NOT_RUN** | 测试凭据、完整sector3包、专用写入器、独立批准 |
| BROKER_ACL_AND_TEST_BACKEND | **BLOCKED** | 专用账号/ACL/服务/入口未部署；仅TLS子项通过 |
| 300S_E2E | **NOT_RUN / NOT_AUTHORIZED** | G1/G2通过后另批单次B5START；45秒预热＋300秒共同评价 |
| REAL_ROLLBACK | **NOT_RUN** | 新42552B和sector3各自实际恢复证据，不能借旧24104演练 |
| B4_ALGORITHM_REGRESSION | **既有ECG60及独立RR15各自PASS；B5联网负载实板NOT_RUN** | B未改阈值/寄存器，不以云传输代替生理有效性 |
| ROM_ROOT_CAUSE | **UNRESOLVED** | 保留历史原件；本轮不主动复位排查 |
| B4_INDEPENDENT_COLD_BOOT | **NOT_VALIDATED** | 观察/计数差异保留，不签新候选通过 |
| SIMULTANEOUS_HR_RR | **NOT_VALIDATED** | 不同模式/导联两窗不拼成同窗PASS |
| ABSOLUTE_CALIBRATION | **IMPEDANCE_AMPLITUDE_NOT_CALIBRATED_INSTRUMENT_REQUIRED** | 名义ECG参考/增益非绝对标定，ΔΩ/Z0/Zpp仍未知 |
| CONTROLLED_CAN_FAULT_RECOVERY | **NOT_RUN** | 需另批故障注入及恢复窗 |

完整工具/快照/测试/授权卡SHA见[冻结清单](../evidence/B5-G0/G0-bindings.json)。原件、负例与设备身份只存受限EFS，Git不含Flash/options/UID/凭据。正常推送及独立远端取回的实际结果在[交付回执](../evidence/B5-G0/git-delivery.json)记录。未启动三板集成、云端发布或保护分支合并；本轮结束，等待PI分别决定后续G1/G2/G3。
