# PHY01 暂停交接（2026-11-05）

**此暂停已由负责人后续“现在继续”解除。** 本文件保留暂停时快照；后续实际进展和最终留机状态见 [41 Ω最终观察记录](41OHM-RESULTS.md)，不再用本快照中的待处理问题覆盖新证据。

**负责人已明确暂停：** “暂时进度暂停到这里，稍后我通知你继续，保存当前进度，不用提交与push git”。恢复工作必须等负责人通知。只保存本地文件，不再 commit/push，不继续设备连接、查询、烧录、UART 或上电测试。

## 当前进度

- 工程工作树：`E:/medical-monitor-five-node`，分支 `codex/five-node-single-module-v1`。
- 本轮开始 HEAD 为 `f3f4ac9b1cb89ac46bad29dccf7eb21017f96dba`。暂停之前已产生本地 checkpoint `bd1ee2175c98fe20019f889596e8df40e57eec51`，包含 C 诊断入口及首次 60 Ω 结果，尚未推送。B/D 后续资料、D 首写工具和本交接保留在工作区，未提交。不要为了“未提交”表述而自动撤销既有 checkpoint。
- M0 底座标签仍为 `baseline/abc-unified-pre-split-v1` → `26e695ffda43a7a76aa54d1c4e3a5631ac0dc42e`。main、冻结标签未更改。当前各实板程序见下表，不能称作仍全部运行 M0。
- 所有本轮启动的串口与 SDK 会话均已结束，实际回执记录 Close 成功。没有启动云、Broker、Backend、AI/TTS 或浏览器服务。没有调用固定 COM15 的通用 `stm32_console` MCP。

| 实板 | 当前安装 | 写入及核验 | 本轮实际结果 |
|---|---|---|---|
| C | PHY01 专用五节点 CAN2 诊断程序，非完整 M1 网关；boot 392 B、code 24,784 B | sector0/4；安装前身份/全片/Options 匹配，安装后全片及 Options 通过，其余扇区保留；Halt/Reset/Go 各1，WriteMem 2 | 与原 B41516 的 60 Ω、60 s CAN 接收/重建通过；停止后不再主动发送，仍可 ACK。新 M1 B 尚未与 C 复测 |
| B | M1 `FIVE_NODE_B.bin` 40,032 B，Node2，SHA `d0401d96a4a051f964b4d8dce17f7630095ddb5ee8469bc84c3020b828531cd6` | 原 B41516 双读备份及身份匹配；sector0–2 安装、全片/Options/区外保留通过；Halt/Reset/Go/WriteMem 各1 | 15 s 单板只读：26份观察，ADC约250.084 SPS，HR60，相关采集错误增量0。C/D断电，因此不是新 CAN 联动通过 |
| D | M1 `FIVE_NODE_D.bin` 24,544 B，Node4，SHA `a9fb8437adfc5e2dd35e4941688fc84b632651d94bf39c98d42555701984500b` | sector0/1；全片/Options/区外保留通过；Halt/Reset/Go/WriteMem 各1；按负责人决定不另做旧应用备份 | 15 s GY641只读：30份稳定有效观察，新帧67，To 23.23–23.47 ℃，UART/溢出/校验/头错误增量0；**屏幕仍固定36.5，不刷新** |
| A/E | 本轮未处理 | 未连接或刷写 | NOT_RUN |

C 诊断镜像 boot SHA `2ec6c1aacba0f09362d0cc96168fc84082dd4e32d44fed177a8fd0c6b4d9b483`；code SHA `0394d70cdc91824bf28664beebe8cae106e238d54b818f2d8bd66acc26f55bf5`。实际构建目录由本机 pointer 的配置引用，避免误用完整 M1 的 C 镜像。C 诊断 START 等待最多5分钟，START后硬时限60秒；安装后已执行一次 START，无重武装/循环重试。

## 现场与未决问题

