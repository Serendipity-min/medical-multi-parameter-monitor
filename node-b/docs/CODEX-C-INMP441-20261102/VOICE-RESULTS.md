# Gateway-C INMP441 实测回执 · 2026-11-02

从三板基线 `e1274b337e2b8393b315409cc5d030a83658b129` 开始，在 `codex/c-inmp441-voice-20261102` 完成独立C语音台架。A/B保持断电、C两段CAN隔离；复用现有SDK安装引擎、GNU/SPL、ESP/TLS/coreMQTT及VOICE-002组件。本轮没有制作统一镜像。

| 验证层级 | 结果 | 实证 |
|---|---|---|
| MIC_LOCAL | **PASS** | 静音、实放1000Hz、连续手机语音的真实PCM/WAV；负责人确认原声可辨认 |
| MIC_ASR_UPLINK | **PASS** | C直接TLS/MQTT上行125块、64000B；源PCM、Broker重组、服务器SHA一致；真实ASR退出0，负责人确认英语片段相符 |
| MIC_CLOUD_ROUNDTRIP | **PASS** | 同session真实AI HTTP200/VALIDATED，C收到回复，TTS ACK=1/DONE=1、UART错误/溢出=0；负责人确认喇叭说出同一句话 |

成功会话为 `1793616888`。C采集16kHz、24bit/32slot左槽，转换为无额外增益的PCM16，2秒32000点；DMA双缓冲2560B，原始250个IRQ时间戳和200个连续有效块均留存，无DMA错误、覆盖或截幅。采样率由寄存器与声明HSE下的周期计数核验，未冒充独立频率计测量。

云端识别为 “plan shown in the package the premium”，真实AI回复为“已收到该测试内容”。ASR耗时36.862秒，AI耗时1269ms，实际用量387 tokens。负责人分别确认识别片段与手机内容相符、听到的是C喇叭回复。主机对C输入主题的应用发布数为0。此次验证为2秒非人体工程短句，未签发ASR准确率、长语音/VAD或三板并发能力。

详见[同会话完整回执](VOICE-OWNER-CONFIRMED-PASS.json)、[现场原生回执](VOICE-FINAL-FIELD-RECEIPT.json)和[Host检查原始输出](VOICE-HOST-REGRESSION-OUTPUT.txt)。

| 制品 | SHA256 |
|---|---|
| 实装验证语音候选R9，29684B | `6f2b910c276f4143261e8555dd778933493cb22a1fb7a651bacfd103912b05e5` |
| 成功会话原始PCM | `771aad26dfec6c38b4c1cd93264fb06a3a2513aa66be78021ea8491c0bdc2771` |
| 成功会话服务器原始回执 | `e19749a7508456d8ca14fe55edd866557b1ebf3e22bcb410ad76ef652e3776af` |
| 收尾恢复后的完整1MiB Flash | `423a805860e2300a03de87471ba69ac9ec439a74b19dd76f561b7dce16d7fcdf` |

候选只触及sector0/1，恢复使用今天备份的原应用49152B；恢复后完整Flash与测试前完全一致，sector3及Options未变，恢复控制器/原生工作进程退出0。[安装](VOICE-R9-INSTALL.json)、[恢复](VOICE-RESTORE.json)保留真实Halt/Write/Reset/Go及Close记录。负责人在恢复后回复“已关闭”。J-Link板端仍在C，A/B保持断电、C两段CAN隔离。

本轮失败及整改均保留：

| 观察 | 原始结果与处理 |
|---|---|
| 初始静音尾IRQ多一次 | 采集退出1；修正原子停机顺序，随后真实录音完整性通过 |
| 声源未覆盖窗口、电脑短句未真正外放 | 作为刺激无效保留，不记麦克风或ASR准确性失败；后续使用先播放后回复的连续手机声源 |
| 换环境后原Wi-Fi不可用、UDP授时无有效回复 | 连接退出1；改用负责人手机热点，仅注入RAM。独立台架改用SSH认证且NTP同步的服务器UTC，记录查询延迟及秒级量化；原B5新鲜UDP判据未改，UDP失败未改签PASS |
| 外部18884无入站SYN | 相关探测与受限抓包保留；改用空闲且已有放行规则的1883透传到隔离TLS Broker，证书校验保持，防火墙未改 |
| QoS1订阅被coreMQTT拒绝 | 实际C Host回放原生退出3、状态MQTTBadParameter；补齐语音适配层入站状态表。完整/分片SUBACK、拒绝/错ID、真实入站与出站QoS1/PUBACK回归退出0 |
| 首次上传时透传按180秒总连接时长断开 | 现场退出1，原始PCM已保全；改为逐次空闲读取超时，两项定向Host测试退出0 |
| 首次实际ASR成功后AI输出被拒绝 | 原session `1793609561`：125块逐字节对账、ASR退出0，AI HTTP200但输出校验拒绝，最终C超时退出1。原失败留存；具体触发哪条校验为UNKNOWN。收紧JSON/短中文请求并增加私有输出原件，不改原校验器；成功会话重新走默认完整流程 |
| 在线重连配置帧处理不当 | 修正为完整消费249B帧，在线拒绝应用；连接先S并等待CONTROL_READY。含S/N/R等命令字节的配置帧定向回归退出0 |
| 等待期间临时入口一小时到期 | 该次未启动录音，主机退出1；入口续建为六小时预算，采集工具先确认RECORDING事件再等待结果；不要求人工精确计时 |

早期少量Python socket诊断把内部失败标志误命名为native_exit，已在[退出码语义更正](PROBE-EXIT-SEMANTICS-CORRECTION.json)区分实际控制器退出0与socket失败；原件未覆盖。正式采集主进程退出0；ASR原生进程退出0；SSH隧道被主机主动清理的子进程退出值仍原样保留，不能合并成全部进程均退出0。更多检查见[汇总](VOICE-FINAL-CHECKS.json)。

收尾已停止本任务四个临时单元，1883/18884/18885均无监听；原到期入口的failed状态保留。正式五个服务仍active、PID与入场一致，Broker配置/ACL/密码文件SHA一致，正式服务重启和防火墙修改均为0。[云端收尾](VOICE-CLOUD-CLEANUP.json)包含各命令真实返回值；Windows临时热点已关闭，频段设置仍为原AUTO。

未关闭项：STOP请求完成但没有ACK＋IDLE全证据（[真实STOP回执](VOICE-FINAL-STOP.json)），SDK Open/Close原生隐式副作用仍UNRESOLVED；实物PCB修订、模块外部去耦/下拉仍UNKNOWN；运行栈高水位及三板音频负载共存未实测。可选U重传入口本轮未做实板验证。旧RR24/RR30失败、TEMP180末帧异常、RR下HR源端真值及旧冻结评测结果均保持原状。

原始音频、IRQ元数据、完整Flash/UID、原生日志及凭据留在受限EFS与服务器任务目录，不入Git。本机从忽略的 `node-b/build/voice-mic-current-pointer.json` 定位受限证据。代码、公开回执和简报提交该独立分支，后续统一镜像及正式合并等待负责人指令。
