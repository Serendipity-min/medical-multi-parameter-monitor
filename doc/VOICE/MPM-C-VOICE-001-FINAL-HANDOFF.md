# MPM-C-VOICE-001 最终交接｜本轮单次离线试音｜2026-10-22

**本轮目标已完成：TW-TTS搭配现有8Ω1W喇叭，正常独立启动后完整播放“语音模块测试完成”，负责人确认能听清且无失真等异常。已按批准范围恢复原C固件，现场已断电拆除测试线。** 这是一次离线、v1低音量固定短句验证，不是联网语音集成或扬声器功率认证。工作区 `E:/medical-monitor-c-voice`，分支 `codex/gateway-c-tw-tts-v1-20261022`，起点 `a5cdd5b0b1ad48108fd631136e9de69e30582f2d`。

## 已完成

- 完整阅读合同；独立worktree/单写入者登记，开工实际复核PRIVATE仓库、H3远端及annotated tag精确身份。
- 读取厂家V0.21、本地6页原理图及数据手册，给出PA2/PA3、P3板载路由、FT电平条件、5V及SPK差分设计，区分代码/图纸/负责人确认/未测。
- 新增独立纯C帧/单槽状态机/USART2端口、人工单次WK_UP离线台架、专用ELF加载段检查及sector0维护工具；原H3构建/核心协议/业务源码未改。
- Host3103断言、维护工具7项合成回归、Backend/AI/Gateway318项+4子测试（1跳过）、P5 42/48、CAN Host、物理IRQ Host、原两ARM与独立ARM通过。原始非零失败不覆盖。
- 原正式C BIN复现到43172B，SHA **b9b25b186c3b40d62b4a1c1919e09f27b639806271a3b20ae7fc80ea4cda1efe**。隔离旧BIN只离线编译、未使用。
- 实际硬件执行绑定软件HEAD **deaba320ab2a47efb8e1593e4d58172817e6c522**；负责人明确批准AUTH-VOICE-C-OFFLINE-BENCH-1，随后确认T脚3.33V、ESP断开、接线/正常独立启动及最终收尾。J-Link实际VTref3.3V。模块V供电仅获“正常”的定性回报，未取得数值/纹波/峰值电流。
- 双读C sector0–3，磁盘原件一致；仅将完整FF补齐16KiB块写sector0；读回及1–3/7/11/options/Flash控制器核验通过。没有mass erase、A/B操作、SetPC/MSP/VTOR强起或新网络连接。
- 读回状态证明音量帧及文本帧发送完成各一次，模块接收确认累计2、播报完成1，实际UART错误0/溢出0。人工可闻是独立负责人证据，不以这些计数替代声音。
- 原C sector0恢复后整个64KiB重回 **49d3fad5040b25b746905d5c1468bff4d5be5a4f13197286ce215e0711798fb4**；sector3配置 **395c6a36d7c4a636b34a72eacd1ccc2a2fc7f025df7089f3d94e1d2de14c5a3b** 未改，sector7/11/options不变。恢复退出0，现场确认断电、J-Link拔除、TTS四线已拆。原固件没有本次按键播报功能。

## 候选身份与资源

| 文件/资源 | 实际身份 |
|---|---|
| offline bench BIN | 3756B；SHA256 `311032f64c7f6674f14410414504c99a3d4ae35dd0e7be0703a97715fca8ad30` |
| offline bench ELF | SHA256 `ed8d81161ea78ea5001ee619739f0daf343fcdc7f72293b3937fe36128c00f32` |
| MAP | SHA256 `69c300d589f3dc63ca07832c45c86234b0b3a07cc0157b239a8a74ebfaeab84e` |
| 台架加载范围 | 应用0x08000000–0x08000EAB；实际写入FF补齐16KiB sector0，SHA `0734d09ad8f7197d9afd940e4334a728db02ae40d6860ae68ad46faf9e577981` |
| 静态size | text3744/data12/bss2468；bss包含2048B链接预留栈，不是实测水位 |
| Queue | Host344B，ARM符号voice_bench实测size312B；32B UART静态RX；无动态分配 |
| 外设 | 只新增PA2/PA3 USART2 AF7、PA0按键、SysTick；无网络、CAN、Flash配置运行时写入 |

## 分层结论

