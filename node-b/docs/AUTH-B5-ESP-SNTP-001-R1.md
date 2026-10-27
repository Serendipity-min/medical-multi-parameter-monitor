# AUTH-B5-ESP-SNTP-001 R1｜启用返回、配置读回及时间变化

绑定负责人本次“继续下一步，启用命令返回→配置读回→时间变化，然后继续上次失败进度”的新许可。C/J-Link/J5现状沿用，B断电、C USB断开、ESP在板；不复位、不烧录、不改线，ROM/HALT/SDK错误或短读即停，不自动恢复。

一次180秒会话：核对C UID、完整Flash/options、保护、Flash运行及DISARMED后，仅通过USART3_DR发送一次固定计划：SYSSTORE=0及查询确认；CWMODE=1；用同一冻结sector3的测试Wi-Fi参数CWJAP一次（最多30秒）；SLEEP=0；CIPSNTPCFG=1,0一次；CIPSNTPCFG?一次；在配置读回后0/5/15/30秒各SYSTIMESTAMP?一次。Wi-Fi命令/确切字节计划只存在EFS，以完整命令SHA及总字节绑定；禁止任意UART命令、设时间、改NTP服务器、SYSSTORE=1、ESP升级、MQTT/B5START及任何Flash/sector3写入。

SYSSTORE设置/读回不为0或Wi-Fi失败即停止，不继续启用SNTP；启用返回ERROR须保留，后续固定只读观察仍可完成。不重试设置、不自动改服务器。所有原始回复、路由/时基、SDK返回、前后完整Flash/options存EFS。结束验证固件/options未变、DISARMED及Flash正常运行后正常关闭。

正常时间观察结束后仅发送一次CIPSNTPCFG=0并查询确认关闭，不让诊断结束后继续SNTP请求；该两条也计入固定字节计划。关闭未确认或中途原生失败，不再发送命令，由负责人切断C J5及J-Link电脑USB；主机退出不能证明模块网络停止。Wi-Fi连接不写Flash，G3启用仍由候选自己的有界流程执行。

诊断仅把启用OK、配置enabled=1、至少两次有效时间推进且与主机UTC粗差≤5秒记为“时间观测通过”；不替代G3的新鲜UDP SNTP/nonce/RTT和严格TLS检查。G3仍为新的独立一次300秒评价/420秒硬停窗口，不能复用失败许可或跳过现场准备。没有修改正式云服务权限。
