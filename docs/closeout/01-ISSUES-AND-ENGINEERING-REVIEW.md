# 多参数监护系统结项审查

## 问题闭环、遗留事项与答辩技术难点

**审查日期：2026-11-12（America/Chicago）**  
**项目：** `Serendipity-min/medical-multi-parameter-monitor`  
**定位：** 五板多参数监护工程样机的最终仓库审查与阶段结项依据。

本报告以仓库代码、历史执行回执、Claude 的 R1–R65 复核记录及本轮离线回归为依据。用户上传的 `ISSUES-SUMMARY-20261112(1).md` 与 Claude PI 分支的结项总结字节相同；本报告在其基础上补充代码核对、后续状态变化、独立历史分支检查和本轮发现的可复建问题。历史失败原件和审查记录保持原貌，本报告给出截至本次审查的统一解释。

本轮部分工具日志使用 UTC，因此日期显示为 **2026-11-13**；换算至审查采用的 Chicago 日期仍为 **2026-11-12**。历史现场时间沿用原回执标注，不将 UTC、北京时间和本机时间混用。

---

## 1. 最终结论与能力边界

**项目已形成可展示、可追溯的五板工程样机。** 当前完成的主链路为：A/B/D/E 采集与本地显示 → 双 CANopen → C 汇聚与时间/队列管理 → ESP8266 TLS/MQTT → 云后端 → 公开只读网页；云端确定性规则生成播报后，还可经 MQTT 下发到 C，由 TW-TTS 模块驱动喇叭。

这项结论不等于所有测量精度、所有故障恢复、所有负载和长期运行均已通过。项目最有价值的成果是：打通了完整链路，解决了实际遇到的采集、总线、出口容量和恢复问题，并留下了原始失败与改善效果的证据。尚未关闭的问题也已经可以明确描述，而非藏在“联调完成”四个字里。[最终样机裁定][r65]、[安装与现场回执][az3]

### 1.1 当前可以确认什么

| 项目 | 当前结论 | 可主张的范围 |
| --- | --- | --- |
| 五板架构 | 已实现 | A：SpO₂/PR/PPG；B：ECG/RESP/HR/RR；C：网关与播报；D：GY641 物表温度；E：NIBP |
| 双 CANopen 与上云 | 有工程验证 | 两段独立 500 kbit/s CAN；正式云身份与节点映射已配置；公开网页可观察 |
| 原出口吞吐缺口 | 已修复至当前负载可运行 | 多个有限窗口稳态约 10.45–10.50 批/s；不能外推为任意负载或长期容量余量 |
| 约三分钟断网标量保留 | 限定场景 PASS | S3 约 203 s 断网，五路标量 1,030/1,030，零缺失、零重复、保序；不是所有波形全量无损 |
| 自动网络恢复 | 已实现并有实板记录 | 退出透传、重入、退避；网络失败不再简单按第三次永久停传；字节级断链根因未关闭 |
| 真人窗口 | 部分通过 | 传输与一次 NIBP 工程结果通过；SpO₂ 数值合理性未通过；ECG HR仍使用模拟器 |
| 确定性播报与板载喇叭 | 样机级 PASS | TEMP、HR 播报及断电/复电行为有现场听辨与WSS证据；没有带声录像 |
| 30 min 稳态观察 | 已完成 | WP-AZ 指定窗口内无链路劣化；不替代2 h/24 h长测 |

依据：[五板接手说明][handoff]、[S3执行][s3]、[窗口2][window2]、[真人窗口统计][stats]、[R65最终补充][r65]。

### 1.2 必须同时说明的限制

- **正式 C 固件没有使用 FreeRTOS。** 它采用裸机协作循环、中断和有界队列；MQTT 客户端为 coreMQTT v2.3.1 / MQTT 3.1.1。coreMQTT 来自 FreeRTOS 项目，不意味着已启用 RTOS 内核。[源码身份][core]、[实际构建白名单][build]
- **正式 WP-AZ 镜像关闭麦克风采集，保留板载 TTS 下行播报。** INMP441 → ASR → AI → TTS 的单板台架成功是历史成果，不能写成最终五板镜像同时启用的功能。[WP-AZ构建][az1]、[历史语音结果][voice]
- **GY641 提供物体表面温度。** 当前没有把它标定成可靠的核心体温测量，不应将皮肤表面约31–34℃解释为人体体温异常。[统计与来源][stats]
- **SpO₂ 的 VALID 标志不能替代数值合理性或精度验证。** 两批有效读数中分别有22.7%和14.8%超出项目预登记范围；中位数与持续时间规则用于减少播报误触发，没有修好传感器测量精度。[R43统计][stats]
- **当前“AI”主要是确定性事实问答和规则播报。** 仓库保留模型适配器与历史模型试验，最终主路径不代表调用付费大模型，也不提供医学诊断。[问答代码][ai-before]、[播报实现][broadcast]
- 所有验收结论均是**工程样机范围**，不能作为临床精度、医疗器械合规或长期可靠性的证明。

### 1.3 状态词怎么读

| 状态 | 本报告中的含义 |
| --- | --- |
| **已修复并验证** | 有具体实现变化和对应验证；会写清是Host、有限实板窗口还是现网记录 |
| **缓解，根因未关闭** | 降低了故障影响或增加恢复能力，但没有证明原始故障成因消失 |
| **NOT_PASS，已接受** | 原预登记指标未达到，负责人决定接受该限制；保留未达事实，不改名为原指标通过 |
| **UNKNOWN** | 缺少根因、精确数值或充分的因果证据，不将推断写成事实 |
| **NOT_RUN** | 尚未完成相应范围的验证；软件通过不能替代硬件，模拟器不能替代人体 |
| **历史失败，后续有限复测通过** | 原失败保留；新结果只覆盖新窗口，不对旧失败作追溯性改判 |

---

## 2. 审查依据与当前基线

### 2.1 关键提交

| 对象 | 审查锚点 | 用途 |
| --- | --- | --- |
| Codex最新固件与回执 | `7c94cc1ceb83b1f00097272563e30f6b17a9b616` | 运行代码、R64现场回执及此前嵌入式历史 |
| 正式 WP-AZ 实现 | `2c9709474d11d09d8538783d44aea189a1864af8` | 最终TTS播报实现；到7c94cc1仅增加证据文件 |
| Claude PI复核 | `01df885ebdb3ee1ac874a562a60ac301a4eb3b04` | R1–R65及上传的问题总结 |
| Claude UI | `1945c9cc7273e352a5f3d219c8d7a3fdc99d5e19` | 最终界面、趋势/历史、浏览器朗读与状态显示 |
| 本轮整理与最小修复 | 见第10节治理记录 | 与历史部署锚点区分，不能冒称已经部署到设备或云端 |

本轮枚举了两个 Claude 分支与全部其他远端分支的提交关系，核对独立成果和历史归档价值；R1–R65编号均存在，相关目录共有67份R开头Markdown。对所有分支做了清单与差异分组，对当前源码、关键缺陷和状态变化逐项溯源。**这是一轮覆盖全部分支的系统审查，不意味着对每份历史脚本和第三方源码都做了逐行形式化验证。**

### 2.2 正式部署基线与资源

R65冻结的 C 镜像为 WP-AZ，源码 `2c97094`，boot 392 B，code 61,228 B；code SHA-256 为 `9d1902461e340a20672be54ef255215ddb95a3936d0030fc4cdb5db818a9d083`。写入范围为sector0/4，sector3正式配置保持一致；WP-AY0是已登记的回退对象。云后端版本为`wp-az-2c97094`，页面为`web-20261112-03`，正式HR自动播报在测试收尾后关闭。[R62制品][az1]、[R64安装][az3]、[R65冻结][r65]

| 区域 | WP-AZ占用 | 余量 | 解读 |
| --- | ---: | ---: | --- |
| sector0，16KiB | 392B | 15,992B | 向量/boot区域 |
| sector4，64KiB | 61,228B | 4,308B | 当前代码分区，新增功能余量有限 |
| 常规SRAM，128KiB | 116,048B，含预留堆栈 | 15,024B | 不等于实测运行时最坏栈余量 |
| CCM，64KiB | 61,824B | 3,712B | 当前主要用于标量/状态保留，不是PCM录音区 |

这张表是固定分区策略下的预算。F407器件的总Flash并非只有64KiB；“当前不引入RTOS”是项目阶段和资源分配选择，不能扩展为“该芯片不可能运行RTOS”。

---

## 3. 已修复或已完成的问题

### 3.1 采集、算法、显示与CAN

