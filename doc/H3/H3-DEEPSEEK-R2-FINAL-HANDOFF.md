# H3-R2 工程收口与现场准入交接

本轮合同：MPM-H3-002 R1.0；执行者为 Codex。沿用合同指定的唯一文件名，不代表执行者变更为 DeepSeek。用户已排除第八节 ECG 采购和选型，本轮没有执行该支线。

**阶段结论：H3_PARTIAL_CONTINUE。C 的一次正常BOOT、J5独立供电/USB拔除及Flash配置保留窗口已经实测通过（连续在线310.045秒，见第10节）；负责人指定改接2.4GHz路由器，generation2配置及sector3专用更新工具已准备、联合236项回归通过，实板换网待现场窗口（第11节）。NIBP_PENDING；FORMAL_RELEASE_NOT_AUTHORIZED；FORMAL_ROLLBACK_NOT_RUN。** 不宣告整体 H3_PASS、七页正式上线或生理准确性通过。

## 1. Git、镜像及现场身份

工作区 `E:/medical-monitor-h3`，仅使用 `dev/h3-nodea-cloud-ai-integration`。接管时本地/远端均为 `74d12a27425cdba6de18a833af86aa2087ee9c8a`。

**固件候选源码、最初编译及180项测试证据提交：`b57f5464391174ca2bf45d0ed3453bd1cfe42093`。** 首次交接提交为`ed86bf6effaa56c59e81088ea7871c7a05d85bba`。负责人接受存储策略后新增的离线封装/下载工具和211项回归见第9节，不改变上述固件源码或镜像。包含本文件的最新交付提交可用 `git log -1 --format=%H -- doc/H3/H3-DEEPSEEK-R2-FINAL-HANDOFF.md` 取得，最终完整 HEAD 和实际 push 结果在交付消息中列明。本文件不虚构包含自身的预知 SHA。

| 保护分支 | 重新查询到的远端 SHA |
|---|---|
| A | `3fa14b00a0823d2855e9dd8bd1c6c8545abb8dc5` |
| P6 | `77dd14d1ca761a488956f7a4ebf28cb3174835e4` |
| P4 | `67f5f57bd82c6e326e9e78ec9540481c80105e5f` |
| main | `50699048010c57ba10f8573461844c525b022a07` |

未创建 PR、合并、强推或执行正式 Security Gate。原有未跟踪根目录 `build/` 保留、不提交，因此不能声称整个工作区毫无未跟踪文件。已有疑似并行生成的未提交审计文件仅按用户指令移出工作区，原件在受限目录保留，SHA256 `011227e31e4e0d4358cda065adf51ef74c4b40b593a54826434ca3c0d9b3f6f1`；没有杀其他窗口或覆盖用户构建目录。

| 镜像身份 | 字节数 | SHA256 | 实际状态 |
|---|---:|---|---|
| C 窗口前旧镜像，源码 `ec044cc3e1887f7fd7812d6fd60b06a49d92f5ae` | 42728 | `c3bc10c6bb01831fb7c1f7a44dabb5fc0295fa667045a5428856bd6991250b6f` | 新窗口备份时实际核对；原件保存在受限目录 |
| C 隔离持久配置镜像 | 43172 | `59229f1b34660f053538737fc0fd17c814fde5502a0dfe33603e8e08b72ca8a5` | 第10节已实际下载、读回并独立冷启动 |
| C 新正常端口持久配置候选 | 43184 | `9df43acd34732cacb8c1a90a6a15e420b96ad9675a004d65c3a088246268f977` | 仅构建；未下载/连接正式Broker |
| A 新完成时间扩展候选 | 50084 | `f59b76ef865c373c6df62aa09aea958597687f6d46b17c402ceb7126ca8f60d6` | Keil/FromELF通过；未下载 |

候选镜像对应本轮代码提交；精确编译文件摘要、命令、向量、装载区间见 `gateway/physical_can/evidence/h3-r2/persistent-*/` 和 `node-a-arm-image.json`。最终文档提交不改变固件源码。

初审时反馈为A断电/J-Link拔下、C USB/COM15供电、下载BOOT接线，初审未操作板卡。第10节记录负责人随后明确批准的实板窗口；窗口结束时**C B0=GND/B1=GND、J5独立供电且USB已拔，A独立供电/J-Link拔下，CAN线不变**。不再用初审RAM会话状态代替最新实板结论。

## 2. Gate 裁定

