# AUTH-B-RUNTIME-STATE-001 R1｜启动与J-Link关闭/重连只读核验卡

2026-10-22 Asia/Shanghai。依据负责人本轮“继续排查，先准备启动和运行状态只读核验的精确授权卡，重点检查PC、VTOR以及J-Link连接和关闭流程，然后继续采集”。本卡只覆盖下面两次预先列明的只读连接。目标内存/Flash/options/GPIO/SPI配置写0，halt/go/reset均0；没有恢复或烧录权限。R3失败一次及所有旧原件保留，不复用R3。

## 固定现场和身份

同一B板STM32F407ZGT6、J5/YL-1210供电ON、BOOT B0/B1原GND位置；J-Link原接口，ADS1292_V2.0/5V/common GND/START PG15/DRDY PA3保持。负责人确认未移动或操作开发板，唯一操作方Codex；不要求重新插拔或测量。R红→RA、L黄→LA、F绿主动RLD→RL，LL/胸导空置；无CAN/A/C/人体，SKX独立呼吸波形15bpm/1.5R、电池、断USB，万用表已移开OFF。窒息未知且不更改，Z0/ΔΩ=null。

真实UID/OPTCR仅绑定受限原参考，SHA256 `6807dc3c928c11b5ba3d2185286f2a7e18bc526485d7ac84edace59728dc0323`，每次仍重新读取确认。完整Flash期望`f713277a50a5ec8d8a93317f412d5ab1b754e5d619918e57e9efe9dceef24cbb`，options期望`52d5979da03bd7be45e385920ec7d5901793bab3f6bc1daa0c1c1997f9e91687`。固件BIN25284B SHA`438a8120f6df06ce219cdc30c0e5b697ac0e993f98d5a80521b10361536ae3ae`，不改变固件或BIO_V2阈值。

## 会话、预算和入口

使用冻结官方9.86a DLL `E:/medical-monitor-node-b-field-private/field-r3/jlink-986a-portable/JLink_x64.dll`，SHA`632d0d78e72b8a55c65945a0c393a9f081082c725fff4ba3081b0a565fd58cff`；单探针、VTref3000–3600mV、SWD1000kHz。代码与manifest哈希在Open前核对。入口`supervise_runtime_state_b.py`→`runtime_state_b.py`；准确argv、卡SHA和依赖SHA在受限`resp-003/runtime-state-01-manifest-private.json`独占保存，输出固定`resp-003/runtime-state-01`且必须不存在。

计划恰好两次连接，每次Open≤1、显式Connect≤1、Close≤1，无连接重试；第二次仅在第一轮IO完整且Close成功后进行，用于已列明的关闭/再连接比较，非失败重试。每轮受控SDK调用≤700，共≤1400，另Close≤2，总≤1402。普通SDK≤5秒、Flash读取≤45秒、RAM≤15秒，全流程硬上限240秒；独立监督器仅终止，不另开连接或补发硬件命令。

原保护策略在Open前先设置，Open后在Device选择前重申：SuppressGUI、DisableAutoUpdateFW、SetRestartOnClose0、InhibitConnectRetries1、ForceAttachTarget1、Flash/options禁缓存、SetSkipDebugDeInit1。Device选择可能连接，策略不留到事后。SDK执行命令只允许这些精确字符串及Device=STM32F407ZG；不发reset/供电/解锁/下载/WorkRAM/indirectread/trace启用命令。J-Link连接本身需要调试协议交互；“只读”指不写应用数据或配置，不声称无调试访问副作用。

## 精确读取白名单

每次连接：当次身份→attach-entry快照→已暂停才读核寄存器→完整Flash/options→别名和ROM向量→after-flash快照→128KiB RAM→间隔0.5秒→before-close快照→Close。两轮间隔0.5秒。

