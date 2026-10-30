# P1-A：既有只读 SDK 调用链上下文

范围：`01864fb4c1ea35c9da38aa98b1e85790d2ed5415` 的源码静态分析及 DLL 文件纯字节 SHA256；未导入工具模块、未加载 DLL、未打开串口、未连接探针、未执行目标或云操作。此报告不是 P1-B 执行许可。

`P1_B = NOT_AUTHORIZED`；`CURRENT_BOARD_IDENTITY = NOT_READ`；`SDK_CONNECT_CLOSE_BEHAVIOR_ON_CURRENT_TARGET = UNKNOWN`。

## 1. 入口和职责边界

| 工具／函数 | 已有行为、依赖与前提 | P1-A 分类／可复用边界 |
| --- | --- | --- |
| `readback_b.py::Link`（45–175） | 构造时检查 DLL 哈希、创建独占本地日志、`os.add_dll_directory`、`ctypes.CDLL`；此时已跨入原生 SDK 边界。`open()` 在 Device 选择之前配置策略；Device 命令可能自动连接。 | 源码可读；实例化为 `FIELD_DENIED`。不能把构造器作为无副作用校验。 |
| `readback_b.py::acquire`（194–237） | 需要原先获准的暂停／续跑范围；运行态执行 `JLINKARM_Halt`，保存双份全片/options，若最初运行则 `JLINKARM_Go`。卡 SHA 等于调用方提供值并不构成本轮许可。 | `FIELD_DENIED`；**不是 P1-B 零 Halt/Go 入口**，仅复用数据格式/底层受约束调用思路。 |
| `runtime_state_b.py::RuntimeLink`（59–107） | 独立 API 和地址白名单；核心寄存器读取需 `register_reads_allowed`，其余读取受固定旧 ABI 地址和 700 次调用预算限制。`core_if_halted`（110–136）仅已暂停时读真实核心寄存器。 | 源码可复用；设备实例化及 CLI 为 `FIELD_DENIED`。旧 25284B 的 PC 区域/诊断 ABI 不可直接解释 B40928/B41012。 |
| `live_state_b.py::LiveLink`（43–80） | 增加 `SetRestartOnClose = 1`；仅 `verified_running_flash` 为真才允许。500 次 API 上限；固定旧 25284B Flash 读取与诊断地址。 | 作为父类设计参考；不是当前 P1-B 成品。隐式 Close 续跑须单独裁定。 |
| `b5_b_temp_readonly.py::authorize/Link/worker`（25–108） | 校验当期工具/DLL、旧安装回执、15s观察/90s会话、一次探针、零重试、EFS。按 B40928 温度 RAM ABI 读取真实快照。 | `FIELD_DENIED`；可复用 B40928 已有安装/身份匹配设计，但不能沿用旧 `.used` 或假定新候选 ABI。 |
| `b5_g3_devices.py::BLink`（24–90） | 继承 B4 Link；按 Profile 扩充允许 RAM/slot/UART ring 地址。完整 Flash/options 每种最多一次。结束正常 Flash 核验后才打开 Close 续跑；主机取消和原生失败区分。 | 源码可复用，必须由当期 Profile/授权绑定；构造或运行 `b_worker` 为 `FIELD_DENIED`。 |
| `b5_g3_devices.py::CLink/c_preflight`（93–146） | 继承 BridgeLink，但最外层 `call()` 只允许 `c.ro.CALLS`，不允许 DAP API。冻结 flags 四字节地址可由安装绑定传入；完整 Flash/options 各一次；90s上限。完整身份、全片/options与 DISARMED 验证后 Close。 | 可作为 C49132 只读准备的复用候选；不是独立 P1-B 授权入口。不能为得到双读证据偷偷增加会话或读次数。 |
| `b5_g2ro.py`（16–23、57–86、170–203） | 明确锁定历史 C24104 的完整 Flash/options；双全片和双 options、180s、一次探针、零重试；配置必须非 B5。 | `FIELD_DENIED`；**不允许套用 C49132/gen5**。复用其日志过滤、原生返回和独占存证方法即可。 |
| `c_b4_readonly.py`（54–144、147–168） | ReadLink API/地址白名单、旧 C 状态卡或历史现场例外、旧排除 B 身份；全片/options双读，正常时允许 Close 续跑。不是最新 B5 身份绑定。 | `FIELD_DENIED`；只作底层读法参考，旧 COM/ESP/CAN现场断言不能虚填到今天。 |
| `b5_g0_readonly.py::main`（193–218） | 建立EFS/ACL后经既有 SSH 别名执行远端 Python，读取配置并做网络/服务观察；不是“完全离线”。 | `FIELD_DENIED`（本轮无云连接许可）。`write_private`（186–190）单纯本地独占写加 EFS 验证可由调用方在许可范围内复用。 |

