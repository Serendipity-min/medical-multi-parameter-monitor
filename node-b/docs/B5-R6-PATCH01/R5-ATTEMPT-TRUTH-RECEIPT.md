# MPM-B5｜R5 现场全部 7 次尝试原始证据独立对账台账 (Truth Receipt)

> 审计基准：`E:\medical-monitor-node-b-precan-private\20261023\time-init-field-6cd64b90`  
> 审计提交：`64d07ff33e2fddb46a4a0570d9abfa83adbc3e02`  
> 生成时间：2026-10-30  
> 状态：`AUDIT_RECONCILED_AND_FROZEN`（保持 R5 历史 3 窗口全部 NOT_PASS / exit_code=3 原貌）  

---

## 1. 核心事实勘误总述

此前在某些报告中存在以下两项严重数据失真，特此根据底层磁盘原始 receipts 予以绝对纠正：
1. **进程退出码错误纠正**：
   - 错误说法：“中途终止的 attempt 退出码为 exit 2”。
   - **底层铁证**：在所有 4 次中途终止的尝试中，`supervisor-private.json` 记录的 `worker_exit_code` 和 `supervisor_exit_code` 均为 `1`，`joint-receipt-private.json`（若生成）中的 `exit_code` 亦为 `1`。底层系统中从未产生过进程退出码 `2`。
2. **START 发送计数错误纠正**：
   - 错误说法：“部分终止尝试没有发送 START，START=0”。
   - **底层铁证**：在全部 7 次尝试中，`joint/ARM_ATTEMPT.json` 均准确记录了 `bytes: 8`（即发送了 1 次完整的 `B5START\n` 指令，SHA256: `a3749dc530005c1da18ac057f4782dfee4556aef3ccce669b68dd4fab2023db2`）。不存在 START=0 的情况。

---

## 2. R5 全部 7 次尝试精确逐项对账总表

| 序号 | 现场目录名称 | 业务模式 | 启动时刻 (UTC_ms / mono) | Worker 退出码 | Supervisor 退出码 | Joint 退出码 | 正式联评 退出码 | B5START 发送字节 | 实际停止/终止原因 | 联评失败项或结论 |
|---|---|---|---|---|---|---|---|---|---|---|
| **1** | `owner-observed-ECG60-R5-55d99a50` | `ECG60` | `1793273149084`<br>(mono: 1007195.187) | **0** | **0** | **0** | **3** | **8 字节**<br>(1次) | 完成 420s 业务硬停与 300s 窗口评价 | **NOT_PASS**<br>(5 项失败：`BROKER_NOT_MOCK`、`C_DIAGNOSTIC_GAP`、`C_NEW_REALTIME_LOSS_OR_EXPIRY`、`ECG_WSS_BATCH_MISSING`、`WSS_TARGET_CHANNEL_INVALID`) |
| **2** | `owner-observed-TEMP_OBJECT-R5-75cf9999` | `TEMP_OBJECT` | `1793274322242`<br>(mono: 1008368.343) | **1** | **1** | **1** | *无 (未完成)* | **8 字节**<br>(1次) | `G3_C_STOPPED_BEFORE_EVALUATION_END`<br>(SNTP 校验不匹配触发停机) | **ABORTED**<br>(在进入评价前由主管进程主动中止) |
| **3** | `owner-observed-TEMP_OBJECT-R5-cff28389` | `TEMP_OBJECT` | `1793323487931`<br>(mono: 1057535.031) | **1** | **1** | **1** | *无 (未完成)* | **8 字节**<br>(1次) | `G3_C_UNEXPECTED_REBOOT`<br>(Gateway-C 在约 37s 处发生意外重启) | **ABORTED**<br>(下位机硬件异常重启触发安全断开) |
| **4** | `owner-observed-TEMP_OBJECT-R5-f75b446e` | `TEMP_OBJECT` | `1793323756314`<br>(mono: 1057803.343) | **1** | **1** | **1** | *无 (未完成)* | **8 字节**<br>(1次) | `G3_C_STOPPED_BEFORE_EVALUATION_END`<br>(SNTP 校验不匹配触发停机) | **ABORTED**<br>(在进入评价前由主管进程主动中止) |
| **5** | `owner-observed-TEMP_OBJECT-R5-6104c2e6` | `TEMP_OBJECT` | `1793324048419`<br>(mono: 1058095.375) | **0** | **0** | **0** | **3** | **8 字节**<br>(1次) | 完成 420s 业务硬停与 300s 窗口评价 | **NOT_PASS**<br>(1 项失败：`B_TEMP_FRESH_SOURCE`，29/600 帧 age < -10ms) |
| **6** | `owner-observed-RR15-R5-7058a3bd` | `RR15` | `1793325036561`<br>(mono: 1059083.312) | **1** | **1** | *未生成* | *无 (未完成)* | **8 字节**<br>(1次) | `G3_COMMON_NOT_READY_IN_60S`<br>(授权卡写30bpm与配置15bpm矛盾导致超时) | **ABORTED**<br>(60秒共同就绪超时，主管强杀工作进程) |
| **7** | `owner-observed-RR15-R5-5bb61eef` | `RR15` | `1793325606946`<br>(mono: 1059653.593) | **0** | **0** | **0** | **3** | **8 字节**<br>(1次) | 完成 420s 业务硬停与 300s 窗口评价 | **NOT_PASS**<br>(3 项失败：`B_RR_VALID15_HR_INVALID`、`RR_EXPECTED_INVALID`、`RR_BROKER_COVERAGE`) |

