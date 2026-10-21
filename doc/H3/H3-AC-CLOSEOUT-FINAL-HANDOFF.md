# H3 A→C 唯一权威交接（MPM-H3-004 R1.0）

**2026-10-21 最终裁定：`H3_AC_FINAL_PASS`（负责人确认的非人体MOCK工程链路范围，保留已接受风险）。新A→正式C8883→新版Backend→正式七页/豆包实际闭环；最终新鲜PPG连续359.701秒、NIBP完成/90秒及AI事实核对通过；原路由真实回滚、旧HTTPS/WSS复验与同一候选再次激活均已执行。全部烧录/规则/源中断/观测工具失败保留，未伪造生理准确度。A/C当前J5独立运行，USB/J-Link拔下、BOOT0/1=GND、CAN保持连接，采集可停止。最终矩阵见 `gateway/physical_can/evidence/h3-ac-final/closeout-status.json`；当前权威结果和访问方式见第16–17节。

下列第1–8节保留MPM-H3-003原轮事实及失败历史；其中“本轮”指该历史窗口。MPM-H3-004的新增事实从第9节开始。

执行日期：2026-10-21；执行者：**Codex**。负责人明确改派Codex接管，覆盖合同中DeepSeek主执行的角色标签。本文件是本轮唯一权威总结，R2及更早报告和失败原件全部保留。

**历史MPM-H3-003结论（已由第16节更新）：AC-0只读基线通过并保留残余风险；AC-1成对软件验证通过，当时整体为H3_AC_CLOSEOUT_PARTIAL。** 没有执行AC-2/AC-3真机采集、云端临时服务、正式发布或真实回滚。正式门保持`BLOCKED_SECURITY_REVIEW`，不能将本轮软件通过写成正式交付。

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

## 9. MPM-H3-004 R1.0：F0–F6新增执行记录（2026-10-21）

### 9.1 F0：接管、现状与源条件

本轮完整阅读 `MPM-H3-004-AC-FINAL-DELIVERY-CODEX.md`。重新查询H3远端与本地，起点均为 `5a4cfd25753b5fe8f812d3acc6494aa898e1adb1`，工作区干净。上一轮外部租约明确关闭；按负责人“唯一工程执行者”指令归档旧租约并登记新租约。进程列表有其他Codex进程，不能由进程名称断言其编辑器状态；未发现未知工作区改动，旧H3工作区及原件未动。不使用不可用的跨对话交接工具伪造交接回执。

负责人本轮回报：A/C接J5，C同时接USB/COM15，A的J-Link未连接，BOOT均接GND；并说明“A与C均未开启”。这作为现场回报原文保留，不据USB枚举推断MCU的实际供电状态。未要求改接线、开关电源或移动跳帽。CAN既有三线、500kbps及双终端约60Ω为继承静态基线，本轮没有重新测量；板间不得互接电源，Node-B仍未接入、必须OFFLINE。

负责人确认模拟设备“能模拟血压并进行测量”，但型号/说明和非人体信号来源仍“不确定”。因此当前是 `OWNER_REPORTED_MEASUREMENT_CAPABLE / SOURCE_IDENTITY_UNCONFIRMED`，尚不构成合格HKB-08B+成功完成事件/PPG源证明，也不构成AUTH-AC-SOURCE或HUMAN。未要求人体佩戴或进行新测量，F2保持具名来源缺口。

`F0-input-continuity.json`重新逐文件计算AC1的固件及关键Backend/AI/Web输入摘要，差异均为0；这是身份连续性检查，未重跑或认领AC1的255项/Keil/ARM/浏览器成绩。新A镜像离线计划再次核对50084B及向量/扇区，未连接设备。历史A完整备份及C generation1原件仍不当作当次当前Flash。

### 9.2 F0/F3：实际服务器只读结果与风险差异

实际SSH只使用本机别名，在服务器内存执行只读查询；新证据位于 `gateway/physical_can/evidence/h3-ac-final/F0-*.json`、`cloud/evidence/h3-ac-final/F3-access-*.json`。无临时目录、staging、服务、规则、凭据或云安全组写入，真实AI调用0。

- 正式Backend/AI/Broker包装器/Nginx的PID分别仍为845095/394625/851111/3631，Broker实际子进程及完整源码/静态树指纹另在F0-runtime记录。8883监听，8884/18775无监听。旧AI的五槽限制仍在旧部署，不能说新账本已上线。
- 当前**整张filter表**为393行，SHA256 `e6f238e23dece4fe2763aae2c48a482f749a56f632aeac6d31aa1130d7abed1c`；与AC0的395行比较，有2条旧规则散列消失、无新增，脱敏顺序元数据保留于 `F0-filter-delta.json`。没有旧原文，不能将差异归因UFW/Fail2ban或某位执行者；未恢复整表。
- NAT为12行，SHA256 `96ba2354a7ee95379dbc8c4bc83f5c5d13ccc95d5367d69e3af1e6dec9ed3157`；filter/NAT自有H3引用均为0。不能因此宣称全部防火墙恢复。
- `nginx -T`退出0，真实引用只以别名/散列公开。最初更详细的只读原件移至私有目录留存，原摘要回执保留；新脱敏回执不含其他虚拟站点文件名。
- 只读定位了实际业务Broker配置及ACL：2个write角色、1个read角色，Topic散列和通配符性质已记录。这是现有配置观察，尚未绑定/验证本次独立正式publisher/subscriber权限，未建立新的业务MQTT连接。
- 正式Backend/AI沿用的用户及NoNewPrivileges/ProtectSystem已记录；云安全组控制平面8884未取得实测，生产受众尚未确认。残余风险仍须负责人裁定，`BLOCKED_SECURITY_REVIEW`不解除。

### 9.3 F1：新A工具与失败恢复的软件准备

新增 `gateway/physical_can/bench/final_a.py`，专用于本合同50084B候选，SHA256 `f59b76ef865c373c6df62aa09aea958597687f6d46b17c402ceb7126ca8f60d6`。默认plan仅离线；program必须有绑定工具SHA、执行HEAD、有效期、A单板现场条件及候选SHA的负责人专项卡。旧49888B下载器不复用。

程序在写前确认A身份、1024KiB、RDP0、选项字节；两次完整1MiB读取并磁盘复核；核对当前旧应用身份，未知即停止。只load/verify新A应用，检查64KiB以外、UID/容量/选项字节均不变。只临时冻结调试暂停期间IWDG，成功后恢复原调试寄存器；不长期关看门狗，不发送mass erase、PC/MSP/VTOR或go。原始UID/Flash/J-Link输出只进入私有新窗口目录。

restore是单独批准入口：只能取该窗口新双份原件前64KiB；先核验保护区和选项，再恢复A sector0–3并全片读回。损坏/身份变化即停，不自动用旧整片备份覆盖。当前只验证了合成存储模型；新A写入、屏幕/看门狗正常冷启动及真实Boot-up/Heartbeat均NOT_RUN。

### 9.4 F3：新不可变包、完整原件和受控发布准备

运行包源码冻结提交为 **`5da742f4e0e078d2d40453facdad1e65ff51fdda`**，包含 `8afb1e2` Backend会话隔离修复及 `f0a63e0c6d1af9e6f5fba375b70a46f0e0cbfe7e` 新维护/恢复工具。独立上传工具提交为 `8b4cb86b146f845495b3ebb8070208f9294cc2f9`；它不改变已冻结运行包内容。包含本次文档/证据的交付HEAD以提交后远端回执为准，不预写自身SHA。

