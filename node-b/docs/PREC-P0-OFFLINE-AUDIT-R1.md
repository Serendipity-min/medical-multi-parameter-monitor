# PREC-001 P0：软件与历史证据离线审计 R1

2026-10-23，Asia/Shanghai。远端历史实测分支HEAD经ls-remote及独立fetch核实为bb9bc8e00860ff4f61fa3c4f315edfb76815a59b。独立工作区E:/medical-monitor-node-b-precan-closeout，分支codex/node-b-precan-closeout-20261023。本次离线审计完成，**CPU_ROOT_CAUSE_UNRESOLVED**；未连接任何硬件、未复位/刷机/切源，CAN集成暂停。

## 当前现场更正与证据范围

负责人最新报告：B已接串口屏但当前无波形变化，J-Link接电脑、开发板USB未接，SKX实际是普通心电60bpm。此前“保持呼吸24”的描述已被现场新事实覆盖，不擅自切回、不用当前普通ECG冒充独立RESP。屏幕静止不等于算法Flash消失，亦不能仅凭它判CPU一定在ROM。

原件包括37份SDK日志及对应心跳、IO、安装/故障/启动/ECG/RESP回执，完整审计清单与SHA见node-b/evidence/B-PREC-001/offline-audit-r1.json；SDK原文和原话只在EFS加密私有目录。既有ECG六窗、RR六窗206025帧/681次稳态观察、原生失败退出码不改。

## 已成立的事实

| 事实 | 直接证据 | 不能据此推断 |
|---|---|---|
| ROM暂停确实出现 | runtime-state-01两次连接真实R15=1FFF32F0、MSP20001940、VTOR1FFF0000、DHCSR00030003，CFSR/HFSR0 | ROM是冷启动、Close还是Connect造成 |
| Flash仍完整 | 整片f713277a…及options一致；ABI失败来自应用未按预期运行时的RAM | 算法被擦除、重新烧录能闭环 |
| 相关会话无显式reset/halt/go | e1-01/e1-02/rall20-01/runtime两连接的心跳与回执 | SDK内部未做调试控制、NRST从未发生脉冲、供电从未复位 |
| ROM状态并非始终暂停 | rall20-01运行PCSR多次落在ROM；后续另一次初态变Flash | 已确定发生转换的准确时刻或责任动作 |
| 正常器件复位后能运行 | 多个获批窗口核实真实Flash入口080001A0、MSP20002F30及采样推进 | 根因已解决、独立冷启动或关闭后也一定正常 |
| 复位标志是组合值 | 早期ROM快照RCC_CSR=0E000000，BOR/PIN/POR位为1、SFTRSTF为0 | 最后一次复位必然是哪一类，或可完全排除软件复位 |

RCC标志是粘滞记录，历史未清标志，没有逐事件时间轴；ROM/应用/SDK可能在首次读取之前产生或改变状态。DHCSR的S_RESET_ST还具有读后清除特性，SDK可能先读，不能用本层未看到该位证明没有复位。首次目标快照均在连接之后，现有证据没有“完全不连调试器”的真实PC/VTOR基线。

## 五条归因路径逐项审查

### BOOT、电源、NRST

