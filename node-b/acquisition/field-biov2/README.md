# BIO_V2 B2-0 采集准备

profile.offline.json 是本轮真实BIN/ELF/符号及ARM offsetof绑定的**离线计划**，没有硬件读取后端，不能交给既有acq.py/capture_v2.py执行。设备绑定全部null；实际UID、全Flash和options只能在受限目录内建立，并另行审查真实采集器。

离线生成（输出文件独占创建，存在时必须使用新的名称保留历史）：

```text
python node-b/tools/field_profile.py --arm-build <本轮ARM目录> --abi-receipt <本轮ABI回执> --output <新profile路径>
```

此命令只读本地构建并写离线JSON；既有audit_biov2_identity.py负责ARM布局与旧profile拒绝。field_profile.py进一步检查源、工具、实际文件、SRAM边界和精确ABI。check_observation仅验证外部记录的元数据一致性，不连接设备、不授予权限，也不保证原码和逐样本诊断原子性。

受限运行包须沿用通用采集协议的session/channels/condition/reference/sample/state/manifest/index结构，新增并明确下列字段：

| 字段 | 要求 |
|---|---|
| run/sample/condition/repeat/boot/segment | 每轮唯一；跨启动/序号回退不合并 |
| provenance | ENGINEERING_NONHUMAN，真实采集与OFFLINE_REPLAY分开 |
| source | 型号/固件/模式/电极/供电/参考值/误差依据；未知null |
| device/firmware/tools | 受限设备manifest SHA、本轮BIN/ELF/symbol/采集器/profile SHA |
| register evidence | 初始化SPI回读与采中观察时刻分开，GPIO按mask；不冒称即时回读 |
| raw observations | 原始24B槽、IO时刻、观察次数、所有版本及冲突；不能多数投票掩盖冲突 |
| diagnostics | raw/filtered、valid/reasons、峰计数/末周期/质量；live非原子标OBSERVATIONAL_ONLY |
| derived per-frame | 冻结原码上同源回放，标REPLAY，不冒充实板实时数据 |
| stop/end | STOP请求、最后稳定窗口、halt确认、同份RAM的head/slots、恢复确认和实际目标末态 |
| quality/reference | 完整性、信号质量、参考、准确度分别裁定；没有真值不算准确率 |

建议读区：活动slots 3072B，前2KB状态，独立120B g_bio_v2（旧工具漏读）；最终确认halt后保存128KiB SRAM，head及最后127个已发布槽来自同一快照。周期、时长、reset/halt/go次数必须在真实采集器可审查后绑定现场卡。停止未确认、跨代或冲突，保留pending/INCOMPLETE，不补点。

冻结诊断120B不是逐帧事件日志；最终是否需要新诊断插桩由ECG采集设计审查决定。本轮不改固件、不声称采集器已就绪。原软件回归不能替代ECG/RESP实物验收。
