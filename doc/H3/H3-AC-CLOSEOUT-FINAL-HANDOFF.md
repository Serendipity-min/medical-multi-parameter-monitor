# MPM-H3-003-AC-CLOSEOUT 唯一阶段交接

执行日期：2026-10-21；执行者：**Codex**。负责人明确改派Codex接管，覆盖合同中DeepSeek主执行的角色标签。本文件是本轮唯一权威总结，R2及更早报告和失败原件全部保留。

**AC-0只读基线通过并保留残余风险；AC-1成对软件验证通过。整体仍为H3_AC_CLOSEOUT_PARTIAL。** 没有执行AC-2/AC-3真机采集、云端临时服务、正式发布或真实回滚。正式门保持`BLOCKED_SECURITY_REVIEW`，不能将本轮软件通过写成正式交付。

## 1. 执行人、worktree与Git身份

远端开始时重新查询，H3准确为`9a2c1db22e5c9ce11aa5cd3b65429185be98fb5c`，与合同一致；没有发现起点漂移。上一轮Codex就是本对话，已正常提交并停止。未发现引用旧H3目录的在执行命令行，但这不是对所有编辑器/其他会话的绝对证明；当前用户明确改派、独立worktree和外部单写入者登记共同限定本轮写入范围，没有声称获得不可用的跨对话工具回执。

- 新工作区：`E:/medical-monitor-h3-ac-closeout`，本地分支`codex/h3-ac-closeout`。
- 只正常推送既有远端`dev/h3-nodea-cloud-ai-integration`；不另推新远端分支，不强推、不建PR。
- 旧工作区`E:/medical-monitor-h3`仍停留`9a2c1db…`，未跟踪根`build/`保留；未切换其分支、移动原件或在其中运行构建。
- 新Web使用指向旧`node_modules`的本机junction复用既有安装，没有自动安装技能、升级依赖或改前端框架。构建/截图/临时证书只在新工作区/本轮受限目录。
- 本轮未打开COM15、未调用J-Link、未复位/上电/烧录设备。负责人提供的现状为C连接COM15，A未连接且未供电；BOOT实物状态本轮NOT_OBSERVED。

| 保护分支 | 开始时远端HEAD |
|---|---|
| A | `3fa14b00a0823d2855e9dd8bd1c6c8545abb8dc5` |
| B | `f8c99433561b2e110c04ba9fb33c30235910a3e9` |
| P6 | `77dd14d1ca761a488956f7a4ebf28cb3174835e4` |
| P4 | `67f5f57bd82c6e326e9e78ec9540481c80105e5f` |
| main | `50699048010c57ba10f8573461844c525b022a07` |

关键代码提交：

1. `8afb1e2903f18c3a562769b9e9352db7e1db438a`：Backend启动会话隔离、A/C边界/WSS负例、只读/验证入口、证据目录隔离；14项完整回归任务使用此提交。
2. `030d13d765991da8f41d6ad2f4769e3c581a80fc`：C断言宏文件名显式前缀映射，精确复现两个历史BIN。
3. `093f2d9a84874c6031d5d350a552f58452675c02`：补充HTTPS/TLS只读证据；初始成对manifest冻结于此。
4. **`926136bcd25118cb12a2f8b79fc91bc0165b2adc`**：本轮最终软件提交，仅补充实际进程二进制/完整部署源码与静态树的只读指纹。与初始成对manifest的所有固件和Backend/AI/Web文件SHA一致，源码连续性另有回执；与14项回归提交的运行时代码无新增差异。

包含本文的最终交付HEAD不预写：提交后用`git rev-parse HEAD`及远端回执取得并向负责人报告。`closeout-status.json`中的`h3_source_sha`是最终软件提交，配对manifest记录其初始冻结提交，连续性回执证明所验固件/应用字节没有变化；均不冒充包含自身的新文档提交。GitHub只读查询同时确认仓库仍为PRIVATE。

## 2. Gate与授权状态