STM32F407的BOOT脚在复位后时钟初期锁存，BOOT0低选择Flash；PB2当前GPIO值不是BOOT1上电锁存，专用BOOT0也不能由GPIOB读出。参见[ST RM0090](https://www.st.com/resource/en/reference_manual/dm00031020-stm32f405415xx-stm32f407417xx-stm32f427437xx-and-stm32f429439xx-advanced-armbased-32bit-mcus-stmicroelectronics.pdf)，本机旧版第69–70页（SHA67705a2183fe3427866215e0171dab586071c5712e10293f424763a85282ebcd）。

用户提供的神舟号V2.0六页板图SHA7737115dc272d6daff1f3bb08b7c8c23c10415c10bca57c3d72979adf53b46b2，第3/4页已目视复核：J5是三引脚DC插座，电源选择是K1，不能把J5误当三针选择跳帽；旧授权草案的这处解读在此更正，不重写历史。复位键、上拉/电容、JTAG的RESET#与CH340自动下载网络可能共用RESET；nTRST/PB4是另一信号，不能混成NRST。

BOOT跳帽路径包含串联电阻，CH340的RTS/DTR还经晶体管连到RESET/BOOT0。图纸CH340接板上+5V，**开发板USB未接不能单独证明该电路完全失电或没有输出**；但实物版本对应、电平及时序均未测，不能签为根因。现有万用表只能提供安全授权后的静态电平，不能证明复位锁存瞬间或捕获毛刺。初始取证卡不碰跳帽/电源/表笔。

### J-Link连接与关闭

37份SDK原件中，相关失败只见通用InitTarget及CoreSight识别，未提供可证明隐式reset有/无的底层总线记录。ForceAttachTarget是策略意图，不是零副作用的物理证明。SetRestartOnClose0禁止自动续跑，与reset不是同一含义；SetSkipDebugDeInit1用于保留调试状态。参见[SEGGER命令文档](https://kb.segger.com/J-Link_Command_Strings)。

实际回执显示SetRestartOnClose在Open前设0，Open后再次执行返回此前1，再确认0，说明不能只在Open前设置后就假设一直有效。历史工具已在Device前重新施加关键保护。早期e1-01的SetSkipDebugDeInit在Device之后才设置，后来runtime工具提前到Open前/后且Device之前；该次改进不证明此前由Close造成ROM。

候选systick.c以DWT CYCCNT实现阻塞延时，关闭调试状态有使DWT不推进的风险；这可形成“应用仍在Flash但采样/界面停滞”的竞争解释，必须与ROM异常分开。不能凭DWT风险将PC=ROM归因。Type0复位为器件相关策略，并不是“仅改PC”；本轮不调用。参见[SEGGER复位策略](https://kb.segger.com/J-Link_Reset_Strategies)。

本轮新取证工具增加逐调用前/后序号、时间、命令参数、读取范围及返回值；只读调用仍会涉及调试控制，首次读值明确是连接后，不伪称前置无侵入状态。

### 映射、Fault与启动向量

Flash向量初始SP20002F30、Reset_Handler080001A1；已归档AXF/BIN与符号SHA核对，单独离线反汇编，不重新构建。Reset_Handler→SystemInit→__main→main；SystemInit正常配置VTOR08000000。CFSR/HFSR=0只排除当次所读Fault标志，不排除一切软件异常。

历史ROM暂停时0地址别名等于Flash头，且SYSCFG时钟未开，MEMRMP读0不能单独证明真实BOOT锁存；ROM或调试流程可能在观测前改变映射。别名/PC/VTOR必须联合记录，不能因别名Flash而否认真实ROM PC，也不能反过来推出唯一的软件跳转根因。

### 软件复位与ROM跳转

main.c第59–65行存在实际屏命令复位：queue_find_cmd取到完整EE…FFFCFFFF帧后，第二字节07触发NVIC_SystemReset。CRC16_ENABLE=0。冻结BIN反汇编08005AD0确实写AIRCR/SYSRESETREQ，不是未链接的源码猜测。

没有找到已链接应用中直接跳1FFFxxxx、强设ROM VTOR/MSP的显式路径；这不是穷尽性证明，不能排除损坏的返回地址/间接跳转。正常软件复位在正确BOOT锁存条件下应回应用，单有屏幕复位路径仍不足以解释ROM。没有屏→MCU输入抓包或触发时点，不能断言该路径已经执行。当前没有开发板USB连接，但屏幕UART输入路径仍存在，后续卡不发送07、不按屏幕复位按钮。

### 证据缺口与关闭条件

仍缺：调试器完全断开时应用确实启动/持续输出的独立证据；受控冷启动与人工NRST对照；连接前/后的连续外部观察；BOOT0/电源/NRST锁存时序；屏串口是否曾触发07；可复现机制与纠正措施的独立验证。理论、一次复位恢复、六窗RR成功都不能填这些缺口。

当前先提交[原态单连接取证卡](AUTH-B-PREC-P0-STATE-001-R1.md)，不改变现有状态。完成后按[单变量计划](PREC-P0-FIELD-CONTROL-PLAN-R1.md)逐卡申请；若不能复现或证实机制，始终CPU_ROOT_CAUSE_UNRESOLVED，P1不得越过P0启动。
