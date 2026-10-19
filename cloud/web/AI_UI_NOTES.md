# P6-V2 页面设计与发布准备

## 设计裁定

沿用原 Vite + TypeScript + DOM/Canvas，`#/ai` 是同站第七页。顶部快捷入口与底部导航均进入该页，没有第二套弹窗会话。深蓝底 `#080e16`、对话底 `#0b141f`、表面 `#121c27`、边界 `#2b4052`、正文 `#e8f1fc`、次级字 `#a0b3c7`；AI 强调 `#9bdce9`。原 ECG/SpO₂/RESP/TEMP/NIBP 通道色不变。字体沿用 Segoe UI / Microsoft YaHei，数值用 Consolas。未安装依赖/Skill、未复制第三方模板、未向视觉服务上传数据。

1920 桌面对话为主，380px 事实侧栏为辅；侧栏先显示模型与播报，再呈现实时事实。对话内滚动，编辑区固定在对话区底部。1000px 以下堆叠，600px 以下单栏；小屏沿用原中央滚动和底部导航，编辑器位于对话末端，另外提供实际滚动位置截图。无装饰性动画、录音按钮或臆测设备状态。

`MonitorSocket`、`MonitorStore`、RAF 仍由 main 持有。AI 单实例保留最多八轮；离页取消待答，换网关取消待答、清空聊天、更换 AI session、暂停后续播报。刷新保留 hash、清除内存令牌/聊天、等待重新连接。最新事实读取原 Store，原始快照只保留一份并在断连时清除；冻结不冻结 AI 事实，页面对此明确说明。回答回执和当前事实分别显示。

AI 独立令牌仅在内存输入框保留，接口仍为 `POST /medical-monitor/ai/api/v1/text`。没有新健康轮询或自动模型调用；发送字段仍是 session_id/gateway_id/question/voice，浏览器不上报测量值。问题与回执全部 textContent；错网关/会话/畸形回执拒绝，15 秒超时并取消。失败时撤下上一轮模型标签，避免错误继承“本轮使用豆包”。历史来源 REPLAY 优先显示“历史回答回放·本轮未调用模型”。Broker PUBACK 只表示接收，不表示设备播放。

## 本地复现（均不连接云端）

在仓库根目录开两终端，各启动同一合成协议夹具：

```text
python -m uvicorn cloud.web.tests.ui_fixture:app --host 127.0.0.1 --port 18765 --no-access-log
python -m uvicorn cloud.web.tests.ui_fixture:app --host 127.0.0.1 --port 18766 --no-access-log
```

在 cloud/web 启动 `npm run dev -- --host 127.0.0.1 --port 18767 --strictPort`。
从根目录运行 `python cloud/web/tests/ui_browser.py`。夹具令牌全部无生产权限，fixture/control 只用于 loopback 测试，**不得部署夹具到服务器**。CLI 使用本机已安装 agent-browser；其它机器设置 P6_BROWSER_CLI 指向其安装路径。测试截图和回执保存在 `cloud/evidence/p6-v2-ui/`。

原 AI 应用整合测试另行用 MOCK Provider + MONITOR SnapshotReader，通过本地 18765 合成 WS 读取同一数据。停止 18766 协议夹具后，在仅本机测试进程中清除既有 P6_/ARK_ 环境配置，再设置合成 P6_AI_TOKEN=`local-ai-service-` 加 32 个 x，P6_MONITOR_VIEW_TOKEN=`local-monitor-fixture-` 加 32 个 x，P6_MODEL_MODE=MOCK，P6_SNAPSHOT_MODE=MONITOR，P6_MONITOR_WS_URL 为上述 loopback WS。禁止设置 MQTT、ARK、WEB_DIR；启动 `python -m uvicorn cloud.ai.app:create_app --factory --host 127.0.0.1 --port 18766 --no-access-log` 后运行 `python cloud/web/tests/ui_service.py`。本轮 6 项通过，服务端校验当前事实、一般提示、DISABLED、INVALID/OFFLINE；真实模型零调用。

