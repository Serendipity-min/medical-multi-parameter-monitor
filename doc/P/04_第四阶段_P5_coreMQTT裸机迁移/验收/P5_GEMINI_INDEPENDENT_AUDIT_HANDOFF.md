# P5_GEMINI_INDEPENDENT_AUDIT_HANDOFF · 真实结果回执

> **审计执行方：** Gemini / Antigravity（本机独立审计代理）  
> **审计合同：** MPM-P5-GEMINI-INDEPENDENT-AUDIT-20261009（依据《Gemini 独立全量功能测试与安全复核执行合同 v1.0》）  
> **审计性质：** 独立第三方功能重跑、安全门禁执行与静态代码深度交叉复核；**不代替**项目负责人的最终 PR 合并决议。

---

## A. 精确身份与范围

```ini
P5_GEMINI_INDEPENDENT_AUDIT_HANDOFF
DATE_UTC = 2026-10-09T11:58:00Z
TARGET_SHA = d1e7388a91149a7c66e6cf1a5df7321bbb8eab12
BASE_SHA = 8dee339491cfd4edc468bb9451511d421f26db5e
PR6_HEAD_AT_START = d1e7388a91149a7c66e6cf1a5df7321bbb8eab12
PR6_HEAD_AT_END = d1e7388a91149a7c66e6cf1a5df7321bbb8eab12
SOURCE_TREE_SHA256 = ae1ad79cb32d53029e19c675955084e06ee644b3367130a3accb261a6bb26857
PROFILE_SHA256 = 1d6194eaaecc7e8837efc1979ba33d4b2300bc9a4d1d352c750131d8dd9354e2
ACCEPTED_FINDINGS_SHA256 = 43906b2b66bdd93fd7aa97e3334bfcb492dd4e8d34db0ff0f035b82db8a804a8
DIRTY_START_END = clean/clean，审计执行全程未污染或修改目标签出工作树
TEST_ENV = Linux 6.6.87.2 WSL2 (HERA-C3) / Python 3.13.5 (venv 5b2a6c50c6dd) / GCC 14.2.0 / ARM GNU 14.2.Rel1 / Node v20.19.2 / npm 9.2.0
GATE_DOCTOR_EXECUTED = YES
GATE_DOCTOR_EXIT_CODE = 0
GATE_PR_EXECUTED = YES
GATE_PR_EXIT_CODE = 2
GATE_PR_VERDICT = CONDITIONAL PASS
INDEPENDENT_BROKER_30 = 30/30 PASS
PHYSICAL_HARDWARE_OPERATIONS = NONE
PRODUCTION_BROKER_OPERATIONS = NONE
CODE_MODIFICATIONS = NONE
P4_MERGED = NO
FREERTOS_STARTED = NO
RECOMMENDATION = RECOMMEND_FOR_REVIEW
```

---

## B. 功能测试原始事实矩阵

