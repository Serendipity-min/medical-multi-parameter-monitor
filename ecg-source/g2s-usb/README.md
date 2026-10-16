# G2-S USB串口入口变体

本目录为MPM-ECG-G2S-001窗口内新增的S板专用入口。原G1 `src/`驱动、码表、启动平台和工程文件全部保持原字节。此目录不链接BIO_V2、不接B/ADS，不是原`ai_serial_console`固件。

## 为什么新增入口

现场决定完全不接J-Link。原G1程序依赖调试器写`g_source_requested_mode`切换模式，没有串口日志。仅USB下载原BIN不能完成模式实测。新增`main_usb.c`经USART1 PA9/PA10、板载CH340，以115200/8N1执行明确的模式命令并返回数字诊断。

`E:/stm32/ai_serial_console`的现有MCP固定烧录另一控制台BIN和目标，不可用于本S源候选；不替换它的BIN、不改它的目标绑定或服务。复用已安装的stm32loader 0.7.1和pyserial 3.5，在本目录新增独立ROM工具。其只读电子签名采用该库已说明的F4对齐256字节读法。

## 固件与串口行为

- 上电默认OFF，没有自动波形、自动轮播或自动复位恢复。
- 命令白名单：`info`、`status`、`off`、`bias`、`sine`、`ecg60`、`ecg90`，ASCII一行一条，以LF或CRLF结束。
- 不提供任意内存/寄存器/Flash运行时命令。未知文本拒绝，超长/二进制帧丢弃到LF并撤销输出，串口错误独立累计。
- 每次只处理一问一答。串口错误或TX超时撤销动态输出；G1的DMA/DAC故障锁存与历史计数不清零。
- 仅复制数字诊断的短临界区屏蔽中断；格式化、TX有界等待均在临界区之外，TIM6/DMA仍独立工作。没有新增周期日志中断。
- 数字计数、模式ACK不是示波器波形或物理电压证据。

## 脱机验证

```text
python ecg-source/g2s-usb/test_console.py
python ecg-source/g2s-usb/test_usb_rom.py
python ecg-source/g2s-usb/build_usb.py
```

构建在独立`ecg-source/build/usb-arm-<UTC>/`目录复制并冻结输入，保留失败/成功日志；不改G1 `artifacts/ecg-source/arm-summary.json`或旧Host回执。新摘要在`artifacts/ecg-source/g2s/`，固件二进制和完整构建目录只留本地。

## 硬件门禁与下载流程

只有现场确认S独立供电、P11两组DAC负载断开、无B/ADS/人体连接、供电实测通过和本轮窗口有效时才执行ROM工具。端口必须显式提供，不能以COM号代替硬件身份。

1. `usb_rom.py backup --port <S端口> --source-S-only`：查询芯片和容量，在私有目录绑定S身份；两次完整读取1MiB Flash并比较。任何NACK/短读/身份问题停止，不解除读保护。
2. `flash`动作必须显式给出双读备份目录、S专用构建目录和准确BIN SHA；确认ROM支持恢复所需GET/READ/WRITE/ERASE命令，并在同一连接内再次核对UID和全片原件，才允许擦除sector0。候选超过16KiB则停止，不自动扩大擦除范围。
3. 写入后完整读取1MiB，与“新sector0＋原其它sector”计划逐字节比对；失败不启动部分固件，保留恢复条件及原始证据。
4. `restore`动作只接受同UID绑定的完整双读备份，全片恢复并独立回读比较；Option/OTP不修改。恢复动作的真实执行与Host验证分开记录。

原Flash、UID、完整回读和异常详情只留`local-evidence/`，不提交。公开只保留脱敏状态、字节数及SHA。首次短UID读取失败的工具副本和日志保留，不将历史FAIL改成PASS。

若自动ROM进入阶段发生通信失败，停止自动重试及擦写。现场按S板丝印断电设置B0=3V3/B1=GND、接回USB_232并明确按RESET，收到现场确认后才可使用`--manual-boot`。该模式在打开端口前释放RESET并禁用自动BOOT0输出，不再自动切换这两根控制线。先执行不含擦写的`probe`，再核对同源身份及备份；烧录成功后仍须现场断电把B0恢复GND并重启，工具不会冒称已经恢复Flash启动。B板与P11其它跳帽均不涉及。

## 模式会话与仪表

```text
python ecg-source/g2s-usb/app_session.py --port <S端口>
```

该会话先核对`fw=ecg-source-usb-1`且初始OFF/无故障，之后逐条接受白名单。端口保持开启，供现场在同一模式下观察仪表；`quit`先请求OFF并记录是否得到确认，再关闭串口。会话不提供下载，源ROM工具不提供应用模式指令，避免串口配置串用。

按已核验CH340自动下载电路，运行会话在打开端口前配置DTR=True（释放复位）、RTS=False（Flash启动）。这一组合不能泛化为所有板卡；实际初始OFF和固件身份必须由串口返回验证。串口ROM采用115200/8E1，不与应用的8N1混用。

DSO-153使用自身电池、不接充电/电脑USB，探头只接输入接口。确认实际S.GND后黑夹接GND、红夹接所需PA4或PA5；测量前按现场步骤确认。裸红黑夹线按1X，屏幕倍率也为1X；观察偏置及低频波形用DC耦合。1Hz/60/90模式初始建议200ms/div、500mV/div，再根据真实波形调量程和触发，不拿自动频率读数直接当QRS节律。

没有真实截图或独立样本时仍记DYNAMIC_UNVERIFIED。DMM平均值不能代替峰峰值/节律。任何电源、身份、备份、非预期负载或故障异常立即停止；不启动G2-A/G3。
