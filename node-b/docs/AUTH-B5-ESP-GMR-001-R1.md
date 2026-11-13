# AUTH-B5-ESP-GMR-001 R1｜独立ESP版本查询，待批准

`enabled=false; owner_approved=false; executions=0`。这是一笔新的ESP身份查询，不复用已经失败停止的G3许可。G3首次START已消费，不能据本卡重启云窗、重发B5START或重启测试服务。

## 目的与准确权限

确认当前ESP的实际AT/SDK版本。C42552B没有AT透传入口；COM6通向MCU的USART1，不能直接向该口发AT冒充查询ESP。板载CH340由5V供电，未核实TX逻辑电平前也不把它直接跨接到ESP RX。

本卡采用已有MEM-AP连接流程，C正常运行且DISARMED时，向**USART3_DR `0x40004804`**依次写入固定的 `AT\r\n`（4字节）；仅成功后再写 `AT+GMR\r\n`（8字节）。ESP查询不改其配置，但这**不是对C全目标零写入**：最多12次UART数据字节写请求，须本卡单独批准。禁止其他指令、空命令、+++、扫描波特率、ESP复位/升级/证书操作。

不写Flash、sector3、options、RAM、GPIO、BOOT、PC/MSP/VTOR或UART波特率/控制寄存器；显式halt/go/reset均0。不发送Wi-Fi/TLS/MQTT命令或B5START，不恢复/修改云端。ESP继续在板供电，非隔离例外只用于本查询，自主联网状态仍UNKNOWN。

## 一次冷态准备，由负责人完成

1. 关B/C J5，拔C USB及J-Link电脑端USB，确认板/ADS/屏/ESP全部熄灭并等10秒；不把此前未确认断电写成已完成。
2. 只把整只JTAG排线从B转到C；P5/P7、P4/P6、CAN/独立GND、BOOT和源/电极均保持现状，不改ESP接线或供电引脚。方向不确定就停。
3. 只恢复C原J5供电及J-Link电脑端USB。B保持断电，C USB_UART保持断开，不按RESET。完成后一次回复“冷态完成，J-Link在C，C为J5，B断电，C USB断开”，有异常即停。

## 固定执行与停止

仅 `b5_esp_gmr.py --execute --authorization <受限EFS独立许可>`，一个SDK连接/关闭、总硬限180秒、每个API单独监督；输出独占且一次性.used，不重试、不自动恢复。工具、依赖、卡及ELF SHA见[冻结清单](../evidence/B5-ESP-GMR-PREP/bindings.json)。

先核C私有UID/F407/1MiB/保护、正常Flash运行、完整Flash `acb33fdd39ecb016ecd848ec25eee051635f56ef8138b577a8590d2734ad687e`、options `52d5979da03bd7be45e385920ec7d5901793bab3f6bc1daa0c1c1997f9e91687`和DISARMED四字节0。C ELF SHA `3c726f61f76eadac4909826203ca84dee65521aec448ad477ddca0c3c58795d8`已与42552B BIN绑定；固定RX环8192B在`0x2000F6D4`、head `0x2000F6D0`、tail `0x2000F6CC`、UART计数块 `0x2000F6C0+20`。只读这些运行中对象及系统/身份白名单，不使用任意RAM扫描。

核对当前USART3寄存器与8MHz HSE/APB分频计算的实际波特率必须在115200±1%且8N1、RX中断打开；若不符，只记录停止，不改波特率。复用已连接目标做SDK/MEM-AP只读交叉核验，禁止重新Configure。AP的SELECT规范化为0并恢复可读CSW/TAR；只允许带一次性字节许可的UART_DR写，Flash控制/数据地址永远不可写。

AT等待最多2秒，GMR最多3秒；由运行中的USART3中断将ESP响应写入原接收环，主机只读新字节。保留原始响应和错误增量，区分NO_BYTES、非OK/ERROR、UART错误和版本缺失，不能把“未收到OK”自动改写为“旧模块”。不能为了读到版本重复AT、延长窗口或改波特率。GMR版本不证明模块生产年代、物理Flash容量或TLS通过。

成功后独立重读完整Flash/options，核对逐字节不变、DISARMED和UART配置不变、CPU仍正常Flash运行；完整Flash/options各最多2读（前/后各1），不是重复G2-RO双备份。纯协议失败且SDK仍健康时仅做收尾身份/字节验证，不再发送查询；原生DLL错误/短读、ROM/HALT/复位立即停止，不以复位/重刷掩盖。正常Flash核验后才设置关闭续跑；异常关闭不擅自Go。

原始Flash、UID、UART环及响应、SDK回执和实际启用许可仅存现有受限EFS，日志不输出可能出现的Wi-Fi信息。Git只保存版本字符串、SHA、计数和真实退出码。结束后保持现状，不自动恢复H3、回退配置、恢复跳帽或重新进入G3；需后续决定。
