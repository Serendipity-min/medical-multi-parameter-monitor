# P 第一阶段：云端先行

> 当前代码为从 `codex/p-cloud-phase1` 完整迁入 `dev/p-gateway-cloud-v07` 的 WSS 历史基线。
> 新执行依据为 [P 合同 v0.2](../doc/P/P_第一阶段_GatewayC云端Web执行方案合同_v0.2.md)。
> 下方启动与测试说明仍对应旧实现；完成 MQTT/TLS 迁移后再更新，不能据此判定 v0.2 已验收。

范围依据 `doc/P/P_第一阶段_云端先行执行方案合同_v0.1.md` 与 v0.6 总方案。
仅实现模拟网关 → Backend → Web。正式 MMP/2、硬件控制、数据库和报警不在此阶段。

## 本机启动（PowerShell，Python 3.11+ / Node 22.12+）

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r cloud/backend/requirements.lock

# 两个随机值仅在当前终端环境中生成，不写进代码或命令字面量。
$env:MONITOR_DEVICE_TOKEN = [Convert]::ToBase64String([Security.Cryptography.RandomNumberGenerator]::GetBytes(36))
$env:MONITOR_VIEW_TOKEN = [Convert]::ToBase64String([Security.Cryptography.RandomNumberGenerator]::GetBytes(36))
$env:MONITOR_ALLOWED_ORIGINS = 'http://127.0.0.1:5173'
.\.venv\Scripts\python.exe -m uvicorn app.main:app --app-dir cloud/backend --host 127.0.0.1 --port 18765 --ws-max-size 65536 --no-access-log
```

另开终端运行前端：

```powershell
cd cloud/web
npm ci --no-audit --no-fund
npm run dev
```

访问 `http://127.0.0.1:5173/medical-monitor/`，输入对应的只读 Token。
从受控凭据文件或进程环境取得 Token，不将其提交到 Git。
页面刷新后需要重新输入 Token；同一次页面会话的网络断线与 Backend 重启会自动重连。

Mock 启动方式及外部配置见 [Mock README](tools/mock_gateway/README.md)。
部署方式见 [部署说明](deploy/README.md)。

## 功能验证

```powershell
.\.venv\Scripts\python.exe -m pip install -r cloud/backend/requirements-dev.txt -c cloud/backend/requirements.lock
.\.venv\Scripts\python.exe -m pytest cloud/backend/tests -q
cd cloud/web
npm run build
```

远端模拟验收在本机运行 `cloud/tools/acceptance.py --config <外部配置> --report <输出JSON>`。
执行前停止该网关的其他 Mock 进程，避免同一 Gateway 的独占连接被占用。
该验收只注入模拟数据，不启动安全扫描。

## 结构与限制

- `backend/app/adapters.py`：MOCK/1 JSON → 内部 Frame。
- `backend/app/hub.py`：单 Gateway、单 worker、LIVE/REPLAY 隔离、5 秒过期、最多 32 个浏览器。
- `web/src`：TypeScript + Canvas 2D；8 秒有界窗口，掉帧时断开波形。
- `deploy`：现有 Nginx 的路径 include、systemd 和首次离线部署脚本。
- `tools/mock_gateway`：本机合成信号源与运行时控制文件。

内存状态在 Backend 重启时清空；不承诺长期记录或多 worker 水平扩展。
页面只展示 LIVE 的波形与标量；REPLAY 以独立到达记录与采集时间展示，不提供历史波形播放器。
