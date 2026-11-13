# MPM-B5｜R6-PATCH01-FIX02 交付与 PI 独立复核数据包 (Executive Summary Packet)

> 合同编号：`MPM-B5-R6-PATCH01-FIX02｜限定交付`  
> 裁定日期：2026-10-30  
> 审查基线：`Serendipity-min/medical-multi-parameter-monitor`  
> 经 GitHub 核实的审查基线提交：`81984f4e9f5c89df56dce7691c723f6b3fea7dd6`  
> 本轮工作分支：`patch/b5-r6-patch01-20261030`  
> 执行方：Gemini（Antigravity）／审核方：PI  
> **当前授权级别：仅离线证据纠正、主机准入整改、Node-B 候选微调度构建与 CPU 仿真。实板操作仍为严格 NO-GO。**  

---

## 1. FIX02 限定交付五大结果落实总述

依据 PI 对 `81984f4e9f5c89df56dce7691c723f6b3fea7dd6` 的审查裁定意见，执行方已全面达成五项限定交付成果：

1. **R6 专用 B41012B 完整纳入主机准入体系**：
   - 在 `node-b/tools/b5_channel_profiles.py` 中定义 `B_PROFILE_R6`（`BIN_bytes: 41012`、`B_CANDIDATE_R6_BIN`、`B_ELF_R6`、`B_SYMBOLS_R6`）；
   - 在 `validate(a)` 中动态区分 `R6` 与历史版本（`R5` 及历史批次仍绑定原 40928 字节固件，保持 100% 历史确定性）。
2. **修正 RR 授权卡与工况矩阵菜单描述**：
   - 在 `node-b/docs/AUTH-B5-R6-THREE-WINDOWS.md`、`R6-PHYSICAL-MATRIX.proposed.md` 与 `b5_channel_profiles.py` 中，采用现场真实菜单名明确区分：
     - **主菜单呼吸率【RR】**：必须且只能设为 **15 bpm**（严禁设为 30 bpm！）；
     - **阻抗基准心率 / 呼吸波形周期菜单**：设为 **30 bpm**；
     - **阻抗变化量菜单**：设为 **1.5R**；
     - **窒息时间菜单**：设为 **0s**。
3. **可审计的候选源码、WCET 最坏时序预算与边界排空证明**：
   - 在 `node-b/tools/build_b4_arm.py` 与文档中严格对齐 **8 处** `text.replace` 插入点，输出真实候选源码原件 `node-b/evidence/B5-R6-PATCH01/hr_page.candidate.c`（41042 字节，SHA256: `f7e6bc7e0526...`）；
   - 建立 115200 波特率下最大切片耗时预算表（单切片最长 3.67ms $\le 4.5\text{ ms}$）；
   - 完成 1s + 10s + 30s + 60s + 200ms 五大任务同毫秒重合触发的 WCET 极限压力仿真：EcgQueue 队列滞留深度严格 $\le 1$ 帧，最坏 age 为 **-7.5 ms**（$\ge -8.0\text{ ms} > -10.0\text{ ms}$），0 越界；
   - 证明此前 149,999 帧系仿真末端在 599999.0ms 退出的离散步长边界伪象；加入末端边界排空后，总采样帧数严格达到 **150,000 / 150,000 帧**（100.000% 理论匹配，零丢帧）。
4. **修正历史审计台账与统一 ECG WSS 批次口径**：
   - 在 `R5-ATTEMPT-TRUTH-RECEIPT.md` 与问题台账中，按 `formal-RR15-review-private.json` 原件纠正 RR15 正式联评失败项为 3 项：`B_RR_VALID15_HR_INVALID`、`HR_EXPECTED_INVALID`、`WSS_TARGET_CHANNEL_INVALID`；彻底删除此前笔误的 `RR_EXPECTED_INVALID` 与 `RR_BROKER_COVERAGE`；
   - 统一 ECG WSS 批次缺失口径：Broker 期望 750 批，评价期内实际接收 740 批，评价期后另接收 1 批（会话总接收 741 批）；评价期内严格缺失 **10 批**（`750 - 740 = 10`）。
