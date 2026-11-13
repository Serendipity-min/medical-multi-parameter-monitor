# 温度 age：分次读取偏差的最小主机修复

## 复现依据

此前 RR15 同窗 22/600 个 age 越界，最小 -22ms；本轮未修改工具的 ECG60 同窗再次得到 23/600 个越界，最小 -20ms。它们不是独立温度正式通过结果，旧裁定不改。

原 `b4_runtime.snapshot` 顺序为 BIO→ADC→寄存器→CAN→ESR→TEMP；BIO 的 `last_sample_ms` 可能先于随后 TEMP 的新 `last_ms`。同一 MCU 时钟下，目标正常推进即可使两个主机观测相减为负。新的合成目标夹具每次读取推进4ms，原工具实际计算 -20ms，定向测试退出1；先前一版 stale 夹具还存在一个断言边界错误，原失败日志及修正后只剩时间偏差失败的版本均保留。

## 改动

仅修改主机 `node-b/tools/b4_runtime.py` 的带温度 snapshot 分支：**BIO-before→TEMP→BIO-after→ADC→寄存器→CAN→ESR**。诊断 `bio` 使用后一次读取的完整120字节及原解码，没有单独替换时戳或拼接一项新时基。TEMP仍使用原64字节解码，没有 clamp、补偿、伪造、阈值或有效位改写。

增加 `temperature_observation`：两次 BIO 的原始 sample tick、TEMP 原始 last tick、主机读取区间；前一次 BIO 和 TEMP 原码另存受限 EFS，后一次 BIO 继续走原有原码保存。`coherence=LIVE_NONATOMIC_NO_HALT` 保持，**不宣称原子快照或主机时钟等于 MCU 时钟**。真实过期、未来时间戳继续保留并由冻结评测器拒绝。

每个带温度 snapshot 增加一次120字节白名单读取，不新增地址/目标写入；每0.5秒诊断一次的既有采集节奏不变，计入原会话SDK预算、原生单调用/整窗监督。无温度分支保持原 BIO→ADC→寄存器顺序。未修改固件、采样/算法/驱动、Flash、Options、C、云端逻辑、旧卡或任何冻结判据。

ECG60 工具绑定中的 `b4_runtime.py` 为父提交版；独立温度窗口采用修复版。两个窗口分别保存32项绑定源码快照和输入 SHA，绝不把修复后的工具哈希说成 ECG 实际执行版本。未来针对新日志做时序分析，应按 `temperature_observation` 识别每诊断两次 BIO；旧 RR 的“一个BIO读对应一个诊断”顺序配对脚本只适用旧布局，不能盲用。

## 验证

17项受影响的离线回归：原 B4 runtime 14项，加新温度观察3项；最终退出0、失败0、错误0。新例检查正常更新落在两次读之间、原始时戳不被改写、陈旧帧仍失败、真正未来帧仍失败，并直接调用原 `b5_channel_review.assess_b` 的温度新鲜度逻辑。测试 runner 对 DLL加载、socket、subprocess、Serial设置拒止，目标原生调用0。没有重跑旧151项或旧R5三窗来替代本轮验证。

独立 TEMP_OBJECT 的现场结果及新增 native 调用实际数见本轮 `TEMP_OBJECT-review-summary.json`、`TEMP_OBJECT-execution-summary.json`；其结论只适用于桌面非人体物体的工程传输/新鲜度，未做绝对温度标定。本修复不关闭 SDK Connect/Close 副作用、ROM 根因、或 RR15 非零 HR 问题。
