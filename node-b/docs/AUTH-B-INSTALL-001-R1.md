# AUTH-B-INSTALL-001 R1｜B板合同候选恢复卡

2026-10-22 Asia/Shanghai。本卡执行依据为负责人明确指令：“当前开发板在其他地方做过测试，之前的被覆盖掉了，因此不一致，重新烧录下载即可”。本卡在烧录前展示，范围仅为同一B板恢复和校验，不需重复确认已有授权。

对象沿用READBACK-001 R2核验通过的唯一B板：STM32F407ZG、DEV_ID=0x413、1024KiB、RDP0、VTref实测3300mV；真实UID绑定受限identity-before-private.json及其SHA，不公开UID。供电仍为J5/YL-1210 12V1A中心正极；J-Link仅调试，B0/B1接GND，现有ADS模块保持连接。无CAN、人体、模拟器，唯一操作者Codex /root。不能使用其他串口工具的“固定工程固件”入口替代本卡。

## 固件、备份与地址

- 候选为c0617b9合同BIO_V2，不改源码/阈值。BIN 25284B，SHA256 `438a8120f6df06ce219cdc30c0e5b697ac0e993f98d5a80521b10361536ae3ae`。
- 当次整片原件1048576B，独立双读逐字节一致；SHA256 `69d9efb0ce0a9228138ea3cc21adbb09c09a15a8b6dbf0d9a1d1ff861a32fc2a`。独立恢复副本及options已封存于受限field-r3目录。
- 仅提交Flash sector0 `[0x08000000,0x08004000)`、sector1 `[0x08004000,0x08008000)`，共32768B。有效BIN至0x080062C4，剩余7484B从当次原件保留。sector2–11保持原件，不用FF填尾，不全片擦除。
- 预期完整Flash SHA256 `f713277a50a5ec8d8a93317f412d5ab1b754e5d619918e57e9efe9dceef24cbb`。校验必须覆盖整片，不能仅验BIN前缀。
- 原件、扇区回滚文件、预期整片、计划JSON和运行日志仅存 `E:/medical-monitor-node-b-field-private/field-r3`。本卡不自动回滚；失败保留现场并先报告，不用旧PC继续运行新代码。

## 精确动作与停止

入口为supervise_readback.py --operation install及install_b.py；绑定本卡SHA、工具SHA、计划SHA及READBACK实际UID。使用已脱机验证的便携SEGGER9.86a x64 DLL，SHA `632d0d78e72b8a55c65945a0c393a9f081082c725fff4ba3081b0a565fd58cff`。沿用READBACK-R2的无固件升级、无自动连接复位重试、关闭不go、单探针、3.0–3.6V参考门及SWD1000kHz策略。

1. 单会话attach，先核身份/保护/UID与备份一致；halt最多1次，确认稳定暂停。再读整片Flash并核当次原SHA；漂移、忙/错误、保护或身份不符立即停止，尚不开始下载。
2. 固定SDK顺序BeginDownload(0)、WriteMem(0x08000000,32768)、EndDownload；标准扇区算法可使用工作RAM、Flash控制寄存器并擦写上述2扇区。本卡明确允许该算法造成调试暂停、内部编程操作和RAM工作区变化。未导入全片擦除、options/RDP/OTP写入口。
3. 暂停状态下读回完整1MiB，逐字节比对预期整片；另核0x08008000以外原件未变，UID/OPTCR及16B option原始字节不变。
4. 仅全部核验成功后，明确reset最多1次、go最多1次，清读该次RESET粘滞位后确认RUNNING。Flashloader内部操作如异常触发额外复位或丢失暂停立即停止，不能据此冒称零扰动。
5. 普通SDK调用5s、halt3s、EndDownload45s、完整读取45s，监督进程180s总上限；STOP或超时杀工作进程，无自动恢复/重连/再烧。失败目标可能暂停或状态未知，必须如实报告。

不更改供电/排线/跳帽，不接源，不读取采样RAM，不采波形，不接CAN，不操作云和保护分支。成功/STOP即结束本卡；后续ADS输入检查及ECG接源采集另展示卡。合成测试验证成功、原件漂移、全片校验损坏和错误UID停止路径，只作为工具验证。
