# AUTH-B5-G3R5-P0A-FINALIZE-001 R1｜补完已批准事务的DNS与停止

负责人在获知原窗口受主机6000次API预算中断、SNTP关闭未执行后，明确要求“修改工具上线，继续执行测试”。本卡只用于补完原事务剩余工作；不重新启用SNTP、不重跑15次观察、不手工发公网NTP包，不代批P0-B、配置、服务或G3。

一次新SDK会话/90秒硬限、零重试、零RESET/halt/go/固件/sector3/时间写入；沿用负责人确认未变的C/J-Link/ESP在板供电、正确2.4GHz网络以及免重复UID/镜像哈希条件。原始R1失败/源码/许可/.used保持不变；本次新scope、新工具绑定和独占.used，明确计为第二次会话。

先核实最小Flash运行、VTOR/DHCSR/Fault、DISARMED和既有串口路由；ROM/HALT/原生错误立即停止，不补Go或RESET。随后11槽固定序列：SYSSTORE?、CWJAP?、CIPSTATUS、CIPSNTPCFG?、SYSTIMESTAMP?、原卡未执行的三次默认主机DNS查询、CIPSNTPCFG=0、关闭读回、SYSTIMESTAMP?。只核对并保存原始网络/时间，不改变SSID/模式/DNS；口令/IP/MAC不回显。

SDK调用上限12000，每个普通命令之前保留3200次收尾余量，在主机读调用之前检查；若资源不足仅跳至预定关闭序列，不触发ReadMemEx的错误锁存后再抢救。清理命令仍受相同读写白名单/原生SDK上限/90秒外部监督，不扩大任何目标地址或UART字节权限。正常停止SNTP后读回确认0，最终Flash/DISARMED及正常SDK关闭；完整Flash/options/已有SHA复核仍0。

如果发现ROM/HALT或原生错误，本卡不允许继续UART写；若SNTP停止不能确认，应由负责人按已批准异常停止步骤关闭C J5并拔J-Link电脑端USB（B保持断电、C USB仍断开），不把主机退出当作ESP停网。原窗30.235秒中止后到本次停止前的模块后台流量未完整测量，不能补签原180秒内已经关闭。

14项新工具定向检查通过；不重跑旧矩阵。私有授权和现场例外取自负责人最新继续指令，仅EFS，原始返回码独立保留。
