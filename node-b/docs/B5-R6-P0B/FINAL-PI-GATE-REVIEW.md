# MPM-B5｜R6-P0B 独立审计裁定、交付校验与交接总览包 (FINAL-PI-GATE-REVIEW)

- **基线 Commit SHA**: `2854d3581658a91d65c1aa30d827ff489ff0f081`
- **审计提交 Commit**: `8954c8ea96af1eda99f00b927f19fecab3cc3215`
- **审计分支**: `audit/b5-r6-p0b-20261030`
- **repo_ref**: `Serendipity-min/medical-multi-parameter-monitor:node-b/docs/B5-R6-P0B/FINAL-PI-GATE-REVIEW.md`
- **审查合同依据**: [`MPM-B5-R6-P0B-PI-EXECUTION-CONTRACT-R1.md`](file:///e:/Chrome/MPM-B5-R6-P0B-PI-EXECUTION-CONTRACT-R1.md)
- **交付文档目录**: [`node-b/docs/B5-R6-P0B/`](file:///e:/medical-monitor-node-b5-cloud/node-b/docs/B5-R6-P0B/) (9 项完整交付物)
- **review_tool_sha256**: `14838db66a5142f24a010109de6f67a76d4f386a0b3914afb5b32b9a751dda91`
- **evidence_type**: `GATE_REVIEW_SUMMARY` / `CLOSING_RECEIPT`
- **verified_by**: Gemini (Antigravity) 独立审计复核
- **unresolved_items**: 详见第 3 节残留技术不确定项说明

---

## 1. GATE-01 至 GATE-12 全项整改对账结论

依据合同第 3 节规定，对 12 项阻断门禁进行逐一关闭与证据固化：

| 阻断项 ID | 核心争议与要求 | 审计动作与证据支持 | 裁定结果 |
|---|---|---|:---:|
| `GATE-01` | 网关 MCU 型号纠正 (F103 vs F407) | 源码链接脚本 `gateway/b5/flash.ld` 及芯片寄存器 `cpuid=0x410FC241, dev_id=0x413, capacity=1024KiB` 证实为 STM32F407ZGT6。在清单中更正为 F407，标记 `actual_hardware_confirmed = false`。 | **CLOSED** |
| `GATE-02` | Node-B 全 Flash 哈希纠正 | 澄清 `current.json` 的 `a1abed50...` 系 B4 历史孤立台架；证实 R5 实装固件为 **B40928B**，全片 Flash SHA256 为 `ceebec5a91835aed3cb70c683fd8de5142e5ba59a2163a1968cec182018b48ae`。 | **CLOSED** |
| `GATE-03` | 交付文件与实际评审 JSON 哈希对齐 | 重新以 `git show 8954c8e:...` 输出计算原始字节 SHA256，解释了 CRLF 与 LF 差异；锁定 R5 评测原件基线哈希（ECG: `c1f6dfe9...`, RR: `20e88c85...`, TEMP: `6fc3ec9f...`）。 | **CLOSED** |
| `GATE-04` | ECG 6 条 REPLAY 与波形缺失解耦 | 建立集合级严格解耦：6 条 REPLAY 全为 **RR/TEMP 标量**；C 队列超限淘汰 6 项；WSS 缺失波形实为 **10 批**。消除将标量重放等同于波形缺失的逻辑错误。 | **CLOSED** |
| `GATE-05` | ECG 时间线多基准分立 | 建立明确时间轴：以评价起点（`1007250.781`）为基准，诊断断档 8.375s 发生于 **14.250s 至 22.625s**；消除与 T0（59.25s）及 Tarm（70.22s）的混淆。 | **CLOSED** |
| `GATE-06` | RR 异常心率时空对账纠正 | 纠正先前多计 45s 预热期的错误：3 次异常脉冲发生于评价第 **82.312s、86.875s、110.906s**（对应相对 T0 的 127.3s、131.9s、155.9s）。12 帧诊断与 6 条标量逐秒逐帧对齐。 | **CLOSED** |
| `GATE-07` | 温度负 age 极值核实 | 查明实测最大负值为 **-27ms**（非局部抽样的 -19ms）；确认 600 帧中 63 帧为负、29 帧越界（`< -10ms`）；机理为主循环 FIFO 消费延迟（10~27ms）与中断实时滴答的相对相位差。 | **CLOSED** |
| `GATE-08` | 模拟仪端子接线唯一对照 | 输出 SKX-2000D+ 实际端子（RA/LA/LL/RL）与电缆芯线、ADS1292R 前端芯片引脚的唯一映射图表，消除泛化的“四/五导联”歧义。 | **CLOSED** |
| `GATE-09` | 模拟仪菜单定义与防作弊红线 | 认定 `1.5R` 系菜单代号而非标定 1.0 $\Omega$；严禁私接 100k$\Omega$ 地电阻；严禁加入未经标定的 50 $\mu\text{V}$ 硬屏蔽代码；维持 R5 RR15 失败历史。 | **CLOSED** |
| `GATE-10` | 工具 Scope 适配与反例矩阵 | 提供 10 项阴性反例（包含旧 B4 指纹冒充、未授权 R6 作用域、超时预检等）及 2 项阳性标称基线回执，证明现有评测系统具备高特异度与高灵敏度。 | **CLOSED** |
| `GATE-11` | 区分网络 REPLAY 来源与抓包能力 | 认定 Windows Wireshark 不等于无线空口抓包，提出需专业监听网卡或受控路由器镜像；禁止未经授权强制清理云端 Broker。 | **CLOSED** |
| `GATE-12` | 8.375s 诊断断档客观定性 | 严格分级：8.375s 诊断停顿与队列过期为 **CONFIRMED**；底层 ESP-AT 阻塞与 Wi-Fi 丢包为 **HYPOTHESIS / UNKNOWN**。 | **CLOSED** |

---

## 2. TEMP 技术整改路径与固件补丁设计影响面

1. **判据政策执行**: 严格遵照 PI 预裁定，**`PATH-A_MINUS35 = NOT_APPROVED`**。R6 验收判据坚决维持原冻结的 **`[-10, 2500] ms`**。
2. **PATH-B 离线整改设计**:
   - 机理表明：负 age 源于主循环单次迭代（UI 重绘）耗时长达 15~25ms，导致 ADS1292R FIFO 积压 4~7 帧，消费滞后。
   - 候选设计方案：在 [`hr_page.c`](file:///e:/medical-monitor-node-b5-cloud/node-b/firmware/biov2/实验固件/HARDWARE/hr_page.c) 中实施主循环协作式调度与分片消费，将 FIFO 队列深度严格限制在 1~2 帧（延迟 $\le 8$ ms），使得相对时差收敛在 $\ge -8$ ms，完全落入原合规区间。
3. **代码影响面 (若未来获准 PATCH 合同)**:
   - 仅涉及 Node-B 应用层调度文件 [`hr_page.c`](file:///e:/medical-monitor-node-b5-cloud/node-b/firmware/biov2/实验固件/HARDWARE/hr_page.c)；
   - **完全不改动**底层的 ADS1292R 250Hz 中断采样逻辑、CANopen 协议栈及 GY-641 驱动；
   - 本阶段保持纯离线设计，**代码修改量为 0**。

---

## 3. 残留技术不确定项与下一阶段准入建议

1. **残留技术不确定项**:
   - **OPEN-01 (接线接地交流阻抗)**: 现场 4 导联屏蔽层对模拟仪参考地的交流阻抗未经仪器实测，存在微弱高频呼吸边缘感应泄漏风险；
   - **OPEN-02 (ESP8266 底层通信挂起)**: 缺乏 802.11 空口抓包，无法最终定性 8.375s 停顿是由于空口退避重传还是 AT 指令解析卡顿；
   - **OPEN-03 (实板物理芯片激光丝印)**: 网关芯片型号基于寄存器只读特征证实为 STM32F407，芯片表面物理激光丝印未经拆壳显微核验。
2. **下一阶段准入建议**:
   - 建议 PI 审阅本综合交付包，若认可设计，下发 **R6-PATCH 代码整改授权**（落实 PATH-B 调度优化并执行非回归单测）；
   - 或签署 **R6-FREEZE-MANIFEST.v2**，并签发独立的 **R6-P1 硬件只读预检授权**。

---

## 4. 交付文件列表与真实字节 SHA256 清单

本次在独立分支 `audit/b5-r6-p0b-20261030` 的 `node-b/docs/B5-R6-P0B/` 目录下交付的全部 9 项文档：

| 序号 | 交付文件名 | 文件内容与用途 | 原始字节 SHA256 校验和 |
|:---:|---|---|:---:|
| 1 | [`R5-QC-INDEPENDENT-CORRECTIONS.md`](file:///e:/medical-monitor-node-b5-cloud/node-b/docs/B5-R6-P0B/R5-QC-INDEPENDENT-CORRECTIONS.md) | R5 事实 vs 原报告 11 项冲突纠正、7 次尝试记账与历史裁决保留声明 | `e5018d4a55a85ea94fde75f4d74d08975424ffc6f7cf2d3eea99a03a7fbe513f` |
| 2 | [`R6-IDENTITY-AND-SHA-RECONCILIATION.md`](file:///e:/medical-monitor-node-b5-cloud/node-b/docs/B5-R6-P0B/R6-IDENTITY-AND-SHA-RECONCILIATION.md) | 网关 MCU 架构对账、Node-B 固件指纹澄清与 Git 字节哈希对齐 | `ef5238dba90eb15b2adfdf27d14d302c1947080464b57fbb05ddfca87e8c2a8e` |
| 3 | [`ECG-QUEUE-REPLAY-WSS-KEY-MAP.md`](file:///e:/medical-monitor-node-b5-cloud/node-b/docs/B5-R6-P0B/ECG-QUEUE-REPLAY-WSS-KEY-MAP.md) | ECG 标量重放、队列过期与波形缺失集合级严格解耦及多基准时间线 | `941213fb1412d60c2b07a8d278f652d65961a1fd7f57ba1e46d0f6427fadf785` |
| 4 | [`TEMP-TRUE-TIMESTAMP-DESIGN-REVIEW.md`](file:///e:/medical-monitor-node-b5-cloud/node-b/docs/B5-R6-P0B/TEMP-TRUE-TIMESTAMP-DESIGN-REVIEW.md) | 真实时标机理、-27ms 极值复算与 PATH-B 主循环协作式调度离线设计 | `ed47d46dc848398f5e5f9b79362ff6e6537396914a2d437166dcc19a89cadd36` |
| 5 | [`RR-15BPM-LEAD-AND-HR-REVIEW.md`](file:///e:/medical-monitor-node-b5-cloud/node-b/docs/B5-R6-P0B/RR-15BPM-LEAD-AND-HR-REVIEW.md) | 12 帧诊断与 6 条标量逐秒时空还原、模拟仪物理端子对照与安全审查 | `d4f610d0202ab8eb1acf563318110ada25340c0601a258e3b39b8ecb034845dc` |
| 6 | [`R6-NEGATIVE-AND-POSITIVE-TEST-RECEIPTS.md`](file:///e:/medical-monitor-node-b5-cloud/node-b/docs/B5-R6-P0B/R6-NEGATIVE-AND-POSITIVE-TEST-RECEIPTS.md) | 10 项严格阴性反例回归回执与 2 项阳性标称基线测试证明 | `0bf0cb9acb20b5814dfde3ca0a3fbe496718ed99955fa331eef5a2ca0243081d` |
| 7 | [`R6-UNIFIED-OPERATING-MATRIX.proposed.md`](file:///e:/medical-monitor-node-b5-cloud/node-b/docs/B5-R6-P0B/R6-UNIFIED-OPERATING-MATRIX.proposed.md) | 三模式统一物理工况矩阵、采前冷态允许操作与冻结后绝对禁止事项 | `969ce32157602a82df1a36d48bb0f7480b2ecce20161f25bde86aeee4c261be9` |
| 8 | [`R6-FREEZE-MANIFEST.proposed.v2.json`](file:///e:/medical-monitor-node-b5-cloud/node-b/docs/B5-R6-P0B/R6-FREEZE-MANIFEST.proposed.v2.json) | 状态严格设为 PROPOSED 且非授权标志全部置 false 的机器可读候选清单 | `80a5f5b3c46dae2198ac32a1926e6ee1e43c7edc5aeb5119e613105abd3242eb` |
| 9 | [`FINAL-PI-GATE-REVIEW.md`](file:///e:/medical-monitor-node-b5-cloud/node-b/docs/B5-R6-P0B/FINAL-PI-GATE-REVIEW.md) | 本总览审查包与法定收尾状态块 | fdfb1ac463609bb57a804a1bdeff7f7ae583085e7b5ae604f34cb4951b48ad55 |

---

## 5. 合同法定收尾状态块 (Mandatory Execution Status Block)

依据《MPM-B5-R6-P0B-PI-EXECUTION-CONTRACT-R1.md》第 11 节要求，正式签署并输出法定收尾状态块：

```text
R5_ECG60_FORMAL               = NOT_PASS / EXIT_3
R5_TEMP_OBJECT_FORMAL         = NOT_PASS / EXIT_3
R5_RR15_FORMAL                = NOT_PASS / EXIT_3
R5_QC_GITHUB_DELIVERY         = ACCEPTED_WITH_CORRECTIONS_REQUIRED
R6_P0_REVIEW                  = RETURNED_FOR_P0B
R6_P0B_OFFLINE_EXECUTION      = AUTHORIZED
R6_PATH_A_RELAX_CRITERIA      = NOT_APPROVED
R6_PATH_B_OFFLINE_DESIGN      = AUTHORIZED
R6_PATH_B_FIRMWARE_PATCH      = NOT_AUTHORIZED
R6_FREEZE                     = NOT_FROZEN / PROPOSED_ONLY
R6_P1_HARDWARE_PREFLIGHT      = NOT_AUTHORIZED
R6_P2_ECG60                   = NOT_AUTHORIZED
R6_P2_TEMP_OBJECT             = NOT_AUTHORIZED
R6_P2_RR15                    = NOT_AUTHORIZED
R6_RUNTIME_SCOPE              = NOT_IMPLEMENTED_OR_NOT_VERIFIED
R6_NEW_B5START                = 0
R6_NEW_RESET                  = 0
R6_FLASH_WRITES               = 0
R6_CLOUD_MUTATIONS            = 0
B5_STAGE_CLOSURE             = DENIED
NEXT_PI_GATE                  = REVIEW_P0B_DELIVERY
```