| Gate | 状态 |
|---|---|
| T0 | 图纸/资源核对及T脚3.33V、VTref3.3V完成；模块V数值、播放峰值/功率未测 |
| T1 | HOST_PASS；候选独立编译通过 |
| T2 | SINGLE_LOCAL_PHRASE_AUDIBLE_CONFIRMED；完整电源/功率、暂停/继续/查询和停止实测未全完成 |
| T3 | C离线USART2实测通过单条播报；未向生产8883固件整合，不签发完整T3通过 |
| T4 | DESIGN_ONLY；未实现/实测新下行 |
| T5 | CLOUD_AUDIO_NOT_AUTHORIZED；豆包真实调用0 |
| T6 | NOT_RUN；CAN/MQTT并发窗口/实板栈/电流未测 |
| T7 | 当次双备份、实际写/恢复/回读、RAM诊断均在本机加密归档并核验第二份；本地源码提交；未推送或新打tag |

**用户要求的单次本地发声验证通过；合同全门禁总状态 `LOCAL_PHRASE_HEARD_ORIGINAL_C_RESTORED / CONTRACT_PARTIAL`。** 因未测峰值/功率及未完成完整停止与网络回归，不签发全合同C_TTS_LOCAL_PASS或C_TTS_AI_LINK_PASS。不追认H3临床精度或更改H3原报告。A/B/Node-B未参与；麦克风与ASR始终NOT_IN_SCOPE。

## 实际异常、诊断和退出码

| 事件 | 实际结果/退出码 |
|---|---|
| C只读身份/容量/保护区/控制器 | 0；实际角色匹配，未写Flash |
| 第一次维护入口读取UTF-8授权卡 | 1；Windows默认GBK在连接目标前抛UnicodeDecodeError，无Flash/RAM写入 |
| 等价ASCII转义授权卡后的单次写入 | 0；不是第二次物理烧录尝试，前次尚未调用Bridge |
| 首次现场反馈无声 | 只读诊断exit0，但VTOR=0x1FFF0000、USART2未启用、boot alias非应用；RAM不是已初始化程序状态，随机值全部判INVALID，绝不作为累计计数 |
| 确认BOOT/拔J-Link/独立冷启动后 | 负责人确认完整短句可闻；未重刷、未强设PC，具体BOOT电平/先前反向供电未测，不能唯一归因为某个跳帽或J-Link |
| 成功后的只读记录 | 0；VTOR=0、boot alias匹配应用，BRR=0x341/CR1=0x202C；触发1、发送完成2、ACK2、DONE1、RX5、UART错误0、RX溢出0 |
| 成功后额外按一次WK_UP | 按设计只提交STOP，不重播；收到STOP ACK（最后状态0x41），没有后续0x4F，stop_idle=0/stop_failed=1、errors=1，保持不清零 |
| 原sector0恢复 | 0；整个64KiB精确恢复，配置/保护区不变；工具末态HALT无GO，随后负责人断电收尾 |
| 加密准备首次读取外部UTF-8回执 | 1；同类默认GBK问题，尚未生成密文或访问板卡；改为显式UTF-8后加密/第二份解密均0，失败索引保留在私有预归档回执 |
| 收尾修复UTF-8读取并增加负例 | 0；9项Host通过；硬件窗口仍绑定旧deaba320，新改动只修维护JSON读取，不改变已验证BIN、未再编译/烧录固件 |

STOP这项不能写成“停止成功”或“播放中静音通过”。当前计数与代码路径支持一次等待空闲超时，但没有保留额外按键前的独立RAM快照；没有重复播报来掩盖。未来应明确模块STOP/QUERY实际回包时序后，再验证播放中停止、暂停、继续和状态查询。

用户听清短句属于人工证据；未录音、未用逻辑分析仪取得逐字节带时间串口抓包。41/4F由已冻结代码的处理计数证明，4A/4E及45/46的实际型号响应和QUERY长度仍待实测。5V、峰值电流、纹波、扬声器差分功率、实际温度和栈水位未测；v1不证明≤1W，也不扩张为可长期/高音量使用1W喇叭。

## 私有恢复物与执行边界

完整窗口AES256密文：`E:/medical-monitor-c-voice-private/encrypted/C-voice-complete-window-20261022T031943Z.tar.gpg`；第二份 `D:/medical-monitor-c-voice-archive/` 同名。**2192402B，SHA256 c256a21685dac36a24dd6cd5df778658b480fd59c147f59b7906612530f8cf96**，第二份流式解密逐项核验160文件通过，exit0。另保留试播前预归档，SHA **03aa6ed035ae49e3a787ba07d2b373978386fb482c3205672591ffa5db683725**。

