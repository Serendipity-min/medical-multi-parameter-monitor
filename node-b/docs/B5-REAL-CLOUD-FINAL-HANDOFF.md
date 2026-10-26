# B5-002阶段唯一交接｜G0完成，真实云窗尚未授权

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
