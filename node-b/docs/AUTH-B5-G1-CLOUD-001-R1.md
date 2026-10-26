# AUTH-B5-G1-CLOUD-001 R1｜仅测试云配置，禁用

`enabled=false; owner_approved=false; executions=0`。依据MPM-B5-002 G1；[共同绑定](B5-G0-SPLIT-AUTHORIZATIONS.md)适用。不得连接实板、写Flash/sector3、运行B5START或恢复生产联网。

## 待批准的唯一变更集

推荐方案A：复用现有8883/TLS，新增专用角色；独立Backend绑定专用Unix socket，另起独立前缀/配置/pid/log的TLS反代进程，仅监听`127.0.0.1:18775`，不改正式nginx。其`/medical-monitor/`剥离前缀后转独立Backend，复用已验收Web固定base和WSS路径，单独关闭AI代理。既有证书/私钥只能由批准的服务权限引用，不能复制进源码或日志。测试Backend只允许GW-B5-001，使用冻结B5软件树及独立配置/日志/令牌、数据目录和服务身份。**18775空闲仅为G0瞬时证据，执行前再查。**

方案A浏览器由独立SSH本地转发18775连接云端TLS进程，专用浏览器profile仅对该进程设置已批准的私有证书域名→127.0.0.1解析规则，访问HTTPS同名SNI、18775端口、`/medical-monitor/?gateway=GW-B5-001`；保留CA/名称校验，无全局hosts修改、无证书例外。Origin精确含该端口。取得的是**真实云端WSS经SSH隧道观察**，不能冒称公网浏览器直接可达。正式Backend、AI、nginx、防火墙不变。

备选方案B：独立Backend不变，另用负责人批准的**专用测试域名及覆盖该名称的有效证书**，在既有443上新增独立SNI虚拟站点，站内仍使用`/medical-monitor/`固定base和WSS路径。不新增公开端口、不改正式站点的upstream/令牌/Hub；需批准DNS/证书来源、测试server块及一次语法检查后的正式nginx reload。当前没有给测试域名或证书配对赋值，不虚构URL；这些是选择B前的明确缺口。可取得浏览器公网WSS直达证据，需更多基础设施与共享nginx变更审查。不得复用正式域名同路径来覆盖现有Web。8445即使空闲也不使用，合同不允许增开公开端口。

两方案均不把GW-B5-001加入当前正式Backend，不复用正式MQTT/浏览器凭据，不更新正式AI服务。当前线上Hub缺少B5会话代次隔离，不能直接只加白名单。A不需新增域名/公网端口且不改正式nginx，优先；B的域名/证书未落实前只保持设计可行，不称入口已可用。

## 账号、Client ID、ACL

- 发布角色`b5-gateway`，C客户端`b5-c-isolated`，Gateway `GW-B5-001`，端口8883；独立测试接收角色建议`b5-observer`、Backend客户端`b5-backend-isolated`，独立证据观察客户端`b5-evidence-isolated`。凭据由负责人批准的仓库外流程创建，不在终端/Git打印；本卡未要求或生成密码。
- 发布者只允许`topic write mpm/v1/GW-B5-001/#`，无read/readwrite/pattern授权，无`mpm/v1/#`或正式GW-C-001权限。测试接收角色只读`mpm/v1/GW-B5-001/#`，无写权限；不得给跨Gateway通配订阅。所有C载荷由冻结候选强制MOCK/synthetic；ACL本身不验证JSON字段。
- 不设置全局`use_username_as_clientid`，不改正式客户端ID。G0最近120行日志未见测试ID不等于没有冲突；执行前审查实际连接/日志，确认三个新ID没有占用，禁止拿正式ID试连。现有password_file/ACL无客户端ID绑定证明，固定新ID与独立凭据属于本次运行隔离约束，不宣称Broker强制绑定已验证。

## 动作顺序与限额

1. 负责人批准方案、具体私有配置路径、一次变更附件与SHA后，先在受限位置备份当前业务Broker配置/ACL/password_file、服务单元及受影响文件，记录属主/权限/SHA。完整password_file若需备份只在服务器受限备份及本机EFS，不输出密码散列。备份不授权回滚。
2. 离线生成最小增量，只增加测试角色和专属资源，逐条核对正式角色规则保持字节/语义不变。配置语法及ACL评估先通过。当前Broker单元无ExecReload，禁止直接套用`systemctl reload`；G0实际包装器已确认转发SIGHUP，批准附件可精确选择`systemctl kill --kill-whom=main --signal=HUP medical-monitor-mqtt.service`一次，执行前重核unit/MainPID/包装器SHA。正式Broker不停止、不重启；重载失败或新规则未生效停，不临时改成restart。
3. 独立Backend服务启动至多1次，180秒准备上限；失败停止留日志，不自动清理/回滚。TLS证书/SNI有效、8884仍关闭、正式服务PID/健康和正式配置未改变才继续。
4. 仅在单独批准附件包含账号冒烟检查时，运行一次≤120秒受控检查：只使用上述测试ID，正例发布仅测试命名空间且MOCK；订阅只测试命名空间。负例采用负责人预留的非正式拒绝测试命名空间，不向GW-C-001发任何试探消息；若ACL静态评估不能证明拒绝则不发。记录CONNECT/SUBACK/Broker接收/Backend接受/WSS各层证据，不能把SUBACK当Backend验收。此检查不运行B5START、不代替G3实板300秒。

到期、身份冲突、越权或误标LIVE、正式服务异常即停止，停止测试会话；配置回滚仅按R-CLOUD另批事务。G0实际执行：0。这里未启动任何测试服务、隧道或浏览器profile，未复制私钥，未改防火墙。18785已被其他服务占用，明确不复用。