| 冻结项 | 实际身份 |
|---|---|
| 新runtime包 | 3,878,350B；SHA256 `85f0e830991e79f8702ce01ae204c8326c66203ac6a2d2b21e55e6b7c6cd9c3f` |
| 全payload映射SHA | `b8fbb14b5c356090f8a35f211b9bc1f070be251b58436db7f1445283013ac87e` |
| Web完整dist映射SHA | `d081b7036e521208a433a7410f1a86c9f06208260434b4257f10eeddd1a174be` |
| 本机私有引用 | `ac-final/runtime-5da742f`及独立repeat目录；两次包SHA/字节完全一致 |
| 候选远端目录（未创建） | `/opt/medical-monitor-h3/releases/runtime-b8fbb14b5c35` |
| 完整内容 | 70个文件：Web dist、Backend、AI、发布工具、依赖清单、20个Linux/CPython3.12 wheel及来源manifest |
| 原始中间包 | `bf2b184f…`留在私有目录，因服务禁止写pyc等修正被新包取代，从未上传 |

依赖离线下载退出0，每个wheel进入manifest散列；Linux本机现有解释器为3.13，未安装3.12，**没有声称目标服务器venv安装或服务健康已通过**。新prepare要求独立版本venv并逐个核对锁定版本，后续安装仍需AUTH-AC-CLOUD-STAGE，不能借旧共享venv冒充新运行环境。

新增完整恢复组件覆盖整个Web/Backend/AI树、持久状态、unit/env、Nginx引用、Broker配置、执行文件和release链接，保存内容、mode/uid/gid/mtime、符号链接及POSIX xattrs/ACL。创建时源变化即失败；恢复先重建校验，同文件系统逐对象交换，中途失败按反序还原并保留被换下原件。**逐对象交换不宣称跨整站的一次文件系统原子事务**；正式入口以单个Nginx片段原子替换控制。真实服务恢复/重启/HTTPS仍须正式窗口验证。

正式prepare现在拒绝旧四文件计划或只有角色标签的假完整清单，按真实进程/环境/Nginx引用核对覆盖范围。activate/rollback要求完整恢复包可验证、候选服务SUBACK健康及DOUBAO/MONITOR健康；回退不再被损坏候选包封锁。旧服务保持原位，仅切换自有路由/候选服务。候选unit禁写pyc，NoNewPrivileges/ProtectSystem约束写入到既有STATE；避免重启污染不可变源码。Broker实际ACL、完整原件路径和服务端安装尚须现场审查/授权，当前不是F3_RELEASE_READY。

`tools/h3_stage_runtime.py`只接受冻结包，默认plan；upload须AUTH-AC-CLOUD-STAGE绑定准确包SHA/工具SHA/目录/有效期。源包是本机生成且无服务器直接下载源；批准后仅经E:/Server_file中转，远端尺寸/SHA、tar边界和全部文件摘要验证通过才清理本次中转件。不安装依赖、不启动服务；本轮只执行plan和tmp仿真，没有上传。

### 9.5 本轮新增验证及真实退出码

| 验证 | 退出码 | 本轮证据和限制 |
|---|---|---|
| 新A/恢复包/发布事务定向pytest | 0 | `cloud/evidence/h3-ac-final/software-20261021T072238226948Z/tool-regression.log`：30 PASS，1个Windows下POSIX项SKIP |
| Linux本地POSIX恢复 | 0 | 同目录posix-recovery：内容、额外文件、mode/uid/gid、xattr、链接共6项检查；补足对应平台覆盖，非服务器实际回滚 |
| 新A候选离线plan | 0 | 同目录new-A-offline-plan及node-a/evidence/h3-ac-final；无J-Link调用 |
| TS/Vite完整dist构建 | 0 | 同目录web-package-build；为新包构建，不重报旧浏览器20项成绩 |
| 上传器定向pytest | 0 | `cloud/evidence/h3-ac-final/stage-tool-tests.log`：3 PASS；含拒绝未授权网络、包变更、越界tar，全部tmp仿真 |
| 冻结包两次构建/解包逐文件核验 | 0 / 0 | `runtime-package.json`；SHA一致；无上传/模型调用 |
| F0/F3 SSH只读查询、nginx配置查询 | 0 | F0-cloud/runtime、F3-access脱敏回执；非新候选健康 |

新增合计33个pytest通过，另有1项Windows跳过及Linux独立6项检查。开发中每轮验证目录、旧较早中间包均保留，不以最终结果覆盖历史。尝试查询WSL pytest时发现未安装该模块，因此用stdlib独立POSIX检查；未将该查询当作通过的Linux pytest。AC1成绩单保持原归属。所有板端/实际发布退出码为null（未执行），不填0。

本轮无固件运行时代码变化，A/C资源统计继承AC1；运行包新增本机磁盘占用见上述大小，不声称实板水位或新服务RSS已测。没有更改第三方代码、CANopen/coreMQTT/Router/AT/TLS架构、ABI或TTL；没有PR、强推或Security Gate。

### 9.6 F0-window-request：当前只申请AUTH-AC-A-FLASH

**卡号 `AUTH-AC-A-FLASH / F0-A-1`，状态REQUESTED_NOT_APPROVED。** 这是一份合同内授权卡，不是新合同。批准后一次使用；批准时间起2小时内有效，超时重核现态。执行HEAD在收到批准后登记为当时准确交付HEAD，必须包含上述冻结提交，工具/候选字节不变。

| 项目 | 本卡准确范围 |
|---|---|
| 设备/工具 | 仅Node-A、原J-Link；工具 `final_a.py` SHA256 `4dd2c60b146e278bb917e45a577693e83c79256d1da6d57830e0692c85bbb27e`，J-Link/Keil/FromELF摘要另在F0-input-continuity |
| 现场动作 | 批准后才由现场使A/C及屏/传感器断电、隔离CAN三线，C保持断电；仅A接原J-Link及已核验独立供电，探头/袖带不接，BOOT正常GND |
| 新镜像 | 50084B，SHA256 `f59b76ef865c373c6df62aa09aea958597687f6d46b17c402ceb7126ca8f60d6` |
| 写入/保护 | A应用 `[0x08000000,0x0800C3A4)`；擦除影响仅A sector0–3/64KiB，`0x08010000`之后及options不变；不操作C Flash |
| 写前门禁 | A私有历史身份比对、容量/RDP/options、当前完整1MiB两次读/磁盘回读一致，当前49888B应用前缀必须匹配历史 `506423dc…`；未知即停，原始完整备份SHA不替代当次双读 |
| 下载/核验 | 有界load/verify，完整读回新镜像和保护区/选项；不mass erase、RDP或options写，不强设入口、不go |
| 冷启动 | 通过后由现场断电拔J-Link，原J5/双屏正常BOOT独立启动，报告屏幕/重启；C仍不操作。真实CAN Boot-up/HB留到下一次获准C观测，未取得前不宣称F1整体PASS |
| 失败与恢复 | 任一步异常即停、保留原件和真实退出码，不自动恢复。若需要恢复，另明确批准绑定本窗口新备份SHA，仅恢复A sector0–3；身份/保护区改变时不得恢复 |
| 明确不含 | C串口/读写/复位、采集/人体、云写入、8883生产、隔离故障、正式发布或回滚 |

此项必须等待明确批准，依据本合同第3/5/12节。批准前不要求现场执行表内断电/改接动作。后续C只读、AUTH-AC-SOURCE、隔离云/故障和staging将以已齐备身份分别出卡；**正式C和PROD卡目前NOT_READY，不对空配置SHA/未生成完整恢复包请求批准**。

### 9.7 F2–F6当前矩阵及后续准入

