# C46584三路独立窗口｜R2

落实PI在R1实测失败及负责人误触RESET后明确续批的三路测试，并绑定R2应用安装后的真实全片/只读。新候选46584B，BIN `d01d08c23de3fbdc6639609136cacc6c0da0eda1fc4489bad8273829a2200e7a`；全片 `707d88987431cb4cdf4580d8f627ba58eea4980429d95fc6dcde6ceb8718ca4a`。B固定40928B，gen5不写，ESP在板供电例外沿用当前批准。

独立scope分别为 `B5_FINAL_ECG60_R2`、`B5_FINAL_TEMP_OBJECT_R2`、`B5_FINAL_RR15_R2`。每个新token/原件目录/.used，START≤1、计划C实体RESET≤1、B联合只读连接≤1，失败不自动消耗下一窗，不复用之前失败START。C安装PASS、独立只读DISARMED、实际供电/COM/源/隔离事实及云状态通过后才逐窗启用。

沿用R1窗口卡的全部数据、数量、源、温度入口、STOP及时间门：准备300秒、启动行确认后30秒START门、60秒共同就绪、45秒预热、300秒共同评价、15秒尾段、420秒硬停、20秒被动观察；B连接上限755秒；云驻留≥805秒。MCU源STOP应420000ms/reason1/CLOSED7/unsynced0/pending0，保留原419–422秒主机观察门。

与R1不同之处仅为恢复已存在端点轮换所需的启动前失败观察额度 `precommon_ntp_retries_max=2`。固件只对“48B发送完整、零回复、UDP已关闭、AT同步”的已知情况向原下一端点尝试；每包仍完整1000ms门、新nonce，粗TIME/部分包/错误nonce/未知状态等不重试。额度不是新增START，也不延长60/420秒；新窗口不得靠过往ESP启动的授时结果代替本次新鲜验证。

- ECG60：普通60bpm/1mV、RA–LA–RL/LL空，电池无充电USB；HR58–62 VALID、RR INVALID，ECG≥74250连续源点、RESP≥14850源点、HR≥295条，WSS≥2900。
- TEMP_OBJECT：原GY-641V3 PC11接收、PC10不发配置，非人体物表；有效TEMP≥295报告，真实UART→CAN→C入口追踪→Broker→Backend→WSS一致；2500ms与原2ms界不放宽，无临床/绝对精度结论。
- RR15：独立呼吸15bpm/1.5R、周期30bpm、窒息0s、RA–LL–RL/LA空，RR14–16 VALID≥295条、RESP≥14850源点；HR无有效QRS必须INVALID。由负责人在该窗前冷态断B/导联模块改黄L至LL，禁止热改、短接LL/RL或将RLD接地；完成事实另行绑定。

每窗五层原件、同session/boot/seq/UTC/值、MOCK/synthetic、Backend接受=去重Broker且拒收/丢弃0，无新增覆盖/过期/历史代实时/错误STALE/txfail/mqtt_fail，QoS1严格PUBACK、QoS0波形及2048B不变。A OFFLINE，麦克风/TTS/人体断开。

计划C RESET只在记录就绪后提示一次，之后不再触碰复位；意外启动横幅先停止并核对负责人事实，不能自动归咎CPU或自动复位继续。任何ROM/HALT/漂移/UNSYNCED按原STOP_TARGET处理。云服务启动/ACL修改、R-APP/R-CFG/R-CLOUD等仍为独立对象；当前云服务若在运行只读核验，不自行重启正式服务。