| 阶段 | 裁定 | 实际边界 |
|---|---|---|
| AC-0 | AC0_READONLY_BASELINE_PASS_WITH_EXPLICIT_RISKS | 远端/单写入者/正式身份/历史备份可追踪；INPUT及云安全组风险保留 |
| AC-1 | AC1_PAIRED_SOFTWARE_PASS | A Host/Keil、C Host/双ARM、P5 42/46、255项及4子测试、Web/20项浏览器通过 |
| AC-2 | NOT_AUTHORIZED / NIBP_PHYSICAL_BLOCKED_SOURCE_MISSING | 没有新A烧录、合格新输入或真实完成事件证据 |
| AC-3 | NOT_AUTHORIZED / NOT_RUN | 没有本轮云临时服务、现场故障注入或新有源300秒 |
| AC-4 | PARTIAL_STATIC_REVIEW_ONLY | 本机七页/前缀已回归；没有全新正式不可变包/全套恢复备份/正式ACL证明 |
| AC-5 | BLOCKED_SECURITY_REVIEW / NOT_AUTHORIZED | 不执行正式prepare/activate/rollback |
| Node-B | OFFLINE_REQUIRED | 不修改B代码/分支，不接入实物B；H3夹具及页面检查B离线 |

未运行Security Gate、扫描器或sanitizer。P5入口明确记录`security_gate=NOT_AUTHORIZED/NOT_RUN`。

## 3. AC-0正式云只读核验与INPUT风险

原始回执位于`gateway/physical_can/evidence/h3-ac/`：`AC0-identity.json`、`AC0-cloud-readonly.json`、`AC0-risk-register.json`、`AC0-firewall-diff-review.md`、`AC0-runtime-readonly.json`及两份访问只读回执。SSH仅使用本机别名，在内存执行只读查询，没有写服务器脚本、配置、规则、临时目录或候选服务。

| 对象 | 本轮实际身份/结果 |
|---|---|
| 正式Backend | PID845095，`/opt/medical-monitor/releases/mqtt-v07-phase2-20260920-01/backend`，python3.12 |
| 正式MQTT单元 | PID851111包装器；实际mosquitto子进程PID851112、`/usr/sbin/mosquitto`，SHA `22cb8f9dbfda6032e26d230295c89d1a65bd8c675de89f6c29095715a83e25eb`；8883仍监听 |
| 正式AI | PID394625，`/opt/medical-monitor-p6`，python3.12；健康DOUBAO/MONITOR |
| Nginx | PID3631，`/usr/sbin/nginx`；原配置和Web index SHA与旧正式计划一致 |
| 原Backend健康 | status=ok、mqtt_connected=true；是既有进程的只读健康，不是新候选已订阅的证明 |
| HTTPS与8883 TLS | TLSv1.3及主机名/证书校验通过；叶证书SHA `a3c4d1284c8f59ccb434b8736f4a1862d1ff3b42e589a26f0108c2a2d854bacd` |
| 旧静态入口匿名HEAD | 200；未传令牌、未读测量内容，不能据此推断API/WSS或个人数据公开 |
| 新旧版本 | 旧AI源码AST仍有`range(1,6)`，正式片段无新AI前缀；没有切换为本轮H3 |
| 旧临时端口 | 8884/18775无监听；不能将当前C的8884配置当作正式8883联网 |

真实旧站URL从服务器已有`MONITOR_ALLOWED_ORIGINS`仅在内存使用；公开记录只保留受限引用，不落真实主机或令牌。实际部署目录不是Git worktree，版本以文件摘要/PID/路径核验，不给它伪造源码SHA。逐文件版本见`deployed_source_sha256`。正式publisher/subscriber ACL未独立证明，浏览器/WSS实际受众未作带令牌公网访问验证。

收尾同时冻结四个实际服务的unit与可执行文件SHA；已部署Backend应用7文件、AI应用6文件、Web dist36文件逐一散列。树SHA分别为`5eb24192d4d84b907ff5c31c5b5d5dd278ab36759556570dce6f9236d04f0d27`、`57c36360d9ad52f3f089089ac84115a3337bb6c9324a7ff0e4af37216799134b`、`c0780cbf36ddfe898dc4ea608f31abc7df7a4b9d05d7d500175e0a016de5e3d0`。这是只读版本快照，**不是已制作完整可恢复备份包**，AC-4/AC-5仍需补齐受限原件恢复包。

合同所称“INPUT总散列”历史实际来自`iptables -S`整个filter表，不仅是INPUT链。历史前/后SHA分别为`3c5a486467a9ea2ed4c7afeb3c8b45f1e9747cec67201f9b340a71d476f794b5`、`1fe2081c0f0cc04d56c8064144a11463bb03568c8c2b28524f755bacfeddbfd0`；本轮为**`05f3c5952feb6301c951704f9d93e7788531c28696a5d407c8bea4e9a629a983`**，395行。NAT当前SHA `96ba2354a7ee95379dbc8c4bc83f5c5d13ccc95d5367d69e3af1e6dec9ed3157`。当前filter/NAT链、规则顺序及逐条散列保留；地址只留范围类别/摘要，不输出原文。自有`MPH3R2C/MPH3R2N`引用均0。

