# P 第一阶段云端执行报告

日期：2026-09-19。阶段：MMP-P-SOW-001 v0.1，云端先行与 Mock Gateway 联调。
执行分支：`codex/p-cloud-phase1`，基于稳定 main `533eeb2`。不合并 main。

## 实施结果

- 建立 `cloud/backend`、`cloud/web`、`cloud/deploy`、`cloud/tools/mock_gateway`。
- FastAPI + Uvicorn；MOCK/1 适配器与内部 Frame 分离；MVIEW/1 浏览器快照。
- Web 显示 ECG / PPG / RESP、HR / RR / SpO2 / PR / NIBP / TEMP、在线状态、更新时间。
- 所有页面明确标注 SIMULATION；不接收真实患者数据，不实现硬件控制或报警。
- Mock 在本机运行，可动态切换节点、质量、LIVE/REPLAY、断网与静默。
- 复用已有主域名 HTTPS，在 `/medical-monitor/` 下提供页面与接口。
- 服务器独立目录 `/opt/medical-monitor/`，systemd 服务 `medical-monitor`，单进程监听 `127.0.0.1:18765`。

用户在本次对话明确要求主域名路径部署，覆盖合同中“建议独立子域名”的部署建议。
已有 443 足够；未修改安全组/防火墙、证书、DNS，也未新开其他公网端口。

## 已完成验证

| 验证 | 结果 / 证据 |
|---|---|
| 后端协议与状态测试 | 14 项通过；包括重复帧、断线失效、数据过期、角色分离、非文本帧拒绝 |
| 前端 | TypeScript 检查与 Vite 生产构建通过 |
| 真实 HTTPS/WSS | 12 项公网链路验收通过，使用系统证书信任链 |
| 真实浏览器 | 11 项通过：Canvas、Invalid、两节点上下线、REPLAY、网络恢复、静默失效、刷新订阅、Backend 重启、Nginx reload、手机布局 |
| 既有页面 | 主页面与两条现有项目路径的 HTTP 状态及内容 SHA-256 前后一致 |
| Nginx 修改范围 | 原配置除增加本项目 include 外逐字一致；`nginx -t` 通过再 reload |
| Backend 监听 | `ss` 核实只有回环监听，systemd active |
| 部署来源 | 运行源文件、前端构建产物、service/snippet 与本机 SHA-256 一致 |
| 干净环境 | 本机新建 venv 运行测试；服务器新建 venv 从上传的 Linux wheels 离线安装成功 |

证据位于 [cloud/evidence](../../../../cloud/evidence)：
`public-wss-acceptance.json`、`browser-acceptance.json`、`existing-pages.json`、
`deployment-transfer.json`、`protocol-fix-transfer.json`、`deployed-source-sha256.json`，以及 LIVE/REPLAY/手机截图。
报告及脚本不包含真实服务器地址、Token、私钥或连接主机映射。

## 部署与备份

初次发布编号：`phase1-20260919-01`。
Nginx 配置原件：`/opt/medical-monitor/backups/phase1-20260919-01/nginx-site.conf`。
实际目标由同目录 `nginx-target.txt` 记录。凭据在服务器私有 config 与本机仓库外配置中。

首次包约 3.4 MB，包含 15 个 Linux/通用 wheel。全部先下载到本机 `E:/Server_file`，
上传后核实 SHA-256 与字节数，再清除本次精确暂存文件。服务器未从原始来源下载依赖。
随后对 `backend/app/main.py` 做了非文本帧/非 ASCII 令牌的协议拒绝修正：单文件同样经本机暂存、
上传哈希核验与清理；旧文件已备份。最终代码以 `deployed-source-sha256.json` 为准。

恢复步骤见 [部署与回滚说明](P_云端部署与回滚说明.md) 及 [部署 README](../../../../cloud/deploy/README.md)。

## 使用与交接

打开主域名的 `/medical-monitor/`，输入本机私有凭据文件中的只读 Token。
页面仅把 Token 保存在当前标签页内存，刷新后需要重新输入。
本次为展示保留一个本机 Mock 进程；关闭本机/停止进程后云端显示 OFFLINE/STALE，属于预期行为。
运行控制文件、进程号及凭据保存在本机 `.codex/private/`，未纳入 Git。

第二人启动步骤见 [cloud README](../../../../cloud/README.md)。已验证新虚拟环境安装运行，但尚无第二位人员实际复核记录。
已有用户未提交的合同、硬件文档和草稿原样保留，不混入本次代码提交。

## 阶段边界与已知限制

- 尚未连接真实 Gateway-C 或任何传感器；所有结果均为模拟链路验证。
- 正式 MMP/2 二进制适配器、CAN、离线 Flash、数据库、长期记录、复杂用户权限、报警均未实现。
- 仅一个 Gateway、一个 worker、最多 32 个浏览器；内存状态在 Backend 重启时清空。
- REPLAY 只显示独立到达记录，不提供历史波形播放器，也不刷新 LIVE 状态。
- 波形采用最新快照有界投递；慢浏览器可能跳帧，前端断开绘制缺口，不保证无损录制。
- 本轮未做 24h 稳定性测试或两台独立电脑的性能基准；不将本轮结果解释为最终整机验收。
- 测试输出有两条上游测试客户端弃用提示，不影响测试通过；未为消除提示升级运行依赖。
