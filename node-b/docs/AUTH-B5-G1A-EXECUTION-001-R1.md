# AUTH-B5-G1A-EXECUTION-001 R1｜一次云部署与独立冒烟

依据负责人`MPM-B5-002-G1-G2RO`明确批准G1-A；不再重复请求该项许可。技术启用仍需离线审阅通过及EFS授权附件绑定。`enabled=false`为本草案状态，实际启用值只在受限单次附件中；不改变G2/G3/R-CLOUD批准状态。

## 冻结对象

- 事务`g1a-1ceb665360`，服务器独占根目录`/opt/medical-monitor-b5/g1a-1ceb665360`；配置位于`config/backend.json`、`config/backend.env`、`config/nginx.conf`；部署B5冻结`cloud/backend/app`与既有`cloud/web/dist`，源码不改。
- 新OS角色`b5-monitor`，system/user-group、无home、shell=`/usr/sbin/nologin`；独立Backend与TLS工作进程，不复用正式角色。服务`medical-monitor-b5-g1a-1ceb665360-backend.service`和`...-tls.service`，只启动各一次，`Restart=no`，最长驻留21600秒。到期仅停止专属实例，不删角色/配置/证据、不自动恢复或联网；交接写明启动与到期UTC。
- 独立Backend为`run/backend.sock`，仅Gateway `GW-B5-001`；独立令牌/日志。独立nginx只监听`127.0.0.1:18775`，固定`/medical-monitor/`剥离前缀后转该socket，AI路径404。独立prefix/pid/lock和5类临时目录均在本事务BASE内，不能继承Debian绝对temp目录并改变正式nginx目录属主。
- TLS引用现有已核验chain/key路径，真实域名、SNI、Origin、令牌/账号口令均在EFS附件，Git不填值。**不读取/复制私钥正文**，不改证书校验，不新增公网端口/8884，不改正式nginx/Backend白名单/Hub/AI/P6。
- 只追加`b5-gateway`写`mpm/v1/GW-B5-001/#`、`b5-observer`读该namespace，原ACL/password_file保持原字节前缀、属主和权限。不会给测试用户跨Gateway或发布正式权限；不会让发布者读取。
- 修订包`deployment-package-r2-private.json` SHA256 `dcee1658be5ce4db2531975069441444a0f50078828321a3e978a8352b520db0`。原41863f包保留，**从未执行**；r2纠正nginx共享temp目录风险。配置/补丁逐项SHA见`node-b/evidence/B5-G1/prepare-r2.json`，工具/监督器及冒烟脚本SHA在启用附件冻结，任一变化先停。

## 事务A：一次安装，180秒服务器硬限

1. 重新只读核正式四服务MainPID、包装器SHA `e9f215332b5d6822984f4bf7f19d3b97a242eb897e5c97fe7ba9ea48608b1340`、完整受影响配置SHA、18775空闲、测试角色/目录不存在。与G0或本次准备快照不符即停；不换端口/复用账号。
2. 先在本机受限EFS和服务器`before-private`完整备份ACL/password_file/业务配置与服务原件及mode/uid/gid。服务器备份root700，私有文件600；真实口令、散列、主机信息不打印。
3. 建立新角色、专属配置/服务/源码，执行独立`nginx -t`。原正式角色和配置不改；确认最小追加补丁后原路径原子替换ACL/password_file，保留原权限。
4. 仅一次`systemctl kill --kill-whom=main --signal=HUP medical-monitor-mqtt.service`。实际systemctl已只读核实支持该参数；不能改为restart/stop/reload。HUP意图和每条真实命令退出码写受限账本。随后仅`daemon-reload`读入新unit、各启动一次专属Backend/TLS；不重启正式unit。
5. 正式MainPID及不受影响配置SHA保持，记录新服务PID/UTC/期满UTC。失败即停、不重试、不自动回滚。外层监督器210秒涵盖SSH运输开销，远端实际写事务用`timeout 180s`且内部170秒预算。

## 事务B：一次≤120秒冒烟，独立计数

部署成功后用同一单次附件授权独立smoke阶段；失败不重发。先本机建立独占SSH本地端口转发至云`127.0.0.1:18775`，WSS使用真实域名/SNI/CA及正确Origin，连接层定向本机转发端口，不改全局DNS/hosts或关TLS验证。

正例MQTT3.1.1：`b5-c-isolated`发布、`b5-evidence-isolated`只订阅B5 namespace，实际CONNECT/SUBACK逐条留证。只发布6条当前UTC、非保留的**人工生成MOCK/synthetic冒烟夹具**（Gateway/Node-B ONLINE、HR60、RR/TEMP INVALID、100点ECG），不冒称ADC实测或B→C传输验收。保存Broker订阅实收原字节、Backend health接受增量/拒绝计数及WSS会话/内容对应。

负例只用`mpm/v1/GW-B5-DENY-001/NODE-B/telemetry/hr`，两个身份各一次QoS1。诊断客户端`b5-g1-deny-pub-isolated`、`b5-g1-deny-obs-isolated`采用MQTTv5，要求实际PUBACK `0x87 Not authorized`；其他原因或仅未收消息不算拒绝通过。不订阅越权namespace、不向GW-C-001发送任何测试包。发布者无读授权的结论来自静态最小ACL，本轮不假称其所有读取负例已实测。

结束关闭本次客户端/SSH转发，独立服务按6小时上限驻留，只接收不自动发布，下一轮须重新确认其健康。配置/角色撤销、应用/sector3写入、B5START、任何实板和R-CLOUD实际回退**均未获本卡许可**。ROM等历史门禁不因本次云冒烟通过而改变。
