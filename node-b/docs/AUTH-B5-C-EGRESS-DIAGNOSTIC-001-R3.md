# C出口终态补证与三路续测方案｜R3，待批、默认禁用

本卡不是已获得的安装/START许可。C46584实测在53.919秒发生完整854B发送后SEND OK未确认，UNSYNCED=1，物理断电尚未确认。根因未确定，R3仅补充失败取证和主机有界收尾，不能冒称已修复该实板故障。

## 字节资产

最后已读回C46584：BIN `d01d08c23de3fbdc6639609136cacc6c0da0eda1fc4489bad8273829a2200e7a`，全片 `707d88987431cb4cdf4580d8f627ba58eea4980429d95fc6dcde6ceb8718ca4a`，四状态0x20001DC2–0x20001DC5；B40928不变。

唯一待批诊断候选47120B：BIN `edd2bb8db2632993bf4fae5d577c1aa967e943884f2ebdc8b40d52710b08db88`，ELF `32909b34625f965c785fa59b8cf9b48d1ad14bcdcc1bb47660c07bad1463938b`；源码清单 `504b86effe2ea6d08fedc86c300b02d258e84ab97735cb4b306b05d3b6db27ba`。预期全片 `ffd814e16f6cc947fbf336c73abccfd3fcd7aa19e804dd1dbb54900a7c0e8a77`，包manifest `bde330d3b8d84d4b7c49ba73e6f135a684bd1833358cfe52097695e6b80565f3`，options保持 `52d5979da03bd7be45e385920ec7d5901793bab3f6bc1daa0c1c1997f9e91687`。镜像/配置/UID和恢复原件只存EFS。

## 独立对象及前置

1. **物理停机与冷态转C**：负责人先关B/C J5、拔C USB及J-Link电脑USB，全暗10秒；确认后才冷态转JTAG至C，只恢复C J5/J-Link电脑USB，B断电、C USB断开。当前不能将这些完成事实填true。ESP在板例外由本批明确确认；CAN/地/BOOT/温度/源均不动。ROM/HALT/漂移不自动复位或Go。
2. **应用安装**：`B5_C_EGRESS_APP012_UPDATE`新私有token、会话≤1、180秒，Halt/正常Reset/Go各≤1。开始必须新鲜双1MiB Flash/双16B options、真实UID/保护、正常Flash运行及DISARMED精确匹配46584。只写sector0/1/2，写后双全片/options及新符号状态验证，sector3/7/11等所有尾部不变。不把已有备份当今天实时读回。
3. **应用回退**：`B5_C_EGRESS_APP012_RESTORE`单独批准才启用，恢复全片应精确707d…ca4a；不自动回H3/C24104。更早C43036/46456资产继续保留。离线拼接通过不等于实物恢复演练。
4. **三个独立窗口**：`B5_FINAL_ECG60_R3`、`B5_FINAL_TEMP_OBJECT_R3`、`B5_FINAL_RR15_R3`，各token/目录/.used、START≤1/C计划RESET≤1/B只读≤1。C安装及独立只读PASS、实际现场事实、严格云就绪通过后，先ECG，满窗PASS且剩余对象已批准才逐窗进入TEMP/RR。一个失败不自动消耗下一窗。

## 保持不变的判据

沿用R2的ECG60/1mV/RA–LA–RL、非人体GY-641V3、RR15/1.5R/周期30/窒息0/RA–LL–RL源；B40928、算法、ADS寄存器、CAN、gen5不变。每窗准备300秒、≤60秒共同就绪、45秒预热＋300秒评价＋15秒尾段、420秒源业务硬停、20秒被动观察。新鲜NTP完整1000ms，启动前最多两次已知安全的既有端点轮换；粗TIME、部分包、错误nonce、UNSYNCED等仍停止。

ECG≥74250连续点/HR58–62 VALID≥295条、RR INVALID；RESP源≥14850点；TEMP有效≥295报告且真实UART/入口追踪2500ms及原2ms界；RR14–16 VALID≥295条且无QRS时HR INVALID。五层同session/boot/seq/UTC/值、MOCK/synthetic、Backend接受=去重Broker/拒收丢弃0、WSS≥2900，无新增覆盖/过期/REPLAY替代/错误STALE/txfail/mqtt_fail。QoS0/严格QoS1 PUBACK5000ms、2048B、CA/SNI不改；源STOP420000ms/reason1/CLOSED7/unsynced0/pending0和原主机观察门均需证据。

## 这次新增证据及分支裁定

- C只在失败时输出数字诊断：等待结束原因、回复字节数、CLOSED/ready/busy观察标志、实际发送预算/耗时/完整写数，以及QoS/stream/seq/pending age。标志只用于归因，不改变协议边界；不输出SSID/凭据/原始敏感载荷，不补发原包。
- 已明确ERROR/SEND FAIL的命令边界与“完整写完但超时/关闭/重启提示”分别记录；未知仍UNSYNCED且不盲发CIPCLOSE。
- PC健康查询改为单次总时限，WSS关闭≤1秒/SSH等待有界；保留清理开始和完成回执、最后队列及原生断开码。原主机/设备总限不扩大；不能将进程退出当C/ESP停机。
- 若失败seq在Broker/Backend实际原件可找到，重点区分ESP终态确认/解析与观察器缺口；若找不到，结合数字URC、UART/CAN错误及严格只读网络证据判断模块/TCP/链路。当前未证明的分支不先命名根因。

真实云仅现有测试GW-B5-001，正式GW-C-001/ACL/Backend/Nginx不改。测试服务如到期，独立G1-RESUME对象另批；不自动启动或撤销账户。当前没有新的B5START、烧录、sector3写入或恢复许可。未确认本次物理全暗前，不执行新目标操作。
