# AUTH-B5-R-CFG-001 R3｜已连接流程恢复sector3、ESP在板，待独立批准

`enabled=false; owner_approved=false; executions=0`。不是G2-B附带动作；本轮禁止执行。

- 仅适用于G2-B完整成功后的全片 `acb33fdd39ecb016ecd848ec25eee051635f56ef8138b577a8590d2734ad687e`，目标 `3eaf583a703137b09665da5d2bfd7e860cd3a2208bf659b631d7ee4d0541545c`。恢复整sector3 SHA `1698c8783b4fbdd1bc7fc5a8641babc7b499b58a65be54e7b36c65c6c5b88313`，generation4→原3，原committed字最后写。42552B应用暂保留。
- 绑定真实配置包 `20cba97d9587fd50f6ad9a98a19efc2812c62675e1304c646d88e771b9d2c73f`、相同writer/protocol/监督器/DLL SHA；独立一次EFS授权scope=`B5_R_CFG_SECTOR3_CONNECTED_CONTEXT_ESP_PRESENT`、phase=restore_config，单独有效期/输出/现场附件。
- 入口状态必须在批准前冻结 `entry_runtime_state_hex`：云窗正常收尾后为 `00000101`，对应mqtt_connected=0、network_open=0、stopped=1、armed=1；若尚未武装则只能另在授权内明确 `00000000`。冻结固件STOP不清armed，因此不能把保留历史armed标志误判为仍在联网，也不能接受活动armed、network/mqtt仍为1或任意其他组合。暂停前后读值必须完全匹配授权，ESP保持在板供电，必须另批本次恢复的非隔离例外，ESP_isolated=false；此前G2-A或配置写入许可不能借用；不为匹配门禁先复位。成功恢复后的正常启动仍要求全零DISARMED。
- 本卡不移动ESP/VCC/EN，模块自主联网仍UNKNOWN；明确ESP_present_powered_exception_approved=true、ESP_exception_scope=本卡scope，并绑定真实现场附件；B/源不变，C运行/UID/保护/双全片及双options重新核对。ROM/HALT/意外复位或任何漂移即停。不是允许联网的H3配置恢复，也不解除保护。
- 动作仅sector3 `[0x0800C000,0x08010000)`；一次erase、最后一次commit，halt/reset/go各≤1，180秒硬限、不重试。原始MEM-AP只读交叉核验、cache策略、全片双验、入口真实寄存器及失败清理与[G2-B R3](AUTH-B5-G2B-SECTOR3-001-R3.md)相同；所有应用/options/sector7/11保留。
- 失败留下记录并停。部分写失败的当前全片并非本卡before，不得忽略不匹配继续恢复；必须另行取证、重新编制精确恢复事务并获得批准。

此后C仍为B5应用＋旧配置，应保持DISARMED，不发送AT/B5START，不能宣称ESP已隔离。只有再单独批准并完成[R-APP](AUTH-B5-R-APP-001-R2.md)，完整全片才能回到本轮原始C24104检查点。恢复包存在不等于已演练恢复。

写入器SHA256 `5464387e61ecbd1d109539996e06648a0e47d0ac601f674a3e1d449a045e0c3d`，完整工具/DLL与配置包绑定见 `../evidence/B5-G2B-CONNECTED-PREP/bindings.json`。card_sha256必须为本R3文件SHA。禁Configure，复用已连接SDK，原始错误锁停止所有后续AP/DP；仅健康idle暂停态允许非NVM清理。入口双全片/options及成功后双读均必须一致，原件仍在受限EFS。实际恢复未执行；R-APP维持独立申请，其ESP条件不得由本卡代批。