| 问题 | 修复/处置 | 验证结果与边界 | 证据 |
| --- | --- | --- | --- |
| 主循环迟读ADS帧造成丢样 | DRDY中断读9B帧，128帧FIFO，保留源时间戳与序号 | 3,406帧捕获/交付一致，限定窗口错误计数为0；不宣称任何负载都不丢样 | [历史证据矩阵][matrix] |
| START使用PA1时出现异常间隔/边沿 | 改用PG15 | 异常消失；与板载网络共用的因果解释仍属推断 | [历史证据矩阵][matrix] |
| SPI配置和初始化缺少回读 | 分频/64改为/128，加入真实寄存器回读 | 8,412帧完整；当时开放输入不构成生理精度验证 | [历史证据矩阵][matrix] |
| RESP削顶连带ECG失效 | BIO_V2逐路`accept_input()`和独立原因位 | 隔离用例28/28；不再把一路无效传播成两路同时失效 | [B-ALG-002][alg] |
| HR/RR旧算法与初态问题 | BIO_V2重写、有效性和原因位明确化 | ECG60/90/120各两轮通过；RR12/18/24六窗681/681稳态观察有效；不同模式分别验收 | [算法交接][alg] |
| 呼吸电极路径不正确 | 按参考手册接RA–LL路径 | 出现可分析呼吸周期；不等于完成阻抗绝对标定 | [算法交接][alg] |
| 历史B温度屏固定显示36.5，五板后迁至D | 补齐USART3及板载RS232/屏路由，再迁移至D温度角色 | 读数与现场显示一致；显示值仍是GY641物表温度 | [三板显示修复][two-group]、[五板记录][five-field] |
| CAN仲裁后心跳缺失 | NART=DISABLE允许自动重传；STOP有界取消邮箱 | 三窗180/180；不替代故障注入和物理裕量测试 | [B-PRECAN][precan] |
| CAN中断早于应用运行标志 | 延迟IRQ使能到协议进入正常模式 | Host复现早到循环并回归；避免初始化阶段反复进入未就绪处理 | [五板修复提交][five-fix] |
| 同COB-ID多邮箱导致顺序风险、待发PPG被覆盖 | 请求先后发送；待发槽未释放时保留源积压 | 五板定向修复/现场回执保留；不能据此抹去后续源端PPG缺口 | [五板修复提交][five-fix] |
| ISR新样本的年龄被无符号差误判 | 使用有符号tick差和一致的采样时刻 | 当前Node-A代码保留修复；避免新点被当成约49天旧点 | [年龄策略][age] |

### 3.2 C出口、透传、恢复和数据保留

| 问题 | 修复/处置 | 验证结果与边界 | 证据 |
| --- | --- | --- | --- |
| 输入约10.45批/s，出口仅约8.08批/s | DWT分解service/发送/接收开销，改为115200 SSL透传 | W3工作段10.458批/s，队列6/24，0丢弃；后续稳态约10.45–10.50批/s | [R6分析][r6]、[W3][w3]、[R36][window2] |
| 一次START被Wi-Fi失败提前消耗 | 增加独立`FIELD01 PRE`预检 | 入网、串口前提可先检查，不消耗正式START；没有追溯证明旧失败唯一原因 | [预检架构][preflight] |
| ESP实际flow=1与先前flow=0假设不符 | 按实际五元组允许flow0/1，拒绝未支持状态 | 预检实板通过；不靠猜测改持久UART参数 | [R5回执][r5] |
| T0前TLS“失败”实为本地剩余预算不足 | 根据剩余预算安排完整AT事务与收尾 | 后续五板窗口完成；当时不是已证明的TLS服务故障 | [TLS修复回执][tls-budget] |
| SNTP被关闭时初始化过早退出 | 明确识别`+CIPSNTPCFG:0`，易失启用并回读 | 冷启动时间门问题有修复证据；外部SNTP零回复仍独立开放 | [B5修复交接][repair] |
| STOP后透传退出不确定 | 静默→`+++`→静默→AT确认，有界退出和重入 | 历史重入实板通过；对端断开是否自行退出透传尚无直接验证 | [R21执行][r21] |
| 重入次数耗尽后永久停传 | WP-AW长退避，网络失败继续重试，本地不可恢复异常才停止 | 2/4/8/16/30s退避；多轮失败没有继续消耗为永久停传 | [R36窗口2][window2] |
| 冷启动约222–225 UART错误误触发锁停 | ESP静默后建立基线，稳态使用新增错误 | 480s稳定观察新增错误为0；噪声物理来源仍未示波确认 | [R22执行][r22] |
| WP-AX冷启动缺陷叠加 | 接纳无连接的STATUS0/1；完整ready/AT确认后才重设复位噪声基线 | Host复现与冷启动复测通过；不等于PF6所有实板路径完成 | [R40原因审查][cold]、[R41修复][ax] |
| 配置缺失被误改成停止本地采集 | 恢复LOCAL_ONLY，保留本地CAN服务 | 对应回归及位级核对；网络配置缺失不应自动变成本地停机 | [R35回执][local-only] |
| 断网时源时间锚/缓存层层失效 | UTC保持610s、CCM标量/状态环、实时优先回放 | S3五路1,030/1,030；保留期240s，状态不云端回放，波形尽力 | [S3][s3]、[保留环][router] |
| 回放队首因时间戳检查失败卡住 | 时间戳检查、保留/出队语义及Host用例修正 | 软件回归通过；没有篡改原始采集时刻 | [R25回执][r25] |
| 新A标量抢在更老B标量之前，使温度STALE | 同级标量按原始时间先后调度 | 后续指定复测0 STALE；保留原101/2,967失败记录 | [两组联调][two-group] |

### 3.3 正式云、Flash、网页与语音

| 问题 | 修复/处置 | 验证结果与边界 | 证据 |
| --- | --- | --- | --- |
| 冻结镜像与正式云端口/网关/身份/节点不匹配 | WP-AY0 formal-cloud档、正式sector3和five后端 | 正式云直连通过；不以隔离Broker成功替代正式云 | [R52回执][formal] |
| sector3擦写后才发现提交预算不足 | 改为写前预算判断，恢复时只补1个提交字 | 0次重擦、1个提交字完成恢复；整片核对，原失败保留 | [R50修复][flash-fix]、[R51恢复][flash-recover] |
| webai沿用旧令牌/旧节点映射 | S2更新令牌与five映射 | 历史现网记录通过；仓库整包重部署另有本轮修复，见§3.4 | [R48回执][r48] |
| 页面必须带令牌不便展示 | 公开只读视图，保留Origin/网关检查 | R53通过；AI仍有独立鉴权，公开只读不表示全部服务匿名 | [R53复核][r53] |
| NIBP90s边界不一致 | 运行代码统一为年龄严格小于90s才有效 | 实现已修；本轮同步旧测试断言，不延长数据有效期 | [Hub实现][hub]、[原测试][five-test] |
| 源码包压缩SHA跨环境变化 | 改用未压缩tar并逐成员对Git blob | 部署包内容可追溯；不把压缩器元数据差异当代码漂移 | [R48回执][r48] |
| 后端WebSocket测试偶发CancelledError | 测试夹具读快照后显式关闭并等待服务端关闭帧 | R54连续20轮、R55独立5轮通过；属于测试清理时序缺陷，已经关闭 | [修复提交][ws-fix]、[R54][r54]、[R55][r55] |
| 浏览器run1朗读无声且无状态提示 | 用户手势解锁、中文音色选择、软键显示朗读状态 | 后续有声；原run1唯一触发因素未确定 | [最终UI提交][ui-commit] |
| 正式透传镜像禁音频，旧回复又依赖麦克风会话 | MPB1独立下行，3槽队列、TTL、顺序去重、有界UART服务 | R65§6已确认TEMP/HR喇叭播报，样机级PASS；无带声录像 | [R62][az1]、[R65][r65] |
| 历史TTS STOP只收到ACK，空闲状态不确定 | STOP→ACK→查询0x21→0x4f | 旧语音台架/统一模式保留证据，当前驱动继续保留修复 | [TTS状态机][tts-queue] |
| 历史64,000B PCM与普通SRAM/Flash预算冲突 | PCM放CCM，DMA留常规SRAM，boot/code分段 | 历史单板全链路通过；最终CCM已改用于断网保留，不能声称两套同时启用 | [历史语音][voice]、[WP-AZ资源][az1] |
| Windows/VPS镜像尺寸不一致 | 固定Arm GNU14.2.1、SPL及库输入，独立重编 | 后续候选boot/code/HEX逐位一致的历史回执；本轮未重做ARM构建 | [R6构建][r6] |
| 工具把MEM-AP负返回解释成short-read、读活动RAM跨槽混字 | 保留原生返回语义、绑定槽身份/快照 | 避免把观测工具错误误判成固件错误 | [MEM-AP审查][memap]、[历史矩阵][matrix] |

### 3.4 本轮新增的仓库修复

以下是**本轮审查发现并离线修复**的可复建或验证问题，不是新的现场部署结果。最终提交/PR由第10节记录。

| 新发现 | 原始表现 | 本轮最小修复 | 验证与边界 |
| --- | --- | --- | --- |
| 正式WebAI网关被请求模型拒绝 | 即使Settings允许GW-C，`Question`模型仍固定GW-B5，正式请求返回422 | 语法支持已知GW-C/GW-B5，实际授权继续由白名单控制；增加`P6_GATEWAY_IDS`，默认仍只隔离GW-B5 | 进程内合成LIVE快照验证正式D温度/E血压、拒绝其他网关；未部署，不能宣称修复了现网故障 |
| five模式旧NIBP测试期待恰好90s仍有效 | 定向回归64过/1失败，与已有严格边界相矛盾 | 仅把90s预期改为无效，不改生产逻辑 | 修复后65过；不以改门槛掩盖实现问题 |
| Security Gate工作流上下文非法 | `jobs.gate.env`使用`runner.temp`；历史失败运行jobs=0 | 将路径初始化移至step，使用`RUNNER_TEMP`写入`GITHUB_ENV` | YAML/触发条件/权限/原步骤静态核对通过；未dispatch、未运行扫描，不能写Security Gate PASS |

