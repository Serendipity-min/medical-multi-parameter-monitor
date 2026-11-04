# M1 离线迁移结果与本轮接线说明

**结论：M1 离线构建和所列软件回归通过；候选未安装，点对点、三节点共线、五板实测和事实语音均未做。** 工作继续在 `codex/five-node-single-module-v1`。M0 标签 `baseline/abc-unified-pre-split-v1`、提交 `26e695ffda43a7a76aa54d1c4e3a5631ac0dc42e` 保留。新合同父线为 `fc4dc4597c28832f6eba40fcac2ddce5ee0fb9e5`。

## 1. 这次实际确认的电阻与接线

下表是负责人按断电分测要求反馈，执行人没有远程读表或接触硬件。

| 单独隔离的接口 | C.CAN1 | C.CAN2 | A.CAN1 | B.CAN1 | D.CAN1 | E.CAN1 |
|---|---:|---:|---:|---:|---:|---:|
| H–L | 120 Ω | 120 Ω | 120 Ω | 120 Ω | 120 Ω | 120 Ω |

| 仅连接两个接口 | H–L |
|---|---:|
| C.CAN1 ↔ A.CAN1 | 60 Ω |
| C.CAN2 ↔ B.CAN1 | 60 Ω |

负责人本次纠正：此前面包板的 41 Ω 组合为 **C.CAN1＋B.CAN1＋D.CAN1**。旧 05/06 中的 E 是更早的口述记录；今后按本次 B/D 组合理解。原状照片已复制到本机忽略的 `node-b/build/five-node-m1/owner-wiring-before.jpg` 并记 SHA256，原照片保持不变，未将原照片上传 Git。

六个原口各120 Ω、两口并联60 Ω，支持当前底板具有固定端接的判断。图纸第5页也把 CAN1 的 R7、CAN2 的 R1 各120 Ω直接跨接 H/L；P6/P4 是逻辑信号连接，不是 TERM 开关。41 Ω与三只120 Ω并联相符；当前新增终端电阻数量为 **0**。不再做同样的全套重复分测。

## 2. 现在怎样接

**当前保持原两条点对点线，D/E 的 CAN 原口暂不并进来：**

```text
第一段：C.CAN1 H ───── A.CAN1 H       C.CAN1 L ───── A.CAN1 L
第二段：C.CAN2 H ───── B.CAN1 H       C.CAN2 L ───── B.CAN1 L
参考地：沿原非隔离台架接法连接对应 GND；不互并各板 3V3/5V 输出。
```

认板卡上的 `CAN1/CAN2` 与 `H/L` 标识，不按照片的线色或插座左右推断。两段的 H/L 不能通过面包板接成一条。GND 共地本身不表示两段 CAN 混线。泵的功率电流不经过面包板。

若保留面包板作接点，先在空板用通断档确认：通常同一个数字的 a–e 五孔互通，f–j 另五孔互通，中沟两边不通；不同数字之间不通，电源长轨另算。**把 H、L、GND 放进三个互相隔离的五孔组**，另一个总线用另外三个孔组。照片中的零散电阻及导线归属不能只靠外观确认，不把它当作已确认端接或照着颜色接线。使用短支线和 H/L 双绞线，实际主干、最长支线长度仍待记录。

## 3. 没有外置收发器时，后续点对点顺序

以下是现场窗口的接线计划，本轮没有执行刷写、传感器/屏迁移、通电或泵控。每次转线前全部断电，拔掉可能反供电的 USB/J-Link；先确认目标板、接口电平及候选写入范围。

| 窗口 | 先移开的 CAN 支路 | 临时接线 | 端接条件 | 此时能签的结果 |
|---|---|---|---|---|
| D 温度与屏 | B.CAN1 从 C.CAN2 那段脱离，避免原线还留在面包板里 | C.CAN2 H→D.CAN1 H；L→L；参考 GND→GND | 只剩 C2、D1 两个120 Ω口，整段约60 Ω，不外加电阻 | D 本地温度/屏、D→C2→隔离后端/网页的点对点结果 |
| E 血压与屏 | A.CAN1 从 C.CAN1 那段脱离 | C.CAN1 H→E.CAN1 H；L→L；参考 GND→GND | 只剩 C1、E1 两个120 Ω口，整段约60 Ω，不外加电阻 | 非人体工装上 E 本地人工启停、完成代次/网页与90 s失效 |

