# gen5与G3分对象授权包｜默认全部禁用

2026-10-28。`enabled=false; owner_approved=false; executions=0`。当前仅授时复验已批准并完成；本文件不批准Flash、服务启动、接线、B上电或B5START。PI可一次选择多项，但各项仍有独立scope、私有授权、有效期、SHA及`.used`，失败不自动转入恢复。

## 前置事实及来源

本次快速桥仅一次48B公网请求，完整区间595ms，冻结C函数1秒门、nonce/格式/epoch及清理均通过；前一SNTP启停/读回/时间推进通过。原2578ms失败与首条SYSSTORE ERROR不覆盖。实际回执及SHA见对应FAST证据目录。

gen5离线包由既有G2-B双读一致的gen4完整镜像、options、身份原件和本次成功入网的私有Wi-Fi参考生成。它是**待现场核对模板，不是今天新鲜全片实读**。包manifest、每个原件及完整工具SHA在受限EFS，公共来源清单仅给指纹。本轮不改变B39948/C42552应用、BIO_V2或TLS。

## 对象A：C sector3 gen4→gen5

- scope=`B5_GEN5_WIFI_WRITE`，phase=`provision`；新入口`node-b/tools/b5_gen5_writer.py`，默认禁用，经独立监督器执行。旧G2-B R3的3→4许可不能借用。
- 授权必须绑定私有package/manifest SHA、before/after完整镜像SHA、卡/工具/DLL SHA、输出及有效期，和本次SNTP＋FAST实板PASS回执SHA；准确数值在封存manifest中，不在模板里猜填。
- 一次连接180秒；Halt≤1、仅sector3 erase≤1、最后commit≤1、正常Reset≤1、真实Flash PC/MSP匹配后Go≤1；不重试。禁止整片擦除、解保护、options或其他sector写、B5START与AT。
- 写前核对C实时私有UID/F407 1MiB/保护位、ROM/HALT/Fault、DISARMED=`00000000`、电压/HSE/空闲控制器；**同一连接双1MiB Flash、双16B options**逐字节匹配模板。未知或漂移在unlock前停，不刷写掩盖。
- 原始MEM-AP与SDK只读交叉核验后才可写；只写`[0x0800C000,0x08010000)`，验证未提交整sector、提交字最后写；完整全片/options再次双读。336B记录仅SSID、Wi-Fi口令、generation/CRC改变，16048B尾部、应用、sector7/11及options保持。
- 仅成功写验后按上述批准复位/Go，并证明Flash运行及全零DISARMED；这不是一次新的CPU根因实验。若异常，保存原件、停止，无自动再擦除或回滚；只在链路健康、控制器idle、已暂停且范围允许时清PG/重锁/还原ACR，不能把它称作数据恢复。
- 现场附件一次冻结：J-Link在C、C供电和USB实际状态、B/A段状态、CAN/独立地、BOOT/RESET、其他进程独占和无人体。ESP若仍在板供电，必须**本对象另批**非隔离例外；`ESP_isolated=false`、自主联网UNKNOWN，不填成隔离。需要断电改线则另按明确物理动作批准，不能热转接。

## 对象B：云服务只读与必要恢复

- `G1_LIFECYCLE_READONLY`：仅既有隔离Backend/TLS及正式服务/PID/配置保护检查，一次只读SSH≤120秒，使用既有别名和受限输入；不读取私钥、不打印凭据、不启服务、不发布。
- 若测试实例已经停止，再单独批准`B5_G1_RESUME_EXISTING_TEST_UNITS_ONLY`：复用既有G1-RESUME R2及本次新绑定，两个测试unit各start≤1，300秒硬限；不restart、不HUP Broker、不改ACL/password/正式Backend/Hub/Nginx/AI、不开放8884或其他公网端口。输入/状态漂移即停，不自动回退。
- 真实服务状态当前UNKNOWN，历史6小时驻留不能当今天仍在线；账号/ACL没有因驻留过期自动撤销。G3前须证实至少625秒可用驻留预算、TLS名称/CA有效及正式服务不变；不足就停，不假造expiry。

## 对象C：gen5 C只读准入及冷态台架准备

