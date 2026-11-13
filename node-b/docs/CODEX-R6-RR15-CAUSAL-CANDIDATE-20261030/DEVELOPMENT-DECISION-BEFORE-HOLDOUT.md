# 开启留出前的开发裁定

此文件形成于 ECG各02、R5 RR15原始波形/算法留出回放之前；此前仅验证它们的封存链，历史正式标签已知。

当前R6 RR15与新ECG60的实际C回放、逐样本C观察包装及逐seq SWD对应已完成。600/600评价期HR/valid对应一致；RR有1帧非有效HR状态下last_good/count不一致、13帧IRQ时间字段不一致，ECG有15帧IRQ时间字段不一致。真实getter/Tick时间线和120B非原子SWD读时序没有记录，不能捏造“全状态完全等价”；异常HR本身没有出现对应偏差。

六事件窄峰经过原C的幅值/宽度与3周期资格，周期时间戳/速率在回放中重现。原始CH2含强50Hz成分，分解后仍有RESP相关残差。**没有独立物理通道真值证明六事件中不存在微弱QRS**，相关性和去工频干预也不能证明物理来源。因此登记：

```text
ROOT_CAUSE = ROOT_CAUSE_UNRESOLVED
ALGORITHM_ORIGIN_OF_VALID_HR = CONFIRMED_BY_SAME_C_REPLAY
NON_QRS_PHYSICAL_SOURCE_FOR_ALL_SIX = NOT_PROVEN
ALGORITHM_PATCH = NOT_IMPLEMENTED
FIRMWARE_SOURCE = UNCHANGED_SHA_3adca55cb1eb1fa3ed8e4148f837287d0454bcc2c08ae77a8f73deb1dac156a7
MODE_SPECIFIC_HR_MASK = FORBIDDEN_NOT_IMPLEMENTED
NEXT = EVALUATE_LOCKED_REAL_AND_SYNTHETIC_CORPUS_WITH_UNCHANGED_C
```

留出用于独立表征、检验既有边界和避免仅凭RR失败调阈值，不反向影响本轮阈值或产生第二次候选。若发现已知非QRS合成输入仍被认成HR，标记合成反例已证实；不能将其外推为本次物理信号根因。最终报告应分别呈现算法路径已复现和物理根因未解决。
