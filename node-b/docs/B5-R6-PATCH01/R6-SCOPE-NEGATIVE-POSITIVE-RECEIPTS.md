# MPM-B5｜R6 作用域注册、B41012B 身份准入、机器互锁与阳性 Mock 凭证

> 文档编号：`MPM-B5-R6-SCOPE-RECEIPTS-V2`  
> 基线提交：`81984f4e9f5c89df56dce7691c723f6b3fea7dd6`  
> 工作分支：`patch/b5-r6-patch01-20261030`  
> 测试工具：Python 3.11.9, unittest / pytest  
> 状态：`OFFLINE_MOCK_VERIFIED_NO_HARDWARE`（离线验证通过，严格禁止实机执行）  

---

## 1. R6 主机工具准入与 B41012B 身份集成设计

在 `node-b/tools/b5_channel_profiles.py` 中，完整集成 R6 专用 B41012B 候选固件指纹与机器门禁互锁，同时严格保留历史 R5 绑定不变：

```python
FINAL_CARD_R6 = g.ROOT / 'node-b/docs/AUTH-B5-R6-THREE-WINDOWS.md'
FINAL_SCOPES_R6 = {
    'ECG60': 'B5_FINAL_ECG60_R6',
    'TEMP_OBJECT': 'B5_FINAL_TEMP_OBJECT_R6',
    'RR15': 'B5_FINAL_RR15_R6'
}

# 历史基线 Node-B 固件指纹 (40928 字节)
B_PROFILE = {'BIN_bytes': 40928, 'BIN_sha256': update.CANDIDATE_BIN, 'slots': 0x2000216c,
             'UART_ring': 0x20004878, 'RAM': temp.RAM}
B_ELF = 'e0433f3246e3e9aa422365834ceeae7e2e3c68360164a8bb583d7a45f4700ed1'
B_SYMBOLS = '4c3e2ab42a3379c615924d8af4deb7e81207554bc1ef3d9e9ac79e977c9ecfcf'

# R6 候选微调度 Node-B 固件指纹 (41012 字节)
B_CANDIDATE_R6_BIN = '1dbbf27177caa429f037ac72c43581a519e8ff70ac6224411c9c4ffe9529432d'
B_ELF_R6 = 'e11219c4de3718fc0832a6e6863ec9645836300197f36503cc13d8e8bd9923b7'
B_SYMBOLS_R6 = '07e2166e9a145bcbdbb592b475b789cf55553ee38cf97c1dd5fcf9aebe7853f8'
B_PROFILE_R6 = {'BIN_bytes': 41012, 'BIN_sha256': B_CANDIDATE_R6_BIN, 'slots': 0x2000216c,
                'UART_ring': 0x20004878, 'RAM': temp.RAM}
```

### 1.1 动态准入与机器互锁规则 (Machine Interlock)
1. **固件身份动态切换**：在 `validate(a)` 中依据当前版本动态绑定：
   - 当 `version == 'R6'` 时，强制核验 `BIN_bytes == 41012`、`B_CANDIDATE_R6_BIN`、`B_ELF_R6` 及 `B_SYMBOLS_R6`，并将 `bundle['_B_profile']` 注入为 `B_PROFILE_R6`；
   - 当 `version != 'R6'` 时，严格沿用历史 `B_PROFILE`（40928 字节）与原版 ELF/符号表，保证历史审计与回放 100% 确定性。
2. **机器互锁阻断实机误执行**：
   - 授权卡声明 `status=PROPOSED_NOT_FROZEN`；
   - `validate()` 程序硬编码互锁：当 `version == 'R6'` 且未显式指定 `execution_mode == 'OFFLINE_MOCK'` 时，必须读取并核验由 PI 正式书面签署的 `R6-FREEZE-MANIFEST.json`（状态必须为 `FROZEN_GATE_F_SIGNED` 且 `pi_signature` 有效）；
   - 若清单未签署或未授权现场执行，机器程序直接抛出 `CHANNEL_R6_FIELD_EXECUTION_BLOCKED_UNSIGNED_FREEZE` 阻断执行，防止仅凭 `owner_approved = true` 触发实机误操作。
