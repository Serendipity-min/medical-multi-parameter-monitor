# AUTH-B-PREC-P0-STATE-001 R1｜当前原态单次连接取证

2026-10-23，Asia/Shanghai。离线审计已完成，CPU_ROOT_CAUSE_UNRESOLVED。本卡尚未执行，须负责人明确同意后才建enabled清单。因当前屏幕静止，先保存原态，不先人工复位/冷启动或重刷。后续动作不包含在本卡中。

## 现场冻结

同一B STM32F407ZGT6，原J5供电/BOOT跳帽/模块/JTAG连线保持。负责人最新确认已接串口屏、无波形变化，板USB未接；实际SKX为普通ECG60bpm，覆盖上一阶段24bpm的当前状态记录。电极仍原红RA/黄LL/绿RL，LA空；源电池断充电USB，CAN/A/C/人体断开，表笔离开OFF，不新增仪器。若条件变化先停，不自行改源/供电/电极/屏幕设置，也不打开COM口或自动下载软件。

本卡只授权Codex一次SDK会话：Open≤1、显式Connect≤1、Close≤1；**reset=halt=go=0，Flash/options/目标数据/PC/MSP/VTOR/BOOT/GPIO/RCC写0**，不发屏幕07命令、不升级/供电/启trace/Flashloader。SWD1000kHz，VTref须3.0–3.6V；单探针/唯一操作者Codex。SDK≤700次，另Close≤1；总180秒硬限，10秒是两组状态间观测等待，不是HR/RR采集窗口。

## 精确顺序

1. 校验卡/工具/DLL/身份参考/现场事实和本次授权原话SHA、输出不存在及EFS加密目录；未获批准清单在SDK构造前拒绝。
2. 按历史成熟流程在Device前施加SuppressGUI、DisableAutoUpdateFW、InhibitConnectRetries1、ForceAttachTarget1、SetRestartOnClose0、SetSkipDebugDeInit1及Flash/options禁缓存，Open前后均记录；不尝试不同策略。
3. 核身份后取首次状态：DHCSR/VTOR/RCC_CSR/Fault、映射/时钟、GPIO当前值、DWT和5个PCSR样本、设备/HMI计数、120B BIO/48B ADC统计/12B初始化缓存。首次快照已经在连接后，不冒称介入前状态；BIO ABI不符仍保存原件。
4. 仅若实际已经暂停，读取一组真实核心寄存器（名称≤256、值≤21）；否则不为读取PC新增halt，以PCSR样本记录并允许不可用。ROM或Fault被观察到时不go、不reset。
5. 单读完整Flash1MiB/options16B及0地址/ROM头64B，保存原件；若身份或映像不符立即停。匹配后取第二组状态，等10秒，再取第三组状态；最后保存一份128KiB RAM。此RAM是运行状态取证，不冒充暂停稳定采集或同步有效性窗口。
6. 一次Close即结束；失败不重试、不补go/reset、不开第二连接。SDK/标量/核心值与前后事件逐项写EFS日志。关闭后状态未知，不宣称Close无副作用。

RCC_CSR位粘滞不清除，不能当复位时间；DHCSR S_RESET_ST可能被SDK先读且读后清除，不能由“未见”反推无复位；GPIOB/PB2是当前电平而不是BOOT锁存。SYSCFG时钟未开时MEMRMP读值只记录不采信。任何无效PCSR（0/FFFFFFFF）不伪装成真实PC。

普通/槽读及策略调用≤5秒，Flash读≤45秒，RAM≤15秒，Close≤5秒；监督仅终止，不另连恢复。出现连接错误、身份/Flash/options漂移、复位/供电/异常或主人STOP，保存失败后停，不故意触发故障。主进程异常不续作后续卡。

## 地址/长度/次数白名单