| Gate | 结果 | 边界 |
|---|---|---|
| R2-0 | PARTIAL：代码/正式服务及C身份读回通过 | 初审与实板窗口分开；云安全组仍未用API独立验证 |
| R2-1 软件 | PASS / BENCH_STORAGE_POLICY_ACCEPTED | 两种ARM、记录损坏/重载/闭锁Host及受限下载事务通过；Flash物理保密性未具备 |
| R2-1 实板 | PASS_ONE_AUTHORIZED_COLD_BOOT_WINDOW | 双备份、sector3写入读回、正常BOOT及310.045秒通过；坏配置实板/重复冷启动仍未测 |
| R2-2 软件 | PASS | 真实Node-A CANopen代码→Gateway→Backend→AI的合成协议字节及浏览器90秒过期通过 |
| R2-2 新信号源 | NIBP_PENDING | 没有新的合格血压源；未采集人体或上传新生理记录 |
| R2-3 新实板稳定/故障窗口 | NOT_AUTHORIZED / NOT_RUN | 不把历史无探头网络回归或本地MOCK当本轮有源300秒验收 |
| R2-4 本地七页/前缀 | PASS | HTTPS等效入口、WSS、桌面/移动截图20项；服务器内存候选nginx -t退出0 |
| R2-4 完整正式准备单 | PARTIAL / REPREPARE_REQUIRED | 新正式MQTT只读身份、完整受限备份及新的不可变候选目录未生成 |
| R2-5 | FORMAL_RELEASE_NOT_AUTHORIZED | activate、真实rollback及公网复验全部NOT_RUN |
| 第八节 | EXCLUDED | 用户已完成选型，不新增采购建议或B操作 |

## 3. 修改范围及持久配置方案

修改限于Node-A血压完成身份/对象字典、物理Gateway的NIBP采集时间还原、显式候选配置profile、功能夹具、只读核对与发布准备工具。没有迁移框架、改动第三方CANopenNode/coreMQTT、增加RTOS、麦克风或真实TTS路径。原Wi-Fi/ESP-AT/TLS及QoS1/PUBACK五秒预算保留，Node-B始终OFFLINE。

新配置profile默认关闭，通过 `--persistent-config --irq --fresh-sntp` 显式选择；隔离版本另加 `--isolated`。应用装载限sector0–2，不含配置段；链接断言禁止进入sector3。sector3提议保存336B记录（24B头+原312B结构）：版本、代次、CRC32、最后提交字；无效/缺失记录失败闭锁，不回退RAM或sector11。运行固件没有Flash写入口，不会在启动/重连时磨损Flash。**CRC不是加密、认证或物理读出保护。** ARK密钥不进入设备结构。

| 扇区 | 地址（右端不包含） | 擦除大小 | 本轮方案 |
|---|---|---:|---|
| 0 / 1 / 2 | `08000000–08004000` / `08004000–08008000` / `08008000–0800C000` | 各16KiB | C应用 |
| 3 | `0800C000–08010000` | 16KiB | 新配置，尚未授权写入 |
| 4 | `08010000–08020000` | 64KiB | 未使用且未确认擦除状态 |
| 5 / 6 | `08020000–08040000` / `08040000–08060000` | 各128KiB | 不动 |
| 7 | `08060000–08080000` | 128KiB | 严格保护 |
| 8 / 9 / 10 | `08080000–080A0000` / `080A0000–080C0000` / `080C0000–080E0000` | 各128KiB | 不动 |
| 11 | `080E0000–08100000` | 128KiB | 严格保护 |

按STM32F407ZGT6的1MiB设计，实际容量本轮未再读取。ST DS8626 Rev12 Table42列明指定温度条件下Flash最低10000次擦除寿命；这不是当前器件磨损实测。参考：<https://www.st.com/resource/en/datasheet/stm32f407vg.pdf>。

外部安全存储尚无已确认器件/驱动；sector3方案只适用于负责人接受**芯片可读的、可撤销且权限受限的台架Wi-Fi/MQTT凭据**。负责人已在后续答复中明确接受该方案。RAM方案仍可作为台架，不算持久交付。完整比较、记录结构、断电失败处理、擦除粒度和准入在 `H3-R2-1-CONFIG-PLAN.json`；该原始设计回执保留初审时待接受状态。接受后仅在仓库外生成一份336B候选记录（第9节），没有Flash写入，也没有绕用旧RAM下载工具写新profile。

