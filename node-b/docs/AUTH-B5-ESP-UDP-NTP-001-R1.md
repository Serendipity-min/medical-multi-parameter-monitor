# AUTH-B5-ESP-UDP-NTP-001 R1｜单个ESP侧UDP/NTP包

负责人已明确批准单包取证，并确认模块未变、不重复识别开发板或哈希。本次沿用J-Link在C、C J5、B断电、C USB断开；不读取UID、Flash数据或options，不做全片哈希。仅保留当前运行态/Flash控制器只读状态、DISARMED及串口/接收路由检查；MEM-AP只用控制寄存器交叉核对，不重读芯片ID或Flash向量。

一次180秒会话，固定目标取既有ESP DNS第二个原始回复；仅一个48B NTPv4请求，transmit内含本次UTC与随机fraction，禁止重发。先查询SNTP关闭、CIPMUX=0、接收模式、CIPDINFO=0及无既存socket/Wi-Fi已连接，再UDP连接该既有IP:123，CIPSEND=48获得提示后仅发送一次48B。兼收主动+IPD与一次CIPRECVDATA=48（主动模式ERROR照录），不改变接收模式/网络配置；随后CIPCLOSE一次并CIPSTATUS核验无socket。

接收观察最多2秒，SDK串口/读取延迟不是精确线缆RTT。按长度提取原始二进制并校验48B、originate nonce、LI、version、mode、stratum及服务器时间；不设置模块时钟、不冒充G3新鲜授时/1秒RTT/TLS通过。原始包、原始AT流、时间点和API返回只存受限EFS；公开安全摘要及执行来源。工具/固定字节计划独立绑定，不让“跳过重复板卡核验”扩大UART/Flash权限。

ROM/HALT/SDK错误/短读/不符前置立即停，不复位、Go或烧录。异常未确认socket关闭时提示负责人关闭C J5及拔J-Link电脑端USB，不把主机退出当UDP关闭。执行后当前运行状态和DISARMED只读收尾；没有整片复核就不签新的Flash不变实测结论。不发B5START、不改算法或正式云环境。
