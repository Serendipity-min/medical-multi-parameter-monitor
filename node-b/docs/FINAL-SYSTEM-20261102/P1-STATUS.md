# FINAL-P1：STOP候选与并发风险处置

状态：OFFLINE_STOP_FIX_PASS / C_ONLY_STOP_NATIVE_PASS / CONCURRENCY_NOT_RUN。全部三板已完成身份、双份1MiB及Options核验，当前先做C单板，MIC隔离、CAN断开，不更改A/B应用。

旧证据为STOP已发送且ACK=1、IDLE=0、stop_failed=1。厂家V0.21支持0x21状态查询；旧代码停止后只等待自动4F，没有查询。该缺口是修复候选，不能据此宣称已证明旧真机失败的唯一原因。[厂家协议页](https://www.haohaodada.com/new/bbs/forum.php?extra=&mod=viewthread&tid=2621)直接打开403，本次搜索索引返回的厂家正文可核对命令及状态表；查询长度沿用已审计的FD 00 01 21，真实模块仍待抓包。

最小改动：STOP物理TX完成后接收ACK，只追加一帧状态查询；只在查询物理TX完成后认领4F。共用原1500ms总预算，不重复STOP、不重发文本、不自动重试。STOP失败禁止重新enable，保留显式错误。Host定向8场景退出0，原语音3351条断言退出0；真实接口/Flash规划相关44项退出0。初始反例原生退出3，首次补丁的重新enable负例退出3均保留。MinGW格式编译失败1通过ANSI STDIO编译开关解决；另有控制脚本语法错误1，未触及设备。

独立台架复用原SPL/GNU构建器、USART2队列与安装引擎，不链接MIC、CAN、ESP/MQTT；USART1输出TTS实际TX/RX逐字节及单调时间、停止各状态。显式V设低音量1，P发固定非人体测试句，S停止，Q状态，I身份；不开机自动播放。7164B，仅sector0，扇区尾部取本次C备份，其他Flash及Options不变。安装前独立实读完整Flash并比对今日备份；核验不通过不执行下载。结束恢复C44520原应用并完整读回，恢复范围sector0–2；不动sector3或其余区域。计划及SHA见P1-STOP-CANDIDATE.json。

安装适配器原来强制三个应用扇区，小C镜像离线计划退出1；现仅为C允许从sector0开始所需的1/2个应用扇区，实际SDK写入字节数随计划收紧，仍不允许sector3。合成测试覆盖7164/20000/44520B，非影响扇区及镜像尾部保持原件。

SDK隐式副作用仍UNRESOLVED。拟采用受控替代：安装/恢复只在单板隔离状态；有效运行观察前正常断电、物理断开J-Link并冷启动，运行入口只用UART，不创建SDK对象。此方案不是SDK原生无害证明，尚不能签发三板并发通过。

C合体资源仍NOT_READY：64KiB PCM拟放CCM、DMA留普通SRAM；CAN须高于MIC IRQ，统一SysTick/UART/网络owner，保留有界轮询。仅C独立STOP台架不触碰这些尚未完成的资源整合，不修改既有算法或云端结果。MIC PCB/外部去耦/下拉仍UNKNOWN，模块维持拆下，不能开展麦克风并发供电。

## 本次原生首轮失败与R2

R1安装退出0，完整读回正确，仅sector0改变。负责人正常断电、拆除J-Link后冷启动，经COM18仅UART测试。首轮原生退出1：低音量设置返回41，但逐字节USART1日志消耗数ms，主循环在物理发送完成后尚未补记tx_done就消费该ACK，进入错误；随后的自动STOP也收到41，却在stop_sent补记前被忽略，最终1500ms超时。仅发I/V，没有人工发起P/S。见P1-C-STOP-R1-FAIL.json及原始UART文本，失败不覆盖。

R2只修台架日志顺序：输出TX日志后，若当前帧已全部提交，先再执行一次有界轮询补记物理TC，再消费RX；该额外检查不会多发下一字节。不修改原TTS队列判据，不降低ACK/IDLE要求。R2为7180B，构建退出0；计划仍sector0。使用既有MIC安装薄入口，复用R1真实完整读回+入口独立实读，避免再做两遍无关备份。首次离线计划因BIN未位于EFS返回1，移入EFS后计划0；并未因此打开SDK。

新stop_field.py复用既有pySerial低控制线方式，不加载SDK，不联网，不发送B5START。保存C实际TX/RX及时间、Host命令、原生退出；必须满足STOP四字节→ACK→查询四字节→4F及最终禁用/空闲、UART零错误。6项校验器Host测试及3个子测试通过。播放模式首先证明文本ACK接受，不把此状态冒称已收到4E或人工可闻。

## R2现场结果与恢复

R2安装退出0，完整读回/Options/sector0外一致。负责人决定保留J-Link线与USB_UART，串口COM18。三次UART运行期间SDK打开数为0，但J-Link实际连接、独立冷启动未获确认，不能把本轮记作调试器物理隔离或SDK无副作用证明。

空闲STOP、两次短句ACK后STOP均退出0；每轮有且仅有一次FD 00 01 02、41、一次FD 00 01 21、4F，最终disabled且stop_failed=0，UART错误/溢出0。负责人确认听到短句开头后停止。停止前模块未返回4E，仅文本ACK接受+人工可闻，不伪造播放状态。7项当前Host校验器测试及3个子测试通过；初版6项结果亦保留。网络中断时STOP尚未验证，不能签发完整并发准入。

随后通过既有安装薄入口恢复C44520，sector0–2，恢复退出0；完整1MiB SHA为423a805860e2300a03de87471ba69ac9ec439a74b19dd76f561b7dce16d7fcdf，与本次测试前完全一致，Options/其他区未变。负责人确认全部断电熄灭，CAN不接、MIC仍拆下、J-Link板端可留C。A/B程序未改、云端正式服务未改。

## 静态资源合体试链接

`build_arm.py --b5 --egress-final --tri --audio-link`仅是离线链接探针，保留完整录音/TTS API与强ISR，用于真实容量计算；原B5 main不调用音频API，无录音/语音上行现场命令，不允许作为并发固件安装。PCM64000B位于CCM，DMA2560B位于普通SRAM，SysTick/USART1沿用既有owner，音频IRQ静态优先级8低于CAN=3。不是活机优先级/调度实测。

最终源码构建退出0，BIN48936B，在sector0–2的48KiB内仅剩216B；普通SRAM含静态堆栈预留占112728B，余18216B，CCM余1536B。尚未加入音频MQTT上行/回复编排及现场控制，不能由链接成功推定后续仍可装入48KiB，也不能推定运行栈/队列/IRQ延迟通过。默认双CAN目标再次构建44520B且BIN/ELF与P0完全一致；独立语音共享队列构建29744B退出0，未安装。

下一步仍是FINAL-P1：完成真实音频上行与双CAN的单网络owner整合，解决剩余Flash裕量、SDK操作互斥/可观察替代、并发水位与故障降级；MIC硬件未知项核实前不接回/供电。R02仅本地停止证据已补齐，R03/R04/R12及整阶段准出未关闭。