纯源码读取及本地文件 SHA 为 `SAFE_OFFLINE`；对这些模块的函数单测只有在原生 SDK、串口、网络和子进程均被替身封锁之后才属于 `REQUIRES_SANDBOX`。文件名含 readonly 不改变此分类。

## 2. 真实原生路径与副作用

### 2.1 连接和策略顺序

调用链：只读子类构造 → `readback_b.Link.__init__`（46–79）加载精确 DLL → `runtime_state_b.RuntimeLink.open`（77–96）→ 策略 `ExecCommand` → 探针计数/选择 → `OpenEx` → 再次确认策略 → `GetHWStatus` → `TIF_Select(1)`/`SetSpeed(1000)` → `Device = STM32F407ZG` → 条件 `Connect`。

| 原生操作 | 源码位置 | 建立的契约与尚未建立的事实 |
| --- | --- | --- |
| `ExecCommand` | `readback_b.py:99–113`、`runtime_state_b.py:68–70` | 只读子类仅允许固定命令；不是任意配置字符串。`SetRestartOnClose 0` 首次返回 1 且空文本时会再设置一次，源码将此解释为“返回此前值”；此解释尚无本轮独立 SDK 文档或真实回执验证，标 `UNKNOWN_NATIVE_SEMANTICS`。这不是连接重试，但也不是0次原生调用。 |
| `EMU_GetNumDevices`/`SelectUSB` | `runtime_state_b.py:82–83` | 必须恰一探针、选择USB 0。这只能选择探针，不能证明插在 B/C 哪块板。 |
| `OpenEx` | `runtime_state_b.py:84–85` | 返回 None 才接受；`opened=True` 在成功回执后设立。已可触及探针/目标。 |
| `GetHWStatus` | `runtime_state_b.py:88–91` | 返回0且VTref 3000–3600mV；VTref是电平参考，不是板卡身份或供电隔离证明。 |
| `TIF_Select`/`SetSpeed` | `runtime_state_b.py:92–93` | SWD=1、1000kHz固定；速度调用没有额外成功码断言。 |
| `Device`、`IsConnected`、`Connect` | `runtime_state_b.py:94–96` | Device选择本身可能连接；策略须先建立。只在未连接时显式 Connect，并接受非负返回；无循环自动重连。SDK内部是否仍隐式 halt/reset/连接处理：`UNKNOWN`。 |
| `ReadMemEx` | `readback_b.py:139–153`、下述各子类 | 固定 address,size,flags=0；全片45s、普通读5s。不能仅因读API就认定调试访问对运行时没有影响。 |
| `Close` | `readback_b.py:162–175` | 直接调用 `self.dll.JLINKARM_Close()`，**不经过子类 `call` 白名单**；记录5s心跳截止，但函数本身无可中断时限。依赖外部监督器终止卡住进程。Close退出后目标状态不是同次SDK能自证的事实。 |
| `SetRestartOnClose = 1` | `live_state_b.py:72–80` | 可使Close具有隐式续跑语义。显式 Go=0 不能解释为完全无目标控制副作用。只有经核验正常Flash且许可包含此行为时才可考虑。 |

