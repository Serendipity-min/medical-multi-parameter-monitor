# 实现与离线核验

## 1. 实现范围

| 部分 | 本轮结果 | 边界 |
|---|---|---|
| C自动启动 | 显式 `--five-appliance` 构建初始化双CAN、音频和PE3后才开启协作回调；向1/2/4/5发NMT；有效配置自动尝试网络 | 不写配置；缺配置保持本地CAN；没有可信授时不伪造UTC |
| 网络失败 | 2/4/8/16/30/30秒合作式退避，仍推进本地CAN；成功连接MQTT重置2秒 | AT帧边界不明时沿用停止网络、等待同步的处理，不盲目重发；物理断网恢复NOT_RUN |
| A/B/D/E | 复用现有自采集/CANopen上电Operational；E仍只由屏启动/停止气泵 | 四板源码与实装制品未改；没有K1/网页泵控命令 |
| K1 | PE3上拉、低有效、30ms消抖；按下开始，再按结束；长按不重复触发 | PCM不足1秒时继续录音并提示；原DMA最大32,000点/2秒不变；实际引脚电平NOT_RUN |
| 音频 | 实际1–2秒PCM逐点CRC、MC01按实际长度分块；末块仅传输层空位清零 | 不补PCM点、不放大64KB CCM、不改原采样率；默认旧2秒路径保留 |
| 回复 | 新构建使用MR02，绑定录音session/CRC、B5身份、源时间、流/节点、序号、会话及失效期限 | 不接受仅换Topic的P6V1或旧MR01；有效性与当前C观察身份不符时拒绝 |
| 事实/API | 五板映射；高压/低压独立选流；D物体温度；5秒/90秒精确失效；模型耗时后重查 | 数字由可信事实模板生成；历史/无效/离线不播旧数；默认MOCK且语音DISABLED |
| 网页 | 显式 `five-appliance` 模式默认只选GW-B5-001；温度D、血压E静态与实时来源一致 | 原production模式保留；URL不能在五板模式另选旧网关；PUBACK不标为可闻 |

新API源码从已核对H3参考定向引入，原始文件SHA见SOURCE-INPUTS；不是部署或整个分支合并。旧 `cloud/microphone/worker.py` 仍是MR01确认文本流程，**不能直接拿它启动本候选**。新 `appliance_worker.py` 已接好隔离MQTT→有界重组→whisper子进程→同进程ASGI事实API→MR02的运行入口；ASR/HTTP端口可注入离线测试。真实MQTT订阅、CPU ASR、隔离服务运行及可闻播放均未执行。

自动构建仅取消原诊断运行窗口的自动停止，以满足持续自动运行；未改变医疗5秒/90秒有效期、音频整轮300秒或装配90秒超时。保留串口X/STOP维护处理和不加新选项的手动构建。CAN错误累计不再因邻板暂未供电而全机停止，错误仍计数；这不是把错误记为通过，也不能恢复已溢出的原始数据。

## 2. 实际运行的验证

| 检查 | 结果 | 证据 |
|---|---|---|
| 真实C自动入口＋端口替身 | 36,099检查PASS | 缺配置本地运行/不授时，初始化回调不抢跑，6次连接失败仍处理CAN，第7次成功进MQTT/订阅并重置退避；startup-run.txt |
| 真实C K1/CRC/TTS状态机 | 1,494检查PASS | 1.010秒真实长度64块、2秒125块，消抖/长按/短按，错会话拒绝，身份变更拒绝，固定拒答，期限到达STOP→ACK→QUERY→IDLE；keys-short-audio-run.txt |
| 默认旧C音频路径 | 1,947检查PASS | 旧MR01、固定125块、预算及停止语义；legacy-audio-run.txt |
| Python/真实C跨语言/ASGI | 53项PASS | C生成MC01→真实AudioAssembler→替身ASR→worker实际ASGI调用→真实FastAPI/事实→P6V1/MR02→真实C解析器；错源/CRC/身份、过期、重复、无UTC、模型等待后源龄、隔离Backend/WSS、ASR成功/失败与临时PCM清理；TEST-RESULTS.json |
| 网页 | 两模式定向检查＋16项原受影响回归PASS；TypeScript与Vite构建PASS | 五板/旧默认、D/E来源、历史/失效语义，新增上下文状态文案 |
| 原供应模拟重跑 | 原生退出0；26 PASS/7历史KNOWN_GAP保留 | 真实BioV2 C，合成同窗75,000次调用，69,729点HR/RR同时有效，首次21.084秒，末值60/18；Hub接收3,151条合成消息 |
| ARM | 自动五板候选及旧手动五板构建均原生0 | IRQ向量检查通过；仅链接构建，无设备操作 |

