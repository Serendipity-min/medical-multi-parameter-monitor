# 第二版预览：通道配色与模拟节奏

2026-09-22，按用户预览反馈进行本地调整。当前未 push、未执行安全门或合并；第一版准出报告不作为当前未提交工作树的准出结果。

- 血氧、脉率和 PPG 改为红色；心电亮绿、呼吸亮黄、体温青色。血压 SYS 白色 / DIA 青色。活动导航与详情导出按钮跟随通道颜色。
- 提高背景层次与读数饱和度；趋势填充沿实际连续有效记录绘制，不表示正常范围或报警。
- 默认 MOCK 场景：NIBP 每 30 秒一组；HR/PR/RR/SpO2 每秒更新；TEMP 每 2 秒更新。标量持续变化，波形相位随模拟频率连续变化。血压历史不再每 200ms 增加一条。
- 用户预览与验收使用不同回环实例，故障注入和固定值断言不干扰用户预览。原本机临时令牌保留；刷新网页重新连接后清除旧的高频记录。

验证结果：Vite/TypeScript 构建通过，9 项前端状态回归通过，4 项模拟节奏固定测试通过；[浏览器验收](browser-acceptance.json) 39 项通过，包含实际观察各标量变化，以及 CSV 血压采集时间间隔精确为 30000ms。

默认变化场景截图：

- [总览](overview-varied.png)
- [心电](ecg-varied.png)
- [血氧](spo2-varied.png)
- [呼吸](resp-varied.png)
- [血压](nibp-varied.png)
- [体温](temp-varied.png)

`*-1920x1080.png` 等用于固定场景功能断言，`*-varied.png` 对应默认变化场景，全部明确标记 MOCK。未修改 Backend、Gateway、协议或真实设备采集节奏。

## 服务器审核同步

用户另行授权先同步服务器审核，继续暂停安全门、GitHub 推送和合并。已启用 `stitch-ui-review-20260922-105734`；[脱敏同步回执](server-review-sync.json) 记录包哈希和在线功能验证。

HTTPS 页面与本机构建一致；只读快照观察 378 帧，HR/SpO2/PR/RR/TEMP 分别出现 24/4/25/7/8 种值，NIBP 两条测量相隔 30000ms 且数值不同，均为 MOCK。只重启模拟发布器；Backend、Broker、Nginx 的进程保持不变，原访问令牌未更改。

回滚资料位于服务器 `/opt/medical-monitor/backups/stitch-ui-review-20260922-105734/`，包含旧 current 和旧模拟场景文件。回滚需原子恢复 previous-current 目标、恢复 mock-control.json，并重启 medical-monitor-mock。新审核版复用旧版本的 Backend 与 Python 环境，因此保留 `mqtt-v07-phase2-20260920-01`，不能删除该目录。

原发布器默认仍为固定场景；服务器控制文件显式选择 `scenario: varied`，新发布器复用 `tools/preview_signals.py`。今后打包发布器时须同时包含该辅助模块。已从 `E:/Server_file` 中转上传并核对两份文件哈希，确认后清除了本次本地暂存文件。