固定策略见 `readback_b.py:18–21`：SuppressGUI、禁固件自动更新、Close不重启、禁止连接重试、ForceAttach、排除Flash/options缓存；`runtime_state_b.py:25,79–86` 添加 SetSkipDebugDeInit。SDK是否真正执行、何时生效与当前硬件上的残余副作用都不是静态源码能证明的事实。

### 2.2 Halt/Reset/Go、Configure和写API的可达性

- `readback_b.acquire` 在194–235行**主动 Halt 和 Go**；不得给P1-B直接选这个CLI。
- `runtime_state_b.CALLS`（26–30）不包含 Halt/Reset/Go/内存写；`CReadLink.call`（`c_b4_readonly.py:58–74`）还排除核心寄存器API。B温度Link和G3 BLink同样在最外层拒绝控制API。
- `b5_g2_site.BridgeLink`（96–136）源自 `b5_sector3_write.NativeLink`，历史桥接程序允许有限 `CORESIGHT_WriteAPDPReg` 改DP SELECT与AP CSW/TAR；其 `bridge_readonly`（139–175）会做原始AP交叉读及接口状态恢复。这是**历史G2桥接行为，不是本次允许行为**。
- `b5_sector3_write.py:149–162` 为父类声明 Halt/Reset/Configure/DAP API 原型；声明原型不等于已调用。该父类 `_call_native`（193–247）还拥有受阶段约束的 Halt/Reset/Go 和目标写引擎；所以不能绕过最外层子类去调用父类现场操作。
- `b5_g3_devices.CLink.call`（103–117）先要求 `name in c.ro.CALLS`，因此实际 `c_preflight` 路径的 DAP Write/Read/Configure、Halt/Reset/Go均被顶层排除；父类可写能力不能推断为该路径已写目标。固定四字节flags例外也只调用 `ReadMemEx`。
- Configure会重初始化调试接口的项目设计说明在 `b5_g2_site.py:149`；NativeLink.call在 `b5_sector3_write.py:174–175`直接拒绝 `JLINKARM_CORESIGHT_Configure`。本轮未做独立厂商语义验证，确切硬件效果仍标 `UNKNOWN`。

## 3. 地址范围、身份与ABI

### 3.1 可以申请复核的最小身份读范围

基础声明来源 `readback_b.py:15–17,178–190`：

| 起点／字节数 | 用途 |
| --- | --- |
| `0xE000ED00 / 4` | CPUID，核M4特征 |
| `0xE0042000 / 4` | DBGMCU ID，器件族0x413 |
| `0x1FFF7A10 / 12` | UID；只存受限EFS，不公开值 |
| `0x1FFF7A22 / 2` | Flash容量1024KiB |
| `0x40023C0C / 4`、`0x40023C14 / 4` | FLASH_SR/OPTCR；保护、忙与错误状态 |
| `0x1FFFC000 / 16` | Option Bytes |
| `0x08000000 / 1048576` | 1MiB完整Flash；只能申请固定计数，无故障重读 |
| `0xE000EDF0 / 4` | DHCSR；HALT/LOCKUP/RESET证据 |

运行态检查的额外寄存器来源 `c_b4_readonly.py:22–26`：VTOR、CFSR、HFSR、RCC_CSR、DWT_PCSR、RCC_APB2ENR、SYSCFG_MEMRMP、FLASH_CR；各4B。必要时的`0/64`和`0x08000000/64`仅用于VTOR=0时Flash别名对照（91–103）。`check_running` 要求无HALT/LOCKUP/新RESET、无Fault、Flash空闲锁定、不在ROM且能观察到Flash区PC样本。PCSR不是暂停后的真实PC/MSP。

### 3.2 不得混用的版本

