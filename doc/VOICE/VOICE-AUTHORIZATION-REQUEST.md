# 下一项现场卡：AUTH-VOICE-C-OFFLINE-BENCH-1（待负责人批准）

来源：[MPM-C-VOICE-001合同](</E:/多参数心电监护仪系统-样机开发/doc/P/05_第五阶段_云端AI语音与沙盘模型构建/合同/MPM-C-VOICE-001-TW-TTS-Codex-Execution-Contract.md>)第6节：“C J-Link/ROM 接入、读/擦/烧/复位”需要准确现场卡。当前执行文档与1W短测授权不被解释成未知镜像任意擦写许可。

目的：同一合同内用C作为等效完全离线测试源，先电气核对，再一次短句发声，最后恢复当次原sector0。该窗口不签发联网C整合/T3/T6通过。

## 绑定对象

- 工作区 `E:/medical-monitor-c-voice`；分支 `codex/gateway-c-tw-tts-v1-20261022`；实际提交HEAD由提交后的现场请求明确给出，源码/工具/候选SHA另见INPUT清单。批准后不得再变更代码再用旧许可。
- C STM32F407ZG，外部私有UID身份引用；不在Git保存UID。A/B断电、无人体连接；C的ESP断开、USB不接、原J5独立供电、J-Link只接C；BOOT0/1=GND。正常独立冷启动，不用SetPC/MSP/VTOR强起。
- 候选BIN `gateway/voice/build/offline-bench/c_voice_offline_bench.bin`：**3756B**，SHA256 **311032f64c7f6674f14410414504c99a3d4ae35dd0e7be0703a97715fca8ad30**。
- 实际写入块为BIN后补FF至16384B，SHA256 **0734d09ad8f7197d9afd940e4334a728db02ae40d6860ae68ad46faf9e577981**；精确范围 **0x08000000–0x08003FFF，只sector0**。
- 当前正式8883应用预期43172B/b9b25b18…；当前64KiB/49d3fad5…；generation3配置336B/395c6a36…，完整SHA见INPUT。任何身份/历史SHA不符先停，不猜测重刷。

## 操作顺序及范围

1. **先电气核对，不写Flash。** 负责人保持全部断电，核对P9 PA2/PA3丝印/P3已解除RS232/485跳接，A/B和人体源不在测试中。先只接TW-TTS G/V，喇叭和R/T暂不接；模块5V来自C已核验5V输出，ESP断开后短时给C上电，测5V、MCU3.3V和T对G的空闲电压；不明/越界即停。该步骤不代表已经具备电流/差分功率实测结果。
2. **合格后断电接线。** PA2→R，T→PA3（仅确认兼容后），GND→G，5V→V，喇叭两线→SPK±；SPK−不得接GND。按负责人本轮指令仅8Ω1W/v1短句，不升音量、不循环。用户需配合回报实际电压及异常，未回报不填PASS。
3. **只对C双读当次sector0–3共64KiB**，磁盘回读核验、身份/容量/RDP/options、sector7/11及FLASH_SR/CR核验；临时DBGMCU IWDG冻结位保存/恢复。数据仅入外部受限目录，窗口结束加密归档，不入库。双读和所有保护门禁通过才进行一次sector0写入；不解锁/修改options，不触及sector3，不mass erase，不自动重试。
4. 读回整个64KiB，应等于新sector0+原sector1–3；再比对sector7/11/options、身份及FLASH_SR/CR干净锁定。工具结束HALT，不发GO。负责人断电拔J-Link，按原J5独立上电，2s后仅按一次WK_UP。固件先设置v1，41确认后发送固定“语音模块测试完成”；软件完成/模块接收/人工听到分开记录。再次按键仅尝试STOP，不重复播放。
5. 一次实际发声或明确无声结果后停止。记录人工可闻、失真/复位、实际电压/电流（无仪器项NOT_MEASURED），不采集录音。允许同窗口**人工指令触发的一次原sector0恢复**：当前bench完整SHA、双读/保护门禁必须通过，用当次双备份的原16KiB恢复sector0，整个64KiB恢复49d3fad5…，sector3/7/11/options不变。恢复后断电拆TTS再正常启动原固件；无自动回退循环。

本卡许可时限：负责人明确批准起2小时、一次bench写入及一次有条件原sector0恢复；中途角色、镜像、保护区、电平、接线或Flash控制器状态异常立即停。异常不自动续时或扩大扇区。

残余边界：输出功率未实测，v1不证明≤1W；不能可靠测量功率时按本轮负责人短时试音指令保留此缺口。无实际电压前不连回传T；无模块接收/声学证据不报告播放通过。无USB-TTL工具，因此本卡使用显式无网络的C候选，不使用原生产UART或旧8884镜像。

本卡**不含**云端操作/下行、真实豆包调用、A/B烧录、麦克风、正式Security Gate、保护分支/标签改写、PR或新标签发布。
