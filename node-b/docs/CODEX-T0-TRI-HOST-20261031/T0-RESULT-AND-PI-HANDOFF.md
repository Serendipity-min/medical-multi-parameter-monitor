# T0纯Host三板接口集成结果与交接

2026-10-31，Asia/Shanghai。**T0_HOST_INTERFACE_INTEGRATION_PASS；最终完整运行器exit0。** 这是明确合成输入下的协议、网关、Hub/UI接口集成，不是A/B/C实板并发或临床验证。用户已授权本轮T0；没有要求上电/改线，也没有SDK/COM、RESET/HALT/GO、B5START、Flash或云业务动作。

父提交 `e78cd19197bda2f9986355e28ecf05ce5cf02fb9`；独立分支 `codex/b5-tri-t0-host-20261031`。范围继承M0的P7计划，只修必要夹具/薄适配；没有合并A/B4/P5/P6/main分支、修改算法或冻结正式评测器/Criteria。

## 实现与执行边界

| 层 | 本次真实执行的软件 | 替身/未覆盖边界 |
|---|---|---|
| A | 实际CANopenNode与通用MpOD的A生产/映射模型，PPG/SpO2/PR/NIBP合成数据 | 未执行A传感器、NIBP驱动或实际A整机应用；M0固定A源提交/OD仅作接口来源，不冒称A实装BIN已核对 |
| B | 实际BIO_V2、B OD/CAN适配器、GY641解析器与有效期逻辑 | 仅UART字节到达边界替身；固定帧33.07°C，30–36s暂停字节；无ADC/温度硬件或真实SKX输入 |
| C | 实际双CAN协议、网关、Router、序列化与coreMQTT序列化器 | 总线/邮箱为内存替身，MQTT消费为本地drain；不是C49132原B-only网络镜像，也不是MQTT网络端到端 |
| Backend | 实际decode_mqtt与Hub，逐条消费C输出并派生快照 | Broker连接状态是显式内存夹具，网关ONLINE由合成状态补齐；未启动Backend/Broker/WSS服务 |
| UI | 实际MonitorStore/viewModel消费Hub文件快照 | Node纯函数/状态测试；没有浏览器、WebSocket、真实DOM/画面或WSS传输 |

复用 `node-b/tools/run_b4.py`，新增可选 `--temperature` 与新输出目录参数；无参数仍是原TEMP-disabled用例。旧配置的TEMP INVALID期望合理，不将其当生产缺陷；新配置才编译B_TEMP_ENABLED和真实温度解析器。模拟器按模式分别断言TEMP有效/无效/恢复，并把启动状态在内的全部合成出口明确标MOCK；没有改生产源/有效位。

新增Hub→UI文件检查覆盖A/B身份、250/50Hz批次、单位、HR无效清空/恢复、REPLAY不覆盖实时、B新BOOT与旧epoch高seq不复活、普通5s过期与NIBP90s域分开、网关换代及慢订阅者有界最新快照。HR/RESP同时有效来自已知QRS+RESP合成输入，不据此解释历史SKX RR15。

## 实测结果与真实退出码

| 检查 | 结果 |
|---|---|
| 最终完整回归 | 14项检查PASS；12项native exit0，I²S2引脚冲突/混合ABI两个预期负例native exit1；整体exit0 |
| B原采样→CAN | 正常90s 22500 ECG / 4500 RESP真实编码；抖动用例另保留；TIME过期、拥塞及NMT隔离assert通过 |
| 双总线常态 | ECG222批、RESP88批、A PPG90批；HR有效81条、RR有效64条；正常段router_drop=0 / malformed=0 |
| 温度→C→Backend | 88条，83有效33.07°C、5条无效null；有停帧超期及恢复，未把旧值续活 |
| 模拟5秒消费暂停 | router_drop=0，REPLAY50条；这是虚拟时钟/内存消费暂停，非真实MQTT/WiFi阻塞 |
| Hub输入/UI | 正常文件976条，8个Hub状态场景，3项UI测试全部通过；只内存/文件，无服务器 |
| 原TEMP-disabled定向非回归 | 原生产者编译、原生产者、双CAN网关、Backend共4项均exit0；没有重复整套旧矩阵 |
| STOP | 复用M0已通过的真实bxCAN代码RAM-MMIO STOP组件及源SHA；本轮未执行B5完整生命周期，不把组件PASS当实板STOP/Close证明 |

222个ECG批不等于证明22500点全部端到端保留；启动质量转换/不完整批次及评价边界仍按真实代码处理，没有插值、拼批或以源样本总数替代出口计数。模拟器后段有故意注入的错总线/畸形帧/缺点/重复/BOOT、单段邮箱拥塞和Router容量溢出负例，预期计数上升被断言，不把“正常段0错误”扩写成全程无错误。

第一次完整运行所有14项已满足预期，但末尾打印EFS路径时错误使用repo-relative路径，进程实际exit1；原receipt/log/脚本完整保留。仅修打印路径表达式，提前登记一次补充完整复验，最终exit0，未改输入、断言或判据。最初反例准备还误用温度单位C，被严格模型拒绝exit1；改成合同单位degC后才命中旧夹具TEMP-invalid断言，原输入/失败日志均保留。

初版[预注册](PREREGISTRATION.json)在完整运行前冻结，路径修正的[补充登记](PREREGISTRATION-AMENDMENT-01.json)也在复验前冻结。原失败、最终18项原生检查、日志/脚本/夹具SHA见[执行与结果](../../evidence/CODEX-T0-TRI-HOST-20261031/execution-and-results.json)；[旧配置非回归](../../evidence/CODEX-T0-TRI-HOST-20261031/legacy-temperature-disabled.json)单列。

公开[完整性清单](EVIDENCE-HASHES.json)可复算。全部编译产物、合成CAN/Canonical/Hub快照、日志与执行脚本留在新EFS job，由忽略文件 `node-b/build/tri-t0-pointer.json` 定位。Git不放这些原始制品、真实ADC、UID、全Flash/options或凭据。本轮未读取新现场敏感资料；M0旧EFS保护缺口不因T0完成而消失。

## 未关闭项与停止点

T0通过只扩大Host接口证据。A实装BIN/完整构建链仍UNKNOWN；C49132仍B-only，不能直接连接A+B开启并发，双CAN候选的应用空间、供电/终端、CAN2 PB12/PB13及音频冲突、CPU/队列/公平性/真实负载均需独立证据。当前Host使用通用64槽Router，不替代B5最终24-live/56-history的实板资源验收。

RR15正式NOT_PASS/exit3、SOURCE_UNKNOWN/ROOT_CAUSE_UNRESOLVED，SDK Open/Close原生副作用、冷启动ROM、绝对测量校准、云租期/部署/ACL、Gate F/Security Gate保持开放。没有调整HR阈值、按RR模式屏蔽HR、伪造Lead-Off或改变250/50Hz采样/诊断ABI。

本轮不需要实板，当前不要按本包上电/改线。[现场入场缺口](FIELD-ENTRY-GAPS.md)集中列出后续条件。建议先独立冻结A完整候选身份与C双CAN可构建候选/资源及回退范围，再申请T1单A→C，M1单B多速率、T2/T3及云端各自独立签署；不能凭T0 Host PASS跳入现场。提交推送后停止，等待PI下一轮决定。