- `live_state_b.py:16–21,100–103` 绑定25284B旧候选；`runtime_state_b.py:48–56` 的 `pc_region` Flash末端仍为旧`0x080062c4`。不能据它否定当前较大应用的合法PC。
- `b4_runtime.py:21–25,114–116` 绑定39948B及旧RAM；B40928B温度ABI应使用 `b5_b_temp_readonly.py:17–19` 的 bio=`0x20001d20/120`、ADC=`0x20000614/48`、寄存器缓存=`0x20000644/12`、CAN=`0x2000377c/44`、temperature=`0x20004c78/64`。这些是历史工具布局，不是今日实板已验事实。
- G3 BLink按 `profile['RAM']`、`slots`和`UART_ring`追加地址（`b5_g3_devices.py:25–32`）；必须先用精确BIN/ELF/symbols绑定验证Profile。不能把B41012候选标识注入B40928实板记录，也不能因两个版本某些地址相同就跳过版本核验。
- `b5_g2ro.py:17–23,77–84,184–198` 固定C24104完整Flash及旧配置身份，与C49132/gen5不兼容。
- `c_b4_readonly.py:147–168` 的现场例外与旧COM15/CAN状态为历史；`c_b4_closeout_readonly.py`另绑定23952B旧基线。都不能替代本轮C49132身份/全片/options参考。
- G3 CLink可读取安装绑定提供的 `_C_flags_address`（`b5_g3_devices.py:121–138`）；没有冻结来源时不能猜flags地址或扩大内存白名单。P1-B仅身份/完整Flash/options核对未必需要业务flags。

## 4. 原生返回、预算、异常与Close

| 实现 | 现有契约 | 不能扩大为的结论 |
| --- | --- | --- |
| `readback_b.Link.call/read`（86–97、139–153） | native调用前记deadline，返回后查期限与SDK错误回调，Read返回必须等于请求；全片45s、普通5s，Link会话180s。 | 若SDK先阻塞，Python自身不能中断DLL；必须监督器。负数与正短读都报PARTIAL_READ，历史原生返回日志有保存。 |
| `runtime_state_b.RuntimeLink.call/read`（65–107） | 700次；RAM全块15s；精确长度。 | “SDK调用预算足够”不证明目标CPU无扰动。 |
| `b5_b_temp_readonly.Link`（40–54） | 3000次；精确地址/长度；worker15s采样，authorize90s/一次探针/零重试。 | 故障时仍可能已有Close策略=1；未取消前不能声称保存暂停态。 |
| `b5_g3_devices.BLink.call/read`（46–78） | 100000次、原生整数返回先记录；`n<0`与正短读分别`G3_B_NATIVE_READ_ERROR`/`G3_B_POSITIVE_SHORT_READ`；错误设native_failed并撤销running资格。完整Flash/options各一次。 | 门禁自身预算拒绝不等于MCU故障。deadline/session失败不是允许重连的理由。 |
| `b5_g3_devices.CLink.call/read`（93–117） | 会话90s，完整Flash/options各一次；flags必须恰读4B；其他读取走父类长度检查。 | 不能调用历史G2RO双读流程补齐额外回执；须独立申请读次数。 |
| `b5_g2ro.ReadLink`（105–148） | 300次，完整Flash/options各最多2次；Close=0最多6次、Close=1最多1次；native返回类型/整数先留日志。 | 旧工具良好返回处理不使C24104身份变成C49132。 |

Close策略失败路径并不完全相同：`live_state_b.inspect`（124–143）、`c_b4_readonly.worker`（183–195）及`b5_g2ro.worker`（221–237）通过嵌套finally保证取消续跑失败时仍尝试唯一Close；`b5_b_temp_readonly.worker`（99–105）在同一个try中先取消、再Close，取消抛错会跳过Close。G3 C preflight（140–146）不单独取消已启用续跑；若设置Close=1成功后没有新的目标读，此后故障路径与“SDK错误后还可否发取消命令”须由未来逐板方案明确。**本报告记录这些前提差异，不在P1-A偷偷修复现场恢复逻辑。**

`b5_g3_devices.BLink.prepare_host_cancel_close`（80–86）仅在SDK健康且未native_failed时允许主机取消清理，额外做一次CPU快照以验证正常Flash，再启用续跑；ROM/HALT/native失败不走此分支。其额外读是否属于未来P1-B的许可必须写入申请，不能沿用G3窗口许可。

