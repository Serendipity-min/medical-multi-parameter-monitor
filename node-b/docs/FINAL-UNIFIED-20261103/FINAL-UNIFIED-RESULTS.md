# FINAL 三板语音统一集成回执

2026-11-03（Asia/Shanghai）。本次结论：**FINAL-P1C / C_UNIFIED_RUNTIME_PASS**，仅覆盖非人体C单板、真实MIC、隔离TLS/MQTT、真实ASR/AI工程短回复、实际喇叭、软件CAN接收入口负载及上行故障恢复。**不是B+C、ABC、监护事实问答或最终整机验收通过。**

分支 `codex/final-unified-c-runtime`，本阶段从 `5abd83443e42ad0aae3d94a91e1a814715502b88` 继续；本报告及制品绑定包含本文件的阶段提交，实际提交SHA在交付回执及Git记录给出。P1B起点为 `baccc7bc6ca2a14da6779664eead919a3240ccf4`。执行合同原件及SHA保留在EXECUTION-CONTRACT.md和历史P1B提交。

## 实物、版本和安装

负责人已一次批准C的sector0（0x08000000–0x08003FFF）及sector4（0x08010000–0x0801FFFF）用于本合同内安装、必要更新及恢复。四个不同候选的受控安装全部退出0；实际SDK日志为2 ranges /81920B。每次均在身份/现状核对后下载，1MiB读回及Options/身份全部通过才启动。sector1–3、5–11及Options原字节保留；无整片擦除入口或保护位修改。回退仍使用已有C44520完整备份及同范围分段入口，新分段实板回退本轮未执行。

当前保留C **R4 / ABC_UNIFIED_C_V1**，未定版。最后一次安装全片SHA为 `b0107fd5b1bc4ffa38f82ae7ad584736887292277362fb54ccd356b28529c6a4`；本轮没有在运行后额外连接SDK重读。负责人已确认本次C喇叭及ASR内容相符，并按请求完成断电、拔电脑端USB；A/B保持断电、两段CAN隔离，板端MIC/TTS及J-Link接线保留。运行观察阶段SDK会话0。A/B固件未改，正式云服务/ACL/防火墙未改，main未合并。

| 当前制品/资源 | 实际数值 |
|---|---|
| ELF SHA256 | `fb79a7c3c31f4cfafa0895a3c5f79187ab7d79ed8f2f43158b65ec764b7706eb` |
| HEX SHA256 | `d27d9b888fa48b70d14b73bf0e43306f588ec2fd5f8cb16d5498d00c946591ac` |
| boot / code加载地址 | 0x08000000 / 0x08010000；禁止跨sector3平坦BIN |
| boot+code | 53888B；sector4代码53496B，余12040B |
| 普通SRAM | data+bss=81540B；预留24KiB堆、8KiB栈后另余16760B |
| CCM / DMA | PCM64000B在CCM，余1536B；DMA2560B在普通SRAM |
| 本上电周期栈水位上界 | 3084B，不能代替全部路径最坏栈证明 |
| 隔离云重组器 SHA256 | `d1fee189b304279e4f0492bcb6fb59b0cf13f04b7e4572a1bf9fdcf7c4dd3c58` |

ELF/HEX/map/链接脚本/分段BIN在 `candidate-r4/`；R1–R3历史制品保留。[构建回执](P1C-R4-BUILD-RECEIPT.json)和[SOURCE清单](SOURCE-SHA256.json)给出实际交付输入。三份源码沿用仓库原CRLF格式后重新构建，boot/code/ELF/HEX与实装R4逐字节相同，未重刷；原安装构建回执另留P1C-R4-INSTALL-BUILD-RECEIPT.json。另保留原仓库LF与Windows未改文件CRLF的输入对照；所有修改的自有源文件均逐字节绑定，旧文件仅行尾差异，不把原Git换行转换误报为代码漂移。原C44520源码目标再构建，BIN仍为 `5f4690eca0a00334ff1a9b653be2a0b99cba034b869ae4592dd36a042a147442`，ELF亦与原基线一致；未将它重新安装。

