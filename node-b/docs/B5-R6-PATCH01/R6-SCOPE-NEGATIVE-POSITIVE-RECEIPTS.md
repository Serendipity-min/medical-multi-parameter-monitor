# MPM-B5｜R6 作用域注册、负例回归与阳性 Mock 准入凭证

> 文档编号：`MPM-B5-R6-SCOPE-RECEIPTS-V1`  
> 基线提交：`64d07ff33e2fddb46a4a0570d9abfa83adbc3e02`  
> 工作分支：`patch/b5-r6-patch01-20261030`  
> 测试工具：Python 3.11.9, pytest 9.1.1  
> 状态：`OFFLINE_MOCK_VERIFIED_NO_HARDWARE`  

---

## 1. R6 主机工具作用域注册设计

在 `node-b/tools/b5_channel_profiles.py` 中，完成对 R6 阶段的独立主机准入绑定：

```python
FINAL_CARD_R6 = g.ROOT / 'node-b/docs/AUTH-B5-R6-THREE-WINDOWS.md'
FINAL_SCOPES_R6 = {
    'ECG60': 'B5_FINAL_ECG60_R6',
    'TEMP_OBJECT': 'B5_FINAL_TEMP_OBJECT_R6',
    'RR15': 'B5_FINAL_RR15_R6'
}
```

### 1.1 关键门禁隔离规则
1. **正交隔离**：R6 作用域集合与历史批次（R1, R2, R3, R4, R4TC, R4D, R4TB, R4TI, R5）完全正交，互不包含。
2. **专属授权卡绑定**：R6 作用域必须绑定到唯一的 `AUTH-B5-R6-THREE-WINDOWS.md`，使用旧卡或篡改卡名均被立即拒绝。
3. **时效恢复严格 3600 秒**：
   ```python
   time.time() - cp['observed_unix'] <= (86400 if version == 'R5' else 3600)
   ```
   R5 阶段针对跨夜断电的 86400 秒临时特例被严格限定在 `version == 'R5'`，在 `version == 'R6'` 下强制恢复为标准的 3600 秒上限，杜绝特例无限制蔓延。
4. **运行状态默认禁用**：授权卡声明 `status=PROPOSED_NOT_FROZEN`，`field_execution_authorized=false`。

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

---

## 3. 阳性 Mock 全流程准入测试（Positive Mock Admissions）

| 用例 ID | 测试目标 | 测试配置条件 | 预期返回 | 实际测试输出 | 判定 |
|---|---|---|---|---|---|
| `POS-R6-01` | R6 完整凭证全链条 Mock 准入校验 | Scope=`B5_FINAL_ECG60_R6`, Card=`AUTH-B5-R6-THREE-WINDOWS.md`, Preflight 新鲜度 50 秒，校验和完整对齐 | 返回 `(bundle, site)` 且注入 `_B_profile` | 顺利返回，`bundle['_B_profile']` 正常注入，`site['C_USB_port'] == 'COM6'` | **PASS_MOCK** |

---

## 4. 自动化测试执行回执 (Pytest Execution Log)

```text
============================= test session starts =============================
platform win32 -- Python 3.11.9, pytest-9.1.1, pluggy-1.6.0
rootdir: E:\medical-monitor-node-b5-cloud
configfile: pyproject.toml
plugins: anyio-4.12.1
collected 35 items

node-b\tests\test_b5_channel_profiles.py ............................... [ 88%]
....                                                                     [100%]

============================= 35 passed in 0.59s ==============================
```

> **重要审计声明**：上述测试为离线 Mock 与工具链单元测试，验证主机评测与准入工具已具备 R6 识别与门禁防护能力；严禁以 `PASS_MOCK` 替代实板物理执行准入。未获 PI 正式书面批准前，实板操作严格保持 NO-GO。
