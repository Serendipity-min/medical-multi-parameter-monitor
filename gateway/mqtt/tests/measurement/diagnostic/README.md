# C2.5 独立诊断覆盖层（仅脱机）

仅依据MPM-P5-C25-SOW-001。没有串口/J-Link/socket/SSH/云端或扫描能力，不触发Git提交或PR动作。
ARM产物含MMIO探针代码，但本轮只编译，不运行于目标板；Host通过PROBE_HOST_TEST替换周期/毫秒/能力读取。

## 冻结与隔离

- P4固定8dee339491cfd4edc468bb9451511d421f26db5e；P5固定e598fc63719acdf49a99c6da46c656dc8c607782。
- Git原始blob逐一SHA1/SHA256核验，导出到忽略的`gateway/mqtt/build/h16-diagnostic/run-<UTC>/`。
- overlay只触及临时副本中main.c、platform.c、gateway_transport.c、heap.c和既有SysTick源五处；原生产树不动。
- 四份临时新增源/头：probe_config.h、probe_events.h、probe_events.c和数值probe_variant.h。
- 原build.py/linker/vendor原封保留。新构建器重用冻结构建基础和同一-Os选项，额外输出map/stack-usage。
- 每次构建生成新目录，不覆盖或清理旧run；之前失败的archive导出副本也保留。不要直接运行其中的acceptance/网络测试。

```text
python gateway/mqtt/tests/measurement/diagnostic/build_diagnostic.py
python gateway/mqtt/tests/measurement/diagnostic/verify_isolation.py gateway/mqtt/build/h16-diagnostic/run-<实际UTC目录>
python gateway/mqtt/tests/measurement/diagnostic/tests/run_host_tests.py
```

`prepare_overlays.py`可从固定对象重现patch；已有patch时拒绝覆盖。它只供审查/初次生成，最终精确patch已经在overlays/。
所有命令只调用本地Git读取/精确apply、现有Python/GCC/ARM GNU及HERA-C3的普通编译/测试，不安装依赖。
不执行git add/commit/push，不创建/删除用户worktree。

## 观察语义与边界

`probe_state`为固定1264B结构（实际最终ARM符号），静态总增量1268B，硬上限1536B。
profile=0xC2500001，两版相同；只读P4_DIAGNOSTIC/P5_DIAGNOSTIC构建标记保留在BIN，并在state内存地址中引用。

| 数据 | 写入者/一致性 | 含义 |
|---|---|---|
| clock_seq/lo/hi/last | SysTick单写；DMB和奇偶seq；前台最多8次重试 | 32位DWT扩展，同一固件单调时域；信任SysTick上界须C3再验证 |
| ticks/head/drop | ISR单写，发布head前DMB；tail仅主线程写 | 16项SPSC计划tick；不覆盖未消费项，未配对/丢样显式记录 |
| aggregate/span/events/cache/heap | 主线程单写；ISR不动这些字段 | 不依赖多字原子；C3窗口结束后须安全一致性快照，不能盲读运行中64位统计 |
| network_us/first_business_id | 主线程，合成/VALID业务判定后记录 | MCU阶段点与纯数值node/stream/seq/epoch/boot；不保存payload或配置 |

每个scope/成功失败类别仅保留**实际最大样本**的原始起止周期和可信上界；相同类别原地更新。
event低8位为scope，bit8为成功，bit9为失败。16类别上限；满记录只增加丢样并标质量不足。
没有全量分布或p95；aggregate整体概况不混称按结果分布。有丢样、tick不匹配、时钟失真或调试暂停时不得声称全窗口最大/准出。

父span只扣直接子span一次，不重复扣除孙层AT/CAN区间；IRQ仍包含，不能把剩余值称为纯协议CPU。
Paho的Publish含ACK等待，coreMQTT API Publish后才由Gateway等待ACK：完整Gateway publish包容跨度可作同口径准备，库子区间直接比较NOT_COMPARABLE。

实际处理D的主循环发布边界才开始新window_generation；不能在活动嵌套span中清空。
下一个D前C3必须保存上一窗口编号/快照，软件不自动传输旧数据。没有保存就如实记缺失，不能把累计窗口当三轮独立样本。
记录D请求、30s结束、CIPCLOSE开始、2s等待开始/结束、network_open入口、TLS、CONNACK和首业务发布成功。
M07首LIVE可为状态；M06首业务必须synthetic/valid，状态和RR INVALID不能代替。QoS0发送完成不是Broker ACK。

## M04与实际运行限制

没有栈哨兵实现或填充函数。已有main在platform_init前已入栈，故该初始化位置不安全；M04=BLOCKED_UNSAFE_SENTINEL。
保留8KiB预留但它不是高水位，.su单函数最大72B也不是全程序高水位。
真实DWT能力、IRQ持续服务、对业务干扰、堆/栈余量、网络重连和所有H16真机数值都NOT_MEASURED。

当前为数值RAM观察格式，不生成analyze_h16要求的JSON，不修改旧解析器以适配。
原始最大样本可以对应cycle_samples，但环境/固件/观察批准、每轮有效性、窗口快照及符号读数需后续经审查的导出器，
未采集的字段只能未知/null。若需要export_h16.py，须另行批准，不能编造字段喂出PASS。

完整审查：[差异与构建审查](../../../../../doc/P/04_第四阶段_P5_coreMQTT裸机迁移/设计/P5_C2_5_诊断覆盖层差异与构建审查_v1.0.md)。
