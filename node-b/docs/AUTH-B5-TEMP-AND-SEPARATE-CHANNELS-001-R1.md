# B5温度启用与分路验证｜R1

## 已冻结的软件与真实现状

R4已完成300秒共同评价、420.078秒STOP；原review退出3，仍有3条标量REPLAY及68点ECG缺口，不追补PASS。当前实板B39948B、C42880B+gen5；C已STOPPED、禁止自动重武装。负责人新增要求分别测量并验证ECG、RR、TEMP传输，原G3的TEMP INVALID判据不覆盖或改写。

负责人确认温度为GY-641V3，VCC=3.3V、共地、RC→PC10、TD→PC11，无非人体温度参考源。UART4仅9600/8N1接收PC11，PC10保持输入，不发送模块配置或保存命令；接收不到完整有效帧就留证，不自动改波特率、模式或模块NVM。

厂家原件响应为`A4 03 07 07`＋7个寄存器＋校验，共12B；项目整理手册中长度06的说明不采用。保存To/Ta/Bo及原帧；本轮TEMP仅为0..100℃非人体物表To工程值，单位0.01℃，新鲜期2500ms，明确非临床补偿体温、非绝对标定。负温/域外值保留原码但INVALID。B原PDO2保留字仅在新变体中携带TEMP帧龄，配套C还原测量时刻；不把重复发布当作新测量。

## 本次可申请对象：仅B启用与只读接收

1. `B5_B_TEMP_APP012_UPDATE`一次：候选40928B，BIN SHA256 `a1cf57648ca3787de30c1ad7055634c278fbbde538bb0bc562961bd212182ed2`；ELF `e0433f3246e3e9aa422365834ceeae7e2e3c68360164a8bb583d7a45f4700ed1`。正常Flash及B私有身份/保护一致后，新鲜双完整1MiB Flash及双16B options，精确匹配私有before/after包才Halt≤1、sector0/1/2写49152B≤1；双完整after/options及所有尾区一致后正常Reset≤1、向量PC/MSP匹配才Go≤1。一次连接180秒硬限。sector3/options/模块NVM/C/云不写；ESP继续在C板供电需本次明确例外，不填写已隔离。
2. 安装PASS后独立`B5_B_TEMP_15S_READONLY`一次：90秒总限，其中15秒接收观察；独立监督器和新符号表白名单。完整Flash/options、身份、正常Flash/ADC计数及温度64B诊断读回；reset/halt/go/UART写均0。保留To/Ta/Bo、原帧、校验/头错/溢出/串口错/时基及CPU证据。没有有效帧时保留`B_TEMP_NO_NEW_VALID_FRAMES`，不自动重试或发配置。

现场沿用J-Link在B、B J5、C供电/USB不变且维持STOPPED、CAN/地/BOOT不动、非人体；不需要为此转接J-Link或改线。是否仍保持这些现状及ESP例外，随本次批准一次确认即可。发现ROM/HALT/未知、漂移、保护/原生错误立即STOP_TARGET；不复位续试、不自动恢复。B BIO_V2/ADS寄存器不改。温度变体内只将CAN时间锚与当前时刻放在同一临界区取样，修复已离线复现的假过期；不能冒称已唯一解释R4缺口或解决历史ROM。

原B39948B完整原件及sector0/1/2恢复包留EFS，安装前必须再次真实双读匹配。恢复未执行、未演练，另行独立批准；不能把准备好恢复包当作恢复PASS。所有私有包、工具/DLL、身份、before/after及现场附件SHA绑定一次性私有授权，模板默认禁用。不得用原B固定RAM地址采新固件。

## 后续分路窗口：尚未申请执行

取得温度真实接收证据后，绑定配套新C及新B ABI、冻结三种独立源profile，再统一申请C安装及三个分路云窗。每窗仍45秒预热、300秒评价、420秒硬停、MOCK/synthetic及真实Broker/Backend/WSS实收；ECG普通60/1mV沿RA–LA–RL，RR独立15/1.5R/周期30/窒息0沿RA–LL–RL，温度使用同一非人体被测物，不签绝对温度精度。源切换/改线按冷态步骤由负责人实施。各窗的HR/RR/TEMP有效性及原码映射分别裁定，不用原TEMP INVALID的G3报告工具裁定新温度窗。

本卡本次前两对象不包含C下载、切源、改线、人工RESET、B5START、测试服务启动/撤销或任何实际恢复；后续未准备完毕的对象不提前启用。不合并保护分支、不改正式云或启动Security Gate。