UFW active、Fail2ban inactive；查询历史UTC11:18–11:27窗口未找到Ban/Unban线索。INPUT策略为ACCEPT、FORWARD为DROP、OUTPUT为ACCEPT，这不是完整有效访问路径裁定。缺少旧逐条文本，**不能归因于UFW、Fail2ban或其他执行者，也不能确定哪些链变更**。没有整表恢复或删除未知规则。

本机无`tccli`，未获得云安全组控制平面快照；旧“TCP8884全部IPv4保留”仍是历史负责人反馈，未冒充本次API核查。该未知项、INPUT残余风险、正式ACL/受众证明缺口继续阻断生产。AC-1离线不依赖这些生产门，已继续完成。

首份访问回执TLS字段已经通过，但broker的占位`state`未更新；保留原件，修正工具后新增时间戳回执明确`TLS_ONLY_OBSERVED_NO_MQTT_SESSION`。两次均为只读，未建立新MQTT业务会话或调用模型。

## 4. A/C NIBP软件审查与本轮修复

Node-A的`app_bp.c`成功结果才更新`valid_tick`并递增非零完成代次。CAN应用只读结果，停止/测量/过期锁存不可被旧代次解除；0x2111经0x281传完成tick和SYS/DIA镜像，0x681 bit9为扩展声明、bit3为有效位。原0x181/0x381/0x481/0x681和频率、双屏、看门狗/采集流程不重写。

C要求扩展、metadata/质量/TIME/PDO新鲜且值配对，用同一节点锚点复原完成UTC；90秒从完成算，不用2秒重发时间续期。89s/90s可有效，90.001s无当前值；uint32 tick回绕、旧A、缺0x281、身份错配、过期元数据、未来/错误时钟、重启均有定向负例。A本地完成代次没有额外写进PDO或JSON；详细线上身份边界见`AC1-protocol-validity-matrix.md`，后续真机不能虚报C直接收到未传输的本地代次。

**本轮发现并修复Backend跨启动续活缺口**：原Hub只检查90秒和流序号，新A/Gateway ONLINE可能使旧会话、未满90秒的血压重新作为当前值，真实WSS也会发送。修前新增6项中3失败/3通过，原日志保留。修复后记录网关接收代次、核对节点状态与遥测会话；旧会话高seq、REPLAY不能借新ONLINE复活，当前会话的同值新完成仍可有效。两个映射按已配置网关/current固定通道有界；未测运行RSS，不能编造Python内存变化。

本轮未修改Node-A或C的运行C源码、Router、CANopenNode、coreMQTT、AT/TLS/PUBACK期限或数据TTL。新增内容为Backend最小边界修复、负例和构建/审计/证据工具。Host不能证明HKB-08真实气路或生理准确性，原双屏实物本轮NOT_OBSERVED。

## 5. 冻结镜像、配置ABI与资源

详见`AC1-paired-manifest.json`，二进制及配置正文只在本机受限候选目录独占保存并磁盘回读，不进Git。

| 角色/候选 | 字节数 | SHA256 | 实际状态 |
|---|---:|---|---|
| A完成时间候选 | 50084 | `f59b76ef865c373c6df62aa09aea958597687f6d46b17c402ceb7126ca8f60d6` | Keil/FromELF重新生成，等于R2候选；未烧录 |
| C隔离8884 | 43172 | `59229f1b34660f053538737fc0fd17c814fde5502a0dfe33603e8e08b72ca8a5` | 精确复现历史已下载镜像；本轮未读板 |
| C正式8883 | 43184 | `9df43acd34732cacb8c1a90a6a15e420b96ad9675a004d65c3a088246268f977` | 精确复现旧候选；未烧录/连接正式链路 |
| C隔离配置generation2 | 336 | `3b1a8c344dfad1d1faa82bc962811e50a467eec9adbc1cec5b2a32979c6a2c25` | 本机私密原件CRC/ABI核验；当前板状态仅历史读回证明 |
| C正式配置 | — | — | NOT_PREPARED，正式publisher凭据/ACL/新记录SHA未冻结，不能申请不完整写入 |

C应用仅sector0–2，配置0x0800C000、sector3、16KiB擦除，24B头＋312B payload、版本1、CRC32、commit最后写；运行无Flash写入口。**端口不在记录内**，修改sector3不能把8884固件变成8883。隔离来源宏保留MOCK/synthetic，即使传输用实物CAN；正式来源仍须实际输入和授权，不凭正式端口假定LIVE。

