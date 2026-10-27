# AUTH-B5-ESP-NTP-DNS-001 R1｜现有NTP主机的有界DNS读取

SNTP设置及读回成功而30秒内仍无有效UTC，按负责人本轮继续排查并推进的许可补充只读DNS取证，不重复设置SNTP或重开云窗。一次180秒会话、单连接，沿用C J5/J-Link、B断电和C USB断开；不复位、不改线，不改算法/Flash/正式云。

三个查询目标只能逐字节取自上一SNTP原始CIPSNTPCFG读回（EFS原件SHA绑定）；仅按原序各一次`AT+CIPDOMAIN="<existing-server>"`，单条最多10秒。命令全字节、总数、总字节和目标SHA独立冻结。允许保存ERROR作为诊断，原生错误/短读/ROM/HALT则停，不重试；禁止CIPDNS设置、NTP服务器变更、Wi-Fi设置、时间设置、MQTT或B5START。

先核验C身份、完整Flash/options、保护、正常Flash运行及DISARMED，再查询；结束复核原件不变和正常Flash/DISARMED，主机会话关闭。DNS返回IP只说明解析成功，不等于UDP123或授时通过。原始主机/IP/回复只存受限EFS，Git仅计数、状态、SHA和真实退出码。
