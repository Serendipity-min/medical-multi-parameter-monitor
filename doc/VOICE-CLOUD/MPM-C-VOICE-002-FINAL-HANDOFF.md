# MPM-C-VOICE-002 唯一权威交接报告

结论：**VOICE_CLOUD_SINGLE_PHRASE_PASS_WITH_BLOCKERS**。
2026-10-22已取得真实豆包→正式8883→C→TW-TTS的可辨短句证据。第二次负责人明确回报“清晰，能正常辨认，通过”。
完整工程Gate未通过：A已移除，新PPG300s、A/C并发实板非回归、STOP及扬声器功率门仍未通过。
试验已结束，C与云端均实际恢复原H3；没有永久新增语音发布。

## 1. 身份与授权

| 对象 | 实际身份 |
|---|---|
| 独立工作区/分支 | E:/medical-monitor-c-voice-cloud / codex/c-voice-cloud-20261022 |
| H3基线/保护HEAD | a5cdd5b0b1ad48108fd631136e9de69e30582f2d |
| 原H3 tag object | 8a9265146a293f8a020df39863943e9de4adce68，h3-ac-mock-eng-20261021-r1 |
| P6选取来源 | 1a5d7d16a1df00a1195a6754c35d33f4380324a6 |
| merge-base | 67f5f57bd82c6e326e9e78ec9540481c80105e5f |
| 实板固件源提交 | 0e204d193aa3af42e7c190bf4856380a5874821e |
| 首个云候选源提交 | 76f586ac803c52ba1435686b677ef558c24b50b7，已回退 |
| 实际发声云候选源提交 | a3e15a2ec8a56a8c0c1bebb920ac4ee7b5c1d402 |
| 实际发声云release | voice-002-a69d3749de65 |
| release manifest SHA256 | a69d3749de6504b7d9f25b7c951f98638c4a745201895ca15297e553acd41140 |
| 上传包SHA256 | 49910736f0c48eebbed88e8a237dd3a376b2bfb618b929cc8180f2f291778295 |

不整体合并两分支。只取P6驱动/队列/UART/测试，保留H3 Backend、CANopen、Router、NIBP及既有MQTT路径。
P4/main/A/B/B2/P6/H3保护分支及原tag不写；不创建PR/新tag，不运行Security Gate。
最终交付HEAD由正常推送后的仓库外DELIVERY-RECEIPT.json、远端取回核验和最终答复提供，避免报告自身commit SHA自引用。

负责人最新指令统一授权合同内步骤，后续询问仅收集现场事实。独立隔离Broker按最新指令跳过，V2为OWNER_SKIPPED。
第二份合同后续提供，B不介入。8Ω1W第一次可闻但不够清楚后，负责人另要求再发一次辨认；第二次正常重启、新许可、新请求执行。
未重放旧P6V1包，未提高音量，没有自动重试/循环。

## 2. 修改与资源

新增gateway/voice：P6V1严格解码、会话/时间/重放/频率门、单槽TTS、USART2 IRQ15、维护工具及Host负例。
仅MP_CLOUD_VOICE构建增加订阅和入站记录；官方coreMQTT处理入站PUBACK，回调内复制文本，不保存RX借用指针。
上行单在途、5000ms PUBACK、QoS0波形、CAN ISR/Router、ESP-AT/TLS/fresh SNTP、NIBP90s没有改写。
错误业务载荷只丢语音；损坏MQTT分帧/超出库512B缓冲仍走库错误路径，不声称任意洪泛下永不重连。

云端增加严格TLS/SNI精确主题发布器、2小时/3次5000Token持久预算窗；页面每次提交后撤销播报勾选。
只取本轮审核后模型完整短句≤60UTF8字节；超长不截断、不填示例、不下发。
网络字符策略取P6交集：BMP白名单、拒绝非字符/控制字/隐藏Unicode/方括号；本地TTS原合法四字节UTF8能力保留。
digest仅绑定事实，不是MAC。新授时/会话下界拒绝旧包，但不等于认证授时，仍依赖既有SNTP/TLS/ACL。

| 构建 | BIN | data | BSS（含链接预留） |
|---|---:|---:|---:|
| 原H3，最终源码再复现 | 43172B | 88B | 123136B |
| 语音合体 | 47324B | 92B | 123824B |
| 变化 | +4152B | +4B | +688B |

48KiB Flash剩1828B；128KiB SRAM扣除data+BSS后7156B，不是运行时栈高水位。
ARM队列312B、Guard168B、metrics132B、UART RX32B、MQTT入站记录4B；每次主循环最多发1B、读4B，无新增malloc。
实板C-only试验最大轮询间隔7ms；TTS/CAN/ESP原始IRQ优先级0xF0/0x10/0x00。
.su中voice_check312B、receive96B、poll24B为静态函数栈帧，没有CAN实载下完整调用链/ISR栈高水位。

## 3. 测试与原始退出码

全部原始日志、命令、源SHA与失败轮次在evidence/，不以最新通过覆盖初始失败。

