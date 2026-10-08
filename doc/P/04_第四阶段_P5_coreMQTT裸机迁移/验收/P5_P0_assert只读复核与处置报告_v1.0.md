# P5 P0 assert 只读复核与处置报告 v1.0

日期：2026-10-08。复核对象：原 PR #6 `dc97019`，原 ELF SHA256
`f32d378e9cedb64688c8154f81665003c84605ca53cb2e4a10e69b8cb15bc66b`。
依据本轮实际读取的源码、link map、nm 和 objdump，不将链接告警视为已发生的运行时故障。

原路径：coreMQTT 内部 assert → newlib `__assert_func` → fiprintf → abort → raise/_raise_r
→ `_getpid_r/_kill_r` → libnosys `_getpid/_kill`（返回 -1、errno=88）→ `_exit` 永久自旋。
原 `_write` 由既有 syscalls.c 显式返回 -1，stdio 诊断无法输出；项目未配置看门狗自动恢复。

结论：正常、满足库前置条件的 MQTT 路径不会因这两个信号桩自动失败；但一旦内部断言失败，
原故障路径是无可见诊断的主循环停顿，CAN 协作与 MQTT 前台工作停止。这影响故障可观测性
和终止策略，应在真机窗口前给出明确处置。没有进行故障攻击、随机输入或真实硬件注入。

用户已单独授权固定诊断后停机。`gateway/mqtt/src/gateway_assert.c` 覆盖项目级
`__assert_func`，不修改官方库、不关闭 assert、不补造 OS `_getpid/_kill` 桩：

1. `gateway_assert_latched=1`，关闭中断；忽略 file/line/function/expression，避免记录输入内容。
2. 直接向既有 USART1 最佳努力输出固定 `GW ASSERT_FATAL`；每字符最多8192次就绪检查。
3. 串口不可用则跳过输出；进入不返回的 WFI 循环，不自动复位、写 Flash 或回到业务。

测试/固件代码提交：`e598fc63719acdf49a99c6da46c656dc8c607782`。
4 个普通用例覆盖固定标志、输入不输出、关中断顺序、UART不可用的有界退出；均 PASS。
ARM 重建无告警，ELF 不再含 abort/raise/_getpid/_kill/_exit；反汇编显示 latch 写入、
`cpsid i`、有限轮询和 `wfi`，无 stdio/signal 调用。见 [反汇编](evidence/p0-assert-disassembly.txt)
与 [资源摘要](evidence/p0-resources.json)。

物理 UART 输出、真实断言停机、时钟/供电故障状态未在 F407 实测；最佳努力标志不等于保证
所有硬件故障下串口可用。故障标志是 RAM 状态，重新启动后清零，不新增持久化或数据协议。
正常 MQTT3.1.1/AT/TLS/Router/Flash 契约保持，硬件测试与统一 Security Gate 仍待独立授权。