回滚必须先备份实际C sector0–3的64KiB原件、至少两次一致SHA，再核对sector7/11/options；失败按同一授权窗口恢复原件。旧正常固件读sector11且此前为空，**不能承诺恢复旧固件后可独立联网**。旧隔离镜像+RAM恢复只代表显式台架会话。

资源：C隔离候选比既有42728B镜像增加444B；正常候选43184B。隔离text43076/data88/bss123136，正常text43088/data88/bss123136，RAM链接占用不变。bss包含链接脚本预留的堆/栈区；128KiB普通SRAM扣除data+bss另余7848B未占链接区，这不是实测栈余量，未做真机栈水位测量。配置独占sector3的16KiB擦除单元，实际记录336B。A Keil：Code46488/RO3108/RW1560/ZI15616；BIN50084B，比此前49888B增196B。A候选占sector0–3，和C配置sector3是不同板卡的范围，禁止混用下载计划。

## 4. NIBP 从完成时刻起算

发现旧Gateway把周期性TIME锚当成NIBP采集时间；旧值每两秒上报会看起来像新测量。Node-A虽已有90秒源端检查，仍需把完成时间传播到云端。

修复：Node-A成功结果增加非零generation，保留完成tick；利用原保留的TPDO2 `0x281` 发送新对象 `0x2111`（完成tick + SYS/DIA镜像），质量bit9标识扩展版本。原`0x181/0x381/0x481/0x681`及周期不降频。Gateway要求扩展新鲜、SYS/DIA镜像一致，并按TIME锚还原完成UTC。只有NIBP按90秒门限判龄，PPG/其他标量原门限不变。旧A无扩展时明确NIBP INVALID，不能倒退为当前时间。**新A/C需要成对部署后才可做本轮NIBP实板验收。**

源端加入中止/过期锁存，通信复位、返回IDLE、tick回绕不能复活旧结果；同值的新测量仍可凭新generation进入。保留已有屏幕、传感器采集流程；本轮仅离线编译，双屏实物没有新增观察。

协议夹具不是手工伪造最终JSON：实际Node-A CANopen发送字节进入实际Gateway栈/Adapter/Router格式化，再用Backend解码/Hub和AI事实层验证，明确MOCK。完成UTC不随重复上报刷新，90.001秒后STALE且AI无当前值；缺扩展、错配、未来时间、源质量和旧协议均覆盖。浏览器另等真实90.25秒验证相同结果。

R3的历史实测、旧人体来源记录仍仅追溯。本轮未填充新实测数值，不作精度结论；新物理NIBP保持PENDING。

## 5. 原始命令、退出码及失败

下表工作目录为 `E:/medical-monitor-h3`，Python使用UTF-8。完整参数、编译源摘要和原始输出在 `gateway/physical_can/evidence/h3-r2/`、`node-a/evidence/h3-r2-*`；未执行硬件。

| 命令/检查 | 退出码 | 结果 |
|---|---:|---|
| `python -m cloud.deploy.h3.r2_audit` | 0 | 只读身份冻结；首次审计前源码与历史实机编译输入一致 |
| `python gateway/physical_can/build.py --irq --isolated --fresh-sntp --persistent-config` | 0 | 新隔离ARM |
| `python gateway/physical_can/build.py --irq --fresh-sntp --persistent-config` | 0 | 新正常端口ARM，仅构建 |
| `python node-a/tests/run_host.py --phase h3-r2-final` | 0/0 | 编译/执行 |
| Keil `UV4.exe -r …uvprojx -o …node-a-keil-build.log` | 0 | 0错误0警告 |
| FromELF `--bin --output node-a/build/h3-r2-node-a.bin …axf` | 0 | 镜像身份单独冻结 |
| `python gateway/mqtt/tests/run_p5_host_tests.py` | 0 | 42项 |
| 同命令加 `--network-irq --fresh-sntp` | 0 | 46项 |
| `python gateway/physical_can/build.py --host --irq` | 0 | 协议、缺席B、过期、重启 |
| 同命令加 `--rx-order` | 0 | IRQ及100ms前台停顿 |
| 同命令加 `--peer-cycle` | 0 | ACK-only恢复、心跳门禁、硬故障锁存及掉电 |
| `python -m pytest cloud/backend/tests cloud/ai/tests gateway/physical_can/tests -q` | 0 | 最终180 passed、4 subtests；此前170/178项原件保留 |
| `npm --prefix cloud/web test` / `npm --prefix cloud/web run build` | 0 / 0 | 15项Web检查、TypeScript/Vite |
| `python cloud/web/tests/run_r2_browser.py` | 0 | 最后一次20项、实际90.25秒；自有进程和证书清理完成 |
| `python -m cloud.deploy.h3.r2_preflight` | 0 | 最新内存候选nginx -t、正式身份不变；没有prepare/activate |
| Python语法编译、Git源码空白检查 | 0 | 原始证据日志不归一化、不删末尾空行 |

