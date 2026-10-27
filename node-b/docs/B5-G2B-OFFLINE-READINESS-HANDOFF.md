# B5 sector3离线准备交接｜2026-10-27

**本轮只做只读生命周期核查和离线开发，未继续实板上云。** 最新负责人要求停止硬件/正式云写入优先于“做完”的目标。已通过的G1人工MOCK云测试、G2-RO双备及B5 Host/ARM、本地TLS、七页UI结果原范围保留，没有重跑。唯一实验分支 `codex/node-b5-cloud-integration-20261026`，起点 `72a02209c0ba205163be46bfa83ed3ae50d49925`。

## 实际状态与本轮边界

| 项目 | 裁定与证据范围 |
|---|---|
| G1人工MOCK云测试 | 历史PASS保留，不能替代实物B→C→云 |
| G1测试Backend/TLS当前存活 | **STOPPED_BY_RUNTIME_LIMIT**，北京时间2026-10-27 01:59:19到期；MainPID0、Result=timeout、Restart=no，18775不监听 |
| 测试账号/ACL | **仍存在，未撤销**；ACL/password文件SHA与G1一致，不能称环境已清理 |
| 正式四服务 | 本次只读观察active，PID及已绑定配置SHA与G1一致；8884未监听 |
| C双1MiB与双16B options | 10月26日G2-RO检查点PASS；本轮未重读实板，不能当今天运行证明 |
| 真实sector3新配置 | **OFFLINE_PACKAGE_PREPARED**，已加密封存；新记录被原固件C校验函数接受，未提交记录被拒 |
| 专用写入器/监督器 | 仅离线仿真与负例证据；**RAW_MEMAP_HARDWARE_NOT_VALIDATED**，不能称物理写入通过 |
| G2-A / G2-B / G3 / R-CFG / R-APP / R-CLOUD | 本轮实际执行均0，仍待分别批准 |
| 当前实板状态 | 负责人确认模拟器普通ECG60；B/C今日供电、运行、JTAG/USB及ESP状态未实测，未操作 |

本次SSH只读查询一次、退出0、重试0；无MQTT CONNECT/PUBLISH、WSS会话、HUP、start/restart或配置写。准确生命周期与正式服务比较见[回执](../evidence/B5-G2B-PREP/cloud-lifecycle-20261027T011046293943Z.json)。它是该时刻观察，不推定未来服务状态。

## 不变的固件与恢复检查点

- C仍以原24104B部署检查点为准；42552B尚未安装。唯一待审BIN为42552B，SHA256 `d5b9624b3da1129b4e045d3b2f669c00d2d93cb7379b15293ff143fe9f130683`；实现源码仍 `c65fbedce7edf5d822c573ef5cdeb6471d1ae3d5`。未重建或替换BIN。
- 原C完整Flash `b460d917e1d454fdb0882d1f837d91c606363179b817a3896a1df6897b2dcb98`；options16B `52d5979da03bd7be45e385920ec7d5901793bab3f6bc1daa0c1c1997f9e91687`；sector3 `1698c8783b4fbdd1bc7fc5a8641babc7b499b58a65be54e7b36c65c6c5b88313`。
- 原应用安装/恢复manifest `3782fc9caa0f921cc51001191df0ac90e2633710e89f56bae017d2e3d35e73fc`，实际双读来源绑定 `f614271c83b8b6f11992531537ea49ab6434f6f2a7c2481f1cced7ae55f1cad1`。原始ROM失败、人工复位后第二窗口成功、SDK实际返回及私有UID不覆盖。
- 原B39948B、历史ECG/RR六窗、BIO_V2阈值/ADS寄存器、H3/P4/main/P6等保护分支均未修改。B5独立冷启动、CPU ROM根因、同窗双有效、绝对阻抗、故障注入仍保持原未验证/UNRESOLVED状态。

负责人按停机程序断电不算新的冷启动或CPU实验；原人工复位后恢复也不等于ROM根因关闭。

## 新真实配置包与固件C判定

从G2-RO真实完整原件和G1专用凭据在受限EFS离线编制，未把主机、口令、UID或固件原码加入Git。仅在内存复用适用WiFi字段，其余312B payload＋24B头重建，代次3→4、CRC/长度/身份/AT字段约束不绕过。最低纪元是冻结的接受下界，不是SNTP实测。

| 对象 | SHA256 |
|---|---|
| 包绑定 | `20cba97d9587fd50f6ad9a98a19efc2812c62675e1304c646d88e771b9d2c73f` |
| 规划manifest | `082d3f89a251d1ad163ee36ad5e03f104d62eae948d2dec685ab1f1370e7236e` |
| 新336B记录 | `d098b53c8126832b38c2f91103dbc20ccff2d239a2618c8db0701ee00178d459` |
| 新sector3已提交 | `260dba9243272dfa2f678a688b0f772e2dace3d41eff84e5d1ce9e3ab9f72dfc` |
| G2-A应用后、G2-B配置前 | `3eaf583a703137b09665da5d2bfd7e860cd3a2208bf659b631d7ee4d0541545c` |
| G2-B配置后 | `acb33fdd39ecb016ecd848ec25eee051635f56ef8138b577a8590d2734ad687e` |

[完整字节回执](../evidence/B5-G2B-PREP/real-package.json)包含未提交镜像及恢复组合SHA。原sector3尾部16048B、应用、sector7/11和options必须保留。忽略指针 `node-b/build/b5-g2b-package-private-pointer.json` 定位受限EFS包；恢复档案及原始负例日志分目录保存。