局部窗口结束时先断电，再按照片与标签恢复 C1–A1、C2–B1；若两次局部窗口连续进行，也逐次记录当前哪块板接在哪一段。D/E 原程序无需备份，沿用负责人决定。A/B/C 原有恢复依据不受该决定影响。

**五板最终接法仍是：C.CAN1 的主干两端为 C/A，中间短支线接无终端 E；C.CAN2 的主干两端为 C/B，中间短支线接无终端 D。** 两个中部节点的额外120 Ω需要处理后，才能做三节点共线。当前没有 TERM 开关或外置模块时，先采用上表点对点即可；不能把三个固定120 Ω原口重新并起来验五板，也不能靠增加、串联或短接电阻解决。

免焊扩展路径沿用06：D/E 各使用一块逻辑与3.3 V兼容、支持500 kbit/s、终端可关闭或无固定120 Ω的高速CAN收发器；该板原 CAN1 H/L插座保持空置。具体模块和实板针1未核实前，不按通用 TX/RX 字样或插座朝向盲接 P6。无需为了点对点测试先购买或改板。

## 4. M1 完成了哪些软件工作

- A=1：五板编译配置不初始化血压屏/泵子系统、不注册血压屏探活，不产生有效 NIBP，保留血氧/PR/PPG。
- B=2：复用当前BIO与R6调度路径构建，不启用温度模块/屏，保留原250 Hz ECG、50 Hz RESP和HR/RR。
- D=4：独立应用复用 GY641 UART4、USART3温度屏和CANopen，未链接BIO/ECG/DSP；本地屏与PDO均调用真实 `BTemp_Get`，串口停帧或帧龄超2500 ms无效。
- E=5：独立应用复用HKB-08B+ UART5、血压操作屏和本地状态机，保留完成tick、打包SYS/DIA、90 s及新完成代次语义；通信重启后的保留旧结果不能自动获得新测量资格。
- C=3：保留两套OD/协议栈，每段复用两个远端镜像槽；总线1为A/E，总线2为B/D，逐节点保存质量、启动观察代次、在线、序号及血压去重。只给A/B分配波形缓存。错段、错角色PDO和后退质量代次拒收。
- 消息/云/Web：Topic支持A/B/D/E并核对角色。Backend以 `MPM_NODE_PROFILE=three|five` 选择静态白名单，默认three；AI事实来源同步选择D温度/E血压，WSS快照带 `node_profile`。网页据此显示D/E状态、实际来源和物体温度UART4标签，缺失/过期不显示旧有效数字。

五板配置须同时使用本轮五个应用和 `MPM_NODE_PROFILE=five` 的隔离Backend/事实服务；混用三板A/B、五板C或旧云白名单会被拒收或缺流。三板默认配置保留；要恢复已验收M0原字节，仍按冻结标签及原制品清单，而不是把当前源码重建物称作原实装。

M1没有完成测量事实语音：现有worker的空事实工程短答、旧下行MR01仍保留。后续需要按04/06绑定E完成身份、截止时刻并在C提交TTS前复核；“测完再问仍有效可闻”和“90 s后拒答”各自实测，分类规则继续未启用。当前C候选沿用B5台架的合成来源标记，不可据本轮测试宣称已经提供LIVE测量语音。

## 5. 制品与资源

[候选及SHA清单](M1-20261104/RELEASE-MANIFEST.json)列出各板BIN、AXF/ELF、map、符号和构建输入证明。各板为独立候选，不能互刷；清单中的写入区是构建布局计划，实板身份/Flash原状未核实，**不构成安装准入**。

| 板 | 应用大小 | 构建布局计划 |
|---|---:|---|
| A | 33,380 B | 0x08000000，覆盖sector0–2 |
| B | 40,032 B | 0x08000000，覆盖sector0–2 |
| D | 24,544 B | 0x08000000，覆盖sector0–1 |
| E | 29,416 B | 0x08000000，覆盖sector0–1 |
| C | boot 392 B + code 55,332 B | boot在sector0、code从0x08010000起在sector4；保持分段 |

