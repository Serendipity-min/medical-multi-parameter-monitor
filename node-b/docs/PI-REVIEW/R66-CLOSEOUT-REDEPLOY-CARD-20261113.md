# R66 · 结项重部署卡（后端依赖 + WebAI 整包）

2026-11-13，PI 签发。负责人已授权重新部署（原话：“允许重新部署”），由 Codex 用管理员权限执行。PI 的 `mmpm-deploy` 账号只能 status/restart，不能写 `/opt/medical-monitor-h3` 或 systemd，所以由 Codex 执行。**执行完成后交回执，PI 复核后再判定 PASS。**

## 0. 目的与范围
让现网与 main 对齐，只动两个服务：
- `medical-monitor-h3-webbackend`：代码不变，换到 websockets 17.4 的新环境。
- `medical-monitor-h3-webai`：从 H3 旧版（R48-S2 文件级组合）换为 main 的 `cloud/ai` 整包，并显式配置正式网关。

**禁止**：改 ACL；重启或 SIGHUP Broker；改 Nginx；发布网页；烧录或给设备上电（C 保持断电）；修改原有 release、环境或 env 文件（只新建，不覆盖）；在回执中写出任何令牌或密码原文。

## 1. 源码身份
- 运行代码基线 `a5c6dd5f2d2509e5259986e29248076a3ce187ac`（tag `closeout/20261112-dependencies`）。PI 已核对：`10b6880`、`b11e04a`（PR #21）的运行文件与它逐字节相同（`cloud/backend/app`、`requirements.txt/.lock`、`cloud/ai` 非测试、`cloud/microphone`）。
- PI 已只读核对现网：`releases/wp-az-2c97094/cloud/backend/app/*.py` 8 个文件与 main 的 SHA-256 全部一致，所以后端只换环境。现网环境 `environments/runtime-b8fbb14b5c35` 为 websockets 16.0（fastapi 0.135.1、uvicorn 0.40.0、pydantic 2.12.5、starlette 1.6.0、paho-mqtt 2.1.0），两个服务共用。
- 现网 WebAI 为 `releases/runtime-b8fbb14b5c35/cloud/ai`（`app.py` `248d1369…`，`facts.py` `df87c974…`），与 main 不同。

## 2. 制品（只新建）
1. Release `releases/closeout-a5c6dd5/`：从 `git archive a5c6dd5` 取 `cloud/backend`（去掉 tests）、`cloud/ai`（去掉 tests）、`cloud/microphone/protocol.py`，做成**未压缩 tar**。回执记录 tar SHA-256，并逐成员与 Git blob 核对；服务器解包后再逐文件重算。PI 已验证：只有这三部分就能导入 `cloud.ai.app` 并 `create_app()`。
2. 环境 `environments/closeout-a5c6dd5/`：Python ≥3.11，`pip install -r cloud/backend/requirements.txt -c cloud/backend/requirements.lock`。回执附 `pip check` 和完整 `pip freeze`，其中 websockets 必须为 17.4，其余与 lock 一致。旧环境不动。
3. WebAI env：把现有 `formal/20261021T093335Z/ai.env` **复制**为新文件（如 `formal/closeout-a5c6dd5/ai.env`，属主和权限与原文件相同），只追加或确认以下键：
   - `P6_GATEWAY_IDS=GW-C-001`（新增；不设则默认只允许 GW-B5-001，正式页面会返回 403）
   - `P6_SNAPSHOT_MODE=MONITOR`（必须显式写；main 默认已改为 MOCK，现网旧代码默认是 MONITOR，原文件可能没写这一项）
   - `MPM_NODE_PROFILE=five`；`P6_MONITOR_WS_URL`、`P6_MONITOR_ORIGIN`、`P6_MONITOR_VIEW_TOKEN` 沿用 R48-S2 的值（main 在 MONITOR 模式下缺少 WS_URL 会拒绝启动）
   - `P6_MQTT_MODE` 保持原值并在回执中记录（不得新设为 ISOLATED）；`P6_MODEL_MODE` 记录原值。注意：main 不再调用模型解释，付费模型已搁置。
   回执只列键名与“新增/保留/改值”，不写值。

