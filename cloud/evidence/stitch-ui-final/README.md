# Stitch 六页面最终 UI 回归证据

2026-09-23，针对最终准备提交的本地构建运行。测试目标为独立回环夹具，真实 Backend/Hub 接收明确标记为 MOCK 的合成快照；临时只读令牌及控制文件位于仓库外。以下文件仅含脱敏测试结果和截图，不代表真实硬件或临床验收。

| 套件 | 结果 | 主要覆盖 |
|---|---:|---|
| [六页面 Browser Acceptance](regression/browser-acceptance.json) | 39/39 | 六路由、三波形、五组读数、状态隔离、CSV、动态值与 30 秒 NIBP |
| [全屏与交互](interaction/interaction-acceptance.json) | 113/113 | 真实点击命中、全屏、返回总览、横竖屏尺寸、冻结、断连和重试 |
| [连接反馈专项](auth/interaction-acceptance.json) | 13/13 | 错误令牌、格式不兼容、全屏弹窗与冻结继续接收 |

截图索引：

- [总览 1920×1080](regression/overview-1920x1080.png)、[1366×768](regression/overview-1366x768.png)、[动态 MOCK](regression/overview-varied.png)
- [ECG](regression/ecg-1920x1080.png)、[SpO2](regression/spo2-1920x1080.png)、[RESP](regression/resp-1920x1080.png)、[NIBP](regression/nibp-1920x1080.png)、[TEMP](regression/temp-1920x1080.png)
- [全屏连接后](interaction/fullscreen-connected.png)、[全屏未连接](interaction/fullscreen-disconnected.png)、[横屏短屏](interaction/temp-844x390.png)
- [令牌错误普通模式](auth/invalid-token-normal.png)、[全屏](auth/invalid-token-fullscreen.png)、[冻结仍接收](auth/connected-frozen.png)

原始 Security Gate 报告留在仓库外；准确提交 SHA、CI Run ID 与合并结果由 PR #4 的“Stitch 六页面最终验收回执”绑定，避免为了回填自身 SHA 变更已检验的提交。
