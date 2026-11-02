# FINAL-P1：STOP候选与并发风险处置

状态：OFFLINE_STOP_FIX_PASS / NATIVE_STOP_NOT_RUN / CONCURRENCY_NOT_RUN。全部三板已完成身份、双份1MiB及Options核验，当前先做C单板，MIC隔离、CAN断开，不更改A/B应用。

旧证据为STOP已发送且ACK=1、IDLE=0、stop_failed=1。厂家V0.21支持0x21状态查询；旧代码停止后只等待自动4F，没有查询。该缺口是修复候选，不能据此宣称已证明旧真机失败的唯一原因。[厂家协议页](https://www.haohaodada.com/new/bbs/forum.php?extra=&mod=viewthread&tid=2621)直接打开403，本次搜索索引返回的厂家正文可核对命令及状态表；查询长度沿用已审计的FD 00 01 21，真实模块仍待抓包。

最小改动：STOP物理TX完成后接收ACK，只追加一帧状态查询；只在查询物理TX完成后认领4F。共用原1500ms总预算，不重复STOP、不重发文本、不自动重试。STOP失败禁止重新enable，保留显式错误。Host定向8场景退出0，原语音3351条断言退出0；真实接口/Flash规划相关44项退出0。初始反例原生退出3，首次补丁的重新enable负例退出3均保留。MinGW格式编译失败1通过ANSI STDIO编译开关解决；另有控制脚本语法错误1，未触及设备。

独立台架复用原SPL/GNU构建器、USART2队列与安装引擎，不链接MIC、CAN、ESP/MQTT；USART1输出TTS实际TX/RX逐字节及单调时间、停止各状态。显式V设低音量1，P发固定非人体测试句，S停止，Q状态，I身份；不开机自动播放。7164B，仅sector0，扇区尾部取本次C备份，其他Flash及Options不变。安装前独立实读完整Flash并比对今日备份；核验不通过不执行下载。结束恢复C44520原应用并完整读回，恢复范围sector0–2；不动sector3或其余区域。计划及SHA见P1-STOP-CANDIDATE.json。

安装适配器原来强制三个应用扇区，小C镜像离线计划退出1；现仅为C允许从sector0开始所需的1/2个应用扇区，实际SDK写入字节数随计划收紧，仍不允许sector3。合成测试覆盖7164/20000/44520B，非影响扇区及镜像尾部保持原件。

SDK隐式副作用仍UNRESOLVED。拟采用受控替代：安装/恢复只在单板隔离状态；有效运行观察前正常断电、物理断开J-Link并冷启动，运行入口只用UART，不创建SDK对象。此方案不是SDK原生无害证明，尚不能签发三板并发通过。

C合体资源仍NOT_READY：64KiB PCM拟放CCM、DMA留普通SRAM；CAN须高于MIC IRQ，统一SysTick/UART/网络owner，保留有界轮询。仅C独立STOP台架不触碰这些尚未完成的资源整合，不修改既有算法或云端结果。MIC PCB/外部去耦/下拉仍UNKNOWN，模块维持拆下，不能开展麦克风并发供电。
