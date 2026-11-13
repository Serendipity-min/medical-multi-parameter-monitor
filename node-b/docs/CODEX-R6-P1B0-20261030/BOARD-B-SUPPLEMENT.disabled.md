# Node-B 后续单板只读申请补充（禁用）

`status=HALT_NOT_READY`；`enabled=false`；`token=NOT_CREATED`；`nonce=PI_TO_ISSUE_ONLY`；`scope=CODEX_P1B_READONLY_B`；`field_execution=NOT_AUTHORIZED_FOR_A_NEW_SESSION`。

本文件补充，不修改或启用 P1-A 原 `R6-P1B-BOARD-B-REQUEST.disabled.md`。旧申请的 B40928 历史身份仍属历史；本轮负责人直接授权安装后，当前 B 是 **B41012**。旧 40928 计划将拒止当前 Flash；未静默改动薄入口历史 IMAGES 常量。

## 待签对象

| 字段 | 候选 / 待填内容 |
|---|---|
| 板卡 / scope | B / CODEX_P1B_READONLY_B，不得与 C 共用 |
| BIN | 41012 bytes；SHA `1dbbf27177caa429f037ac72c43581a519e8ff70ac6224411c9c4ffe9529432d` |
| 当前完整 Flash | `9ff8133d06330a4b05cb15d26bfb51b6f7e1197014692c5267d178d744f4287d`；以本轮安装及 RR 前读回为证，未来仍须绑定引用 |
| 身份 / Options | 本轮安装后 EFS 引用及其 SHA；不嵌 UID、options 原码，签发时通过私有 digest index 定位 |
| 代码 | 最终实际 repo commit/tree、所有工具 SHA 及 DLL SHA：PI_TO_FREEZE，不以父提交替代最终工具 |
| 入口 | 默认禁用 CLI；当前不支持 B41012 现场放行，未来经审查显式新版本冻结 |
| 会话 / 次数 | 仅 B，一次新会话，retries=0，独立 B 输出目录；不重置本轮已消费次数 |
| 时间 / nonce | PI_TO_ISSUE，单板独立 not_before/expires 与随机 nonce，不预造有效卡 |
| 风险 / 责任 | SDK Connect/Close 风险未闭合；明确禁止恢复；人工保全/断电负责人、步骤 PI_TO_SIGN |

完整 Flash `0x08000000/1048576` 一次，options `0x1FFFC000/16` 一次；身份读 `CPUID 0xE000ED00/4`、`DBGMCU_IDCODE 0xE0042000/4`、UID `0x1FFF7A10/12`、容量 `0x1FFF7A22/2`、FLASH_SR `0x40023C0C/4`、OPTCR `0x40023C14/4`。状态 DHCSR `0xE000EDF0/4`、VTOR `0xE000ED08/4`、CFSR `0xE000ED28/4`、HFSR `0xE000ED2C/4`、PCSR `0xE000101C/4`；首尾状态、入口粘滞 DHCSR、PCSR 每组 3 次，VTOR=0 时向量别名 `0/64` 一次。未来实际次数表、SDK 白名单及全部父类 SHA 必须与签名对象共同冻结，不允许扩大至业务采集、UART DR 或整块 RAM。

提议 session<=90s、全片调用<=45s、其他<=5s、零重试，独立监督器负责原生阻塞。任何负返回/短读/超时/身份漂移/ROM/HALT 即停止，保存已获得原件，不再读取或恢复。无 Reset/Halt/Go/写入、Flash/options/配置、B5START、AT、网络业务。允许的 SDK 初始化/关闭政策需逐项 PI 承认残余，不能藏在“只读”字样中。

最新断电事实见 final-site-owner-report.json；未来签发时须重新确认仅目标板供电、J-Link 方向/探针/VTref、C/USB 隔离及无反供电，不因历史状态要求现在上电。B/C 各自裁决，当前 **HALT**。本模板没有签名，不可执行。
