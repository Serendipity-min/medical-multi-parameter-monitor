# MPM-C-VOICE-002 唯一交接报告

状态：进行中，`VOICE_CLOUD_PARTIAL/BLOCKED`。不得把下列软件验证理解为真实云端可闻通过。

## 已完成

V0/V1独立工作区、受限接收、P6V1、UART合体候选及功能回归已完成。
完整审计见 `V0-BASELINE-AND-DIFF.md`，精确实板/云端/恢复范围见 `OPERATION-PLAN.md`。
原始退出码和字节摘要在 `evidence/`；曾失败的轮次保留，最新通过不覆盖原件。

最终候选 BIN 47324B：`ad51f436284b314c8287df8541a94e44ba581124521807be5a6df532a130af8d`。
ELF：`c2a18b793bef6c329d29a619dec7f1b89b2b81c1e665688c3acb3d0874e512cf`。
MAP：`d14e7f2fb5762e2f601f928f43f4fa3aedea1b7c9faf331b635153d08d15d8dc`。
Flash只限0–2，末端0x0800B8DC；原H3 BIN已字节复现。静态BSS123824B，增加688B；运行栈尚未测量。

Host：原TTS3103断言、P6V1 84检查、6组真实MQTT混合负例；普通P5 42及IRQ48、CAN/Router通过。
Python332 passed/1 skipped/4 subtests，补充维护/云发布器19 passed；Web15项通过、Vite构建通过。
V2依据负责人最新指令跳过独立隔离Broker，仅使用Host替身进行软件验证，不能标完整V2 PASS。

## 当前未完成

新镜像实板身份/备份/烧录、正常冷启动、正式8883最小ACL及AI发布器部署、真实模型调用与人工听音、
本轮新PPG连续300s、实际应用/云端回退均尚未执行。
8Ω1W只做v1单条≤60B，不扩展多次声学；STOP仍BLOCKED_STOP。
第二份合同后续提供，本轮不介入B，不创建新tag或PR，不修改任何保护分支。

最终提交、窗口与逐层实测结果待执行后补充，不预填PASS。
