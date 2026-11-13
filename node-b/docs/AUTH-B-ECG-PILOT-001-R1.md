# AUTH-B-ECG-PILOT-001 R1｜电池模拟源ECG60接线与10秒工程试采卡

2026-10-22 Asia/Shanghai。负责人已明确要求准备后连接模拟源、采集排查；本卡在任何接源动作前提交。操作者Codex /root执行软件，负责人执行物理断电/接线/开关/源菜单。没有操作者“已按卡接好并选普通ECG60、电池断USB”回复，不启动本卡软件采集。有效范围为本轮这一次接源和首个10秒窗口，结束或STOP失效；不覆盖正式HR矩阵或RESP。

## 当前实物与候选

- B：照片STM32F407ZGT6，实际DEV_ID413/1024KiB/RDP0/VTref3300mV，真实UID绑定受限READBACK身份。J-Link接B JTAG、仅调试、唯一探针/无其他程序；J5使用负责人确认YL-1210 12V1A中心正极，B0/B1均GND，不改接法/跳帽。
- 模块ADS1292_V2.0，J1空置，J2接开发板5V及共GND、灯亮；START→PG15、DRDY→PA3负责人确认。实际启动RREG缓存 `73 01 E0 F0 40 40 EC 00 FF EA 03 0F`，GPIO低两位允许输入变化；FF为未读LOFF_STAT。CH2 ECG增益4、CH1阻抗、RLD开启、250SPS。
- 当前候选BIN25284B SHA `438a8120f6df06ce219cdc30c0e5b697ac0e993f98d5a80521b10361536ae3ae`，实际完整Flash SHA `f713277a50a5ec8d8a93317f412d5ab1b754e5d619918e57e9efe9dceef24cbb`；原件独立双读SHA69d9efb0…/options及恢复副本受限封存。只使用自研BIO_V2，不换旧心电衍生呼吸程序。
- 未接源5秒249.94985SPS/错误0；10秒原码稳定导出2609帧，连续序号内缺口0、重复版本冲突0、8个起始pending保留。CH2削顶比例0、HR无效；CH1开路顶轨不作RR结论。
- 源为负责人已到手SKX-2000D+，可内置电池且能选普通ECG60BPM。机身固件/校准误差未提供，不声称外部校准或I导联精确1mV；本卡仅工程节律输入/原码检查。

## 接线设计与证据边界

| 这套实际夹子 | 模块设计网络 | 模拟器端子 |
|---|---|---|
| R红 | ERA→CH2 IN2N | RA / R |
| L黄 | ELA→CH2 IN2P | LA / L |
| F绿 | RLD主动反馈输出，经模块输出电阻 | RL / N |

依据为V2原理图、厂家同款模块RA/LA/RL演示及负责人同款线缆声明。资料级F→RLD已确认；夹子字母/颜色不是端到端通断实测，SKX旧款演示不等于本机D+兼容认证。本次明确为有界、非人体电池工程试接，兼容性仍需实际输入/异常观察，不预签完整电气PASS。若实际接点与表不符、不能明确辨认端子、异常发热/输出异常，停止，不猜接或桥接。

**LL/F及胸导全部空置。F绿不接LL/F，RL不接GND，不桥接LL/RL；不连接人体、A/C或CAN。**

## 负责人物理动作顺序

1. 先保持三个夹子悬空；关B的J5电源开关，拔下J-Link的电脑USB，使这次接线处于断电状态；不改JTAG排线/BOOT。模拟器先关闭，充电USB拔除，只用内置电池。
2. 仅按上表夹R→RA、L→LA、F→RL/N；确认LL/F与胸导空置、夹子之间没有互碰。若不能明确确认端子则停，不做带电试碰。
3. 开模拟器，选普通ECG60BPM，保持电池/无USB；开B既有J5供电，等待至少5秒，再接回同一J-Link电脑USB。保持CAN和人体断开。
4. 回复实际已完成条件。负责人可随时STOP；若见异常发热/电源异常，先关源/B电源并报告，不继续软件采集。

## Codex软件窗口

先把负责人实际回复保存为受限source-record：ENGINEERING_NONHUMAN、operator_ready、ORDINARY_ECG、reference_bpm60、battery_only、usb_disconnected、上表导联映射。其SHA与本卡/工具/profile一起冻结manifest；不把“可选60”当成“已输出60”。

入口supervise_readback.py --operation capture --seconds 10及capture_b.py。受限capture-profile-r3-02.json SHA `9d17280c4d918f50a3b3d0ce344bff98bf0072fdd20f5db6bd9547fcb305a6ab` 已绑定真实身份、整片Flash/options、BIN/ELF/符号、ARM ABI、全部入口工具及槽解析器。固定DLL9.86a SHA632d0d78…、单探针/VTref门/SWD1000kHz/禁止自动复位重试/关闭不go/保留DWT，均与未接源实板核验相同。

精确读取/状态次数与CAPTURE-OPEN-R1相同：起止整片Flash各1MiB及options16B核SHA；仅无fault的候选Flash暂停点条件go1；连续10秒读slots20001F30/3072约50ms一次，每约0.5秒独立保存diag20001AE4/120、stats2000018C/48、启动RREG缓存200001BC/12；结束halt1、确认暂停读完整RAM20000000/131072，同一RAM取head140及末127已发布槽；只有全部确认才末尾go1。总halt≤1、go≤2、reset0、Flash/options/GPIO/SPI配置写0。不同于“零扰动”采集，运行态影响如实记录。

普通调用5秒/整片45秒/RAM15秒、全会话240秒监督，失败保留且无自动恢复。原码/UID/Flash/RAM/源原始记录仅受限本地，公开脱敏摘要。活动RAM非原子，末尾有确认；pending/冲突不补点、不投票洗白。

本次10秒是接源输入检查：CH2若近满量程比例明显增加、出现持续大干扰、ADC错误/丢帧或源状态不符，停止进入正式矩阵，先定位输入。不以降低阈值制造PASS。保存raw和实板末帧filtered/quality诊断；逐样本filtered/峰事件只能另做精确C回放并标REPLAY。本卡不评医疗精度、逐峰敏感性、RESP或绝对幅值，也不以10秒取代60/90/120各30秒预热+60秒稳态×2。输入检查通过后再给出正式窗口卡及冻结速率判据。
