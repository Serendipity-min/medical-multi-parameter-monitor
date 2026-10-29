# B5 C出口修正与300秒复测 R1

本卡绑定本轮新对象，不能复用此前42552B安装卡或已消费的START。保留所有旧失败原件；未取得现场完成事实和一次性EFS授权，不连接目标。普通工具问题可离线修复，工具SHA改变后重新冻结，不能重置现场次数。

## 软件冻结

- C BIN：42764B，SHA256 `61cbfd551b6111407c9c4fcf684febc6c4afa809e3039b05addb7df9687789ce`。
- ELF：`65d2181cc5be9d6a36f83ec361a99fc6780cba0c36d14517934cde36acb9bc55`；symbols：`39b19f702a5e13c14b525951b0468b29526bed56f28334f049d3565f655c6b55`。
- 旧42552B+gen5完整Flash：`a5239d616523621593b5e76fd70212aa199e72603b85e359492d642448fff528`。
- 新应用安装后的预期完整Flash：`533133d9e7b73b459b65126075e878a571e6b345d0fa58a152d609bc70605d06`；这是离线重建值，不是实际读回PASS。
- app012恢复包manifest：`50a35b8fc641f62ea95525598ff1df3501466c5471ba6ee6fd42dd72f73a4a2e`。完整原件/UID/配置仅存既有受限EFS。
- 新ABI的四个连续状态字节从`0x2000191A`开始，顺序为mqtt_connected/network_open/stopped/armed；旧ABI从`0x20001918`开始。仅冻结包对应的符号表可决定地址。
- 安装器`b5_c_app_update.py`及依赖SHA、地址白名单、DLL、现场附件、EFS包与收据均逐事务绑定。没有options/sector3/ESP固件写权限。

## 对象一：C应用安装

scope `B5_C_EGRESS_APP012_UPDATE`，一次连接、180秒硬限、失败不重试。负责人先冷态转接：关B/C J5，拔C USB和J-Link电脑USB，全暗10秒，JTAG从B转C；只恢复C J5和J-Link电脑USB，B断电、C USB断开。CAN/地/BOOT/ESP/源不变，禁止热插拔JTAG或人工RESET。ESP在板供电例外必须明确列入该事务，不能写成已隔离。

顺序：真实C身份/保护和正常Flash运行核验→双份完整1MiB及双options与包逐字节一致→旧ABI四字节全零DISARMED→Halt≤1→仅sector0/1/2的49152B下载一次→双份完整Flash/options、完整尾部及身份复核→正常器件Reset≤1→实际PC/MSP等于应用向量→Go≤1→正常运行及新ABI DISARMED→正常续跑Close。

不强设PC/MSP/VTOR；ROM/HALT、Fault、任何漂移、短读/native错误或超时立即STOP_TARGET，保存原件，不追加恢复。完整before/after每次分别双读，不以离线包替代新鲜实板读回。

## 对象二：新C只读及冷态回接

仅安装真实PASS后，新ABI C预检一次≤90秒，显式Reset/Halt/Go/写入均0。核验完整Flash/options、正常运行、DISARMED。随后负责人冷态转接回B，恢复C J5与USB_UART/USB232、B J5和J-Link电脑USB；回报实际COM、B屏刷新、源与隔离条件。不得接USB_SLAVE，不按B RESET。

## 对象三：测试云与G3一次

只读核验既有独立测试服务/TLS、Broker、ACL、正式服务与配置未变，至少625秒预算。仅两个已冻结独立unit因驻留到期而停止且所有条件匹配时，须本对象明确批准后各start≤1；不部署、不改ACL、不HUP/重启正式Broker、不改正式站点。

scope `B5_G3_ONE_ECG60_MOCK_CLOUD_WINDOW`，本次B连接≤1；计划内C人工RESET≤1，记录就绪时才提示；DISARMED启动行和负责人完成事实齐备后B5START≤1，失败不重发。原候选授时端点轮换最多两次仅限启动前观察，不放宽60秒共同就绪门、TLS、新鲜1秒授时门或其他停止条件。

保持原420秒业务硬停、45秒预热、300秒共同评价、15秒尾段及20秒被动停止观察。原数量/覆盖/有效率判据不变：ECG100点@250SPS、RESP50点@50SPS；HR58–62且稳态有效，RR/TEMP真实INVALID，A OFFLINE，非人体MOCK/synthetic；B原码→C→Broker→Backend→WSS逐层实收。原失败不能被新结果覆盖。

C在420秒前后必须按原419–422秒观察界限给出STOP。发布中达到硬限不产生新的网络失败计数；真实发布故障仍停止，不能以此豁免。新增B5 IO仅记录数字诊断，不修改MQTT语义或验收判据。

异常时不自动复位/Go/重刷；负责人按已批准停止范围断B/C J5、C USB、J-Link电脑USB。主机退出不证明ESP停止，物理断电未回报则如实记UNKNOWN。

## 对象四：恢复方案（独立批准，默认不执行）

scope `B5_C_EGRESS_APP012_RESTORE`，只将sector0/1/2恢复为本次保留的42552B+gen5原件，完整Flash必须精确返回`a5239d616523621593b5e76fd70212aa199e72603b85e359492d642448fff528`，options及sector3/7/11不变。每次恢复同样一次连接/180秒，正常向量检查及DISARMED；失败不自动重试。

恢复到C24104/H3、gen5配置回退、云资源撤销不是本应用恢复对象，不默认执行。离线恢复一致性不冒充实板恢复演练PASS。B算法/固件、正式云环境及保护分支均不改变。