模拟中B同时有效只证明原算法能接受该合成并行输入，Hub直接输入不经过真实CAN/AT/MQTT，因此不证明8.08帧/s容量问题消失。ASR、网络、DMA与喇叭使用替身的环节不升级为物理PASS。

开发中发现并修正：初版Host夹具的函数const签名/源文件路径/嵌套事件循环和旧文案数量断言不匹配；最终均通过。审阅还发现初版C事实身份比较误用了原PDO generation，已改为与B5 emit真实输出一致的“网关session＋observed_boot”，并补了正负例。首轮构建/失败记录保留在忽略作业目录，不覆盖历史现场失败。

## 3. 最终ARM资源（未安装）

| C资源 | 实装历史 | P1离线 | 本候选 |
|---|---:|---:|---:|
| boot | 392 B | 392 B | 392 B |
| sector4加载 | 56,072 B | 56,144 B | 57,744 B |
| 总Flash加载 | 56,464 B | 56,536 B | **58,136 B** |
| sector4余量 | 9,464 B | 9,392 B | **7,792 B** |
| SRAM静态及保留段总和 | 115,720 B | 115,720 B | 115,772 B |
| CCM PCM | 64,000 B | 64,000 B | 64,000 B |

SRAM统计含原32KB保留区，另有4字节段间对齐；尾部连续余量15,296 B。CCM余1,536 B；不是可分配的额外长录音缓存。以上是静态链接段，不是实板栈高水位，也没有为FreeRTOS建立新任务栈预算。DMA保持普通SRAM，PCM保持CCM；CAN IRQ3、音频IRQ8不变。新候选SSL测试端口28895与旧默认1883区分，仅是拟议隔离参数，没有监听服务。

候选制品目录：`node-b/build/b4-c-arm-20261107T025348486628Z`。镜像SHA与段表见ARM-RESOURCES；仅sector0/4布局可供以后评审，**不是当前刷写授权**。A/B/D/E和当前C实装清单仍以[旧CURRENT-IMAGES](../FIVE-NODE-MIGRATION/FIVE41-20261106/CURRENT-IMAGES.json)为准。

## 4. 复现

在本工作树根，使用现有GCC/Python，不安装新依赖：

```powershell
python -X utf8 gateway/microphone/run_five_appliance_tests.py --cc C:/mingw64/bin/gcc.exe --out node-b/build/five-appliance-recheck
$env:FIVE_APPLIANCE_NATIVE_OUT = "$PWD/node-b/build/five-appliance-recheck"
$env:MPM_NODE_PROFILE = 'five'
python -X utf8 -m pytest cloud/ai/tests/test_five_appliance.py cloud/microphone/test_protocol.py -q
python -X utf8 gateway/dual_can/build_arm.py --b5 --egress-final --tri --unified --split-flash --five-node --five-appliance
# 保留手动构建：同上移除 --five-appliance
```

在 `cloud/web` 使用现有node_modules：

```powershell
node tests/five-appliance.mjs
node tests/run.mjs
node node_modules/typescript/bin/tsc --noEmit
node node_modules/vite/bin/vite.js build --mode five-appliance
```

供应模拟在作业目录的副本重跑，设置`CC=C:/mingw64/bin/gcc.exe`后运行原`scripts/run_isolated_sim.py`；原附件未改。其5个快照Git blob校验均通过。当前Python3.11、FastAPI0.141.1、Pydantic2.12.5、pytest9.1.1、httpx0.28.1；FastAPI版本与原锁定0.135.1不同，部署环境复核仍待做。网页复用现有Vite7.3.5/TypeScript5.9.3，不安装依赖。

## 5. 保留项、回退与后续

P1 router/egress、四板采集代码、BioV2及实装清单与f9bdff8一致；M0标签及R6指针未改（PRESERVATION-CHECKS）。离线实现结束时未提交/推送；本次后续按负责人授权执行独立分支Git交付，见[PI审核入口](PI-REVIEW.md)，原工作树保持原状态。没有软件或硬件回退动作。软件可直接回到原工作树f9bdff8；以后需要实板恢复时另按身份及受限分区授权执行，不能照本报告自动刷写。

仍未通过：出口容量与全量点覆盖、A入口间断根因、41Ω物理裕量、实体K1/自动冷启动/断网恢复、真实ASR/事实播报及可闻、生产隔离端部署。FreeRTOS只保留待决，不以本轮功能实现代替容量裁定。

后续只建议分项验证：先评审隔离TLS入口/凭据来源及各板实际镜像，再单独验证自动入口、K1/短音频和固定拒答；在实测出站服务率与历史/音频余量满足要求前，不组织“完整五板＋语音300秒通过”窗口。本轮设备保持既有断电状态，无上电指令。