失败没有被替换：NIBP修前pytest退出1、夹具7；两次Node-A对象字典初始化逗号编译1；独立wire夹具模块路径失败1；首轮浏览器MOCK标签断言失败1；只读预检缺全局json导入失败1；Nginx从不可seek的pipe解析失败1，改为内存memfd后退出0。详见 `failure-register.json`，含哪些首次输出仅留在工具会话、未另存完整原件。最早预检五槽窄正则false也未冒充无上限证明，后续AST查实 `range(1,6)`。

Git对原始Windows日志的CRCRLF/编译器末尾空格检查有提示，保留原始字节；源码（排除证据目录）空白检查通过，不把整库raw-log空白检查写成零告警。

## 6. 分层证据、浏览器和AI账本

| 层 | 本轮证据 | 未证明部分 |
|---|---|---|
| A CANopen→C Router | 实际代码Host字节、完成时间及过期；IRQ/掉电回归0 | 未烧录新A/C，无新实物CAN计数 |
| ESP/TLS/MQTT | P5原行为42/46项；两种联网ARM | 无本轮真实QoS0/QoS1、PUBACK、Broker/丢包增量 |
| Broker/Backend | 正式8883进程只读身份；本地真实Hub解码合成CAN JSON | 无本轮设备→隔离Broker有源300秒 |
| WSS/Web/AI | 本地真实Backend/AI应用，MOCK供数，HTTPS/WSS七页20项 | 无本轮正式HTTPS上线或真实模型调用 |

历史故障窗口仅历史：UART329.234s/PUBACK增加693；WSS320.052s A ONLINE/B OFFLINE；隔离单连接丢包6.002s、3包/783B，同次启动恢复。证据仍在旧 `mqtt-interruption-fix/`，不是新profile通过。MID1430/MID790因果差异不改；支持传输路径/无线延迟，未证明路由器硬件为唯一根因。本轮不继续无界网络诊断、不改5秒预算、不清零缺陷计数。

截图均标明本地测试，未使用人体读数：

![桌面AI合成测试](../../cloud/evidence/h3-r2/browser/ai-desktop-valid.png)

![移动AI合成测试](../../cloud/evidence/h3-r2/browser/ai-mobile-valid.png)

![90秒过期后当前值失效](../../cloud/evidence/h3-r2/browser/ai-desktop-expired.png)

七页overview/temp/ecg/spo2/resp/nibp/ai、独立浏览器AI令牌、AI鉴权失败不破坏监护、刷新清除令牌、移动无横向溢出均通过。端口仅loopback18765/18766/18767，自签名证书仅用于该入口，未修改系统信任、共享浏览器或正式TLS。

本轮真实豆包调用0、Token0，费用未新增且未查账户余额；历史10次/7496 Token原账保留，不能推定剩余免费额度。H3候选移除了五槽累计上限，仍有持久流水/并发/速率/预算授权/错误熔断及禁止自动重试。本轮DOUBAO真实服务没有切换。确定性读数标NOT_CALLED，MOCK一般解释不能标REAL_REQUEST_USED；不向模型发送原始波形、身份或完整聊天史。

## 7. 正式服务只读结果及发布审查包

| 正式运行对象 | PID | 实际工作目录/可执行文件 |
|---|---:|---|
| Backend `medical-monitor.service` | 845095 | `/opt/medical-monitor/releases/mqtt-v07-phase2-20260920-01/backend` / python3.12 |
| MQTT单元 `medical-monitor-mqtt.service` | 851111 | `/` / python3.12；实际8883 mosquitto子进程851112 |
| AI `p6-ai.service` | 394625 | `/opt/medical-monitor-p6` / python3.12 |
| Nginx | 3631 | `/` / nginx |

初审与收尾正式PID、CWD/executable、原配置散列和Web index均未变。业务Broker在`medical-monitor-mqtt.service`内；默认`mosquitto.service` inactive不代表正式Broker停机。8883监听存在，8884当前无监听；全IPv4安全组规则仍按负责人反馈保留，不代表主机监听或云规则已撤销。