正式WebAI重部署时需要显式配置`MPM_NODE_PROFILE=five`与`P6_GATEWAY_IDS=GW-C-001`，并沿用已有只读WSS和鉴权配置。历史线上曾保留正式app/reader、仅替换facts.py，因此“线上可以用”和“仓库整包能复建”此前并不完全一致。[修复前app][ai-before]、[S2部署范围][r48]

工作流错误属于**配置没有成功进入作业运行**，不能说“安全扫描发现漏洞”或“安全扫描已经通过”。[历史失败运行][workflow-run]

---

## 4. 偶发、未稳定复现或后续窗口未再出现的问题

这里单独列出用户关心的偶发问题。所谓“后续未复现”，只说明已观察的窗口里没有再出现，不能证明根因消失。

| 编号 | 现象 | 复现与后续情况 | 当前判断/需要保留的边界 |
| --- | --- | --- | --- |
| I01 | B/C CPU停在系统ROM，VTOR=0x1FFF0000 | 历史发生，部分场景需人工RESET；后续正常运行不解释旧事件 | 根因UNKNOWN；调试器副作用/BOOT状态均未证实，保持独立问题 |
| I02 | TEMP180末帧1条校验不一致 | 该轮异常保留，后续温度600/600通过 | 历史失败未关闭因果，不删异常或宣称从未发生 |
| I03 | 个别ECG90s不稳、RR初窗削顶 | 稳定输入复测曾通过 | 模拟器、导联、供电和CAN耦合未单变量分离；同窗双有效未验证 |
| I04 | R43原批次4条实时标量被顶替 | 后续均经REPLAY到达，两路实时+回放各300唯一标量；复测无顶替 | 数据没有丢失，排队触发原因UNKNOWN；不能写成4条永久丢包 |
| I05 | `svc_max≈21ms` | 只能定位到跨工作段/停发/STOP的采样区间 | 不知道具体调用；不能当作已定位的稳态最大耗时来源 |
| I06 | 230400候选收尾`RESTORE=DIRTY` | Host复现H-JUNK并修复；实板原因未确定 | 230400未进入正式生产；保留原候选问题，不与115200现状混淆 |
| I07 | 早期FIELD01 Wi-Fi入网失败 | sector3凭据与先前RAM配置不同；后续预检和正式配置解决可用性 | 历史现场实际热点配置仍未完整证实，H1凭据不一致最可能，超时等未排除 |
| I08 | 浏览器run1无声 | run2起有声，UI增加可见状态及中文音色选择 | 交互/兼容性增强已完成，旧轮唯一根因UNKNOWN；不再是当前功能阻断 |
| I09 | HR120测试中零星INVALID | 设定模拟器后不再触碰的run4稳定通过 | 可说明该操作条件下复测正常；不能说所有输入情况下算法均稳定 |

证据：[CPU/算法历史][alg]、[PRE-CAN][precan]、[RR/TEMP批次][rr]、[R43统计][stats]、[W3][w3]、[R63][r63]。

**已经不能继续列为“未解偶发问题”的两项：** WebSocket `CancelledError`已被测试时序修复关闭；两次曾未解释的复电后来由负责人确认是本人手动操作，不能继续写成未知远程控制或安全事件。[R54/R55][r54]、[R57负责人说明][r57]

---

## 5. 多次出现、根因未明，以及未达但接受的事项

### 5.1 多次出现且根因未关闭

| 编号 | 问题 | 已经知道 | 仍不知道/最终状态 |
| --- | --- | --- | --- |
| U01 | MQTT协议错误、畸形载荷和断链 | R33累计9次，稳态无人操作也出现；本地短写/TXE超时/重入计数未显示异常；已实现恢复 | ESP缓冲、C应用组包、UART线路等不能仅凭现有证据完全排除。线上逐字节完整性UNKNOWN；根因未关闭 |
| U02 | 新鲜SNTP零回复 | 短断网后Wi-Fi多次成功关联，17次零回复加退避耗时显著；取得合格SNTP后很快上线 | 外部零回复原因UNKNOWN；热点上游未就绪是推断，不是已证实根因 |
| U03 | SpO₂数值越界但VALID | 原批次66/291、复测44/298越出项目94–100%范围；中位数均95% | 无参照仪器、佩戴/运动/灌注/模块算法原因未分离；数值合理性NOT_PASS |
| U04 | PPG按点缺口 | 早期约6.3–6.8%且有约2.08s特征；后期窗口覆盖99.30%/98.81% | 源端质量门控解释有支持，但模块算法窗口与工装耦合未知 |
| U05 | 冷启动UART约222–225错误基线 | 基线机制已避免正常启动被误锁停 | ESP ROM74880baud日志与115200接收不匹配是合理假设，未做线上波形确认 |
| U06 | 两段CAN约40–41Ω端接 | 有限窗口TEC/REC等无异常 | 无差分波形和受控故障注入，物理裕量未验证；计数为0不等于电气条件最优 |
| U07 | RR模式零星HR有效 | 0–6个快照，可见43/66/88/146等值 | SOURCE_UNKNOWN；不把它们当真人HR有效性证据 |

依据：[R27追查][disconnect]、[R33][r33]、[R36][window2]、[R43统计][stats]、[五板物理条件][handoff]。

**断链计数纠正：** R33的9次由R22一次、S2四次、S2-b两次、S2-c收尾一次、S3一次组成。S2-c/S3部分事件紧邻人工动作，先后不确定，所以应写“累计9次断链，包含无人操作稳态事件”，不应全部称为“9次非人工断链”。[R33][r33]

**TLS能说明的边界：** Broker在TLS连接内报告MQTT协议错误，支持把排查重点放在发送应用/封装与接入链路端点；TLS完整性并不能单独证明“ESP内部缓冲必然坏了”，也不能证明“STM32输出的每个字节都正确”。发送计数器证明的是可观测路径没有触发指定错误，不是线上完整抓包。[R27][disconnect]、[S3][s3]

### 5.2 原始指标未通过，负责人接受限制

| 项目 | 预登记/目标 | 实际证据 | 最终解释 |
| --- | --- | --- | --- |
| 热点恢复后实时遥测 | ≤90s | 一轮约551–582s | NOT_PASS，已接受；不是把超时改称合格 |
| 标量积压排空 | ≤390s | 1,239条约676s，约1.83条/s | 数据全部到达、保序；性能未达接受。两在途提速方案取消 |
| PUBACK峰值 | 一轮≤800ms | 811ms；其他补传/断链窗口曾1,732/2,496ms | 保留各窗口差异，不把不同场景最大值混成同一分布 |
| RR批次 | ≥118/120 | RR24-R2为108/120，RR30-R1为94/120；全批13/15通过 | 旧失败保留，不因12/18/24名义矩阵通过而覆盖 |
| RR15特定历史端到端窗口 | 该轮完整工程验收 | 若干旧轮未过，另有独立B→C稳态窗口通过 | 按窗口、阶段、固件区分；不能写“RR15从未通过”，也不能写“全部RR15问题已关闭” |
| SpO₂数值合理性 | 项目预登记94–100%范围 | 两批显著比例超范围 | 限定工程NOT_PASS；不据此诊断被测人员，也不声称传感器精度合格 |

依据：[R33][r33]、[R36][window2]、[RR批次记录][rr]、[B→C旧窗口][precan]、[R43][stats]。

### 5.3 已知设计取舍

1. **保留资源有限。** 1,472项标量、736项状态，各28B，使用61,824B CCM；保存期限240s。UTC锚可保持610s，但数据缓存不会因此自动扩展至610s。短物理断网若加上长SNTP恢复超出保留期，仍可能丢失。[保留定义][router]
2. **状态历史只留设备本地，波形尽力保留。** S3的“标量无损”不能扩展为状态和全波形均云端无损。[S3][s3]
3. **当前状态/FAULT帧仍有MOCK语义。** 正式生理遥测LIVE与状态MOCK并存；播报只使用符合条件的生理LIVE数据。标签是软件来源语义，不能代替真实输入说明。[发布策略][policy]
4. **TTS电源/协议就绪没有实时感测。** `tts_enable(..., true, true)`依赖安装和现场验证；模块断电时固件不能直接识别供电消失。[TTS实现][tts]
5. **重播规则保持现状。** 离线不清同参数5min重播计时，因此复电后TEMP可能约92s才播；负责人已选择保持。后端重启会清内存历史并重新计时，可能新生成一次播报。[R65][r65]
6. **正式gateway-c写ACL仍较宽。** 收窄草案没有完整上线验证，本轮不改生产ACL；它属于尚未实施的加固项。[R64][az3]
7. **sector3的180s主写入流程仍有预算限制。** 最后提交字恢复通过，不等于今后每次完整擦写都能在同样时限完成。[R50][flash-fix]、[R51][flash-recover]