---

## 3. 原始 JSON 关键字段摘录

### 3.1 尝试 1 (ECG60-W01: `owner-observed-ECG60-R5-55d99a50`)
- `ARM_ATTEMPT.json`:
  ```json
  {
    "monotonic": 1007195.187,
    "UTC_ms": 1793273149084,
    "bytes": 8,
    "command_sha256": "a3749dc530005c1da18ac057f4782dfee4556aef3ccce669b68dd4fab2023db2",
    "authorization_scope": "B5_FINAL_ECG60_R5"
  }
  ```
- `joint-receipt-private.json`: `exit_code: 0`, `status: "G3_FILES_CAPTURED_REVIEW_PENDING"`
- `formal-ECG60-review-private.json`: `exit_code: 3`, `status: "B5_SEPARATE_ECG60_NOT_PASS"`

### 3.2 尝试 3 (TEMP-A02: `owner-observed-TEMP_OBJECT-R5-cff28389`)
- `ARM_ATTEMPT.json`: `bytes: 8`, `UTC_ms: 1793323487931`
- `joint/STOP`: `{"reason": "G3_C_UNEXPECTED_REBOOT"}`
- `supervisor-private.json`: `worker_exit_code: 1`, `supervisor_exit_code: 1`
- `joint-receipt-private.json`: `exit_code: 1`, `status: "STOP"`

### 3.3 尝试 5 (TEMP-W01: `owner-observed-TEMP_OBJECT-R5-6104c2e6`)
- `ARM_ATTEMPT.json`: `bytes: 8`, `UTC_ms: 1793324048419`
- `joint-receipt-private.json`: `exit_code: 0`, `status: "G3_FILES_CAPTURED_REVIEW_PENDING"`
- `formal-TEMP_OBJECT-review-private.json`: `exit_code: 3`, `status: "B5_SEPARATE_TEMP_OBJECT_NOT_PASS"`, `failures: ["B_TEMP_FRESH_SOURCE"]`

### 3.4 尝试 6 (RR15-A01: `owner-observed-RR15-R5-7058a3bd`)
- `ARM_ATTEMPT.json`: `bytes: 8`, `UTC_ms: 1793325036561`
- `joint/STOP`: `{"reason": "G3_COMMON_NOT_READY_IN_60S"}`
- `supervisor-private.json`: `supervisor_reason: "COMMON_READY_DEADLINE"`, `worker_exit_code: 1`, `supervisor_exit_code: 1`
- `joint-receipt-private.json`: 进程在生成该文件前即被超时终止，文件缺失，记为 `None`。

### 3.5 尝试 7 (RR15-W01: `owner-observed-RR15-R5-5bb61eef`)
- `ARM_ATTEMPT.json`: `bytes: 8`, `UTC_ms: 1793325606946`
- `joint-receipt-private.json`: `exit_code: 0`, `status: "G3_FILES_CAPTURED_REVIEW_PENDING"`
- `formal-RR15-review-private.json`: `exit_code: 3`, `status: "B5_SEPARATE_RR15_NOT_PASS"`

---

## 4. 结论与审计效力

1. R5 期间发生的 7 次硬件尝试中，有且仅有 3 次进入了完整的 420 秒评价窗并生成了正式审查器输出，其结果均为 `exit_code=3 / NOT_PASS`。
2. 其余 4 次尝试均因底层环境、SNTP、意外重启或配置矛盾在 60 秒内被主管程序安全中止，退出码均为 `1`（`ABORTED`）。
3. 历史记录不可篡改，本台账作为 R5 硬件尝试的唯一最终对账原件归档。
