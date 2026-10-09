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

## C2.5 追加：隔离诊断覆盖层

[diagnostic/](diagnostic/README.md)新增本地来源导出/patch/编译调度器和普通Host测试；以上“只读JSON、无子进程”约束仍指原analyze_h16解析器。
新调度器可调用本地Git/GCC/WSL，仍不含设备/服务器/扫描/提交能力。原解析器及22项测试代码只读不变。
C2.5仅生成两套带诊断标记的隔离产物，56项新诊断测试与既有22项检查分开；M04 BLOCKED，其余均无实机测量。

## C2.5-R1 审计口径

审计发现当前探针每轮只留最大类别样本；不能把这些最大值填入`analyze_h16.py`的逐次`cycle_samples`后解释其中位数。
M02仅称`SYSTICK_ISR_SAMPLE_TO_COOPERATIVE_SERVICE_DONE`；M03只报告完整Gateway发布包容周期，纯CPU成本未测；
M04保持`BLOCKED_UNSAFE_SENTINEL`；M07只称`OBSERVED_CACHE_EMPTY_AT_LAST_SNAPSHOT`，不代表终点全量排空。
新[r1_snapshot_index.py](r1_snapshot_index.py)只检查脱机索引的连续三轮、冻结SHA、固件身份和丢样声明，
不读取真机或导出`analyze_h16.py`输入，永远不授予H16验收。实际快照流程见[R1规约](../../../../doc/P/04_第四阶段_P5_coreMQTT裸机迁移/设计/P5_C25_R1_快照与扰动判废规约_v1.0.md)。

## C2.5-R2 脱机原始字节链

索引器现要求`--event-log`，并从独立SHA链记录核对D、halt、双读、保存、resume与下一D的绝对顺序。
`r2_generate_layout.py`用ARM编译器生成`ProbeState`的版本化布局，输出目录必须是忽略build下的新空目录；
`r2_snapshot_bytes.py`只读两份已保存的本地1264B文件；`r2_verify_bundle.py`再把六轮真实文件SHA与索引/事件链绑定。
三者均不连接设备，输出固定不授予H16/C3A。人工合成样本与完整普通测试：

```text
python gateway/mqtt/tests/measurement/r2_generate_layout.py --output-dir gateway/mqtt/build/h16-diagnostic/r2-layout-new-run
python -m unittest discover -s gateway/mqtt/tests/measurement -p "test_*.py" -v
python gateway/mqtt/tests/measurement/r1_snapshot_index.py gateway/mqtt/tests/measurement/fixtures/r1-snapshot-index-synthetic.json --event-log gateway/mqtt/tests/measurement/fixtures/r2-synthetic-event-log.json
```

固定布局SHA、现场暂停限制和指标字段边界见[R2规约](../../../../doc/P/04_第四阶段_P5_coreMQTT裸机迁移/设计/P5_C25_R2_原始快照链路与C3A申请规约_v1.0.md)。
