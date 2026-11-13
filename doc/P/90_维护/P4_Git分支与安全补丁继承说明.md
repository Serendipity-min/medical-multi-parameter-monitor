# P4 Git 分支与安全补丁继承说明

P4.1 基线为 `ec75b10c885b066f6a7bd6142cc1a9cf98b6affa`，工作分支为 `fix/p4-security-closeout`，PR 目标为 `P4`，不自动合并。

| 提交 / 分支 | 含义 | 继承关系 |
|---|---|---|
| `cfb30d0a4a52f36e9dca6733b761741aae226de6` | 阶段二功能基线 | 本次上游功能起点 |
| `c4b1662d78bfa94afc4d53aceb2aa44dd42185b2` | UI 阶段成果 | 包含此前模块化、界面重构、验收等提交 |
| `d992712` | 维护文档同步 | 位于 UI 成果与 P4 安全提交之间 |
| `ec75b10c885b066f6a7bd6142cc1a9cf98b6affa` | P4 安全治理提交 | 已继承前述 UI 和维护历史 |
| `fix/p4-security-closeout` | P4.1 已知问题修复与治理收尾 | 从指定 P4 基线新建，向 P4 提交 PR |

P4 不是 security-only 分支。将 P4 merge 到其他功能分支会携带其可达历史，不能描述成“只合入安全补丁”。

若未来需要 security-only 迁移，应创建独立分支，按依赖顺序挑选所需安全提交并 cherry-pick，处理上下文差异后重新跑固定回归。不要把整个 P4 的 merge 当成安全补丁移植。本次没有执行这种移植。

本轮只做追加提交、普通 push 和 PR；不修改 main，不 force push，不 rebase 已推送历史。原始 JSON/SARIF 从新 HEAD 删除后，仍可在旧提交中追溯；这不是历史清除。

若以后确认秘密曾进入历史，应另行授权 Credential Rotation + History Purge，并核查其他分支、克隆和平台缓存。本次不轮换凭据、不删除历史，也不将原始扫描产物含有某项秘密视为已经证明的事实。

合入前审查以 [P4.1 最终分析报告](P4.1_安全治理收尾分析报告.md) 的代码 / 回归基线、CI 和残余风险为准。
