# Gateway-C 后续单板只读申请补充（禁用）

`status=HALT_NOT_READY`；`enabled=false`；`token=NOT_CREATED`；`nonce=PI_TO_ISSUE_ONLY`；`scope=CODEX_P1B_READONLY_C`；`field_execution=NOT_AUTHORIZED_FOR_A_NEW_SESSION`。

原 `R6-P1B-BOARD-C-REQUEST.disabled.md` 字节保持不变。本轮仅初始只读和一次 RR15 业务/人工 RESET，没有 C Flash、sector3、options 写入。初始实测 C49132 配置代际 5；不能把当前断电状态当作新的 DISARMED 寄存器实测。

| 字段 | 候选 / 待填内容 |
|---|---|
| 板卡 / scope | C / CODEX_P1B_READONLY_C，不与 B 共用 token/nonce/目录/时间窗 |
| BIN | 49132 bytes；SHA `72131dbb5ef6bc0e0d33e328925c685403bae928aea9447a81f8291c6ae5c1ab` |
| 完整 Flash | `9bba23b436f079183296fa98dcaeed047eb919ba8597d75a85bc144bc48417fd`，本轮初始实测匹配 |
| DISARMED flags | **C49132 绑定地址 `0x20001E6A/4`**，本轮初始返回四个零；不复制 C24104 常量 |
| 身份 / Options | 独立 C 的 EFS 引用和 SHA，原码不上库；不能引用 B 身份 |
| 代码 / 签名 | 实际 repo commit/tree、所有工具 SHA/DLL SHA、PI 公钥指纹、时间窗及 nonce：PI_TO_FREEZE；根未配置 |
| 会话 / 预算 | 仅 C 一次、零重试、90s；全片<=45s，其余<=5s；独立输出与监督器 |
| 异常人工责任 | PI_TO_SIGN；Close/Connect 风险未证实，故当前 HALT |

精确身份、状态和向量别名读采用 B 补充表同一地址/长度，只绑定 C 身份；加上述 C flags 一次。全片 `0x08000000/1048576` 一次、options `0x1FFFC000/16` 一次；不读 UART DR、不做业务采集、不写目标。按签名冻结实际每组次数，不给无限轮询权限。B/C 的授权对象绝不互换。

未来现场前置：冷态由负责人转接 J-Link 到 C，仅 C 获准供电，B 与 C USB 断开，探针唯一/方向/VTref/无反供电与当期目视记录重新确认；本文件不要求现在做物理动作。任何异常仅保存已获状态、STOP_TARGET_NO_RECOVERY，不自动补读、重连、Reset/Go 或 Flash 修复。SDK 初始化/Close 政策及人工断电保全责任应具体签署。原始 disabled 卡、布尔确认、非空签名和 OFFLINE_MOCK 都不能启用候选 CLI。

当前 **HALT_NOT_READY**；只读观测成功没有授予新现场动作，也没有关闭 SDK 原生副作用风险。
