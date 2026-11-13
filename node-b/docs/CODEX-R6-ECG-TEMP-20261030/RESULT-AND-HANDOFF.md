# R6 ECG60 / TEMP_OBJECT 实板结果与交接

**两个独立窗口均为 ENGINEERING_PASS / 真实联评进程退出0。** 本轮修复一项主机温度观察时序问题，未刷写或修改 B/C 固件，未修改冻结评测器或放宽判据。结果只适用于本轮非人体样机工程窗口，不关闭此前 RR15 的 NOT_PASS，也不构成 B5 三窗结项或发布。

分支 `codex/b5-r6-ecg-temp-20261030`，父提交 `98bd1f86d8e1cbf3b764a0876142a888b8837343`；交付 SHA 是包含本文件的提交，提交推送后另行给出，避免自引用。当前负责人直接授权范围及接线更正记录见 [RUN-SCOPE.md](RUN-SCOPE.md)。未启用生产 P1-B CLI、未签 Gate F、未冒称可信 PI 自动化现场门禁已完成。

## 实测结果

| 项目 | ECG60 | TEMP_OBJECT |
|---|---|---|
| 冻结正式裁定 | B5_SEPARATE_ECG60_ENGINEERING_PASS | B5_SEPARATE_TEMP_OBJECT_ENGINEERING_PASS |
| collector / supervisor / formal review 退出码 | 0 / 0 / 0 | 0 / 0 / 0 |
| 评价期诊断 | 600；HR60有效600/600，RR0 | 600；温度present600/600 |
| 主要源证据 | ECG74981点；WSS观察目标批751 | UART原码/checksum/源报告秒区间映射；新增温度帧1373 |
| 温度观察 | 修复前工具：age -20..204ms，23/600越界，不能当独立温度PASS | 修复后工具：age 1..220ms，0/600越界，600条原始观察区间 |
| 物体温度范围 | 25.75..26.01°C（同窗观察） | 25.69..26.01°C（桌面目标，未标定） |
| Broker / Backend accepted | 2858 / 2858 | 2823 / 2823 |
| Backend rejected / dropped | 0 / 0 | 0 / 0 |
| WSS评价期快照 | 2974 | 2973 |
| C新增txfail/overflow/uart_err/dropped/mqtt_fail | 全0 | 全0 |
| MCU business elapsed / phase / reason | 420000ms / 7 / 1 | 420000ms / 7 / 1 |
| STOP required / written | 858 / 858 | 878 / 878 |
| STOP unsynced / pending | 0 / 0 | 0 / 0 |
| STOP残留live / cache | 24 / 28 | 24 / 29 |
| 业务START / 负责人C RESET | 各一次 | 各一次 |
| B受限SDK调用数 | 25770 | 23853 |

不能把 live/cache 非零描述为“全部队列清空”。两窗均完成420秒MCU业务停止及末尾20秒被动观察，collector关闭J-Link、串口、观察器和隧道；Close后目标状态没有独立仪表观测。协议 `source=MOCK, synthetic=true` 是非人体工程模式标识，本轮窗口数据来自实板采集；另列的17项CPU Mock并非实板数据。

公开裁定及实际执行回执：[ECG60-review-summary.json](../../evidence/CODEX-R6-ECG-TEMP-20261030/ECG60-review-summary.json)、[TEMP_OBJECT-review-summary.json](../../evidence/CODEX-R6-ECG-TEMP-20261030/TEMP_OBJECT-review-summary.json)、两份对应的 `*-execution-summary.json`。正式联评各只运行一次，无改判回放。

## 修改和验证

仅在所有ECG会话退出后修改主机 `b4_runtime.snapshot`：从先BIO后TEMP，改为 BIO-before→TEMP→BIO-after，并用完整BIO-after解码诊断，保留前BIO及TEMP原码和时戳。没有单字段时基替换、clamp、有效位改写或阈值放宽。新增一次已允许的120字节读取，无新地址/写入；仍标记非原子观察。详见 [TEMPERATURE-HOST-FIX.md](TEMPERATURE-HOST-FIX.md)。

修改前负age夹具退出1；修正夹具自己的stale边界断言后，仍单独复现 -20ms。修改后受影响回归 **17项、0失败、0错误、真实进程退出0**，guard拒绝DLL/网络/子进程/串口；本次Mock目标调用0。原始失败、Mock、SSH及各窗口进程真实退出码见 [exit-code-ledger.json](../../evidence/CODEX-R6-ECG-TEMP-20261030/exit-code-ledger.json)。两次准备脚本入口问题均在目标连接前失败并修正，未隐去。

ECG执行 `b4_runtime.py` SHA `03bcf557a1ce8dcc20ddc51479bdbd5dd7d9394af193246d37752659cda2573b`；TEMP执行修复版 SHA `66adde98790da1bca713b68607474f8fe7222914ab503e3d61bb6d88b216c66f`。每窗单独保存32项工具绑定源码快照及输入SHA，不能说最终工具版本完整重跑过ECG。17项回归可由 `python -X utf8 node-b/tests/run_b4_temperature_mock.py` 复现；PowerShell调用时须显式透传 `$LASTEXITCODE`。

冻结联评器SHA仍为 `14838db66a5142f24a010109de6f67a76d4f386a0b3914afb5b32b9a751dda91`。旧profiles、判据、R5记录、两张原disabled申请、核心固件/驱动/采样算法、安装器、云逻辑没有修改；旧R5三窗回放、旧151项和RR重试均未运行。每窗B身份、全片和options均在采集前由原worker匹配受限引用，全片SHA `9ff8133d06330a4b05cb15d26bfb51b6f7e1197014692c5267d178d744f4287d`；C使用本日已核验C49132引用和当窗串口启动/STOP证据，本轮没有重新转接C做SWD全片读取。

## 最终现场与未关闭项

负责人最终确认：**B/C断电、C USB和J-Link电脑端USB拔除、板卡全部熄灭；板端J-Link留B、黄L留LA，其余接线不动。** SKX最后确认正常ECG60bpm/1mV，最终SKX电源未再次确认；温度目标为桌面，没有人体或独立温度参考仪。后续RR测试需另行确认L/模拟器工况，不能沿用旧LL/呼吸状态描述。

本轮只读核验既有隔离backend/TLS运行、正式服务PID及配置哈希一致，未启动/延长服务、未修改Broker ACL/password或正式云配置。既有六小时租期预计北京时间2026-10-30 22:53:26结束，未在收尾再次连接核实到期，账号/ACL未撤销。勿宣称全部云资源已清理。

继续保留：RR15非零HR失败；SDK Open/Device/Connect/Close隐式副作用；ROM根因；独立冷启动；绝对温度/阻抗标定；同窗HR与RR双有效。B5三窗结项仍拒止，生产P1-B入口保持禁用、Gate F未签。本轮没有ROM、未自动恢复、未重刷、未追加窗口。

私有UID/整片/options/凭据/真实端点只在用户受限EFS。126项关键私有原件仅发布文件名/大小/SHA索引：[private-evidence-digest-index.json](../../evidence/CODEX-R6-ECG-TEMP-20261030/private-evidence-digest-index.json)。本交付所有公开文件和修改源码见 [EVIDENCE-HASHES.json](EVIDENCE-HASHES.json)。完成一次汇总提交推送后停止，等待后续具体任务。
