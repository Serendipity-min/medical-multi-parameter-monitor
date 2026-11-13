# R4 TIME启动端点修正：一次综合增补申请

状态：离线冻结、所有新事务默认禁用，等待负责人一次批准。不是已消费I-D/E-D的自动重试。

## 真实前态与唯一候选

实装B40928/C49048，gen5不变。C49048安装、独立只读均PASS；E-D已消费START一次，15次时间查询/28005ms/末次epoch122，TIME拒绝，未进入新鲜NTP、TLS、MQTT或300秒评价。TEMP/RR未运行。最近停止后物理断电未获确认，不能引用安装前的全暗事实。

新C49068B仅修复SNTP启动选择/读回/轮换，补有界数字诊断；原FIFO、单在途QoS1、严格PUBACK及诊断调度保留。为守住48KiB应用区，ARM断言保留条件、文件/函数/行号和同一fatal停机路径，仅去掉现有handler本就未使用的表达式文本，不关闭断言、不改vendor coreMQTT源码。

- BIN：`b663e82b16c16d1d252ca38e0ceec5b172495a30f893e50c370e200a4777dead`。
- ELF：`f6dbbb9a93327752ecdb844fd547812ca02f9be8cf630966871b0a5bbfb72b38`。
- 必须匹配的实装before全片：`81b1808f9936b02f115cef99a47059417eec99eb80dff4ca4cf1f103392588d7`。
- **预期，尚未实测**after全片：`75db57c038c021b40f36fa1ee627f410d26061e18e0f59a8465c73af0216bc25`。
- 源码、工具、安装/回退包及资源绑定见`node-b/evidence/B5-C-REPAIR-R4/TIME-BOOTSTRAP-R2/`。完整Flash/options、UID、配置和原始回执仅保存在受限EFS。

SNTP每次network_open仅使用启动读回的至多3个已有端点，不新加地址：显式停用≤3、选择并读回、最多15次UTC查询，原30秒准备预算内；每次选择均携带完整原端点列表、只轮换优先次序，并逐项读回一致；成功后保留该次序（启用合计≤3），不再额外启用SNTP恢复默认列表。记录query/primary/parsed/epoch/tried，不打印服务器地址。无可信UTC仍失败；随后原48B nonce匹配、1000ms新鲜NTP、TLS证书门继续独立执行。

方案A的一致性判据在采前冻结：设ESP秒级回复为e，查询起止tq0/tq1，新鲜包所对应接收时刻tr，q=tq1-tq0≤2000ms，rtt≤1000ms，u=floor(rtt/2)+1ms。粗时间下沿L=1000e+uint32(tr-tq1)，仅在新鲜UTC样本S满足`L-u ≤ S ≤ L+1000+q+u`时继续。实际使用测得q和rtt，上侧最大3501ms、下侧最大501ms，不临场调宽。量化区间不是对NTP真实性的密码学证明。两份时间分别保留，不用C主动NTP结果写ESP，不发SYSTIMESTAMP设置命令。

成功新增TIME_MATCH的实际差值/查询耗时；差值不符以SNTP_REJECT reason=10拒绝TLS。ESP系统时间高于下界但过旧/超前的负例必须失败。当前模块的TLS证书日期检查构建选项UNKNOWN，保留原CA/CN/SNI/TLS校验，但不以CA配置OK或AT版本号声称已验证该选项。保留候选原有最多2次启动前安全NTP零回复轮换，不增加START。配置读回错、AT错误、预算不足、坏nonce、迟包均不能进入TLS。

## 一次批准、分开消费的对象

