# AUTH-B-READBACK-001 R2｜当次B板身份与完整备份执行卡

2026-10-22，Asia/Shanghai。前版R1保留，不沿用其中已被负责人补齐或撤销的重复资料要求。

## 授权依据与现场事实

负责人本轮明确说明：“由J5供电，jlink只负责烧录”，“前面已经经过确认供电和jlink正常，我不在提供J-Link型号，连线等”，“B0和B1均连接GND，未连接CAN，未连接模拟器与真实人体”，“如果没有问题，就开始链接模拟源，进行采集，排查分析原因”。

据此采用负责人确认的现有供电/JTAG接线，不再索要探针型号及重新拍线。按本次继续执行指令，先执行采集所必需的身份/备份；本卡在实际调用探针前提交展示。尚未解决的模拟源电气兼容与采集适配不被默认为PASS，因此本卡不接源、不写候选、不采样。

| 字段 | 当次冻结值 |
|---|---|
| 对象/操作者 | B，负责人确认STM32F407ZGT6；唯一Codex /root；没有其他调试或自动下载程序 |
| 供电 | 负责人确认J5现有路径，J-Link仅调试不供电；铭牌YL-1210，12V DC/1A、中心正极 |
| 供电依据 | E:/stm32/stm32文件/STM32F407_原理图.pdf第3页DC IN标6–24V，图纸SHA7737115d…；名义12V处于范围内，不冒称本次实测电压 |
| 启动/外部 | B0/B1均GND，正常Flash启动；CAN、模拟器、人体均未连接；现有ADS模块接B保持原状 |
| 探针接线 | 已连接B的JTAG模块，沿用负责人已确认正常的接法；本次选SWD 1000kHz，不改排线或跳帽 |
| 供电动作 | 不用软件切电；若板仍断电，只测得VTref不足便停止，不自动供电。已授权的J5上电由负责人完成，不接第二路电源 |

## 工具及脱机验证

原V5.12和本机7.22b不满足本次受控attach策略，不尝试在B上验证。采用官方便携发行9.86a的JLink_x64.dll，版本数98601，27023344B，SHA256 `632d0d78e72b8a55c65945a0c393a9f081082c725fff4ba3081b0a565fd58cff`，位于本次受限field-r3/jlink-986a-portable目录。

官方发行包86724120B，SHA256 `5bb3160bd3467a17fdbad3e8802d3aedad2f8b7358f88d052989ae7518b957a4`，Windows签名Valid/SEGGER。只解包，不运行安装器、不改现有安装/USB驱动、不自动升级探针固件。MSI管理解包曾被自动审批以blocked by policy拒绝；后改用官方7-Zip发行包的CRC有效归档载荷，以纯文件解包方式取得工具，没有执行任何安装器。

入口为node-b/tools/supervise_readback.py及readback_b.py，精确SHA在随卡manifest中；卡文件自身SHA在运行命令和回执绑定，不写入自身。七项合成/并发状态机测试已通过；真实新版DLL不Open/Connect的策略解析检查通过，故意未知命令被拒绝。

执行顺序：Open前设置SuppressGUI、禁止固件自动更新、SetRestartOnClose 0、InhibitConnectRetries = 1、ForceAttachTarget = 1；Open后先再次确认关闭不go，再确认其余连接策略；排除整个用户Flash和options的SDK缓存；只允许识别到一个USB探针，VTref需3000–3600mV；全部成功才选SWD/速度/Device。Device选择可能连接目标，故其前必须已完成所有guard；禁止默认失败复位重试。

## 动作、地址及停止

1. 仅一次探针会话，先读取探针参考电压；不在VTref不足时访问目标或开供电。
2. 目标读取固定白名单：CPUID 0xE000ED00/4B、DHCSR 0xE000EDF0/4B、DBGMCU_IDCODE 0xE0042000/4B、UID 0x1FFF7A10/12B、容量0x1FFF7A22/2B、FLASH_SR 0x40023C0C/4B、OPTCR 0x40023C14/4B。
3. 容量须1024KiB、DEV_ID低12位0x413、核为M4、RDP=0xAA、Flash非忙/无错误。任何不符立即STOP，不解锁。
4. 初态RUNNING则halt最多1次，确认后保留暂停；初态HALTED不发halt也不擅自go。记录并清读初次RESET粘滞状态基准，随后新RESET/LOCKUP/HALT丢失均停止。不写看门狗冻结寄存器。
5. 同一暂停窗口独立双读options `[0x1FFFC000,0x1FFFC010)` 各16B，以及完整Flash `[0x08000000,0x08100000)` 各1048576B；每次读前后核halt/reset，双读之间核身份/保护。关闭Flash缓存，不以复制第一次文件充当第二次读板。
6. 重开磁盘文件核长度、逐字节一致和SHA。只有全部成功且原为RUNNING、由本卡halt，才go最多1次并两次确认运行；原为HALTED保持HALTED。失败不追加go/reset/reconnect，关闭禁止自动go。
7. 成功后本地再封存同ACL恢复副本并核SHA；本卡不回灌，不写Flash，不执行候选下载或模拟源连接。备份时点为本次正常上电后的暂停点，不宣称上电前字节已观测。

普通SDK调用硬超时5s，halt3s，完整Flash长读45s，全会话180s；独立监督进程读取每调用心跳，超时或STOP终止子进程，不再调用目标。原始DLL输出仅写受限日志。复位请求=0、Flash/options/RDP/OTP写=0、擦除=0、目标供电控制=0、模拟器/导联/采集=0。h/go属于明确列出的调试状态变化，不称为零运行态扰动。

原件：E:/medical-monitor-node-b-field-private/field-r3下唯一readback运行目录。真实UID、探针序号、双读Flash/options及原始日志不入Git；公开仅脱敏状态。任何失败原件独立保存，停止后不自动重试。

有效范围：本轮这一次备份窗口，开始后180秒内，成功或STOP即结束；后续连接源、烧录或采集另展示精确卡并按负责人继续执行指令及实际准入条件处理。当前没有宣布ECG或RESP输入已合格。
