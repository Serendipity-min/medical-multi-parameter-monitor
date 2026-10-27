# G2-B后第三阶段准备｜联合工具与R4卡已冻结，未启用

G2-B R3首次实板写入已PASS（110.641秒），G1-RESUME R2随后已实际通过；本次只准备G3，不再次启动/查询服务、不发AT/B5START、不追加实板连接。G1人工MOCK通过与真实B→C→云验收分别记账。

| 顺序 | 事务与准入 | 目前状态 |
|---|---|---|
| 1 | G2-B R3：新工具/配置包/卡SHA绑定，一次sector3事务和ESP在板非隔离例外分别明确，180秒，失败即停 | 首次真实写入PASS；完整Flash/options/DISARMED合格，许可已消费 |
| 2 | G1-RESUME R2：新鲜只读比对正式服务/PID、ACL/password SHA、测试unit/权限/端口；仅既有Backend和TLS两个unit各start≤1，300秒准入，Restart=no/驻留6h | 新resume-only执行器及9项定向测试通过、输入/源码/权限已绑定；负责人已另批并实际恢复PASS；仅backend/tls各start1，G3仍另批 |
| 3 | ESP实际AT版本、CA/SNI/证书存储/SNTP及串口电气检查 | 实测仍未运行；已冻结仅在未来一次START后60秒内按现固件日志判定，首次失败要求人工切电，不另发AT探测/放宽证书校验 |
| 4 | [G3 R4](AUTH-B5-G3-CLOUD-WINDOW-001-R4.md)：B原码/实际CAN队列、C诊断、Broker原始实收、Backend聚合接受/拒绝及WSS、420秒独立监督 | 41项定向离线测试及合成300秒联评通过；[工具SHA/白名单/环境](../evidence/B5-G3-PREP/bindings.json)已冻结；实际现场事实与HW/G3许可仍缺，B5START=0 |
| 5 | G3后R-CFG R3→R-APP R2、另R-CLOUD | 分别批准；不自动恢复；ESP在板例外不能代批H3启动 |

源固定普通ECG60/1.0mV、电池/USB断开、RA–LA–RL路径；保持现状的事实由后续现场附件记录，当前不改源/电极。若实际不同则停，不自动换线。300秒共同评价前45秒预热、后15秒尾段，Tarm至多420秒；60秒内就绪并冻结T0，不采后改判据。HR58–62且有效观察100%；RR/TEMP INVALID，A OFFLINE，数据MOCK/synthetic，绝不进入正式GW-C-001/LIVE语义。

历史生命周期证据 `../evidence/B5-G2B-PREP/cloud-lifecycle-20261027T030648078926Z.json`记录北京时间2026-10-27 01:59:19超时停止；之后已另批实际恢复，见文末。两者都不是本次工具准备时的在线查询。账号/ACL未自动撤销，不声称环境已清理。原受限EFS部署包SHA仍为 `dcee1658be5ce4db2531975069441444a0f50078828321a3e978a8352b520db0`，本次不连接或修改云端。

禁止使用 `b5_g1_cloud.apply` 替代resume：该旧G1-A事务包含ACL/password安装及Broker HUP，不属于G1-RESUME权限。恢复不得修改正式unit/Nginx/AI/证书校验，不开放8884或公网端口。测试入口仍仅loopback18775，经既有SSH别名转发。

SDK读路径实际PASS仅来自MEMAP_READONLY_02；新sector3写入已按R3首次实际通过。所有旧ROM、B5冷启动、同窗HR/RR、绝对阻抗、故障注入状态原样保留。BIO_V2及唯一42552B候选不变。

当前登记现场仍为J-Link在C、C J5、C USB_UART断开、B断电。G3需C串口记录及B供电/原码观察；这些变化须精确电气附件和负责人操作，不能从本次“供电接线不变”的配置许可推导出热转接或上电权限。当前COM号不得直接套用历史COM6/COM15。

最新G1-RESUME R2已经真实通过：TLS/CA/SNI、Backend健康及MQTT订阅正常，18775监听，正式服务PID/配置不变。见 `../evidence/B5-G1-RESUME-01/result.json`。服务预计北京时间17:15:45到6h驻留上限，账号/ACL不自动撤销；当前没有B5START。

新增[HW准备卡](AUTH-B5-G3-HW-PREP-001-R1.md)把C一次90秒只读与通过后的冷态转接合在一张待批卡；USB、B上电和J-Link步骤一次列清。当前不要求负责人操作，不能因工具就绪自动执行。G3额外计划内C RESET只在未来B/网络观察器就绪后提示，需G3 R4独立批准。完整阶段状态以唯一[B5-REAL-CLOUD-FINAL-HANDOFF](B5-REAL-CLOUD-FINAL-HANDOFF.md)为准。