---

## 6. 未完成的验证与后续工作边界

| 未完成项 | 当前已有证据 | 还缺什么 |
| --- | --- | --- |
| 真人ECG HR | 模拟器多档名义速率与播报通过 | 真人输入、参照与合适测量条件；正式HR播报目前关闭 |
| 同一窗口HR/RR双有效 | ECG与RESP分别验收过 | 同一固件、同一窗口和输入条件下双有效证据 |
| 2 h/24 h长期运行 | WP-AZ30min指定稳态窗口 | 更长窗口断链率、资源变化与数据完整性；短窗不能证明改善长期断链率 |
| PF6完整实板硬复位恢复 | Host覆盖ready/AT/错误基线/失败分支，现场曾进入相关恢复路径 | 受控完整成功与失败场景、复位后重新建链的独立实板验证 |
| 最新恢复策略下的独立自然断链 | 历史断链有自愈；窗口2/3未出现独立自然断链 | 最新冻结策略遭遇此类故障的长窗证据 |
| 极限容量、长时间余量 | 142s工作段和后续300s稳态 | 最高可承载负载、长窗边界、不同实际输入；不能用一次负载通过推定所有余量 |
| CAN物理裕量/故障注入 | 实测端接、有限窗口计数 | 差分波形、规范端接与受控异常场景 |
| 各测量量绝对标定 | 传输连续性、工程范围与名义速率 | ECG幅值、阻抗、温度、NIBP、SpO₂的参照与精度评估 |
| 整机麦克风上行/语音问答 | 历史C单板或三板相关台架成功 | 当前五板冻结镜像下联合容量与资源验证；正式镜像未启用 |
| 付费AI模型正式服务 | 历史适配与试验代码 | 已搁置，当前确定性问答不冒充付费模型验收 |
| 对端断开后ESP是否自动退透传 | 本地有显式退出/重入实现 | 设备真实行为直接证据 |
| 精确上电/断电耗时 | WSS、COM枚举和历史时序上界推定 | 统一时钟下独立记录真实拨开关秒数与网络尾延迟 |
| 全部回退路径实操 | 备份、恢复计划与部分演练 | 未逐一实操的路径仍保留“未演练”；有备份不等于恢复已测 |
| 源板S的DAC动态真值 | 有准备与历史排查记录 | 已改用SKX模拟器，不把弃用工装列为当前已完成能力 |

以上是后续工作清单，不因本轮仓库合并自动启动设备、部署、标定或长测。结项可以接受已明确的工程限制，但展示材料应按上述范围表述。

### 6.1 对R65时间上界的最终审查意见

R65将“断电≤20s清空”由执行回执的UNKNOWN改为基于上界推定的PASS。其逻辑是最后消息后15s进入网关STALE，再加网络延迟与采样间隔，约17s。这个估计有价值，但设备断电后**已发送的在途或缓存消息仍可能到达**。没有独立界定网络尾延迟时，约17s不能作为任何网络条件下的硬上界。

因此最终材料保留：“历史PI基于现场时序估计判PASS；本轮确认相应STALE/清空实现与记录，没有新增精确断电计时”。上电≤90s也应注明由历史时间区间推定，精确耗时仍未知。这个证据限制不否定已观察到的实际清空、复电不重播和喇叭功能。[R64原始回执][az3]、[R65推定][r65]

---

## 7. 可用于答辩与面试的八个技术难点

建议每个回答遵循同一顺序：**具体症状 → 定位证据 → 选择与实现 → 量化结果 → 未覆盖边界**。下列口述示例可按个人实际参与范围调整；不要把团队协作成果全部改称个人独立完成。

### 7.1 出口吞吐为什么不足，为什么不是简单加波特率或RTOS

**难点。** 五路源端持续输入，出口约8.08批/s，长期低于约10.45批/s；积压最终表现成过期、回放或丢弃。串口标称波特率看似足够，但它没有反映逐字节回调与每包AT往返成本。

**解决。** 用DWT周期计数器分解service、发送、TXE等待和接收开销，结合Host敏感性扫描与实板结果选择115200 SSL透传；保留单一网络所有者和有界服务，减少每包控制交互。[R6][r6]、[W3][w3]

**口述示例：**

> 我们遇到的瓶颈是持续输入约10.45批每秒，出口只能送出约8.08批。最初考虑提高波特率，但测量发现业务回调和AT逐包往返占用了很大比例。我们用DWT把热路径分段计时，再切换到115200透传。工作段达到10.458批每秒，队列高水位6/24且没有丢弃。结论是当前输入负载可以跟上，但没有把短窗口结果写成长期极限容量。

**常见追问。** 批/s为何不能代替字节/s？DWT包含式区间为什么不能直接相加？为什么142s工作段和150s整窗分别报告？增加RTOS为什么不会自动消除串口协议开销？

### 7.2 怎样在192KiB总SRAM条件下设计断网保留

**难点。** 全波形、标量、状态的体量不同，不能一律放进同一种“大帧队列”。普通SRAM还要给运行对象、堆栈和DMA留空间，CCM也不是无限缓存。

**解决。** 把标量/状态压成28B项，CCM放1,472标量和736状态；实时优先，回放以确认驱动释放；波形尽力保留，保持源时间和REPLAY语义。[保留定义][router]、[S3][s3]

**口述示例：**

> 我们先按数据类别算内存，而不是直接承诺全波形无损。标量价值高、体积小，所以用28字节的紧凑项保存，波形保持有界缓存。203秒断网窗口中五路标量共1,030条全部到达，零重复、保序。代价是1,239条积压排空用了676秒，没有达到原390秒目标；另外SNTP恢复过慢时也会超过保留期。我们把这些条件明确写进了能力边界。

**常见追问。** 为什么状态仅本地留存？为什么610s时间锚不等于610s缓存？QoS1确认为什么不是网页已经收到？

### 7.3 采集与算法为什么要解耦，通道为什么要分别判有效

**难点。** 只在主循环读取ADC会被屏幕等任务延迟；RESP削顶又曾触发ECG一起失效，导致两个不同原因被混成“芯片读不到心电”。

**解决。** 中断取原始帧，FIFO交给主循环，保留时间和序号；BIO_V2逐通道评估，输出无效原因位。采集完整、算法有效、名义速率和医学精度分别验收。[矩阵][matrix]、[算法][alg]

**口述示例：**

> 我们把问题拆成采集和算法两层。DRDY中断及时读取9字节帧放入128帧FIFO，主循环再处理；这样可以区分ADC是否连续和算法是否输出有效值。算法方面，RESP削顶只清RESP，不再连带清掉ECG，并保存具体无效原因。后来ECG和RR分别通过多档模拟器窗口，但我们没有把分窗通过包装成同窗双有效或临床精度通过。

**常见追问。** FIFO满怎么办？为什么不能用主循环处理时刻作为采集时刻？VALID与数值可信有什么区别？

### 7.4 双CANopen、多节点和时间语义怎样统一

**难点。** 从A/B/C到五板拆分，传感器归属、节点号、PDO、心跳和时间戳必须一起迁移；否则网页看起来有数据，也可能读的是旧节点或旧会话。

**解决。** 两段独立500kbit/s经典CAN，C各自运行协议实例，固定对象字典和源身份；使用TIME、采集tick、seq/epoch/boot识别新鲜度、重启和回放。修复IRQ初始化顺序、自动重传和同COB-ID发送顺序。[B-PRECAN][precan]、[五板修复][five-fix]、[双CAN实现][can]

**口述示例：**

> 五板不是把线并起来就完成了。我们明确A/E在C.CAN1、B/D在C.CAN2，两段都是500kbit/s；C只汇聚业务数据，不跨段转发CAN帧。节点身份、对象字典、时间和重启代次统一后，云端才能判断一条值属于哪个源、是不是旧会话。实际修复过CAN中断在应用未就绪时进入，以及同COB-ID多邮箱发送顺序的问题。

**常见追问。** CAN ACK、CANopen心跳、MQTT PUBACK各证明哪一层？为什么两段控制器编号不必相同？终端40Ω测试通过为何仍有物理裕量问题？

### 7.5 不知道字节级根因时，怎样仍把系统做得可恢复

**难点。** Broker报协议错误，发送侧计数正常；没有UART抓取器，无法把ESP内部或线路行为完整还原。若只把重试次数做成三次，反复网络问题又会导致永久停传。

**解决。** 保留未知根因，增加显式退出/重入、长退避、停滞时的波形节流；把网络可恢复失败与本地不可恢复异常分开。将“影响已缓解”和“根因已关闭”分开报告。[R33][r33]、[R36][window2]

**口述示例：**

> 这个问题我们没有声称已经定位到ESP内部某个字节。现有证据只说明Broker收到过协议错误，MCU本地的短写、超时和重入计数没有异常。我们一方面保留故障证据，另一方面把第三次就停止的策略改成长退避恢复，并在ACK停滞时限制波形灌入。这样提升了可用性，但自然断链发生率是否下降还需要更长窗口，不能靠几十分钟无故障就宣布根治。

**常见追问。** TLS完整性为什么不能证明组包正确？为什么重试必须退避？哪些错误应该继续重试，哪些必须停止？

