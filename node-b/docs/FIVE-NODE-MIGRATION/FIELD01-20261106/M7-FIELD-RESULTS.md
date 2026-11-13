# M7-FIELD-RESULTS（执行中，2026-11-06）

**最新：E屏101/67已在C、隔离Broker和真实网页同次匹配，原90秒失效分项通过，负责人确认全部断电。** 网页在源龄90.074秒转STALE，实际DOM隐藏SYS/DIA，未见旧值复活；C控制器原生退出1和TTS STOP未确认分别保留。见[E有效实测报告](DE-NIBP-101-67-RESULTS.md)。未commit/push，不自动重试。

当前保留C1↔E1=61Ω、C2↔D1=60.9Ω线束，USB/J-Link电脑端不接。此前[A/D短窗报告](AD60-POINT-TO-POINT-RESULTS.md)、[首次E计时失败](DE-NIBP-FIRST-RESULTS.md)、[等待修正](DE-NIBP-WAITING-FIX.md)与[暂停交接](PAUSED-HANDOFF-20261106.md)按历史保留，不用最新分项通过覆盖原生失败。

五板各自实装入口已核对：A/B/C/E已受限安装并完整读回；D现有M1完整镜像匹配，未重刷。正常M1与临时60秒双CAN诊断镜像分别冻结，实际留机状态随回执更新。

| 层级 | 当前结果 |
|---|---|
| 镜像/恢复 | 五板身份逐一核对；A/B/C/E受限安装PASS，D只读匹配PASS |
| D本地源/屏 | 源端15秒PASS，24.97–25.14℃；负责人确认屏读数一致 |
| E本地/点对点/90秒失效 | 本次非人体101/67同次匹配；网页90.074秒STALE、值隐藏，E仍ONLINE；分项通过 |
| 约41Ω短诊断 | NOT_PASS：44.005秒A发送缓冲溢出，退出1；已断电，无自动重试 |
| 收尾/定向修复 | C正常M1已逐字节恢复；A发送背压/同ID顺序修复已安装，本次约60Ω点对点未复现EMCY；全窗源端无损证据不足 |
| A/D点对点 | 本窗链路工程通过；PPG59批/2,950点，SpO₂/PR/温度各59条；A只读观察仅覆盖最后约13秒，原生退出1保留 |
| 隔离Broker→本机后端→真实WS网页 | A/D窗236/236条精确匹配；本E窗NIBP1/1匹配，D温度145条VALID匹配＋1条启动STALE遮蔽；两窗均无REPLAY，不冒充正式远端WSS或五板300秒 |
| 正确端接五板300秒 | NOT_RUN；D/E无终端接口尚缺 |
| TTS/语音/自动冷启动 | TTS无ACK/STOP未确认继续开放；没有录音或语音验收，自动冷启动NOT_RUN，不作为五板硬件前置 |

实际镜像、SHA、写区及恢复指纹见[制品清单](PREPARATION-MANIFEST.json)。分板原始退出码与状态、最新物理状态、局部检查和剩余项见[详细记录](RESULTS.md)。完整私有原件、UID、Options及恢复入口留在既有EFS，通过本机忽略的 `node-b/build/five-node-field01-current-pointer.json` 定位。

R6仍为NOT_PASS；三项保持开放：`R6_AUDIO_ASSEMBLY_TIMEOUT`、`R6_LIVE_QUEUE_OVERFLOW_30`、`A_PPG_SOURCE_GAPS`。没有安排ABC R7/R8，没有整体合并R6分支，没有修改main、正式云、ACL或密钥。本阶段未提交或push。
