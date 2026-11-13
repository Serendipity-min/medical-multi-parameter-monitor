# H16 纯脱机解析工具

本目录只读本地脱敏JSON；没有串口、J-Link、网络、SSH或子进程调用。
它不会编译、烧录或运行固件，也不会授予H16/P5准出。

`fixtures/h16-synthetic-demo.json` 的周期、时刻、内存和丢弃数全部是**人工构造的工具演示数值**。
其中公开生产SHA仅用于演示身份约束，不代表这些生产版本已有这些实测数据。
演示必须输出`SIMULATION_ONLY`及`H16_acceptance=NOT_GRANTED`。

```text
python -m unittest discover -s gateway/mqtt/tests/measurement -p "test_*.py" -v
python gateway/mqtt/tests/measurement/analyze_h16.py gateway/mqtt/tests/measurement/fixtures/h16-synthetic-demo.json --output gateway/mqtt/build/closeout-c2-20261008/synthetic-demo-summary.json
```

只需Python标准库。输入/输出限本仓库本地JSON，拒绝设备/UNC/仓库外路径；未来C3先将脱敏导出放在本地忽略build目录。
输出目录由调用方预先建立；以独占创建方式拒绝覆盖任何既有输出或历史文件。示例路径已存在时改用新的文件名。
CLI exit=0仅表示解析完成；exit=2表示输入/文件不合格，二者都不是硬件PASS/FAIL。

## JSON口径

完整字段定义与示例以已标注的演示JSON和`analyze_h16.py`的白名单校验为准：

| 结构 | 约束 |
|---|---|
| 顶层 | schema_version=1，kind=SYNTHETIC_DEMO或REDACTED_HARDWARE_OBSERVATION，synthetic=true，CAN1_SILENT_LOOPBACK |
| baselines | 固定P4提交/BIN与P5最后受测源码/BIN；测量版另存各run的measurement_bin_sha256 |
| run身份 | 唯一run_id、脱敏environment_id/workload_id/profile_id，核心频率、有效性、完整性、观察丢失及暂停标志 |
| cycle_samples | M01/M02/M03、相同scope、SUCCESS/FAILURE分组、uint32起止计数、独立可信间隔上界 |
| network | 同一clock_domain、分辨率、端点及GATEWAY_NETWORK_OPEN_ENTRY边界；固定故障延时单列；首业务流必须VALID/MOCK/合成 |
| memory | stack/heap实测方法与范围声明；NOT_MEASURED字段必须null，未知堆失败数用null，不用0代替 |
| cache | 同一窗口before/after计数、容量、LIVE/REPLAY先后、真实排空标志；丢弃或未排空保持可见 |

少于每版本3个有效网络样本：`INSUFFICIENT_SAMPLES`；声明环境/方法/时钟/端点漂移或同一版本测量BIN变更：
`NOT_COMPARABLE`。只有符合声明口径时才计算中位重连增幅及`>20%`审查标志；不计算p95，不按D→首帧比较。
工具不能验证物理环境、人员批准或诊断源码真实性，这些仍须C3测试身份证和负责人审核。

单次DWT间隔必须小于完整32位回绕周期，超界拒绝推测；观察丢失或调试器在窗口中暂停的run不计为有效比较样本。
未知JSON键、重复键、非有限数、布尔冒充计数、不安全栈方法、无法解释的缓存计数回退均拒绝。
失败/成功周期分开汇总，缺少指标保留NOT_MEASURED；低于20%也不会自动判PASS。

已有真机JSON没有全部M01–M07原始字段，**不要将其补造为本schema**。未来C3脱敏导出器须另经审查。
本轮只验证解析器，未写`c3-measurement-summary.json`。

测量方案：[P5 H16计划](../../../../doc/P/04_第四阶段_P5_coreMQTT裸机迁移/设计/P5_H16动态资源与P4对照测量计划_v1.0.md)。
