# PI审核入口｜五板自动入口、K1与隔离事实回复

**提交范围：离线实现和脱敏证据。结论仍为 OFFLINE_IMPLEMENTATION_PASS / CAPACITY_NOT_PASS / FIELD_NOT_RUN / FreeRTOS_NOT_STARTED。**

负责人本次授权将现有离线候选提交并push到`codex/five-appliance-integration-v1`；未授权刷写、上电或新300秒窗口。本次不改原五板分支、M0标签、R6失败证据、main或正式云端，不合并旧语音分支。没有新功能修改或重复全量测试，复用哈希一致的已完成验证。

## 建议审核的四项决定

1. **自动入口和K1行为是否符合预期。** 自动行为只在显式`--five-appliance`构建启用；缺配置只运行本地CAN，退避期间协作处理采集。K1按下开始、再按结束，不足1秒继续录音，最大2秒；E血压仍只能由屏手动启动/停止。默认手动构建及维护停止入口保留。实体PE3、冷启动顺序、断网恢复未实测。
2. **隔离协议和事实资格是否认可。** 统一GW-B5-001，D物体温度、E血压；新MR02绑定录音session/CRC、事实身份与源期限，5秒/90秒过期拒答，已知无效或新代次阻止旧回复。摘要不是数字签名，信任边界依赖隔离TLS/认证/ACL。新worker已实现MQTT、ASR和事实API连接代码，但没有启动；真实ASR、真实网络和可闻回执均NOT_RUN。旧MR01 worker不能直接替换使用。
3. **资源与容量是否允许下一阶段。** 本候选Flash加载58,136 B，sector4余7,792 B；SRAM静态及保留段115,772 B，CCM PCM64,000 B。ARM链接与IRQ检查通过，不等于实板栈/并发裕量通过。已有出口约8.08批/s低于输入约10.45批/s，至少需约29%服务率提升才追平，历史与语音还需要余量。没有用扩大FIFO、补点、降采样或延长时效制造通过。
4. **性能路线与41Ω实验如何区分。** 现有记录更支持先分解C出站AT/接收查询/PUBACK/调度开销；FreeRTOS可能改善等待和调度，但没有自动提高物理服务能力的保证，本轮不启动迁移。41Ω贡献仍UNKNOWN，不能仅凭电阻值或周期零错误计数作因果裁定。完整五板＋语音验收仍受容量缺口阻断，不由本次push触发新实板窗口。

## 证据入口

- [实现与复现命令](RESULTS.md)：真实C状态机检查、53项Python/跨语言/ASGI检查、16项网页回归、两个网页profile及ARM构建。
- [协议、隔离模板及worker边界](PROTOCOL-AND-ISOLATION.md)：令牌角色区分、默认MOCK/语音DISABLED、拟议隔离端口；不是已部署配置。
- [容量及FreeRTOS/41Ω判断](CAPACITY-DECISION.md)：保留原P1实际服务率和缺失证据，不将合成Hub输入冒充现场吞吐。
- [ARM摘要](ARM-RESOURCES.json)、[测试结果](TEST-RESULTS.json)、[来源](SOURCE-INPUTS.json)、[交付哈希](DELIVERY-MANIFEST.json)。
- [原五板实际镜像清单](../FIVE-NODE-MIGRATION/FIVE41-20261106/CURRENT-IMAGES.json)：**本候选未安装**，没有替换其中的C或其他板记录。

`PRESERVATION-CHECKS.json`内`commit_push=NOT_RUN`和旧报告的“尚未提交”是离线验证时点记录；本页说明后续Git交付，不将旧时点证据改写成新现场验证。推送后的实际提交SHA、远端匹配和工作区检查在交付回复及本机忽略目录收据中记录。

## 审核期间状态与回退

设备继续保持原断电状态；没有刷写、泵控、串口写入或正式服务操作。原分支`codex/five-node-single-module-v1@f9bdff8`继续作为五板软件参考；切回原工作树即可审阅原代码。硬件无需回退；未来如确需恢复镜像，仍先核实板身份及获准分区，本页不构成安装或恢复授权。

仅源码、合成输入、脱敏报告和制品摘要进入Git。完整Flash、UID、凭据、实际端点、私人音频和忽略构建制品不进入本次提交。
