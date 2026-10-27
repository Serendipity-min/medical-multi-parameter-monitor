# AUTH-B5-ESP-GMR-001 R4｜重新插入后的一次查询

负责人本次明确要求“重新插入模块后再测试一次”，并提供照片和模块灯闪烁现象。本卡绑定该新许可，独立一次会话、180秒硬限、失败不重试；不复用R1/R2/R3或G3的已消费许可。

继续使用R3已冻结的固定查询逻辑：115200/8N1，AT一次成功后才GMR一次，USART3_DR `0x40004804`最多12个字节写请求。禁止Flash/options/sector3/RAM/GPIO/波特率/核心寄存器写入、halt/go/reset、ESP升级、联网命令与B5START。不是全目标零写；唯一目标写权限仍是上述固定UART数据字节。

现场沿用最后已确认路线：J-Link在C、C原J5供电、B断电、C USB_UART断开；本次没有报告改变这些路线，不重复要求转接或复位。模块已重新插入是新现场事实，插入时灯闪烁不作为供电电压或AT版本证明。重插是否在断电时进行UNKNOWN，不填成新冷启动通过。照片中P5两竖帽看起来为WB_TX↔PB11_RX、WB_RX↔PB10_TX，模块在P1、Bluetooth/P2空置；照片不代替通断测量。硬件身份与实际运行状态由工具先读回核验，若路线不符、ROM/HALT/复位或身份漂移即停止，不自行恢复。

本次补齐纯只读取证：GPIOB_MODER `0x40020400`、IDR `0x40020410`、AFRH `0x40020424`；RCC_AHB1ENR `0x40023830`、APB1ENR `0x40023840`；NVIC_ISER1 `0xE000E104`、ISPR1 `0xE000E204`、IABR1 `0xE000E304`；USART3_SR `0x40004800`及已验证ELF运行时基`0x2001170C`。不读UART_DR、不清零计数、不写NVIC或GPIO。查询前后保存SR/路由/时基，可区分软件缓存为空与RXNE/中断待处理；不能仅凭缓存0认定ESP物理无输出。

先核对C私有UID/保护、正常Flash运行、DISARMED及完整Flash/options与原件一致；仍为42552B，完整Flash SHA `acb33fdd39ecb016ecd848ec25eee051635f56ef8138b577a8590d2734ad687e`，options SHA `52d5979da03bd7be45e385920ec7d5901793bab3f6bc1daa0c1c1997f9e91687`。MEM-AP沿用已连接流程，不重新Configure。结束核对完整Flash/options不变、DISARMED及正常Flash退出；纯协议失败仅验证原件与最后状态，不再查询，原生错误/ROM直接Close。

原始照片、UID、Flash、RX原码及API回执仅存受限EFS；Git只保存SHA、固定状态/版本和退出码。工具/照片/卡SHA及定向验证见[B5-ESP-GMR-R4-PREP](../evidence/B5-ESP-GMR-R4-PREP/bindings.json)。AT/GMR结果不自动批准上云或重开G3；BIO_V2、B部署、CAN接线及正式云环境均不改。