| 测试 ID | 执行命令/工作目录 | 真实测试数 | 退出码 | 日志相对路径 / SHA-256 | 结论 PASS/FAIL/NOT_RUN |
|---|---|---:|---:|---|---|
| F01 Vendor 来源 | `python gateway/third_party/verify_coremqtt_integrity.py` | 9 文件 (v2.3.1) | 0 | `logs/f01_coremqtt_integrity.log`<br>`2d3cd937766cf1c76f4bc17eb585152e1db7645bce5e7499fbcdad5a2130199c` | PASS |
| F02 六项契约 | `python -m unittest discover -s gateway/mqtt/tests -p 'test_p5_integrity.py' -v` | 6 项测试 | 0 | `logs/f02_p5_integrity.log`<br>`ec2619c6180d2571d61188d089e8daf2199e07a2244d05614346408ba8d91c27` | PASS |
| F03 42 MQTT Host | `python gateway/mqtt/tests/run_p5_host_tests.py` | 42 项用例 | 0 | `logs/f03_p5_host_tests.log`<br>`563e6b5db3b69f7b14c21635009ea60ffd828769623f1f8c3fbe68870f0feaca` | PASS |
| F04 CAN/Router/17重启 | `python gateway/canopen/build_host.py` | 40 项用例 (12协议/11管道/17重启) | 0 | `logs/f04_canopen_build_host.log`<br>`5e37734cbf37290f568ef2babedd01dd9b183c53cfe4888fc6f056dbd8175520` | PASS |
| F05 41 条 Canonical 消息 | `python gateway/canopen/tools/check_canonical.py` | 41 条规范消息 (11 流) | 0 | `logs/f05_canonical_messages.log`<br>`213096b2507e926911276c49c31d78ce61ff89824f4d98965fc9ddb69d928547` | PASS |
| F06 Backend pytest | `python -m pytest cloud/backend/tests -q -p no:cacheprovider` | 28 项回归 (2 警告) | 0 | `logs/f06_backend_pytest.log`<br>`6d4dddbf084deabbc03f164b60fb70ff561164104558891862241d4917b05163` | PASS |
| F07 Web 11 / build | `cloud/web/` 下 `npm ci --ignore-scripts --no-audit --no-fund` && `npm test` && `npm run build` | 11 项用例 + Vite 构建 | 0 | `logs/f07_npm_test.log`<br>`146fb6aaa923e4302f931a40911df2cc77798f6f0a8de7c358470424415952d9` | PASS |
| F08 ARM 真正编译 | `python gateway/mqtt/build.py` | 1 ELF (66820 B) / BIN (35892 B) | 0 | `logs/f08_arm_build.log`<br>`722b329cac16768a35d2cddace1899ebe2720c3211e029c1191745f744595a94` | PASS |
| F09 localhost Broker | `python gateway/mqtt/tests/run_broker_integration.py --runtime <runtime>` | 30 项检查 | 0 | `logs/f09_broker_integration.log`<br>`0c90f60e6f90f514602377aab7363e65b2e7fa14b692960b977df504f6916106` | PASS |
| F10 GitHub CI 只读 | `gh pr checks 6` (run 37906799859, 113742095807) | 2 项已完成通过 Checks | 0 | PR #6 元数据与日志索引 | PASS |

---

## C. 统一 Gate 的本轮原件

| 项目 | 真实 status | 真实 exit_code | 扫描数量/发现数 | 未检查或跳过 | 本次证据 |
|---|---|---:|---|---|---|
| doctor | OK | 0 | 15 项工具与配置核查 | arm: PROJECT_CONFIG_REQ (独立配置), docker: MISSING (ZAP已排除) | `doctor-2026-10-09T114818.815372_0000-6d9086/doctor.json` |
| Semgrep Pro | OK | 0 | 66 文件扫描 / 0 发现 | 0 跳过, 0 错误 | `raw/semgrep.json`, `raw/semgrep.sarif` |
| Gitleaks | OK | 10 | 81 文件历史 / 6 发现 (全部为已接受误报) | 0 | `raw/gitleaks.json` |
| Trivy | OK | 0 | 3 扫描目标, 65 许可证 / 1 发现 (esbuild LOW) | 0 | `raw/trivy.json` |
| pip-audit | OK | 0 | 16 依赖项 / 0 漏洞 | 0 | `raw/pip-audit-0.json` |
| npm audit | OK | 1 | 65 依赖项 / 1 发现 (esbuild LOW) | 0 | `raw/npm-audit-0.stdout` |
| Bear / clang-tidy | OK | 0 | 12 翻译单元 / 106 MEDIUM 发现 (38 项目, 68 上游 coreMQTT) | 9 个 ARM 专属单元缺口 | `raw/clang-tidy.json`, `raw/compile-database.stdout` |
| coreMQTT ASan/UBSan | OK | 0 | 42 项 Host 测试 / 0 错误 | 0 | `raw/p5-coremqtt-asan-ubsan.stdout` |
| CAN/Backend/Web mandatory | OK | 0 | CAN 40 / Backend 28 / Web 11 / 全部通过 | 0 | `raw/{canopen-host-tests,backend-tests,web-build}.stdout` |
| Gateway ARM mandatory | OK | 0 | 真实编译生成 ELF/BIN/MAP / 全部通过 | 0 | `raw/gateway-build.stdout`, `harvest/arm/` |
| **Gate 汇总** | CONDITIONAL PASS | 2 | blockers=0; warnings=114; tool_errors=0 | 9 个 ARM-only TU (预期硬件代码) | `gate-result.json`, `coverage.json` |

```ini
gate-result.json SHA256 = e81d9dfd50ce06151ba0db0a3823f2fec63b901a62a3fa6f4c08684d3f850637
coverage.json SHA256 = 6e90f150964bc9f3e045fbef815a47c8ee33f36fd1a16451b133a9d97c9f296d
normalized-findings.json SHA256 = 2e2d281dc59363b0902218f30fc3d30a6bf36c77868c1415a5e008024fc8c1f9
report-integrity.json SHA256 = 0c475102fda10ca86b29397d4b1d0921b3b829e19a2196d609952a699dd7b566
```