普通测试：根目录 `python -m pytest cloud/ai/tests -q`、`python -m pytest cloud/backend/tests -q`；cloud/web 下 `npm test`、`npm run build`。均为本地功能回归，不是 GitHub Actions / Security Gate / 真机播报准出。

## 本轮缺陷台账

|发现|处置|验证|
|---|---|---|
|新路由可能被 parameters 索引|ai 排除参数类型，SessionView 提前返回|七页循环、TS 构建|
|播报状态被事实长列表挤到下方|播报区域前置，侧栏可滚动|1920、125%、手机播报截图|
|折叠令牌区原生 required 无法可靠聚焦|显式校验，缺令牌时展开并聚焦|本地输入交互|
|相同 URL 的工具 open 只软导航|用显式 reload 验证刷新|hash 保留/凭据清除 PASS|
|失败请求可能继承上一轮模型标识|请求开始/失败时撤下旧模型标签|取消、超时、认证/回执失败|

剩余：较矮桌面需滚动侧栏，手机需滚动中央视图查看模型/令牌和事实。聊天只在内存保留八轮，不持久化患者或聊天数据。不同时间的当前快照与回答快照不承诺相同采集 seq；回答依据可展开核对。设备实际播放仍无证据，既有 HOST_VERIFIED 结论不升级。

## 未来正式发布与回滚（本轮未执行）

只读核对：正式 current 仍指向 `/opt/medical-monitor/releases/stitch-ui-interaction-20260922-113809`，正式 Backend 工作目录为 current/backend；`/etc/nginx/snippets/medical-monitor.conf` 将 `/medical-monitor/` 转发到 loopback 18765，尚无正式 AI 子路由。p6-ai.service 在 `/opt/medical-monitor-p6`，独立 18766 服务正常。服务 PID/启动时间、Nginx 文件哈希、两个静态入口哈希及预算文件哈希见 before/after 证据。未执行 Nginx -t/reload、current 切换、服务重启、文件上传或真实 API 请求。

后续需明确授权：V2 静态构建发布、只增加 AI 子路径的 Nginx 修改与 reload、正式浏览器入口/权限验收、执行备份/回滚。任何真实模型复验还须单独批准使用剩余额度。TW-TTS 真机、麦克风、Security Gate、PR/P4 合并均另行授权。

最小发布建议：

1. 固定审核通过的 P6 SHA，生成带内容哈希的 dist；只交付静态资产，排除 tests、凭据和云端配置。本机至服务器的文件转移遵循用户暂存与完整性规则。
2. 发布窗口先复核线上漂移，备份当前 Web 目录、Nginx snippet、current 指向及哈希。保留旧静态 assets，避免缓存中的旧 index 无法加载。
3. **不切换整个 current release**，该链接同时承载原 Backend。将新 Web 放入独立版本目录，按经批准的静态目录切换办法只更新 Web；原 Backend/Broker/ACL、P6 服务和设备协议保持原发布。发布前确认目录权限、原 Backend 的静态挂载规则及原子切换方式。
4. 仅在现有 HTTPS server 内增加更具体的 `location ^~ /medical-monitor/ai/`，尾部斜杠转发 `http://127.0.0.1:18766/`；普通 /medical-monitor/ 和 WS 仍走 18765。不更改其它应用 location、TLS 或 Broker。AI 独立令牌继续由安全服务器配置管理，浏览器仅持有访问令牌。
5. 经授权执行 `nginx -t`，成功才 reload。先用 MOCK/不调用模型的鉴权及静态路由检查，再验收七页、WS、冻结/Canvas、token 区分、AI 失败与播报标签。正式真实问答需另批预算，不能因为页面上线自动消耗两次额度。
6. 出现路径、鉴权、WS、资源 404 或六页回归即回滚：恢复原 Web 入口/资产与 snippet，`nginx -t` 后 reload；核对原发布 SHA/哈希、四项服务状态与原六页连接。恢复原六页后 AI 正式入口撤销；P6 独立服务/预算不改动。不回滚整个 current、不重启 Backend/Broker。

回滚是未来授权窗口中的操作说明。本轮只提供候选和证据，正式 `/medical-monitor/` 尚未切换。
