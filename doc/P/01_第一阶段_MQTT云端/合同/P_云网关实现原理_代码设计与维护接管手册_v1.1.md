# P 云网关实现原理、代码设计与维护接管手册 v1.1

> 文档类型：ADR/DESIGN + 接管说明；基线：P4 `09695ff2023ef6fd8dadaf5ecd64268b384a9190`（PR #4 合并后）。
> v1.0 为历史版本，当前维护操作以 [维护手册 v1.1](../../90_维护/多参数监护仪_P端云网关维护手册与工作流程_v1.1.md) 为准。

## Current Implementation

当前工程样机为 STM32F407 裸机 Gateway + 加固的 Paho Embedded C + MQTT 3.1.1。ESP8266 出厂 AT 固件负责 Wi-Fi 和 TLS；Gateway 通过串口 AT 管理连接。CAN1 静默环回上的 CANopenNode 测试节点只验证 P 侧链路，不能代表真实 A/B 板外部 CAN 已验收。

数据路径：CANopenNode 测试节点 → OD/PDO 等协议对象 → Canonical Model → Router → 实时队列/32 帧 RAM 缓存 → Paho MQTT 发布 → Broker → Backend → WebSocket → Web 六页面。LIVE 优先于 REPLAY；断线重放按既有契约标识，不能当作实时采样。Gateway 的 MQTT 边界是 **publish-only**，不处理服务端下行命令或订阅业务。

Gateway 当前使用 MQTT 3.1.1（CONNECT 版本 4）。波形 QoS0；标量、状态及 REPLAY QoS1。ESP TLS 路径包含 CA 校验、时间同步、主机名/SNI 相关配置；敏感配置留在外部，不在仓库或日志落明文。具体 topic、payload 和边界以代码及相应历史合同为准。

### Paho 固定安全补丁

第三方来源与完整性由 `gateway/third_party/paho-embedded-c/upstream.json`、`patched.json` 和 `gateway/third_party/paho-embedded-c/PATCHES.md` 记录。`gateway/third_party/paho-embedded-c/verify_paho_integrity.py` 核验原始文件、补丁文件和允许编入固件的源文件清单；修改第三方代码后必须同步审查这些声明。

- PATCH-01：修正 ARM 短枚举 ABI 相关边界。
- PATCH-02：对 MQTT Remaining Length 与接收报文实际长度做有界解析；意外下行 PUBLISH 在 publish-only 边界报错；格式化与凭据输出加界限。
- PATCH-03：补齐长度生命周期与初始化校验、前缀及正文容量校验，并固定 UNSUBACK 相关回归。

`gateway/canopen/run_security_regression.py` 是既有 ASan/UBSan 固定回归入口。安全修复的原始证据见 [P4.1 安全治理收尾报告](../../90_维护/P4.1_安全治理收尾分析报告.md)；这里不改写当时结论。

### Cloud 与 Web

Backend 负责接入、校验、WebSocket 分发与运行日志。浏览器 UI 由 Vite 7.3.5、TypeScript、Vanilla DOM、Canvas 2D、Hash Router 组成，页面为 Overview、ECG、SpO2、RESP、NIBP、TEMP。SessionHistory 为当前浏览器会话内有界数据；冻结只停止可视呈现，接收计数仍可增长。CSV 为本地会话导出；Snapshot v1 的恢复边界依最终 UI 验收报告，不等同于服务器持久历史。Web 不作临床判断。

### Security Gate 与分支

统一 Security Gate 已建立；其准出根据指定基线与既有规则执行，涉及 Semgrep、Trivy、Gitleaks、clang-tidy、ASan/UBSan 等工具。具体运行条件、例外、证据以 [P4.1 报告](../../90_维护/P4.1_安全治理收尾分析报告.md) 和 Security Gate 文档为准。文档对齐不触发新的安全扫描。

`main` 是稳定历史主干；`P4` 是当前 P 集成基线；`dev/node-a-v07` 和 `dev/node-b-v07` 为其他节点独立开发分支。P4 UI 合入点为 `09695ff2023ef6fd8dadaf5ecd64268b384a9190`。

## Future Target

下列均为迁移路线，**不是当前已实现功能**。P5 候选为保持裸机、改用 coreMQTT v2.3.1 且仍使用 MQTT 3.1.1；P6 候选为 FreeRTOS + 同版本 coreMQTT/MQTT 3.1.1；MQTT 5.0 是独立可选协议升级，候选 coreMQTT v5.0.2。版本兼容性和准出条件见 [MQTT/RTOS ADR](../../90_维护/ADR_Gateway_MQTT客户端与FreeRTOS迁移路线_v0.1.md)。新栈须由后续合同授权、单独实现和单独验收，不能用本手册视为获批。

真实 Node-A/B 接入、外部三板 CAN、RR、Flash 持久缓存、FreeRTOS、24 小时运行和 Release Security Gate 仍待完成。当前仅可引用 P2 测试节点准出，不能延伸为整机可靠性结项。