1. 最新明确的现场状态为：**仅 D 上电，J-Link 在 D，C/B 断电，D 的 H/L 移开；C2–B1 保持原60 Ω线束。** 随后已请求全部断电检查 P5，但负责人回复暂停，**没有确认已完成断电**。恢复时先确认实际供电/连接状态，不把请求当成已执行事实。
2. C/B/D 收发器实物丝印已由负责人明确确认 TJA1050。各独立口120 Ω、C2–B1约60 Ω可复用前次负责人分测；不要求无意义地重测六个口。
3. 模拟器：非人体 SKX，普通 ECG 60 bpm、1 mV；黄 L 接 LA。保持原 ECG 连接，不推导同窗 RESP/RR 有效。
4. GY641：RC→PC10、TD→PC11、3.3 V、GND。软件 UART4 仅 PC11 接收9600，PC10保持输入；实时源已通过。D 屏是从 B 移来的原屏/整套线，负责人称接 COM2。M0 记录为 USART3 PB10 TX、PB11原回线、115200，现程序只发送。**COM2 是否为板载9针口及 D 的 P5 跳帽尚未获得回答。**
5. D 屏目前不通过。D USART3 寄存器只读确认 PB10 AF7、发送使能、BRR `0x16c`、时基推进，传感器实温与屏36.5不一致。不能据此重刷屏幕固件，也不能将寄存器配置正确写成物理串口波形正确。
6. 参考 `node-b/hardware/STM32F407_原理图.pdf` 第5页：P5针1=T2IN、2=R2OUT、3=USART3_TX、4=USART3_RX、5=GBC_RX、6=GBC_TX。若走板载 USART3 RS232 接口，需要 **1↔3、2↔4** 将 MCU 接入 SP3232。仅为图纸推断，尚未确认 D 实物跳帽；依丝印针1认号，不能按图片左右猜插。P5放大图保存在当前任务的忽略 build 目录。
7. **D CAN 尚未通过，而且末态 ESR 有需核查的异常：** 本地源采集最后一次 `CAN1_ESR=0x44000055`，其中 BOFF 位为1，REC=68、TEC=0。仅有末态快照，未核查来源/时序/恢复过程；不得笼统归为“单板无对端、正常缺ACK”，不得据此进40 Ω。D 当时 H/L未接对端。恢复时还应结合该版本原理图检查 D 的 P6 MCU↔板载CAN1路由跳帽，先做正常60 Ω点对点定位；不能通过Reset/改速率/放宽判据隐藏原失败。当前无后续硬件动作。
8. B单板无上电对端时 ESR 为 `0x00800033`，已原样保存；这不是 T1 同窗错误记录。原 T1 仅 C ESR/接收证据齐备，不能反填 B 或 D 的同期错误为0。

## 测试与进入条件

- 已完成：原 C M0 当前镜像只读匹配；C 诊断安装；原 B41516+C 的 60 Ω、60 s；B 当前应用匹配及 M1 安装、本地 ADC/HR；D M1 安装、本地温度；D 屏寄存器只读。
- T1 原60 Ω结果见 [RESULTS.md](RESULTS.md)、[T1-result.json](T1-result.json)、[T1-signal-summary.json](T1-signal-summary.json) 和 [波形图](T1-ECG-HR.png)。35 s评价内8754个ECG点、35次HR均60，有效位正确，模型值/时戳匹配192次；C观测 TEC/REC峰值0/0、溢出0、ACK128、TX失败0、busoff0，串口CRC/序号缺口/采集丢包0。无示波器差分/眼图，无绝对幅值或临床精度结论。
- 新 M1 B+C 正常60 Ω联动：**NOT_RUN**。此前 B 程序随后改变，需要新版本的定向正常链路验证；不重做全项目旧矩阵。
- D正常60 Ω点对点、屏实时显示：**NOT_RUN / NOT_PASS**，先解决该问题与 D CAN 异常。
- T2新三节点断电40 Ω测量：**NOT_RUN**。T3有人在场一次短时40 Ω观察：**NOT_RUN**。T4恢复60 Ω及最终断电：**NOT_RUN / 未确认**。
- 负责人此前已接受40 Ω超保证负载/样机损坏风险，授权为60 Ω通过后一次人工在场短观察；保留决定，不重复索要。暂停期间不消耗这次预算。恢复后仍需满足当前版本、正常60 Ω、目标状态、电气路线和短时小报文条件。
- **40 Ω专用限时/先小报文策略尚未实现/验证。** 当前仅完成60 s诊断代码，构建器虽然可接受15 s参数，但没有配套 B预操作等源负载限制，不能直接拿 `--bench-seconds 15` 当成已准备好的40 Ω安全窗口。当前 bench init 会发 Node2 OP+TIME，可能立即启动ECG流。继续前需在最小范围内补齐或采用已有合适受限入口，不自动执行满载/长窗或重复40 Ω。

