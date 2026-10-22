# AUTH-B-PRECHECK-001 R2｜出现首批帧后的连续计数核验

2026-10-22 Asia/Shanghai，承接负责人既有采集排查授权，在实际访问前展示。START-PULSE-R2实际读到129IRQ/129帧，错误计数0，故跳过脉冲，GPIO写入0。该单点不代替连续采样验收，原件保存。

身份/候选/当前全Flash SHA、供电及未接源范围、11次约5秒RAM读取、SPI不干预和全部判据按 [PRECHECK R1](AUTH-B-PRECHECK-001-R1.md)。负责人新增确认模块ADS1292_V2.0、电源灯亮、J2为开发板5V共GND，J1空置；只见J1/J2，不能假定实物J3状态。

工具supervise_readback.py --operation precheck及更新precheck_b.py，使用已实测PathLink及SetSkipDebugDeInit=1保留DWT。固定DLL与卡/工具SHA冻结。整片Flash仍先读一次核完整SHA。

唯一新增运行动作：若连接后已HALTED，仅在CFSR/HFSR0且实际PC位于合同Flash候选范围时允许go最多1次；保存PC/MSP/XPSR，不改PC、不复位、不额外halt。读取故障寄存器/核寄存器范围同ADC-PATH R2。若ROM、fault、LOCKUP立即停止。此条件续跑后同会话直接观察5秒计数，不把会话间暂停当输入丢帧。

GPIO写=0、Flash/options写=0、ADS/SPI配置写=0、接源/改线/上断电=0。所有读取和统计均非人体OPEN_UNKNOWN，不计算准确率。普通SDK5s、Flash45s、总180s监督，失败不重试。记录Close前状态，成功/STOP即失效。若连续采样通过，还需独立ECG接源电气/采集卡，不能直接签发HR PASS。
