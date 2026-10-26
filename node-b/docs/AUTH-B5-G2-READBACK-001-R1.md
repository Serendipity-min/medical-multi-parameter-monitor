# AUTH-B5-G2-READBACK-001 R1｜新鲜C身份/双备份，禁用

`enabled=false; owner_approved=false; executions=0`。[共同绑定](B5-G0-SPLIT-AUTHORIZATIONS.md)适用。本卡只准备，G0不连接调试器或串口。

批准对象为C STM32F407ZGT6私有UID与既有C原件一致；不得把接在B的探针当C。现场需单独明确调试排线转接、C现有供电与USB状态、ESP隔离方式。未经另批不拔插/复位/改BOOT；B保持当前部署且不读不写。

一次会话，180秒硬限，重试0，显式reset/halt/go/寄存器写/Flash写/解保护均0。SDK连接与关闭须冻结ForceAttachTarget、SetRestartOnClose、SetSkipDebugDeInit及调用顺序，退出不得使已运行的Flash停止；仅确认正在Flash运行后使用已验证的退出续跑策略，异常不发Go恢复。若SDK无法在此预算下取得某个寄存器，填NOT_OBSERVED并停止相应门禁，不能擅自halt。未冻结新scope工具及DLL SHA前不可执行。

按序只读：

1. UID、DBGMCU_IDCODE、CPUID、Flash容量、OPTCR/Flash SR/CR，必须匹配F407/1MiB、RDP0和目标扇区可写条件；不解除任何保护。
2. DHCSR、VTOR、DWT_PCSR连续三点、RCC_CSR、SYSCFG_MEMRMP、CFSR/HFSR及当前Flash头64B、0地址映射64B。DWT采样单列；真实PC/MSP只有非侵入接口能提供时记录，否则未知，不能把向量值充当真实寄存器。观察ROM/HALT即停，不先复位。
3. 独立SDK读取两次Flash：起始`0x08000000`，每次1048576B，结束`0x08100000`；读取两次options：`0x1FFFC000`，每次16B，结束`0x1FFFC010`。两次不同文件，分别保存SDK调用与真实返回长度/退出码，不能复制首份充第二份。
4. 分别从两份整片切出sector3 `[0x0800C000,0x08010000)`16384B、sector7 `[0x08060000,0x08080000)`131072B、sector11 `[0x080E0000,0x08100000)`131072B；身份前后、options及每区双份逐字节相同。sector3只解析336B提交记录/CRC/身份布尔，原件不输出。
5. 受限EFS独占目录保存Flash/options/UID/配置/日志；核验每文件EFS和目录ACL，发布SHA、长度和脱敏布尔。若与C24104历史全片`b460d917…`不同，保留新原件并停止，不使用旧包套写。

通过只代表新鲜原件可追溯；不代表B5已安装、恢复演练、sector3配置准入或ROM根因已修复。后续纯离线从本次双读重新生成42552B三扇区包，重新核对完整预期SHA及所有保护区；历史G0布局包不得直接装板。
