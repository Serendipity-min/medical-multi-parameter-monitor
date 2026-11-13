# G3R6 易失授时收尾与公网单包综合结果

2026-10-28。独立B5分支，起点`d9af94bfbd86166fe1bb9ad30ecbbe4ee66e2cd9`。本报告合并前次SWD续窗归档、本轮实际授时、失败归因、离线修正和下一次受控单包建议；不签发gen5写入或G3权限。

## 裁定与设备状态

**SNTP_CLEAN_PASS；公网真实48B回复已取得，但冻结的完整区间1秒门未通过，因此整轮仍为BLOCKED。** 没有用辅助子区间或离线重放改写实板失败。gen5未生成/未写入，G3未启动。

| 事项 | 实际结果 |
|---|---|
| 前次SWD人工复位续窗 | 第2/3连接正常Flash、受检身份/应用头/配置/options匹配、DISARMED、任务推进；第3次入口证实第2次Close后推进883ms；Go0，原ROM失败保留 |
| 本轮第1窗口 | 首条`AT+SYSSTORE=0`收到完整ERROR；未入网、未启用SNTP、未发手工包；关闭/读回/状态及健康Close通过，退出1 |
| 本轮第2窗口 | 先查询SYSSTORE=1，设置0并再读回0后才易失入网；SNTP启用/读回、12份时间样本、关闭/读回/无socket均通过；退出0 |
| 本轮第3窗口 | 被动接收模式下发一个48B请求，收到48B NTP回复；关闭socket、恢复原接收模式0、健康Close通过；完整区间2578ms，严格C门拒绝，退出1 |
| 总调用/动作 | 本轮3个SDK会话，各≤180秒；SDK分别930/7245/4005，共12180；SNTP启用1、disable3（含首笔失败收尾）、手工NTP包1 |
| 禁止对象 | 代理Reset/Go、Flash/options/sector3写、ESP刷写、B5START、正式云与测试云服务变更全部0；BIO_V2/ADS/CAN/TLS未改 |

接线未动，B未上电，J-Link留C。各窗健康退出；SNTP关闭读回、无socket、接收模式恢复均有原始证据。无需负责人额外物理操作。最后一次Close后未另开连接，不把主机关闭当作物理断电或未来状态保证。旧CPU ROM/HALT根因继续UNRESOLVED。

## 实际授权、失败与最小纠正

负责人本次明确批准有界易失Wi-Fi/SNTP启停和一个受控公网包；未批准持久配置、B5START或云变更。初计划两笔180秒，首笔在第一条AT即安全失败且未消费启用/单包权限；随后公开说明保留失败计数，把同一轮上限限定为三笔180秒，不清零旧`.used`、不重复发包。

初次ERROR是模块AT协议返回，不是DLL负返回、短读、预算或CPU故障。原样回执和执行源码保存在EFS，原因不强行归为“已是0所以不能设置”。修正为先查询：仅读回0才可跳过无必要的设置；若是1，设置和后续0读回必须通过。本次实际走的是1→设置0→读回0，未绕过易失门禁。

