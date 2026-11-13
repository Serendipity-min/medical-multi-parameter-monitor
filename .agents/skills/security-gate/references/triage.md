# 结果处理

1. 先确认执行错误、超时、解析失败和实际扫描文件数，再判断漏洞数量。
2. 对 blocker 提供规则、仓库相对路径、严重度和修复建议。不要在聊天或可提交报告中显示秘密值、源码片段、用户名或服务器地址。
3. 风险接受由 P 决定；accepted-findings 项须 ID、tool、path、reason、owner、accepted_at、expires_at、review_issue。秘密误报还须 false_positive disposition 与证据。过期自动恢复门禁。
4. 不自动生成历史 baseline 以消除发现；clang-tidy 历史问题同样逐项审批。修复进入独立任务/PR，随后只在再次获得授权后复验。
