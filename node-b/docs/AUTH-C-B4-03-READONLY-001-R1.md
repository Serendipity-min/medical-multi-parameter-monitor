# AUTH-C-B4-03-READONLY-001 R1｜当次C只读身份及恢复原件

2026-10-23。**待PI独立批准，尚未执行，不授权烧录或G4。** 当前J-Link在B、C尚未接入、USB未接、P4空置、无INMP441/TTS、全部CAN断开。准入范围与实际程序一一绑定；获批前不转接J-Link、不上电、不改任何跳帽。

## 对象、输入与现场准备范围

对象仅物理标记的C板STM32F407ZGT6（Cortex-M4 CPUID part0xC24、DBGMCU ID低12位0x413、Flash容量1024KiB）。当次UID读取后仅存EFS；拒绝与既有B UID相同的设备，防止J-Link仍在B。历史H3应用43172B/b9b25b18…、sector3配置336B/395c6a36…仅用于读后比较，不作为今天的Flash原件。

获批后先在不接CAN条件下确认C当前电源状态及网络隔离：保持现有J5供电方案，不替换电源、不并联B/C电源；C必须无USB/ETH，ESP断开或已有效隔离。需要断电隔离ESP或接调试排线时，C J5 OFF≤1/ON≤1，保持BOOT原正常Flash启动配置，不拨BOOT、不按RESET。仅把原J-Link从B端拔下≤1、接C端原调试口≤1；沿用其仅调试、不供电的已确认设置。不碰B传感器、电极或源菜单。P4空置保持不动。实际供电/接口看不清则不执行，不能根据此卡猜线。

程序 `node-b/tools/c_b4_readonly.py` SHA256 **39b39643d710079968c0ffe494d642d4beab731c0cb329d2d90d53415d6db756**；[冻结只读计划](../evidence/B4-003/c-readonly-disabled-plan.json) SHA256 **0c5e2bd32373da3097b049fc82757ce99c895fdfd48779f0eed41290a823a469**，包含全部依赖SHA和DLL SHA。计划enabled=false；只有PI批准后的受限EFS授权文件enabled=true、owner_approved=true、未过期、现场状态字段满足 `C_J5_ONLY_USB_OFF_JTAG_C_CAN_OFF_NO_MIC_TTS_ESP_ISOLATED` 才能加载SDK。授权独占消费一次，失败也不重用。

## 唯一软件会话与精确读取范围

| 操作 | 限额/规则 |
|---|---|
| Open/attach/Close | 唯一会话，各至多一次；SWD通过原调试口，1MHz，VTref须3000–3600mV；ForceAttachTarget、禁止自动连接重试及SkipDebugDeInit先于Device选择生效 |
| 完整Flash | `[0x08000000,0x08100000)`，1048576B，独立读取2次，每次原件先独占保存再核验；磁盘回读相同。单次SDK硬限45秒 |
| options | `[0x1FFFC000,0x1FFFC010)`，16B，独立2次，不写、不解锁；读RDP必须为0，WRP位只记录，不能解除 |
| 身份 | CPUID0xE000ED00/4B、DBGMCU_IDCODE0xE0042000/4B、UID0x1FFF7A10/12B、容量0x1FFF7A22/2B，前后身份/OPTCR一致 |
| Flash状态 | SR0x40023C0C、CR0x40023C10、OPTCR0x40023C14各4B；BSY/错误须0，CR锁定且PG/SER/MER/STRT未激活，否则STOP，不修复锁状态 |
| 运行状态 | DHCSR0xE000EDF0、VTOR0xE000ED08、CFSR0xE000ED28、HFSR0xE000ED2C、RCC_CSR0x40023874、DWT_PCSR0xE000101C、RCC_APB2ENR0x40023844、SYSCFG_MEMRMP0x40013800，各4B。PC为运行采样，不冒充暂停后的R15 |
| 合法零VTOR | 仅当VTOR=0时允许额外读取0地址64B和Flash首64B作向量别名比较；必须相同且运行PC采样位于Flash。不强设PC/MSP/VTOR或改变映射 |
| 禁止动作 | 显式reset/halt/go、写寄存器/RAM/Flash/options、冻结看门狗、清复位/Fault标志、BOOT/ROM切换、mass erase、unlock均0；不执行USB下载 |
| 硬限 | SDK调用<300，普通调用≤5秒，总会话≤180秒。超时只终止本次进程并保存真实退出码，不重连、不重试或重刷 |

## sector3/7/11与恢复规则

从每份完整Flash切出sector3 `[0x0800C000,0x08010000)` 16KiB、sector7 `[0x08060000,0x08080000)` 128KiB、sector11 `[0x080E0000,0x08100000)` 128KiB，各自SHA及完整1MiB前后比对。sector3可能含336B正式配置，但不打印或改写其正文；sector7/11无论是否全FF、是否硬件WRP，均按逻辑保护区处理。旧P资料曾把0x080E0000称sector7，本卡按F407真实扇区号修正，不能跟随旧名称扩大写入。

全部Flash、UID、options、配置及原生日志只入 `E:/medical-monitor-node-b-precan-private/20261023/` 新建受限EFS子目录，禁止覆盖旧原件、复制凭据到Git或终端。仅公开状态、SHA及是否匹配历史H3。新读回若不是历史H3/配置版本，仍保存真实原件，但 `H3_restore_identity_eligible=false`，禁止把历史镜像强刷上去；待PI另审。读取成功不等于已经恢复演练。

后续C台架21700B仅需评估sector0/1，不因此擦sector2/3/7/11；实际下载/回退工具另审。恢复的是本次确认属于H3的当次原应用及原尾部，最终完整1MiB/options逐字节与本次原件一致，配置及保护区均不变；此卡没有任何恢复写入授权。

## 退出与停止

入口旧DHCSR复位粘滞位单独记录；窗口内新增RESET、ROM、HALT、Fault、读回不一致或身份/保护变化立即STOP，不自动Go/重刷掩盖。正常Flash运行核验后SetRestartOnClose=1防止SDK退出遗留暂停；明确异常时禁止隐式续跑，I/O错误保留最近确认策略。原生阻塞被监督器终止时，CPU终态记UNKNOWN，不自行补救。PI批准及现场准备完成后才能使用本卡；现在只提交准备结果。
