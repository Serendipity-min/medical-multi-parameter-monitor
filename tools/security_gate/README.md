# 统一安全门（跨项目）

安全门是确定性 Python 执行器，Codex Skill、Gemini 与人工终端调用同一套脚本。`--repo` 选择目标 Git 仓库，profile 决定语言、依赖、构建和固定回归范围。医疗监护项目是一个适配实例，不是默认扫描目标。

默认不扫描。只有用户明确授权本次目标和模式后才传 `--authorize`；可提出扫描建议，但不能代用户授权。不安装自动 Git hook、后台任务或 push/PR 扫描。所有 raw、构建快照、编译数据库、SBOM 和扫描缓存均在仓库外。

## 调用

Python 3.11+；Windows 入口自动转到现有 WSL，默认发行版 HERA-C3。无需改 CODEX_HOME、项目 venv、代理或全局 Python。

```text
python tools/security_gate/gate.py doctor --repo <project>
python tools/security_gate/gate.py quick --repo <project> --authorize
python tools/security_gate/gate.py pr --repo <project> --profile medical-monitor --base <base-sha> --authorize
python tools/security_gate/gate.py release --repo <project> --dry-run
python tools/security_gate/gate.py release --repo <project> --authorize --checklist <review.json>
```

DAST 只在用户明确授权 Staging URL 时追加 `--target <url> --authorize-target`；只调用 ZAP Baseline，不运行 active/full/api scan。默认没有 target，DAST 状态为 MANUAL_NOT_RUN，release 不会因此假报 PASS。

`doctor` 只查版本、输出写权限、Git、配置和 Pro `--validate`；不扫描。`--dry-run` 只输出执行计划，固定为条件状态，不能作为 release 证据。quick 为工作树 Gitleaks、4 条快速 Semgrep 规则及 profile 固定测试/构建；pr 加入固定 225 条官方规则、提交范围 Gitleaks、Trivy、pip-audit、npm audit、first-party clang-tidy。release 增加完整历史、SBOM、GitHub Alerts、人工清单与授权的 ZAP。

## 安装与工具锁

```text
python tools/security_gate/bootstrap.py
python tools/security_gate/bootstrap.py --install --authorized-machine --system-deps --tool-root <dedicated-tools> --output-root <external-results>
```

第一条仅显示计划。第二条从官方 GitHub Release 下载 Linux amd64 Trivy/Gitleaks，并核对官方 checksum；已有锁时重用精确版本和校验和。pip-audit 使用独立 venv。系统 clang/clang-tidy/bear/node/npm 来自发行版签名包。Semgrep 只检测，不覆盖、不读取认证文件。安装结束运行 doctor，不启动扫描。

`toolchain.lock.json` 记录精确版本、来源、文件/资产 SHA-256 与时间。编译器版本由发行版提供；跨发行版迁移需要复验并提交新的工具锁。更新工具或规则是单独的显式安装操作，不随扫描自动升级。Trivy 扫描可能更新官方漏洞库，该时点证据保存在 raw；CVE 结果本身不承诺跨日期不变。

可设置用户变量 `SECURITY_GATE_TOOL_ROOT`、`SECURITY_GATE_OUTPUT_ROOT`、`SECURITY_GATE_WSL_DISTRO`；Windows 入口只转发这三个非敏感设置。Linux 默认 `~/.local/share/security-gate` 与 `~/.local/state/security-gate`；bootstrap 也写用户级 `.config/security-gate/settings.json`。执行器没有硬编码盘符。现有 Pro 登录由用户管理；登录失效时只报错，不展示或收集令牌。

Docker/ZAP 无可用 daemon 时记录不可用。本轮不启动 Docker 服务或安装第二套商业 SAST。准备 ZAP 后须将官方 stable 镜像解析后的 `sha256:` digest 写入锁，release 才允许用固定 digest 执行。无 digest 的授权 DAST 返回工具缺口，不能静默跳过。

## 接入其他项目

在目标仓库保存 `.security-gate.json`，从 `profiles/generic.json` 按实际范围填写：

- `source_roots`：自有源码路径。
- `requirements`：精确锁定的 Python 运行依赖文件。
- `npm_roots`：具有 package-lock.json 的目录。
- `first_party_c`：自有 C 路径，避免把所有第三方源码作为 Gate。
- `compile_capture`：实际构建命令，交给 Bear 记录原始参数；或 `compile_database` 指向已有编译数据库。
- `commands`：名称、argv 数组、相对 cwd、适用 modes、mandatory 与可选 required_file。
- `manual_checklist`、`real_data_checklist`：发布需人工核对的项目特定条目。

profile 是可执行项目配置，须在本次用户授权范围内审阅；安全门不会凭发现新文件就执行未知脚本。路径必须在目标仓库中。通用空 profile 只提供基础 SAST/Secrets/SCA，缺少项目测试与依赖声明时明确保留覆盖警告。

项目测试环境另行准备：

```text
python tools/security_gate/prepare.py --repo <project> --requirements cloud/backend/requirements-dev.txt --constraints cloud/backend/requirements.lock --authorized-machine
```

解释器存入安全工具专用 test-envs，`{python}` 在 profile 中解析为该解释器；不污染原项目运行 venv。npm ci、构建与测试在本次 Git 可见文件快照中运行；快照在留存回归记录后删除，不形成整库备份。

## 策略与覆盖