**原始与解释性交叉核验说明：**  
`gate-report.md` 中的 `## ASan/UBSan` 小节由执行器静态模板固定生成文本 `Not executed in this mode; see coverage and project checklist.`，但在实际执行中，`p5-coremqtt-asan-ubsan` 被定义为 mandatory step，且在 WSL 原生环境中真实编译并执行了 42 项完整断言（原始日志见 `raw/p5-coremqtt-asan-ubsan.stdout`，退出码 0，42/42 全部 PASS）。本回执如实记录该报告文案与执行事实的差异，不擅自修改底层工具原始输出。

---

## D. 独立新增发现（每项一张）

```text
Finding-ID: GEMINI-P5-001
分类: HIGH_CONFIDENCE_RISK
发现来源: P4_INHERITED
文件:行号 / Git blob SHA: gateway/mqtt/src/main.c:60,62 / blob 1bb83fa270fef4c0839e5596e1074e50882e5b7e
输入和触发前置条件: 本机调试串口输入命令字符 'E' (EMCY 故障注入/清除)，且在此之前节点 0 (stack.nodes[0]) 曾发生启动分配失败或通信复位未恢复成功 (stack.nodes[0].co == NULL)
可信调用链及是否现役可达: CONDITIONAL (仅限调试串口交互输入字符通道；正常自动化运行不进入；但在活动固件源码中)
影响: stack.nodes[0].co 为空时，CO_errorReport(stack.nodes[0].co->em, ...) 发生空指针解引用，导致 MCU 产生 HardFault 宕机
独立复现步骤(仅Host/离线):
  1. 静态确定性逻辑分析：main.c:55-64 中在处理字符 'E' 时直接调用 stack.nodes[0].co->em，未像 mp_stack_nmt() 和 mp_stack_online() 那样添加 `if (!s->nodes[...].co) return;` 保护。
  2. 当 mock 注入分配失败使 stack.nodes[0].co 为 NULL 后向 console 写入 'E'，立即触发 NULL 解引用。
真实退出码与最小日志 SHA: 逻辑缺陷确认，静态证明确定，无需虚构崩溃日志
对照旧 Codex 是否记录（YES/NO/UNCERTAIN）: NO (Codex 既往报告未将此调试字符路径列为独立风险项)
误报排除或风险支持证据: 源码明确缺少对 stack.nodes[0].co 的判空守卫；对比 mp_stack_restart() 恢复逻辑证实该节点存在动态置 NULL 周期
等级与证据强度: LOW-MEDIUM (仅限本地调试字符触发，非公网/远程可利用；代码逻辑证据确凿)
建议下一步（仅建议，未修复）: 在 main.c 的字符 'E' 处理入口增加 `if (!stack.nodes[0].co) { console("GW EMCY_TEST_NODE_UNAVAILABLE\r\n"); break; }` 防护
```

---

## E. 已知风险逐项与 Codex 对照