| Gate | 当前裁定 | 不可替代的下一项 |
|---|---|---|
| F0 | READONLY_COMPLETE_WITH_SOURCE_SECURITY_GAPS | 新鲜现场回报已得；合格来源、SG及历史差异仍保留 |
| F1 | SOFTWARE_PREPARED / WAITING_AUTH | 新A镜像实读/写/正常冷启动、双屏/看门狗/真实CAN证据 |
| F2 | BLOCKED_SOURCE_AND_AUTH | 模拟源身份与AUTH-SOURCE；新C实读配对；新runtime隔离云、真NIBP完成/90秒、PPG300秒和故障恢复 |
| F3 | LOCAL_PACKAGE_AND_RECOVERY_SOFTWARE_PREPARED | 服务端独立venv/完整原件、SG/有效ACL/受众/风险裁定；未达RELEASE_READY |
| F4 | NOT_READY | 正式publisher/subscriber角色、正式336B配置SHA、当次C64KiB双读及保护区；不复用隔离凭据 |
| F5 | NOT_AUTHORIZED / NOT_RUN | 精确正式发布卡、HTTPS七页/AI、真实rollback及获批再激活 |
| F6 | H3_AC_FINAL_PARTIAL | 等待专项门，不能冻结A→C为FINAL_PASS或推进Node-B |

正式权限设计为独立publisher仅write GW-C状态/节点状态/telemetry/replay/event、独立Backend仅read这些Topic，避免授予控制/downlink写权；client_id按角色/窗口隔离，TLS CA/SNI验证，具体账号/ACL文件差异必须在私有窗口核验后申请。正式C仍43184B/SHA `9df43acd…`、正式336B记录NOT_PREPARED；8883端口在编译镜像，不在sector3记录。

正式网址沿用受限 `MONITOR_ALLOWED_ORIGINS` 引用，未发布新HTTPS入口；`/medical-monitor/#/ai`仍只是候选操作入口。此次没有新增正式截图、真实豆包回执或Token；不把第7节本机截图当正式成果。设备扬声器/ASR/TTS仍NOT_VERIFIED。实际rollback及再次激活均NOT_RUN，旧正式服务保持原版本。

本轮阶段性软件与证据可正常提交/FF推送H3；受保护ref须在推送前后逐项核对。最终交付提交SHA和远端一致性由提交后的真实Git回执提供，报告中的软件/运行包SHA为以上真实冻结提交，不预造文档自身散列。

## 10. AUTH-AC-A-FLASH / F0-A-1 实际执行与下一准入卡

### 10.1 已批准窗口及实际下载

负责人明确回复“批准 AUTH-AC-A-FLASH / F0-A-1”，绑定交付 `d87295723160cd884033104ae683ac8713301fb2`。本次登记采用保守截止 `2026-10-21 17:29:03 +08:00`（UTC09:29:03）；没有借新代码提交延长窗口。现场随后回复“A单板已就绪，C断电，CAN三线分离”。工具/镜像/J-Link摘要与批准卡一致后才连接A；C/COM15没有打开。

实际执行区间：UTC `2026-10-21T07:31:38.715625+00:00` 至 `07:33:04.452238+00:00`，即北京时间15:31:38–15:33:04。`python -m gateway.physical_can.bench.final_a program` 实际退出码 **0**。完整命令、输出、UID/原件只在私有 `ac-final/A-F1-*` 窗口，目录移除继承授权，仅当前操作者、SYSTEM及Administrators可访问；Git仅留脱敏散列。

| 实际核验 | 结果 |
|---|---|
| 芯片/身份 | STM32F407、1024KiB、A历史私有身份一致、RDP0；无UID原值入Git |
| 当前原件双读 | 2×1,048,576B，磁盘回读一致；SHA256 `4c2730ebc9a8eab33b1e4d585db7deb47567261b6369165e47ecaf9630f35f3a` |
| 写前49888B应用 | SHA256 `506423dc295318a8de730d0d6b5100fc4ef199c349ee3acd2fbba350bf576f88`，符合批准的旧应用身份 |
| 新应用实际读回 | 50084B，SHA256 `f59b76ef865c373c6df62aa09aea958597687f6d46b17c402ceb7126ca8f60d6` |
| 实际边界 | 仅A sector0–3；应用 `[0x08000000,0x0800C3A4)`；64KiB外逐字节不变 |
| 64KiB外散列 | `8e6f77366baf8f9b9cddc873765484b539c202d890ef8291302eae35e63b37ce`，前后一致 |
| options | SHA256 `52d5979da03bd7be45e385920ec7d5901793bab3f6bc1daa0c1c1997f9e91687`，前后字节不变 |
| 写后完整1MiB | SHA256 `7c0f68fbd779c61fd7184d687a858d41d154361862af3b1c2a93b32ef67e49a6` |
| 命令审计 | 7个J-Link会话；21条savebin、1条loadbin、1条verifybin、2条调试暂停IWDG寄存器写；无erase/go/强设入口 |
| 恢复 | 未需要、未执行；旧历史整片备份未用于覆盖 |

工具完成后再次独立从私有文件核对双备份、实际镜像、应用外及身份/options，全部一致。证据：`node-a/evidence/h3-ac-final/F1-A-flash-20261021T073138715625Z.json`，含全部8份私有输出日志摘要（7个J-Link会话加CLI日志）。这是当次当前原件，不能与历史原始1MiB `0fd4a4e8…`互换。

### 10.2 正常独立冷启动与未观测部分

按已批准卡，请现场断A/双屏电源、拔J-Link、等约10秒后由原J5独立供电，BOOT正常GND、不按RESET、不接探头/袖带；C继续断电且CAN分离。对“两屏自行显示、时钟持续更新、约一分钟无反复重启/异常”的组合核对，负责人回复 **“正常”**。

记录为 **OWNER_REPORTED_NORMAL_COLD_BOOT_SMOKE**；这是实际现场反馈，没有精确切电时间或仪器级看门狗超时故障注入，手工观察退出码为null，不伪填0。没有连接J-Link强设PC/MSP/VTOR。证据：`F1-A-cold-boot-owner.json`；真实CAN Boot-up/Heartbeat/PDO和新NIBP完成事件仍 **NOT_OBSERVED**，不能据此把整个F1/F2标PASS。

本次A单板下载窗口已完成并标记CONSUMED，不再重复烧录；无真实采集、C操作、云写入或实际回滚。运行包、Backend/AI/Web、A/C固件源码和资源统计均未新增变化；新A现在已在实板，配对C仍须当次只读证明。

### 10.3 已备好的C只读工具和软件证据

新增 `tools/h3_c_readonly.py`，源码提交 `64bfd1274be9b3711e161812b8a34fc05ebb8ed7`，工具SHA256 `b0bada02b2e044d7c97f8879857b5f8535afc7abe6089f0f61279c0bc8a1cd70`。默认plan，无串口动作；read须下一张专项卡绑定工具/支持库/身份源摘要、实际执行HEAD、有效期及现场状态。

仅调用ROM识别/读取命令，核验当前43172B隔离镜像、generation2/336B配置、两次64KiB原件及sector7/11/options。原件先独占保存以保留失败证据；任何不一致即停止，无自动重刷、RAM注入、erase/write/go或自动RESET入口。只读计划见 `gateway/physical_can/evidence/h3-ac-final/F2-C-readonly-plan.json`。

3项本机合成内存检查退出 **0**（正常配对、双读不同保留原件并停止、总合同不能绕过读板专项门）；FakeBoot没有写入API。完整新日志及回执为 `cloud/evidence/h3-ac-final/C-readonly-tool-tests.*`。没有运行C实板检查，不能把这3项算为物理结果；既有33项不改归属。

