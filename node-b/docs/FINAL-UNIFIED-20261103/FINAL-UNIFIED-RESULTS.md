# FINAL 统一集成阶段回执

当前阶段：**FINAL-P1B OFFLINE_READY**。从 `baccc7bc6ca2a14da6779664eead919a3240ccf4` 创建 `codex/final-unified-c-runtime`；已核对远端起点无更新。合同 SHA256 为 `e25b311d1f57fe9203446622e897c60d12d62072e7eb97cfb31d015c2bb779c8`。

本次未打开SDK、连接UART、上电、烧录、RESET或修改云服务；C实装仍是最后核验的C44520。既有P0/独立STOP/历史两组链路直接复用，没有重新验收。MIC的100nF陶瓷电容和100kΩ电阻按负责人明确核实记录，不再重复辨认。

## 实际整合

- 保留 `gateway/b5/network_main.c` 为唯一main，原平台SysTick、ESP/TLS/coreMQTT为唯一owner；没有链接独立MIC网络main。
- 复用MIC I²S3/DMA、原CRC/MC01/MR01协议、现有B5异步出口及TTS队列；CAN先推进，MIC在前台解码。128B增量CRC分500轮处理，音频每轮最多提交一块512B，最多一个QoS1在途。只有监护实时队列与发布者空闲时提交低优先级音频，不进入逐块5秒ACK等待循环。
- 音频和监护共用消息ID/出站QoS1表；增加一个入站QoS1表。实际SUBACK授予QoS1后才能录音；音频PUBACK不计作监护标量成功。回复只在WAITING接收，绑定session/PCM CRC、非retain、指定主题、长度/UTF-8校验，保留60字节文字协议上限。
- 复用现有TTS STOP→ACK→查询→IDLE与失败锁止；断网取消音频，CAN和本地停止仍可推进。已失同步的AT流不盲发恢复命令，报告人工恢复需求；这类原生异常的无重启恢复仍待现场验证。
- `UNISTART C` / `UNISTART BC` / `UNISTART ABC` 分别启用0/2/3总线掩码，无420秒固定停机；旧 `B5START` 仍保持420秒。`R`录音、`S`停止音频、`Q`状态、`X`全局停止；全局停止后禁止R重启，D原音导出仅在停止后允许。
- F帧沿用MCF3长度/CRC/字符串格式，只在未武装时应用RAM配置。固定B5身份、原Flash配置有效性、主机/证书和新鲜SNTP判据保留；忽略旧独立MIC的reference epoch，不以SSH时间替代SNTP。F帧内的X/R等字节不解释为控制命令。
- 统一候选TLS默认1883，仅供后续任务隔离监听；原B5默认8883不变。本阶段没有启动监听或改Broker ACL。

## Flash与RAM（实际ELF）

| 区域 | 新制品/占用 | 安装范围或余量 |
|---|---|---|
| sector0向量 | 0x08000000–0x08000187，392B | 需擦写0x08000000–0x08003FFF |
| sector4代码及初始化数据 | 0x08010000–0x0801CEA7，52904B | 需擦写0x08010000–0x0801FFFF；余12632B |
| sector1/2/3、5–11、Options | 无镜像加载段 | 全部保持原字节；sector3含配置 |
| 普通SRAM data+bss | 81516B | 含DMA，另4B对齐 |
| 固定堆/最小栈预留 | 24576B / 8192B | 预留后另余16784B；堆末至MSP顶实际区域24976B |
| CCM CPU PCM | 64000B，0x10000000 | 余1536B；禁止DMA访问 |
| DMA双缓冲 | 2560B，普通SRAM | 实际地址见RESOURCE-LAYOUT.json；CAN IRQ3高于MIC IRQ8 |

新候选真实尝试48KiB链接失败，原生退出1，超3808B；没有删除状态校验来强行塞入。现在使用有地址的HEX和两个BIN，不生成跨sector3空洞的平坦BIN。实际MSP=0x20020000，Reset向量=0x0801A5DD，VTOR保持0x08000000；启动代码和ISR在sector4，104B初始化数据从0x0801CE40加载到0x20000000。CCM为NOLOAD，PCM只在录满后使用。资源表不代表实际栈/IRQ水位通过。

ELF、HEX、map、链接脚本、两个段及SHA清单位于 `candidate/`。HEX与BIN逐字节校验、向量检查及真实备份拼接的PLAN_ONLY执行退出0；未加载DLL。旧C44520构建BIN仍为 `5f4690eca0a00334ff1a9b653be2a0b99cba034b869ae4592dd36a042a147442`，与既有实装基线一致。

## 最小复现与真实退出码

```powershell
python -X utf8 gateway/dual_can/build_arm.py --b5 --egress-final --tri --unified --split-flash
python -X utf8 gateway/microphone/test_unified.py
python -X utf8 gateway/microphone/test_unified_install.py
```

最终ARM构建0；五组Host编译与执行均0；分段安装10项单元测试0。Host中的300秒为虚拟时间，不是实板持续采集。