退出码固定：0 PASS；1 FAIL；2 CONDITIONAL PASS / HUMAN REVIEW；3 TOOL / COVERAGE ERROR。真实数据缺少人工准入证据时另标 `FAIL_FOR_REAL_DATA`。

- 秘密、Critical 漏洞、High 静态发现、新的失败测试和完整性失败会阻塞；发现是待确认问题，不宣称已经证明可利用。
- mandatory 工具缺失、超时、坏 JSON、空覆盖或运行错误为 3；optional 缺口和明确 ARM 解析缺口为条件状态。
- 没有 fix 的依赖问题必须保留；严重度未知的 pip-audit 结果进入人工定性，不能当成低风险。
- `accepted-findings.yml` 每项需 id/tool/path/reason/owner/accepted_at/expires_at/review_issue。秘密只允许有证据的误报接受；过期自动恢复阻塞。clang 历史 baseline 同样须逐项批准，绝不自动批量忽略。
- C 编译数据库来自 Bear 捕获的实际 flags；ARM 源码不在 host 数据库时逐文件记录 Gap，禁止删编译参数追求“零发现”。
- Semgrep JSON/SARIF 保留 scanned/errors/skipped 信息，不能仅凭零 finding 认定通过。
- 代码质量不作安全准出替代；未来可在 profile 增加 Ruff/ESLint optional 命令，本轮不新建风格门禁。

## 输出与人工审核

每次输出 manifest.json、tool-versions.json、coverage.json、normalized-findings.json、gate-result.json、gate-report.md、report-integrity.json 和 raw/；release 实扫另生成 sbom.cyclonedx.json。报告只保留规则标识、相对位置、数量和状态，不含扫描器自由文本、密钥、服务器地址或源码片段。原始文件不加入 Git。

Trivy 不一定自动识别自定义 `.lock` 名称；执行器会从 profile 指定的精确 Python runtime lock 补齐 CycloneDX 包组件，并记录来源锁哈希。未识别的许可证和依赖关系不会编造，仍保留覆盖说明。

人工 checklist 参照 templates/manual-checklist.json，但必须覆盖选用 profile 全部键。每项需 `status: pass` 和 `evidence`；顶层需准确 commit、reviewer、reviewed_at。真实人体数据需额外完整核对身份撤销、HTTPS/WSS、日志脱敏、数据保留、备份权限、Mock/Live 隔离及危险控制。

发布流程：冻结准确候选 SHA → 确认 Git clean → doctor → 明确授权 release → 检查退出码和覆盖 → P 审阅报告与 residual risk → 再由发布流程打 tag/部署 → 部署后 smoke test。扫描器不升级依赖、不修改源码、不轮换令牌、不改防火墙、不部署。

## 项目导出、CI 与 Dependabot

```text
python tools/security_gate/export.py --target <project-checkout> --profile medical-monitor
python tools/security_gate/export.py --target <project-checkout> --profile medical-monitor --apply
```

导出相同执行器、Skill、profile、独立 workflow 和 Dependabot 配置；不会复制整个集中技能库，也不会创建分支、提交或推送。首轮既有文件冲突时停止。后续跨项目 Git 提交须基于目标分支历史逐文件提交导出内容，不把技能库历史 merge 进项目。

workflow 仅 workflow_dispatch，输入准确 SHA、模式与扫描授权；ZAP 有单独目标授权。所有 Actions 固定 commit SHA（Node 24 版本）。默认云端 runner 未持有本机 Semgrep Pro 认证；应由仓库管理员准备合法 Pro runner/认证或将 workflow 改为受控 self-hosted runner。缺少 Pro 返回工具错误，不以 OSS 冒充。CI 不复制本机认证，不上传 raw。

Dependabot weekly 监控医疗项目 pip/npm/github-actions，不自动合并 PR。配置只有进入平台认可的默认分支后才可能生效；仅推 P4 不声称已经启用。管理员一次性在 Settings → Security/Code security 中核对 Dependency graph、Dependabot Alerts、Malware Alerts（若账号/平台可用）与 Security Updates。Release 通过 gh 只读查询未处理 Alerts；权限不足就是 MANUAL_CHECK_REQUIRED。CodeQL 为可选深审，许可/能力不足不阻塞当前安装。

pre-commit 只提供人工执行 Gitleaks 的用法，不安装 hook，以符合默认不扫描的全局约定。如另行授权启用 hook，范围限 staged Gitleaks，不放 Pro/Trivy/ZAP/ASan 全套。

## 自测

```text
python -m unittest discover -s tools/security_gate/tests -v
```

覆盖工具缺失、超时、非零、坏 JSON、秘密、Critical CVE、有效/过期接受、coverage gap、未授权 ZAP、dirty tree、真实数据及 CLI/result/report 一致性。测试使用合成数据，不扫描外部目标。

## 官方来源

- [Trivy installation](https://trivy.dev/docs/latest/getting-started/installation/)
- [Gitleaks](https://github.com/gitleaks/gitleaks)
- [pip-audit](https://github.com/pypa/pip-audit)
- [clang-tidy](https://clang.llvm.org/extra/clang-tidy/)
- [ZAP Baseline](https://www.zaproxy.org/docs/docker/baseline-scan/)
- [Dependabot 配置](https://docs.github.com/en/code-security/reference/supply-chain-security/dependabot-options-reference)