旧正式AI `providers.py` SHA256 `40741521f34feaf3467d8d8bf7928342a36fbe2db463d99dc63b5715406140f6`，查实仍有五槽；未启动或调用该服务。此前三个runtime目录和旧 `20261020T034945Z/plan.json` 仅PREPARED_ONLY_NOT_PUBLISHED，不能作为R2部署完成。

发布代码修复：正式prepare必须显式输入外部0600正式只读角色MQTT8883配置，不能继承隔离8884；正式独立client_id；schema2拒绝旧准备单；健康要求Backend真正MQTT连接、AI DOUBAO/MONITOR；所有unit先校验再安装，部分复制失败也进入清理。purpose标识不是实际ACL已验证。11项本地发布失败保护测试通过，但activate重复执行目前是原路由hash不符后闭锁，并非幂等成功；不得无脑重跑。

候选路径：`/medical-monitor/#/ai`；AI `/medical-monitor/ai/*`完整保留给AI上游；API/WSS剥离项目前缀给Backend。本地等效HTTPS通过；新候选Nginx配置在服务器内存memfd执行`nginx -t`退出0，未reload、开监听或写正式配置。测试alias指向待重新prepare目录，不是已有可访问站点。

完整新正式prepare仍待：批准MQTT实际只读ACL/客户端、冻结新runtime源与静态散列、完整受限Web树/Backend/AI源码及所有unit/env/Nginx备份与权限、独立候选配置审查。旧prepare只备份四个配置文件和Web路径/index，不能把它当作全套原件备份。文件传输遵循E:/Server_file暂存→服务器SHA核验→仅删除自有暂存，本轮未上传。

新正式地址：**未发布**；原地址不变，仍由负责人本机受限生产配置管理。仓库不写真实主机或连接信息；原站点不能冒充新H3公网验收。正式activate/rollback、rollback后公网HTTPS复验均NOT_RUN；没有更改腾讯云、主机防火墙、ACL或正式站点。

## 8. 待负责人裁定的准确范围

合同第1节明确“任何…Flash擦写…写入持久密钥/配置或新增Flash扇区”须另行授权，第11节及最终签发裁定重复此门禁；第3.2标题“无需单独授权”与其冲突，本轮依授权矩阵和最终裁定停在现场门，不自行认定全硬件授权。

1. **配置存储策略已接受**：负责人明确答复“接受 sector3 台架方案”，此前问题限定仅选择方案，不含烧录。当前方案不能作为密钥物理保密方案；本项不再重复征询。
2. 若接受，批准单次C窗口：只读实际容量/镜像、备份实际sector0–3原件两次SHA；保护7/11/options；仅sector0–2写上述隔离候选，sector3另经批准写固定336B配置（擦除单位16KiB、commit最后）；按正常BOOT、独立供电并去除USB/宿主辅助验300秒。精确配置摘要和受限下载工具必须在真正写入前冻结；现有RAM工具不能绕过新布局门禁。
3. A候选若需配对验NIBP：另列A角色、50084B镜像和sector0–3写入范围，使用既有完整备份并核对当前原件，保持传感器/双屏功能。未给新的合格非人体源仍NIBP_PENDING；人体数据另需来源、最小上传及受众范围批准。
4. 同源码/镜像/配置下新有源300秒及单次隔离网络故障恢复，需要批准精确电源/BOOT/接线动作和隔离单连接故障窗口；分层统计FIFO、队列、Router、UART/Host、QoS0/QoS1、PUBACK、Broker、Backend及WSS，不能继承旧无探头结果。
5. TCP8884云规则准确待处理目标：仅负责人指认实例上“全部IPv4→TCP8884”规则；删除或换成现场出口/32均属公网范围调整，尚未执行。8883等原规则不在目标内。
6. 正式发布/真实回滚另待单次窗口，先补齐上节prepare缺口、确认受众/数据范围及原件。不能仅凭本次通用合同授权执行activate。

上列待授权项记录初次收口时的范围；C单次窗口随后已批准并按第10节完成。其余A新镜像/NIBP源/网络故障注入/正式发布没有自动扩展授权，不需要再拆新合同。

## 9. 存储策略接受后的下载准备（仍未操作板卡）

新增`gateway/physical_can/r2_config_record.py`，将既有312B配置封装为版本1、generation1的336B记录。只读取受限目录内与上次C隔离下载回执配置SHA完全一致的原件，不打印字段、不改变Wi-Fi或MQTT角色；新记录仅在原受限目录独占创建，不进入Git。CRC/布局用实际C固件验证器交叉检查。接受存储策略不是新建/更改服务器凭据、ACL或正式端口授权。

