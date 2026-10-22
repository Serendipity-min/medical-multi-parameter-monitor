# MPM-B-RESP-003探索性验证报告

2026-10-22 Asia/Shanghai；精确起点`codex/node-b-bio-v2-field-20261022@2d34b848d5946d38b6f942fa61c4fc7c05138a40`。本轮唯一实施者Codex /root，在原独立测试工作区新增提交。依据负责人明确调用的[RESP-003合同原字节副本](contracts/MPM-B-RESP-003-R1.0.md)，**厂家未给ΔΩ或端子等效图不再作为探索性短窗的一票否决**。电气判断、准确卡和实际源菜单仍须核对；不能用未知Z值冒充绝对阻抗精度。

## 当前阶段

| 阶段 | 状态 | 已完成 / 尚待执行 |
|---|---|---|
| E0 | **E0_SOFTWARE_PREPARATION_PASS** | RESP独立源类型/profile、受限采集/监督、全部120B字段、独立中位周期/谱峰/自相关、冻结C源RR回放、13项离线测试及真实CLI退出码负例已完成 |
| E1 | **HOLD_FOR_SAFE_FIELD_GATE_AND_ACTUAL_MENU** | [精确10秒R2卡](AUTH-B-RESP-PILOT-001-R2.md)和禁用启动计划已备；尚无可审阅的现场电压/限流依据及实际独立呼吸15菜单确认，探针未打开 |
| E2 | NOT_RUN | 仅E1安全且见可信变化后另卡15→30两窗，当前采集profile未启用 |
| E3 | NOT_RUN | 仅E2周期跟踪成立后另卡12/18/24×2正式名义RR矩阵，不能提前签通过 |

本轮真实开发板读取、halt/go/reset、源菜单改变、接线变更、烧录与采集均为0。下文合成结果仅验证软件，不是实物L1/L2/L3。已通过的ECG六窗原码/摘要、旧profile、失败原件、整片备份和恢复副本均保留；BIO_V2源码及阈值未改，A/C/CAN/人体/云均未接入。

## 已收到的现场材料

负责人确认接线方式不变、未添加模块、SKX电池供电且无异常；此前为R红→RA、L黄→LA、F绿→RL，LL/胸导空置及USB/CAN/A/C/人体断开。电气信息第③项最初未给有效内容；随后负责人提供DLX-YQ2915照片并确认电池供电：可见OFF、白色直流20V档、红VΩ/黑第三孔COM位置；输入阻抗和校准未知，尚无实际电位/限流读数，不静默填成测量合格。尚未收到“当前独立呼吸15/1.5R”实际菜单回复，保持上轮普通ECG120状态描述。

新增出厂检测报告照片可见型号SKX-2000D+及呼吸15/30/45/60条目与手写数值；支持厂家声称进行过这些功能测试，可用于选择15→30对照。该页没有列动态阻抗端子、幅度单位/上下限、32kHz激励耐受、主动RLD电位/限流测试或测量不确定度，不能把表中名义数字当成独立校准的实际频率。本轮不鉴定报告真伪；照片原件、产品编号等仅私有保留，公开仅SHA及范围说明。

## E0实现及边界

源schema为`RESP_EXPLORATORY_SOURCE_1`，source_type=`RESP_EXPLORATORY`，独立呼吸模式；保存实际菜单文字、名义rpm、1.5R原文字段，Z0_ohm和delta_Zpp_ohm必须为null，dynamic_pair=UNVERIFIED。即便有规律RR，也不会写为ABS_IMPEDANCE_CALIBRATED。公共模板operator_ready=false，模式/15显示只是提案；不得用模板宣称设备已经切换或把它标成ORDINARY_ECG。

私有运行profile使用`BIO_V2_RESP_EXPLORATORY_CAPTURE_1`，绑定独立源门禁、单次10秒、准确读地址、SDK预算、固件ABI/BIN/ELF/符号、身份参考和全部共用/新增工具。共用的是冻结连接类和稳定槽重建器，以及固件ABI静态材料；没有复用ECG运行profile。源、安全记录和实际卡SHA在Open之前核验，未知Z允许探索但安全/菜单未就绪会拒绝。新采集器明确拒绝旧ECG profile，旧入口也不会被修改去接受RESP。

120B诊断按`8I + 4i + 14I + 4f`解码，保留所有30字段及ADC12项统计，分别记录hr/rpm原因位；有符号raw/filtered不再按无符号误读。原槽块、SHA/偏移/实际时间、完整诊断/启动配置缓存即时落盘；确认halt后单次128KiB RAM取head及稳定尾段。初始化缓存来源/时间属性如实标注，不冒称本轮SPI实时回读。控制次数、函数/地址/调试策略白名单及超时详见R2卡。

