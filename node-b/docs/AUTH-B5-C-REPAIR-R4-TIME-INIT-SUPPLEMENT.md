# C冷启动SNTP初始化增补：应用安装与单次ECG60窗口

状态：候选已冻结，以下新对象默认禁用，等待负责人一次批准；不复用已消费的C49068安装或E-TB START。

## 精确字节与改动

实装B40928/C49068，gen5不变。C49068已实测双全片/options、独立只读、DISARMED通过；其ECG窗在TIME停止，queries=0、tried=0，尚未进入TLS、MQTT或300秒评价。负责人已确认全部断电熄灭。

- 新C49132B BIN：`72131dbb5ef6bc0e0d33e328925c685403bae928aea9447a81f8291c6ae5c1ab`。
- ELF：`10051aa990cff78882d94870ad99509011f140439d01e76aa0e47f2bcfc44b0b`。
- 必须匹配before全片：`75db57c038c021b40f36fa1ee627f410d26061e18e0f59a8465c73af0216bc25`。
- **预期，尚未安装**after全片：`9bba23b436f079183296fa98dcaeed047eb919ba8597d75a85bc144bc48417fd`。

只修复明确的`+CIPSNTPCFG:0`冷启动回复：易失启用一次并重新读回列表，随后仍显式选择、完整列表读回和安全轮换。此路径最多额外一次启用及一次配置查询，启用合计≤4、显式停用≤3；共享15次时间查询、30秒SNTP准备和60秒共同就绪预算不变。不是对任意错误的重试，不接受空/错误的启用后配置，不添加端点，不设置人工UTC，不写ESP或sector3。

方案A的两类校验、既有时间一致性区间、1000ms新鲜NTP、TLS CA/CN/SNI、5000ms严格PUBACK、2048B、FIFO与原源时间戳均不变。应用仍限制sector0/1/2的48KiB，当前余20B；不得借此扩展擦除范围。冻结源码、资源、工具和恢复包见`node-b/evidence/B5-C-REPAIR-R4/TIME-INIT-R1/`。

## 一次确认、分开消费

| 对象 | 严格范围 |
| --- | --- |
| I-TI | 冷态准备中负责人C人工RESET≤1；随后C sector0/1/2安装一次≤180秒，一次连接，安装器正常Halt/Reset/Go各≤1。新鲜双1MiB Flash、双16B options、私有UID/保护、正常Flash和DISARMED、精确before通过才写；写后双全片/options及精确after。sector3/7/11/options与B不写。 |
| RO-TI | 安装后独立C只读一次≤90秒，正常Flash、精确after、DISARMED；显式halt/reset/go/写均0。 |
| L-TI | 隔离云只读和TLS/CONNECT/SUBACK/Backend/WSS就绪；仅原两个unit按RuntimeMax到期且配置/PID/权限/端口完全合格时各start≤1，总限300秒，不动正式服务/ACL/Broker，不开8884。 |
| E-TI `B5_FINAL_ECG60_R4TI` | B只读≤1，C人工RESET≤1，B5START≤1；ECG60/1mV、RA–LA–RL、电池无充电USB、非人体MOCK。45秒预热＋300秒评价＋15秒尾段，原420秒业务硬停，原60秒就绪/300秒人工准备/串口启动行确认不变。 |

ECG≥74250点、HR58–62且有效标量≥295、WSS≥2900，源点映射/时效、ADC250SPS、TEC/REC/BOFF、队列和STOP原判据不变。非目标流按原独立profile语义保真传输，不伪造有效值，不把本窗合并为ECG/RR同窗有效。TEMP/RR新窗口不在本次增补范围。

ESP在板供电非隔离例外须明确沿用；自主联网状态UNKNOWN。负责人完成全暗10秒后转JTAG至C，只开C J5，等5秒接调试器电脑USB，B断电、C USB_UART断开，负责人仅C实体RESET一次；若入场仍ROM/HALT立即停止，不追加复位或Go。I/RO/L通过后集中提示冷态回接B、C USB_UART与实际COM/B上电，记录就绪才提示E-TI唯一C RESET；工具直接按随后新DISARMED启动行发送一次START。

ROM/HALT/Fault、身份/Flash漂移、原生SDK错误、TLS/正式服务异常、AT边界未知或420秒失控即STOP_TARGET；不追加START、复位、Go、擦除或自动回退。安全离线研究继续。结束按批次关闭B/C J5，拔C USB/J-Link电脑USB并由负责人确认全暗。

R-APP只备妥新C49132→当前C49068的精确sector0/1/2回退，逐字节离线重建通过不等于实板恢复演练，实际恢复另批。R-CFG/R-CLOUD不在本次权限内。保留所有旧失败和原件，CPU ROM根因等遗留不补签PASS；不改BIO、保护分支或Security Gate。唯一交接仍为`B5-C-REPAIR-R4-FINAL-HANDOFF.md`。