冻结配置SHA256：**`5c22cee1d7978faec50ea5431f749b36ac1ea01de52742342317e91a08a3ce18`**，336B。配对隔离应用仍为43172B、`59229f1b34660f053538737fc0fd17c814fde5502a0dfe33603e8e08b72ca8a5`。身份源SHA（无UID正文）、原312B配置摘要和完整范围见 `gateway/physical_can/evidence/h3-r2/persistence-tool/offline-plan.json`。该回执`hardware_accessed=false`、`flash_written=false`、`owner_hardware_window=NOT_GRANTED`；生成私有文件不是实板持久性通过。

新增`gateway/physical_can/r2_flash_c.py`，以`python -m gateway.physical_can.r2_flash_c`调用：

- 默认`--action plan`只读文件并生成脱敏范围，不导入串口；`backup/program/restore`必须有外部负责人窗口记录、固定C/COM15、当前源码SHA、应用/配置SHA、身份源SHA、8884范围及有效期。窗口文件仅记录已经获得的许可，不能替代会话授权。
- 仅接收明确的8884/MOCK持久配置IRQ候选，拒绝8883/旧RAM布局；执行前复核所有固件输入及外部SDK摘要、版本固定的stm32loader0.7.1，实际C身份/1MiB容量。SDK路径由外部参数给出，不复制SDK。
- `backup`与旧C应用/配置保护回执匹配后，实际读取sector0–3共65536B两次，保护7/11/options前后不变，再在受限目录独占保存两份原件并从磁盘回读。任一步失败都不产生可用backup证明。
- `program`重新核对完整64KiB原件；先只擦sector0–2并写应用，核对整应用区；再只擦sector3，先写头/CRC与payload、保持commit字擦除态，核对整个16KiB后最后写commit四字节。最终核对全64KiB、保护7/11及options。不写RAM、不调用GO、不自动重试；后续仅在已批准C窗口显式使用`--reset-c`进行ROM复位，不把它算作正常冷启动。
- `restore`只接受该C窗口的两份一致原件、当前完整64KiB已知摘要及不变保护区/options；仅恢复sector0–3并完整读回。保护不符立即停止，不能以“回滚”为由扩大写入。恢复旧RAM固件仍不能证明独立联网。

新增31项下载/封装功能检查全部通过；联合Backend/AI/物理Gateway套件**211 passed，4 subtests passed，退出0**，原始命令/日志/工具字节摘要在`persistence-tool/functional-result.json`及`functional.log`。覆盖C验证器与Python封装互认、错误镜像/IRQ/范围/旧RAM/正常端口、双读不一致、写前门禁、应用/配置读回故障停止、提交标记最后写、保护变化时禁止继续、完整原件恢复、过期/错板/错配置窗口以及无窗口不打开串口。未重复ARM构建，因为固件输入未修改；原ARM镜像和证据保留。

**本次请求的单次C现场窗口**：批准上述镜像+336B配置；先备份C sector0–3并核对7/11/options，再仅写C sector0–3及读回；允许C在完全断电时将BOOT0从3.3V改接GND，BOOT1保持GND，并以原核验独立电源冷启动，去除USB/宿主辅助后观察至少300秒。当前BOOT0接3.3V仍是下载模式，尚未更改。A需恢复其原独立供电以提供心跳，J-Link仍拔下、探头/袖带不接。需启动临时8884隔离服务并在主机仅允许现场出口/32，测试后停止服务/清理本次主机规则；不改云安全组、8883生产服务或正式页面。若仅批准下载、不批准网络/电源窗口，只能报告写入读回，不能报独立冷启动联网通过。

上述段落是首次提请窗口的方案。负责人随后明确批准该单次C窗口，实际执行、失败原件和清理结果如下。A新固件、NIBP实源、有源300秒、网络故障注入和正式发布仍按第8节各自范围待审，不包含在本次C窗口中。

## 10. 已批准C独立冷启动窗口的实际结果

负责人明确批准第9节单次C窗口，并先后配合C手动复位、USB重新插拔、热点开启/电脑连接。下载完成后，负责人确认**C由J5独立供电、USB已拔，A已上电**，按已完成请求B0=GND/B1=GND、A J-Link保持拔下、无人连接探头/袖带。无需逐项照片。正常从Flash启动的证据来自该次真正断电后的独立运行，不是此前的ROM GO、RAM注入或调试器设PC/MSP/VTOR。

