# Stitch UI 本地验收证据

全部截图来自本机回环夹具，使用实际 Backend/Hub 和 Snapshot v1，数据明确标记 MOCK。没有连接外部服务器、MQTT Broker、开发板或真实患者。

- `input-manifest.json`：用户素材的六页映射及 13 个源文件 SHA-256；素材中的静态示例值不进入生产运行时。
- `browser-acceptance.json`：六页面扩展验收，36 项通过。
- 六张 `*-1920x1080.png`：总体页及五个详情页。
- `overview-1366x768.png`、`overview-1600x900.png`、`temp-390x844.png`：响应式证据。
- `overview-mock.png`、`rr-invalid.png`、`node-a-offline.png`、`node-b-offline.png`：来源与异常状态证据。

复现时先构建 `cloud/web`，使用已安装的测试环境启动 `cloud/tools/stitch_ui_fixture.py --repo <repo> --output <仓库外临时目录>`，再运行 `cloud/tools/stitch_ui_acceptance.py --config <临时目录>/config.json --control <临时目录>/control.json --output <截图目录>`。夹具只绑定回环地址，验收器拒绝非回环目标。配置含临时令牌，禁止提交；结束后关闭本次进程并删除本次临时配置。

前端固定测试为 `npm --prefix cloud/web test`，使用项目已存在的 esbuild 与 Node 内置测试器，未引入新依赖。

本轮迭代记录：首次浏览器检查发现 1600×900 Grid 隐式最小高度造成内部滚动，已用明确的 `minmax(0, 1fr)` 修正；测试中的 hash 导航改为真正 reload 后验证刷新清空。Windows Backend 初次运行因仅父进程使用 UTF-8 导致子进程 stderr 解码失败，使用进程级 `PYTHONUTF8=1` 后 28 项通过，未修改 Backend。

精确提交 SHA、安全门目录、GitHub CI、合并与清理结果见 PR #4 的最终验收回执。回执发布在检查完成后，避免为写入自身 SHA 而改变已检查提交。
