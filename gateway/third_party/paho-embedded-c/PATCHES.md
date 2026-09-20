# 本项目补丁与许可证

上游固定提交见 `upstream.json`，其中 SHA-256 为下载时已按 Git blob SHA-1 核验的原始文件。
本项目选择 Eclipse Distribution License 1.0；随源码保留 `edl-v10` 和 `epl-v20`。

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
4. **网关上行攻击面收敛**：
   网关固件仅作上行遥测发布者，不订阅下行主题。在 `cycle()` 调度中对接收到的下行 `PUBLISH` 报文主动返回 `FAILURE` 协议错误，彻底消除未预期下行报文的攻击面。
5. **格式化越界写防御与密码脱敏**：
   在 `MQTTFormat.c` 中实现 `safe_append` 严格约束 `snprintf` 索引更新；将调试输出中的密码脱敏；并在 `gateway/mqtt/build.py` 中仅编译必需客户端源文件，将 `MQTTFormat.c` 完全排除出固件产物。
