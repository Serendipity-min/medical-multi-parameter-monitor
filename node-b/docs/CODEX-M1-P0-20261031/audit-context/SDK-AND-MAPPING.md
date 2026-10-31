# M1-P0：B41012映射与SDK复用上下文

本审查仅读取既有源码、历史安装回执和同次本地制品；没有加载DLL/SDK、枚举探针、COM/网络、实板连接或构建/测试。基线为025839a2fc272232141b557bfce8aa10952ca682。制品和源码SHA、映射符号原行见 `node-b/evidence/CODEX-M1-P0-20261031/b41012-mapping-and-reuse.json`。

## 同次安装构建链

本轮重新计算 `node-b/build/b4-arm-20261030T062335164483Z` 中的三个既有文件：BIN41012B SHA1dbbf27177caa429f037ac72c43581a519e8ff70ac6224411c9c4ffe9529432d；AXF811816B SHAe11219c4de3718fc0832a6e6863ec9645836300197f36503cc13d8e8bd9923b7；symbols108998B SHA07e2166e9a145bcbdbb592b475b789cf55553ee38cf97c1dd5fcf9aebe7853f8。与既有安装摘要及 `b5_channel_profiles.py:40-45` 所用完整链相符，不混用后来相同BIN但不同.comment/symbol路径的AXF。

这是本地制品存在性/身份核验，不是新读板或当前冷启动证明。实际板是否仍为B41012、完整Flash/options/身份是否匹配，必须在下一次独立批准的B会话中核验；本轮不读取UID或Flash字节。独立冷启动只由当期现场证据建立，新的run_id/输出目录本身不证明冷启动。

## RAM/槽ABI

| 项目 | 地址/大小 | 原符号依据 |
|---|---|---|
| BioV2诊断 | 0x20001d20 /120 | g_bio_v2，symbols:1617 |
| ADC统计 | 0x20000614 /48 | s_stats，:558 |
| 初始化RREG缓存 | 0x20000644 /12 | g_ads_readback，:1616 |
| 原ADC槽 | 0x2000216c /3072 | slots，:855；128×24B |
| CAN生产队列 | 0x20002d6c /2560 | queue，:879；128×20B |
| UTC锚 | 0x2000376c /16 | clock_anchor，:880 |
| CAN诊断 | 0x2000377c /44 | g_b_can，:1618 |
| UART4接收环 | 0x20004878 /1024 | rx，:1089 |
| 温度诊断 | 0x20004c78 /64 | g_b_temp，:1619 |

`b5_b_temp_readonly.py:18-19` RAM及 `b5_channel_profiles.py:44-45` R6 slots与上述符号一致。G3从slots起5692B一次读涵盖3072B原ADC+2560B CAN队列+16B时钟+44B CAN诊断；`b5_g3_contract.py:255-263` decode_block可复用。若M1只采原槽，可复用StableSlots的3072B路径，无需为了复用旧G3而读取CAN/时钟/温度之外无关地址。

原24B记录为status大端3B、CH1呼吸原码signed24、CH2心电原码signed24、flags@9、padding@10..11、seq little32@12、IRQ cycles@16、sample_ms@20，见 `stable_slot_export.py:75-90`。两原ADC通道均250Hz；50Hz RESP为 `b_canopen_app.c:76` 按seq%5抽取的派生流，不应把全部CH1原码先丢掉再称独立50Hz原始ADC。保存所有版本、至少两份完全相同记录、冲突/复位隔离规则可直接沿用StableSlots，不用新投票算法。

## 最小复用边界

- `b5_g3_devices.BLink:24-92`已有原生返回日志、负读返回/正数短读区分、全片/options读次数限制、RAM/profile扩展和Close标记；可复用库方法，但不能运行G3旧CLI或原封不动使用其gate。
- `BLink.gate:34-42`耦合ARM_ATTEMPT、422s业务及565s总会话；`call:47`固定100000调用，不是M1的165s采集/独立停机预算。M1应以小型适配子类收紧自己的gate/调用额度/精确地址及Close阶段，不改旧类或全局profile。
- `b4_runtime.snapshot:59-100`接受显式RAM映射，保存状态及原字节；TEMP用BIO→TEMP→BIO夹逼留原件。`assess:103-124`判累计ADC/序号/时钟推进，短间隔非原子观察不当作250Hz精确证明。M1的120个1Hz槽仍应独立实现，不能借旧联评器改分母。
- `readback_b.Link.__init__:46-80`构造时即检查DLL哈希、打开本地日志并CDLL加载。新M1授权拒止必须在构造或工厂调用前；导入模块与真正构造分开，不把OFFLINE_MOCK字符串或自填字段当现场权限。

## Open/Close原生风险仍开放

`RuntimeLink.open` (`runtime_state_b.py:78-102`)在Device前设置禁止更新、禁止重试、ForceAttach、SetRestartOnClose0及SkipDebugDeInit；Device选择可能已隐式连接。SDK探针枚举、USB选择、OpenEx、TIF、SetSpeed、Device/Connect都不是物理零副作用证明。白名单不含显式Halt/Go/Reset/写RAM/Flash，但不能由此推出SDK内部从未暂停/重置目标。

`readback_b.Link.open:115-139`在OpenEx返回None后才置opened=True；失败前可能部分初始化的原生状态仍UNKNOWN。构造中CDLL/回调/日志初始化失败时，调用方可能还没有可Close的完整对象；M1应保存该阶段并让隔离worker进程结束，不能自动第二次Open或声称正常Close已执行。

`BLink.read:74-81`分别标记负值和正数短读，清verified_running_flash；不得把正数当成功。`BLink.call:58-70`以心跳记录原生deadline，并记录返回后超时；真正阻塞要外层监督器到期终止，不能只依赖返回后检查。M1需要分别记录原生码、worker码、监督器reason与终止码。

`b4_runtime.snapshot`会请求set_close_resume(True)，但BLink (`:43-45`)在final_close_verified=False时压住该请求；最终只有再次确认CPU在Flash健康运行且策略获批，才可启用Close续跑。若错误/ROM/HALT/原生失败，不能为“清理”自动发Go。`c_b4_readonly.check_running:91-103`检查合法Flash区/VTOR/别名；它只是当次观察，不证明Close后的CPU继续运行。

`readback_b.Link.close:162-180`直接调用JLINKARM_Close，不经过call gate；它写5s活跃心跳，但需要监督器执行超时终止。Close异常会使后续本地句柄清理中断，当前库本身未给出全面异常清理保证。M1应预留独立Close预算，记录Open失败、Close失败、阻塞/强杀以及Close后目标UNKNOWN；不重连确认，不由Mock签发SDK_RESIDUAL_RISK_CLOSED。

预算应明确拆成Open/身份/完整Flash或前缀/Options、准备推进、165s采样、末态/必要读回、Close与监督收尾；不能以165s采集预算容纳全部工作。50ms轮询约3300次，每次CPU+槽读，0.5s完整诊断约330次且含多次CPU/RAM读，SDK调用可超过12000。额度须按实际适配精确计算并留Close余量，不能照抄旧500/24000/100000或把循环次数当原生调用数。上述是离线静态计数，不是现场WCET或原生耗时证明。

签署、信任根、nonce、当前现场和制品绑定来自独立的新M1卡；P1-B原CLI尚禁用，旧G3签卡/nonce已消费，均不能继承。Mock只能检查这些拒止/控制路径，不能建立今日身份、冷启动、SDK原生副作用或RR15源真值。