独立离线估计器只接受CH1原码及真实设备时间，不接收菜单数字作先验：完整性先核验，不补点，100ms分箱去线性趋势和小窗平滑，取相邻峰间隔中位数`60000/median(T_ms)`，同时输出谱峰及自相关估计、周期数和有限窗口分辨率。平直、过短、跳帧、flags或削顶输入拒绝评价；少量周期/估计器分歧只记未解出可信周期，不造稳定RR。

冻结自研C源Host回放另存RESP候选/接受/最后周期事件及逐样本raw/filtered/quality，明确标HOST_REPLAY；真实板上诊断、独立原码估计、Host回放和名义菜单参考分开。回放从首个保留帧重置，不冒称完整实板滤波历史或与ARM逐位一致。首次诊断以前的环形槽历史保留，但不混入本次10秒源状态周期结论。

## 实际软件验证与退出码

| 检查 | 实际结果 |
|---|---|
| Python/C真实头文件布局、RESP偏移、负原码及float | 通过；C宿主编译/运行均exit0，结构体120B |
| 13项新测试 | 全部通过，unittest真实exit0，含源类型/空菜单/null真值/错误芯片/ABI/地址布局/时长、reset/任意读写拒绝、尾段/恢复/退出失败、重复槽与3:2冲突、跳帧/flags/削顶/平直/噪声、时间回绕及Host事件 |
| 合成12/15/18/24/30次/分 | 独立三估计器一致，误差在测试±1次/分界内；仅合成功能回归，不是SKX实测 |
| 旧ECG profile负例（真实CLI） | worker1、监督1；RESP_PROFILE_SCHEMA_NO_ECG_REUSE，board_open_attempted=false |
| pending源负例（真实CLI） | worker1、监督1；RESP_SOURCE_NOT_READY，board_open_attempted=false；null阻抗未被拒绝，未就绪状态被拒绝 |
| 92秒参数负例（真实CLI） | argparse真实exit2，未启动worker/探针 |

初次测试发现两个Windows宿主问题：C源码中UTF8 include路径无法被当前GCC打开；ctypes宿主算法DLL句柄残留导致临时目录无法清理。修为复制真实头文件原字节到ASCII临时路径、结束回放后明确释放Host DLL；失败/复现及修复后日志分别保留。未改算法或旧ECG代码，也未用反复硬件尝试消化软件问题。

采集/监督和分析均记录真实退出码：采集0成功、1 STOP或前置拒绝、2导出失败；分析0相干变化、2完整性失败、3未观察到可信周期、1分析异常。成功HR/RR末值不能覆盖尾段或进程失败。SDK阻塞超时由独立监督终止，错误路径无自动reset/go。所有受限原件不覆盖。

## E1执行包与下一步

R2卡精确限定同一RA/LA/RL接法、独立呼吸15/1.5R、一个10秒窗、≤201槽块、≤21组完整诊断、受控SDK调用≤4000及额外Close≤1、halt≤1/go≤2/reset0，无Flash/options/GPIO/SPI配置写。profile02 SHA `3ff2e6b95ade0a1f35db97ce608a04fe7b2c303f460a0748f66a48362ce98857`，R2卡及工具SHA见E0回执；完整argv存私有E1-launch-plan，当前enabled=false、actual_source_record_sha256=null。01较早绑定和全部失败均保留。

目前只需补现场电气判断依据及其适用范围，不再把厂家ΔΩ/端子图列为绝对阻断。已据DLX-YQ2915照片完成[准确电气核对卡](AUTH-B-RESP-ELECTRICAL-001-R1.md)：当前仅第一组普通ECG120下的RA–RL/LA–RL/RA–LA直流20V粗筛，每对3秒、每组60秒上限、|V|≥0.20V即停，原三线不动；审阅实际读数后才安排独立呼吸15下第二组，仪表移开后才可能进入E1；不让负责人为回答而盲接普通接地示波器、带电电阻档或试碰RL。电气门成立后再按R2确认实际菜单、窒息文字及就绪源SHA，才运行一次E1。出厂报告可作为功能来源材料，与电气检查分列。

本轮不签E1_INPUT_SEEN、E2_RATE_TRACKING_SEEN或E3_NOMINAL_RR_ENGINEERING_PASS；亦不以未知输入或现有ECG原码计算RESP准确率。机器证据和测试日志见`../evidence/B-RESP-003/`，所有UID/Flash/RAM/原码/现场原图及执行包在受限`field-r3/resp-003`。正常提交/推送仅独立分支，远端字节核验记录仓库外DELIVERY-RECEIPT。
