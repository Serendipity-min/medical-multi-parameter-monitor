# 全屏与页面交互自动化回归

本轮针对 2026-09-22 用户测试请求及“全屏网格后面残留文字”的截图，执行功能回归与修复。没有执行安全门、漏洞扫描、Git 提交、GitHub push 或合并。

## 复现和修复

1. **全屏模态层残留**：点击设置里的全屏时，根元素进入浏览器顶层，但设置 dialog 仍保持 `open` 和模态状态。文字从波形面板缝隙露出，`elementFromPoint` 命中 dialog，参数卡片无法收到点击。修复为在真实点击回调内同步关闭设置，再调用全屏 API；权限失败重新打开设置显示持续提示。
2. **手机横屏导航越界**：844×390 视区下，外框最小高度 500px 将底部导航挤到视区外。短屏取消最小高度，保留中央滚动区。

- [全屏修复前](fullscreen-before.png)
- [横屏修复前](landscape-before.png)
- [首次交互回归与横屏失败断言](initial-regression.json)
- [本地全屏修复后](local/fullscreen-connected.png)
- [本地横屏修复后](local/temp-844x390.png)

## 自动化结果

| 范围 | 结果 | 原始记录 |
|---|---|---|
| TypeScript / Vite 构建 | 通过 | 本轮构建输出，静态产物见 source-manifest.json |
| 前端状态单元测试 | 9/9 | 本轮 `npm --prefix cloud/web test` |
| 原有浏览器回归 | 39/39 | [browser-acceptance.json](regression/browser-acceptance.json) |
| 新增本地交互回归 | 113/113 | [interaction-acceptance.json](local/interaction-acceptance.json) |
| 服务器交互回归 | 112/112 | [interaction-acceptance.json](server/interaction-acceptance.json) |

交互脚本使用 agent-browser 0.27.0 / Chromium：先校验实际点击中心未被遮挡，再发送浏览器点击。不会用 JS `.click()` 绕过模态遮罩。

桌面 2560×1440、1920×1080、1600×900、1366×768、1280×720 分别覆盖正常/全屏六页；390×844、844×390 覆盖六页响应式布局和导航。覆盖参数卡片、波形入口、返回总览、底部导航、浏览器前进/后退、设置、8/16 秒窗口、原生 Escape、重复全屏、冻结/恢复、CSV、断开重连、WebSocket 单实例和未捕获异常。全屏权限拒绝只在独立本机页面测试。

Chromium 原生 Escape 行为：设置打开且处于全屏时，第一次退出全屏，第二次关闭设置。按钮文案由 `fullscreenchange` 同步。F11 属于浏览器窗口功能，不以页面全屏 API 的通过结果替代操作系统级验收；其他浏览器内核、真实手机和长时间运行不在本轮覆盖范围内。

## 服务器同步

[同步回执](server-activation.json)：静态审核版 `stitch-ui-interaction-20260922-112133`，前一版 `stitch-ui-review-20260922-105734` 保留。HTTPS 页面索引与本机构建相同；Backend、模拟发布器、Broker、Nginx 均未重启，配置和访问令牌未改变。

服务器全屏已截图复核：[连接前](server/fullscreen-disconnected.png)、[连接后](server/fullscreen-connected.png)。网格间无设置文字残留，六页切换全程只创建一个 WebSocket；主动断开再连接后为两个，符合预期。测试期间未捕获页面异常或未处理的 Promise 拒绝。

新发布复用前一版的服务文件，不能删除依赖的旧发布。服务器备份目录 `/opt/medical-monitor/backups/stitch-ui-interaction-20260922-112133/` 保存 `previous-current.txt` 和同步回执。回滚只需原子切回该记录的 current 目标。

压缩包及部署脚本经本机 `E:/Server_file` 中转，远端 SHA-256 一致后已删除本次精确暂存文件。在线自动化只连接既有服务、操作自己的浏览器会话；故障注入全部在独立本地实例完成。报告不含地址、令牌或认证载荷。

当前为 `codex/p4-vite-clang-triage` 未提交工作树，HEAD `1a85d5c48b6930c6f00be1022dfb0a5938bbb421` 不是本轮修复的提交 SHA；不得将结果记为该提交本身已经包含修复。
