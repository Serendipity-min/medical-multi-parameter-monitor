# H2 CAN_ONLY_BENCH

只用于A/C非人体、完全离线验收。完整联网候选的main/platform、ESP/AT/TLS/MQTT库和配置读写实现均不参与链接。本目标不覆盖原候选输出。

```text
python gateway/physical_can/bench_build.py --host
python gateway/physical_can/bench_build.py
python gateway/physical_can/tests/test_flash_plan.py
```

输出在忽略的`build/bench/`，时间戳原始证据在`evidence/h2/`；失败不覆盖。C链接硬限制前64KiB，实际镜像的受影响扇区、向量和load地址另作检查。24KiB堆/8KiB栈预算沿用原候选。

控制台仅USART1 PA9/PA10，115200 8N1。C板USB232/CH340C对应此接口，P6切换的USB_SLAVE数据是另一路。只初始化USART1与CAN1，默认控制器正常接收但不运行协议、不发送NMT。独立供电检查时不得发送S。

| 命令 | 行为 |
|---|---|
| S | 两板静态、电源及身份门禁通过后，首次启动真实Gateway栈并单次提交START |
| G | 无故障时显式重建Gateway协议/CAN，清除bench时间使能，再提交START |
| T | 已启动后显式开启固定测试epoch及0x100 TIME；所有诊断均标为BENCH_TEST_TIME_UNTRUSTED，不是SNTP时间 |

其他字节不提供网络或配置功能。无时间/无传感器不填入示例值；Node-B没有本地协议实例/生产者。真实TSR.TXOK后才计NMT成功；Host策略注入单列为模拟。Bus-off、发送锁止、意外B帧或禁用281触发锁止；命令不能解除故障停止门禁。

每秒诊断包括PCLK1/BTR、TEC/REC/LEC/BOFF、实际TXOK计数、701 Boot-up/OP心跳、181/381/481/681等帧的计数/首末时刻/周期范围/最后8字节、RPDO镜像、质量/代际/新鲜度、Adapter/Router本地产物身份/有效性/来源及丢弃/调度积压计数。原始未授时镜像不等于有效监护数据。USART输出采用有界队列，溢出单列，不阻塞CAN；不能把诊断缺帧当作总线零丢帧。

## 下载与恢复门禁

先核对身份并只读备份A完整Flash两次，保护本地原件，且两个摘要必须一致。A应用使用同源Keil镜像，禁止调用工程默认整片下载设置。C按用户指令不做Flash整片备份；只核对sector7（0x08060000）和既有配置宏指向sector11（0x080E0000）的整扇区及前312B摘要，不保存正文。

`flash_c.py`是C/COM15专用受限入口，只有正确的已提交源、ARM镜像SHA、A已验证备份、外部身份源及现场C角色核对全部通过才可进入下载。只调用非空明确的Extended Erase扇区列表（最多0..3），不使用None/空列表、mass erase或RDP解锁；回读应用、保护区及选项寄存器。CLI只在当前H2现场角色门禁通过后调用，不能用它绕过批准步骤。

既有`ai_serial_console/tools/flash.py`使用固定的其他镜像和未限定扇区的erase，本轮不调用、不修改该工程，也不调用MCP固定擦除烧录工具。旧脚本的UID字面量只由外部身份源在内存读取，不能复制入库。

若下载失败或校验不符立即停止，不自动复位运行或重刷。A恢复使用受限目录内同一设备的备份，先核对身份/只恢复本轮改动扇区；C的原配置须全程保持摘要一致，后续恢复应用也仅用已核验本地旧镜像及明确应用扇区，不能用整片擦除。任何实际恢复必须记录，不宣称从未执行的回滚已成功。

## 串口实测记录

`python gateway/physical_can/bench/capture_uart.py --seconds 420`只开启COM15观测，默认不提交命令。现场需要按复位键时使用`--await-boot`：旧故障行仍被保存，但必须看见新的`CAN_ONLY_BENCH`启动标记才能通过命令门禁。本机DTR复位尝试没有观察到新启动，不把串口电平设置等同于实板复位成功。

运行期间，`build/bench/uart-status.json`给出脱敏状态。明确追加单行`S`或`T`到`build/bench/uart-control.txt`才会提交相应命令；超过3秒的旧状态、故障或Bus-off拒绝提交，T还要求真实NMT TXOK及A在线。STOP仅关闭Host记录，**不会切断板卡电源或停止已经运行的固件**。无自动重启、自动故障恢复或网络控制接口。