### 10.4 下一张卡：AUTH-AC-C-READONLY / F2-C-1

**REQUESTED_NOT_APPROVED；单次窗口，批准后2小时有效。** 仅为了得到当前C配对原件，不是正式C烧录授权；不得据此进入8883或生产。当前A无需再刷、J-Link保持拔下，批准前现场不必移动任何接线。

| 对象 | 请求的准确范围 |
|---|---|
| 现场操作 | 批准后A/双屏保持断电、J-Link拔下、CAN三线仍分离；C先断电，BOOT0改3.3V、BOOT1保持GND，仅C通过USB/COM15进入手动ROM；无人体/探头/袖带 |
| 连接/读区 | 115200/Even，核验已冻结C身份/1024KiB/RDP0；`[0x08000000,0x08010000)`两次64KiB并私有磁盘复核；只读sector7 `[0x08060000,0x08080000)`、sector11 `[0x080E0000,0x08100000)`、16B options及ROM识别所需UID/容量映射 |
| 必须匹配的旧应用 | 43172B，SHA256 `59229f1b34660f053538737fc0fd17c814fde5502a0dfe33603e8e08b72ca8a5`，编译期8884 |
| 配置/完整原件 | generation2/336B SHA256 `3b1a8c344dfad1d1faa82bc962811e50a467eec9adbc1cec5b2a32979c6a2c25`；历史写后64KiB期望 `102575dc940425d91b2db7c2a0f22ddf44c5cfab652b1b5ca0790f8924d3705b`，此次实读前不称当前已确认 |
| 保护区期望 | sector7/11各 `b5a41c3758763bbec72769fab4a2533bf2db0b6312d93d25a695f9e4b9e02260`；options `52d5979da03bd7be45e385920ec7d5901793bab3f6bc1daa0c1c1997f9e91687` |
| ROM握手界限 | 最多初次同步、一次现场手按RESET后同步、一次USB断电重插后同步；各留独立失败原件，不自动无限重试；仍失败即停，不改镜像/身份门禁 |
| 结束状态 | 关闭COM15；现场断C电并把BOOT0恢复GND，BOOT1保持GND，C保持断电，不自动GO；A/C仍不联板采集 |
| 明确禁止 | 任何Flash/RAM/options写、擦除、C重刷、A再次写入、恢复、Wi-Fi凭据变更、云写入或实际测量；不删除错误计数/失败原件 |

专项等待依据合同第3/6/12节：本轮A许可明确不含C，当前C实读必须另获批准。此卡不要求新合同；批准后只安排上述已有精确范围。之后再按实际身份/来源条件推进隔离云和真实CAN/NIBP，避免在无源条件下重复300秒计时凑进度。

## 11. C实际配对核验、窗口收尾及F3上传准备（2026-10-21）

### 11.1 USB只读失败与负责人追加J-Link授权

第10.4节卡后来获明确批准，执行源为 `56f92b2bb398956d042121c711805d79eeb154f9`。初次、负责人手按RESET后、负责人USB重插并确认电源开关开启后，共三次进程退出码均为 **1**；没有获得Flash备份，也没有写Flash/RAM或GO。第1次冻结工具仅保存GateError，不能补称已精确定位失败阶段；第2/3次对原工具只增加异常代码/函数名观测，均记录 `MANUAL_ROM_SYNC_NOT_CONFIRMED`，身份读取尚未到达。原工具SHA未改。三份 `F2-C-read-attempt*-failed.json` 及私有原日志全部保留，旧窗口已EXHAUSTED，没有第四次串口同步。

负责人随后明确授权“再烧录一次”，澄清“C隔离应用，保留配置”，并指示“jlink已连接C版，尝试烧录”。据此登记本地追踪号 **AUTH-AC-C-ISOLATED-JLINK / F2-C-2**，不是要求负责人重复审批，也不声称负责人原话包含该编号。新工具先做本机合成检查，冻结实际硬件执行源 `0f410541d1525045e780b59d73cf7c86441f8cf0`，工具SHA256 `e43dfa1eec635d25ec3816d27ff2169d8544e35032441c2fbbb7bdea0860db9d`，再执行一次C隔离应用load/verify。

### 11.2 J-Link实际结果：镜像原本正确，未发生物理擦写

实际执行UTC **08:02:27.106371–08:02:49.612380**（北京时间16:02:27–16:02:49），`python -m tools.h3_c_jlink program` 子进程退出码 **0**。原件、UID、配置、原始J-Link日志只在受限私有 `ac-final/C-JLINK-20261021T080212609722Z`；公开回执 `gateway/physical_can/evidence/h3-ac-final/F2-C-jlink-load-verify.json` 提供原始文件散列和准确执行提交。

| 实际对象 | 核验结果 |
|---|---|
| C身份/供电参考 | 冻结私有C身份匹配；1024KiB、RDP0；8个J-Link会话VTref均3.3V，无UID原值入Git |
| 当前应用 | 43172B，SHA256 `59229f1b34660f053538737fc0fd17c814fde5502a0dfe33603e8e08b72ca8a5`；起址0x08000000，末址不含0x0800A8A4，仍为隔离8884 |
| 当前64KiB双读/写后读回 | 三份字节相同，SHA256 `102575dc940425d91b2db7c2a0f22ddf44c5cfab652b1b5ca0790f8924d3705b` |
| sector3配置 | generation2、336B、CRC核验通过；SHA256 `3b1a8c344dfad1d1faa82bc962811e50a467eec9adbc1cec5b2a32979c6a2c25`；整个16KiB前后相同 |
| sector7 / sector11 | 两者各SHA256 `b5a41c3758763bbec72769fab4a2533bf2db0b6312d93d25a695f9e4b9e02260`，前后字节相同 |
| option bytes | SHA256 `52d5979da03bd7be45e385920ec7d5901793bab3f6bc1daa0c1c1997f9e91687`，未写且前后相同 |
| load/verify | 1条loadbin、1条verifybin，SDK明确 `SKIPPED_IDENTICAL`，随后Verify successful；**实际C擦除/编程为0次** |
| 命令范围 | 8个会话、24条savebin、2条临时调试IWDG冻结寄存器写，原值已恢复并读回；没有erase、GO或强设PC/MSP/VTOR，没有凭据RAM注入 |
| 本窗口运行结果 | 没有冷启动或联网测试，也没有新A→C CAN/NIBP实测；不把读取成功算运行通过 |

原v1 `result.json` 的 `flash_write_started=true` 表示已经提交loadbin，不代表实际物理擦写；保留该原件，通过派生回执准确解释，未为凑“重刷”强制擦除或第二次下载。随后提交 `aff4cd5e051f2267de3b8895336f2a1f72989868` 仅修正工具日志字段，将提交动作与SDK跳过区分；该版本仅软件验证，**未再次执行硬件**。

