# C48988诊断空档回放夹具

来自已完成的非人体ECG60实板窗；仅保留原C诊断行到达的相对毫秒，不含端点、凭据、UID或UTC。原C行文件SHA256：`0fd2529ca4cf5e71d0bf6a550a4f9f20c374800a1cc08dadca64b37bdad5618e`。

数值采用主机单调时钟相对本窗START，加源armed_at=711ms；本窗评价起点为61163ms、长度300000ms。只取START后410秒以内的DIAG/QUEUE/WAVE/IO/LAT/FLOW/TEMP_ENTRY/RAM/SCHED行，851个已观察输出空档。它们不是所有循环迭代或精确CPU执行时刻。

`test_diagnostic_schedule.c`编译实际network_main.c，用这些空档验证调度。温度以首个空档起每秒一项的合成生产者驱动，不能冒充原始温度帧回放。旧代码复现主诊断不足和入口追踪积压；新代码按原≥58条、≤8秒及入口不丢的要求评估。所有软件结果都不代替新候选实板验收。
