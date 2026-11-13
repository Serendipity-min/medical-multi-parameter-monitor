# 本项目补丁与许可证

上游固定提交见 `upstream.json`，其中 SHA-256 为下载时已按 Git blob SHA-1 核验的原始文件。
本项目选择 Eclipse Distribution License 1.0；随源码保留 `edl-v10` 和 `epl-v20`。
项目补丁后的文件 SHA-256 单独记录于 `patched.json`，不得覆盖 `upstream.json` 的原始哈希。
`gateway/third_party/verify_paho_integrity.py` 只读核验；后续只有补丁经过评审且固定回归通过后才可人工更新补丁清单。

## 补丁一：ARM 短枚举 ABI 越界防护 (PATCH-01)

修改 `MQTTClient-C/src/MQTTClient.c` 的 `MQTTSubscribeWithResults`：
用局部 `int` 在 QoS 枚举与序列化 API 之间转换，避免 ARM 默认短枚举被强制转换为
`int *` 后越界读写。MQTT 订阅路径目前不用于 Gateway 发布器，但必须消除构建时暴露的
接口大小不匹配；不采用与工具链运行库不一致的全局枚举 ABI。

## 补丁二：有界报文反序列化与接收端主动安全加固 (PATCH-02, P4)

1. **有界 Remaining Length 解码**：
   在 `MQTTPacket.h` / `MQTTPacket.c` 中新增 `MQTTPacket_decodeBufSafe`，在逐字节反序列化变长 Remaining Length 时严格检查 `offset < buflen`，防止截断报文导致越界读。
2. **底层错误传播修复**：
   修复 `MQTTPacket_decode` 与 `decodePacket`：在网络读取失败或长度超过 4 字节时统一返回明确负数错误码 `MQTTPACKET_READ_ERROR` (-1)，并在 `readPacket` 中显式检验。
3. **真实长度门禁与有效报文长度传递**：
   - 彻底修复 `MQTTDeserialize_publish`、`MQTTDeserialize_ack`、`MQTTDeserialize_connack` 及 `MQTTDeserialize_suback`：增加输入指针与最小长度检查，验证 `1 + lenlen + mylen <= buflen`，确保 `enddata <= buf + buflen`。
   - 在 `MQTTClient` 结构体中记录实际成功收到的有效字节数 `c->read_packet_len`，向全部反序列化器传递真实包长，废止向解析器传递缓冲区总容量 `c->readbuf_size`。
4. **网关上行接收范围收敛**：
   网关固件仅作上行遥测发布者，不订阅下行主题。在 `cycle()` 调度中对接收到的下行 `PUBLISH` 报文主动返回 `FAILURE` 协议错误，关闭 MQTT 会话且不分派消息回调；这一限制不能替代其他接收路径的边界检查。
5. **格式化越界写防御与密码脱敏**：
   在 `MQTTFormat.c` 中实现 `safe_append` 严格约束 `snprintf` 索引更新；将调试输出中的密码脱敏；并在 `gateway/mqtt/build.py` 中仅编译必需客户端源文件，将 `MQTTFormat.c` 完全排除出固件产物。

## 补丁三：已知边界收尾与固定回归 (PATCH-03, P4.1)

1. `MQTTClientInit()` 与每次 `readPacket()` 入口显式清零 `read_packet_len`，仅在完整报文读完后保存本次实际长度。首次初始化、读首字节超时、长度解码失败、容量不足和正文截断均不得复用旧值。
2. `readPacket()` 先在四字节局部区编码 Remaining Length，按“前缀长度非负、前缀不超过容量、正文非负、正文不超过剩余容量”的顺序检查；检查通过后才写回前缀并读取正文，避免 `size_t - int` 混算和提前写入。
3. `MQTTPacket_read()` 显式传播 `MQTTPacket_decode()` 失败，不再编码部分解出的长度或读取正文；其前缀回填同样在容量检查后执行。
4. 合同固定的 truncated / declared-length-too-large UNSUBACK 用例发现包装器会用报文类型覆盖底层 ACK 失败状态。`MQTTDeserialize_unsuback()` 现在同时要求 ACK 解析成功和类型为 UNSUBACK。
5. `MQTTFormat.c` 的 CONNECT 密码字段仅显示 `[REDACTED]`，C 字符串形式的密码仍省略输出。该文件只为固定本机 formatter 回归编译，不进入 Gateway source list / ELF。

### Safe Decode 与当前构建范围

当前 `gateway/mqtt/build.py` 的客户端白名单包含以下反序列化路径：

| 反序列化器 | Remaining Length 解码 | 调用长度 |
| --- | --- | --- |
| `MQTTDeserialize_connack` | `MQTTPacket_decodeBufSafe` | `read_packet_len` |
| `MQTTDeserialize_ack` | `MQTTPacket_decodeBufSafe` | `read_packet_len` |
| `MQTTDeserialize_suback` | `MQTTPacket_decodeBufSafe` | `read_packet_len` |
| `MQTTDeserialize_unsuback` | 委托有界 `MQTTDeserialize_ack` | `read_packet_len` |
| `MQTTDeserialize_publish` | `MQTTPacket_decodeBufSafe` | 固定本机测试传实际样本长度；Gateway `cycle()` 直接拒绝 PUBLISH |

`MQTTPacket_decodeBuf()` 为上游兼容 API 保留；当前 Gateway 编译白名单内没有对它的调用。
引用旧 API 的 `MQTTConnectServer.c`、`MQTTSubscribeServer.c`、`MQTTUnsubscribeServer.c`、`MQTTFormat.c`
不在固件白名单。此结论只涉及当前客户端构建，不能推广为全部上游兼容 API 已验证。

### 固定回归与维护约束

Linux/WSL 本机执行 `python gateway/canopen/run_security_regression.py`，实际编译当前 Paho 源码，使用 ASan/UBSan 和编译器告警检查：

- 29 个固定 parser / reader 案例（含 CONNACK、SUBACK、UNSUBACK 各三类及 decode error 传播）。
- 10 个固定客户端初始化、接收长度生命周期、缓冲容量和 inbound PUBLISH 拒绝案例。
- 3 个固定 CONNECT formatter 脱敏 / 小缓冲案例。

样本仅在内存中处理；不使用网络、串口、随机生成或变异。输出和日志存于被忽略的 `gateway/canopen/build/security-regression/`。

Gateway-C 当前为 publish-only client。若未来需要 OTA、Remote Command 或 MQTT Subscription，不能直接恢复旧 PUBLISH 逻辑，必须重新签订协议与安全合同。
