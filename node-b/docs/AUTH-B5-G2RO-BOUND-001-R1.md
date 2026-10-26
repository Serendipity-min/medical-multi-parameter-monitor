# AUTH-B5-G2RO-BOUND-001 R1｜C24104新鲜只读单次事务

依据负责人本轮`MPM-B5-002-G1-G2RO`授权，G2-RO一次读取已获准；**当前只完成工具离线准备，实际执行次数0**。HW0附件与独立冷态转接确认就绪后，主执行者才能在EFS生成单次私有启用记录；不以此卡授权热转接、改跳帽、改供电、复位或下载。

## 冻结身份与工具

- scope：`B5_G2RO_C24104_DOUBLE_BACKUP_NO_TARGET_ACTION`。入口仅独立监督器`node-b/tools/b5_g2ro_supervisor.py`；worker不能脱离单次已消费授权标记运行，授权绑定唯一输出目录，存在旧输出/标记即拒绝。
- C当前预期完整Flash SHA `b460d917e1d454fdb0882d1f837d91c606363179b817a3896a1df6897b2dcb98`；options16B SHA `52d5979da03bd7be45e385920ec7d5901793bab3f6bc1daa0c1c1997f9e91687`。私有UID/完整身份绑定C24104既有EFS原件，不能用B同款MCU代替。
- 固定DLL SHA `632d0d78e72b8a55c65945a0c393a9f081082c725fff4ba3081b0a565fd58cff`，冻结脚本/实际依赖SHA见[tool-plan.json](../evidence/B5-G2RO/tool-plan.json)。只有工具全部一致、授权未过期、EFS及现场附件通过才允许加载DLL。
- 既有23952B读回scope、旧24104下载scope不修改、不复用启用记录。G0的历史布局也不能视为本次新鲜采前包。

## 现场附件必须绑定

`site_record`及其SHA只在EFS。必要机器字段：`JLink_target=C`；`HW0_completed`、`cold_transfer_completed`、`no_hot_transfer`、`C_power_ready`、`C_USB_unchanged_for_session`、`BOOT_and_RESET_untouched`、`readback_only_no_power_change`均为true；`cold_transfer_authorization_id`指向负责人明确批准的独立冷态转接事务。

额外保留真实B/C电源、USB、P4/P6、CAN/参考地、A段与ESP现状。已知ESP在C但AT版本/网络态未知，可如实记`PRESENT_UNVERIFIED_NO_COMMANDS`；本只读事务不发ESP/网络命令，不要求把未确认的状态伪填ISOLATED。不能为获取读回条件临时热拔插、改线或重启。

私有授权另外必须冻结`enabled=true / owner_approved=true`、唯一output、有效UTC期限、180秒总限、会话1、重试0、显式reset/halt/go/目标写0、DLL/工具绑定及C身份/整片/options引用各自SHA。缺项在SDK前拒绝。

## 唯一一次非侵入会话

1. 监督器独占消费授权，启动唯一worker；SDK调用45秒（1MiB读）/5秒（其他调用）和总180秒均由独立进程监督。超时/STOP只终止worker，保存真实worker退出与监督退出，不另连恢复。
2. 打开顺序复用既有已冻结RuntimeLink保护：Open/Device前ForceAttachTarget、禁止连接重试、禁止自动更新、关闭重启、SkipDebugDeInit、排除Flash/options缓存；SWD1000kHz。Device可能隐式连接，只在未连接时调用Connect一次，不重试。`SetRestartOnClose 0`返回此前开关值：返回1且文本为空时，只允许再确认一次必须为0；这是冻结SDK初始化/关闭策略的确认序列，不是故障重试。Open前和Open后各一组、异常取消续跑至多一组，每组≤2次，因此该策略命令全会话最多6次；`SetRestartOnClose=1`仅已验证运行Flash后≤1次。其他连接失败不重复Connect。
3. 读取UID/F407/1MiB/RDP/Flash状态，与C私有原件精确一致才继续。DHCSR首次复位粘滞单独保存，然后VTOR、DWT_PCSR三采样、Fault、RCC_CSR、映射与Flash CR。ROM/HALT/LOCKUP/新增复位/异常即停止，不复位、Go或重刷。
4. 运行态禁止SDK ReadReg：真实PC/MSP明确`NOT_OBSERVED_RUNNING_NO_HALT`，DWT_PCSR只称PC采样；VTOR=0仅在0地址映射64B与Flash64B一致时接受，不写VTOR。
5. 两次**独立SDK**读取options `0x1FFFC000`16B与Flash `0x08000000`1048576B；每次实际返回长度、整数返回码与读序保留，先独占落盘再比较。第一份与当前C24104/options不符立即停止，不继续凑第二份；第二份漂移也保留两份原件，不自动重读。
6. 分别从两次整片保存完整sector3 `[0x0800C000,0x08010000)`、sector7 `[0x08060000,0x08080000)`、sector11 `[0x080E0000,0x08100000)`；确认逐字节相同，验证336B记录头/CRC/committed有效及B5身份不匹配。源配置正文不输出。
7. 正常运行Flash已验证后才设置已审`SetRestartOnClose=1`退出续跑策略；实际Close一次。显式Go仍0，但此SDK退出策略可能续跑，回执单列，不把它描述成“设备绝无运行状态影响”。异常运行状态取消续跑策略后唯一Close，无自动恢复；连接/关闭仍保留历史ROM风险。

SDK文本日志只保留消息SHA/长度、API整数返回与计时，不记录UID/配置/返回内存内容。身份UID和Flash/options原件只在受限EFS身份/二进制文件，公开回执仅SHA/布尔/退出码。失败不得将异常敏感正文复制到终端。

## 准出与边界

G2-RO通过后，主执行者仅从本次**独立双读**离线重建42552B sector0/1/2安装/恢复包及完整预期SHA；不能复制同路径两份冒称独立采集。保留sector3/7/11与options，不下载。新候选SHA仍为`d5b9624b3da1129b4e045d3b2f669c00d2d93cb7379b15293ff143fe9f130683`。

本卡不授权G2-A、G2-B、B5START、实际回滚、ESP AT/联网、旧ROM重复排查。不能把“读回一致”签成B5安装、恢复演练、独立冷启动或ROM根因通过。G2-RO未执行前门禁保持`FRESH_READBACK_REQUIRED`。
