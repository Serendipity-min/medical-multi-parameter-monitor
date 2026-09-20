# 阶段二验证证据

硬件测试日志只保留固定 `GW` 事件、数值计数与明确合成的示例帧。没有保存网络地址、凭据、原始AT交互或真实生理数据。

早期失败记录保留以便追查；不能把这些目录中的已通过子项理解为整轮通过：

| 目录 | 结果与原因 |
|---|---|
| board-smoke | CAN1退出初始化失败；后增加RX上拉 |
| board-smoke-rx-pullup | CAN与云端通路启动，原小批次/发送负载导致部分标量饥饿 |
| board-acceptance | 调整批次后仍有队列公平性问题 |
| board-acceptance-final | 单节点/EMCY通过，连续串口控制丢失了重启命令 |
| board-acceptance-r3 | 重启/CAN恢复通过，发现重连空队列时REPLAY可能先于新实时帧 |
| board-acceptance-r4 | 13个链路子项通过，但Gateway重启瞬间2条状态来源误标，整轮失败 |
| board-acceptance-r5 | 最终来源修复后的首次烧录遇ESP持续AT无响应，等待物理重新上电 |
| board-acceptance-r6 | 重新上电后CPU停留系统ROM启动程序，项目串口无输出；通过J-Link明确进入Flash程序解决本轮测试启动 |
| board-acceptance-r7 | 独立节点、重启和CAN故障通过，但持续负载让历史补传饿死；新增有界发送配额及主机回归 |
| board-acceptance-r8 | 最终整轮13项通过、无解码/来源异常；74.09s，含30s断网与Broker重启恢复。有限RAM溢出有记录，不代表无损采集 |
| browser-fixture | 本机LIVE/REPLAY渲染夹具，通过4项；不是实物LIVE采集 |
| browser-public | 公开大屏只读验证2项通过；实际Gateway-C合成流、RR留空及ECG Canvas，附截图 |
| restoration.json | ESP模式恢复、原始1MiB Flash逐字节回读一致；BOOT0启动现象如实记录 |

早期报告的 `synthetic_only` 表示“允许持久化的样本子集”，不代表未观察到其他来源；实际异常必须同时看 `decode_errors`。新报告使用 `persisted_samples_synthetic_only` 和明确的 `passed` 字段消除歧义。
