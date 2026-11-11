# R41 · WP-AX 离线交付与窗口 3 复测准备

**2026-11-11 · Host 和 Windows ARM 构建通过，实板 `NOT_RUN`。** 源码 `b057a65e886cc0000db10faea30733162d19f083`，基线 `2a8ee475667fac0ccf23a212bdda17c78de98c35`。WP-AX 候选待 PI 位级复核及按完整 SHA 放行。 [R41 §3](https://github.com/Serendipity-min/medical-multi-parameter-monitor/blob/9e79457/node-b/docs/PI-REVIEW/R41-20261111.md) · [窗口 3 停机复核](R40-COLD-STOP-REVIEW-20261111.md)

## 修复与验证

- 生产透传的 socket 判定接受 `STATUS:0/1/2/4/5` 且无 `+CIPSTATUS:` 连接行。`3`、有连接行、查询失败和无法解析均保持未确认。未确认诊断只输出状态数字、`QUERY_FAILED` 或 `UNKNOWN`。 [socket 判断](../../../gateway/mqtt/src/gateway_transport.c)
- ESP 硬复位收到完整 `ready` 和 `AT OK` 后才允许重设基线。接纳范围从发起该次硬复位到收到 `ready`，且复位前累计值须与旧基线一致。复位未确认、复位前已有增量或 `ready` 后出现新增错误时，原停机判断仍生效。累计计数保留，`PASS_RESET_UART_REBASE` 记录前后值，`PASS_LOCAL_FAULT` 记录基线、总数、ORE、NE、FE 和环溢出。硬件分项按标志计数，同次中断可命中多个标志。 [ESP 恢复](../../../gateway/mqtt/src/platform.c) · [重连门禁](../../../gateway/b5/network_main.c)
- COM15 被动记录器识别上述复位和基线标记，并保留复位失败及后续 UART 增长的停止判断。窗口 3 可选 45 分钟记录，绝对截止仍由批次台账约束。 [被动记录器](../../tools/r18_s1_capture.py)

`python -X utf8 gateway/microphone/test_unified.py` **30 组全过**。两个原 Host 复现已并入现有生产用例，覆盖 `0/1` 冷启动通过、`3` 和连接行触发恢复、复位中一次 FE 后 `ready` 与 AT 成功可重连、缺 `ready` 或 AT 无应答时不重设、复位前及稳态新增错误仍停机。定向 pytest **94 项、12 个子例通过**，覆盖 `test_field01*.py`、台架、统一安装、被动记录及 R36/R40 汇总。 [真实 AT 夹具](../../../gateway/b5/test_five_p3_egress.c) · [真实重连夹具](../../../gateway/b5/test_link_control.c)

## 候选制品

Windows Arm GNU 14.2.Rel1（GCC 14.2.1），STM32F4 SPL v1.4.0。沿用 R38 的构建参数。WP-AX 修改受现有 `--link-resilience` 保护，WP-AW 冻结件仍由其既有提交和 R38 归档复现。用当前源码移除 `--link-resilience` 构建，boot、code、HEX 与 S2-c 归档逐字节一致。 [R38 构建环境及冻结件](R38-WP-AW-FREEZE-20261111.md)

```text
python -X utf8 gateway/dual_can/build_arm.py --b5 --egress-final --tri --unified --split-flash --five-node --five-appliance --no-audio --esp-passthrough --pass-lifecycle --production-diag --outage-retention --tx-integrity-diag --link-resilience
```

| 制品 | 字节 | SHA-256 |
| --- | ---: | --- |
| [boot](r41-wp-ax/FIVE_APPLIANCE_C_2S_V1-boot.bin) | 392 | `1692cd7fe7a84e99bce8ae4708ad2a7c7d88280a9e6d2a4a42836a1dea5461bb` |
| [code](r41-wp-ax/FIVE_APPLIANCE_C_2S_V1-code.bin) | 58,480 | `0fa2e77469ba02d213541118219f15cd285536edfe45575cf3518f42d2aab922` |
| [Intel HEX](r41-wp-ax/FIVE_APPLIANCE_C_2S_V1.hex) | 165,691 | `ea8a6a8cee368ad2d5ac39328dcd6e2e0d213f743678236365117237d114fbc7` |

HEX 保留构建原始字节，已解码与两个 BIN 逐字节核对。IRQ 向量检查通过。Flash sector0 余 **15,992 B**，sector4 余 **7,056 B**，code 较 WP-AW 增 **388 B**。常规 SRAM 扣除保留堆栈后余 **16,072 B**，CCM 余 **3,712 B**。 [安装器布局](r41-wp-ax/unified-layout.json)

## 复测准备

1. 依据 R10 的受限整片双读备份、R36 安装回执与 R40 首份完整读回，`unified_install.py` 的离线计划已通过。计划整扇区写入只覆盖 C 的 sector0 `[0x08000000, 0x08004000)` 和 sector4 `[0x08010000, 0x08020000)`，保留 sector3、其他 Flash 和 Options。回退以同一冷启动安装入口及 R38 的 WP-AW 分段制品为目标，整片预期与 R40 首份读回一致。 [冷启动安装器](../../../gateway/microphone/unified_install.py) · [WP-AW 回退制品](R38-WP-AW-FREEZE-20261111.md)
2. 候选获批后按新卡执行 C 安装一次、整片和 Options 读回，再断电并拔掉 J-Link，随后依 R40 做隔离 Broker、冷启动和空载试验。贴人体探头前复核 R40 §2。记录笔记本和整条导电链按卡采用电池供电，测量阶段保留现场双人分工和停止手段。 [R40 批次卡](https://github.com/Serendipity-min/medical-multi-parameter-monitor/blob/752de06/node-b/docs/PI-REVIEW/R40-20261111.md)
3. ECG 沿用只输出 ECG 的 60 bpm 模拟器，HR 标注模拟来源。真人 PR 与模拟 HR 的中位数差判据不适用。血氧、体温、血压按批次卡记录。若现场自然触发 ESP 硬复位，单列 `PASS_RESET_UART_REBASE` 与后续建链结果。否则该路径仍为 Host 证据。
