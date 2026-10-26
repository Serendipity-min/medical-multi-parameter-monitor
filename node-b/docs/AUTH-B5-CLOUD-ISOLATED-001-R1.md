# AUTH-B5-CLOUD-ISOLATED-001 R1｜待PI审批，当前禁用

合同：MPM-B5-001。本卡仅为下一轮准入计划，`enabled=false`、`owner_approved=false`；本轮软件授权不包含下列硬件、配置、ACL、云端或启动动作。不得根据本文自动执行。完整源码身份由[B5交接报告](B5-CLOUD-INTEGRATION-READINESS-HANDOFF.md)和[候选清单](../deployment/b5-candidate.json)绑定。

## 固件与已有状态

| 项目 | 冻结值 |
|---|---|
| B，保持部署不变 | 39948B，SHA256 `676eb7a46ad9cd15c7bf93db51a1931d7711d37c6f2fd636197dc4a85b339b82`；Node-ID2、CAN1 500kbps、ADS1292R 250SPS |
| C，当前仍为B4台架版 | 24104B，SHA256 `127ba765b8144e8f8ae98ef826ac2a98f45f8facb4021ce1888c004e5ca46547`；当前完整Flash冻结SHA `b460d917e1d454fdb0882d1f837d91c606363179b817a3896a1df6897b2dcb98` |
| 唯一B5送审候选 | 42552B，SHA256 `d5b9624b3da1129b4e045d3b2f669c00d2d93cb7379b15293ff143fe9f130683`；ELF SHA `3c726f61f76eadac4909826203ca84dee65521aec448ad477ddca0c3c58795d8` |
| C应用范围 | sector0/1/2，`[0x08000000,0x0800C000)`，不能沿用旧C仅sector0/1的授权 |
| 恢复目标原件 | 原H3完整Flash SHA `1c7ea80359892a96a68503f9a0f054d16d860088f3831b0749b4eb7226549390`；原件/配置只留受限EFS |
| 离线布局包 | manifest SHA `ba21721a0e7d8654c29b7be2b848c4eacc7b9e9da6ccc0adefb1deb61f789c5a`；仅历史H3布局计算，不是今天C的实时备份或安装许可 |

负责人已说明ESP8266装到C；本轮未查询模块供电、串口、版本或联网状态。J-Link在B、C串口COM6等仅为最后记录，下一轮按实际枚举和板卡身份核实，不能据此自动连接。B/C各自硬件状态不得在审批前改变。

## 开始前必须补齐的独立批准与资料

1. PI批准具体C烧录/恢复次数、B/C冷启动验证、ESP电气隔离/恢复和下述有限云窗。历史ROM机制仍UNRESOLVED，不能用此次安装宣告修复。
2. 新鲜C设备身份与两份独立完整读回：Flash `0x08000000` 长1048576B；options `0x1FFFC000` 长16B；实际UID/容量/保护、PC/VTOR/DHCSR、复位与Fault状态。原件受限EFS，禁止打印凭据。ROM、HALT或异常复位立即停，不解保护、不强设PC/MSP/VTOR。
3. 明确C供电与ESP电源/串口隔离方式。恢复原H3镜像期间ESP必须保持电气隔离，防止旧固件使用旧配置自动访问正式环境；只在新B5已确认DISARMED且测试配置核验后，才按单独批准恢复ESP。麦克风、TTS、人体和A段均断开。
4. 独立云测试身份、ACL与接收端。C固定 `GW-B5-001`、Client ID `b5-c-isolated`、发布角色 `b5-gateway`，使用现有8883/TLS；不得重开8884、复用正式Gateway身份或改正式服务环境。由PI确定专用测试Backend/WSS入口和允许来源，Backend白名单含GW-B5-001，七页Web显式选择该身份。所有地址、口令、CA/访问令牌由仓库外受限配置提供，本文不填写真实值。
5. **sector3测试配置包单独审批。** 冻结原件的H3记录CRC有效，但身份不匹配B5；新固件将拒绝联网。需要专用336B H3提交记录、generation、CRC和整sector3旧原件及读回SHA。现有B5应用安装工具明确不写sector3；配置写入不包含在应用安装卡内。sector7/11、options不得改变或用于回退取配置。配置改变后，必须按新鲜全片重算安装/恢复manifest和完整Flash预期SHA，不能继续使用上述历史布局包预期值。

本地TLS Broker/Backend/WSS与浏览器验证已完成，不能替代这里的真实云账户、ACL、订阅和部署审批。

## 电气与输入冻结