新编译的专用小审计器直接调用冻结C代码 `h3_config_record_valid` / `b5_identity_allowed`：原记录CRC有效但B5身份拒绝、新已提交B5记录接受、新未提交B5记录拒绝；编译及三例真实退出均0。只验证新配置字节，不重跑原Host/ARM/TLS/UI，也不冒充ARM实板读取。见[C审计回执](../evidence/B5-G2B-PREP/actual-record-C-audit.json)。

## 写入器的工程审查与真实限制

新增专用sector3物理执行代码与独立180秒监督器，默认只输出禁用计划；本轮没有enabled=true授权、未加载J-Link DLL。没有放宽旧G2-A工具范围或修改冻结规划器。

原始MEM-AP路径用于避免高层Flash下载器自动读改写。SEGGER明确说明小块Flash写可能触发读改写，不能仅凭API名含WriteU32就宣称绕过擦除；新桥仍须在未来获批事务中先做只读跨路径核对，不能把仿真等同SDK/探针实测。[SEGGER说明](https://kb.segger.com/Read-Modify-Write_Flash)、[命令语义](https://kb.segger.com/J-Link_Command_Strings)。

本地STM32 RM0090 Rev11 p1682–1684表300/301用于核对SWD DP offset8的READ=RESEND、WRITE=SELECT，以及MEM-AP CSW/TAR/DRW；不再将RESEND读值冒充SELECT旧值。AP退出恢复CSW/TAR，SELECT仅规范化到AP0/bank0。p84–87及p100–104用于核对sector3、PSIZE32、Flash控制与数据缓存：编程前DCEN关闭并复位缓存，直到阶段验证与最终全片/options比较通过后才恢复原ACR。

状态机绑定唯一目标字节/顺序、一次sector3擦除、提交标记最后一次、整sector及全片/options双验、C身份、真实返回与错误停止；只允许健康暂停且非busy时清PG/重锁和恢复ACR，不在失败路径补写NVM、复位、Go或自动回滚。监督器超时杀进程后保留UNKNOWN，不重连清理。总限180秒，commit前剩余必须至少110秒，不足就保持未提交并停止，不加时。

新增writer最终**27项离线测试通过，真实退出0**，覆盖NOR/MEM-AP状态机、第二读漂移、原生错误、越界/重复commit、缓存、scope/包篡改、STOPPED恢复和监督器超时。开发期间18/23/23项各次回执也保留，不叠加为独立27项之外的验收数量。测试中有 `NativeLink.__new__` 假对象，真实 `__init__` / J-Link DLL加载均0；不能称原生SDK已验证。见[逐次回执与用例](../evidence/B5-G2B-PREP/writer-tests.json)。

| 冻结执行代码 | SHA256 |
|---|---|
| writer | `39befcee1c7426c0b74222509fbe86759da0f3d4d18521f6729bb95ac2a52107` |
| protocol | `d5705c619add19262e328f74513f1335142457afb80362b20ce61eada2df4e90` |
| 独立监督器 | `3f2fb998c758eac68d4312c6f5961a29610372578669ccaf1f1b18f9019e1197` |

完整工具/依赖/卡片以[冻结清单](../evidence/B5-G2B-PREP/bindings.json)为准；[检查点保留回执](../evidence/B5-G2B-PREP/checkpoint-preservation.json)确认历史47个交付文件SHA不变。[真实包加载核验](../evidence/B5-G2B-PREP/real-package-loader-audit.json)仅做15文件及原规划器重建，无目标连接。

恢复入口单独核对冻结的 `network_main.c`：STOP后armed仍为true，最终状态字节为 `00000101`（网络和MQTT均关闭），不是初始DISARMED全零。R-CFG必须在单独批准时选择这一个确切已停止状态或尚未武装的全零状态，暂停前后保持一致；活动armed/未关闭网络均拒绝。G2-B写入仍只接受全零，恢复后启动也要求全零，不修改固件或为过门禁自动复位。

## 下一轮各自独立批准

1. [G2-A R2](AUTH-B5-G2A-FRESH-001-R2.md)：仅42552B应用三扇区安装；新上电运行与ESP隔离需先实核，历史双备不等于今天状态合格。
2. [G2-B R2](AUTH-B5-G2B-SECTOR3-001-R2.md)：仅绑定的新sector3配置事务；新桥只读核对不一致须在KEYR前停。当前所有物理执行仍禁用。
3. [G1-RESUME](AUTH-B5-G1-RESUME-001-R1.md)：仅原独立测试Backend/TLS各一次start，另批；不动Broker、ACL、正式Backend/Hub/Nginx/AI，不开放8884。本轮未执行。
4. [G3 R2](AUTH-B5-G3-CLOUD-WINDOW-001-R2.md)：前置全部实过后，单次B5START；ECG60、RR/TEMP INVALID、A OFFLINE、MOCK，45秒预热＋300秒共同评价＋15秒尾段，420秒硬停。现场附件、ESP AT/CA/SNI及各层有界取证工具如有缺项即停在准入阶段，不能边测边放宽。
5. [R-CFG R2](AUTH-B5-R-CFG-001-R2.md)与[R-APP R2](AUTH-B5-R-APP-001-R2.md)分别批准：先配置 `acb33…→3eaf…`，再应用 `3eaf…→b460…`。默认恢复真实C24104检查点，不自动切换历史H3目标。部分失败态必须另绑新事务，不能硬套成功态before。R-CLOUD撤销账号/资源仍按旧独立卡另批。

本轮到软件准备与证据提交为止，不自动进入上述任何现场动作。后续首次新上电遇ROM/HALT立即留证停止，绝不为赶进度重刷掩盖。
