# G0板卡与输入核对

2026-10-15。文档/源码核对完成；硬件准入 **BLOCKED**。本轮零设备连接/测量，不能填写当前Flash身份、电压、通断或跳帽实测。

## 源板与采集板分开标记

| 信号 | 图纸/芯片核对 | 实物状态/门禁 |
| --- | --- | --- |
| S.PA4/DAC1 | STM32F407ZGT6 LQFP144芯片40脚；板级网STM_DAC，P11.5 | 来源板同型号仅用户确认；源板实物针脚/通断待核验 |
| S.PA5/DAC2 | 芯片41脚；板级网STM_ADC，P11.3 | 作为DAC2偏置候选，不能与B.PA5跨接 |
| S.P11 5–6 | 图纸5=STM_DAC，6=DS2＋R51 1kΩ到GND | 跳帽在位会加载波形DAC；未来窗口先照片核验，若在位需批准后断电取下 |
| S.P11 3–4 | 图纸3=STM_ADC，4=RJ2 10k电位器滑端 | 跳帽在位会加载/拉动DAC2；未来窗口需核验并处理，不忽略极端滑端负载 |
| S.P11 1–2 | 图纸TPAD与GND | 不用它作DAC接法，本轮不改 |
| S.J5/K1 | J5 DC 6～24V输入；K1按下外部DC、弹起USB | 用户拟用12V/1A；插头直流/极性、实际5V/3.3V、纹波未测 |
| S.SWD/VTref | VTref用于目标参考；用户计划烧录后断开源板探头 | 未接设备，不将VTref当供电或声称源板已浮地 |
| B.PG15 | 当前ADS驱动START；PA1不驱动START | 保持现有采集线，未移动 |
| B.PA5/PA6/PA7 | SPI SCLK/DOUT/DIN；PA0 PWDN、PA2 CS、PA3 DRDY | 保持已验收采集设计，不能为源板DAC改B.PA5 |
| 模块LA/ELA | 图纸ELA→R15 56k/保护RC→IN2P（芯片6脚） | 用户确认LA丝印；插头/适配线实际通断尚未测 |
| 模块RA/ERA | 图纸ERA→R4 56k/保护RC→IN2N（芯片5脚） | 用户确认RA丝印，适配线与图纸版本需核验 |
| 模块RL/RLD | RLDOUT经R5 0Ω、反馈及R10 100k→RLD外端 | 用户确认RL；G2/G3初期悬空绝缘，不连任何板GND或PA5 |

模块图纸A1接点1/2属于RLD，3/5属于ERA，4/6属于ELA；它们是图纸接点标号，**不是从插头正面猜出来的物理排列**。

P11重要核对来自开发板原理图第5页局部图；主电源为第3页，MCU/引出为第4页。图纸只作为连接依据，未认定两块实物完全同版。

## 供电与输入共模

模块V2.0图纸给出AVDD=AVDD_5V、AVSS=GND，数字DVDD_3V3；现行CONFIG2=E0选择内部参考缓冲，VREF_4V=0，名义2.42V；CH2SET=40增益4。**这些是图纸/字段/历史回读事实，实际电压未知。**

TI规定PGA共模范围依AVDD/AVSS、最大差分幅值和增益计算，不能统一固定成1.65V。示例仅作条件计算：若AVDD=5V、AVSS=0、gain=4、最大差分绝对值1mV，则按手册式(5)约为0.202～4.798V；不以该计算代替实测电源/共模。源板2048码也不等于已测1.65V。

最新正常B候选仍是EC/EA；初期共地源要求CC/2A的配置变更 **本轮未应用**。没有采集板当前Flash读取或安装记录，不声称板上运行最新通道修复BIN。

## G0缺口

- S板UID/原Flash、S板实物P11状态、接口/附件、实际HSE时基。
- 12V适配器标签/极性、两板供电路径、USB/J-Link/仪器参考回路、电源与偏置实测。
- 模块实际版本、RA/LA/RL适配线通断、AVDD/AVSS/VREF与输入共模。
- 万用表/波形测量设备、衰减/匹配电阻BOM及测得值。
- B板当前镜像身份，以及未来CC/2A候选的审批/构建/回读。

缺口只阻止G2/G3，不取消本轮明确授权的G1脱机实现。B板原件/源码已冻结保护，所有硬件信息空缺如实保留。

## 资料依据

本地板图/参考手册/模块图的SHA记录在资料身份清单。PDF、局部图片及实物照片不推送，避免未经确认分享资料。

[ST STM32F407数据手册，引脚表](https://www.st.com/resource/en/datasheet/dm00037051.pdf)；
[ST DAC机制应用笔记](https://www.st.com/resource/en/application_note/an4566-how-to-extend-the-dac-performance-on-stm32-mcus-stmicroelectronics.pdf)；
[TI ADS1292R，PGA范围/CONFIG2/RLD](https://www.ti.com/lit/ds/symlink/ads1292r.pdf)。