恢复引用/密钥外部路径通过本地 `E:/medical-monitor-c-voice-private/VOICE-ARCHIVE-RECEIPT.json` 及既有H3私有交付回执关联；密钥本体不读取、不打印、不放Git或密文包内。负责人离线密钥保管仍由原交付要求约束，不因本轮成功自动宣称已异地保管。原始窗口、备份、UID与配置均仅在外部受限目录/加密包，Git只存脱敏结果。

无CAN/ESP/MQTT并发或300秒窗口、无10次长短句/断线声学验证；离线候选根本未链接这些路径，不能以它们的零计数证明生产功能不退化。除负责人最新明确授权的P6分支更新外，H3原标签、A/B/P4/main/H3分支和报告未修改，无PR、强推、Security Gate或真实豆包调用。

## 后续授权：发布到P6分支

负责人在试音收尾后明确要求推送至 `dev/p6-cloud-ai-text-tts-v1`。P6原HEAD为 `77dd14d1ca761a488956f7a4ebf28cb3174835e4`，与H3存在分叉；在独立工作区 `E:/medical-monitor-p6-voice-publish` 从该P6提交移入本轮两份语音提交，保留P6既有内容。没有合入H3的其余历史。

P6未包含H3维护/物理CAN目录，因此仅在VOICE目录补入本地离线依赖：原H3的时钟C/头文件字节相同，J-Link白名单及身份/保护读取方法与配置验证函数AST相同；不移入原H3烧录CLI、联网入口或配置写入工具。历史 `VOICE-INPUT-MANIFEST.json`、`VOICE-CLOSEOUT-MANIFEST.json` 仍描述原H3执行身份，不冒充P6当前源码清单；当前清单为 `evidence/P6-publication-manifest.json`。

P6实际验证：Backend/AI/维护工具共83项通过，语音Host3103断言通过，ARM构建退出0，3756B BIN与实测SHA `311032f64c7f6674f14410414504c99a3d4ae35dd0e7be0703a97715fca8ad30` 完全一致。ELF/MAP因构建路径变化独立保存，未拿原ELF SHA冒充P6新ELF。没有再次访问板卡/串口/云端。

P6离线复现命令：`python gateway/voice/build.py`；WSL内本工作区运行 `python3 gateway/voice/build.py --host`；普通Python运行 `python -m pytest cloud/backend/tests cloud/ai/tests gateway/voice/tests/test_bench_window.py -q`。依赖既有ARM工具链、STM32 SDK及维护环境中的stm32loader，不安装新依赖。`gateway/voice/regression.py`是原H3整套历史回放入口，在缺H3工程的P6明确退出2并给出适用命令，不把缺失的H3用例标为通过。

本提交准备正常快进更新P6；真实推送、远端回读及最终SHA以发布后的私有回执和最终回复为准，不预写尚未生成的提交ID。当前变更范围仅 `gateway/voice/`、`doc/VOICE/` 和限定的 `.gitattributes` 回执字节策略；P6既有云服务和前端源码未改变。

## 可审查材料与下一步

- [T0引脚/电源](VOICE-T0-PIN-POWER-AUDIT.md)
- [T1协议/测试与真实异常](VOICE-T1-PROTOCOL-AND-HOST-RESULT.md)
- [T4下行方案](VOICE-T4-DOWNLINK-DECISION.md)
- [下一张准确现场卡](VOICE-AUTHORIZATION-REQUEST.md)
- [引脚及B整合边界](PIN_RESOURCE_MAP.md)
- [不可变输入清单](VOICE-INPUT-MANIFEST.json)与[evidence](evidence/)
- [实际硬件分层结果](evidence/HARDWARE-20261022.json)及[收尾源码身份](VOICE-CLOSEOUT-MANIFEST.json)

实际最终Git提交SHA在提交后由外部受限交付回执与最终回复给出，本文不预写自身SHA。按最新授权更新P6，不创建PR/新tag；其余保护refs保持基线。本次硬件卡已完成并关闭，后续不复用它继续烧录/试播。只需确认可以播放的本轮目标已满足，完成P6发布核验后停止。