### 7.6 云端播报怎样避免旧值、重复和阻塞

**难点。** 页面显示值、浏览器朗读和板载喇叭是不同路径。网络重连后旧消息可能重复到达；复杂语音流程也可能拖慢遥测。

**解决。** 云端只用当前会话新鲜LIVE数据，按持续窗口生成确定性文本；MPB1携带issued_ms、15s TTL和长度，MQTT QoS1非retain；C用3槽队列，接收与播放前验证过期，每次服务有界。TW-TTS承担语音合成。[播报规则][broadcast]、[MPB1交付][az1]、[C实现][tts]

**口述示例：**

> 我们把正式语音功能收敛成小文本播报，而不是在网关里运行模型。云端先验证数据新鲜度和来源，再生成规则文本。下行帧带时间和15秒有效期，C还会在播放前再检查一次；队列只有三槽，每轮最多推进少量UART字节，避免影响采集上传。浏览器朗读和板载TTS各自验证，最后由现场确认听到TEMP和HR播报。

**常见追问。** QoS1为什么仍要去重？C重启后去重状态怎样处理？为什么后端重启可能重新播报？

### 7.7 固件、配置和回退怎样分开管理

**难点。** 固件升级不能意外擦掉热点/身份配置；构建环境差异又使相同源码不一定产出相同镜像。一次sector3写入预算估算错误曾导致停在提交字之前。

**解决。** boot、代码、配置分区，固定工具链和输入；写前预算检查，最后提交字标记配置完整性；安装后核对实际写入范围和保留区域。[R50][flash-fix]、[R51][flash-recover]、[R62][az1]、[R64][az3]

**口述示例：**

> 我们把应用和配置分开，正式升级只写sector0与sector4，sector3保留。曾经因为把预算判断放在擦写后，配置在提交前停止；随后改成写前判断，并用只补一个提交字的方式恢复。构建还固定了GNU工具链和库输入，避免把Windows与Linux的库差异当成源码差异。回退对象、备份和实际演练范围分别记录，不把“有备份”自动算作“全部恢复已验证”。

**常见追问。** 为什么提交字最后写？电源中断后如何识别完整配置？镜像相同和ELF容器相同是不是一回事？

### 7.8 如何证明测试没有把错误“测没了”

**难点。** 调试器读取、跨槽快照、WebSocket测试关闭和人工等待都曾污染观察结果；旧合同与新实现的边界又可能不一致。

**解决。** 保留原生返回和失败记录，按层对账，明确测量时钟；测试夹具关闭竞态单独修复，90s旧断言与已冻结运行规则统一；每一项PASS写明对象和分母。[MEM-AP][memap]、[WS修复][ws-fix]、[R54][r54]

**口述示例：**

> 我们不把一个PASS当成整个系统通过。比如SEND OK只说明串口/模块层终态，PUBACK也不等于网页实收；模拟器通过不等于真人通过。还遇到过WebSocket测试结束时的取消异常，最后证明并修复的是测试清理时序。原失败没有删除，新结果有新的条件和记录。这个方法让问题能复核，也能避免为了好看的结论去改验收口径。

**常见追问。** 为什么必须保留失败窗口？如何区分工具错误与被测系统错误？没有精确开关时间时哪些结论只能给区间？

---

## 8. 对原问题汇总的统一纠错

| 原表述/容易误读的状态 | 本次统一口径 |
| --- | --- |
| WebSocket `CancelledError`仍为UNKNOWN | 后续d30f7e7和R54/R55已关闭测试时序问题；本轮回归未复现 |
| HR喇叭内容还没逐条确认 | R65§6负责人补充已经确认，关闭该缺口；无带声录像仍保留 |
| 非人工断链共9次 | 累计9次，含与人工动作邻近且先后不确定的事件；无人操作稳态也出现过 |
| 已证实TLS前字节被破坏、STM32完全干净 | 有协议错误/畸形载荷与本地诊断证据，线上逐字节完整性UNKNOWN；不能武断归因ESP或完全排除发送应用 |
| 断电≤17s是精确实测 | 历史时序推定，含网络尾延迟假设；真实拨开关秒数未独立记录 |
| 断网无损覆盖所有数据 | 限定场景五路标量完整；状态仅本地、波形尽力，恢复超保留期会丢失 |
| W3全窗10.458批/s且0丢弃 | 这是142s工作段；150s全窗含收尾，速率9.900且尾部有丢弃/顶替；后续300s稳态另有证据 |
| RR名义矩阵通过，所有旧RR15失败可关闭 | 不同窗口、阶段、输入和固件分别判断，旧失败继续保留 |
| FreeRTOS已使用/必然放不下 | 正式裸机；不引入是当前分区与工程取舍，不是芯片绝对能力结论 |
| 当前五板仍有录音→AI→TTS完整并发 | 历史台架能力；正式WP-AZ为`--no-audio`加独立TTS播报 |
| 页面仍是七子页加总览 | 最终Claude UI为overview/trends/ai三路由；早期页面结构是历史版本 |
| 两次未解释复电可能是他人操作 | R57负责人已确认手动操作，不继续保留为未知安全事件 |
| 2025-11-02语音台架 | 当前证据路径对应2026-11-02；原记录保留，新文档统一正确年份 |
| Security Gate失败等于扫描查出漏洞 | 已知运行jobs=0，配置非法；本轮只修工作流，不执行扫描、不宣称安全通过 |

纠错依据：[R54][r54]、[R55][r55]、[R57][r57]、[R33][r33]、[W3][w3]、[R65][r65]、[UI代码][ui-tree]、[历史工作流运行][workflow-run]。

---

## 9. 本轮验证记录与审查局限

| 对象 | 本轮结果 | 能证明什么 |
| --- | --- | --- |
| Codex基线 + Claude UI本地预合并 | 无冲突 | 内容可整合，不等于自动证明功能正确 |
| 固件统一Host矩阵 | **32/32组编译与运行通过** | 真实Router/CANopen/coreMQTT与替身的集成；包含恢复、保留、正式云、TTS |
| Web单元测试 | **28 passed** | 状态、AI、报警、演示、播报等软件逻辑 |
| Web生产构建 | **PASS** | TypeScript检查与Vite构建 |
| Web默认正式/隔离五板档 | 两档**PROFILE_PASS** | 默认正式GW-C与隔离GW-B5入口配置 |
| 后端默认档 | **108 passed / 6 skipped** | 默认软件回归；跳过项需独立five进程 |
| 后端five定向修复前 | **64 passed / 1 failed** | 暴露90s旧测试断言 |
| 后端five定向修复后 | **65 passed** | 断言与已有严格TTL逻辑一致 |
| AI网关受影响路径 | **2 passed / 48 deselected** | 显式正式配置与默认隔离授权，进程内合成数据 |
| 既有普通CI入口 | coreMQTT42项、完整性6项、EMCY5项、CAN12+11+17项均通过；canonical41条/11种流 | 固定输入下主机协议及跨语言解析，不等于新增实板验收 |
| Security工作流 | 静态配置检查通过 | YAML、上下文位置、原触发/权限/步骤保留；没有执行扫描 |

本轮Host环境为GCC14.2.0、Python3.12.14；前端Node24.22.1，后端运行依赖按锁文件安装。ARM位级复现、真人窗口、现场声音和云部署均引用历史记录，不冒称本轮重新执行。原始真人数据不被复制到结项报告。

本轮没有重新运行全部历史测试、长期浸泡、硬件故障注入、烧录、生产部署或Security Gate。判断重点是当前集成对象与明确风险；这既保留了现有硬件基线，也避免把无关旧实验作为新验收重复计算。

---

## 10. 仓库合并、分支清理与恢复索引

### 10.1 范围与处理办法

初始盘点为 **41个远端分支、496个可达提交、2个既有标签、0个开放PR**；默认分支 `main` 仍停在 `5069904` 的早期合同阶段。6个既有PR均已关闭，其中4个已合并到历史P4路线，另外2个关闭但未合入main。当前可维护成果必须重新集中到main，不能仅删除分支名称。

本轮候选以 `codex/field01-preflight@7c94cc1` 为运行代码基底，真正合入 Claude UI 与 Claude PI 的独立提交。原41条分支中，**33条可达于集成候选，8条为独立历史路线**。后8条不把旧代码强行混入当前固件；其所有提交通过逐分支归档标签保留。

<!-- GOVERNANCE_RESULT_START -->
**远端执行状态：本地审查和合并候选已完成，正在执行PR合并与归档清理。** 最终状态会在本节及[执行回执](CLEANUP-RECEIPT.json)更新；当前文字不代表远端删除已经完成。
<!-- GOVERNANCE_RESULT_END -->

归档名统一为 `archive/20261112/<原分支名>`，包括原main。先建立并取回核对所有归档引用，再删除已核对的分支；删除使用每条分支的精确SHA约束和原子推送。若分支被其他人更新、仓库保护拒绝，或出现未盘点的新分支，保留相应内容并报告，不关闭保护、不强行覆盖。已有两个标签保持不变。

### 10.2 逐分支清单

下表覆盖初始41条分支。完整SHA与归档标签见[机器可读清单](BRANCH-INVENTORY.json)；提交链接固定到原始对象，删分支后仍可通过已保全的标签追溯。

