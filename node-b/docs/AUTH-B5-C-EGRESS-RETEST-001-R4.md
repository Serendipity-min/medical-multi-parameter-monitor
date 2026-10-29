# C实时波形FIFO与真实共同会话复测 R4

## 已有实证与修正

R3实板：C丢弃/传输故障0、完整Broker原码映射无错、HR/RR/TEMP各300条，STOP在420.078秒收到；但33个ECG批次被同流“只留最新”转为REPLAY，其中29个在评价窗，被WSS正确排除。实际B会话始终一致，旧共同就绪门却把新Gateway与上一轮旧B快照配对。R3原始T0及NOT_PASS收据全部保留，不追补成功。

仅新增：B5的Node-B ECG/RESP在原16槽实时队列中FIFO排队，不扩大RAM；真实断链/过载仍使用原历史和REPLAY策略。主机共同就绪须四路B流同一当前Gateway命名空间，ECG/HR有效且来源MOCK；不修改Backend/Hub或原验收阈值。R2的5ms服务、字节等价编码及STOP修正保留。

## 冻结对象

- C BIN 42880B，SHA256 `696a9342fd5be87892682a5a75a295828c12fef3fb385054e8c1fc1b117c9e20`。
- ELF `10ed3a45c10ea9d3d3e088a8123948eca3ad52f19a46ec579d5fa2d0889b18e6`。
- 当前实测完整Flash `1b56bc00b84714c326fe8d75162ee873a7caa7a07c24fa35b30b7e69601c6ea0`。
- 新应用完整Flash离线预期 `45274e8ab217777986f666c0a386926d532c5fde2199d86ccd7ffaaed202fc9c`。
- 包manifest `523d4cbb281908983dd58730a03e7ed83e9459d96ea714e23a662563eb541815`。原件、私有身份、配置、完整Flash/options只存受限EFS。
- 当前/新状态字节按各自冻结符号表，从`0x2000191A`起。工具/DLL/包/现场/所有一次性scope分别SHA绑定，未批准模板禁用。

## 批量授权范围（须负责人批准）

1. **C应用一次**：`B5_C_EGRESS_APP012_UPDATE`，一连接≤180秒；新鲜双全片/options、身份/保护、正常Flash及DISARMED匹配才Halt≤1，sector0/1/2共49152B下载≤1，双全片/options及完整尾部验证；正常Reset≤1且真实PC/MSP向量匹配才Go≤1；新应用正常且DISARMED，正常Close。ESP在板供电例外本事务明确批准。sector3/options/ESP固件不写。
2. **C预检一次**≤90秒，显式Reset/Halt/Go/写入0；通过后冷态回接B。B只读联合连接一次；没有B Reset/Halt/Go或下载权限。
3. **G3一次**：记录就绪后计划内C人工RESET≤1，新DISARMED启动行和完成回报后B5START≤1。未START的人工准备原120秒＋单独180秒，合计最多300秒，准备退出监督余量30秒；健康CPU只读复核/关闭余量10秒。沿用R3经过验证的有界退出，不把主机预算拒绝当作DLL读取失败。
4. 原60秒共同就绪、30秒复位回报、45秒预热＋300秒评价＋15秒尾段、420秒硬停、419–422秒STOP及20秒被动观察完全保留；所有旧数量/连续性/原码映射/五层实收/HR有效与RR/TEMP INVALID、MOCK/synthetic判据不变。测试云先只读确认≥805秒预算，不部署、不改ACL/正式服务/云配置。

冷态转C：关闭B/C J5，拔C USB及J-Link电脑USB，全暗10秒，整只JTAG从B转C；只恢复C J5及J-Link电脑USB，B断电、C USB断开。CAN/地/BOOT/ESP/源不动，不按RESET。C预检通过才提示一次冷态回接及原ECG60/1mV、RA–LA–RL确认。

ROM/HALT/未知、Fault、漂移、短读/native错误或硬限立即STOP_TARGET，不强设寄存器、不追加复位/Go/烧录/START，不自动重试。普通工具问题继续离线排查。异常断电由负责人沿用已知范围执行并回报。

## 恢复只准备，不自动执行

`B5_C_EGRESS_APP012_RESTORE`若另批，仅把R4 sector0/1/2恢复为本卡当前R2全片`1b56bc00…c6ea0`，gen5及保护区不变；一次≤180秒。回到R1、42552B、C24104或原H3及R-CFG/R-CLOUD都非本卡执行权限。离线恢复包不冒充实板恢复演练。B算法/原ECG与RR六窗/保护分支/Security Gate均不改。