监督器 `b5_g2ro_supervisor.py:12–25`、`b5_sector3_write_supervisor.py:12–27` 与 `supervise_runtime_state_b.py:12–46` 超时只结束子进程，不自动重连/Reset。kill并不保证已执行Close，也不保证SDK或目标状态；超时必须记 `UNKNOWN_NO_RECONNECT` 并交负责人按批准方案处理。

## 5. DLL身份核对

只执行了文件 SHA256 读取，**没有LoadLibrary/CDLL**：

- 预期：`readback_b.py:12`，SHA256=`632d0d78e72b8a55c65945a0c393a9f081082c725fff4ba3081b0a565fd58cff`。
- 本机既有便携 DLL 字节核对：同上，`DLL_BYTES_MATCH = true`。
- `DLL_LOAD = NOT_EXECUTED`；当前板上的原生策略返回、连接/关闭副作用均 `NOT_OBSERVED`。工具文件SHA由主交付清单统一登记，不在报告内自引用。

## 6. P1-B逐板申请必须冻结的内容

本节仅准备申请字段，**不创建授权JSON、不签名、不产生nonce或.used、不运行任何探针会话**。

1. 板角色B/C分别审批：B40928B历史BIN及完整Flash参考，C49132B历史BIN及完整Flash参考；UID/options参考只由受限EFS原件定位，先验哈希与今日读回分开。
2. 新工具Git提交与逐文件字节SHA、精确DLL SHA、唯一入口、读地址/尺寸/计数、单次会话/零重试、原生每次时限、整会话上限、日志独占/EFS与脱敏策略。
3. 当前负责人报告：USB在C、J-Link在B、未上电、SKX呼吸模式、黄L在LL、其他线不变。仅作 `OWNER_REPORTED`；没有本轮目视照片/时刻、J-Link电脑端供电和C USB反供电排除证据，不能写 `TOOL_VERIFIED_ALL_DARK`。SKX开机具体状态/菜单值须独立确认，不因“模拟呼吸波形”自动补造数值。
4. B板保持/恢复供电的完整人工步骤单独批准；C板若需移动调试排线，需独立冷态转接授权及负责人操作，绝不借B板申请顺带移到C。
5. SDK Device可能隐式连接、Close策略是否允许=1、正常/异常Close允许哪些命令均由PI预裁定；对不能证明无halt/reset的SDK行为保留风险，不以显式控制计数0宣称全程无CPU动作。
6. 发生UID/Flash/options不符、ROM/HALT/Lockup/Fault/新RESET、负返回/正短读、原生超时或未知状态：`STOP_TARGET_NO_RECOVERY`；保存许可内已有证据，不重读凑齐、不连接补救、不Go/Reset/写寄存器，不自动重刷。负责人承担批准的现场断电责任。
7. 签署/授权引用、起止时间窗、唯一nonce、一次性消费验证必须在未来专门授权机制批准后建立。本轮不填入有效值、不接受任意非空 `pi_signature`。

## 7. 仍未建立的假设

- `NOTHING_FOUND`：当前SDK和便携DLL在这些板的当前态下必然无隐式halt/reset的独立证明；静态白名单只能证明调用意图。
- `NOTHING_FOUND`：Close返回后目标仍正常运行的独立观察证据；补一次连接将是另一次未获授权的会话。
- `NOTHING_FOUND`：P1-B最新完整合同、逐板PI授权和可验证授权机制（主代理另行登记文件交付情况）。
- `UNKNOWN`：今日芯片/UID/完整Flash/options；本轮无电子只读取证。
- `UNKNOWN`：今日USB反供电、J-Link电脑端、J3/额外导联实际状态；历史事实与本次负责人文字分别记录。

结论：可复用已有SDK封装的固定地址、原生返回日志、单次监督和EFS存证设计；**不能执行历史readback_b.acquire、C24104流程或任意旧卡来完成本轮P1-B**。本轮保持 `HALT_BEFORE_CONNECT`。