|地址 / 字节|每会话最大次数|
|---|---:|
|`E000ED00` / 4|1|
|`E000EDF0` / 4|8|
|`E0042000` / 4|1|
|`1FFF7A10` / 12|1|
|`1FFF7A22` / 2|1|
|`40023C0C` / 4|1|
|`40023C14` / 4|1|
|`1FFFC000` / 16|1|
|`08000000` / 1048576|1|
|`E000ED04` / 4|3|
|`E000ED08` / 4|3|
|`E000ED24` / 4|3|
|`E000ED28` / 4|3|
|`E000ED2C` / 4|3|
|`E000ED30` / 4|3|
|`E000EDFC` / 4|3|
|`E0001000` / 4|3|
|`E0001004` / 4|3|
|`E000101C` / 4|15|
|`40013800` / 4|3|
|`40023874` / 4|3|
|`40023844` / 4|3|
|`40020410` / 4|3|
|`00000000` / 64|1|
|`1FFF0000` / 64|1|
|`20000000` / 131072|1|
|`20001AE4` / 120|3|
|`2000018C` / 48|3|
|`200001BC` / 12|3|
|`20000044` / 4|3|
|`2000013C` / 4|3|

核心读取只在S_HALT已成立时允许；没有任何写寄存器/内存或reset/halt/go函数的转发权限。所有共享底层与新协议逐项SHA冻结：

- `node-b/tools/runtime_state_b.py`：`39554d2292b50a604c2b28c7aaa31b442a348e2ab65a77f281ae0b56b3b8ad46`
- `node-b/tools/supervise_runtime_state_b.py`：`98587c514f8987e76851b87465259a0b3242cb4b222c2289c1b6de5b0f580b22`
- `node-b/tools/readback_b.py`：`a095665739454398e359accca3cf67e885de1fa51bff756b7f6b5192b0c00116`
- `node-b/tools/resp_exploratory.py`：`2b6a176b3568403fc8ba2e8ede92f537833d654112603a0b221e00e775762d77`
- `node-b/tools/precan_cpu_state_b.py`：`5f31200849906799ed15b71223cdd0a87015f449d4e785bb3b5e0f74aae6d5b0`
- `node-b/tools/supervise_precan_cpu_state_b.py`：`fc4282e68b560e780a3d6b996884f5d0cf0c286b0cb03c6b0f0447b578054164`
- `node-b/tests/test_precan_cpu_state_b.py`：`592b361217698c9394e5ec1490cd9cc2bc6f3d52369e99fcad69eaa4337eb8c3`

## 身份、归档和执行参数

冻结BIN25284B SHA438a8120f6df06ce219cdc30c0e5b697ac0e993f98d5a80521b10361536ae3ae；期待完整Flash f713277a50a5ec8d8a93317f412d5ab1b754e5d619918e57e9efe9dceef24cbb、options52d5979da03bd7be45e385920ec7d5901793bab3f6bc1daa0c1c1997f9e91687；UID/OPTCR私有参考SHA6807dc3c928c11b5ba3d2185286f2a7e18bc526485d7ac84edace59728dc0323。不会拿早期安装前完整备份69d9efb0…代替已安装候选f713…；两者均分级归档留存。

- DLL固定E:/medical-monitor-node-b-field-private/field-r3/jlink-986a-portable/JLink_x64.dll，SHA632d0d78e72b8a55c65945a0c393a9f081082c725fff4ba3081b0a565fd58cff。
- scope：PREC_P0_ONE_ATTACH_STATE_ONLY_10S_NO_RESET_HALT_GO。
- 准备清单：E:/medical-monitor-node-b-precan-private/20261023/state-s0-manifest-prepared.json；enabled/owner_state_authorized均false。
- 实际清单：同目录state-s0-manifest-ready.json，获准后另建，绑定本卡实际SHA、全部工具、现场记录与本次原话SHA。
- 一次输出：同目录state-s0-01，当前不存在；EFS加密＋私有ACL；旧历史原件不修改。
- 监督→工作进程：node-b/tools/supervise_precan_cpu_state_b.py → precan_cpu_state_b.py。
- 完整未来argv由准备清单中argv_ready固定；本卡实际SHA在清单中提供，卡自身不使用循环自引用hash。

worker0只代表当前观察完整且见应用推进，仍不是P0 PASS；worker3代表取证完整但运行异常/证据不足；worker1代表错误；监督0/1及调用方实际退出码分列，不能抹掉3或失败。8项离线负例通过，另有真实禁用CLI在SDK前拒绝；这些不是现场CPU验证。

本卡结束不自动进入冷启动、人工复位、第二连接、P1同步、P2测量或CAN。本卡不证明锁存时刻、不构成独立无调试器启动证据，不独自关闭根因。