SYSSTORE=0之后才执行CWMODE/CWJAP；这是ESP-AT文档规定的不保存模式。[Espressif v2.3 SYSSTORE说明](https://docs.espressif.com/projects/esp-at/en/release-v2.3.0.0_esp8266/AT_Command_Set/Basic_AT_Commands.html#at-sysstore-query-set-parameter-store-mode)。Wi-Fi凭据仅复用已有受限参考，不打印、不写Git，也未改sector3的旧SSID。

## SNTP正常收尾证据

- 一次`CIPSNTPCFG=1,0`及配置读回，默认服务器列表与冻结私有参考相符；没有轮换服务器或重试启用。
- 在约0至33秒内查询12份模块时间，达到冻结下界`1792977536`并递增；启用、时间条件和关闭各自记账。递增本身不单独证明一次新的网络校时瞬间，另取新nonce公网回复作独立来源证据。
- `CIPSNTPCFG=0`成功，随后明确读回0；CIPSTATUS无应用socket，UART配置未漂移，C仍Flash运行且DISARMED，Close前重新检查通过。
- 内置SNTP可自行发DNS/NTP重试流量，实际包数未在AP抓包，不把“一次enable”说成“只有一个网络包”。手工公网NTP请求则严格只有一个。

## 新鲜公网回复与1秒门

目的IPv4来自本次ESP DNS回复并在发送前冻结，只选一个全球可路由端点、远端123、本地42024。唯一48B请求采用本次nonce。接收模式临时设为1，结束恢复原值0；并未把主动模式的CIPRECVDATA ERROR当根因。[Espressif被动接收说明](https://docs.espressif.com/projects/esp-at/en/release-v2.3.0.0_esp8266/AT_Command_Set/TCP-IP_AT_Commands.html#at-ciprecvmode-query-set-socket-receiving-mode)。

| 检查 | 实际证据 |
|---|---|
| 新nonce / 长度 | 本请求8B originate匹配；回复48B |
| 服务器字段 | LI=0，version=4，mode=4，stratum=2，时间达到下界 |
| 判定实现 | 编译冻结C固件的同一`sntp_sample.h`作Host适配器，未修改判定函数或MCU时间 |
| 采前冻结计时 | 从发送CIPSEND前至完整回复观测，保守主机区间2578ms；超过1000ms，**原判定FAIL** |
| 关闭/恢复 | 无socket、接收模式恢复0、UART寄存器不变、Flash运行/DISARMED与Close通过 |

离线把相同回复送入同一C函数、仅将RTT参数设为1000ms时，其余字段通过；这是用于隔离拒绝原因的重放，**不能把人工参数替代实测RTT来签PASS**。没有在设备设置人工系统时间、放宽TLS或重发请求。

### 开销拆分（辅助取证，不改变冻结判定）

提示命令约484ms，SWD逐字节写48B及SEND响应约1313ms，被动读取19B命令及返回约781ms。旧桥每字节需要12次MEM-AP调用及TX状态读；每次RX还读取8192B完整环缓冲，工具开销显著。

实际SEND回复已包含`+IPD,48`。最后一个payload字节的原生DR调用开始，到该提示被观察到约453ms，表明数据在这个子区间内已到ESP缓冲；之后读到的包nonce一致。这个较短区间有助于排除“本次仍然完全无回包”，不能取代原完整区间或证明C固件原生传输计时已通过。完整包被Host观察到距最后DR调用约1234ms；SDK与UART传输、缓冲读回的耗时必须分开。

时序数字均来自原始SDK active事件与返回日志对齐，操作名和调用数逐项匹配；无PCAP或路由器侧抓包，不宣称已测量真实线上RTT。

## 离线修正与回归

保留执行源码后新增`b5_esp_fast_uart.py`，**尚未实板执行**：

1. 一条命令/一个payload只打开一次MEM-AP上下文，使用原始AP读UART_SR并按固定字节写UART_DR，结束恢复CSW/TAR及规范SELECT。期间不混入会改变AP上下文的SDK内存读取。48B在真实Python包装器＋假DLL中为202调用，原逐字节方案为624；TX等待仍有上限。
2. RX仅读取已变化且≤512B的既定环缓冲区域，支持回绕、前后head一致性、错误/消费者变化及超限拒绝；不再为几十字节回复复制完整8192B。没有新增UID/Flash读取或UART_DR读取权限。
3. 单独FAST_SCOPE默认禁用，旧已消费授权不能启用它；仍用原保守完整区间和原C函数1000ms门。没有用453ms子区间改工具的通过标准。

新增时间事务14项、快速桥8项及受影响ESP回归合计100项，退出0；无真实J-Link/网络测试。未重复旧Host/ARM、TLS/UI和算法六窗。工具本轮的运行版和修正版SHA分别保留，不能把修正版测试写成已执行版实板PASS。

## 下一次最小授权建议（DRAFT_DISABLED）

下一笔只需审批**一次快速桥公网NTP复验**，不是gen5或G3：

- 一次C SDK会话≤180秒、一个新的48B nonce、一个已冻结公网端点123/本地42024；没有重发、Go、Reset或持久写。
- 前提是C/ESP保持供电、现有易失Wi-Fi未变，进入时Flash/DISARMED、SYSSTORE0、SNTP0、无socket均重新核验；若掉电/网络变化，先停，不默默重新启用SNTP或入网。
- 使用已离线验证的FAST_SCOPE、最小RX范围与同一C解析函数；采前冻结完整计时起止，仍须≤1000ms；失败关闭socket、恢复模式，异常状态不强行恢复。
- 新nonce、活动令牌、输出目录与新工具/Host DLL SHA必须在下一次明确批准后冻结；当前只保存禁用草案，无新的实际发包权限。

只有完整新鲜门通过后，才生成仅Wi-Fi字段变化的gen4→gen5记录、CRC/提交字/完整sector3和恢复包；再分别准备应用/配置恢复、测试服务和G3的对象授权。当前不生成可写gen5，也不启动服务。G3仍要求独立身份、MOCK、ECG60、RR/TEMP INVALID、A OFFLINE、300秒评价与420秒硬停及Broker/Backend/WSS真实实收。

## 归档与提交

[本轮结果](../evidence/B5-G3R6-TIME-01/result.json)、[时序辅助取证](../evidence/B5-G3R6-TIME-01/udp-timing-forensics.json)、[回归](../evidence/B5-G3R6-TIME-01/tests.json)、[来源绑定](../evidence/B5-G3R6-TIME-01/bindings.json)分别保留。私有EFS保存全部原始AT字节、nonce/端点、SDK、授权消费记录、失败与正确退出码、执行版源码和Host DLL；公开不含密码、SSID、IP/UID或配置原码。

上轮人工复位后续窗本地记录一并归档，先前ROM回执不修改。本阶段完成安全收尾、离线修正后集中提交一次，不因中间AT异常推送；实际远端回读结果另存在build/EFS，不预签通过。
