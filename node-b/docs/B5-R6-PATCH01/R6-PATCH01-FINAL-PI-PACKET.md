# MPM-B5｜R6-PATCH01 最终交付与 PI 独立复核数据包 (Executive Summary Packet)

> 合同编号：`MPM-B5-R6-P0B-PI-NOGO-PATCH01-R1`  
> 裁定日期：2026-10-30  
> 审查基线：`Serendipity-min/medical-multi-parameter-monitor`  
> 经 GitHub 核实的唯一真实基线提交：`64d07ff33e2fddb46a4a0570d9abfa83adbc3e02`  
> 本轮工作分支：`patch/b5-r6-patch01-20261030`  
> 执行方：Gemini（Antigravity）／审核方：PI  
> **当前授权级别：仅离线证据纠正、主机工具整改、Node-B 候选源码/离线编译/仿真回归。实板操作仍为严格 NO-GO。**  

---

## 1. 合同执行与阻断项关闭综述

执行方已严格按照 PI 签发的《MPM-B5-R6-P0B-PI-NOGO-AND-PATCH01-CONTRACT.md》要求，全面闭合 `BLOCK-01` 至 `BLOCK-08` 全部 8 项阻断点，未发生任何实板上电、预检、RESET、B5START、Flash 擦写或云端变更。

### 1.1 八大阻断项闭合简述
1. **BLOCK-01 (Git SHA 纠正)**：确认 `64d07ff33e2fddb46a4a0570d9abfa83adbc3e02` 为唯一真实基线，废止笔误的 `64d07ff388e6...`；在独立分支 `patch/b5-r6-patch01-20261030` 上开展全部工作。
2. **BLOCK-02 (消除自引用哈希)**：设立独立哈希清单 `R6-EVIDENCE-HASHES.json`，使用原始二进制字节计算 SHA256，所有被校验文档保持静态冻结。
3. **BLOCK-03 (R5 尝试真相台账)**：彻底核实 EFS 原始 receipts，纠正此前将终止记录为 exit 2 和 START=0 的错误；出具 7 行精确对账总表，证实 worker 退出码均为 1，START 均为 1 次 8 字节。
4. **BLOCK-04 (R6 作用域注册)**：在 `b5_channel_profiles.py` 注册专属卡 `AUTH-B5-R6-THREE-WINDOWS.md` 与三个独立 Scope，恢复严格 `preflight <= 3600s`，通过 35 项自动化测试。
5. **BLOCK-05 (Node-B 候选微调度补丁)**：在 `build_b4_arm.py` 实现微调度切片补丁，Keil UV4 离线构建 0 错误（41012B，SHA256: `1dbbf27177caa429f037ac72c43581a519e8ff70ac6224411c9c4ffe9529432d`）；全相位扫描与多任务仿真证实 age 严格 >= -8ms（绝不低于 -10ms），250Hz ECG 与 50Hz RESP 采样零丢帧。
6. **BLOCK-06 (网络三集合解耦)**：严格区分 Broker REPLAY（6 条）、C 队列 expired（6 条）、以及 WSS 批次缺失（9 批）的三重物理实体与时间基准，否定随意混同为 Wi-Fi 物理断开的错误归因。
7. **BLOCK-07 (物理接线矩阵回归)**：严格回归 R5 现场实测基线（ECG: RA/LA/RL; RR: RA/LL/RL），出具端子与线色映射图纸，严禁私自增加 V1 导联或接地假电极。
8. **BLOCK-08 (自动化测试与分级声明)**：新增全链条正反例回归用例，明确标注测试通过状态为 `PASS_MOCK` 与 `PASS_SYNTHETIC`，绝不混淆为实板 `FIELD_PASS`。

---

## 2. 交付材料清单

本批次所有技术成果均已归档于 `node-b/docs/B5-R6-PATCH01/` 目录下：

1. `R6-PATCH01-ISSUE-LEDGER.md`：八项阻断项逐项关闭技术台账。
2. `R5-ATTEMPT-TRUTH-RECEIPT.md`：R5 现场 7 次尝试原始证据独立对账凭证。
3. `R6-SCOPE-NEGATIVE-POSITIVE-RECEIPTS.md`：主机工具作用域注册、负例回归与 Mock 准入凭证。
4. `TEMP-PATCH-CPU-REGRESSION.md`：Node-B 候选微调度补丁、Keil 离线编译与 CPU/回放验证报告。
5. `R6-PHYSICAL-MATRIX.proposed.md`：R6 物理接线与三模式工况配置草案。
6. `R6-PATCH01-FINAL-PI-PACKET.md`：本总结数据包。
7. `R6-EVIDENCE-HASHES.json`：全量交付文件独立二进制字节 SHA256 清单。

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