## 最终同窗结果

会话 `1793674218`，在当前R4和软件CAN负载下录音，且紧接真实上行故障恢复之后执行；该段之间没有重启C或worker，也未清空中断会话来绕过缺陷。

| 层次 | 证据与裁定 |
|---|---|
| 本地录音完整性 | 32000样本/2秒/PCM16单声道；DMA错误0、覆盖0、截幅0；原IRQ/录块连续性校验通过 |
| 实际C上行 | Broker实收125块/64000B；源导出与云端PCM逐字节相同，CRC32=2259289543 |
| PCM SHA256 | `80cf4cb7b0cb806859e88114bd1ca5ef2747f517961e294dd0a8e6b78bdf5b94` |
| 云端ASR/AI | ASR原生退出0，36.474秒；真实AI调用及回复PUBACK成立；负责人核对英语片段相符 |
| TTS/停止 | 实际C喇叭播报“已确认收到”，负责人确认；ACK/DONE及全局STOP→ACK→查询→IDLE成立 |
| 重组恢复 | 修复后的worker接收141块：前一故障会话16块不完整，随后新会话125块完成；拒绝0，完成C会话1，HOST会话0 |
| 负载/资源 | 有效窗口日志首尾软件帧增量每路27628；队列高水位2/2，无溢出；CAN入口最大22318周期，按声明8MHz约2.790ms |
| 服务间隔 | 业务运行中平台poll最大间隔7ms；全局STOP之后收尾累计16ms，原值保留，不包装为运行期7ms上界 |
| 可用性/延迟 | 首音频包到回复包Host墙钟60.681秒；口耳全流程未独立计时，不宣传低延迟实时助手或统计可用率 |

采样率约16000.001Hz、IRQ间隔约9.989–10.011ms是基于声明HSE与DWT的相对测量，非独立频率计绝对标定。累计音频失败计数1仍在，本有效窗口新失败0，没有复位清零来制造通过。TTS ACK累计2包含启动音量设置1次，实际文本完成1次。

C-only软件负载复用两路原RX队列及真实CANopen/RPDO，每次5ms服务向每路送2个无有效测量值的PDO锚/质量帧。实体控制器静默、RX IRQ关闭，物理CAN RX/TX为0，不产生有效ECG/血压等测量值。该结果只证明软件处理入口与真MIC/网络/TTS共存，不能替代真实CAN IRQ、B250Hz/50Hz上行或三板并发。

## 故障与最小修复

| 失败原件 | 原因及处理 | 修复证据 |
|---|---|---|
| R1，采集退出1，上传0块 | 出口空闲轮重复启动接收查询，占用低优先级音频AT空档；统一模式去掉第二次空轮询，原B5路径不变 | 定向100轮由0空档变50；R2实际125块及喇叭通过 |
| R3，录音入口退出1，未开始采样 | 将任何遥测ACK在途作为拒绝本地录音条件；去掉这项多余限制，上传背压/ACK绑定不变 | 原代码反例退出3，修复后Host及R4负载录音通过 |
| R4首次故障后正常录音退出1 | Broker收到125块，但worker被旧9块未完成会话卡住，新125块全部拒绝，ASR未启动；有效的新会话起始块可取代旧未完成会话 | 同一真实C数据回放：修复前拒绝125/完成0，后拒绝0/完成1，PCM不变；再实物“故障→新录音”完成125块 |

云重组修复只动隔离worker的protocol模块；整包/分块/整音CRC、源隔离、序号/长度、90秒同会话期限及已完成重放拒绝保留，新起始块须先通过原校验且session较新。同会话重复起始块不延长期限。该修复后没有再烧录C。

