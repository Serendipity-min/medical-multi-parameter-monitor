# 跨项目 Security Gate 安装与验收报告

日期：2026-09-21。依据 P5 安全门合同及用户后续修改：主实现和分支全部维护于集中技能库，医疗项目仅接收 P4 审核用接入副本。源分支 `dev/security-gate-v1`；没有修改 main，没有部署，没有自动修复依赖或源码。

## 交付

- `tools/security_gate`：独立于 AI 的 bootstrap、doctor、quick、pr、release、normalize、policy、report、SBOM 和跨项目 export。
- `skills/security-gate`：显式技能，allow_implicit_invocation=false。Windows 自动使用 HERA-C3；Gemini 直接调用同一 gate.py。
- `profiles/generic.json` 与 `profiles/medical-monitor.json`：目标由 --repo 指定，不默认扫描某项目。
- 导出项目提供 `.agents/skills/security-gate`、同一执行器、`.security-gate.json`、独立 workflow_dispatch workflow 与 weekly Dependabot 配置。
- 全局记忆已同步默认不扫描、须当前明确授权、可提出扫描建议但不代替授权。没有自动 Git hook 或后台扫描。

## 安装结果

| 组件 | 版本 / 状态 | 验证 |
| --- | --- | --- |
| Semgrep Pro | 已有 1.175.0 | HERA-C3 validate；实际 quick/pr 成功 |
| Trivy | 0.74.0 | 官方资产 checksum 匹配；实际 fs 成功 |
| Gitleaks | 8.30.1 Linux | 官方资产 checksum 匹配；工作树与提交范围成功 |
| pip-audit | 2.10.1 | 专用 venv；精确 runtime lock 审计成功 |
| clang / clang-tidy | 19.1.7 | Bear 捕获真实 build flags，6 个 host first-party C 单元成功 |
| GCC / ASan / UBSan | 14.2.0 | 合成固定计算编译并运行成功 |
| Bear | 3.1.6 | compile_commands.json 实际生成 |
| Node / npm | 20.19.2 / 9.2.0 | npm audit、npm ci、Web build 成功 |
| Docker / ZAP | daemon 未准备 | 官方镜像 digest 已解析固定，默认关闭 |
| CodeQL | optional | 不作为本轮必需安装组件 |

工具来源、文件哈希、依赖版本、官方规则快照和 Action SHA 在 `toolchain.lock.json`。新工具与原始输出在仓库外；安装位置采用 E 盘及位于 E 盘的 WSL 虚拟磁盘。没有新增整库备份。

## 验证证据

- 17 项自动测试通过：missing/timeout/non-zero/malformed JSON、secret/Critical、risk acceptance/expiry、coverage、ZAP authorization、dirty tree、real data、CLI/result/report 一致性、自定义 runtime lock SBOM 及 release 准确提交快照。
- 安装合成仓库 quick：**PASS / 0**；真实 Semgrep Pro 与 Gitleaks、ASan/UBSan build/run、Python 固定测试均 OK。这证明正向通路，不代表医疗项目安全通过。
- Doctor：**PASS / 0**，未执行源码扫描。
- 医疗 P4 `ec75b10c885b066f6a7bd6142cc1a9cf98b6affa`，clean 工作树：quick 与 pr 都为 **TOOL / COVERAGE ERROR / 3**。
- quick 缺少 `gateway/canopen/run_security_regression.py`；pr 另缺 `gateway/third_party/verify_paho_integrity.py`。这两项在未合并的 P4.1 中，不能凭安全门安装自动合入。
- P4 quick Semgrep 扫描 45 个文件；pr 225 条官方规则扫描 50 个文件，errors=0。秘密检查已执行，无归一化秘密 finding。
- P4 pr：Trivy 3 个 HIGH 依赖记录，npm audit 的 Vite HIGH 记录可能与其重叠，不能加总成 4 个独立漏洞。clang-tidy 有 27 个 MEDIUM 待审记录；没有建立未经批准的 ignore/baseline。
- clang-tidy host 覆盖 6/16 个自有 C 文件；另外 10 个 ARM 相关单元无 host compilation command。ARM 原构建含 Windows 专用工具链路径，WSL 构建记 coverage gap。
- P4 后端、CANopen host、C→Backend、Web 构建通过；未升级依赖、未改固件或业务代码。
- release dry-run：**CONDITIONAL PASS / 2**；只生成计划，无 DAST target，无正式上线扫描。
- SBOM 实际生成：83 个组件，含 npm 及 Python；补齐了自定义 runtime lock 的 11 个组件。SHA-256 `b0ff6514cfcfc9ffdf5d4f7a7c7a832c27a56d60342cfab065fde1636e4d0199`。许可证缺项继续公开为覆盖限制。
- Desktop/CLI 发现共 146/113 项（包含各自运行时/插件），重复名与发现错误均为 0；集中用户技能总数 104。

## PI 必须看到的未准出项

1. 医疗 P4 尚未满足合同“quick/pr PASS 或可接受 CONDITIONAL”。当前 3 是必需组件缺失，不能通过人工风险接受直接改成 0。
2. 需另行处理 P4.1 回归／Paho 完整性组件接入、依赖 HIGH、clang 待审与 ARM coverage；本轮只记录，不越权修复或忽略。
3. Docker/ZAP 尚无可用 daemon；授权 Staging 扫描前必须准备已锁 digest 镜像。未提供目标，本轮没有任何 DAST。
4. GitHub 仓库为 private，Code Security/Dependabot 设置未通过本轮安装宣称开启。配置推到 P4 只供审核，默认分支仍 main；平台设置和配置生效须按 README 人工核对。
5. 云端 CI 不继承本机 Pro 登录。workflow 输入和 Action SHA 已准备；管理员须准备合法 Pro runner/认证，缺少时返回可见工具错误。

## 正式流程

指定项目与范围 → doctor → 本次明确授权 → quick/pr 或 release → 读取退出码与覆盖矩阵 → 独立修复任务 → 获授权后复验。

发布额外要求：准确候选 SHA、Git clean、SBOM 哈希、报告哈希、人工 Architecture/Auth/Privacy checklist。CONDITIONAL 必须 P 书面接受；真实人体数据另有附加清单。只有正式 release 准出及人工审核后才进入用户管理的 tag/release/deploy 流程。

原始报告全部留在仓库外。此文为脱敏安装摘要，不是项目上线批准，也没有“完全安全”保证。