## 本机原件与恢复入口

- 当前任务入口：`E:/medical-monitor-five-node/node-b/build/phy01-current-pointer.json`。
- 该 pointer 的 job 为 `E:/medical-monitor-five-node/node-b/build/phy01-20261105T030640Z`。其中 `runtime-paths-private-local.json` 仅登记 EFS 私有原件路径及本轮配置，不将 UID、全片/Options/端点写入公共文档。
- EFS任务目录含：`C-initial-readonly`、`C-phy60-install`、`C-phy60-UART-idle`、`T1-60ohm`、`B-before-M1`、`B-M1-install`、`B-M1-local15`、`D-M1-install`、`D-M1-local15`、`D-screen-routing-readonly`。源日志、所有成功/失败、父监督器、实际回执均保留，不覆盖或删除。
- job 中保留实际执行的 `inspect_c.py`、`install_c_phy60.py`、`observe_c_phy60.py`、`run_c_phy60.py`、`backup_b_phy01.py`、`install_b_phy01.py`、`observe_b_phy01.py`、`install_d_phy01.py`、`observe_d_phy01.py`、`inspect_d_screen.py`。各输出目录独占；**不能直接重跑这些脚本复用输出目录或授权次数**。
- C恢复到本轮开始前M0的离线方案见 job 中 `C-M0-reinstall-plan.json`；已验证预期全片与原当前M0一字节不差。要用 `unified_install.py --phase install`、冻结M0镜像、当前PHY安装回执及原始合法备份；不能不加区分地用旧 `--phase restore`，后者可能回到更早的 C44520，而非当前M0。**只做过离线验证，未执行恢复。**
- B的当前原件为本轮 `B-before-M1` 双读结果，B原M0镜像为41516 B / SHA `e452c2eafd07868c642c530c09c7ec31b07f919cb41886c849fe84b817644fcd`。回退是独立受控动作，不因本文件自动执行。
- D没有旧应用回退要求，首写只在RAM内比对原内容，保留原摘要而非另存旧应用；新安装后的完整回读/Options/身份在 EFS。禁止以此为由改写其他扇区、解除保护或整片擦除。

## 已完成的离线验证

C bench/PHY60协议、tick回绕及硬限时、取证队列/IRQ、CAN1隔离、仲裁ACK/失败/STOP、恢复负例共18项；五节点网关Host；解码16项（含60 s正负例）；串口入口14项；D首写范围/区外保留/保护/SHA/向量/默认不连接4项，均通过。D源和屏的差异是已保存的现场问题，不能用这些离线PASS覆盖。

恢复建议顺序：先确认断电与探针路由 → 查清 D P5/COM2 显示路径和 P6/CAN异常 → 以新的独占事务完成必要的正常60 Ω定向验证 → 满足进入条件才准备一次短时小报文40 Ω观察 → 断电恢复60 Ω和收尾。没有负责人“继续”之前只保持暂停，不自行开始任何一步。