| 原分支 | 原始提交 | 整理决定 |
| --- | --- | --- |
| `A` | [3fa14b00](https://github.com/Serendipity-min/medical-multi-parameter-monitor/commit/3fa14b00a0823d2855e9dd8bd1c6c8545abb8dc5) | 独立历史归档；不合旧运行代码，归档后删除原分支 |
| `B` | [f8c99433](https://github.com/Serendipity-min/medical-multi-parameter-monitor/commit/f8c99433561b2e110c04ba9fb33c30235910a3e9) | 成果已纳入主线；归档后删除原分支 |
| `B2` | [2ca744d2](https://github.com/Serendipity-min/medical-multi-parameter-monitor/commit/2ca744d2f06d49711863968aeef15b64891edd18) | 成果已纳入主线；归档后删除原分支 |
| `P4` | [67f5f57b](https://github.com/Serendipity-min/medical-multi-parameter-monitor/commit/67f5f57bd82c6e326e9e78ec9540481c80105e5f) | 成果已纳入主线；归档后删除原分支 |
| `P5-coremqtt-baremetal` | [88a993cb](https://github.com/Serendipity-min/medical-multi-parameter-monitor/commit/88a993cb2dad828d2d13438445a67324e10f71d0) | 成果已纳入主线；归档后删除原分支 |
| `audit/b5-r5qc-r6p0-20261030` | [8954c8ea](https://github.com/Serendipity-min/medical-multi-parameter-monitor/commit/8954c8ea96af1eda99f00b927f19fecab3cc3215) | 成果已纳入主线；归档后删除原分支 |
| `audit/b5-r6-p0b-20261030` | [64d07ff3](https://github.com/Serendipity-min/medical-multi-parameter-monitor/commit/64d07ff33e2fddb46a4a0570d9abfa83adbc3e02) | 成果已纳入主线；归档后删除原分支 |
| `audit/b5-r6-rr15-offline-causal-20261030` | [b9b17a76](https://github.com/Serendipity-min/medical-multi-parameter-monitor/commit/b9b17a7657f101e8901a24115da8538becc420d0) | 成果已纳入主线；归档后删除原分支 |
| `audit/codex-b5-r6-p1b0-20261030` | [98bd1f86](https://github.com/Serendipity-min/medical-multi-parameter-monitor/commit/98bd1f86d8e1cbf3b764a0876142a888b8837343) | 成果已纳入主线；归档后删除原分支 |
| `audit/codex-b5-r6-takeover-20261030` | [9f5a6641](https://github.com/Serendipity-min/medical-multi-parameter-monitor/commit/9f5a6641fec2bcdb575f5f9ff549b8e9b0223820) | 成果已纳入主线；归档后删除原分支 |
| `claude/cloud-ui-v2` | [1945c9cc](https://github.com/Serendipity-min/medical-multi-parameter-monitor/commit/1945c9cc7273e352a5f3d219c8d7a3fdc99d5e19) | 成果已纳入主线；归档后删除原分支 |
| `claude/project-review-v1` | [01df885e](https://github.com/Serendipity-min/medical-multi-parameter-monitor/commit/01df885ebdb3ee1ac874a562a60ac301a4eb3b04) | 成果已纳入主线；归档后删除原分支 |
| `codex/abc-two-group-integration-20261031` | [e1274b33](https://github.com/Serendipity-min/medical-multi-parameter-monitor/commit/e1274b337e2b8393b315409cc5d030a83658b129) | 成果已纳入主线；归档后删除原分支 |
| `codex/abc-voice-appliance-v1` | [12d3161b](https://github.com/Serendipity-min/medical-multi-parameter-monitor/commit/12d3161b59fb88d9c9fed01b26d601df69c25b2a) | 独立历史归档；不合旧运行代码，归档后删除原分支 |
| `codex/b5-m1-ecg60-stop-gate-20261031` | [cba0bcfe](https://github.com/Serendipity-min/medical-multi-parameter-monitor/commit/cba0bcfeead7c0c0c38dd4046538b82ddf151722) | 成果已纳入主线；归档后删除原分支 |
| `codex/b5-m1-rr-batch15-owner-20261031` | [010706e2](https://github.com/Serendipity-min/medical-multi-parameter-monitor/commit/010706e2b196b59e489c2dfde557301dae0d0337) | 成果已纳入主线；归档后删除原分支 |
| `codex/b5-r6-ecg-temp-20261030` | [e24e9705](https://github.com/Serendipity-min/medical-multi-parameter-monitor/commit/e24e9705a31ed9c2237ed38dd6bc843b6ffaa45c) | 成果已纳入主线；归档后删除原分支 |
| `codex/b5-r6-rr15-causal-candidate-20261030` | [eda6e24a](https://github.com/Serendipity-min/medical-multi-parameter-monitor/commit/eda6e24a8eedcfe0b50416390022db0c187550af) | 成果已纳入主线；归档后删除原分支 |
| `codex/b5-rr15-source-truth-a0-20261030` | [6669a855](https://github.com/Serendipity-min/medical-multi-parameter-monitor/commit/6669a855662f0655fc7d7b6fc4c9a45ee1ef13b0) | 成果已纳入主线；归档后删除原分支 |
| `codex/c-inmp441-voice-20261102` | [be552179](https://github.com/Serendipity-min/medical-multi-parameter-monitor/commit/be552179d77b21132d0027ff757e5db60959713f) | 成果已纳入主线；归档后删除原分支 |
| `codex/c-voice-cloud-20261022` | [ba61ae2c](https://github.com/Serendipity-min/medical-multi-parameter-monitor/commit/ba61ae2c97204f240d8fa6f316eb700aff70d29e) | 独立历史归档；不合旧运行代码，归档后删除原分支 |
| `codex/field01-egress-probe` | [84e4791d](https://github.com/Serendipity-min/medical-multi-parameter-monitor/commit/84e4791d9e4273d9bf0abe3982dd7addacb6165e) | 成果已纳入主线；归档后删除原分支 |
| `codex/field01-preflight` | [7c94cc1c](https://github.com/Serendipity-min/medical-multi-parameter-monitor/commit/7c94cc1ceb83b1f00097272563e30f6b17a9b616) | 成果已纳入主线；归档后删除原分支 |
| `codex/final-system-20261102` | [baccc7bc](https://github.com/Serendipity-min/medical-multi-parameter-monitor/commit/baccc7bc6ca2a14da6779664eead919a3240ccf4) | 成果已纳入主线；归档后删除原分支 |
| `codex/final-unified-c-runtime` | [c0b36430](https://github.com/Serendipity-min/medical-multi-parameter-monitor/commit/c0b36430cb8262147b2249d18d889892d3c7b0fa) | 成果已纳入主线；归档后删除原分支 |
| `codex/five-appliance-integration-v1` | [4616c30f](https://github.com/Serendipity-min/medical-multi-parameter-monitor/commit/4616c30f03b00ad6bf47527a525b6f029de2143d) | 成果已纳入主线；归档后删除原分支 |
| `codex/five-node-single-module-v1` | [f9bdff8a](https://github.com/Serendipity-min/medical-multi-parameter-monitor/commit/f9bdff8a6d73993390baf59abc8a52bdc992f16c) | 成果已纳入主线；归档后删除原分支 |
| `codex/m0-abc-unified-baseline-20261103` | [26e695ff](https://github.com/Serendipity-min/medical-multi-parameter-monitor/commit/26e695ffda43a7a76aa54d1c4e3a5631ac0dc42e) | 成果已纳入主线；归档后删除原分支 |
| `codex/node-b-bio-v2-field-20261022` | [bb9bc8e0](https://github.com/Serendipity-min/medical-multi-parameter-monitor/commit/bb9bc8e00860ff4f61fa3c4f315edfb76815a59b) | 成果已纳入主线；归档后删除原分支 |
| `codex/node-b-bio-v2-test-20261022` | [c0617b9f](https://github.com/Serendipity-min/medical-multi-parameter-monitor/commit/c0617b9fc0ee1f1c6b2f3c4ece90b36db7a78740) | 成果已纳入主线；归档后删除原分支 |
| `codex/node-b-precan-closeout-20261023` | [9988d37c](https://github.com/Serendipity-min/medical-multi-parameter-monitor/commit/9988d37cd5470d6857bb535aab1d821cf2581302) | 成果已纳入主线；归档后删除原分支 |
| `codex/node-b4-dualbus-software-20261023` | [ffa440b3](https://github.com/Serendipity-min/medical-multi-parameter-monitor/commit/ffa440b31b8b4993967f0e9aef1b3071a0d1dcfe) | 成果已纳入主线；归档后删除原分支 |
| `codex/node-b5-cloud-integration-20261026` | [2854d358](https://github.com/Serendipity-min/medical-multi-parameter-monitor/commit/2854d3581658a91d65c1aa30d827ff489ff0f081) | 成果已纳入主线；归档后删除原分支 |
| `codex/p5-c3a-diagnostic` | [38ccef7f](https://github.com/Serendipity-min/medical-multi-parameter-monitor/commit/38ccef7fd7e265b848880dd2ca1015ca3f3a7099) | 独立历史归档；不合旧运行代码，归档后删除原分支 |
| `codex/pi-r1-offline-fixes` | [78a6d00f](https://github.com/Serendipity-min/medical-multi-parameter-monitor/commit/78a6d00f53ecd6e442c9ea76165a74cfb042289f) | 成果已纳入主线；归档后删除原分支 |
| `dev/h3-nodea-cloud-ai-integration` | [a5cdd5b0](https://github.com/Serendipity-min/medical-multi-parameter-monitor/commit/a5cdd5b0b1ad48108fd631136e9de69e30582f2d) | 独立历史归档；不合旧运行代码，归档后删除原分支 |
| `dev/node-a-v07` | [dab0b3de](https://github.com/Serendipity-min/medical-multi-parameter-monitor/commit/dab0b3de78a8c76efb48593eb8a164a13663e422) | 独立历史归档；不合旧运行代码，归档后删除原分支 |
| `dev/node-b-v07` | [ce84b33b](https://github.com/Serendipity-min/medical-multi-parameter-monitor/commit/ce84b33b705403775790d4723978d586aeb877a4) | 独立历史归档；不合旧运行代码，归档后删除原分支 |
| `dev/p6-cloud-ai-text-tts-v1` | [1a5d7d16](https://github.com/Serendipity-min/medical-multi-parameter-monitor/commit/1a5d7d16a1df00a1195a6754c35d33f4380324a6) | 独立历史归档；不合旧运行代码，归档后删除原分支 |
| `main` | [50699048](https://github.com/Serendipity-min/medical-multi-parameter-monitor/commit/50699048010c57ba10f8573461844c525b022a07) | 保留为唯一主入口；旧头另行归档 |
| `patch/b5-r6-patch01-20261030` | [01864fb4](https://github.com/Serendipity-min/medical-multi-parameter-monitor/commit/01864fb4c1ea35c9da38aa98b1e85790d2ed5415) | 成果已纳入主线；归档后删除原分支 |

### 10.3 八条独立历史路线为何不继续占用活跃分支

| 分支 | 内容检查与归档理由 |
| --- | --- |
| `A` | Node-A早期支线，后续H3与五板实现已吸收或替代；保留原采集证据。 |
| `codex/abc-voice-appliance-v1` | 三板音频方案及失败记录；年龄修复已存在当前代码，旧调度不适用于正式no-audio透传。 |
| `codex/c-voice-cloud-20261022` | 早期单板云语音/H3恢复证据；正式主链已有更新实现。 |
| `codex/p5-c3a-diagnostic` | 绑定旧P4/P5对象的诊断覆盖层；不作为当前生产修复重新合并。 |
| `dev/h3-nodea-cloud-ai-integration` | 旧单总线physical_can与H3阶段代码；当前使用dual_can/b4_*。 |
| `dev/node-a-v07` | 旧node_a路径；归一后149文件相同、15文件已更新，仅早期README/批处理独立保留。 |
| `dev/node-b-v07` | 早期合同与状态材料，无待集成的当前运行修复。 |
| `dev/p6-cloud-ai-text-tts-v1` | 旧P6V1语音、模型试验与诊断；正式WP-AZ使用独立MPB1规则播报。 |

这不是把8条路线判为没有价值。其价值分别是早期协议选择、原始硬件记录、失败复现、回退与阶段演进；用归档标签更适合保存这些成果。A→H3→旧云语音之间还存在祖先关系，不应把“分支数”理解为相同数量的独立实现。

### 10.4 本轮进入统一仓库的修正

- [WebAI](../../cloud/ai/app.py)：支持显式 `P6_GATEWAY_IDS=GW-C-001`，默认仍隔离；相关授权与D/E来源用例补齐。
- [NIBP测试](../../cloud/backend/tests/test_five_node.py)：精确90s应过期，测试跟随已有生产逻辑。
- [普通CI](../../.github/workflows/phase1.yml)：push/PR对齐main、使用当前coreMQTT普通回归，加入five档与正式网关定向检查。
- [Security工作流](../../.github/workflows/security-gate.yml)：仅修非法上下文位置，保留人工触发和授权检查；没有启动扫描。
- [根README](../../README.md)：以最终五板、三路由、实际固件技术为入口；历史章节只增加阶段标识，不抹去旧证据。

本轮[离线验证记录](VALIDATION.json)与GitHub PR/工作流共同记录代码验证；设备和线上服务仍以R65历史部署身份为准。

### 10.5 如何恢复某条旧分支

```bash
git fetch origin --tags
git switch -c restore-field01 archive/20261112/codex/field01-preflight
```

其他分支同理替换为清单中的标签。恢复本地分支只用于阅读或继续开发，不自动授权旧固件烧录、服务器替换或安全扫描。

### 10.6 Issue与安全状态

初始开放Issue有两条：#8是早期FIELD01诊断任务，后续已发展为R1–R65工作链，应按后续证据标记阶段收尾，并保留原音频分项等未执行边界；#7记录的六项精确Gitleaks误报接受已在2026-11-08到期，本轮不续期、不将过期例外宣称为当前安全通过，该事项保留待维护。仓库结构整理完成不代表全项目Security Gate或医疗安全验收完成。

---

## 证据索引

以下链接固定到审查时的完整提交，不因删除旧分支而改变指向。第10节应补充本轮最终整合提交和归档映射。

[age]: https://github.com/Serendipity-min/medical-multi-parameter-monitor/blob/7c94cc1ceb83b1f00097272563e30f6b17a9b616/node-a/STM32F407_HOSPITAL/HARDWARE/CANopen/node_policy.h
[ai-before]: https://github.com/Serendipity-min/medical-multi-parameter-monitor/blob/7c94cc1ceb83b1f00097272563e30f6b17a9b616/cloud/ai/app.py
[alg]: https://github.com/Serendipity-min/medical-multi-parameter-monitor/blob/7c94cc1ceb83b1f00097272563e30f6b17a9b616/node-b/docs/B-ALG-002-FINAL-HANDOFF.md
[ax]: https://github.com/Serendipity-min/medical-multi-parameter-monitor/blob/7c94cc1ceb83b1f00097272563e30f6b17a9b616/node-b/docs/PI-REVIEW/R41-WP-AX-OFFLINE-20261111.md
[az1]: https://github.com/Serendipity-min/medical-multi-parameter-monitor/blob/7c94cc1ceb83b1f00097272563e30f6b17a9b616/node-b/docs/PI-REVIEW/R62-WP-AZ-AZ0-AZ1-RECEIPT-20261112.md
[az3]: https://github.com/Serendipity-min/medical-multi-parameter-monitor/blob/7c94cc1ceb83b1f00097272563e30f6b17a9b616/node-b/docs/PI-REVIEW/R64-WP-AZ-AZ2-AZ3-RECEIPT-20261112.md
[broadcast]: https://github.com/Serendipity-min/medical-multi-parameter-monitor/blob/7c94cc1ceb83b1f00097272563e30f6b17a9b616/cloud/backend/app/broadcast.py
[build]: https://github.com/Serendipity-min/medical-multi-parameter-monitor/blob/7c94cc1ceb83b1f00097272563e30f6b17a9b616/gateway/dual_can/build_arm.py
[can]: https://github.com/Serendipity-min/medical-multi-parameter-monitor/blob/7c94cc1ceb83b1f00097272563e30f6b17a9b616/gateway/dual_can/b4_gateway.c
[cold]: https://github.com/Serendipity-min/medical-multi-parameter-monitor/blob/7c94cc1ceb83b1f00097272563e30f6b17a9b616/node-b/docs/PI-REVIEW/R40-COLD-STOP-REVIEW-20261111.md
[core]: https://github.com/Serendipity-min/medical-multi-parameter-monitor/blob/7c94cc1ceb83b1f00097272563e30f6b17a9b616/gateway/third_party/coreMQTT/README.md
[disconnect]: https://github.com/Serendipity-min/medical-multi-parameter-monitor/blob/7c94cc1ceb83b1f00097272563e30f6b17a9b616/node-b/docs/PI-REVIEW/R27-DISCONNECT-OFFLINE-20261110.md
[five-field]: https://github.com/Serendipity-min/medical-multi-parameter-monitor/blob/7c94cc1ceb83b1f00097272563e30f6b17a9b616/node-b/docs/FIVE-NODE-MIGRATION/FIELD01-20261106/RESULTS.md
[five-fix]: https://github.com/Serendipity-min/medical-multi-parameter-monitor/commit/e8804f8a8092a38a8a5ff9be2f7162dfbcd091e3
[five-test]: https://github.com/Serendipity-min/medical-multi-parameter-monitor/blob/7c94cc1ceb83b1f00097272563e30f6b17a9b616/cloud/backend/tests/test_five_node.py
[flash-fix]: https://github.com/Serendipity-min/medical-multi-parameter-monitor/blob/7c94cc1ceb83b1f00097272563e30f6b17a9b616/node-b/docs/PI-REVIEW/R50-WP-AY0-B-F2C-OFFLINE-RECEIPT-20261112.md
[flash-recover]: https://github.com/Serendipity-min/medical-multi-parameter-monitor/blob/7c94cc1ceb83b1f00097272563e30f6b17a9b616/node-b/docs/PI-REVIEW/R51-WP-AY0-B-RECOVERY-RECEIPT-20261112.md
[formal]: https://github.com/Serendipity-min/medical-multi-parameter-monitor/blob/7c94cc1ceb83b1f00097272563e30f6b17a9b616/node-b/docs/PI-REVIEW/R52-WP-AY0-S3-PUBLIC-VIEW-RECEIPT-20261112.md
[handoff]: https://github.com/Serendipity-min/medical-multi-parameter-monitor/blob/7c94cc1ceb83b1f00097272563e30f6b17a9b616/node-b/docs/FIVE-APPLIANCE-20261107/FIRMWARE-SDK-ESPAT-HANDOFF-20261109.md
[hub]: https://github.com/Serendipity-min/medical-multi-parameter-monitor/blob/7c94cc1ceb83b1f00097272563e30f6b17a9b616/cloud/backend/app/hub.py
[local-only]: https://github.com/Serendipity-min/medical-multi-parameter-monitor/blob/7c94cc1ceb83b1f00097272563e30f6b17a9b616/node-b/docs/PI-REVIEW/R35-WP-AW-LOCAL-ONLY-20261111.md
[matrix]: https://github.com/Serendipity-min/medical-multi-parameter-monitor/blob/7c94cc1ceb83b1f00097272563e30f6b17a9b616/node-b/docs/04_证据矩阵与后续路线.md
[memap]: https://github.com/Serendipity-min/medical-multi-parameter-monitor/blob/7c94cc1ceb83b1f00097272563e30f6b17a9b616/node-b/docs/B5-MEMAP-SDK-ERROR-CAUSE-AUDIT.md
[policy]: https://github.com/Serendipity-min/medical-multi-parameter-monitor/blob/7c94cc1ceb83b1f00097272563e30f6b17a9b616/gateway/b5/b5_policy.c
[precan]: https://github.com/Serendipity-min/medical-multi-parameter-monitor/blob/7c94cc1ceb83b1f00097272563e30f6b17a9b616/node-b/docs/B-PRECAN-CLOSEOUT-FINAL-HANDOFF.md
[preflight]: https://github.com/Serendipity-min/medical-multi-parameter-monitor/blob/7c94cc1ceb83b1f00097272563e30f6b17a9b616/node-b/docs/PI-REVIEW/PREFLIGHT-ARCHITECTURE-20261109.md
[r21]: https://github.com/Serendipity-min/medical-multi-parameter-monitor/blob/7c94cc1ceb83b1f00097272563e30f6b17a9b616/node-b/docs/PI-REVIEW/R21-S1B2-FIELD-20261110.md
[r22]: https://github.com/Serendipity-min/medical-multi-parameter-monitor/blob/7c94cc1ceb83b1f00097272563e30f6b17a9b616/node-b/docs/PI-REVIEW/R22-AR-FIELD-20261110.md
[r25]: https://github.com/Serendipity-min/medical-multi-parameter-monitor/blob/7c94cc1ceb83b1f00097272563e30f6b17a9b616/node-b/docs/PI-REVIEW/R25-OFFLINE-20261110.md
[r33]: https://github.com/Serendipity-min/medical-multi-parameter-monitor/blob/01df885ebdb3ee1ac874a562a60ac301a4eb3b04/node-b/docs/PI-REVIEW/R33-20261110.md
[r48]: https://github.com/Serendipity-min/medical-multi-parameter-monitor/blob/7c94cc1ceb83b1f00097272563e30f6b17a9b616/node-b/docs/PI-REVIEW/R48-WP-AY0-B-PREWRITE-S2-RECEIPT-20261112.md
[r5]: https://github.com/Serendipity-min/medical-multi-parameter-monitor/blob/7c94cc1ceb83b1f00097272563e30f6b17a9b616/node-b/docs/PI-REVIEW/PREFLIGHT-R5-FIELD-RECEIPT-20261109.md
[r53]: https://github.com/Serendipity-min/medical-multi-parameter-monitor/blob/01df885ebdb3ee1ac874a562a60ac301a4eb3b04/node-b/docs/PI-REVIEW/R53-20261112.md
[r54]: https://github.com/Serendipity-min/medical-multi-parameter-monitor/blob/7c94cc1ceb83b1f00097272563e30f6b17a9b616/node-b/docs/PI-REVIEW/R54-WP-AY-B1-OFFLINE-RECEIPT-20261112.md
[r55]: https://github.com/Serendipity-min/medical-multi-parameter-monitor/blob/01df885ebdb3ee1ac874a562a60ac301a4eb3b04/node-b/docs/PI-REVIEW/R55-20261112.md
[r57]: https://github.com/Serendipity-min/medical-multi-parameter-monitor/blob/01df885ebdb3ee1ac874a562a60ac301a4eb3b04/node-b/docs/PI-REVIEW/R57-WAY-RUN2-CARD-20261112.md
[r6]: https://github.com/Serendipity-min/medical-multi-parameter-monitor/blob/7c94cc1ceb83b1f00097272563e30f6b17a9b616/node-b/docs/PI-REVIEW/R6-WP-PQ-OFFLINE-RECEIPT-20261109.md
[r63]: https://github.com/Serendipity-min/medical-multi-parameter-monitor/blob/01df885ebdb3ee1ac874a562a60ac301a4eb3b04/node-b/docs/PI-REVIEW/R63-20261112.md
[r65]: https://github.com/Serendipity-min/medical-multi-parameter-monitor/blob/01df885ebdb3ee1ac874a562a60ac301a4eb3b04/node-b/docs/PI-REVIEW/R65-20261112.md
[repair]: https://github.com/Serendipity-min/medical-multi-parameter-monitor/blob/7c94cc1ceb83b1f00097272563e30f6b17a9b616/node-b/docs/B5-C-REPAIR-R4-FINAL-HANDOFF.md
[router]: https://github.com/Serendipity-min/medical-multi-parameter-monitor/blob/7c94cc1ceb83b1f00097272563e30f6b17a9b616/gateway/storage/router.h
[rr]: https://github.com/Serendipity-min/medical-multi-parameter-monitor/tree/7c94cc1ceb83b1f00097272563e30f6b17a9b616/node-b/docs/CODEX-M1-RR-BATCH15-OWNER-20261031
[s3]: https://github.com/Serendipity-min/medical-multi-parameter-monitor/blob/7c94cc1ceb83b1f00097272563e30f6b17a9b616/node-b/docs/PI-REVIEW/R32-S3-FIELD-20261110.md
[stats]: https://github.com/Serendipity-min/medical-multi-parameter-monitor/blob/7c94cc1ceb83b1f00097272563e30f6b17a9b616/node-b/docs/PI-REVIEW/R43-R42-OFFLINE-STATS-20261111.md
[tls-budget]: https://github.com/Serendipity-min/medical-multi-parameter-monitor/blob/7c94cc1ceb83b1f00097272563e30f6b17a9b616/node-b/docs/PI-REVIEW/R10-W1-TLS-FIX-FIELD-RECEIPT-20261109.md
[tts]: https://github.com/Serendipity-min/medical-multi-parameter-monitor/blob/7c94cc1ceb83b1f00097272563e30f6b17a9b616/gateway/voice/tts_broadcast.c
[tts-queue]: https://github.com/Serendipity-min/medical-multi-parameter-monitor/blob/7c94cc1ceb83b1f00097272563e30f6b17a9b616/gateway/voice/tts_queue.c
[two-group]: https://github.com/Serendipity-min/medical-multi-parameter-monitor/blob/7c94cc1ceb83b1f00097272563e30f6b17a9b616/node-b/docs/CODEX-ABC-TWO-GROUP-20261031/TEST-REPORT.md
[ui-commit]: https://github.com/Serendipity-min/medical-multi-parameter-monitor/commit/1945c9cc7273e352a5f3d219c8d7a3fdc99d5e19
[ui-tree]: https://github.com/Serendipity-min/medical-multi-parameter-monitor/tree/1945c9cc7273e352a5f3d219c8d7a3fdc99d5e19/cloud/web
[voice]: https://github.com/Serendipity-min/medical-multi-parameter-monitor/blob/7c94cc1ceb83b1f00097272563e30f6b17a9b616/node-b/docs/CODEX-C-INMP441-20261102/VOICE-RESULTS.md
[w3]: https://github.com/Serendipity-min/medical-multi-parameter-monitor/blob/7c94cc1ceb83b1f00097272563e30f6b17a9b616/node-b/docs/PI-REVIEW/R12-W3-FIELD-RECEIPT-20261109.md
[window2]: https://github.com/Serendipity-min/medical-multi-parameter-monitor/blob/7c94cc1ceb83b1f00097272563e30f6b17a9b616/node-b/docs/PI-REVIEW/R36-WINDOW2-FIELD-20261111.md
[workflow-run]: https://github.com/Serendipity-min/medical-multi-parameter-monitor/actions/runs/43207125057
[ws-fix]: https://github.com/Serendipity-min/medical-multi-parameter-monitor/commit/d30f7e7ae848b7557d5071257e24760abf4ca5a7