## 3. 切换前在副本中检查（以 medical-ai 身份，用新环境和新 env）
- `python -I -c` 导入 `cloud.ai.app`，`Settings.from_env()` 输出 `gateways==('GW-C-001',)`、`snapshot_mode=='MONITOR'`。
- 进程内合成问答（同 R48-S2 方法，注入合成 LIVE 快照，不发 MQTT、不调模型）：对 `GW-C-001` 问“当前温度多少”“当前高压多少”都返回 200，facts 分别来自 NODE-D/TEMP 和 NODE-E/NIBP；`GW-B5-001` 返回 403；`GW-DEV-001` 返回 422（行为变化，旧版允许 GW-DEV-001，PI 已知悉）。
- 用新环境导入后端 `app.main:create_app`，与 R64 相同的 `backend.env` 加载不报错。
任一项失败即停止，不切换。

## 4. 切换（先后端，后 WebAI；每步检查通过后再进行下一步）
1. **备份**到 `/opt/medical-monitor/backups/closeout-a5c6dd5-r66-<随机>`：两服务的 unit、全部 drop-in、env，以及切换前 MainPID。写 `rollback.py` 并先做语法解析。
2. **后端**：新增 drop-in `90-closeout.conf`，内容先写空的 `ExecStart=`，再写新的 `WorkingDirectory`（新 release 的 `cloud/backend`）和 `ExecStart`（新环境 python，参数与现网相同：`-m uvicorn app.main:app --host 127.0.0.1 --port 18785 --no-access-log`）。`EnvironmentFile` 与 50–80 号 drop-in 一律不动。执行 `daemon-reload`，只重启 webbackend。
   - 检查：`systemctl show` 的 `MONITOR_BROADCAST=1`、`MONITOR_BROADCAST_DEVICE=1`、HR 键未设置；健康接口 `ok`、MQTT 已连接；无令牌 WSS 返回 `five / GW-C-001`、`OFFLINE`（C 断电）；进程实际加载的 websockets 版本为 17.4（`/proc/<pid>/maps` 或在该环境中打印 `websockets.__version__`）。
3. **WebAI**：新建 `medical-monitor-h3-webai.service.d/90-closeout.conf`，写空 `ExecStart=` 后接新的 `WorkingDirectory`（release 根目录）、`EnvironmentFile`（新 ai.env）和 `ExecStart`（新环境：`-m uvicorn cloud.ai.app:create_app --factory --host 127.0.0.1 --port 18786 --no-access-log`）。注意：基础 unit 里的 `EnvironmentFile` 会叠加，需确认新文件的键覆盖了旧值，或用 `EnvironmentFile=` 先清空再指定，并在回执中写明采用哪种方式。执行 `daemon-reload`，只重启 webai。
   - 检查：`/medical-monitor/ai/health` 返回 ok；经 Nginx 正式路径用 AI 令牌对 `GW-C-001` 问一次温度，应返回 200，`gateway_id=GW-C-001`（设备断电，值可为空或提示无数据，如实记录 answer 原文）；未带令牌返回 401。
4. Mosquitto（含包装器）、Nginx 的 PID 在切换前后应保持不变，写进 PID 表。

## 5. 回退
任一检查失败：删除对应的 `90-closeout.conf`，执行 `daemon-reload`，只重启该服务，即回到 R64/R48 状态（旧 release、环境、env 都没有改动）。回执写明是否触发回退。

## 6. 回执要求（`R66-…-RECEIPT-…md`）
源码 SHA、tar SHA 及成员核对结果；`pip freeze` 摘要和 `pip check`；env 键变更表（不含值）；§3 和 §4 每项的结果（PASS/FAIL/NOT_RUN）；PID 表；备份路径与回退命令；北京时间时间戳。真人和设备实时数据、设备音频下行一律记为 NOT_RUN（C 断电）。
