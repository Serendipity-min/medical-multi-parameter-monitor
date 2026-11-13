# 固定规则

- quick.yml：本地 4 条快速规则，覆盖指定 Python/C/JavaScript 危险调用，不代表全语言覆盖。
- security-audit.yml：2026-09-20 从 Semgrep 官方 `https://semgrep.dev/c/p/security-audit` 获取的 225 条规则快照；规则内保留原始 metadata、license 与来源链接。
- 快照 SHA-256：`b109a039df712f30c6d3e25e1e8358053fd0f1c91b92d0e8d2871cd141fe602f`。
- 快照只能按其中各规则的许可使用；不得把其许可改成安全门代码许可。更新需重新校验、记录哈希并审阅变更；实际扫描不在线拉取浮动规则。
- Pro 自检只 validate 本地规则；扫描使用 `--pro --metrics=off` 与关闭版本查询的进程环境。