两次本任务透传进程SIGSTOP/CONT制造真实上行ACK停顿，非关闭Wi-Fi；STOP/CONT原生退出均0。最新故障窗C确认15块、Broker实际保留16块，暂停期实见本地STOP ACK/查询/IDLE；恢复后新鲜SNTP、TLS、SUBACK重新完成，CAN软件回放继续、DMA/覆盖0，故障工具退出0。未测试实体AP掉线；新统一程序在实际发声中间打断未单独覆盖，不以此前单板STOP成绩冒称本轮已测。

## 真实退出码、工具和清理

- 最终采集父进程0、ASR0；R4安装/完整核对0；最新8组Host编译/执行0；7项云协议回归0。真实数据回放保留前后结果，不能当作新实板窗口。
- 原48KiB溢出退出1、R1/R3/R4失败退出1、录音入口反例3、Host夹具早期编译/链接/宏错误及部署权限失败1均保留；没有改旧冻结评测器或RR阈值。
- 自有SSH观察隧道由Windows TerminateProcess主动结束，原生退出1，按受控清理记录，未伪称自然退出0。任务三项隔离服务停止命令0，当前全部inactive；正式服务停止/重启0次。
- 沿用唯一main/SysTick/ESP/TLS/coreMQTT owner、原MIC采集/格式/CRC、TTS队列及分段SDK工具；F配置只进RAM。B5新鲜SNTP/CA/主机名校验保留，旧独立MIC的SSH UTC方案没有进入统一运行。
- `UNISTART C/BC/ABC`明确选择总线且无固定420秒停机；旧B5START仍保持420秒。软件回放默认关闭且仅C-only可启用，B+C/ABC拒绝开启。全局X停止后不自动重启。无PI签名/nonce/次数卡。

复现入口：

```powershell
python -X utf8 gateway/dual_can/build_arm.py --b5 --egress-final --tri --unified --split-flash
python -X utf8 gateway/microphone/test_unified.py
python -X utf8 gateway/microphone/test_unified_install.py
python -X utf8 cloud/microphone/test_protocol.py
```

现场工具复用 `gateway/microphone/field.py --unified` 的connect/capture/load/fault/stop/finish，身份不符则不发旧MIC配置。原始Flash、UID、配置、音频和ASR正文仅在受限EFS；本地忽略的 `node-b/build/final-unified-current-pointer.json` 定位原件。公开摘要、必要固定指标日志及SHA见本目录JSON清单。下载核对依据[SEGGER扇区编程流程](https://kb.segger.com/J-Link_flash_programming)，实际以本次2 ranges日志和全片/Options核对为证。

## 唯一阶段清单及后续边界

- [x] P1B真实统一C离线构建/分段布局、唯一网络owner和有界推进。
- [x] P1C C-only实际MIC→Broker→ASR/AI工程短回复→TTS，软件CAN入口负载、STOP及指定上行停顿恢复。
- [ ] B41516+C：真实ECG/RR/物体温度To、温度屏/UART4/CAN/MQTT/WSS同窗300秒，NOT_RUN。
- [ ] A42608+B41516+C及基于同会话监护事实的语音问答，NOT_RUN。
- [ ] 三板与语音30分钟、必要24小时、配套正式发布包/部署版本映射及main合并，NOT_RUN。

本次许可仅C，下一步须另行取得B+C现场授权，不自行连接或上电A/B。C R4仅为受控候选，后续仍需核对真实CAN IRQ优先级编码/时序、物理总线及真实遥测与音频争用；本次源码请求CAN优先级3/DMA8不当作独立实测。保留实物PCB修订UNKNOWN、独立无探针冷启动/SDK隐式副作用未关闭、原链接符号类型警告及未覆盖路径栈风险。

RR24/RR30失败、RR15 SOURCE_UNKNOWN/ROOT_CAUSE_UNRESOLVED、旧TEMP180末帧、绝对阻抗/体温/血压标定及正式云版本映射继续保留。GY641是物体温度To，NIBP为最近完成结果/90秒有效；非人体synthetic标签不改成真人LIVE。本轮AI只作工程短确认，未完成医疗监护事实问答；家庭演示阈值仍按合同冻结，不把本次语音通过当作临床判定或整机放行。
