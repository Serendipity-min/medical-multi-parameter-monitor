# 部署与回滚

按用户要求复用主域名的 `/medical-monitor/`，不新建子域名，不另起 Nginx。
本项目目录 `/opt/medical-monitor/`；服务只监听 `127.0.0.1:18765`。
已有 443 即可访问 HTTPS/WSS；不需要开放 18765。防火墙变更由用户操作。

## 首次部署

1. 本机完成测试及 `cloud/web` 构建。
2. 本机将 Linux CPython 3.12 的 wheel 下载到 `E:/Server_file/<本次任务>/wheels`：

```powershell
python -m pip download --only-binary=:all: --platform manylinux2014_x86_64 --python-version 312 --implementation cp --abi cp312 -r cloud/backend/requirements.lock -d E:/Server_file/<本次任务>/wheels
```

3. 在该暂存目录组装 zip，根目录包括 `backend/`、`web/dist/`、`deploy/`、`wheels/`。
   不包含 `.env`、本机配置、node_modules、私钥或服务器连接信息。另行生成外部 `backend.env`。
4. 通过本机已配置 SSH 别名上传 bundle、`install.py` 和 env 到项目私有 incoming 目录。
   先比较 SHA-256 与字节数。文件超过 1GB 必须暂停，不能走此上传流程。
5. 明确指定已有主域名 Nginx 配置，运行：

```text
sudo python3 /opt/medical-monitor/incoming/install.py \
  --bundle /opt/medical-monitor/incoming/release.zip \
  --sha256 <本机计算的SHA256> \
  --environment /opt/medical-monitor/incoming/backend.env \
  --nginx-config <已核对的现有站点配置> \
  --release <唯一发布编号>
```

脚本仅支持首次部署；发现已有服务/路径会停止，避免覆盖已有版本。
依赖仅通过 `pip --no-index --find-links` 安装，禁止服务器自行下载。
配置备份在 `/opt/medical-monitor/backups/<发布编号>/nginx-site.conf`，对应目标保存在 `nginx-target.txt`。
先启动后端并检查 `/health`，再添加 include，`nginx -t` 成功后 reload。
安装失败会恢复原配置、停止本次服务并删除本次 include；保留发布目录供排错。

上传且远端哈希核验成功后，删除本次精确对应的本机暂存文件。不能清空整个 `E:/Server_file`。
私有配置不是暂存文件，保留在用户控制的凭据目录，不能提交到 Git。

## 运行查看

```text
sudo systemctl status medical-monitor --no-pager
sudo journalctl -u medical-monitor --since today --no-pager
curl http://127.0.0.1:18765/health
```

正常服务日志不含 Token/载荷。不要把未经脱敏的系统或其他站点日志提交到仓库。

## 回滚首次部署

先比对备份与当前站点，确认此后是否有其他任务改动。若仅增加了本项目 include，可恢复备份；
若已有其他改动，只移除本项目 include，不得用旧备份覆盖他人修改。
运行 `nginx -t`，通过后 reload；再 `systemctl disable --now medical-monitor`。
保留项目发布目录及备份作为证据。删除部署目录或凭据不属于例行回滚，不自动执行。

版本升级需另行生成发布编号、保留旧 current 目标，并按当次授权执行；本脚本不会隐式升级。
