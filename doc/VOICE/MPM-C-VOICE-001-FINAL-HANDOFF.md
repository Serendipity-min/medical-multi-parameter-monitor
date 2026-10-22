# MPM-C-VOICE-001 阶段交接｜2026-10-22

**当前为T0/T1软件阶段完成、现场窗口待批准；尚未验证实际发声。** 用户本轮目标仅本地播放确认，8Ω1W短时v1按最新指令准备。工作区 `E:/medical-monitor-c-voice`，分支 `codex/gateway-c-tw-tts-v1-20261022`，起点 `a5cdd5b0b1ad48108fd631136e9de69e30582f2d`。

## 已完成

- 完整阅读合同；独立worktree/单写入者登记，开工实际复核PRIVATE仓库、H3远端及annotated tag精确身份。
- 读取厂家V0.21、本地6页原理图及数据手册，给出PA2/PA3、P3板载路由、FT电平条件、5V及SPK差分设计，区分代码/图纸/负责人确认/未测。
- 新增独立纯C帧/单槽状态机/USART2端口、人工单次WK_UP离线台架、专用ELF加载段检查及sector0维护工具；原H3构建/核心协议/业务源码未改。
- Host3103断言、维护工具7项合成回归、Backend/AI/Gateway318项+4子测试（1跳过）、P5 42/48、CAN Host、物理IRQ Host、原两ARM与独立ARM通过。原始非零失败不覆盖。
- 原正式C BIN复现到43172B，SHA **b9b25b186c3b40d62b4a1c1919e09f27b639806271a3b20ae7fc80ea4cda1efe**。隔离旧BIN只离线编译、未使用。

## 候选身份与资源

| 文件/资源 | 实际身份 |
|---|---|
| offline bench BIN | 3756B；SHA256 `311032f64c7f6674f14410414504c99a3d4ae35dd0e7be0703a97715fca8ad30` |
| offline bench ELF | SHA256 `ed8d81161ea78ea5001ee619739f0daf343fcdc7f72293b3937fe36128c00f32` |
| MAP | SHA256 `69c300d589f3dc63ca07832c45c86234b0b3a07cc0157b239a8a74ebfaeab84e` |
| 台架加载范围 | 应用0x08000000–0x08000EAB；实际拟写FF补齐16KiB sector0，SHA `0734d09ad8f7197d9afd940e4334a728db02ae40d6860ae68ad46faf9e577981` |
| 静态size | text3744/data12/bss2468；bss包含2048B链接预留栈，不是实测水位 |
| Queue | Host344B，ARM符号voice_bench实测size312B；32B UART静态RX；无动态分配 |
| 外设 | 只新增PA2/PA3 USART2 AF7、PA0按键、SysTick；无网络、CAN、Flash配置运行时写入 |

## 分层结论

| Gate | 状态 |
|---|---|
| T0 | SOURCE_REVIEW_COMPLETE；实物电压/电源/功率未测 |
| T1 | HOST_PASS；候选独立编译通过 |
| T2 | BENCH_NOT_RUN，需现场接线与真实发声 |
| T3 | NOT_RUN；离线台架不等于联网C整合 |
| T4 | DESIGN_ONLY；未实现/实测新下行 |
| T5 | CLOUD_AUDIO_NOT_AUTHORIZED；豆包真实调用0 |
| T6 | NOT_RUN；CAN/MQTT并发窗口/实板栈/电流未测 |
| T7 | 源码/软件证据阶段归档；无音频通过标签；本轮新Flash/恢复原件不存在 |

**总状态 `HOST_ONLY / AUDIO_HEARD_NOT_OBSERVED`。** 没有C_TTS_LOCAL_PASS、没有C_TTS_AI_LINK_PASS。不追认H3临床精度或更改H3原报告。A/B/Node-B未参与；麦克风与ASR始终NOT_IN_SCOPE。

## 可审查材料与下一步

- [T0引脚/电源](VOICE-T0-PIN-POWER-AUDIT.md)
- [T1协议/测试与真实异常](VOICE-T1-PROTOCOL-AND-HOST-RESULT.md)
- [T4下行方案](VOICE-T4-DOWNLINK-DECISION.md)
- [下一张准确现场卡](VOICE-AUTHORIZATION-REQUEST.md)
- [引脚及B整合边界](PIN_RESOURCE_MAP.md)
- [不可变输入清单](VOICE-INPUT-MANIFEST.json)与[evidence](evidence/)

实际Git提交SHA在提交后由外部受限交付回执与最终回复给出，本文不预写自身SHA。没有推送新语音分支、没有创建PR/新tag；所有保护refs保持基线。仅在负责人批准具体现场卡后，按卡先测电平，再备份/写入/人工播放/恢复；不在当前软件阶段打开J-Link或串口。
