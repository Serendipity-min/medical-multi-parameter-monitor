# R52 · S3 正式后端公开查看回执

2026-11-12。依据 [R52 §4](https://github.com/Serendipity-min/medical-multi-parameter-monitor/blob/55799d5/node-b/docs/PI-REVIEW/R52-20261112.md)。源码 `caeab01aed5cda5da4505648bb0c3d05a8fc6785`，后端基于 `79143ba`。

## 行为与测试

- 只有 `MONITOR_PUBLIC_VIEW=1` 时，查看连接才跳过令牌比对。Origin 和网关白名单、5 s JSON 首帧时限、4,096 字符上限及令牌字段的 ASCII 校验继续执行。关闭开关或未设置时，必须用正确的查看令牌。启动仍要求配置 `MONITOR_VIEW_TOKEN`。
- 默认后端套件 49 项通过、6 项跳过。five 档补跑 16 项通过，覆盖公开查看、私有查看和五节点适配。NIBP 恰好 90 秒的既有边界用例在本地失败，使用未修改的 `79143ba` 独立重现。本次没有改动 NIBP 逻辑。
- 部署前用新浏览器上下文重现“服务器未开放公开查看”。部署后以同样方式直接打开正式页面，未输入令牌，也未操作页面。浏览器首帧的令牌字段为空，收到 `GW-C-001 / five / OFFLINE`，页面显示“等待设备上电”，令牌框未弹出。
- 无痕截图存于本机 EFS 的 `WP-AY0-S3-20261112/public-view-standby.png`，SHA-256 `0da34e5f835dc46fb596d07fa027731ec27d9c829f6bbf04460ef28542145336`。本次页面核验按 C 断电场景进行。

## 部署证据

- 发布 `wp-ay0-s3-caeab01`。未压缩 tar 为 81,920 字节，SHA-256 `904d7fb1ea3881dacfaa387118906406989e59c13b534f019d3f41b1a793dd78`。使用 `git -c core.autocrlf=false archive --format=tar` 生成，15 个成员逐文件与提交中的 Git blob 字节一致，服务器解包后再次逐文件比对通过。
- 正式运行目录 `/opt/medical-monitor-h3/releases/wp-ay0-s3-caeab01/cloud/backend`。部署的 `app/main.py` SHA-256 `72864f7ed89f5402ca514e4ff7cd277bc2b47df47842b3920cbb7fbaa2cd2f93`。
- 备份 `/opt/medical-monitor/backups/wp-ay0-s3-caeab01/` 含旧 release、env、systemd 单元及 drop-in。新环境文件 `/opt/medical-monitor-h3/formal/wp-ay0-s3-caeab01/backend.env`，设置 `MONITOR_PUBLIC_VIEW=1`。保留 `MPM_NODE_PROFILE=five`、`MONITOR_GATEWAY_IDS=GW-C-001`、Origin 白名单、MQTT 配置及原 `MONITOR_VIEW_TOKEN`。
- 只重启 `medical-monitor-h3-webbackend.service`。后端健康为 `ok`，MQTT 已连接。WebAI、Mosquitto、Nginx 的主进程前后一致。WebAI 健康为 `ok`、快照模式 `MONITOR`，用其现有配置成功读取 `GW-C-001 / five` 快照。
- WebAI 服务的独立提问令牌在腾讯服务器 `/opt/medical-monitor-h3/formal/20261021T093335Z/ai.env` 中，变量名 `P6_AI_TOKEN`。

## 回滚

用 `sudoedit /opt/medical-monitor-h3/formal/wp-ay0-s3-caeab01/backend.env` 删除 `MONITOR_PUBLIC_VIEW=1` 一行，然后执行 `sudo systemctl restart medical-monitor-h3-webbackend.service`。只读查看将重新要求正确令牌，现有页面会显示令牌兜底入口。保留其他环境变量及 WebAI 配置。
