# M1-E60-R1单次试采待签卡（禁用）

**NOT_AUTHORIZED；NOT_RUN；enabled=false；sessions=0；PI_signature=null；nonce=null。** [机器卡](M1-E60-R1-ONE-SHOT.disabled.json)仅在本轮新分支更新，原M0/P0卡和历史结果不变；本稿不消耗现场次数、不创建权限令牌，也不自动解锁其余23场。

| 域 | 已准备的离线绑定 | 尚需PI独立冻结 |
|---|---|---|
| 对象 | 仅Node-B，历史B41012B；BIN SHA `1dbbf27177caa429f037ac72c43581a519e8ff70ac6224411c9c4ffe9529432d` | 唯一许可内采前核对当前真实identity/full/options；不额外连板、不烧录 |
| 符号链 | 同次AXF `e11219c4…`、symbols `07e2166e…`；完整SHA及RAM映射沿用已核验链 | 不混用另一构建；最终tool/commit/tree/SHA按实际签发版本绑定 |
| PI根 | Ed25519，原始32B公钥的SHA256作为固定指纹；当前根None | PI可信渠道选定、提供并核对；私钥由PI控制，不由Codex代建/代签 |
| 单次性 | 原子nonce消耗、父/worker独立claim，失败不自动退还；本稿无nonce | 新签名、唯一目录、有效期、仅M1-E60-R1一次会话，其他23场不继承 |
| 刺激 | 正常ECG60bpm、名义1mV、R→RA/L→LA/F→RL、非人体 | 当期实际菜单、SKX电池/充电USB断开及导联确认，当前未核定 |
| 电气 | B-only，不依赖C业务或双CAN软件 | 经批准冷态图中的C电源/USB/CAN/反供电/探针隔离，不能以“C未采集”代替 |
| 冷启动 | 新独立物理冷启动和真实BOOT epoch；uptime只是附加条件 | 现场人员获得具体许可后按签署时序执行；不允许软件RESET/HALT/Go |
| 预算 | 预检75s、原码165s、收尾20s、总260s/父监督265s；native读/Close5s、full读45s | PI认可界限和人工停止/保全/断电责任；不自动重连或第二场 |
| 判据 | 45s预热+120s评价，120个半开1Hz槽；≥118正确有效、每条已观测有效HR在60±2；原码完整/合法STOP与Close | 仅review exit0且field_scope_PASS=true才可申请工程PASS；失败保留原件后停止 |
| SDK风险 | closing普通调用不再豁免STOP；finally Close未修改 | 原生Open/Device/Connect/Close及在途行为/强杀后的MCU状态未知，PI需明确知情接受 |

当前固定根仍未配置，现场CLI拒止exit2。不得改enabled、填owner字段、拿旧G3 nonce/临时自签根或非空签名来放行；签名数学有效也不等于密钥属于PI。若PI选择固定根并允许写入，工具SHA会改变，必须先重新冻结完整版本及回归再签场次。

本轮仅完成STOP局部补丁和离线材料；不指挥现在上电、改线、拍新上电照或按RESET。首次现场获独立许可后，如预检/采集/Close/review任何一步失败，保留真实码和原件即停；本卡成功且PI接收后才可另申请ECG90/120，RR和其他次数仍各自审批。
