# B5-002 G0｜分阶段精确授权卡索引

所有卡当前 `enabled=false`、`owner_approved=false`、执行次数0。G0签收、软件预检PASS、卡片存在、负责人批准另一卡，均不构成本卡执行授权。禁止自动顺序串联或失败自动回滚。本轮只准备，不访问实板。

| 卡 | 唯一动作 | 当前阻塞 |
|---|---|---|
| [G1](AUTH-B5-G1-CLOUD-001-R1.md) | 8883测试角色/ACL及独立Backend/Web入口 | PI选择隔离方案并批准变更；专用凭据尚未创建 |
| [HW0](AUTH-B5-HW0-VISUAL-READONLY-001-R1.md) | 一次现状目视/已有资料核对，不发AT/不开串口 | 单独批准；不改变供电/跳线/源模式 |
| [G2-RO](AUTH-B5-G2-READBACK-001-R1.md) | C新鲜双份Flash/options与身份，只读 | 单独现场批准；读回器新scope及工具身份尚须绑定 |
| [G2-A](AUTH-B5-G2A-APPLICATION-001-R1.md) | 唯一42552B应用安装一次 | G2-RO通过；新鲜包及SDK/工具/现场身份绑定 |
| [G2-B](AUTH-B5-G2B-SECTOR3-001-R1.md) | sector3测试配置提交一次 | G1测试凭据；G2-A通过；配置写入器/新包离线验收及单独批准 |
| [G3](AUTH-B5-G3-CLOUD-WINDOW-001-R1.md) | 单次B5START，420秒硬停 | G1/G2-A/G2-B和现场门禁全部通过 |
| [R-APP / R-CFG / R-CLOUD](AUTH-B5-ROLLBACK-SEPARATE-001-R1.md) | 三种回滚分别批准 | 每种独立批准；不得顺带重装或恢复正式联网 |

应用恢复后如需重装，必须新发一次G2-A授权，独立授权编号、时限、现场状态及只用一次标记；不能把首次安装批准解释为恢复/重装授权。恢复sector3同样不能使用G2-B配置提交批准。

## 所有硬件卡的共同绑定

- B保持39948B，BIN SHA `676eb7a46ad9cd15c7bf93db51a1931d7711d37c6f2fd636197dc4a85b339b82`，算法/寄存器不改，250SPS。C最后实测24104B，完整Flash检查点 `b460d917e1d454fdb0882d1f837d91c606363179b817a3896a1df6897b2dcb98`，**今天状态未知**。
- 唯一C候选42552B，BIN SHA `d5b9624b3da1129b4e045d3b2f669c00d2d93cb7379b15293ff143fe9f130683`，ELF SHA `3c726f61f76eadac4909826203ca84dee65521aec448ad477ddca0c3c58795d8`，实现提交 `c65fbedce7edf5d822c573ef5cdeb6471d1ae3d5`。不重新构建替换。
- B CAN1↔C CAN2，500kbps，A段断开；两端各120Ω、独立参考地，历史60.8Ω只作历史证据。P6为PA11/RX、PA12/TX，P4为PB12/RX、PB13/TX。不得短接LL/RL或RLD接地，无人体。当前接线/电源/BOOT/J-Link位置只用已有信息准备，**不能未经授权查询或改变**。
- 用户只确认ESP8266已装C；是否隔离、供电和AT/TLS版本均需后续现场门禁，不能沿用旧“已隔离”。任何恢复旧固件前，ESP必须按另批方式电气隔离，防止自动访问正式身份。
- 每次执行前受限授权记录必须包含卡号/独立事务号、UTC到期、C私有UID、完整Flash/options/sector3/7/11预期SHA、包manifest、执行脚本/依赖/DLL SHA、现场电源/接口状态、动作计数和停机方式。缺一项不执行。UID、主机名、密码、令牌仅在受限加密原件，不填Git。
- 当前G0工具只访问磁盘及只读SSH/TLS，没有实板入口。旧`C_B4_CLOSEOUT_CURRENT_23952_DOUBLE_BACKUP_NO_TARGET_ACTION`读回scope及C24104旧sector0/1安装卡均不适用新卡；不得改旧授权内容绕过身份或范围校验。G2新工具/绑定未就绪时卡仍不可执行。
- 任板ROM、HALT、意外复位，或身份/Flash/options漂移即停止，无自动复位、强设PC/MSP/VTOR、解保护、整片擦除、重刷掩盖或无限重试。只读DWT_PCSR是PC采样，不冒称暂停态真实PC；运行GPIO不冒称BOOT复位锁存。
- 所有新原件、负例、SDK/串口原始回执保存在受限NTFS EFS独占目录；Git仅脱敏摘要与SHA。所有卡均不授权云正式身份、8884、Security Gate、保护分支或三板联动。
