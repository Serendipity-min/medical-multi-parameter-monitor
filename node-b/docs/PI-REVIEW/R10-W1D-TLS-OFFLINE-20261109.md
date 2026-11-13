# W1-D TLS 离线排查与复测候选

## W1-D 定位

W1-D 的 `GW FAIL TLS` 发生在 STM32 本地预算门控。C 已确认 Wi-Fi 和新鲜 SNTP，`CA_VERIFY`、`CERT_NAME`、`SNI` 均返回 OK。主机以 `START_ACCEPTED` 为零点，在 27.000 s 的同一接收时隙观察到 `GW OK SNI` 和 `GW FAIL TLS`。MCU 的停止 tick 为 27,360 ms，45,000 ms 的 T0 前上限只余约 17,640 ms。`gateway_network_open()` 为 SSL `AT+CIPSTART` 请求固定 30,000 ms，旧 `at_command()` 要求再加 2,000 ms 关闭余量，预算不足时在写入任何 AT 字节之前返回。STOP 的 `required=48 written=48` 来自此前的新鲜 SNTP UDP 请求的负载计数。

因此本次未发出 Broker 建链命令。DNS、TCP 和 TLS 握手均未进入，现有实板原件不能判定这三层在补丁之后的结果。W1-A、W1-B 在较早获得 UTC 后，同一冻结镜像曾分别在 SNI 后约 2.89 s、2.25 s 完成 TLS。 [R10 实板回执](R10-FIELD-RECEIPT-20261109.md)

## 补丁和离线验证

- 只对 `MP_FIVE_FIELD01` 的 SSL `CIPSTART` 使用剩余预算。原 30 s 仍是上限，关闭余量仍是 2 s，若缩短后连 1 s 的准备余量都不足则拒绝。原失败时点可以分配约 15.64 s。CA、证书名、SNI、连接目标、UART 失步和 STOP 门控沿用原路径。
- 本地预算拒绝输出 `GW TLS_AT NOT_SENT_BUDGET`。进入等待后的失败输出解析原因、标志和耗时。固定数字回执不输出原始 AT 回复、端点或凭据。原因 4 对应 ESP 终止错误，10 对应等待超时，11 对应终止型 URC。单凭这些原因仍不能判断 DNS、TCP 或 TLS 握手的具体失败层。
- USART MMIO 夹具使用真实 AT 发送与解析代码，将 tick 设为 27,360 ms。旧实现退出 3，断言停在 SSL 命令未获准。修复后校验 SSL 命令与 CRLF 完整写入、合成 `CONNECT/OK` 成功、普通 TCP 不获同样的缩短、预算不足时零写入、静默对端超时后保留 2 s 并维持失步门控。统一 Host 18 组通过。
- Windows Arm GNU 14.2.1 的 F-N115 和 F-P230 均通过链接和 IRQ 向量核验。非 FIELD01 的原五板目标 boot、code、HEX 与 R9 摘要逐位一致。

| Windows 候选 | sector4 字节 / 余量 | boot SHA-256 | code SHA-256 | HEX SHA-256 |
| --- | ---: | --- | --- | --- |
| F-N115 | 54,668 / 10,868 | `07626f6bc82ea7e33226ae38f95bc8f260dc4b74f44501376408adede8a0f190` | `9dd76ede3e0bd963087377bb35209f9a2546a1ac1be148c2b9ad0e590c839c2a` | `d878e328f4fea5b25a5dab326833b40668198142e6d39dd52ea0e3c949b38a85` |
| F-P230 | 56,700 / 8,836 | `f760ce2cd469eeb719fdb0b260b2cce2a3b1678104aae4e96fe77e055b1de201` | `bb560b891162aec79161d569a78795268a707527412614574b618a79073c9c16` | `c7f0dd4a5d112adcc014ed5e189c2898d3bbf40af6af95e19fa39ab13fb268a0` |

离线阶段的实板 W1 状态为 NOT_RUN。后续负责人按新 F-N115 摘要放行，安装时仅写 C 的 sector0/4，并完成整片读回。复测验证了真实 TLS、MQTT 和完整 150 s，现场结果与断电确认另见实板回执。 [W1 TLS 修复实板复测回执](R10-W1-TLS-FIX-FIELD-RECEIPT-20261109.md)