| 检查 | 实际结果 | 退出码 |
|---|---|---:|
| TTS Host | 3103断言 | 0 |
| P6V1最终Host | 87检查，含会话/回退/重放/过期/1s边界/UTF8/digest非签名 | 0 |
| 真实coreMQTT混合Host | 6组：订阅负例、关闭、错topic/QoS/retain、短读上下行、重连、原5s预算 | 0 |
| P5普通与CAN/Router | 42项及CAN/Router | 0 |
| IRQ/Wi-Fi/fresh SNTP | 48项 | 0 |
| 最终Python | 342 passed、1 skipped、4 subtests passed | 0 |
| Web | 15测试及tsc/Vite构建 | 0 |
| ARM默认/语音 | 合法加载区间；默认BIN逐字节复现冻结H3 | 0 |
| 维护/云窗口负例 | 改原件、越区、错误端口、预算并发、Origin等 | 0 |

保留失败：初轮未修改Backend下出现WSS取消异常；Unicode放宽与P6测试冲突，改为协议交集；新UI状态使旧5项数量断言失败，补第6项；中间Host错误地收紧本地TTS字符能力，已撤回驱动改变，只收紧网络入口。
两次服务器只读定位误把日志wrapper当直接mosquitto，未写服务器；已按实际wrapper定位。
浏览器最初发送按钮在视口外，点击未产生请求，60s许可按设计失效；正常重启再执行，没有额外模型调用。
首个正式候选发现CORS不是服务端Origin检查，实际回退后只在新语音候选补强。原H3自身未修改。
归档元数据一次因错误cwd复制失败（退出1），加密/第二副本核验已成功，正确路径补录退出0，见归档回执。
未用清计数、延长有效期、重发或示例数值掩盖失败。

## 4. 实板与固件

当次UID与私有参考匹配，J-Link VTref均3.3V；完整64KiB双读和磁盘回读一致。
原64KiB：49d3fad5040b25b746905d5c1468bff4d5be5a4f13197286ce215e0711798fb4。
sector3 generation3/336B：395c6a36d7c4a636b34a72eacd1ccc2a2fc7f025df7089f3d94e1d2de14c5a3b。
sector7/11各128KiB：b5a41c3758763bbec72769fab4a2533bf2db0b6312d93d25a695f9e4b9e02260。
options：52d5979da03bd7be45e385920ec7d5901793bab3f6bc1daa0c1c1997f9e91687。

| 候选产物 | SHA256 |
|---|---|
| BIN 47324B | ad51f436284b314c8287df8541a94e44ba581124521807be5a6df532a130af8d |
| ELF 86304B | c2a18b793bef6c329d29a619dec7f1b89b2b81c1e665688c3acb3d0874e512cf |
| MAP 236499B | d14e7f2fb5762e2f601f928f43f4fa3aedea1b7c9faf331b635153d08d15d8dc |
| FF补齐48KiB块 | 08cfee0be69148d8bb89bec041f7cef305e3cd30cc13fa340741be228848b71b |
| 写后整个64KiB | 2a4338178eb64823d91ad06c02f273f3ab8874d33e885134fdd231e8aa7403bf |

加载[0x08000000,0x0800B8DC)，只写sector0–2至0x0800C000；sector3整区/7/11/options与控制器前后不变。
无mass erase/GO/强设入口。正常BOOT0/1 GND、J5独立供电、USB/J-Link拔除后运行；两次只读快照VTOR=0x08000000、DHCSR_HALT=false。
PA2→R、T→PA3、V/G/P3隔离由负责人核对。本轮没有独立模块功率/温升数值，历史T脚3.33V不替代本轮全面电气验收。

## 5. 真实豆包→可闻

正式第七页路径/medical-monitor/#/ai，完整地址/令牌仅在仓库外私有访问引用。
页面GW-C-001、真实监护WSS；本地WK_UP低音量v1、60s一条许可，然后页面明确提交。
A实际移除、B OFFLINE；实际C上报MOCK/OFFLINE事实，当前读数隐藏。没有人体/原波形上传或音频录制。

| 证据 | 第一次 | 第二次 |
|---|---|---|
| turn_id | 1c274f996f9941de958a5e706e99a9d3 | ebd5c1d0d7cb4e5ebf35f388ba1c74e4 |
| 模型 | doubao-seed-2-0-mini-260428 | 同左 |
| Token | 412+17=429 | 412+19=431 |
| issued UTC毫秒（C实读） | 1792652071762 | 1792652338615 |
| C估算接收UTC毫秒 | 1792652071962 | 1792652338843 |
| 本地接受/ACK/DONE tick | 52384/52437/55769 | 44139/44199/47887 |
| UART文本帧 | 50B | 56B |
| C SUBACK/接受/DONE | 1/1/1 | 1/1/1 |
| 人工反馈 | 能闻但不特别清楚，后确认能辨别关键词 | 清晰，能正常辨认，通过 |

