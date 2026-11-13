# B5-002 G0｜真实环境只读准入结论

**G0审查完成；G1/G2/G3均BLOCKED，尚未获准执行。** B5-0至B5-2软件/离线PASS保留，没有重跑Host/ARM、本地TLS链路或七页UI，没有重构冻结软件。2026-10-26当次只读SSH与TLS结果如下；设备与云端均无写入。

## 来源与范围

开工本地与远端均为`codex/node-b5-cloud-integration-20261026@baa08b850c9bd5e62ace7682a937b9c68423a0fa`，实现源码`c65fbedce7edf5d822c573ef5cdeb6471d1ae3d5`。使用既有SSH别名及代理认证，不读取私钥、不申请密码，不建立MQTT CONNECT/PUBLISH。服务器端按已运行业务Broker子进程的`-c`配置及include树追踪，按实际Backend进程环境/工作目录定位配置与源码，未将仓库模板当线上事实。

审计时间：`2026-10-26T10:57:55.034408+00:00`。运行中服务对应磁盘配置快照及原始进程/配置信息仅受限EFS保存。**这不是Broker内存ACL导出或认证实测**；未经G1批准不做身份试连和负例发布，也不保证过去某次reload后的内存配置与当次磁盘逐字节相同。

## 真实云端差异

| 项目 | 当次观察 | 裁定 |
|---|---|---|
| 业务Broker | 正在运行的Mosquitto为业务包装器子进程，8883监听，匿名关闭，password_file与ACL文件生效配置引用，无auth插件/global ACL/pattern规则 | 已追踪实际进程/配置，不是模板；测试身份未配置 |
| 8884 | 未监听 | 未开放、未修改；不等同于安全组控制面审计 |
| TLS | 服务器回环SNI/信任链校验通过TLS1.3；本机直达配置Broker的TLS1.2校验通过，未发MQTT CONNECT | TLS传输证据PASS；ESP实物CA/SNI/AT兼容性NOT_RUN |
| 证书 | 有效期2026-10-13 05:00:00 UTC至2027-01-11 04:59:59 UTC；DER SHA `a3c4d1284c8f59ccb434b8736f4a1862d1ff3b42e589a26f0108c2a2d854bacd` | 本次时间内有效，不承诺未来不变 |
| B5发布/接收身份 | `b5-gateway`、`b5-observer`均不存在；B5 ACL条目0 | **BLOCKED：需要G1单独创建**；正式账户未扩权 |
| Client ID | 编译固定`b5-c-isolated`；最近120行日志未见，不足以证明全局无占用；无Broker强制Client ID归属的证明 | G1另核占用；不拿正式ID试连 |
| 正式Backend | 正在运行，实际白名单不含GW-B5-001；18765监听、已有访问令牌 | 不可用作B5直接入口，不改其白名单/Hub |
| Backend代码 | main/hub/models/mqtt_adapter四份实际文件SHA均异于已审B5；LF归一后仍异。实际Hub缺少B5新增的gateway/current_generation隔离 | 不能只加白名单宣告兼容；专属实例使用冻结B5树 |
| WSS/Web | 线上没有已部署B5测试实例、测试URL/令牌未分配；Web固定base与Socket路径为`/medical-monitor/` | 入口**NOT_DEPLOYED**，没有构造一个“真实URL”冒充已可用 |
| 端口/重载 | loopback候选18775无监听；18785已占用不使用。Broker unit没有ExecReload；实际包装器代码转发SIGHUP | 后续仅按批准的MainPID/HUP路径，不直接套systemctl reload或restart |

测试发布最小权限拟为`write mpm/v1/GW-B5-001/#`、无读取和跨Gateway授权；测试观察者只读该namespace。固定C身份、独立凭据和强制MOCK必须同时成立；ACL不检查JSON质量标志。当前这些规则**只是冻结提案，未应用**。真实Broker、Backend/Web和AI的接受证据均NOT_RUN，TLS成功不替代云数据验收。