原始UART字节仅保存于预先建立的受限本地目录；版本库中的记录移除181/381样值和MIRROR测量值，保留标识、计数、采集tick和质量。程序公开的valid是源/通信有效性标记，不能作为人体连接安全或生理准确度认证。真实来源、模拟来源和未核实来源必须在交接记录中分别说明。

`python gateway/physical_can/tests/test_capture_uart.py`只验证Host命令门禁与脱敏，不打开串口。被动CAN初始化时`armed=0`，A/B协议在线位尚未建立，不能仅凭此时的`A=0`判定物理收不到A；应同时检查RX计数。

## H2R独立接收候选

`bench_build.py --h2r [--host]`生成`build/h2r/`和`evidence/h2r/`，保留H2已受测BIN及原始失败。只在该目标替换为`bxcan_irq.c`和`rx_irq.c`；原完整物理候选/内部回环不切换驱动。CAN1_RX0强中断向量与实际向量表槽位一并检查。

IRQ只按W1C语义释放三深度硬件FIFO，发布128项静态SPSC队列，使用32位无锁release/acquire原子保证完整帧可见。标准帧的IRQ接收时刻随帧入队，主循环处理协议时保留该时间，不扩展1500ms新鲜度。IDE/RTR/非法DLC、硬件FOVR、软件满队列分别计数并锁止；重初始化只清待处理项并记录数量，不清累计故障。FULL/FOVR是锁存事件计数，不等同准确丢帧总数。

RXQ记录硬件FOVR、软件队列溢出/深度/高水位、FIFO FULL、重初始化和故障后丢弃；MODEL记录Router丢弃、设备UART未入队字节；TIMING记录DWT周期数（HSI名义16MHz）、前台服务间隔、诊断报告耗时、IRQ及出队滞后。硬件路径服务函数还会在显式重初始化前调用一次以保存残留状态，`irq_calls`因此是FIFO服务调用数。所有时间测量都有仪表和时基边界，不把软件IRQ时间当作线上的精确到帧时间。

每份诊断带BEGIN/END、递增报告序号和逐行标号。Host记录完整报告数、缺报告、缺行及重复行，与UART/hardware/Router计数分开。Host可观测缺行可能来自设备UART或Host通路，不据一个计数推断故障位置；附着/停止边界半份报告单独标注。

`capture_uart.py --h2r --seconds 360`默认只监听，控制文件在`build/h2r/`。S启动协议；T显式本地非可信授时；P在A断电前显式停止C协议发送并撤销旧有效模型，C控制器和RX队列继续捕获Boot-up；G只在无故障的P暂停状态由Host明确提交恢复协议，重新T前保持TIME_BLOCKED。P/G不重启C、不清接收/模型累计计数，不以C重置掩盖A失败。D在1Hz/2Hz之间改变C诊断负载，A的TPDO频率、采集算法和有效窗均不变。

H2R C下载必须显式`--h2r`并提供原H2应用文件/摘要和已验证sector7/11基线；旧应用不匹配、保护区已有变化或IRQ目标不符，均在擦写前停止。只读比较旧应用不等于保存C整片备份；C原整片恢复仍未经验证。A正常冷启动不能用SetPC/MSP/VTOR人工启动代替。

`observe_window.py --number 1 [--attempt 2]`只读取既有脱敏状态，持续312秒并保存快照；第二窗先显式D切换C为500ms诊断，再用`--number 2`。不打开串口、不提交硬件命令、不清计数，旧尝试存在时拒绝覆盖。中途P维护暂停会使本次观测退出1，须保留退出码并注明操作原因，不能改写为CAN硬件故障或重跑覆盖为成功。

`analyze_window.py --number 1 [--attempt 2]`从对应快照及公开UART日志重新提取起止内完整报告，要求连续至少300秒并交叉检查四类丢失。报告中的每类帧只保留最近时间，窗口内相邻报告的最近时间增量不等于每帧间隔；累计dt_max包含冷断电，不重置以求好看的数字。中途新增流单列统计，真实来源仍须由现场记录核实，不能从synthetic位或数值外观判断是否接入人体。