初次在新worktree构建的两个C BIN分别为43208B/43220B，SHA `7ce421ca82c588c1725e60f2baf3658f73c84c763a2cb77b4154f126b3955ffb` / `5a1b455db9163d57bf5faf4484d46c33afb5677fcf8413fa90b376bde060da33`。差异来自三份coreMQTT断言的绝对`__FILE__`路径增长，不冒充相同二进制。首轮manifest和日志保留，中间BIN未单独归档、构建路径后来由复现目标更新。新增显式`--macro-source-root`冻结历史诊断前缀后，全字节复现上表两个BIN，并在仓库外归档最终候选；完整输入/命令/对照回执在`reproducible-C/`。没有访问旧目录写入或修改第三方库。

因此配对NIBP代码不额外要求重刷现有隔离C；后续实际核验若不匹配须停并另出C计划。**A仍是旧实机，不能用A候选编译成功推定已升级。**

资源未较R2候选变化：A Code46488/RO3108/RW1560/ZI15616；隔离C text43076/data88/bss123136，正式C text43088/data88/bss123136。bss含链接器堆/栈预留，未作真机栈水位测量；336B记录占独立16KiB擦除单元。Backend新增会话映射未实测RSS。

## 6. 实际测试、时间与退出码

所有命令在新worktree执行。14任务的UTC起止时间、精确argv、提交和退出码在`regression/*-exit.json`及`validation-result.json`；原日志不归一化CRLF、不删失败。没有联网至真实模型；DOUBAO测试使用HTTP边界替身，不消耗真实额度。