配置快照指纹见[cloud-differences.json](../evidence/B5-G0/cloud-differences.json)，其中：

| 脱敏引用 | SHA256 |
|---|---|
| Broker实际配置 | `738d54973d959acf1207746c761d42afa2b412daad1b59ac052f781aa5af078c` |
| Broker ACL | `c987e3ebe5c884f214f2d334c6416804c24480de735c52b896874e6af3b09853` |
| Backend env | `33d94a0e773efc11aa7fad055efe150ef74b8efde5467392804f4c076f4f52d5` |
| Backend MQTT配置 | `9ac3a7ed84adb483d8c19e23e26eb8f422869ab3dcd94ec26a3e7ff728ddbff7` |

原始地址/用户名细节/令牌/env/配置只在NTFS EFS和去继承的用户/SYSTEM ACL目录。password_file仅读取账号集合、文件元数据/SHA，不封存散列正文；没有读取TLS私钥。G1若要改账号，须先另批完整受限恢复备份，G0元数据不能代替它。

## 两种隔离方式

1. **优先A：云端独立Backend Unix socket＋独立TLS反代loopback18775＋SSH转发观察。** 使用原已验收Web固定base与WSS路径，独立浏览器profile的名称解析规则与受信证书/SNI匹配，不关闭证书校验、不改全局hosts。Backend只允许GW-B5-001，专用令牌、日志/数据/进程与服务生命周期，不接正式AI。正式Broker仅增加获批角色，正式Backend/nginx/网络规则不改。实际云端WSS经SSH隧道观察，公开直达能力不在此方案结论中。18775需执行前再查，配置、证书读取权限、精确Origin/URL与服务SHA尚须G1附件冻结。
2. **备选B：同一独立Backend＋既有443的新测试SNI虚拟站点。** 需要专用测试域名和匹配的有效证书及DNS来源，再审新的server块与一次nginx reload。站内仍用原`/medical-monitor/`，不改冻结UI代码、不抢占正式域名同路径。无需新增公开端口，能取得公网浏览器直达WSS证据，但域名/证书目前未落实，共享nginx变更风险更高。未批准前不得改正式站点或把缺少证书的测试域名写成可用入口。

二者均技术可行，**当前均未部署**。不采用新增8445/8884公开端口，不自动改正式Backend白名单。生命周期为G1单独批准后创建→G3有界观察→另批R-CLOUD停止/撤销；原始证据不删除。

## 固件/恢复资产

| 资产 | 核验结果与用途 |
|---|---|
| B39948B | BIN前缀SHA `676eb7a46ad9cd15c7bf93db51a1931d7711d37c6f2fd636197dc4a85b339b82`，冻结全片 `a1abed50a4c4dbab142a2319d61c047bc43b6816dd62754a080e3f7e12415091`；未访问B |
| C24104B | 冻结全片 `b460d917e1d454fdb0882d1f837d91c606363179b817a3896a1df6897b2dcb98`，BIN前缀SHA `127ba765b8144e8f8ae98ef826ac2a98f45f8facb4021ce1888c004e5ca46547` |
| 身份/options | 历史C安装前后身份相同，B/C UID不同；历史两份独立C options与最后读回相同；B/C冻结options均16B，SHA `52d5979da03bd7be45e385920ec7d5901793bab3f6bc1daa0c1c1997f9e91687` |
| 唯一B5候选 | 42552B BIN `d5b9624b3da1129b4e045d3b2f669c00d2d93cb7379b15293ff143fe9f130683`，ELF `3c726f61f76eadac4909826203ca84dee65521aec448ad477ddca0c3c58795d8`；未重构/重建/部署 |
| 应用边界 | sector0/1/2，49152B；42552B后6600B保留本次before原字节，sector3及以后不改；不能沿用旧C仅sector0/1卡 |
| C sector3 | 完整16384B SHA `1698c8783b4fbdd1bc7fc5a8641babc7b499b58a65be54e7b36c65c6c5b88313`；336B头/committed/CRC有效，`B5_identity_matches=false`，拒绝直接用旧配置联网 |
| sector7/11 | 各131072B；B/C两区冻结SHA均`b5a41c3758763bbec72769fab4a2533bf2db0b6312d93d25a695f9e4b9e02260`；策略保护区逐字节保留不等同于宣称硬件WRP已锁定 |
| 新离线布局 | 从**C24104历史检查点**重算manifest `3782fc9caa0f921cc51001191df0ac90e2633710e89f56bae017d2e3d35e73fc`，预期全片 `3eaf583a703137b09665da5d2bfd7e860cd3a2208bf659b631d7ee4d0541545c`；只计算，不是今天备份/许可 |
| 旧H3布局 | 原manifest `ba21721a…`完整保留，仅历史布局；不再作为默认安装/回退包。默认恢复本次新鲜C24104＋原sector3 |
| 冻结归档 | 320份不可变B5文件逐一核验SHA及EFS通过，未覆盖历史失败/原码/备份 |