| 项目 | Codex 既有记录 | Gemini 独立证据 | 新增/一致/冲突 | 未解决项 / 建议 |
|---|---|---|---|---|
| 六项 Git blob SHA-1 Gitleaks 精确误报；Issue #7 | 记录 6 项误报，到期 2026-11-08 | 经核对 `accepted-findings.yml` 与 Git 历史 blob，6 项 ID/提交/内容完全吻合，Gitleaks 退出 10，解析后 0 未决告警 | 一致 | 保持限期豁免，2026-11-08 到期前需随 C1 证据重构进行自然轮转 |
| `source-map-js@1.2.2` HIGH 已修复 | P4 升级到 1.2.2 修复 | package-lock.json 锁定 1.2.2，npm audit 与 Trivy 均无此告警 | 一致 | 已解决，无残留漏洞 |
| esbuild LOW | 1 项开发依赖 LOW 告警 (GHSA-67mh-4wv8-2f99) | Trivy (CVE-2024-34342) 与 npm audit (CWE-22 score 2.5) 各命中 1 处，无生产运行时暴露 | 一致 | 样机开发依赖残留风险，不阻塞 PR 合并审查 |
| clang 38/68 MEDIUM | 38 项项目代码 + 68 项 coreMQTT 上游代码 | clang-tidy 归一化输出恰好 106 条 MEDIUM（38 项 gateway + 68 项 coreMQTT），规则均为参数交换/缓冲区习惯等编译器规范，无缓冲区溢出可利用 PoC | 一致 | 属于静态规范建议，非高危漏洞；coreMQTT 保持上游 9 文件哈希冻结 |
| clang 12/21；9 TU 缺口（3 核心、6 其它） | 12 个 Host TU 覆盖，9 个 ARM 单元缺口 | 证实 Bear 生成 12 单元编译数据库，未包含 3 个核心 ARM 单元 (`heap,main,platform.c`) 及 6 个 probe 单元 | 一致 | 确认为硬件环境编译覆盖缺口 (`COVERAGE_GAP`)，已由 F08 ARM 真实全量编译补足语法与链接验证 |
| CAN 分配失败可靠性修复 17 项 | 修复 G1R-RESTART-ALLOC-001 | F04 真实重跑 17 项全部 PASS，`live_allocations_after_close: 0`，节点释放后 OD 扩展指针完全清空 | 一致 | 已解决，未见内存泄漏或悬空指针调度 |
| `main.c` 调试命令失败路径 | 记录单字符控制，未标记节点 0 判空缺陷 | 独立审查发现调试字符 'E' 缺少 `nodes[0].co` 空指针判断 (GEMINI-P5-001) | 新增发现 | 建议在后续分支为字符 'E' 补充判空守卫 |
| M03/M04/H16、B03、冷启动/assert | 保留样机工程约束记录 | 独立审查代码确认 assert 实现进入关中断死循环，H16 动态堆栈预算依然保持样机工程边界 | 一致 | 保留既有工程样机残余限制 |
| 32 帧缓存历史有损、RR INVALID、双 synthetic 节点 | 确认有损缓存与合成数据 | 独立审查验证 Router 溢出丢弃（46 帧丢弃测试 PASS），合成数据 bit31 标记和 RR INVALID 符合架构事实 | 一致 | 不应夸大为无损医学监护传输，符合当前开发阶段 |
| 最新短 Smoke：43.812s、25 新鲜消息、TIME 首次失败后重试 | 硬件短 Smoke 通过，恢复原程序 | 只读查阅硬件日志与数据，本轮未进行任何硬件操作 | 一致 | 历史硬件基线核验通过；本轮保持零硬件介入 |
| 现时 Flash 恢复 SHA `15102707…`（非旧 `852d7618…`） | 确认最新恢复基线已更新 | 只读核对历史记录，本轮不重写 Flash 或制造虚假旧一致 | 一致 | 保留历史事实记录 |

---

## F. 最终建议与禁止过度断言

**本轮重新发现的可复现生产代码缺陷：** `0`  
**本轮高可信但未复现问题：** `1`（GEMINI-P5-001：调试字符 'E' 在极端分配失败下的 NULL 判空缺失，见 D 节）  
**原始扫描误报且已充分证明：** `6`（Gitleaks 历史 blob SHA-1 误报，Issue #7）  
**覆盖盲区/环境问题：** `9`（ARM-only 编译单元缺少 Host clang-tidy 编译数据库，已由 F08 ARM GCC 全量构建兜底验证）  
**本轮新增未处置 HIGH/CRITICAL：** `0`  
**Gate 结果原文：** `CONDITIONAL PASS`（exit_code: 2，blockers: 0，warnings: 114，tool_errors: 0）  
**工程样机合并审查建议：** `RECOMMEND_FOR_REVIEW`（建议提交项目负责人人工审查，**不自动批准合并**）

---

> **合规不越权声明：**  
> 本轮独立审计未连接 COM15 / J-Link，未执行硬件擦写与复位，未连接生产 Broker 或发送线上请求，未执行 ZAP / DAST，未修改生产代码与安全配置文件，未合并 P4 分支，未引入 FreeRTOS。所有事实与数据均为本机真实实测输出。

**最终 STOP 回执：**  
- **时间：** 2026-10-09T11:58:00Z  
- **Git 状态：** 目标提交 `d1e7388a91149a7c66e6cf1a5df7321bbb8eab12`，分支 `P5-coremqtt-baremetal`，工作树洁净。  
- **独立审计目录：** `E:/security-gate-results/p5-gemini-independent-20261009T114500Z`  
- **证据清单 SHA-256：** `9bb4373cb0a5fac8f06f4b3b78afe7c86af9d20bc24596c48a159e030bac40ba`  
- **不可核验项：** 生产 Broker 真实物理通信、外部三板 CAN 物理联调、临床生理数据精度（本项目当前属于工程样机阶段，不包含上述内容）。
