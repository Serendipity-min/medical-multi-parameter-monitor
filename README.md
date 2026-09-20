# 多参数心电监护仪系统样机

当前依据 [v0.7 最终总合同](<doc/多参数监护仪_总开发合同与系统方案_v0.7 .md>)，
P 已从 [第一阶段合同 v0.2](doc/P/01_第一阶段_MQTT云端/合同/P_第一阶段_GatewayC云端Web执行方案合同_v0.2.md) 进入用户明确授权的 [第二阶段 CANopen 与可靠性](doc/P/02_第二阶段_CANopen可靠性/README.md)。
开发分支 `dev/p-gateway-cloud-v07`；旧 `codex/p-cloud-phase1` 已迁移停用。实现尚未合入 main。

## 当前可用成果

- STM32F407 Gateway-C 运行 Paho MQTT 3.1.1，ESP8266 原厂 AT 提供验证证书的 TLS Socket。
- Mosquitto 8883、分角色 Topic ACL、FastAPI 只读订阅、浏览器 WSS；主域名路径 `/medical-monitor/`。
- 四模块监护大屏：心电、呼吸、血氧、血压；附 TEMP、网关/节点状态、MOCK 与 REPLAY 标记。
- 服务器独立运行模拟网关；真机已验证九路合成数据上云、断网及 Broker 重启恢复，测试后恢复开发板原程序。
- 数据仍为合成测试源；不代表 A/B 传感器、真实 RR 算法或医疗测量精度已经完成。
- CANopenNode 固定版本、A/B数据字典与OD/PDO、Gateway统一模型、RAM缓存及低优先级REPLAY已落地。阶段二使用两个独立测试生产者和F407内部CAN loopback；准出状态见阶段二报告。

[本轮执行和验收报告](doc/P/01_第一阶段_MQTT云端/验收/P_MQTT真机云端执行报告_2026-09-20.md) ·
[接口语义](doc/P/01_第一阶段_MQTT云端/设计与接口/P_MQTT接口语义_v0.7.md) ·
[云端开发](cloud/README.md) · [部署与回滚](cloud/deploy/README.md) · [Gateway 工程](gateway/mqtt/README.md)

## 文档分工

| 目录 | 内容 |
|---|---|
| [doc](doc/README.md) | 总合同、总体方案、全系统报告与草稿 |
| [doc/P](doc/P/README.md) | P 合同、协议、Gateway、云端、大屏、集成验收 |
| [doc/A](doc/A/README.md) | Node-A 血氧、血压相关工作 |
| [doc/B](doc/B/README.md) | Node-B 心电、呼吸、体温相关工作 |

历史 WSS 文档和早期单主控引脚方案只作追溯，不能覆盖 v0.7 总合同；实际板卡接线以已核对硬件记录为准。
阶段二已冻结 CANopen OD/PDO；正式传感器控制、真实RR、报警决策、长期数据库与Flash持久缓存仍需后续工作。RAM缓存有限且掉电丢失，24h稳定性属于最终系统验收。