| 地址/长度 | 内容与次数（每次连接） |
|---|---|
| E000ED00/4、E0042000/4、1FFF7A10/12、1FFF7A22/2、40023C14/4、40023C0C/4 | 身份各1次，匹配私有参考 |
| 08000000/1048576、1FFFC000/16 | 整片Flash/options各1次，哈希核对；Flash头64B从缓冲切片 |
| 00000000/64、1FFF0000/64 | 别名/ROM向量各1次，比较是否等于本次Flash头或ROM |
| 20000000/131072 | RAM1次，运行态非原子，仅诊断原件，不认证稳定槽或RR |
| E000EDF0/4 | 每快照前后各1次、核寄存器前后检查，≤9次；原u32落盘 |
| E000ED04/4、E000ED08/4、E000ED24/4、E000ED28/4、E000ED2C/4、E000ED30/4、E000EDFC/4 | ICSR/VTOR/SHCSR/CFSR/HFSR/DFSR/DEMCR每快照各1次，共3次；只读不清故障寄存器 |
| E0001000/4、E0001004/4 | DWT_CTRL/CYCCNT各3次，不写TRCENA/DWT |
| E000101C/4 | DWT_PCSR，每快照5次、各间隔20ms，共15次；这是运行指令地址采样，不冒称暂停态精确R15 |
| 40013800/4、40023874/4、40023844/4、40020410/4 | MEMRMP/RCC_CSR/APB2ENR/GPIOB_IDR各3次；PB2现值不等于上电BOOT采样，SYSCFG时钟关时MEMRMP不单独作为启动结论 |
| 20001AE4/120、2000018C/48、200001BC/12 | 完整诊断/ADC统计/初始化RREG缓存各3次，ABI错误也保留原件和系统快照；不新发SPI |
| SDK核寄存器 | 仅已有S_HALT且再次核对后，GetRegisterList≤256项、名称≤256，读取R0–R15/MSP/PSP/XPSR/CONTROL/PRIMASK中已枚举项至多21个；运行态绝不调用ReadReg，不隐式halt取PC |

## 判断和停止

身份/哈希/部分读/SDK错误/超时/STOP即停，失败不进入第二连接。ROM或ABI异常本身允许完成已批准的系统快照和关闭/重连比较，但绝不自动go、reset或采集；完整读取并发现异常worker=3，监督=1，异常/前置拒绝worker=1，参数错误真实2。原件、真实返回码、Close尝试/完成及每次u32均保留。只有两轮均确认VTOR=08000000、运行状态正常、观察到候选Flash范围PC、有效BIO诊断/样本前进、ADC无错、初始化缓存匹配且两轮样本未回退，才记RUNTIME_CAPTURE_READY；后续仍使用新采集卡及新输出目录。

本卡不重置DWT、清RCC复位标志、改BOOT/导联/电源/源菜单，不进入E2/E3。若PC落ROM、VTOR指ROM或程序未初始化，先形成实际诊断结论；本卡不授权从ROM跳回Flash或复位。Close后的目标不能在同一已关闭连接观测；第二轮包含重新连接影响，不能把差异唯一归因于Close。ARM DWT_PCSR零/无效值记无PC证据，不写寄存器强制采样。

## 依据

- [SEGGER命令说明](https://kb.segger.com/J-Link_Command_Strings)：ForceAttachTarget跳过目标初始化；SetRestartOnClose0禁止关闭时自动go；SetSkipDebugDeInit1保留应用使用的调试单元。只说明策略意图，不能据此宣称SDK行为已被独立观测。
- [Cortex-M4 r0p1 TRM，DWT寄存器表](https://www.keil.com/dd/docs/datashts/arm/cortex_m4/r0p1/ddi0439c_cortex_m4_r0p1_trm.pdf)：DWT_PCSR E000101C只读PC采样。
- 本机RM0090 Rev11第70–71、291、262页：BOOT采样/内存映射、MEMRMP、RCC_CSR；不将历史读值冒充本次值。

## 冻结工具SHA256

- `node-b/tools/runtime_state_b.py`：`39554d2292b50a604c2b28c7aaa31b442a348e2ab65a77f281ae0b56b3b8ad46`
- `node-b/tools/supervise_runtime_state_b.py`：`98587c514f8987e76851b87465259a0b3242cb4b222c2289c1b6de5b0f580b22`
- `node-b/tools/readback_b.py`：`a095665739454398e359accca3cf67e885de1fa51bff756b7f6b5192b0c00116`
- `node-b/tools/resp_exploratory.py`：`2b6a176b3568403fc8ba2e8ede92f537833d654112603a0b221e00e775762d77`