| 定向验证 | 结果 |
|---|---|
| 真实coreMQTT/adapter + ESP替身 | 414项检查；订阅、分片ACK、错/缺/半/旧ACK、音频/标量ACK归属、Q0继续推进、下行主题及retain拒绝 |
| 真实音频状态机/CRC/原TTS队列 + DMA/端口替身 | 1288项检查；125块、500轮CRC、背压、不提前接受回复、网络中断STOP/查询/IDLE、禁止活动时阻塞导出 |
| 真实main控制/服务函数 + 硬件替身 | 27项检查；C/BC/ABC、旧420秒、超长行、二进制F帧、断网CAN继续、X后R拒绝 |
| 原I²S格式测试 | signed24、PCM16、左右槽和CRC通过 |
| 原B5异步出口 | 三次停顿虚拟300秒回归通过；错误ACK、过载负例保留；原断言未放宽 |
| 分段薄安装入口 + 合成NOR/SDK替身 | 精确0/4安装及恢复、保护区字节不变、错板/ROM/HALT/故障事前拒绝、短写/破坏后禁止启动、HEX篡改/越区/无批准不进入SDK等10项通过 |

初始构建/夹具失败未删除：48KiB容量退出1、两个缺声明/宏的夹具编译退出1、旧夹具漏宏退出3、控制夹具外部入口链接退出1、同时构建目录时间戳碰撞退出1。已各自修正并定向复测；详情见NATIVE-EXIT-CODES.json，原日志在受限EFS。`_heap_end`链接符号char/uint32声明警告为原有警告，旧C44520也存在，默认BIN保持一致；没有把它包装为新候选运行可靠性的证明。

## 安装和回退（尚未执行）

复用 `abc_board_backup` / `b4_swd_install` / `b4_recovery` / 原生监督器，新增薄入口 `gateway/microphone/unified_install.py`。默认仅PLAN_ONLY，`--execute`且负责人已明确批准sector4范围后才可调用原SDK；无PI签名/nonce/次数限制。

1. 使用已有C双份完整备份、Options、身份回执；安装当次核对当前C身份、运行状态与实际Flash。未知HALT/ROM或字节漂移停止目标，继续离线排障，不强设PC/MSP。
2. 仅写完整sector0和sector4块：原备份为底，覆盖两段；两个范围内未被新镜像占用的字节也保留。SDK同一次下载事务提交两个明确范围，禁止整块跨洞BIN、mass erase、解除保护及Options写入。
3. 下载后完整读回对预期，单独核对Options和身份；全部一致才允许按真实向量Reset/Go。原生短写、验证失败、Close异常不自动反复重刷。
4. 必要回退使用原C44520备份，将同样sector0/4恢复原字节；其他区域一律不写。回退工具离线通过，实板回退新布局尚NOT_RUN；SDK隐式副作用与掉电中断写入风险仍保留。

具体CLI的备份路径/安装回执由本地忽略的 `node-b/build/final-unified-current-pointer.json` 指向受限作业目录；不将UID、配置或原始Flash提交。负责人一次确认范围覆盖本合同后续C候选必要更新及恢复，不对每次软件复测重新签发。

## 唯一阶段清单

- [x] 新真实统一C离线构建、分段ELF/HEX、配置保留及RAM/CCM/DMA布局：OFFLINE_READY。
- [x] 一个主入口/网络owner、CAN优先和有界音频推进：实现及定向Host通过；实机时延尚NOT_RUN。
- [ ] C-only真实录音/125块/ASR/TTS、统一运行STOP、网络故障、CAN入口负载与水位：NOT_RUN。
- [ ] B41516+C真实300秒、B温度屏/源帧/CAN/云/WSS关联：NOT_RUN。
- [ ] A42608+B41516+C新同窗、非人体NIBP与事实语音问答：NOT_RUN。
- [ ] 确定性事实/简短回复接入隔离worker及负例：待P3；现有工程确认worker不冒充事实问答。
- [ ] 并发/30分钟、必要24小时、三板版本包及正式部署映射：NOT_RUN，不提前定版。

未关闭：真实CPU/栈/中断/DMA/队列水位、持续监护负载下音频能否及时获调度、热点新鲜SNTP及真实重连、SDK隐式副作用、MIC实物PCB修订与当前接线核对。RR24/30失败、RR15 SOURCE_UNKNOWN/ROOT_CAUSE_UNRESOLVED、旧TEMP180和绝对标定继续保留。GY641仍为物体温度To，NIBP为最近完成结果/90秒有效，非人体数据保留synthetic标签。中国家庭教学阈值按本合同冻结为SYS≥135或DIA≥85；不作单次诊断，不以低于阈值断言正常或偏低。

下一步只申请一次C sector0/4精确范围确认；之后按当前接线确认进入C-only，再推进B+C和ABC。A/B源码未改；没有正式服务切换、main合并或最终发布声明。