| 实际命令/任务 | 退出码 | 原件/结果 |
|---|---:|---|
| `python -m cloud.deploy.h3.ac_readonly` | 0 | AC0-cloud-readonly.json，SSH0、无服务器写 |
| `python -m cloud.deploy.h3.ac_access_readonly` | 0 / 0 | 两次访问回执，TLS/健康只读 |
| `python -m cloud.deploy.h3.ac_runtime_readonly` | 0 | 实际broker子进程、四服务binary/unit及部署树完整只读指纹 |
| 修前`pytest cloud/backend/tests/test_ac_nibp.py -q` | 1 | AC1-before-fix.log/json，3失败/3通过 |
| 修后Backend定向及旧回归 | 0 | AC1-session-fix.log/json，25通过 |
| C Adapter精确边界/负例 | 0 | AC1-adapter-boundaries.log/json，13通过 |
| Node-A Host，`--phase ac1-frozen` | 0 | regression/node-a-host.log、node-a/*，编译/运行均0 |
| C `--host --irq` | 0 | regression/gateway-host |
| C `--host --irq --rx-order` | 0 | regression/gateway-rx-order |
| C `--host --irq --peer-cycle` | 0 | regression/gateway-peer-cycle，含硬故障分支 |
| P5普通 / IRQ+fresh-SNTP | 0 / 0 | regression/p5-42 / p5-46，42/46项、完整编译和运行日志 |
| `pytest cloud/backend/tests cloud/ai/tests gateway/physical_can/tests -q` | 0 | regression/paired-python.log，**255通过、4子测试通过** |
| C两种ARM：`--irq --fresh-sntp --persistent-config`，隔离另加`--isolated` | 0 / 0 | regression/C-*保留首版路径差异镜像回执 |
| 同上加显式`--macro-source-root` | 0 / 0 | reproducible-C两份完整编译回执，复现两个历史SHA |
| Keil `UV4.exe -r …uvprojx -o …log` | 0 | regression/node-a-keil-build.log，0 Error/0 Warning；已核对用户构建钩子禁用，无下载参数 |
| FromELF `--bin --output …bin …axf` | 0 | regression/node-a-fromelf-exit.json，向量/范围及候选另冻结 |
| `npm --prefix cloud/web test` / `run build` | 0 / 0 | regression/web-tests.log、web-build.log，15项Web检查、TS/Vite |
| `python cloud/web/tests/run_r2_browser.py` | 0 | browser原日志/截图，**20项**，真实等待**90.109秒** |

Node-A补充89s及跨uint32回绕检查；C边界注入固定2000ms发布槽，90.001s不是按1Hz粗略近似。新增FastAPI WSS检查使用真实应用和Hub；Controller外部I/O仍是Host桩，不能称真实传感器结果。完整模式/身份/来源矩阵见对应Markdown。

## 7. 七页、豆包与数据范围

浏览器按agent-browser技能、独立会话执行，loopback18765/18766/18767、自签名短期证书仅用于本机；旧浏览器/正式TLS未修改。七页路由、独立AI/监护鉴权、来源标签、移动无横向溢出、90秒过期、停止测量不复活、B离线、刷新清令牌通过；自有进程均退出、证书已删除。复用R2测试入口的历史标题，不将它当正式网页。

![本轮本机MOCK过期后无当前血压](../../gateway/physical_can/evidence/h3-ac/browser/ai-desktop-expired.png)

![本轮本机MOCK移动页](../../gateway/physical_can/evidence/h3-ac/browser/ai-mobile-valid.png)

本轮真实豆包调用**0、Token新增0**；未查询费用账户，历史10次/7496 Token账本只追溯。本地MOCK回答没有REAL_REQUEST_USED证据；新服务代码保留确定性读数NOT_CALLED、真实解释REAL_REQUEST_USED区分、持久账本/限流/并发/错误熔断和禁止自动无限重试。providers仅发送问题和标量有效性/来源元数据，不发送原始波形、患者身份或完整聊天历史。设备音频下发/扬声器仍未验收，页面显示PAUSED/未验证，不宣称播报成功。

R3的README/summary/timeline/RAW_SOURCE摘要仅在保护A分支读取，H3并无该实测目录；本轮用`git show`只读目录和散列，不复制历史真人数值/日志。没有新真人或非人体传感器采集，没有真实PPG/PUBACK/FOVR等新板端计数；全部标NOT_OBSERVED，不能继承路由器654条无探头窗口为本轮有源通过。

## 8. 私密原件与后续准确授权清单

初次只搜索两个私密根目录未找到A备份，原不完整目录回执保留；扩大到已知历史交接`h2-private`后找到两组（包含旧失败原件），至少一组双份1048576B一致并符合原始SHA `0fd4a4e8417b87a157fdf3e4f7c5a2a553c5aa9f69b4417fcac03c3a73d91516`。详见`AC0-A-backup-recheck.json`。没有读取UID正文或重新接板。

C路由器更新前generation1的64KiB双备份仍存在且符合`52a4c9d621375d63cd995c1a003d98473e9be3387d31cd857e702a27bee7e6f8`；它不是当前generation2快照。generation2历史写后完整读回SHA `102575dc940425d91b2db7c2a0f22ddf44c5cfab652b1b5ca0790f8924d3705b`只是旧窗口证明。本轮没有新增Flash双读或保护区实测，未来动写仍要新窗口实际双读/磁盘复核、保护7/11/options。

**可审阅的后续计划已在`AC2-authorization-plans.md`列全范围，不是另签合同：**

1. AUTH-AC-A-FLASH：A50084B候选、精确SHA、仅A sector0–3（应用0x08000000–0x0800C3A3），历史旧应用身份/备份与当前实际读回区别、维护/双屏/看门狗、失败只恢复本窗口原件和正常冷启动次序。未执行，不能复用旧下载器的49888B固定镜像门禁给新镜像放行。
2. 隔离C配对字节不变，本身无须重刷；正式C的AUTH-AC-C-FLASH尚NOT_READY，因为正式publisher配置SHA/权限未冻结。8884/8883应用不同，配置扇区单独授权。
3. AUTH-AC-SOURCE / HUMAN：缺合格新NIBP和血氧来源资料，保持NIBP_PHYSICAL_BLOCKED_SOURCE_MISSING。没有要求人体佩戴或无限重复袖带。
4. AUTH-AC-CLOUD-ISOLATION：新的不可变runtime必须含本轮Backend修复；需当次服务/端口/用户/client_id、现场/32、TTL/清理/故障粒度。没有写服务器staging或启动临时云服务。
5. AUTH-AC-PROD：先有正式ACL、来源/受众、INPUT/安全组风险裁定及完整恢复包，再冻结候选/配置/URL/窗口。当前新正式网址**未发布**；路径`/medical-monitor/#/ai`仅候选入口。实际正式回滚及回滚后公网复验均NOT_RUN。

本轮没有重构CANopen/coreMQTT、没有改P4/main/A/B/P6、没有操作Node-B、没有PR或强推。授权边界来自新合同第3节及AC-2至AC-5入口，既有现场/云窗口均已结束，不能作为本轮操作许可。软件范围已完成；后续依赖上述门，停在阶段复核，不将缺口改写为PASS。
