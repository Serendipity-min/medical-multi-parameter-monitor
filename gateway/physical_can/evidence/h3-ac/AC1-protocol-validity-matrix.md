# AC-1 配对协议与有效性矩阵

本轮没有实物输入、串口会话、设备复位或烧录。所有软件值均为合成夹具；实际CANopen源码在Host中处理字节，不等于真机CAN/气路/生理精度通过。R3真人历史只做摘要目录核对，不回灌当前值。

| 层 | 已复核约束 | 本轮证据 |
|---|---|---|
| HKB-08应用完成事件 | `app_bp.c`只在成功结果分支更新`valid_tick`并递增非零`result_generation`；屏/采集流程未修改 | 源码审查、Keil全重建、相同A候选BIN |
| Node-A有效位 | ST_IDLE且新完成代次解除锁存；停止/测量/过期后旧代次不能恢复；年龄≤90000ms | `node-a/tests/host.c`真实CANopen/应用Host；89s、90s、过期、同值新代次、uint32回绕 |
| 完成PDO | Node-ID1的0x281，8B，0x2111:01完成tick32位＋:02 SYS/DIA各16位镜像；1Hz | `OD.c`映射0x21110120/0x21110220；实际A字节→C Adapter→Backend→AI测试 |
| 质量/会话 | 0x681的bit9仅声明完成时间扩展；bit3为NIBP有效；另一个32位为节点通信boot generation | 旧A没有bit9时C拒绝有效NIBP；Boot-up/新质量代次清空PDO新鲜度 |
| 原有PDO | 0x181 PPG、0x381标量、0x481 TIME锚、0x681质量保留；不更改原频率 | Node-A Host、Gateway Host/IRQ、Keil及双ARM |
| Gateway完成UTC | 0x281须≤1500ms新鲜；SYS/DIA须与0x381逐字节匹配；按同节点TIME锚和有符号tick差还原 | 13个Adapter毫秒/回绕/缺帧/错配/旧A/重启/旧元数据/错时钟/未来负例 |
| 89s / 90s / 90.001s | 前两者允许有效；>90000ms不得有当前数值 | A/C Host精确边界；Backend和AI同边界；不是把秒级采样近似为毫秒边界 |
| Backend启动隔离 | 新Gateway会话提高接收代次；新Node-A状态会话不能激活旧遥测；旧会话高seq仍无当前值 | 修前3失败、修后负例通过；真实FastAPI WSS首帧不带旧值 |
| Router补传 | 原Router保留时间/会话/seq，历史标REPLAY；不能续活当前设备/数值 | 既有Router/P5 Host及新增NIBP重启+REPLAY负例；未宣称新真机补传 |
| 同值重新测量 | 新完成代次/完成tick与当前节点会话可重新有效；值相同不视为旧结果 | Node-A Host、Gateway完成时间回归、Backend新会话同值用例 |
| Web和AI | 当前快照INVALID/STALE/OFFLINE均清数值；AI从只读快照判龄，不把历史回答当新事实 | 本机HTTPS/WSS七页20项，真实等待90.109s；MOCK模型0真实调用 |

`result_generation`是A应用本地完成代次，并未另塞进0x281或云JSON；线上完成身份由节点boot会话、completion_tick、SYS/DIA镜像及TIME锚共同关联。AC-2需要现场取得A完成事件诊断和实际CAN帧对应，不能伪报C直接收到了未传输的本地代次数值。

A到期会清bit3并发INVALID；若只剩旧VALID消息，Backend/AI独立到期为STALE。二者都没有可用当前值，周期重发不得改变完成timestamp。通信复位可重新建立时钟/会话，但不能制造新的传感器完成事件；旧A配新C的NIBP明确INVALID。

## 配置/构建边界

- 隔离C：`MP_CAN_RX_IRQ`＋`MP_H3_FRESH_SNTP`＋`MP_H3_PERSISTENT_CONFIG`＋`MP_H3_TEST_SOURCE`＋`MP_MQTT_TLS_PORT=8884`，来源MOCK/synthetic、传输可为实物CAN。
- 正式C：相同IRQ/授时/持久ABI，未设置隔离来源宏，默认MQTT8883；凭据/ACL及正式数据来源须另审。
- 336B记录并不包含端口；只更换sector3不能把8884固件变成8883。正式publisher配置尚未冻结，不允许沿用h3隔离角色。
- 原两块屏/采集/看门狗代码没有本轮改动；Keil/FromELF50084B候选与R2候选完全相同。屏幕实物和传感器控制仍NOT_OBSERVED。

初次新worktree构建把三份coreMQTT断言`__FILE__`路径写进BIN，C体积各增加36B；该次非相同SHA的manifest/原始日志保留在`regression/C-*`，中间BIN未单独归档，构建路径后来由复现目标更新。新增显式`--macro-source-root`只固定诊断宏前缀，不读取/修改旧工作区，不改第三方源码或TLS/PUBACK。最终C BIN已在仓库外独占归档，并与旧实机/正式候选的全字节SHA相同；因此软件配对本身不要求重刷现有隔离C，但实机当前身份仍须在授权窗口核验。
