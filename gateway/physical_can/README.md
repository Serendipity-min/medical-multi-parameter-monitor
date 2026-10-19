# Gateway-C CAN1 物理候选（仅软件验证，未烧录）

固定 P4 起点：`67f5f57bd82c6e326e9e78ec9540481c80105e5f`。本目录是独立 target；原 `gateway/mqtt/build.py`、main、mp_stack、mp_adapter、bxcan_loopback 均原样保留。物理 target 用自己的 main/stack/adapter/bxcan_physical 替换模拟入口，复用原 Router、Model、CANopenNode 和 coreMQTT v2.3.1、MQTT/TLS/ESP8266 AT 实现，未修改生产 topic/schema 或凭据存储。

## 行为与构建

- 只 CO_new Gateway（Node-ID3）；A/B 仅有十路 RPDO 镜像、Heartbeat consumer 和 EMCY 观察，无本地 A/B CO 实例或采样器。A/B/R/E 模拟控制入口不进入此 main；G 是显式本地重初始化，D 保留原网络断开测试入口。
- 正常 CAN1，PA11 RX / PA12 TX AF9；运行时读取 PCLK1，16MHz 用 2×16TQ、42MHz 用 6×14TQ，均为 500k。BTR 不设置 SILM/LBKM。当前 Gateway 系统配置是 HSI/APB1 16MHz，不能照搬 A 的 42MHz 常数。
- Tx 非阻塞，原队首仅硬件 RQCP+TXOK 后才出队；未 ACK 100ms、发送错误或 Bus-off 锁止链路、清队列、撤销在线身份，需显式重初始化。ABOM 不绕过软件锁止。初始化有 Tick/CPU 双重预算。Host 只验证状态策略，寄存器和实际电气 ACK 仍待 H2。
- 只有物理 Heartbeat ACTIVE/OPERATIONAL 才在线，超时 1500ms。新 boot/generation 清接收新鲜度；PDO 必须 DLC=8，质量/时间/标量独立 1500ms 新鲜度门控。未收 B 时立即周期报告 OFFLINE，无 B 测量值。
- 外部 Boot-up 使用 Gateway 观察代次更新会话，即使 Node-A 掉电后 RAM generation 重新为1也不会复用旧身份；来源位变化也丢弃部分波形，不能混拼 LIVE/MOCK。
- TIME 只有上层 SNTP epoch 非零才每 10s 发；Node-A 30s 超时撤销 UTC。采样时间采用有符号 tick 差，支持跨秒/回绕附近的点，拒绝不合理旧时刻/未来时刻。未同步/过期不伪造 LIVE 有效采样。CAN TIME 的授时者身份依赖已核验的隔离物理总线，不宣称密码学认证。
- 独立候选以64位扩展累计毫秒，CAN1 TIME、采集比较与 Gateway 状态时间跨49.7天计数回绕仍递增；原 P4 32位调度、时效差值与 MQTT 实现不改。
- 波形每 50 点一批；采样间断、有效性变化、boot 或 PDO 过期丢弃未完成批次。质量 bit8 表示 Node-A 接收时基重采样，bit31 保留来源语义。

本机普通验证入口：

```text
python gateway/physical_can/build.py --host
python gateway/physical_can/build.py
python node-a/tests/run_host.py --phase a1-final
python node-a/tests/build_keil.py
```

Host 正常测试与 wire 测试共用一个临时 exe，顺序运行，避免相互覆盖。跨栈 wire：运行 Node-A Host 的 `--wire` 保存 CO_CANsend 原始记录，然后 `python gateway/physical_can/build.py --host --wire gateway/physical_can/evidence/node-a-can-frames.txt`。隔离 Broker 复现用 `python gateway/physical_can/tests/run_wire_broker.py --runtime <已有隔离 Mosquitto runtime>`；Windows 委派到已安装 HERA-C3，**不下载安装包、不联系生产 Broker**。测试启动的监听固定 loopback、临时端口与合成认证，并清理自有 PID。

wire 记录来自合成传感器输入 + 真实 Node-A 栈 + 真实候选 Gateway 栈；canonical 中 LIVE/synthetic=false 用于验证实板模式的字段契约，**不是人体或真实板卡测量证据**。结果 JSON 明确 HOST/NOT_RUN。359 条实际 Host CAN 输出经候选产生 24 条 MQTT 消息/19 次匹配 PUBACK，再由原 Backend 严格解码，Node-A 值 98%、72bpm、118/76mmHg，PPG=50Hz/50点，B=OFFLINE。未执行 ESP AT/TLS 网络、物理 CAN、腾讯云端到端或板卡烧录。

