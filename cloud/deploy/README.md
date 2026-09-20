# MQTT 升级部署与回滚

入口复用主域名 `/medical-monitor/`、既有 Nginx 和 HTTPS；Backend 仅监听 127.0.0.1:18765。
项目独立目录 `/opt/medical-monitor/`。用户已开放 TCP 8883；不开放后端端口。

## 离线升级（由旧 WSS 发布迁移一次）

1. 本机测试并构建 web/dist，下载锁定 Python 依赖的 Linux CPython 3.12 wheels 到 `E:/Server_file/<本次任务>/wheels`。
   命令参数：`pip download --only-binary=:all: --platform manylinux2014_x86_64 --python-version 312 --implementation cp --abi cp312 -r cloud/backend/requirements.lock -d <暂存目录>`。
2. 本机组装 zip，根目录为 backend、web/dist、deploy、broker、tools/mock_mqtt、wheels；不包含任何凭据。
3. 仓库外生成升级 JSON：host、certificate（服务器已有证书路径）、private_key（已有密钥路径），
   roles 下有 backend/mock/gateway，每项含 username、password、client_id，mock 另含 gateway_id。
   用户名须与 broker/acl 一致：backend-reader、mock-publisher、gateway-c。
4. 用 SSH 别名上传 zip、upgrade_mqtt.py、私有 JSON 到项目 incoming；本机和远端核对字节数及 SHA-256。
   所有文件必须经 `E:/Server_file`，≤1GB 才可传输；核验成功只删除本次精确暂存文件。服务器不得下载依赖。
5. 服务器需已有 Mosquitto 2、Python venv、Nginx。若缺包，先按同样规则本机取得匹配安装包。
6. 运行：`sudo python3 /opt/medical-monitor/incoming/upgrade_mqtt.py --bundle <zip> --sha256 <校验值> --config <私有JSON> --release <唯一编号>`。

脚本拒绝已有 broker 目录、占用的 8883、重复发布编号；它是一次性迁移工具，不用于重复覆盖部署。
Python 依赖使用 --no-index；保留旧 current、backend.env、服务文件和 Nginx 备份。
Backend 配置单独放在 ubuntu 可遍历的 mqtt-config（700，JSON 600），避免 root-only 目录导致服务读配置失败。
启动 TLS Broker、切换 current、检查后端 MQTT 订阅健康、nginx -t/reload，再启动服务器 Mock 和证书定时器。
失败回滚旧 current/env 并停止新服务。保留失败目录用于排错，不自动递归清理。

## 当前发布与运维

- current：`releases/mqtt-v07-20260920-01`；旧版：`releases/phase1-20260919-01`。
- 项目服务：medical-monitor（Backend）、medical-monitor-mqtt（Broker）、medical-monitor-mock（服务器合成源）。
- medical-monitor-certificate.timer 每天检查现有证书文件并更新 Broker 副本；它不执行申请或续签、不下载。
- 原系统 mosquitto 服务未启用，项目使用独立配置；TLS 不降级为明文，禁用匿名。
- Broker 只记录 systemd 生命周期，关闭连接地址/载荷日志。敏感配置和备份不入库。
- 查看 `systemctl is-active` 与 loopback `/api/health`，勿把真实主机、口令或完整日志复制进项目文档。
- 删除上传的临时私有 JSON；长期凭据保留在受限配置目录。

## 回滚 MQTT 升级

停止 medical-monitor-mock 和证书 timer；将 current 原子切回备份记录的旧发布，恢复该次 backend.env，
重启 medical-monitor，然后停止项目 medical-monitor-mqtt。旧版依赖与代码保留在原发布目录。
本次升级没有改变 Nginx 路由；若后续需改动，仅改本项目 include，nginx -t 后 reload，不覆盖其他任务改动。
备份目录为 `backups/mqtt-v07-20260920-01`，整份 Nginx 配置只留服务器本机受限备份。
首次升级曾因配置目录权限失败，已触发并验证自动回滚；更正后部署成功。
旧 install.py 仅为历史首次 WSS 部署工具，不再适用于当前代码。
