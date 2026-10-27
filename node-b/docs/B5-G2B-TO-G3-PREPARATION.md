# G2-B后第三阶段准备｜未启用

本轮只准备，不启动服务、不发AT/B5START、不连接实板。G1人工MOCK通过与真实B→C→云验收分别记账。

| 顺序 | 事务与准入 | 目前状态 |
|---|---|---|
| 1 | G2-B R3：新工具/配置包/卡SHA绑定，一次sector3事务和ESP在板非隔离例外分别明确，180秒，失败即停 | 离线PASS；真实写入待PI批准 |
| 2 | G1-RESUME R1：新鲜只读比对正式服务/PID、ACL/password SHA、测试unit/权限/端口；仅既有Backend和TLS两个unit各start≤1，300秒准入，Restart=no/驻留6h | 申请卡已冻结；resume-only执行器完整绑定仍待完成；当前不启动 |
| 3 | ESP实际AT版本、CA/SNI/证书存储/SNTP及串口电气检查 | 未实测；旧P分支/Host TLS不能代替；有限检查须独立授权 |
| 4 | G3 R3：B原码诊断、C队列/CAN/网络、Broker实收、Backend接受/拒绝、WSS同session日志及420秒监督器/人工停止附件 | 判据已冻结；实际联合取证工具绑定和现场附件未齐，不可启用 |
| 5 | G3后R-CFG R3→R-APP R2、另R-CLOUD | 分别批准；不自动恢复；ESP在板例外不能代批H3启动 |

源固定普通ECG60/1.0mV、电池/USB断开、RA–LA–RL路径；保持现状的事实由后续现场附件记录，当前不改源/电极。若实际不同则停，不自动换线。300秒共同评价前45秒预热、后15秒尾段，Tarm至多420秒；60秒内就绪并冻结T0，不采后改判据。HR58–62且有效观察100%；RR/TEMP INVALID，A OFFLINE，数据MOCK/synthetic，绝不进入正式GW-C-001/LIVE语义。

G1最近生命周期证据 `../evidence/B5-G2B-PREP/cloud-lifecycle-20261027T011046293943Z.json`：北京时间2026-10-27 01:59:19超时停止，非当前在线证明。账号/ACL未自动撤销，不声称环境已清理。恢复使用原受限EFS部署包SHA `dcee1658be5ce4db2531975069441444a0f50078828321a3e978a8352b520db0`；本轮不读取/打印其凭据，不接真实服务器。

禁止使用 `b5_g1_cloud.apply` 替代resume：该旧G1-A事务包含ACL/password安装及Broker HUP，不属于G1-RESUME权限。恢复不得修改正式unit/Nginx/AI/证书校验，不开放8884或公网端口。测试入口仍仅loopback18775，经既有SSH别名转发。

SDK读路径实际PASS仅来自MEMAP_READONLY_02；新sector3写入仍未实测。所有旧ROM、B5冷启动、同窗HR/RR、绝对阻抗、故障注入状态原样保留。BIO_V2及唯一42552B候选不变。
