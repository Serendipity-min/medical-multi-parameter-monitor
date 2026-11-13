# AUTH-B5-G3R5-P0B-UDP-001 R1｜独立公网新鲜样本草案

DRAFT_NOT_EXECUTABLE：P0-A尚未实测，不产生有效私有授权/.used，也未冻结目标IP或实施新执行器。P0-A成功不自动批准本卡。独立批准后才可一次同路径ESP公网UDP123请求。

前置：P0-A第一级时间PASS、SNTP正常关闭、新鲜源端DNS原文；从默认列表固定一个具有合法可解析global IPv4的既有服务器，只选一个主机/一个IP/目的123，精确原文/nonce/请求48B/实际本地端口/源码/180秒监督/现场附件绑定。若不能冻结则停止，不依次试公共服务器。新scope不能复用已消费的UDP或LAN卡。

保留C最小Flash运行/VTOR/DHCSR/DISARMED门禁，不重复UID/整片Flash/options/旧固件哈希；当前SSID/信道必须是已批准的正确2.4GHz，手工时钟写入0、B5START0。主动接收路径与正式G3被动接收区别明确保留。

预定一次建连并读回完整peer/local tuple，得到CIPSEND=48提示后仅一个带新8B nonce的48B请求；连续记录主动+IPD和有限接收窗、原始回复与关闭时序。合法48B、originate、mode4、VN3/4、LI非3、stratum1..15、服务器收发时序及minimum_epoch必须通过。SDK观察不是精确线缆RTT；若只能取得含SDK开销的时延上界，应明确它与正式G3的1000ms实现差异，不能事后放宽或据LAN TEST包通过。

失败不重发、不换服务器、不设置时间；健康路径一次CIPCLOSE并status确认无socket；native错误/ROM/HALT则停止留证，不能用复位或重刷掩盖。原件入EFS。此草案须在P0-A通过后补齐实际IP、请求/工具/卡快照与监督器离线检查，再由PI明确批准；当前不可执行。