- 现有HW scope=`B5_G3_PREP_C_READONLY_AND_COLD_TRANSFER`；gen5适配必须绑定本包、gen5安装真实PASS回执与新的完整镜像引用。未写入时不能用离线包冒充已安装。
- C只读一次≤90秒，核对UID、完整Flash、options、gen5及DISARMED；不Reset/Halt/Go/写入。通过后才按单独批准的物理附件冷态转接：B/C J5、C USB、J-Link电脑USB全断，全部灯灭10秒，JTAG从C到B；恢复C原J5和USB_UART/USB232、B原J5，最后接J-Link电脑USB。方向不明即停。
- 实际COM及电源/隔离/源设置由负责人一次回报；不复用昨日COM、不把本准备当冷启动根因验收。A段、INMP441、TTS、人体断开，B CAN1↔C CAN2及独立地沿用已验路径。

## 对象D：唯一G3真实云窗

- scope=`B5_G3_ONE_ECG60_MOCK_CLOUD_WINDOW`；必须分别取得A安装、B云就绪、C新鲜只读及物理附件PASS。将本卡SHA、gen5包/真实安装/只读回执SHA、来源/服务到期、工具及环境一次冻结；当前没有可执行G3授权。
- 串口记录与Broker/Backend/WSS观察就绪后，计划内仅C人工RESET一次；收到本次DISARMED启动行及负责人完成回复，再发**一次8B `B5START\n`**。不复位B、不补发、不自动重新武装。
- 沿用原判据：ECG60/1.0mV、R→RA/L→LA/F→RL-N/LL空、电池无充电USB，无人体；HR58–62且稳态有效，RR/TEMP INVALID、A OFFLINE，所有层MOCK/synthetic，不合成双通道同时有效。B250SPS采集完整，ECG100点/250SPS、RESP50点/50SPS及session/boot/seq/时间/质量标记正确。
- ARM后420秒硬限：≤60秒连接就绪、45秒预热、300秒正式评价、15秒尾段。74250 ECG点、14850 RESP点等既定数量/时效判据保留，不采后修改；当前G3源代码数值冻结并由授权绑定。
- 真正取得Broker接受、Backend接受和同一session的WSS快照，CAN ACK、QoS0发送或PUBACK均不替代实收。测试身份`GW-B5-001`/`b5-c-isolated`和只读observer独立于正式`GW-C-001`。
- ROM/HALT/故障/复位/ADC异常、越权身份、LIVE误标、TLS验证失败、CAN BOFF或正式服务异常即停；不改时间/证书校验/阈值绕过。未确认MCU STOP时按预批物理停机方式由负责人断B/C J5、C USB、J-Link电脑USB；主机杀进程不等于MCU或ESP停止。

## 对象E：配置及应用恢复（各自独立批准）

1. `B5_GEN5_REVERT_GEN4`：gen5→本次写前gen4，保持B5应用42552B，只是测试配置回退，不是完整原部署恢复。
2. `B5_GEN5_RCFG_ORIGINAL_GEN3`：gen5→原gen3整sector3，保持B5应用，作为完整收尾的第一步；尚未执行G3时入口全零DISARMED，正常云窗停止后入口可为`00000101`，**必须事前冻结其中一个精确值**，不能把活动network/mqtt状态当可恢复。
3. 两种配置恢复均用各自before/after全片及阶段sector SHA、独立ESP在板例外、一次180秒、erase/commit/Halt/Reset/Go各≤1、前后双全片/options；部分写失败后的镜像不符合before时不能套用旧恢复卡。
4. R-APP复用现有`B5_C_SECTOR012_MOCK_INSTALL_OR_RESTORE_NO_CONFIG_WRITE`的restore对象：仅在gen3 R-CFG真实通过后恢复原sector0/1/2，目标是**接收B5前C24104实测完整检查点**。旧R-APP R2要求ESP隔离，不能借用gen5写入例外；可在该恢复对象中明确批准冷态移除ESP并由负责人确认后再绑定隔离事实，或先完成另一个在板例外适配审查。此条件未补齐时R-APP仍BLOCKED，不执行。
5. 若最终要历史H3，而非C24104，另绑该完整镜像/配置、设备身份和现场条件；不能把软件标签或C24104原件称作当前H3镜像。

## 对象F：R-CLOUD

停止测试实例、撤销测试账号/ACL及清理临时资源是另一个独立对象；要先绑定最新Broker MainPID/包装器/受控HUP机制及完整备份，正式服务不重启。没有此批准就保留并如实说明，不能用“服务驻留结束”宣称账号已清理。

当前所有后续对象均禁用；本轮只产配置包、软件验证和审批材料，不实际写入、迁线、启云或发送B5START。