5. **机器互锁阻断实机误执行 (Machine Interlock)**：
   - 在 `b5_channel_profiles.py` 的 `validate()` 中硬编码机器互锁：若 `version == 'R6'` 且未显式指定 `execution_mode == 'OFFLINE_MOCK'`，强制核验由 PI 签署的 Gate F 冻结清单（`R6-FREEZE-MANIFEST.json`）；
   - 若未签署清单或未授权实机执行，直接抛出 `CHANNEL_R6_FIELD_EXECUTION_BLOCKED_UNSIGNED_FREEZE`，彻底杜绝仅凭 `owner_approved=True` 误触发实机操作；
   - 增加负向拦截测试用例 `test_r6_field_execution_without_signed_freeze_blocked`，36 项单元测试全部通过。

---

## 2. 交付材料清单

本批次所有技术成果均已归档于 `node-b/docs/B5-R6-PATCH01/` 目录下：

1. `R6-PATCH01-ISSUE-LEDGER.md`：FIX02 专项问题逐项关闭技术台账。
2. `R5-ATTEMPT-TRUTH-RECEIPT.md`：R5 现场 7 次尝试原始证据独立对账凭证（含纠正后的 RR15 真实失败项）。
3. `R6-SCOPE-NEGATIVE-POSITIVE-RECEIPTS.md`：B41012B 准入集成、机器互锁负例回归与阳性 Mock 凭证。
4. `TEMP-PATCH-CPU-REGRESSION.md`：8 处插入点对齐说明、WCET 最坏时序预算、重合风暴压力仿真及 150,000 帧边界证明。
5. `R6-PHYSICAL-MATRIX.proposed.md`：R6 物理接线与三模式工况配置草案（含 SKX 呼吸防错红线说明）。
6. `AUTH-B5-R6-THREE-WINDOWS.md`：R6 授权卡（明确区分 RR=15bpm 与周期 30bpm，增加机器互锁要求）。
7. `hr_page.candidate.c`：真实注入 8 处协作点后的候选源码原件。
8. `R6-PATCH01-FINAL-PI-PACKET.md`：本总结数据包。
9. `R6-EVIDENCE-HASHES.json`：全量交付文件独立二进制字节 SHA256 清单。

---

## 3. 下一阶段准入建议与双重门禁建议

执行方建议维持 PI 合同规定的双重授权门禁路线，严禁跳步：

1. **Gate F（冻结准入评审）**：
   - 审查执行方本次提交的 `patch/b5-r6-patch01-20261030` 分支全部离线材料；
   - 确认 Node-B 候选固件指纹（41012B，SHA256: `1dbbf27177...`）与主机 R6 Scope 注册；
   - 由 PI 明确签署正式的 `R6-FREEZE-MANIFEST.json`。
2. **Gate P（实板现场预检准入）**：
   - 另行签发 `R6-P1` 只读预检合同，时效窗口严格限制在 3600 秒内；
   - 进行 B/C 板物理只读回读，核对硬件指纹；
   - 签发三张独立的一次性现场执行卡（`R6-P2-TEMP`、`R6-P2-RR`、`R6-P2-ECG`），每卡严格仅限 1 次 RESET 与 1 次 B5START。

---

## 4. 强制裁定状态声明块 (Section 6 Closing Status Block)

依据合同要求，如实呈报当前裁定状态：

```text
R6_P0B_DOCUMENT_DELIVERY       = RECEIVED_WITH_OPEN_FINDINGS
R6_P0B_PI_REVIEW              = NO_GO_FIELD
R5_HISTORICAL_RESULTS         = PRESERVE_EXIT_3_ALL_THREE
R6_PATCH01_OFFLINE_SCOPE      = OFFLINE_COMPLETED_FOR_PI_REVIEW
R6_SCOPE_RUNTIME              = REGISTERED_PROPOSED_OFFLINE
R6_TEMP_PATCH                = CANDIDATE_BUILT_AND_SIMULATED
R6_FREEZE                    = PROPOSED_NOT_FROZEN
R6_P1_HARDWARE_PREFLIGHT      = NOT_AUTHORIZED
R6_P2_TEMP_OBJECT            = NOT_AUTHORIZED
R6_P2_RR15                   = NOT_AUTHORIZED
R6_P2_ECG60                  = NOT_AUTHORIZED
NEW_B5START                  = 0
NEW_RESET                    = 0
NEW_FLASH_WRITE              = 0
PRODUCTION_CLOUD_CHANGE      = 0
B5_STAGE_CLOSURE             = DENIED
```

> **执行方最终声明**：离线整改任务已全部完成，所有证据可机器复算。未接到 PI 签发下一阶段正式书面授权前，执行方严格保持待机状态，不执行任何实板操作。