| C资源 | M0实际基准 | M1最后构建 |
|---|---:|---:|
| Flash总加载 | 54,900 B | **55,724 B** |
| sector4余量 | 11,028 B | **10,204 B** |
| 普通SRAM扣除原堆栈预留后余量 | 15,808 B | **15,552 B** |
| CCM余量 | 1,536 B | **1,536 B** |

新增Flash 824 B、普通SRAM 256 B。该表证明链接布局仍可容纳，未证明真实五板容量、端到端时效或长稳。未扩大历史缓存或放宽5 s监护/90 s血压要求。

## 6. 已执行验证与复现入口

| 项目 | 结果 |
|---|---|
| A/B/C/D/E目标构建 | PASS；A/B/D/E用既有ARMCC5，C用既有ARM GCC；C原IRQ向量、DMA/CCM布局检查通过 |
| 五板C接收/OD/Router/JSON | PASS；错段与旧角色拒收、D/E独立状态、温度源龄、重复完成不续期、同值新完成、旧质量代次后退、离线恢复旧完成不复活、90 s旧完成拒收 |
| D/E实际生产者Host协议 | PASS；真实CANopenNode、OD和应用，替换UART/压力与控制器边界；身份、SDO、无波形冒发、温度停帧、血压过期与通信重启旧结果阻断 |
| 五板Backend/WSS/事实来源 | PASS，6项；包含真实FastAPI TestClient WSS，MOCK输入，不是实物LIVE问答 |
| 三板Backend血压/监护相关回归 | PASS，26项 |
| 前端构建/状态测试 | PASS，16项 |
| 浏览器 | PASS；D/E独立状态与来源、详情、D离线B在线、过期血压隐藏；全部明确合成输入 |
| 原B协议/双CAN软件回归 | PASS，包含采样抖动、单位、250/50 Hz通路和MQTT压力；两个编译负例按预期退出1 |
| 原ABC入口/双CAN驱动相关Host | PASS；总线隔离、错误、STOP及有限重试路径 |
| 原M0排队IRQ/重新授时/回绕 | PASS；原时间及新鲜度边界未放宽 |
| 实板安装、点对点、三节点、五板、可闻事实问答 | NOT_RUN |
| 安全扫描/Security Gate、正式云、main合并、24 h长稳 | NOT_RUN |

离线命令（在项目根目录，均无设备操作）：

```powershell
python tools/build_five_node.py A  # B/C/D/E分别调用
python tools/test_five_node_host.py
python tools/test_five_node_producers.py
$env:MPM_NODE_PROFILE='five'
python -m pytest cloud/backend/tests/test_five_node.py -q
$env:MPM_NODE_PROFILE='three'
python -m pytest cloud/backend/tests/test_ac_nibp.py cloud/backend/tests/test_monitor.py -q
```

前端在 `cloud/web` 运行原有 `npm run build`、`npm test`。本轮复用锁文件相同的既有node_modules，无依赖安装。浏览器脚本 `tools/test_five_node_browser.py` 使用本机临时端口和合成WebSocket，静态文件在本地build的webroot；复现前将最新dist复制到 `node-b/build/five-node-m1/webroot/medical-monitor/`。

证据摘要与截图见本目录M1子目录；完整构建日志和独立轮次在清单所列本机build目录。早期软件夹具断言与预览辅助进程失败是开发过程记录，没有转写成板卡故障或现场失败。原始M0及更早失败台账不修改。

当前Host只验证质量报文携带的启动代次、接收时序和已有协议字段；不将同CAN-ID报文解释为经过发送者认证，也不声称能从没有逐帧启动身份的旧标量报文独立证明物理来源。真实重启/延迟场景按现场窗口继续核对。

原RR15源真值、RR24/30、TEMP180、A历史覆盖、绝对精度、ROM/SDK副作用和24 h长稳继续保留原状态。

参考：[06合同](06-CAN-Wiring-and-M1-Contract.md)、[TI CAN物理层](https://www.ti.com/lit/an/slla270/slla270.pdf)、[NI端接说明](https://www.ni.com/en/support/documentation/supplemental/09/can-physical-layer-and-termination-guide.html)。
