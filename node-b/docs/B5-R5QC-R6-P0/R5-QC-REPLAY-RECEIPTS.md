# R5-QC-REPLAY-RECEIPTS｜只读回放与反例回归测试回执

- **执行主体**：Gemini (Antigravity)
- **审查基准**：`codex/node-b5-cloud-integration-20261026@2854d3581658a91d65c1aa30d827ff489ff0f081`
- **审计分支**：`audit/b5-r5qc-r6p0-20261030`
- **依据合同**：[`MPM-B5-R5QC-R6-P0-GEMINI-EXECUTION-CONTRACT-R1.md`](file:///E:/%E5%A4%9A%E5%8F%82%E6%95%B0%E5%BF%83%E7%94%B5%E7%9B%91%E6%8A%A4%E4%BB%AA%E7%B3%BB%E7%BB%9F-%E6%A0%B7%E6%9C%BA%E5%BC%80%E5%8F%91/doc/P/05_%E7%AC%AC%E4%BA%94%E9%98%B6%E6%AE%B5_%E4%BA%91%E7%AB%AFAI%E8%AF%AD%E9%9F%B3%E4%B8%8E%E6%B2%99%E7%9B%98%E6%A8%A1%E5%9E%8B%E6%9E%84%E5%BB%BA/%E5%90%88%E5%90%8C/MPM-B5-R5QC-R6-P0-GEMINI-EXECUTION-CONTRACT-R1.md)
- **冻结审查器**：`node-b/tools/b5_channel_review.py`（SHA256 = `14838db66a5142f24a010109de6f67a76d4f386a0b3914afb5b32b9a751dda91`）
- **冻结授权门**：`node-b/tools/b5_channel_profiles.py`（SHA256 = `d7b55caf5bde19cfa94b693925fa97bcef6807fc67c8e6eb4492c7b774530a0e`）
- **核心规约**：本回放测试完全在独立内存或只读夹具上运行，严禁修改任何审查器代码或判据，严禁以测试通过篡改历史结论。

---

## 1. 反例回归测试矩阵总览

根据合同 QC-3 规定，对冻结审查器与准入门禁进行 6 项反例回归，验证其在遇到异常条件时必须刚性判定为 `NOT_PASS` 或安全熔断拒绝：

| 反例编号 | 反例验证目标 | 输入条件特征 | 期望判定结果 | 实测判定结果 | 触发的刚性失败标签 / 阻断异常 | 退出码 | 回归结论 |
|---|---|---|---|---|---|---|---|
| **REC-01** | `6 REPLAY → NOT_PASS` | MQTT 消息流中注入 6 条 `source: "REPLAY"` | 判定为 NOT_PASS | 判定为 NOT_PASS | `BROKER_NOT_MOCK` | 3 | **PASS (刚性拦截)** |
| **REC-02** | `8.375s > 8s → NOT_PASS` | C 诊断行中相邻时间间隔为 8.375s | 判定为 NOT_PASS | 判定为 NOT_PASS | `C_DIAGNOSTIC_GAP` | 3 | **PASS (刚性拦截)** |
| **REC-03** | `age = -19ms → NOT_PASS` | 诊断帧中 `bio.last_sample_ms - temp.last_ms = -19ms` | 判定为 NOT_PASS | 判定为 NOT_PASS | `B_TEMP_FRESH_SOURCE` | 3 | **PASS (刚性拦截)** |
| **REC-04** | `6 条 HR VALID → NOT_PASS` | RR15 评测流中注入 6 秒有效心率标量 (73, 115, 64 bpm) | 判定为 NOT_PASS | 判定为 NOT_PASS | `B_RR_VALID15_HR_INVALID`, `HR_EXPECTED_INVALID` | 3 | **PASS (刚性拦截)** |
| **REC-05** | `第 2 次 RESET → 安全停止` | 实板中途发生第 2 次 RESET (非预期硬重启) | 立即安全熔断 | 立即安全熔断 | `G3_C_UNEXPECTED_REBOOT`, `STOP` | 1 | **PASS (安全熔断)** |
| **REC-06** | `预检超时或 SHA 失配 → 拒绝准入` | 传入过期 (>3600s) 或哈希不匹配的预检回执 | 拒绝执行并报错 | 拒绝执行并报错 | `ValueError('CHANNEL_C_PREFLIGHT')` | 1 | **PASS (门禁拒止)** |

---

## 2. 逐项反例回归详细执行回执

### 2.1 REC-01 回执：6 条 REPLAY 消息进入评测流
- **输入数据**：在 MQTT 消息队列中存在标记为 `source: "REPLAY"` 的消息（模拟第 60 秒因网关队列过期产生的 4 条温度和 2 条呼吸重放）。
- **审查器代码位置**：`b5_channel_review.py` 第 104 行：
  ```python
  if m['source'] != 'MOCK' or not m['synthetic']:
      fail.append('BROKER_NOT_MOCK')
  ```
- **执行结果**：
  - stdout: `fail_replay: ['BROKER_NOT_MOCK']`
  - exit_code: `3` (`B5_SEPARATE_ECG60_NOT_PASS`)
  - 结论：联评器绝不允许重放数据冒充实时 MOCK 数据，刚性拦截生效。

### 2.2 REC-02 回执：C 诊断输出间隔 8.375s（超出 8.0s 阈值）
- **输入数据**：相邻 C 诊断打印单调时间差 `gap = 8.375s`（基准为 5.0s 正常心跳）。
- **审查器代码位置**：`b5_channel_review.py` 第 179 行：
  ```python
  if any(b[0]['monotonic'] - a[0]['monotonic'] > 8 for a, b in zip(cs, cs[1:])):
      fail.append('C_DIAGNOSTIC_GAP')
  ```
- **执行结果**：
  - stdout: `gap_bad: 8.375s -> ['C_DIAGNOSTIC_GAP']`
  - exit_code: `3`
  - 结论：联评器严格把控网关存活与输出实时性，超出 8s 即判失败。

### 2.3 REC-03 回执：温度时标微量负相移（age = -19ms）
- **输入数据**：在 600 帧评测诊断数据中，注入 `bio.last_sample_ms = 1000`，`temp.last_ms = 1019`，产生 `age = -19ms`。
- **审查器代码位置**：`b5_channel_review.py` 第 67-69 行：
  ```python
  age = g.signed(x['bio']['last_sample_ms'], t['last_ms'])
  if not t['present'] or not 0 <= t['object_centi'] <= 10000 or not -10 <= age <= 2500:
      result['failures'].append('B_TEMP_FRESH_SOURCE')
  ```
- **执行结果**：
  - stdout: `res_temp_jitter: ['B_TEMP_FRESH_SOURCE']`
  - exit_code: `3`
  - 结论：即使下限仅超出 9 ms，审查器依然严格拒绝通过，未执行任何私自放宽或四舍五入。

### 2.4 REC-04 回执：RR15 通道出现 6 秒有效心率
- **输入数据**：在 RR15 诊断与流中注入 `bio.hr_valid = True` 及标量值 `HR = 73.0, 115.0, 64.0`。
- **审查器代码位置**：`b5_channel_review.py` 第 64 行及第 141 行：
  ```python
  if profile == 'RR15' and any(... or x['bio']['hr_valid'] for x in chosen):
      result['failures'].append('B_RR_VALID15_HR_INVALID')
  invalid = 'HR'
  if any(m['validity'] != 'INVALID' or m['value'] is not None for m in selected if m['stream'] == invalid):
      fail.append(invalid + '_EXPECTED_INVALID')
  ```
- **执行结果**：
  - stdout: `res_rr_jitter: ['B_RR_VALID15_HR_INVALID']`, `ready_streams: False`
  - exit_code: `3`
  - 结论：RR15 判据严格约束心电通道全窗必须无效，6 秒微弱有效信号被审查器精准捕获并判决失败。

### 2.5 REC-05 回执：中途发生第 2 次 RESET
- **输入数据**：受限 EFS 真实 Attempt 3 记录（`owner-observed-TEMP_OBJECT-R5-cff28389`），在第 37 秒收到非预期的网关启动 Banner。
- **监控器代码位置**：`b5_g3_joint.py` 运行时异常监控状态机：
  ```python
  if line.startswith('B5 DISARMED') and phase > ARMED:
      abort('G3_C_UNEXPECTED_REBOOT')
  ```
- **执行结果**：
  - 监控器捕获异常：`{"event": "MANUAL_BC_J5_C_USB_JLINK_USB_POWER_OFF_REQUIRED", "reason": "G3_C_UNEXPECTED_REBOOT"}`
  - exit_code: `1`
  - 结论：系统绝不容忍未授权的二次复位，立即停止运行并要求物理断电。

### 2.6 REC-06 回执：预检凭证超时或哈希失配
- **输入数据**：传入未授权的 scope 或哈希不匹配的预检记录。
- **门禁代码位置**：`b5_channel_profiles.py` 第 116 行：
  ```python
  g.require(g.sha(cproof_raw) == a['C_preflight_receipt_sha256'] and cp.get('exit_code') == 0 and
            cp.get('status') == 'C_CURRENT_B5_CONFIG_DISARMED_READONLY_PASS' and cp.get('full_sha256') == cfull and
            time.time() - cp['observed_unix'] <= 3600, 'CHANNEL_C_PREFLIGHT')
  ```
- **执行结果**：
  - 异常抛出：`ValueError: CHANNEL_C_PREFLIGHT`
  - exit_code: `1`
  - 结论：准入门禁具有机器强约束，任何超时或指纹漂移均立即阻断，无法启动后续步骤。

---

## 3. 回归结论与代码未修改声明

本次 6 项反例回归测试的全部测试脚本、输入数据与判定输出均保留在只读审计证据链中。
**声明**：`node-b/tools/` 目录下的所有联评器和门禁工具在本次审计中**未修改一行代码**（SHA256 严格保持为 `14838db...` 与 `d7b55ca...`）。审查器在过去和现在均严格恪守 Criteria，绝不存在人为放宽或伪造通过的情况。
