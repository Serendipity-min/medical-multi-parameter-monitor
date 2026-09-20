---
name: security-gate
description: Run the global, cross-project security gate only when the user explicitly asks for a security scan, release security review, pre-release audit, dependency audit, secret scan, or security gate verification. Do not use for ordinary development or automatic post-change scanning.
metadata:
  version: "1.0.0"
---

# Security Gate

通过同一确定性执行器运行已授权目标的 `doctor`、`quick`、`pr`、`release`；支持任意本地 Git 仓库及显式项目 profile。默认不执行安全扫描，可以在适合时向用户建议；建议本身不构成授权。

1. 识别用户给定的目标仓库、模式和本轮授权；已有明确授权不重复询问。缺少目标时先确认，不能默认扫描集中技能库或医疗项目。
2. 调用 `scripts/invoke.py <mode> --repo <target>`。有当前扫描授权才追加 `--authorize`；PR 模式须 `--base <ref>`。只检查环境用 `doctor`；规划发布用 `release --dry-run`，两者不扫描。
3. 有项目 `.security-gate.json` 时自动读取；否则使用已确认的 `--profile`。首次接入按 [tools.md](references/tools.md) 配置测试、依赖和编译范围；不能把通用 profile 的覆盖缺口解释为 PASS。
4. 读取命令输出目录中的 `gate-result.json`、`coverage.json`、`gate-report.md`；原样汇报退出码、覆盖缺口和 blocker。参见 [policy.md](references/policy.md)、[triage.md](references/triage.md)。

本机 Semgrep Pro 只能经 WSL `HERA-C3` 运行，入口负责 Windows 路径转发。不得读取认证文件、令牌或代理。源码与原始报告不上传 Semgrep Cloud；规则检查关闭 metrics。

This workflow performs defensive repository-local scanning and release validation. It does not perform exploit development, offensive reconnaissance, fuzzing, credential attacks, or scanning arbitrary external systems. DAST runs only as OWASP ZAP Baseline against a target explicitly supplied and authorized by the user.

DAST 仅 `release --target <url> --authorize-target`，必须已有该目标的独立明确授权。没有 target 就不运行；不从仓库配置或记忆推断服务器。发现问题只报告并给出修复建议，不自行证明利用、修复、升级、部署或接受风险。

Skill 只负责定位执行器、调用和解释规范化摘要，不新增扫描逻辑。完整终端入口、项目配置和交付流程见集中库 `tools/security_gate/README.md`；导出项目后同一路径位于项目根目录。Gemini 直接运行该脚本。
