# P1-A 现场交接及只读工具准备

现场仅采用 [负责人本轮报告](CODEX-B5-TAKEOVER-FACTS.md)，不以10月29日代替今日。USB接C、J-Link接B、负责人称未上电、L在LL、SKX呼吸模式；接口、电脑端、反供电、VTref和具体菜单值未独立核验。本轮没有请求移动任何线缆或操作模拟器。

完整SDK审查见 [SDK-DOSSIER](audit-context/SDK-DOSSIER.md)，逐工具SHA见tool-registry.json。DLL仅做文件SHA：`632d0d78e72b8a55c65945a0c393a9f081082c725fff4ba3081b0a565fd58cff`，匹配历史预期；未加载、未枚举。

## P1-B 复用准备及必须解决的边界

- 仅复用既有G3 BLink/CLink的精确地址/长度限制、身份比对、原生返回日志和监督思路；不运行G3联合窗口。B40928/C49132应用、全片/options及私有身份分别绑定，绝不混用B41012或旧C24104流程。
- readback_b.acquire含Halt/Go，禁止使用。旧Runtime/Live类含25284/39948 ABI，不能不经核对直接判断新应用PC/诊断。
- OpenEx/Device/Connect可能有隐式CPU影响；Close绕过call直接进入DLL，SetRestartOnClose=1可续跑。P1-A没有足够证据证明“无目标控制副作用”。不得用显式Reset/Go=0替代该证明。
- b5_b_temp_readonly取消Close续跑失败可跳过Close；工人对`.used`仅检查存在。真实授权信任根/nonce消费机制和P1-B专用入口尚未实现；保持 `P1B_TOOL_EXECUTION_NOT_READY`，不在本轮扩大修复到现场驱动。
- 负返回、正短读、超时、ROM/HALT、漂移、电气异常均STOP_TARGET_NO_RECOVERY。禁止重连、Reset/Go、补读或恢复；主机超时结束进程不证明目标已Close。必须由负责人承担批准范围内断电处置。

## 申请边界

两张 [B申请](R6-P1B-BOARD-B-REQUEST.disabled.md)、[C申请](R6-P1B-BOARD-C-REQUEST.disabled.md) 均为 `NOT_AUTHORIZED / HALT_BEFORE_CONNECT`，不是执行卡、没有nonce或可消费token。它们是逐板审查准备，不代表本轮已完成电子只读验签。若PI要推进，须先裁定上述未决副作用和工具入口，再逐板签发精确工具/DLL、身份、读次数、时限、现场责任和单次许可。