完整B/C保护区指纹与身份布尔见[资产回执](../evidence/B5-G0/assets-readonly.json)、[一致性回执](../evidence/B5-G0/identity-consistency.json)。C检查点文件mtime及其安装原回执SHA见[来源回执](../evidence/B5-G0/checkpoint-provenance.json)；mtime是档案时间，不冒充采集时间。**今天B/C实时身份/Flash/options/BOOT/运行状态全部FRESH_READBACK_REQUIRED。** 不能用冻结SHA一致给今天的设备签PASS。

仅重跑G0要求的恢复包校验19项及权限拒绝11项，真实退出均0；包含禁用授权、旧scope拒绝sector2、新scope仍拒绝sector3、options/整片擦除/PC写/越界读/未核验reset及错误退出续跑拒绝。测试使用内存NOR/SDK替身，无真实DLL加载。恢复包能重算、回退字节一致不等于新42552B实板恢复演练已做。

准备过程中保留两次前置失败：SSH命令的Python引号错误退出1；本地EFS目录首次ACL设置参数错误退出1且未执行SSH/写敏感原件。修正后实际只读核验退出0；后续文档patch上下文检查失败1、两次GBK/UTF8审阅解码失败1也留存，修正为显式UTF8后通过。这些是工具准备/审阅失败，不是实板ROM或云服务故障。

收尾只读复查确认Broker配置/ACL、Backend env/连接配置SHA及四个正式服务MainPID均与开工快照一致，见[末态回执](../evidence/B5-G0/cloud-end-readonly.json)；这不等于已做未授权的云端回滚或实板恢复。

## 门禁、卡与停止点

[分开的精确授权卡](B5-G0-SPLIT-AUTHORIZATIONS.md)当前全部禁用。G2-RO新scope读回器和G2-B专用配置写入器仍须冻结/离线验收，不能借旧工具扩权。本轮没有查询ESP/J-Link/COM，ESP供电/版本/CA/USART3、C P4/A段现状只列现场缺口；不反复索要已有型号、SHA或资料包。

G0准入阻塞：测试身份/ACL不存在；独立Backend/WSS入口未部署且线上Hub非已审B5；新鲜实板双读/工具绑定缺失；sector3专用记录/写入器及恢复演练未批准；ESP实际安全状态未核。G0审查完成不消除这些阻塞。

CPU ROM根因UNRESOLVED、B4独立冷启动NOT_VALIDATED、同窗ECG/RESP双有效NOT_VALIDATED、绝对阻抗幅度未标定、受控CAN故障恢复NOT_RUN均保留。没有改变BIO_V2阈值、ADC寄存器、B/C部署、云配置或保护分支，没有启动Security Gate。推送本独立分支并取回校验后停止，等待PI分别批准下一步。
