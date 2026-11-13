# AUTH-B5-ESP-TIME-DIAG-001 R1｜一次固定时间查询

负责人已确认B/C全部断电熄灭，并明确批准一次有界时间诊断。本事务单独绑定新授权，不复用G3或AT/GMR许可，不再申请相同批准。180秒硬限、单会话、无重试；先核验C私有UID、Flash运行、DISARMED、完整1MiB Flash/options及冻结42552B身份。ROM/HALT/原生错误/短读/身份漂移立即停，不复位或重刷。

现场仅冷态JTAG从B转C，保持CAN/地/BOOT/P5/ESP/源不变；全部熄灭等10秒后，只恢复C原J5与J-Link电脑端USB。B保持断电、C USB_UART断开，不按RESET。负责人回报完成后才开启工具。此步骤不签独立冷启动或ROM根因通过。

固定115200/8N1，仅依次发送一次`AT+CIPSNTPCFG?\r\n`与一次`AT+SYSTIMESTAMP?\r\n`，USART3_DR `0x40004804`总计最多34字节（16+18）。ERROR属于需要保存的诊断回复，可以继续下一条固定只读查询；无终止回复、串口错误、其他消费者或SDK异常立即停，不重发。禁止SNTP配置、设置时间、Wi-Fi配置、AT复位、B5START、Flash/options/sector3、RAM/GPIO/波特率及CPU状态写入。MEM-AP仅沿用已验证连接流程，目标写权限仅这34个固定UART字节。

查询前后记录GPIO/USART3/NVIC/时基，原始回复逐字节仅存受限EFS。结束复核完整Flash/options、DISARMED及Flash正常运行；只在新鲜健康状态下启用SDK退出续跑，不发Go。默认未授权模板禁用，工具/依赖/卡/ELF/私有参考与现场记录均冻结SHA。

断电后的SNTP配置及时间不能倒推上轮G3失败时的状态。本次采到回复不等于授时根因已关闭、TLS或云传输通过；不降低时间/证书门禁、不改BIO_V2算法，不操作正式云。