原回归：CANopen 12、Router/pipeline 11、restart 17；P5 Host 42；隔离 Broker 30；Backend 28；原 P4 MQTT ARM 与本物理候选 ARM 均退出 0。原结果 JSON、失败记录和 source/config SHA 位于 evidence。初次 wire 暴露 Node-A 0x1804:04/05 描述错误，修复后重新运行；ARM 初次产物构建成功但 SDK 位于仓库外导致清单脚本退出 1，也保留原日志并修复记录器。

## 引脚占用（源码/合同核对，不是接线放行）

|用途|Node-A|Gateway-C|约束|
|---|---|---|---|
|CAN1 RX/TX|PA11/PA12 AF9|PA11/PA12 AF9|当前 USB 数据复用冲突；不跨板直连 MCU 引脚|
|调试 USART1|PA9/PA10|PA9/PA10|原配置保留|
|血氧屏 USART2|PA2/PA3|不占用|原双屏不改|
|血压屏 USART3|PB10/PB11|该对引脚用于 ESP8266|两块 MCU 各自资源，不同板用途不同|
|HKB-08 UART5|PC12/PD2|不占用|原血压模块保留|
|UNO/AFE4490 USART6|PC6/PC7|不占用|原接收 ISR/双环不改|
|CAN2/P4|本轮不用|本轮不用|PB12/PB13 与未来 I2S 资源复用相关|
|未来 I2S2|不实施|PB12 WS/PB13 SCK/PB15 SD 暂定|只预留，不接麦克风/不实现 PCM|

## H1/H2 硬件准入清单（本轮全部 NOT_RUN）

用户当前报告 P6 为 PA11→D−、PA12→D+；唯一提供的是一张局部照片，未提供 A/C 分别带身份标签的全板照片，不能据此证明两块板的 CAN 路由或端子编号。该状态按合同记为 USB 档，不作为 CAN 已连接证据；本轮没有请求或执行带电改线。

另行授权 H1 后，在完全断电状态分别核对 A/C 身份、CAN1/U3/R7/P6、板卡修订及导通关系。合同图纸要求 P6 1–3、2–4 连接 CAN RX/TX；目前 USB 3–5、4–6 档不能提供 CAN 通路。实物编号/导通或芯片/电平与图纸不符即停止，不凭照片方向盲插。

- [ ] 用户先批准现场断电检查；分别补齐 A/C 全板与跳帽/端子特写，确认板卡型号、U3=TJA1050、R7=120Ω、CAN1 端子 2=H/1=L；必要时查完整原理图与板卡修订。本轮仅有合同与原图裁剪，不冒充重新检查过完整六页 PDF。
- [ ] 断电核实 MCU PA11/12 到 U3 的收发路径，USB 数据路径与 CAN 互斥；SWD 保留。USB 供电和 USB 数据是不同事项。
- [ ] 两板各自独立供电，确认 U3 的 5V 实际存在；只计划 CANH-H、CANL-L、参考 GND-GND，不跨板连 +5V/+3.3V，不做 TX/RX TTL 交叉。
- [ ] 全总线断电测 H-L 约 60Ω，检查无短路及绝缘；A/C 位于两端，各一只 120Ω。三板扩展预留 B 在中点、短支线，B 第三只终端需在另批断电维护中断开，不能假设软件可控制 R7。
- [ ] 另行批准读取/保存现装 A/C 全 Flash 可恢复备份、镜像身份与恢复方案；本轮未连接调试器、未读取 UID/Flash，不把设备 UID/凭据纳入仓库。
- [ ] H1 记录经用户确认后才申请 H2 烧录/上电/跨板与云端网络窗口；不能把本轮 Keil/ARM/Host PASS 当准入。

H2 应顺序记录 CAN 错误计数/ACK、0x701 和 NMT、0x181/381/481/681 实际帧及周期、缺测/掉线/复位/重新授时，再比对 RPDO→Router→MQTT→Backend→大屏的 seq/session/时间/数值。Node-B 不接即 OFFLINE。Bus-off、时钟不可靠、错号、影响双屏或无法恢复时停止。PUBACK 不是大屏已接收的证据。

物理层参考：[TI SLLA270 §4.5/4.8](https://www.ti.com/lit/an/slla270/slla270.pdf)；该资料只支持终端/干线原则，不证明本实物板卡接线已合格。
