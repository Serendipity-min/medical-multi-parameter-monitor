# SDK、Close 与异常保全矩阵

**结论：`SDK_RESIDUAL_RISK_UNRESOLVED / P1B_NO_GO`。** 复用与少量真实正常会话没有证明 SDK 在所有 Open/Device/Connect/Close 路径都无 CPU 副作用。没有重新开发工具链或下载新驱动。DLL SHA：`632d0d78e72b8a55c65945a0c393a9f081082c725fff4ba3081b0a565fd58cff`。

## 调用和预算

生产 CLI 在加载前拒止。库调用方负责当期授权、选择 BLink/CLink、精确白名单及主机监督器；`capture` 自身只在正常流程尾部检查整体 90 秒，无法中断阻塞原生调用。真实会话同时使用既有独立监督器、全片单调用 45 秒/其他 5 秒心跳；普通 finally 不能保证在 DLL 卡死或 OS 强杀时执行。

初始化策略包括 `SuppressGUI 1`、`DisableAutoUpdateFW = 1`、`SetRestartOnClose 0`、`InhibitConnectRetries = 1`、`ForceAttachTarget = 1`、排除 Flash/options 缓存。Open 前后重复确认策略是继承实现。`Device = STM32F407ZG` 可能隐式连接；SWD 1000kHz、探针唯一及 VTref 检查不能证明内部不会暂停 CPU。不得将这些 SDK 策略称为零控制实证。

`SetRestartOnClose 0` 某些情况下返回此前值 1，继承代码要求无输出并再次确认 0；它不是通用“所有正返回均成功”规则。`SetRestartOnClose = 1` 可能在 Close 恢复目标：B/C 初始只读路径没有主动开启；RR 采集继承旧 B worker 在核验运行态后开启的机制；安装器正常结束也开启。即使运行态前置检查通过，Close 后状态仍未知。

## 离线异常路径

| 场景 / 模拟层级 | Close 尝试 / 完成 | 最后已知状态 / 后续 |
|---|---|---|
| Fake 正常 B/C、完整身份及 flags | 一次 / 是 | Close 前 Flash 运行样本；Close 后 UNKNOWN |
| OpenEx 失败、设置策略失败（适配器抛错） | 调用 close 一次 / fake 完成；native 是否打开取决于阶段 | UNKNOWN；没有补读或恢复 |
| Device 环境变化、Connect 错误（fake 已打开后抛错） | 一次 / fake 完成，记录 native_Close_expected=true | UNKNOWN；不假设原生部分失败状态安全 |
| Connect 后 HALT/ROM 状态假设 | 一次 / fake 完成 | 状态原件先保存，全片读取前停止 |
| 原生负读、正短读 | 一次 / fake 完成 | Fake 异常传播；另对原 BLink 数字返回 -1、3/4 定向测试，均拒止且不重读 |
| 超时、掉线 | 一次 / fake 完成 | UNKNOWN_OR_STOPPED；零重试，人工保全策略必需 |
| SIGTERM/异常 | SystemExit 模拟下 finally 调用一次 / fake 完成 | 仅 Python 路径；没有真实 OS SIGTERM 实证 |
| Close 抛错/超时 | 一次 / 否 | STOP_TARGET_NO_RECOVERY；不二次 Close、不 Go/Reset |
| taskkill/原生永久卡住 | 是否尝试未知 / 不声明完成 | 合成 killed_receipt；Close 后 UNKNOWN，人工断电责任需 PI 指定；不假装已实际强杀验证 |

具体每例 receipt、Close 次数、读次数见 [mock-SDK-fault-matrix.json](../../evidence/CODEX-R6-P1B0-20261030/mock-SDK-fault-matrix.json)。FakeLink 的 OpenEx/Device/Connect 标签模拟的是**Python 适配器异常**，没有证明对应 SDK 原生返回的全部 ABI/副作用。`OpenEx` 实际绑定为 `c_char_p`，成功为 None，错误为指针/消息，不能虚构一个数字负返回；`Close` 是 void，不能编造数值 0。测试名中 negative 不能提升为原生证明。

## 真实会话证据与未决点

B/C 初始各一个会话、零重试、各约 26.141 秒，完整 Flash 读取各一次，ReadMemEx 返回 1048576，options 返回 16，Connect 返回 0，OpenEx 记录非整数 None。正常只读流程 Close 均完成；原生 Close 由继承 finally 直接调用，有心跳但没有整数返回；这条路径未统一收敛到 `call()`，仍是后续审查项。全部数值集合、读地址和执行源码 SHA 见 [live-initial-B-C-read-summary.json](../../evidence/CODEX-R6-P1B0-20261030/live-initial-B-C-read-summary.json)，原始逐调用日志 SHA 见私有证据索引。

真实烧录仅按负责人追加安装许可实施：Halt 返回 0，BeginDownload void，WriteMem 返回 49152，EndDownload 返回 49152，Reset 返回 0，Go void；每项一次。它不是“只读”会话，也不使只读 SDK 风险关闭。RR 使用原 B worker，共 25794 次受限 SDK 调用、2939 块；不把运行期间样本当成 Close 后观测。

未知 HALT/ROM、身份漂移、原生失败时仅 STOP_TARGET_NO_RECOVERY，保存已获得状态；禁止自动补读、重连、复位、Go 或重刷。本轮没有遭遇 ROM，无额外 ROM 实板根因调查。负责人已完成最终断电，不将此动作外推成 SDK 异常路径的通用验证。未来任何风险实证须另立单板次数、关闭策略及人工责任。