| 实际检查 | 结果 |
|---|---|
| C ROM型号/1MiB/外部身份比对 | 通过；不记录UID正文 |
| 当前sector0–3原件双读及磁盘回读 | 65536B一致，SHA256 `54f724fab2e74d00c864afb32a0e1a4f8bf8fd86f51ef6ebb9da4d038c37b817`；两份原件仅在本机受限目录 |
| 固件构建/下载工具身份 | 固件输入冻结于`b57f5464391174ca2bf45d0ed3453bd1cfe42093`，下载时HEAD `9ded93f58e12913b8fdef9b9ce989302399e9355`；期间只修Host下载工具，应用/配置SHA不变 |
| 实际擦写 | C sector0–2应用；sector3配置，commit最后写；不全片擦除、不写RAM、不GO |
| 应用/配置/完整64KiB读回 | 退出0；完整新64KiB SHA256 `52a4c9d621375d63cd995c1a003d98473e9be3387d31cd857e702a27bee7e6f8` |
| sector7/11 | 前后均为SHA256 `b5a41c3758763bbec72769fab4a2533bf2db0b6312d93d25a695f9e4b9e02260` |
| 选项字节 | 前后SHA256 `52d5979da03bd7be45e385920ec7d5901793bab3f6bc1daa0c1c1997f9e91687`，未写入 |
| 无宿主独立冷启动及配置保留 | 单次实测通过，连续A/Gateway ONLINE **310.045秒**，Node-B全程OFFLINE |
| MQTT订阅端/Backend | 654条、全部接收QoS1；Backend accepted增加654、rejected增加0、dropped增加0；MQTT解码错误0 |
| WSS | 含上电前等待共6272份快照；无效值可见次数0，B上线次数0 |
| 本轮新生理输入 | 无；SPO2/PR/NIBP各155次状态报告不是155次有效测量；PPG/QoS0波形数为0，NIBP仍PENDING |

首个全ONLINE状态约为北京时间2026-10-20 18:52:57，连续观测完成约18:58:07。观察器在现场上电前已启动，前322.049秒包括人工等待及准备，**不能把它当作C启动耗时**。会话`can-1792493535-65538`在新隔离Broker/Backend（初始accepted=0）内实际产生。TLS校验、真实MQTT鉴权、CAN来源状态及Backend时间门禁通过支持独立联网结论；USB拔除期间没有C UART，因此**没有直接测量C的FOVR/软件队列/Router/Host丢失或PUBACK计数**，654条订阅接收不能代替C的PUBACK数。

临时Backend使用`runtime-37808287a557`，来源清单提交`41ddc066b92ccdb46b6ecd442d669a9d1db26b14`。启动前核对完整关键清单，并逐一证明其Backend应用源码与当前分支一致；不把目录名当版本证明。观测代码通过SSH stdin在内存执行，未上传新候选或改正式路由。只启Broker/Backend，不启动AI；本窗口真实豆包调用0。

临时公网仅IPv4 8884、现场单个/32与本机环回，其他来源DROP；没有放开所有IPv4。第一次Backend因通过公网地址回连本机而未就绪，失败清理成功；随后增加仅服务UID、原Broker目标IP及8884端口的临时本机DNAT，TLS仍验证原host，不影响8883，Backend恢复。电脑侧一次8884 TLS预检Timeout仍保留，不宣称已定位电脑出口差异；随后C实际连通，未为此扩大/32范围。云安全组宽8884规则依旧为负责人反馈保留，本窗口未修改云规则。

停止回执退出0：本次Broker/Backend及到期定时器停止、临时INPUT/NAT链撤销、INPUT及NAT规则SHA恢复、三份自有临时配置删除。8884/18775已无监听，正式8883仍在；正式Backend/MQTT/AI/Nginx PID及原配置/Web/AI源码与窗口前一致。电脑已由负责人切回原Wi-Fi。C保持正常BOOT与Flash配置；临时Broker停止后，其测试目标不再提供云服务，**不等于正式常驻上线**。

保留的失败：本地编排导入路径失败1（未操作板卡）；5次ROM握手失败退出1且`flash_write_started=false`；稳定等待修复未单独解决握手，实际采用一次受控C ROM复位后才完成备份，并为重开串口增加显式受限`--reset-c`。针对性检查从31→32→33项，最终联合**213 passed、4 subtests passed、退出0**。临时Backend首次启动失败及PC TLS Timeout也保留，未覆盖原件。