| 对象 | 次数、时限及前置条件 |
| --- | --- |
| I-TB | C sector0/1/2安装一次≤180秒；新鲜双1MiB Flash/双16B options、私有UID/F407/保护、正常Flash运行和DISARMED、精确before全部通过才写。正常Halt/Reset/Go各≤1；写后双全片/options、精确after和应用区外所有字节核验。sector3/7/11/options不写，B不写。 |
| I-TB-RO | 安装后独立C只读一次≤90秒；reset/halt/go/写均0。正常Flash运行、DISARMED和精确after通过。 |
| L-TB | 原独立测试环境只读及TLS/CONNECT/SUBACK/Backend/WSS就绪；只在原两个unit按原RuntimeMax到期、配置SHA/PID/权限/端口及正式状态符合时各start≤1，总限300秒。每窗≥625秒可用，另留既有准备余量；不改ACL、不HUP/重启正式Broker、不改正式服务，不开8884。 |
| E-TB `B5_FINAL_ECG60_R4TB` | B只读≤1，C人工RESET≤1，START≤1；普通ECG60/1mV、RA–LA–RL，45秒预热＋300秒评价＋15秒尾段，原420秒业务硬停。 |
| T-TB `B5_FINAL_TEMP_OBJECT_R4TB` | B只读≤1，C人工RESET≤1，START≤1；GY-641V3固定非人体物表，无温标参考，不宣称温度准确率。其余时限同E。 |
| R-TB `B5_FINAL_RR15_R4TB` | B只读≤1，C人工RESET≤1，START≤1；按原冷态方法RA–LL–RL、独立RR15/1.5R/周期30/窒息0。其余时限同E。 |

三窗同一候选、独立token/session/目录，记录B/C/Broker/Backend/WSS原件、真实退出、STOP和末尾落盘。HR58–62/RR14–16及各自真实INVALID、MOCK/synthetic、A OFFLINE、温度2500ms源龄、ECG≥74250点/RR≥14850点/有效标量≥295/WSS≥2900、C主诊断≥58/间隔≤8秒/队列证据≥58、2ms映射、2048B和5000ms PUBACK均不变。原60秒就绪、300秒人工准备/30秒复位确认及有界Close不变。不得用其他候选旧窗口补计本窗通过。

## 一次现场准备和后续操作

批准确定字节包及ESP在板供电非隔离例外后：关B/C J5，拔C USB及J-Link电脑USB，确认板/ADS/两屏/ESP全暗10秒；整只JTAG从B转C，只恢复C原J5和J-Link电脑USB。B断电、C USB_UART断开，不按RESET，CAN/独立GND/BOOT/ESP/温度/源及导联不动。方向不确定就停。负责人回报完成事实后才执行I-TB。

I/RO/L通过后一次提示原冷态回接B、C USB_UART/实际COM及B J5；记录就绪才提示每窗唯一C RESET，以随后新DISARMED行确认START，不等待聊天写盘。T前只确认物表与非人体；R前一次提示冷态切源和黄L由LA移LL/F，红R→RA、绿F→RL/N不变，禁止LL/RL短接、RLD接地。ESP自主联网状态仍UNKNOWN，不能填已隔离。

ROM/HALT/Fault、身份/Flash漂移、原生SDK错误、TLS/正式服务异常、电气异常、AT边界未知或420秒失控即STOP_TARGET；失败不重发、不追加复位/Go/重擦/自动恢复。继续安全离线研究。会话关闭后按预批结束步骤关B/C J5、拔C USB/J-Link电脑USB并由负责人确认全暗，主机Close不替代物理断电。

## 精确回退和交付

仅备妥新候选→实装C49048的精确sector0/1/2恢复包，离线逐字节重组核验，默认禁用，独立批准才执行。部分写入/未知状态不得自动套用成功after恢复；不回H3、不写sector3、不恢复正式联网。

PI R4第7节要求新增字节及已消费后的START集中增补，故本卡需一次新的对象批准；通过后正常门禁连续执行，不逐个普通错误重新申请。唯一交接仍为`B5-C-REPAIR-R4-FINAL-HANDOFF.md`。CPU ROM、独立冷启动、同窗ECG/RR、绝对阻抗/温度标定及CAN故障注入维持原状态。测试账号未撤销，unit到期不是环境清理完成。
