# P 云端接口语义说明

日期：2026-09-19。范围：MMP-P-SOW-001 第一阶段。

## 路径和分层

公网所有入口归入 `/medical-monitor/`：

| 路径 | 用途 |
|---|---|
| `/medical-monitor/` | 模拟监护页面 |
| `/medical-monitor/api/health` | 无鉴权健康检查，不返回遥测数据 |
| `/medical-monitor/device/v1/ingest` | WSS 模拟 Gateway 接入 |
| `/medical-monitor/ws/v1/monitor` | WSS 浏览器只读订阅 |

Nginx 去掉项目前缀后转给本机后端。MockJsonAdapter 将 MOCK/1 转为统一 Frame；
业务层只依赖 Frame，未来可增加 MMP2Adapter。此文件不冻结正式 MMP/2 二进制字节布局。

## MOCK/1

首帧为 Token 鉴权消息，设备与浏览器使用不同的环境变量令牌。设备成功后收到 ready。
设备后续消息字段为：protocol、gateway_id、session_id、seq、mode、captured_at、simulation、nodes。

- `protocol` 固定 MOCK/1，`simulation` 必须 true。
- `gateway_id` 默认 GW-DEV-001，必须匹配服务配置；同一时刻只允许一个已鉴权设备连接。
- `session_id` 在同一连接内不变，`seq` 非负递增；重复/倒序帧 ack.accepted=false。
- 重连建立新的序列窗口；没有跨连接、跨重启的持久化去重承诺。
- `mode` 为 LIVE / REPLAY。`captured_at` 是采集时刻的 Unix 秒，可带小数。
- Node-A 包含 PPG、SpO2、PR、NIBP；Node-B 包含 ECG、HR、RESP、RR、TEMP。
- 每帧为两个节点的完整快照；节点包含 online 与 signals。
- 标量值采用 value；NIBP 为 `[SYS,DIA]`；波形采用 samples 和 sample_rate。
- quality 为 VALID / INVALID / STALE；拒绝非有限数、未知通道与不完整节点集合。
- ECG 250Hz，PPG/RESP 50Hz，Mock 每 200ms 分批发送。

## MVIEW/1 与失效规则

浏览器鉴权后自动收到快照，字段包含 gateway_online、live_fresh、live、replay 和 server_time。
LIVE/REPLAY 使用不同状态槽；REPLAY 不能刷新 LIVE 时效或节点在线状态。
5 秒未收到新数据则 Gateway 过期；没有新 LIVE 或采集时间过旧则 LIVE 过期。
设备明确断开时立即失效；客户端失联超过 5 秒也自行清空当前值。

无效/过期/离线的 LIVE 标量在服务端转为 null，波形转为空数组；前端显示破折号与质量标签。
页面不绘制 REPLAY 波形，只显示补传序号与采集时间。重连及跳帧不连接缺失区间的曲线。
所有信号幅值为模拟相对单位。标量示例不代表真实测量或临床阈值。

## 资源边界

单 Gateway / 单 worker / 最多 32 个浏览器，每浏览器只保留一个待发送快照。
慢浏览器可丢弃旧快照，不能拖慢 Gateway；发送超时回收订阅。波形客户端窗口限制为 8 秒。
Backend 重启清空内存状态，Mock 和已鉴权页面自动重连；刷新页面需重新输入只读 Token。
