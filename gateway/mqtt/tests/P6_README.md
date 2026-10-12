# P6 下行 / TW-TTS 脱机适配

`GATEWAY_P6_VOICE` 默认 0，默认编译无需声学模块；即使启用，未调用已核验的 `p6_voice_bind()` 绑定非阻塞 writer 时仍不订阅下行。没有 GPIO、UART 初始化、烧录或硬件操作。USART1 诊断 / USART3 ESP / USART2 串口屏继续原分配，空闲 UART、实物 TW-TTS V1.0 资料、3.6–5.5V 供电和 UART 电平均待新的硬件窗口核对。

`python gateway/mqtt/build.py` 构建默认固件；`python gateway/mqtt/build.py --p6-voice` 构建独立 `build/p6-enabled` 产物并记录编译器栈用量。没有启动 FreeRTOS，没有修改 312B sector7 配置、遥测契约、AT/TLS 或 CANopen/Router。

coreMQTT 增加一个独立的入站 QoS1 状态槽，出站仍为单在途。SUBSCRIBE 仅固定 `mpm/v1/GW-C-001/voice/reply`，SUBACK 精确匹配独立标识且必须授予 QoS1。订阅等待有界；SUBACK/下行消息均不能设置原 PUBACK 成功标志。下行回调只核验并排入一个驱动槽，UART/播放不在回调中等待。非法业务消息计数后拒绝，Broker 对其 MQTT PUBACK 不表示业务成功。

业务帧与 [AI 下行契约](../../../cloud/ai/README.md) 一致，最大 294B 载荷，加固定 MQTT 头仍小于原 512B RX。顺序高水位与 8 个 turn_id 在 RAM 中保持跨 MQTT 重连，至少 5 秒间隔、15 秒有效期、未来最多 1 秒容差；开始发送首字节前也检查过期。掉电后 RAM 去重丢失、可信时间/物理反馈与真实动态资源尚未验收，不改 Flash 布局。

UART 协议依据：[TW-TTS 开发者官方手册 V0.21](https://www.haohaodada.com/new/bbs/forum.php?extra=&mod=viewthread&tid=2621)。UTF-8 发送 `FD len_hi len_lo 01 04 text`，长度为文本字节数 +2，无 XOR 尾字节；接口要求 9600 8N1。本期文本最多 240B，拒绝代理项、过长编码、非 BMP、方向/控制字符和 `[]` 参数标记，保证云端/设备约束一致。模块实物版本尚未核验，Host 协议验证不能代替上板确认。

上电至少 2 秒，发送总预算 1 秒，每次 poll 最多 32B；writer 必须非阻塞并只返回实际入硬件缓冲的字节数。0x41 为模块接收确认，0x4F 仅在已接收后的播放状态转为空闲才计完成。异常反馈或发送/接收确认/播放超时锁定 FAULT，不自动重播；不影响 CAN/MQTT 主循环。FAULT 恢复/掉电重播策略需要硬件窗口审阅。

普通验证入口：

- `python gateway/mqtt/tests/run_p6_host_tests.py`：真实驱动/coreMQTT，合成 ESP 与 UART。
- `python gateway/mqtt/tests/run_p6_broker.py --runtime <已有本机 Mosquitto runtime>`：进程自有 loopback Broker 与代理，真实核心客户端，合法/非法语音、遥测、PUBACK、重连并存；UART 仅计数模拟。
- 原 `run_p5_host_tests.py` 42 项、来源 6 项、EMCY 5 项、隔离 Broker 30 项及 CANopen/Backend/Web 保留。

所有结果只可称 `HOST_VERIFIED`；未操作开发板或听到喇叭出声。Security Gate、真实 Broker 与公网部署均未执行。
