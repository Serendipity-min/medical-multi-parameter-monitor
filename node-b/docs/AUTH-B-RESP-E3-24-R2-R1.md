# AUTH-B-RESP-E3-24-R2 R1｜名义24次/分第2轮

2026-10-23。仅准备，当前源仍30bpm，本卡尚未执行。此卡只能消耗一次；条件是负责人确认呼吸率确已设24bpm及按本卡执行。呼吸波形、波形周期20bpm、幅度1.5R、窒息0s、原红RA/黄LL/绿RL接法及隔离条件不变。不能把30当作24采集，不能改变波形周期补偿呼吸率。

本卡完整继承[矩阵R1协议](RESP-RR-ENGINEERING-MATRIX-R1.md)，协议SHA256 `a91e1e27e341feb8a258f04674df003fb2a98d8022e09de8578ea17381f6eadd`；其时间边界、判据、只读地址/计数、冻结身份、停止/不重试及未知真值边界均是本卡的一部分。CPU机制不追查、算法阈值不改、历史ECG和RESP数据不覆盖。

每格一次正常复位前置，reset≤1/halt≤1/go≤2/目标数据写0，137秒槽窗=45秒预热+90秒评价+2秒尾裕量；SDK≤10000，另Close≤1，全会话≤360秒。前末身份/完整Flash/options实际核验，Flash入口/初始化门通过才采；窗末暂停单读128KiB RAM并核验后才恢复。失败立即停且不追加复位/连接或下一轮。对启动/ROM问题不增加调查范围。

- cell：`24-r2`；scope：`E3_ONE_NORMAL_RESET_45_WARMUP_90_EVALUATION_2_TAIL`。
- profile：`E:\medical-monitor-node-b-field-private\field-r3\resp-003\e3-matrix-r1\profile-24-r2.json`；SHA256 `1d00cea2dbe4c59b90e496515b5d394310b0ea2b78733f389847584adbc6282e`。
- 未设置源模板：`E:\medical-monitor-node-b-field-private\field-r3\resp-003\e3-matrix-r1\source-template-24-r2.json`；SHA256 `06f4650a2c03d200dba4a71729ffc59bad505372dd5e1d13b6afcecccb61ba31`，不是实际源确认。
- 执行源：`E:\medical-monitor-node-b-field-private\field-r3\resp-003\e3-matrix-r1\source-ready-24-r2.json`，尚不存在；收到实际设档后独立新建，真实SHA写入新清单，模板不覆盖。
- 准备清单：`E:\medical-monitor-node-b-field-private\field-r3\resp-003\e3-matrix-r1\manifest-prepared-24-r2.json`，enabled=false、owner_reset_authorized=false。
- 未来一次执行清单：`E:\medical-monitor-node-b-field-private\field-r3\resp-003\e3-matrix-r1\manifest-ready-24-r2.json`，必须绑定本卡实际SHA、协议SHA、profile/tools/DLL/实际源SHA、现场原话SHA和前格成功分析（首格无前格）。
- 输出：`E:\medical-monitor-node-b-field-private\field-r3\resp-003\e3-matrix-r1\capture-24-r2`；分析：`E:\medical-monitor-node-b-field-private\field-r3\resp-003\e3-matrix-r1\analysis-24-r2`；均须不存在。
- 防重试令牌：`E:\medical-monitor-node-b-field-private\field-r3\resp-003\e3-matrix-r1\attempt-24-r2.json`，SDK前独占消耗。

仅在上述条件成立后使用以下精确参数；卡SHA256以本文件实际SHA写入参数，禁止填模板占位值执行：

```text
python -X utf8 E:/medical-monitor-node-b-field/node-b/tools/supervise_resp_matrix_b.py
  --dll E:/medical-monitor-node-b-field-private/field-r3/jlink-986a-portable/JLink_x64.dll
  --card E:/medical-monitor-node-b-field/node-b/docs/AUTH-B-RESP-E3-24-R2-R1.md
  --card-sha256 本卡实际SHA256（私有manifest-ready中冻结）
  --manifest E:\medical-monitor-node-b-field-private\field-r3\resp-003\e3-matrix-r1\manifest-ready-24-r2.json
  --out E:\medical-monitor-node-b-field-private\field-r3\resp-003\e3-matrix-r1\capture-24-r2
```

上述分行仅为阅读；完整无占位argv在实际清单中冻结。当前没有任何源设置/连接/复位/采样许可被本次准备动作消耗。六格逐轮分析，任一非0立即停止；同档第二轮只在第一轮成功、现场状态未变且负责人同意两轮的前提下执行。