3. **预检时效恢复 3600 秒**：
   `version == 'R6'` 强制恢复 `preflight <= 3600s` 硬门槛，拒绝继承 R5 86400 秒临时特例。

---

## 2. 负例回归测试集（Negative Regression Tests）

在 `node-b/tests/test_b5_channel_profiles.py` 中部署并执行以下反例回归用例：

| 用例 ID | 测试目标 | 测试输入条件 | 预期异常 | 实际测试输出 | 判定 |
|---|---|---|---|---|---|
| `NEG-R6-01` | 跨模式作用域混淆拦截 | Scope=`B5_FINAL_ECG60_R6`, Profile=`RR15` | `ValueError: CHANNEL_FINAL_OBJECT` | `ValueError: CHANNEL_FINAL_OBJECT` | **PASS** |
| `NEG-R6-02` | 伪造授权卡拦截 (R5卡配R6 Scope) | Scope=`B5_FINAL_ECG60_R6`, Card=`AUTH-B5-GEMINI-R5-THREE-WINDOWS.md` | `ValueError: CHANNEL_FINAL_CARD` | `ValueError: CHANNEL_FINAL_CARD` | **PASS** |
| `NEG-R6-03` | 伪造授权卡拦截 (R6卡配R5 Scope) | Scope=`B5_FINAL_ECG60_R5`, Card=`AUTH-B5-R6-THREE-WINDOWS.md` | `ValueError: CHANNEL_FINAL_CARD` | `ValueError: CHANNEL_FINAL_CARD` | **PASS** |
| `NEG-R6-04` | 预检超时拦截 (验证3600s硬上限) | `observed_unix = now - 3605s` (超时5秒，但在86400s内) | `ValueError: CHANNEL_C_PREFLIGHT` | `ValueError: CHANNEL_C_PREFLIGHT` | **PASS** |
| `NEG-R6-05` | 缺少源硬停要求拦截 | `require_source_STOP_state = False` | `ValueError: CHANNEL_FINAL_OBJECT` | `ValueError: CHANNEL_FINAL_OBJECT` | **PASS** |
| `NEG-R6-06` | **机器互锁阻断实机执行** | 未提供签署冻结清单且未声明 `OFFLINE_MOCK` | `ValueError: CHANNEL_R6_FIELD_EXECUTION_BLOCKED_UNSIGNED_FREEZE` | `ValueError: CHANNEL_R6_FIELD_EXECUTION_BLOCKED_UNSIGNED_FREEZE` | **PASS** |

---

## 3. 阳性 Mock 全流程准入测试（Positive Mock Admissions）

| 用例 ID | 测试目标 | 测试配置条件 | 预期返回 | 实际测试输出 | 判定 |
|---|---|---|---|---|---|
| `POS-R6-01` | **R6 B41012B 候选全链条 Mock 准入** | Scope=`B5_FINAL_ECG60_R6`, Card=`AUTH-B5-R6-THREE-WINDOWS.md`, `execution_mode='OFFLINE_MOCK'`, 候选 41012B 镜像指纹 | 返回 `(bundle, site)` 且 `bundle['_B_profile']['BIN_bytes'] == 41012` | 顺利返回，`_B_profile` 字节数为 41012，哈希匹配候选，`site['C_USB_port'] == 'COM6'` | **PASS_MOCK** |
| `POS-R6-02` | **R5 历史基线与 R6 隔离性验证** | 分别执行 R5 与 R6 阳性准入 | R5 注入 `BIN_bytes: 40928`；R6 注入 `BIN_bytes: 41012` | 严格分离，两版本互不影响 | **PASS_MOCK** |

---

## 4. 自动化测试执行回执

执行命令：`python -m unittest node-b/tests/test_b5_channel_profiles.py`

```text
....................................
----------------------------------------------------------------------
Ran 36 tests in 0.056s

OK
```

> **重要审计声明**：上述 36 项测试为离线 Mock 与工具链单元测试，全面验证主机评测与准入工具已具备真实的 B41012B 识别能力与未签署清单机器阻断能力；严禁以 `PASS_MOCK` 替代实板物理执行准入。在 PI 签署正式 Gate F 冻结清单前，实板操作严格保持 NO-GO。