- 首轮仅B CAN1↔C CAN2，CAN_H↔CAN_H、CAN_L↔CAN_L，独立参考GND；A段物理断开，无三段并联。历史断电终端60.8Ω为既有记录，下一轮若要求复测，另批断电测量，不在带电网络上用欧姆档。
- B P6：CAN_RX↔PA11、CAN_TX↔PA12，USB D+/D−选择断开。C P4：CAN2_RX↔PB12、CAN2_TX↔PB13；不得误把RX/TX互短。两路控制器/收发器供电、参考地与500kbps再作现场核对。CAN2共享CAN1时钟/过滤器不等于允许A段工作，候选CAN1静默、A滤波器关闭且禁止A段软件发送。
- 首轮普通ECG60bpm/1.0mV，电池且充电USB断开；红R→RA、黄L→LA、绿F→RL/N，LL空置。无人体、无LL/RL短接、无主动RLD接地。目标HR58–62bpm；RR与TEMP必须如实INVALID。此前独立RR15为另一模式/接线的通过证据，不混入本窗。
- 第二个RR15云窗如需开展，须另批冷态换线、源模式、C新启动与独立窗；不能在本卡首窗内自动切源、换导联或合并签双通道同步PASS。

## 应用安装/恢复动作上限（尚未授权）

新鲜备份和身份/运行门禁通过后，拟按“恢复原H3→安装B5→恢复原H3→重装B5”四个独立事务验收；各阶段仅应用sector0/1/2（旧24104→H3可使用已核对的旧范围恢复包），每事务连接一次，halt/download/reset/go各至多1、180秒总限；失败即停，无自动回滚或重试。新scope为 `B5_C_SECTOR012_MOCK_INSTALL_OR_RESTORE_NO_CONFIG_WRITE`，要求C角色、nonhuman_mock=true及重新冻结的工具/包/SHA；默认禁用。旧B4 C卡仍拒绝sector2写入。

每次都核对完整1MiB、应用尾部、sector3/7/11、options、身份及真实Flash启动；不能只比较BIN前缀。B不烧录、不复位，保持算法阈值、ADC寄存器与250SPS采样。新B5的实际恢复演练尚未执行，不能沿用C24104B演练签PASS。

## 真实云窗（须另行批准后才开始）

1. 本地原码、C USB诊断、Broker订阅观察、Backend接受日志、浏览器WSS观察先就绪；所有日志注明非人体MOCK、source/session/boot、工具SHA与真实退出码。串口先禁DTR/RTS再打开；异常停，不用串口下载或改变BOOT。
2. C启动应只显示 `B5 DISARMED MOCK B_ONLY NO_FLASH_WRITE`，不得自动入网或发送CANopen心跳/TIME。当前配置与专用身份均核验后，才由负责人明确允许发送完整 `B5START\n` 一次。无二次命令、自动重武装或无限复位。
3. 从武装起固件420000ms硬停。最多60秒取得本轮新鲜SNTP、Broker CONNECT/SUBACK、Backend接受及首个Web快照证据；超时停。以该次首次端到端就绪T0冻结：45秒预热、300秒共同评价、至少15秒尾段；若准备提前完成，剩余时间仅记录至420秒硬停，不扩展共同评价，不能采后换窗或剔除失败段。T0最晚武装+60秒，保证总限内完成。
4. 评价至少覆盖：B实际约250SPS原码/序号/ADC错误/队列expired；C CAN2 NMT、HB、TIME、真实TXOK、TEC/REC/BOFF、RX与UART溢出；ECG250SPS每100点、RESP50SPS每50点的源UTC、会话与序列；C队列积压/过期/丢弃和重连；HR有效/RR无效、TEMP无效；各层MOCK/synthetic和A段OFFLINE。300秒名义ECG目标约75000点/750整批，边缘不足整批不得补点；判据以真实源域、固定共同窗及完整接受记录解释。
5. 分层裁定：CAN ACK只证明总线；C的q0_transport只证明QoS0字节发送；q1_puback只证明匹配Broker PUBACK。必须分别取得Broker实收、Backend模型接受、浏览器WSS内容匹配，才称上云链路通过。不能把三种确认替换为后两层证据。
6. INVALID、STALE、断链/重连与会话更新对照需在审批中冻结次数和故障方式。只允许专用测试连接/服务，不停止正式Broker或防火墙；普通断链恢复也不能冒充受控CAN故障注入恢复通过。

立即停止条件：任板ROM/HALT/意外复位；Flash/options/身份漂移；接线、电源、源隔离异常；CAN BOFF、发送失败、RX/UART溢出；配置/来源串位、MOCK被标LIVE、错误Gateway/Topic、非批准云写入；日志缺失、未按限时停止。固件直接处理自身CAN/UART/时限条件；外部观察条件由操作人关闭专属测试连接并执行事先绑定的C/ESP停机方式，不通过复位或重刷掩盖。当前供电/USB状态与停机动作未现场冻结前不得开始。生理输入失效必须保留原码和INVALID，不能靠降阈值、改寄存器或重刷掩盖。

硬停后禁止继续发送业务与自动重连，取消CAN邮箱且保留共享时钟/ACK；仅允许有界CIPCLOSE清理（至多2秒），Broker离线/遗嘱与Backend/Web状态继续取证。恢复原H3及原sector3配置须在ESP隔离和单独恢复批准下执行，读回完整恢复SHA并确认sector7/11/options不变；恢复正式联网不随镜像恢复自动获得许可。

本卡当前执行次数：**0**。不具备真实云准入PASS，等待PI审批与缺口补证。