全部证据在`gateway/physical_can/evidence/h3-r2/c-window/`：`hardware-assessment.json`、`program-*.json`、`controlled-rom-backup-*.json`、`cold-observer-result.json`、654行`cold-mqtt-metadata.jsonl`（SHA256 `4096582226e5b49de04f0c605e30c440152004945f9f2703c487a19e765b2235`）、`isolation-stop-*.json`及前后身份核对。公开记录不含配置正文、Flash原件、UID、真实主机或生理值。操作编排通用源码保存在`operator-tools/`供复核。

坏配置启动仅Host验证，未向实板写故障配置；这是一次成功冷启动，不虚报三次。没有编程后失败，因此未实际调用C原件恢复；没有执行正式activate/rollback或网络故障注入。H3整体仍PARTIAL，后续路由器迁移单独保留配置代次和证据，不覆盖本次热点结果。

## 11. 路由器迁移准备：仅sector3，尚未写板

负责人指定目标`@Tenda_B93620`，复用此前本机受限目录中的私密配置；没有在聊天、命令行或仓库重新写入密码。现有C固件仍是第10节43172B隔离镜像，不重新开发联网固件。当前持久Wi-Fi仍为手机热点，电脑切换网络不会自动改变C。

新记录336B、generation2，SHA256 **`3b1a8c344dfad1d1faa82bc962811e50a467eec9adbc1cec5b2a32979c6a2c25`**；旧generation1记录为`5c22cee1d7978faec50ea5431f749b36ac1ea01de52742342317e91a08a3ce18`。仅替换原312B配置中SSID/密码的两段固定字段；MQTT主机/身份/口令/client_id和授时下限逐字节不变。两份记录仅在本机受限目录，仓库只保存散列。`prepared-plan.json`明确`hardware_accessed=false`、`flash_written=false`，不是实板迁移成功。

`r2_flash_c.py`新增`wifi-plan/wifi-backup/wifi-update/wifi-restore`：

- 默认仍只生成离线计划；Wi-Fi窗口必须单独绑定新旧配置SHA、现有应用SHA、C身份源、COM15、当前工具提交、到期时间以及**仅sector3**。旧允许sector0–3的窗口不能直接用于新操作。
- 换网前重新双读现有64KiB及磁盘回读，要求与当前43172B应用、generation1配置重建的完整摘要`52a4c9d621375d63cd995c1a003d98473e9be3387d31cd857e702a27bee7e6f8`一致；最初42728B旧应用的备份不能冒充这次换网回退原件。
- 只擦sector3的16KiB（0x0800C000–0x0800FFFF），写336B记录、commit最后写；完整应用区0–2仅比较，不发送应用擦写命令。最终核对完整64KiB、sector7/11和options。无RAM注入、无GO，不将ROM复位当独立冷启动。
- 更新中途失败立即停；恢复也仅允许sector3，先双读当前摘要、确认原应用和保护区未变，再恢复本窗口的热点配置并读回。未发生实板失败，目前恢复只在Host模型验证，没有声称实际回滚已执行。

新增23项针对性检查，覆盖只改Wi-Fi/代次、拒绝MQTT或时间字段变化、更新及恢复均无应用擦写、当前应用/备份/保护区异常时不擦除、pending/commit读回失败、失败后恢复、重新双读备份、旧授权范围拒绝、UTF-8字段限长/内嵌NUL/AT转义和离线计划不导入串口。与原33项下载工具检查合计56项通过；Backend/AI/物理Gateway联合**236 passed、4 subtests passed，原始退出码0**。新证据目录`gateway/physical_can/evidence/h3-r2/router-migration/`。本次只改Host配置工具，固件源码/资源/镜像字节均未变，不重复ARM构建。

待现场执行范围已具体化：A/双屏及C先断电、A J-Link保持拔下；C仅USB/COM15下载，B0=3.3V/B1=GND，核验并备份后只更新上述sector3新配置。完成读回后断电把C B0恢复GND、B1保持GND，移除USB、J5独立供电，恢复A原供电；无探头/袖带。临时8884仅现场出口/32及本机环回，独立观察至少300秒后清理；不改云安全组、生产8883、正式页面或A固件。合同第1节和最终授权矩阵要求实际写入前向负责人提供精确范围，原单次热点窗口已结束，不能将其复用为任意配置烧录授权。本轮目标“改接路由器”已明确，不重复征询网络选择，等待该范围的现场就绪回复。