写前启动别名向量与System ROM向量一致。其只读地址依据 [ST AN2606，STM32F40xxx/41xxx系统存储器说明](https://www.st.com/resource/en/application_note/an2606-introduction-to-system-memory-boot-mode-on-stm32-mcus-stmicroelectronics.pdf)；该观测与正确Flash证据排除了本次应用内容/下载地址错误的猜测，但不能唯一定位UART连线、ROM外设选择或USB控制状态等握手原因。**串口下载恢复仍NOT_VERIFIED**。

### 11.3 现场收尾、软件退出码与剩余门禁

负责人完成窗口收尾，原话 **“C已断电，USB/J-Link已拔，BOOT0接GND”**；BOOT1仍GND，A仍断电且J-Link已拔，CAN三线分离、无人连接的既有状态保留。记录为OWNER_REPORTED，手工动作时间和退出码为null，不伪造仪器日志。见 `F2-C-owner-cleanup.json`。J-Link卡已CONSUMED，不再操作板卡；串口原三次失败不删除。

| 本次新增软件/只读检查 | 实际退出码 | 范围 |
|---|---|---|
| J-Link v1本机检查（硬件执行前） | 0 | 7项合成检查，终端观察；没有单独原始stdout文件，未补造日志 |
| 日志字段修复后定向pytest | 0 | 8 PASS；`cloud/evidence/h3-ac-final/C-jlink-tool-tests.log`与JSON，合成内存/SDK文本，非实板结果 |
| SSH目标目录/容量预检 | 0 | 新目标目录不存在；`stage-readonly-preflight*.json`，仅真实服务器只读查询 |

没有固件运行时代码变化、ARM资源变化或CANopen/coreMQTT/AT/TLS架构修改，故未重跑与本工具字段无关的整套ARM回归；继承AC1身份，未重复认领。没有安装第三方依赖/技能、执行安全扫描、创建PR或修改保护分支。新增主机脚本与本地测试只影响受限维护及其证据语义。

F1保持“新A读回/负责人冷启动正常，实际CAN待观测”；F2现已得到**当前C应用/配置配对身份**，仍缺合格非人体源身份、真实新A CAN/NIBP完成与90秒过期、有源300秒和故障恢复。负责人说模拟设备能测量，但型号/PPG非人体来源未确认，不能自行升级为合格来源。Node-B保持OFFLINE要求，没有新增实际采集或豆包调用。

F3运行包仍为第9.4节冻结字节，新增工具不在运行payload内，无需重复打包。正式C配置、角色/ACL、云安全组控制平面、受众、完整服务端恢复原件仍未准出；当前正式Backend/AI/Web未变，旧AI五槽限制尚在生产。F4/F5未执行；新正式HTTPS、七页截图、豆包Token及实际回滚均无新成绩。

### 11.4 下一张精确卡：AUTH-AC-CLOUD-STAGE / F3-S1（仅上传）

**REQUESTED_NOT_APPROVED；批准后单次2小时有效。** 本卡是同一合同的staging写入专项门，依据合同第3/7/12节；不是正式部署、服务启停或新子合同。板卡保持上述断电状态，无须接线或采集。

| 项目 | 准确范围 |
|---|---|
| 连接/执行身份 | 现有SSH别名 `tencent-codex`；收到批准后绑定当时实际交付HEAD，必须包含冻结上传器，先复核包/工具摘要与目标未占用 |
| 冻结运行包 | 源 `5da742f4e0e078d2d40453facdad1e65ff51fdda`；3,878,350B，SHA256 `85f0e830991e79f8702ce01ae204c8326c66203ac6a2d2b21e55e6b7c6cd9c3f`；含Backend会话隔离修复 `8afb1e2903f18c3a562769b9e9352db7e1db438a` |
| 上传器 | `tools/h3_stage_runtime.py`，SHA256 `5126ae060348cfed4decf3ff5ba629920e03738a05f540acc214887cb03da192`；动作 `UPLOAD_EXTRACT_VERIFY_ONLY` |
| 唯一目标 | 新建 `/opt/medical-monitor-h3/releases/runtime-b8fbb14b5c35`；70个payload文件，映射SHA256 `b8fbb14b5c356090f8a35f211b9bc1f070be251b58436db7f1445283013ac87e`；目标已存在即停，不覆盖旧目录 |
| 中转与校验 | 源包本机生成无远程下载源；经 `E:/Server_file/h3-final-<UUID>.tar.gz` → 远端 `/tmp/`同名本次文件，核对尺寸/SHA、安全tar边界及全部文件摘要，成功后仅删除本次中转文件 |
| 失败范围 | 立即停止，记录退出码；不切换任何生产版本，不删除/覆盖旧release；远端未完成候选和本机失败中转件保留为证据，报告精确路径供后续处置 |
| 明确不含 | 不装venv/依赖，不写unit/env/密钥，不启停或reload服务，不改Nginx/Broker/防火墙/安全组/DNS，不运行模型、不传采集值，不建立完整正式恢复包，不执行正式发布或实际rollback |

该卡通过仅代表不可变文件到达服务器，不能标F2/F3发布准出或正式上线。下一阶段的安装/隔离服务与数据范围仍须依据实际源条件另列同合同内的精确卡。包含本节的真实交付SHA以提交后Git/远端回执为准，不把工具执行源或运行包源冒充文档自身HEAD。


## 12. MPM-H3-004 连续执行授权与正式发布精确计划（2026-10-21）

负责人明确指示“只要是合同中的范围均可执行，一次性做完提交”，覆盖后续阶段重复审批；另明确接受历史filter差异无法归因、云安全组8884全部IPv4两项风险，受众限非人体MOCK。没有运行正式Security Gate，没有人体数据授权或采集，没有修改保护分支。

本次正式路由计划绑定 `6edd48c9e83a4609660786ebc240ef4b0ce4e025`，运行包源 `5da742f4e0e078d2d40453facdad1e65ff51fdda`，包含Backend修复 `8afb1e2903f18c3a562769b9e9352db7e1db438a`。runtime payload SHA `b8fbb14b5c356090f8a35f211b9bc1f070be251b58436db7f1445283013ac87e`。正式计划 `/opt/medical-monitor-h3/formal/20261021T093335Z/plan.json` SHA `270e9cd52e3f83b7bc118210418a81252d74a0a30438150d87b86f64e9beb8e6`；完整恢复清单SHA `53e1aec5021e6a0fba8b7e3c8b7df53346f9f8e2bce9c7aa0a64382c503ffed3`。更早、正式角色变更前的完整备份SHA `61f656e835a3689e89f0617d766b5529f7b9a8d9543050fcd83f824fd14145dc` 独立保留。

操作仅启用已冻结18785 Backend/18786 AI两个服务，并把 `/etc/nginx/snippets/medical-monitor.conf` 原子替换为候选SHA `70ac6d03c17b1bcfc54ea87fb8b3fca949d8dabddac191dd7b8b571d58c00ca7`，nginx语法校验后reload；原Backend/AI/MQTT服务保留运行。实际HTTPS/WSS/七页与AI验收后，用同一冻结计划真实恢复原片段并停用新两个单元，验证旧入口，再次启用相同候选并复验。任何无效值可见、读数不匹配、B非OFFLINE、鉴权绕过、TLS错误或不可恢复故障立即停止并按身份门恢复旧路由；不全表恢复防火墙、不删除未知文件、不重写备份、不清空账本。正式站点主机和令牌只经外部受限配置引用，不入库。

正式C镜像43172B SHA `b9b25b186c3b40d62b4a1c1919e09f27b639806271a3b20ae7fc80ea4cda1efe`（8883，保留MOCK/synthetic），generation3配置336B SHA `395c6a36d7c4a636b34a72eacd1ccc2a2fc7f025df7089f3d94e1d2de14c5a3b`，完整64KiB SHA `49d3fad5040b25b746905d5c1468bff4d5be5a4f13197286ce215e0711798fb4`。09:29独立冷启动后只读证实VTOR应用、CPU运行、FLASH_CR=0x80000000/SR=0及sector7/11/options未变。原正式LIVE候选9df43…没有用于非人体源。

正式发布前12秒实测：120个WSS快照PPG/SpO2/PR有效，B始终OFFLINE，无无效值显示；新Backend accepted=886、rejected/dropped=0。这是短窗准入，不冒充正式300秒。C独立供电USB拔下，C_UART_NOT_OBSERVED，不能用Broker计数冒充C实际PUBACK。


## 13. 连续窗口实板与隔离逐层验收（08:14 UTC以后）

来源为负责人确认无人连接、可产生血氧/脉搏及HKB-08B+成功事件的非人体装置；型号、校准和标称输出未核实，始终 `MOCK/synthetic=true`，只验工程传输和时效，不评价生理测量精度。原始帧/Flash/UID/气路数值保存在受限目录，Git只有身份/散列和获准MOCK页面图片。

A新50084B镜像 `f59b76ef865c373c6df62aa09aea958597687f6d46b17c402ceb7126ca8f60d6` 的本轮身份实读一致。初始曾实读System ROM状态，负责人随后正常断电核对BOOT并反馈CAN接反、修正后实际捕获Boot-up/心跳/PDO；不把初始不通信唯一归因为ROM或接线之一。没有把SetPC/MSP/VTOR强行进入应用作为启动验收。A双屏和独立启动均由现场确认正常。

| 真实窗口/任务 | 实际结果与退出码 |
|---|---|
| 隔离08:31:12–08:37:42，390s | exit **1**；最长118.938s，有源中断及网络/临时规则故障，886条MQTT；原件保留 |
| 隔离08:47:25–08:52:55，330s | exit **1**；最长175.889s，925条MQTT；未凑成300秒 |
| 隔离08:52:56–09:00:26，450.117s | exit **0**；新鲜PPG连续 **334.670s**；MQTT1340（QoS1=963、QoS0=377），WSS4450，匹配PPG4181/SpO2 4175/PR4219；Backend accepted3558→4895，rejected/dropped=0 |
| 隔离限定故障09:00:45.630–09:00:51.647 | exit **0**；实际单连接6.002s丢4包/2501B，准确规则已撤；OFFLINE→ONLINE和新有效PPG恢复，另一次自然中断也如实记录 |
| A正常断电及恢复 | C保持运行，现场A J-Link拔下，实际OFFLINE、Boot-up、新NIBP会话65539；旧有效结果不复活。补充20.029s/200快照只读核验exit **0** |
| C接收缓存09:12:58.723–09:13:03.076 | exit **0**；实际五类RPDO过滤器181/281/381/481/681均8B/启用/receiveError=0；这是接收缓存快照，不冒充外部CAN分析仪抓包 |

所有成功有源窗口读数不匹配、无效值可见、B非OFFLINE均0；没有降低发送频率、延长5秒时效或清零故障。串口独立进程退出分别 **1、1、0、1**，首两次及第四次GetOverlappedResult/AccessDenied原件保留。第三次完整1200秒240组诊断无主机组序缺口：FOVR/SW/bad/fault/stale=0，TEC/REC/BOFF=0，接收高水位8；PUBACK358→2682、QoS0 36→310、失败0→4、Router lost0→146、replay1→181。故障窗口损失不伪装为零。第四次末尾有A断电时txfail/no_ack等累计变化；不能把其旧CAPTURING状态当正常进程结束。

临时规则曾错误把SSH出口当作C出口，且首次漏放服务器自身访问；08:37–08:41影响链路，已向负责人说明，按实际C出口及服务器自身修正，全部失败保留。450秒TCP元数据观测19357事件、内核丢0，有重复区间/间歇；无法唯一定位路由器、ESP、WAN或固件，不宣称原网络问题全部根治。

NIBP第一次完成UTCms1792571533215：89.069s仍VALID，90.082s STALE/隐藏；第二次1792572469510：89.069s VALID，90.081s STALE/隐藏。负责人确认两次SYS/DIA同值，新完成事件仍正确恢复有效。第三次用于A断电/新会话旧值失效。原重启观察器要求所有旧流元数据消失过严，未完成PASS；停止进程实际退出0只代表被正常停止，后续更正只检查新NIBP会话及旧值隐藏，另存200快照证据，不覆盖旧状态。

第四次完成实际 `0x281 tick=442196`、SYS/DIA镜像匹配 `0x381`，`0x681 bit9/bit3=true`；实际 `0x481` TIME锚算得1792573969544，与同窗WSS完成UTC毫秒完全相等。AI确定性NIBP事实与该实际WSS内存值相同、MOCK，`NOT_CALLED`、用量不增。A内部result_generation没有单独传到C，报告不伪称C读取了它。

隔离清理09:28:01–09:28:02 exit0：本次preview/AI/Backend/Broker停用，自有INPUT链引用0、8884无监听；全filter393行SHA `e6f238e23dece4fe2763aae2c48a482f749a56f632aeac6d31aa1130d7abed1c`，NAT SHA `96ba2354a7ee95379dbc8c4bc83f5c5d13ccc95d5367d69e3af1e6dec9ed3157`。这与本连续窗口准入表一致，不等于历史395行表已还原。云安全组8884全部IPv4仍在，负责人已明确接受，未修改控制平面。

## 14. 正式C写入、失败、修复与正常冷启动

C写前sector0–3完整64KiB双读一致 `102575dc940425d91b2db7c2a0f22ddf44c5cfab652b1b5ca0790f8924d3705b`，含旧59229…应用和generation2配置。原件、工具身份、UID与供电核对通过。负责人明确允许CAN保持连接、A断电、J-Link连接C；本次不声称三线分离。

09:21:36–09:21:59正式编程进程 **exit1**：限定sector0–3写pending 64KiB并完整读回、再写最后commit字成功，但FLASH_CR单次写LOCK与清PG的恢复方式未得到预期状态，实际 `0x80000201`，立即停止，没有继续GO、重刷、清错误或自动恢复。09:23只读证明完整新64KiB及应用/配置SHA已正确，sector7/11/options不变。离线按实际LOCK行为复现 **exit1**，修复为先恢复未锁定低位再单独LOCK，**88项Host通过exit0**。09:25仅KEYR/CR受限修正尝试 **exit1**（unlock未生效），没有重复Flash编程。该修复后的完整编程序列仅Host验证，未假称再跑过完整实板写入成功。

随后现场正常断电，USB/J-Link拔下，BOOT0/1=GND、J5独立供电；09:29:33–09:29:42再接J-Link只读：**exit0**，CPU未halt/lockup、VTOR=0x08000000、FLASH_SR=0、FLASH_CR=0x80000000、配置generation3、新64KiB SHA49d3…及7/11/options全部核对。09:30单次debug-freeze写回本窗口实际原值0x1800/readback通过，未复位或烧录。后续J-Link拔下的独立联网窗口再验证正常运行。失败1→Host修复0→寄存器尝试1→正常冷启动实读0各有独立原件，未覆盖失败。

保护区sector7/11各SHA `b5a41c3758763bbec72769fab4a2533bf2db0b6312d93d25a695f9e4b9e02260`，options SHA `52d5979da03bd7be45e385920ec7d5901793bab3f6bc1daa0c1c1997f9e91687`。没有全片擦除、RDP或options修改。新C与原隔离C BIN只有端口常量的一字节差别，均43172B；text43076/data88/bss123136不变。A本轮未新增运行代码；相对旧49888B版本的新完成时间镜像为50084B（+196B）。

修改范围：`gateway/physical_can/build.py`加入正式8883+synthetic显式模式及fresh-SNTP门，`r2_flash_c.py`增加对应准确下载profile；`tools/h3_c_jlink.py`仅抽出可复用命令白名单校验，`tools/h3_c_formal.py`限定正式pending/commit/失败停止；相关Host测试及AI失败/超时测试。没有重构CANopen/coreMQTT、改A/C应用时效/路由架构或修改P4/ESP既有核心行为。早期41828B无fresh-SNTP构建仅Smoke，后来已明确禁止用于正式下载；从未烧入该镜像。新增63项、83项旧Host结果按原进程身份保留；实际CR失败后新增88项0才证明修复逻辑，不能用较早83项替代实板发现。

## 15. 正式角色、七页、AI、实际回滚（持续更新）

独立正式publisher写指定GW/A/B状态、A telemetry/replay/event；Backend subscriber仅读相同范围，不授control下行或B telemetry写权限。合并ACL保留旧字节前缀，不覆盖旧角色。loopback TLS实测用实际投递验证“publisher不能读、subscriber不能写”，不是用SUBACK单独推断ACL；首次错误SUBACK断言exit1保留，更正实测exit0。09:31正式8883 SIGHUP既有mosquitto子进程后，新角色CONNACK=0、越权写135拒绝。TLS链/SNI验证开启。

当前合并ACL SHA `c987e3ebe5c884f214f2d334c6416804c24480de735c52b896874e6af3b09853`，password文件只记录SHA `ecd343ceec203afd44737f460b44aa5d23157524761a702978b3e242e50622a4`；明文仅外部受限凭据。原Broker配置/旧角色、主服务PID851111及子851112保留。新runtime在独立Python3.12环境离线安装20个冻结wheel，pip check退出0；旧依赖未升级。Web dist SHA `d081b7036e521208a433a7410f1a86c9f06208260434b4257f10eeddd1a174be`，正式新index SHA `92e1f44f80d1eec38ef17beb0979dfc1fba8088c6a9aa833ab1de15063535acb`。

09:41:18 activate退出0；正式HTTPS index精确匹配，新Backend真实8883订阅，AI DOUBAO/MONITOR。401/404/405、WSS错误令牌1008、非法Origin403实际验证；当前读数NOT_CALLED，一般健康问题真实豆包HTTP200。

09:48:39–09:48:40 **实际rollback退出0**：恢复原Nginx SHA `8e9509551d97489c6cd6a92d4d44f9d6ef06392f031db285e0b1f05d30143ca2`，停用新两服务。09:48:45–09:48:48 **旧版实际HTTPS/WSS复验退出0**：原index SHA `92a48ceea4afb3a3c5b6f34fadd7d3b56063e725321aa2471e3a9285db7a48f0`，旧Backend健康，20个鉴权快照、B离线、无效值隐藏、旧服务PID未变。09:48:52–09:48:54 **同计划再激活退出0**，重复核心HTTPS/WSS/权限及七页桌面/手机检查。回滚针对应用路由与新单元，未回刷C或撤销新正式角色，未把全服务器/防火墙/数据库都恢复；原Backend/AI/MQTT始终运行，旧版本保留可回退。

正式NIBP完成UTCms1792575966019：89.071s VALID、90.084s STALE/隐藏，时间戳未刷新；AI有效事实与实际WSS一致，过期后隐藏，均NOT_CALLED，进程退出0。正式第一420秒窗因源中断最长192.714s、exit1，MQTT1196/WSS4153、Backend拒收/丢弃/数值不匹配均0，负责人明确承认中途取下探头；后续重复取下也单独保留，不把中断归为确定传感器或网络故障。最终独立起点长窗另存，不拼接中断区间。

截图目录：`cloud/evidence/h3-ac-final/formal-https/`（初次正式14张+完成AI2张）、`formal-https-final/`（再激活14张）。七路为overview/temp/ecg/spo2/resp/nibp/ai，1440×900与390×844均7页导航、无页面横向溢出、B离线；初张AI截图还在等待，随后完成回答截图另存，不能用等待截图证明成功。实际完成标签“本轮使用豆包”，模型doubao-seed-2-0-mini-260428；设备播报默认关闭、真实扬声器/ASR/TTS NOT_VERIFIED。浏览器初次daemon继承stdout管道等待已结束，改临时文件捕获后成功，未升级浏览器或终止用户其他窗口。

模型故障/超时：正式UI浏览器内明确合成503、504和15秒Abort，验证失败/超时后不继承上一轮真实模型标签；服务器文件、真实模型和监护网络未被故障注入。Host另有合成TimeoutError/ReadTimeout与HTTP401/403/429/500共7项通过。没有声称实际豆包本轮发生了鉴权失败或超时；正常真实调用HTTP200、错误码无。持久账本取消五次累计上限、保留4并发/每分钟12次/超时/熔断；历史原件不删除，重复历史导入先按内容散列去重为3条独立原记录。金额未知，负责人反馈免费/体验额度，不报零费用。

正式入口和两个独立访问令牌配置在仓库外受限文件 `E:/medical-monitor-h3-private/ac-final/formal-access-config.json`（不含ARK Key）。打开其中formal_monitor_url；连接设置填写GW-C-001和monitor_view_token；第七页 `#/ai` 的独立AI令牌使用independent_ai_token。实际网址由formal_ai_url给出。遵守连接信息硬规则，Git/脚本/日志不写真实主机或口令。原始证据目录 `E:/medical-monitor-h3-private/ac-final/CONTINUOUS-20261021T081425Z`，云端完整恢复包及观测目录留存，负责人可按私有引用复核。


## 16. 最终工程裁定、独立供电与正式有源验收

**最终 `H3_AC_FINAL_PASS`，限定本轮负责人确认的非人体MOCK工程集成、真实豆包文字解释及正式受限访问范围；等待负责人最终H3复核，不开始Node-B。**

| Gate | 最终事实 |
|---|---|
| F0 | 远端/独立工作区/单写入者核对；AC-0/1按原成果继承，风险及源条件逐项注明 |
| F1 | 新A50084B读回、正常独立冷启动、双屏反馈、实际Boot-up与CAN通过 |
| F2 | 真完成NIBP/90秒/同值新事件/新会话不复活，0x281/0x681实板缓存及TIME锚，334.670s隔离有源与6秒限定故障恢复通过 |
| F3 | 新版完整冻结包、有效TLS/ACL/令牌/Origin、两份完整恢复清单逐项验证；负责人接受两项残余风险和非人体受众 |
| F4 | 正式C应用/配置/保护区、正常独立冷启动、实际8883到Backend及C实际PUBACK计数通过；编程CR失败和恢复路径完整保留 |
| F5 | 正式七页与真实豆包、359.701s新鲜PPG、正式NIBP90秒及AI匹配、真实旧版回滚/HTTPS与WSS复验、同候选再次激活通过 |
| F6 | 本报告/最终矩阵/脱敏回执与截图归档，只正常推送既有H3开发远端；无PR/强推/合并/正式Security Gate |

最终长窗 **2026-10-21 09:52:35.126778–09:58:35.285619 UTC**，实际进程exit **0**，360.085s，PPG新鲜连续 **359.701s**。MQTT **1079**（订阅实际QoS1=762、QoS0=317），WSS **3558**；有效且会话/序号/完成时间一致的PPG匹配3478次、SpO2 3480次、PR3433次。Backend accepted541→1618，rejected/dropped=0；坏MQTT、读数不匹配、无效值可见、B非OFFLINE、错误源标签均0。三流同时有效最长203.832s，附属`all_three_valid_exit_code=1`原样保留；合同实际准出是`active_ppg_exit_code=0`，没有把源质量INVALID强改VALID。此前两段源被取下的正式窗口均保留各自exit1，不把其区间拼接入359.701秒。

该窗口 C 为J5独立供电、USB/J-Link均拔下，**C_UART_NOT_OBSERVED**。762是观察订阅收到的QoS1消息，不冒充C已接收PUBACK=762。为补足正式C回执层级，长窗结束后负责人临时接回J-Link，**09:59:14.872109–09:59:27.855049 UTC**做单独只读短窗，**exit0**，先UID/准确正式镜像SHA匹配，CPU未halt/lockup、VTOR应用，再读两组对齐32位累计计数（不是全组原子快照）：

- C实际QoS1 PUBACK **3133→3157（+24）**，uptime1804556→1815231ms；QoS0累计1059，采集已经允许停止，短窗增量0；发布失败累计0。
- 心跳2856→2878（+22）、实际CAN TXOK3007→3030（+23），NMT START ACK累计1、TIME143→144；181累计60984，381/481各1430→1440、681 1488→1499。
- FOVR/SW/bad/stale/fault/Router dropped均累计0，接收高水位9、ESR=0（TEC/REC/Bus-off=0）。Router replay累计14未归零。
- 累计tx_failed=1、tx_no_ack=1、peer_losses/returns各1、tx_peer_discard=782均保留，短窗无新增；不能宣称从开机以来所有丢弃为0。
- 三次J-Link连接仅connect/savebin/q，显式halt/reset/寄存器或Flash写命令0；SDK连接行为不作绝对无副作用保证。ARM目标ABI对象SHA `93a39e588a00becbeeacf7f8c9c83446673c508fabf352e14c2e43955cb6b1b4`，正式ELF SHA `2263a70a3abe2fcfdfaed6385c2615d7817a22d8c1b552b611c153043f266d03`。布局探索首次缺头文件失败两次保留，补齐原storage头搜索路径后离线编译通过，没有链接或修改固件。

负责人已最终回报 **“J-Link已拔，保持独立运行”**。此后没有再操作设备；A/C由原J5供电，BOOT0/1均GND、CAN三线保持、USB/J-Link拔下，无人体连接，模拟输入可停止。C使用已选择的2.4GHz路由器持久配置，**不依赖电脑或手机热点**；仍需要该路由器有网络，离线时系统应显示失效/离线，不能保证断网仍实时上云。

最终运行：`medical-monitor-h3-webbackend.service` PID **2758089**、`medical-monitor-h3-webai.service` PID **2758088**，均active/enabled、ExecMainStatus=0；新Backend端口18785、新AI18786仅回环，Nginx正式前缀路由到它们。原Backend845095、MQTT851111/子851112、AI394625及Nginx主进程保留；旧AI10:00只读健康为ok/DOUBAO/MONITOR。两份完整恢复包最后再验证通过，旧包/旧配置/旧单位/原角色均保留。实际rollback范围仅Nginx路由和新应用单元；未宣称C固件、正式角色、数据状态或整机全量恢复。

本连续轮真实豆包 **6次，2265 prompt +295 completion =2560 Token**，全部HTTP200/VALIDATED，真实request_id/模型名/耗时/用量见 `collect-final-environment.json`。包含历史去重3条的账本总计 **9次/6138 Token**，不归零；累计上限null，未再依赖旧五槽。再次激活后09:55:33真实调用480 Token、request_id `021792576533835534779bc6a83ab3f36a7a90c1e71ba35eb3ead`，当前进程健康REAL_MODEL_VERIFIED；确定性当前读数/过期血压/B离线核对NOT_CALLED且不增加用量。负责人反馈免费/体验，实际货币费用 **UNKNOWN**，不推断为零。

最后只读环境核验10:00:23–10:00:24 exit0：候选Nginx精确匹配、原服务身份未变、合并ACL/密码文件SHA一致，完整恢复包可验证，隔离四服务inactive、8884监听0，filter393行/NAT12行SHA与第13节一致。本机旧预览隧道18767无监听；仅本任务两个浏览器会话收尾。正式浏览器close返回1的原件保留，经本任务pid文件及创建时间核对后仅关闭其Chrome子进程和daemon；另一个本任务会话正常close0，没有关闭用户其他窗口。

## 17. 证据导航、Git交付与后续边界

- 实际逐进程退出码/原始散列索引：[execution-index.json](../../cloud/evidence/h3-ac-final/continuous-20261021/execution-index.json)。索引并不声称全部进程成功；launcher退出0与worker实际退出1分别记录。
- 隔离长窗/NIBP/TCP：[collect-current-observations.json](../../cloud/evidence/h3-ac-final/continuous-20261021/collect-current-observations.json)；重启更正：[verify-restart-recovery.json](../../cloud/evidence/h3-ac-final/continuous-20261021/verify-restart-recovery.json)；0x281实际缓存：[C-actual-RPDO-completion.json](../../cloud/evidence/h3-ac-final/continuous-20261021/C-actual-RPDO-completion.json)。
- C原编程失败、受限寄存器失败、正常冷启动实读分别为 `formal-C-program.json` / `formal-C-control.json` / `formal-C-cold-read.json`；修复复现失败与88项通过分别为 `reproduce-flash-lock.json` / `fixed-flash-lock.json`，原始错误不覆盖。
- 正式最终窗、NIBP、旧路由实际回滚/再激活、模型回执：[collect-final-state.json](../../cloud/evidence/h3-ac-final/continuous-20261021/collect-final-state.json)；正式C直接计数：[C-formal-actual-counters.json](../../cloud/evidence/h3-ac-final/continuous-20261021/C-formal-actual-counters.json)；环境/6次模型清单：[collect-final-environment.json](../../cloud/evidence/h3-ac-final/continuous-20261021/collect-final-environment.json)。
- 正式再激活七页截图索引：[browser-final-result.json](../../cloud/evidence/h3-ac-final/continuous-20261021/browser-final-result.json)，[桌面总览](../../cloud/evidence/h3-ac-final/formal-https-final/desktop-overview.png)、[手机血氧](../../cloud/evidence/h3-ac-final/formal-https-final/mobile-spo2.png)、[正式AI真实回答](../../cloud/evidence/h3-ac-final/formal-https/desktop-ai-completed.png)。本地隔离预览截图保留，未混称为正式HTTPS。
- 新增运行代码实际冻结为 `6edd48c9e83a4609660786ebc240ef4b0ce4e025`；仅追加AI回归后的代码/测试HEAD为 **`8ff12de002cdd8c910e5a84b438589cc125ceec7`**。服务器运行包仍精确来自 `5da742f4e0e078d2d40453facdad1e65ff51fdda`，不把新的证据/Flash工具提交伪称已部署的服务器源码。
- 包含本报告/最终矩阵/截图的交付提交由正常commit后实际取得，最终回复给出；完整SHA/远端一致性在外部 `E:/medical-monitor-h3-private/ac-final/post-push-receipt.json` 中记录，不预写不存在的自身SHA。本文件可用 `git log -1 --format=%H -- doc/H3/H3-AC-CLOSEOUT-FINAL-HANDOFF.md` 查询其实际提交。只推既有H3开发远端，工作树清洁及保护ref对照以该回执为准。

当前不再需要合同内重复分阶段审批；停止等待负责人**最终H3验收**。残余事项：历史整filter差异仍不能归因、云安全组8884仍全IPv4且无控制平面API核验（均已接受）；源型号/校准/临床精度未验证；UART ROM握手原因未解决（改用J-Link）；新完整编程工具修复仅Host验证；网络分段根因未唯一定位。真实人体、临床使用、扬声器/ASR/TTS、Node-B和新的云安全组/架构扩展另行定义范围，不在本次PASS中。没有新功能授权请求，也没有虚报Node-B在线。
