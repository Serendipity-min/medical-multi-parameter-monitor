# R6 P1-B0 收尾及负责人追加现场执行：PI 裁决包

本轮已完成 B/C 初始身份只读核验、B41012 安装和一次 RR15 窗口。采集进程退出 0；冻结联评器裁定 **B5_SEPARATE_RR15_NOT_PASS / exit 3**。独立 TEMP、ECG60 窗口未执行，B5 不得结项。

分支：`audit/codex-b5-r6-p1b0-20261030`；唯一父提交：`9f5a6641fec2bcdb575f5f9ff549b8e9b0223820`。交付 SHA 是包含本文件的提交，推送后在聊天和本地 delivery receipt 中给出，避免自引用。未改写旧审计/Gemini 分支、未合并 main、未创建 PR。

## 范围和授权事实

附件合同仅授权离线工作；同一条用户请求随后明确修改为读取 B/C、烧录并快速测试，并确认已上电、模拟器参数及逐次冷态转接/复位。本轮现场操作依据这些当期负责人直接指令执行，**不是**附件合同自身授权，也不是已完成可信 PI 验签或 Gate F。完整冲突处理、动作及原始回执索引见 [CURRENT-FIELD-AND-FAILURE.md](CURRENT-FIELD-AND-FAILURE.md)。不得使用合同中的“本轮原生调用=0、B41012 未安装”模板覆盖实际事实。

## 交付与结果

| 项目 | 本轮结论 / 退出码 |
|---|---|
| 默认禁用的 P1-B CLI、Ed25519 绑定及一次性 nonce | 离线候选；现场 CLI 无条件拒止，生产信任根未配置 |
| 最终定向 Mock | **16/16，exit 0**，本次测试目标原生调用 0；不等于整个工作轮目标调用 0 |
| 一次 B41012 安装 Mock | PASS_MOCK / 0 |
| B、C 初始只读会话 | 各 worker 0 / supervisor 0；历史完整 Flash、options、身份匹配；Close 后状态未观测 |
| B41012 实装 | 0；48KiB sectors 0/1/2；外区与 options 不变；完整 Flash `9ff8133d…` |
| 已有隔离云测试 backend/TLS 恢复 | SSH 0 / 业务回执 0；正式服务 PID、配置哈希不变 |
| RR15 一次采集 | worker 0 / supervisor 0；B5START 一次，负责人 C RESET 一次 |
| RR15 冻结正式联评 | **NOT_PASS / 3**：`B_RR_VALID15_HR_INVALID`、`HR_EXPECTED_INVALID`、`WSS_TARGET_CHANNEL_INVALID` |
| 独立 TEMP、ECG60；旧 R5 回放；旧 151 项矩阵 | 本轮 NOT_RUN；不重复已结束的 P1-A 审计 |

原始失败保留：收尾 runner 首次初始化被离线 DLL guard 拒止，shell 1、测试 0 项；首次正式联评 Python/JSON 3，但 pwsh 包装未透传而返回 1，后来仅透传已有结果得到 shell 3，没有重评。全部见 [退出码账本](../../evidence/CODEX-R6-P1B0-20261030/exit-code-ledger.json)。

## 待 PI 决定

1. **B、C 后续 P1-B 均 HALT / NOT_READY**：可信生产根、公钥指纹及 SDK Connect/Close 副作用未闭合；补充申请仍禁用，旧两张申请字节未改。B 当前已变为 B41012，历史 B40928 申请不可再作为当前板卡身份依据。
2. RR15 的 600 帧 B 诊断中 20 帧出现非零 HR，云端 10 次；已形成六簇失败夹具。低幅信号/工频噪声是假设，尚不能排除模拟器实际 ECG 成分；不得硬屏蔽 HR 或改冻结判据来通过。
3. 同窗 TEMP 观察有 22/600 age 越界、最小 -22ms；BIO 与 TEMP 非原子分次读取的主机偏差已确认。应先审同一时基/夹逼读观察方案，再决定是否有固件缺陷。不得用主机时间补偿重判 PASS。
4. 建议下一包先批准离线失败夹具和观察方案审查，**不附带新实板次数**；新现场验证另行冻结工具、候选、板卡、次数及停止策略后授权。SDK 风险仍 `UNRESOLVED`，Gate F `NOT_SIGNED`。

最终现场由负责人确认：B/C 关闭，C USB 与 J-Link 电脑端 USB 已拔，全部熄灭；板端 J-Link 留 B、L 留 LL，其余线未动。无新的仪表断电/隔离测量；SKX 最终电源未再次确认。采集器、串口、调试会话、云观察器及隧道已退出。隔离 backend/TLS 的六小时租期预计北京时间 22:53:26 结束，未再次连接核实到期、未撤销账号/ACL，不宣称全部云资源已清理。

文件/大小/SHA256 见 [EVIDENCE-HASHES.json](EVIDENCE-HASHES.json)；私有原件仅在受限 EFS，公开摘要见 [private-evidence-digest-index.json](../../evidence/CODEX-R6-P1B0-20261030/private-evidence-digest-index.json)。**停止等待 PI，不自动重试、重刷或进入下一阶段。**