第二次准确短句：“身体不适请及时休息，必要时就医评估”。
两次fact_digest均d68cb511a588b00a18de22f0bb8cb08c，绑定未变化的MOCK/OFFLINE事实，不是MAC。
模型未严格遵从提示的“十二字以内”，但45/51UTF8字节满足60B硬界；自然语言提示不当硬限制。
200/228ms是两时钟域估算差，不称精密单向时延；ACK/DONE相对时间来自C同一uptime。

2次API均HTTP200/VALIDATED，共860Token，在3次/5000Token内，无自动重试。费用UNKNOWN；免费/体验是负责人历史报告，不推断当前余额/账单。
网页只显示BROKER_PUBACK_ONLY。C turn/digest及模块41/4F处理计数另证，不用Broker回执替代听音。
C入站PUBACK未独立抓取线上包ID；130/56次qos1_acked是各次开机的上行监护确认，不能冒充入站确认。
UART错误/溢出/队列错误及publish_failed均0。第二次后无效探针received=2、accepted仍1、VOICE_OFF拒绝1、DONE仍1，无额外发声。
截图：evidence/real-cloud-answer.png、real-cloud-answer-second.png；逐层数据见V5-real-response*、V5-C-*-runtime、V5-model-window-usage。

## 6. 权限与实际回退

严格TLS链/SNI8883。当前C只加精确voice/reply read，临时publisher只加该topic write；两旧宽C角色仅对新voice主题加deny，原遥测权限不变。
两个云窗口均实际权限测试：publisher不能读回、C角色能读；C反向写、control写、其他Gateway写、B telemetry写均MQTT5返回135。不仅看SUBACK/PUBACK声明。
AI仅127.0.0.1:18796，只切medical-monitor静态/AI snippet。旧AI/Backend/Broker不重启；真实Origin403/无令牌401/页面200已验证。

最终恢复SHA256：

| 对象 | SHA256 |
|---|---|
| ACL | c987e3ebe5c884f214f2d334c6416804c24480de735c52b896874e6af3b09853 |
| password | ecd343ceec203afd44737f460b44aa5d23157524761a702978b3e242e50622a4 |
| Nginx snippet | 70ac6d03c17b1bcfc54ea87fb8b3fca949d8dabddac191dd7b8b571d58c00ca7 |
| C整个64KiB | 49d3fad5040b25b746905d5c1468bff4d5be5a4f13197286ce215e0711798fb4 |
| C原43172B BIN | b9b25b186c3b40d62b4a1c1919e09f27b639806271a3b20ae7fc80ea4cda1efe |

C恢复使用本窗口原48KiB，sector3/7/11/options未变；负责人最终确认原接线独立运行、TTS四线拆下、USB/J-Link拔下。
H3 runtime-b8fbb14b5c35完整manifest复核通过；旧AI2758088/Backend2758089/Broker wrapper851111/Nginx3631主PID未变。
最终HTTPS/WSS/8883正常，Gateway ONLINE、A/B OFFLINE；旧AI voice_mode=DISABLED，18796/8884无监听。
试验进程/回退定时器inactive；已删除的publisher再次认证返回135。未改安全组/防火墙。
8884仅确认主机无监听，不把历史外网闭合不确定性升级为本轮全面安全组认证。
两份试验release和root-only状态留作追溯，不是永久服务；应用回退不是全设备/全云安全组回退。

## 7. 未通过项

- 工程Gate：A移除，真实CAN RX/Boot-up/PPG为0。tx_no_ack=1、TEC8/REC0、BOFF0为缺席对端状态。没有新PPG300s或三流300s，不借旧H3窗口补足。
- BLOCKED_STOP：本轮不探测STOP/PAUSE/QUERY；旧STOP缺少4F的失败证据保留，不承诺即时静音。
- BLOCKED_POWER：8Ω1W仅获准两次v1短句，无差分功率/温升测量。连续/多句工程验证宜换≥8Ω2W或补测。
- CAN实载CPU/栈、模块断电/断线、完整网络/重启负例只有部分Host覆盖，不冒充全部实板PASS。
- Origin补强只在新语音候选，恢复后的原H3保持原行为，后续永久发布应采用已测补强。
- 第一次清晰度不足未唯一归因；串口为0错误、第二次带句读文本可辨，但没有受控声压/声学实验。
- 不创建新tag。第二份B合同待提供，B另起工作区，本结果不构成三板准入。

## 8. 归档和停止

Flash/UID/sector3/凭据/恢复原件仅仓库外受限目录，AES256加密双副本，无明文tar/口令/ARK Key入库。
完整C窗口2315335B，第二副本解密逐份核验180文件，SHA256 d64c090db2451a61eb53bd16a5fcdd7a5308a8aacf40400e7895d4e02d1d86ab。
云窗口153738B，第二副本核验44文件，SHA256 e38c6d503aebd5405465edee6664a6d3e748445b6821c9dfe59891efb8a3182a。
E盘主副本、D盘第二副本为同一电脑，不等于异地备份；密钥离线保管未独立核验。
任务浏览器会话、专属GPG agent和实板窗口已关闭。正常推送并远端取回验证后释放唯一写入租约，停止等待复核。
