# R66 · 后端依赖和 WebAI 重部署回执

2026-11-13，北京时间。R66 部署及断电验收检查通过，待 PI 裁定。部署卡来自 [PR #21](https://github.com/Serendipity-min/medical-multi-parameter-monitor/pull/21) 的 `7f04a73faa343f02109d7679497cf436feaa3a8b`，卡片 SHA-256 为 `80cc8bf1ad452451b52580d6d09229a7e3a8287d65183368a617744c876d8b32`。回执分支基于 `origin/main@10b6880`。原回执分支已从远端删除，本次使用 `codex/r66-closeout-redeploy`。

## 制品与配置

- 源码 `a5c6dd5f2d2509e5259986e29248076a3ce187ac`，标签 `closeout/20261112-dependencies`。与 main 的运行文件一致。PR #21 基线差异仅涉及 AI 测试。
- `closeout-a5c6dd5.tar` 为未压缩 Git 归档，122,880 B，SHA-256 `e1942e91d613940188e24795a918731c1a7baa09e2d2e153e377fa718fe8ba83`。按卡片选取两套服务的目录（排除 tests）和 `cloud/microphone/protocol.py`。本机归档时显式使用 LF，23 个归档文件全部与 Git blob 逐字节一致。服务器逐个重算通过。切换前后端的 8 个 Python 文件与新归档一致。
- 新 release 为 `releases/closeout-a5c6dd5`，新环境为 `environments/closeout-a5c6dd5`，均在 `/opt/medical-monitor-h3` 下。服务器 Python 3.12.3，使用本机中转的 20 个 wheel 离线安装，服务器核对全部 wheel 的 SHA-256。清单 SHA-256 `3d895dc1a9bded7d92c599f9677658ed1a2c4b1413d9001dd098484f387294d4`。
- 后端按 requirements 与 lock 安装。WebAI 的 `httpx` 和其配套依赖沿用旧环境的锁定版本。Linux 下将 lock 中的 `colorama` 显式安装，使新环境保留旧环境的版本。全量 freeze 与 lock 加上述沿用包核对一致。
- 后端继续使用 R64 的 env。WebAI 的新 `formal/closeout-a5c6dd5/ai.env` 保持原属主和 0600 权限。WebAI drop-in 先用空的 `EnvironmentFile=` 清空基础 unit 的列表，再加载新副本。进程只加载这一个文件，六项沿用键均在进程内核对通过。

| WebAI env 键 | 操作 |
| --- | --- |
| `P6_GATEWAY_IDS` | 新增 |
| `P6_SNAPSHOT_MODE` | 改值并显式确认 |
| `MPM_NODE_PROFILE` | 保留 |
| `P6_MONITOR_WS_URL`、`P6_MONITOR_ORIGIN`、`P6_MONITOR_VIEW_TOKEN`、`P6_AI_TOKEN` | 保留，进程实测一致 |
| `P6_MQTT_MODE`、`P6_MODEL_MODE` | 保留，进程实测一致。原模式分别为 `DISABLED` 和 `DOUBAO`，本轮问答记录为 `NOT_CALLED`。 |

`pip check` 为 `No broken requirements found.`。完整 `pip freeze` 如下。

```text
annotated-doc==0.0.5
annotated-types==0.8.0
anyio==4.15.1
certifi==2025.11.12
click==8.5.0
colorama==0.4.6
fastapi==0.135.1
h11==0.16.0
httpcore==1.0.9
httpx==0.28.1
idna==3.20
paho-mqtt==2.1.0
pydantic==2.12.5
pydantic_core==2.41.5
sniffio==1.3.1
starlette==1.6.0
typing-inspection==0.4.4
typing_extensions==4.16.0
uvicorn==0.40.0
websockets==17.4
```

## 执行与验证

| 时间 | 步骤 | 结果 |
| --- | --- | --- |
| 15:40:32.767 | 新制品、配置与备份准备 | PASS |
| 后端切换前 | 以 `medical-ai` 运行 `python -I`，加载新 WebAI env 与工厂 | PASS，正式网关单一白名单，读取模式为 MONITOR |
| 后端切换前 | 进程内合成 LIVE 问答 | PASS，温度和高压分别返回 HTTP 200 并映射至 NODE-D/TEMP、NODE-E/NIBP；GW-B5-001 为 403，GW-DEV-001 为 422。合成检查使用临时用量目录，MQTT 与模型均未调用。 |
| 后端切换前 | 以 `medical-ai` 运行后端 lifespan 并加载 R64 env | PASS，隔离 MQTT 网络连接，完成配置、适配器和应用初始化。 |
| 15:41:54.328–15:41:55.937 | 切换并只重启 webbackend | PASS，health 为 ok、MQTT 已连接。播报及设备播报开启，HR 键未设置。无令牌 WSS 快照为 five / GW-C-001 / OFFLINE，当前播报为空，历史为空。新环境打印 websockets 17.4，现网进程映射也来自新环境。 |
| 15:42:03.886–15:42:05.837 | 切换并只重启 webai | PASS，经 Nginx 的 AI health 为 ok；正式温度请求有令牌为 200，网关 GW-C-001，无令牌为 401。模型标记 NOT_CALLED，设备下发 PAUSED。重验无令牌 WSS，仍为 OFFLINE 且无播报。 |

断电时 WebAI 温度问答原文：

> 没有可用的当前监护事实，请确认数据源连接与采集状态。

| 进程 | 部署前 PID | 后端切换后 | WebAI 切换后 |
| --- | ---: | ---: | ---: |
| webbackend | 1369804 | 1646414 | 1646414 |
| webai | 1244393 | 1244393 | 1646601 |
| Mosquitto 包装器 | 3253 | 3253 | 3253 |
| Mosquitto | 3525 | 3525 | 3525 |
| Nginx | 3383 | 3383 | 3383 |

ACL、Broker 配置、Nginx 配置和网页保持原状。现场 COM15 未枚举，网关在验证时持续 OFFLINE。真人、设备实时数据和设备音频下行为 NOT_RUN。

## 备份与回退

服务器备份目录 `/opt/medical-monitor/backups/closeout-a5c6dd5-r66-38u9dy0r`，含两服务的原 unit、全部原 drop-in、env 副本、前置 PID、归档清单及部署验证回执。部署后重算原始 8 个配置文件的 SHA-256，与切换前逐项一致。回退脚本语法检查通过，本次未触发回退。

回退某个服务时在服务器运行对应命令。脚本删除该服务的 `90-closeout.conf`，重载 systemd 并仅重启对应服务。

```sh
sudo -n python3 /opt/medical-monitor/backups/closeout-a5c6dd5-r66-38u9dy0r/rollback.py backend
sudo -n python3 /opt/medical-monitor/backups/closeout-a5c6dd5-r66-38u9dy0r/rollback.py ai
```
